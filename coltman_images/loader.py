"""Build the transformer from the entry: FP8 projections, plain weights, census.

This module is the only place that opens the checkpoint. It builds the model on
the meta device, swaps every quantized projection for an `F8Linear`, and then
materializes every parameter once from the file. The transformer is never built
in bfloat16 and never copied: a 12.3 GB bf16 copy would not fit this card or
this machine, and the FP8 weights are the whole point (protocol section 6.2).

Two tensors in the file are root-level and carry an `unsloth_root::` prefix;
they map to the model parameters `cap_pad_token` and `x_pad_token`.

Guard 4 is `assert_census`: the measured census must equal the entry's
`expected_census`, and a census with no float8 weights fails on its own, because
that is the shape of a silent downgrade to a plain-precision load.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import resource
import time

import torch
from diffusers import ZImageTransformer2DModel
from safetensors import safe_open
from torch import nn

from .entry import Entry, load_entry
from .fp8 import F8Linear

logger = logging.getLogger(__name__)

QDATA_SUFFIX = "._weight_qdata"
SCALE_SUFFIX = "._weight_scale"
ROOT_PREFIX = "unsloth_root::"
ROOT_PARAMETERS = ("cap_pad_token", "x_pad_token")

CENSUS_KEYS = ("float8", "plain", "other", "total")

__all__ = [
    "CensusError",
    "assert_census",
    "census",
    "load_transformer",
]


class CensusError(Exception):
    """The loaded model is not the FP8 model the entry declares."""


def census(model: nn.Module) -> dict[str, int]:
    """Count the parameters of `model` by kind: float8, plain, other."""
    counts = {"float8": 0, "plain": 0, "other": 0}
    for _name, parameter in model.named_parameters():
        dtype = str(parameter.dtype)
        if "float8" in dtype:
            counts["float8"] += 1
        elif dtype in ("torch.bfloat16", "torch.float32"):
            counts["plain"] += 1
        else:
            counts["other"] += 1
    counts["total"] = counts["float8"] + counts["plain"] + counts["other"]
    return counts


def assert_census(observed: dict[str, int], entry: Entry) -> dict[str, int]:
    """Guard 4: the measured census must be the entry's census.

    Two failures are reported separately: a model with no float8 weight at all,
    and a census that differs from the entry in any count.
    """
    observed = {key: int(observed.get(key, 0)) for key in CENSUS_KEYS}
    expected = {key: int(entry.expected_census[key]) for key in CENSUS_KEYS}
    if observed["float8"] == 0:
        raise CensusError(
            "census: no Float8 weights in the loaded model — the load is a silent "
            f"downgrade to plain precision (observed {observed}, expected {expected})"
        )
    if observed != expected:
        differences = ", ".join(
            f"{key}: observed {observed[key]}, expected {expected[key]}"
            for key in CENSUS_KEYS
            if observed[key] != expected[key]
        )
        raise CensusError(f"census: does not match the entry — {differences}")
    return observed


def _target_name(key: str) -> str:
    """Map a checkpoint key to the name the loaded module expects."""
    if key.endswith(QDATA_SUFFIX):
        return key[: -len(QDATA_SUFFIX)] + ".weight"
    if key.endswith(SCALE_SUFFIX):
        return key[: -len(SCALE_SUFFIX)] + ".weight_scale"
    if key.startswith(ROOT_PREFIX):
        return key[len(ROOT_PREFIX) :]
    return key


def _read_config(entry: Entry) -> dict:
    config = json.loads(pathlib.Path(entry.components.transformer_config).read_text("utf-8"))
    # Left in, diffusers would hand the load to torchao, which was measured to
    # traverse the model and change nothing (protocol section 12).
    config.pop("quantization_config", None)
    return config


def load_transformer(entry: Entry, device: str | torch.device = "cpu") -> nn.Module:
    """Build the transformer from the entry's checkpoint and return it.

    The model is assembled on the meta device, so no bfloat16 copy of the
    projections is ever allocated. Each parameter is materialized exactly once,
    from the file, with its own dtype.

    `safetensors.get_tensor` hands back a view onto the memory-mapped file, so
    the weights live in page cache instead of being copied onto the heap: the
    load keeps RSS under 1 GiB, and the pages are read as they are first used.
    The checkpoint is a read-only input, so a mapping that outlives the file
    handle is exactly what we want.
    """
    checkpoint = pathlib.Path(entry.checkpoint)
    config = _read_config(entry)

    with torch.device("meta"):
        model = ZImageTransformer2DModel.from_config(config)

    quantized: dict[str, tuple[int, ...]] = {}
    scaled: set[str] = set()
    plain = 0
    roots: list[str] = []
    with safe_open(str(checkpoint), framework="pt", device="cpu") as handle:
        keys = list(handle.keys())
        for key in keys:
            if key.endswith(QDATA_SUFFIX):
                quantized[key[: -len(QDATA_SUFFIX)]] = handle.get_slice(key).get_shape()
            elif key.endswith(SCALE_SUFFIX):
                scaled.add(key[: -len(SCALE_SUFFIX)])
            elif key.startswith(ROOT_PREFIX):
                name = key[len(ROOT_PREFIX) :]
                if name not in ROOT_PARAMETERS:
                    raise CensusError(
                        f"checkpoint: root tensor {key!r} strips to {name!r}, which is not "
                        f"one of {ROOT_PARAMETERS}"
                    )
                roots.append(key)
            else:
                plain += 1

        if scaled != set(quantized):
            raise CensusError(
                "checkpoint: the quantized weights and their scales do not pair up — "
                f"{len(set(quantized) - scaled)} weight(s) without a scale, "
                f"{len(scaled - set(quantized))} scale(s) without a weight"
            )

        for prefix, shape in quantized.items():
            if len(shape) != 2:
                raise CensusError(
                    f"checkpoint: {prefix}{QDATA_SUFFIX} has shape {tuple(shape)}, "
                    "expected a 2D [out, in] weight"
                )

        replaced = 0
        with torch.device("meta"):
            for fqn, module in list(model.named_modules()):
                if not isinstance(module, nn.Linear) or fqn not in quantized:
                    continue
                expected_shape = (module.out_features, module.in_features)
                stored_shape = tuple(quantized[fqn])
                if stored_shape != expected_shape:
                    raise CensusError(
                        f"checkpoint: {fqn} stores {stored_shape}, the model expects "
                        f"{expected_shape}"
                    )
                parent_path, _, leaf = fqn.rpartition(".")
                parent = model.get_submodule(parent_path) if parent_path else model
                setattr(
                    parent,
                    leaf,
                    F8Linear(
                        module.out_features,
                        module.in_features,
                        bias=module.bias is not None,
                    ),
                )
                replaced += 1

        logger.info(
            "checkpoint: %d tensors — %d quantized (qdata + scale), %d plain, %d root remapped",
            len(keys),
            replaced,
            plain,
            len(roots),
        )

        state: dict[str, torch.Tensor] = {}
        for key in keys:
            name = _target_name(key)
            if name in state:
                raise CensusError(f"checkpoint: two tensors map to the state name {name!r}")
            state[name] = handle.get_tensor(key)

    expected_names = set(model.state_dict())
    unexpected = sorted(set(state) - expected_names)
    missing = sorted(expected_names - set(state))
    if unexpected:
        raise CensusError(
            f"checkpoint: {len(unexpected)} tensor(s) map to no parameter of the model: "
            f"{unexpected[:5]}"
        )
    if missing:
        raise CensusError(
            f"checkpoint: {len(missing)} parameter(s) have no tensor in the file: "
            f"{missing[:5]}"
        )

    model.load_state_dict(state, strict=True, assign=True)
    del state

    model.eval()
    model.requires_grad_(False)
    if torch.device(device).type != "cpu":
        model.to(device)

    logger.info(
        "loaded %d parameters (%d replaced by F8Linear, %d root tensors remapped)",
        sum(1 for _ in model.parameters()),
        replaced,
        len(roots),
    )
    return model


def _peak_rss_mib() -> float:
    # ru_maxrss is KiB on Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load the entry's transformer and report its census."
    )
    parser.add_argument("--entry", default=None, help="entry file (default: model/entry.yaml)")
    parser.add_argument(
        "--device", default="cpu", help="device to materialize on (default: cpu)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    entry = load_entry(args.entry)
    started = time.perf_counter()
    model = load_transformer(entry, device=args.device)
    elapsed = time.perf_counter() - started

    observed = census(model)
    print(json.dumps(observed))
    print(f"peak_rss_mib: {_peak_rss_mib():.1f}")
    print(f"elapsed_s: {elapsed:.2f}")

    assert_census(observed, entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
