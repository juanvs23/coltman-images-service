"""One render: the core plans and writes; the adapter does the model.

This module is model-agnostic. It validates a request against the entry, decides
what the request actually costs (`_plan`: the size rendered and the size
delivered), picks the seed, resolves the output path, calls the entry's adapter
for the features and the still, runs the declared upscale stage when the request
permits it, and writes the PNG. Nothing here knows what a checkpoint format is,
which text encoder a model uses, or how its pipeline is assembled: that is the
adapter's (`protocol section 6.3`), resolved once from `entry.adapter`.

The stage runs after the render, never during it: the adapter gives the card
back first, and only then does the stage take it. A request may ask for a file
larger than the area this card can render natively; `upscale: true` is the
client permitting the stage, and it is the only way past the ceiling.

Nothing here reads a path, a step count, a guidance value or a census from
anywhere but the resolved entry (protocol section 9, rule 7).
"""

from __future__ import annotations

import dataclasses
import datetime
import gc
import logging
import pathlib
import secrets
import time
from typing import Any

import numpy as np
import torch
from PIL import Image

from .adapter import DEVICE, ModelAdapter, load_adapter
from .entry import PROJECT_ROOT, Entry
from .upscale import load_declaration, load_upscaler, upscale_tensor

logger = logging.getLogger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "out"
"""The default folder (protocol section 4.1, section 7)."""

__all__ = ["RenderError", "render"]


class RenderError(Exception):
    """The adapter could not be assembled, or produced no usable still."""


def _seed_or_pick(seed: int | None) -> int:
    """Absent seed means the system picks one and reports it (section 4.1)."""
    if seed is None:
        return secrets.randbits(32)
    return seed


def _output_path(out: str | None, seed: int) -> pathlib.Path:
    """Resolve the destination and create its parents.

    Absent `out` means `out/` at the project root, named by UTC timestamp and
    seed (protocol section 4.1).
    """
    if out is None:
        stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        path = OUTPUT_DIR / f"{stamp}-{seed}.png"
    else:
        path = pathlib.Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.absolute()


def _validate(entry: Entry, request: dict[str, Any]) -> None:
    """Refuse a bad request before any GPU work (guard 1's rule, applied here)."""
    problems = entry.accepts(request)
    if problems:
        raise ValueError("invalid request: " + "; ".join(problems))


@dataclasses.dataclass(frozen=True)
class _Plan:
    """What this request actually costs: the size rendered, the size delivered."""

    base_width: int
    base_height: int
    target_width: int
    target_height: int
    factor: int | None
    """`None` for a native render, so the stage is not even read from disk."""


def _base_size(max_pixels: int, width: int, height: int, unit: int = 16) -> tuple[int, int] | None:
    """The largest same-aspect size at or below `max_pixels`, snapped down to 16.

    The scale is searched as an integer numerator over a fixed grid rather than
    through a square root, so a ratio that lands exactly on the ceiling (2560x1440
    against 921600 is 0.5, not 0.4999999) produces the exact base instead of one
    step below it. The area is monotone in the numerator, so the search is a
    bisection on the largest numerator whose snapped area still fits.
    """
    grid = 1 << 16

    def snapped(numerator: int) -> tuple[int, int]:
        return (
            width * numerator // grid // unit * unit,
            height * numerator // grid // unit * unit,
        )

    low, high, best = 1, grid, None
    while low <= high:
        middle = (low + high) // 2
        base_width, base_height = snapped(middle)
        if base_width >= unit and base_height >= unit and base_width * base_height <= max_pixels:
            best = (base_width, base_height)
            low = middle + 1
        else:
            high = middle - 1
    return best


def _plan(entry: Entry, prompt: str, width: int, height: int, upscale: bool) -> _Plan:
    """Decide the render size and the delivered size, before any GPU work.

    The requested `width`/`height` are the file the client receives. Below the
    entry's ceiling that is also what gets rendered; above it the request needs
    the client's permission (`upscale: true`) and a base that still fits, or it
    is refused here — at the door, with the ceiling named, not mid-render.
    """
    area = width * height
    if area <= entry.max_pixels:
        return _Plan(width, height, width, height, None)

    declaration = load_declaration()
    factor = declaration.scale
    if not upscale:
        raise ValueError(
            "invalid request: size: "
            f"{width}x{height} is {area} px, above the {entry.max_pixels} px this entry "
            "declares as the largest area measured on this card; send upscale: true to let "
            f"the declared x{factor} stage supply the difference"
        )
    ceiling = entry.max_pixels * factor * factor
    if area > ceiling:
        raise ValueError(
            "invalid request: size: "
            f"{width}x{height} is {area} px, above the {ceiling} px the declared x{factor} "
            f"stage can serve (a {entry.max_pixels} px render, x{factor} on each side)"
        )

    base = _base_size(entry.max_pixels, width, height)
    if base is None:
        raise ValueError(
            "invalid request: size: "
            f"{width}x{height} leaves no same-aspect base at or below {entry.max_pixels} px"
        )
    base_width, base_height = base
    # The base is what the pipeline will be asked for, so it has to pass the
    # entry's own size rule. The entry owns that rule; this call is the check.
    problems = entry.accepts({"prompt": prompt, "width": base_width, "height": base_height})
    if problems:
        raise ValueError(
            "invalid request: size: the largest same-aspect base under the "
            f"{entry.max_pixels} px ceiling is {base_width}x{base_height}, which this entry "
            "refuses: " + "; ".join(problems)
        )
    return _Plan(base_width, base_height, width, height, factor)


def _as_tensor(image: Image.Image) -> torch.Tensor:
    """`[1, 3, H, W]` in `[0, 1]` from the decoded still."""
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).contiguous()


def _as_image(tensor: torch.Tensor) -> Image.Image:
    array = (tensor[0].clamp(0.0, 1.0).permute(1, 2, 0).numpy() * 255.0).round().astype(np.uint8)
    return Image.fromarray(array, "RGB")


def _enlarge(plan: _Plan, image: Image.Image) -> tuple[Image.Image, str]:
    """Run the declared stage, then resample to exactly the size requested.

    The stage produces x`factor`; the client asked for a size, not a factor, so
    the last step is a Lanczos resample of that enlargement. The module is
    dropped here — it was on the card only for this call.
    """
    up = load_upscaler()
    try:
        enlarged = _as_image(upscale_tensor(up, _as_tensor(image), device=DEVICE))
        model = up.id
    finally:
        up = None
        gc.collect()
        torch.cuda.empty_cache()
    target = (plan.target_width, plan.target_height)
    if enlarged.size != target:
        enlarged = enlarged.resize(target, Image.LANCZOS)
    return enlarged, model


def render(
    entry: Entry,
    prompt: str,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    out: str | None = None,
    upscale: bool = False,
    adapter: ModelAdapter | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Render one still and report what was measured.

    `seed=None` picks one and returns the value actually used. `width`/`height`
    are the size of the file the client receives and default from the entry.
    `out=None` writes into `out/` at the project root. `upscale=True` is the
    client permitting the declared stage to synthesize the pixels above this
    card's native ceiling; it is the only way past that ceiling.

    `adapter` is the warm adapter a server built at boot; when it is omitted the
    callable builds and prepares its own and closes it again, which is the cold
    path P2 exercises. `write=False` renders and discards the still, which is the
    warm-up: no file exists even for an instant.

    The returned `render_s` is the render alone and `upscale_s` the stage alone;
    the component loads it needed are reported separately as `load_s`, because
    this callable is cold by design and the server pays the load once instead.
    """
    width, height = entry.dims(width, height)
    plan = _plan(entry, prompt, width, height, upscale)
    request: dict[str, Any] = {"prompt": prompt, "width": width, "height": height}
    if seed is not None:
        request["seed"] = seed
    if out is not None:
        request["out"] = out
    if upscale:
        request["upscale"] = True
    _validate(entry, request)
    seed = _seed_or_pick(seed)
    destination = _output_path(out, seed) if write else None

    owned = adapter is None
    model = load_adapter(entry) if owned else adapter
    prepare_s = 0.0
    try:
        torch.backends.cudnn.benchmark = False
        if not torch.cuda.is_available():
            raise RenderError("render: no CUDA device — this system renders on the card")

        if owned:
            began = time.perf_counter()
            model.prepare()
            prepare_s = time.perf_counter() - began

        torch.cuda.reset_peak_memory_stats()

        started = time.perf_counter()
        features = model.encode(prompt)
        image = model.denoise(features, plan.base_width, plan.base_height, seed)
        finished = time.perf_counter()
        observed = model.census()
        # `last_load_s` covers the encoder and the denoiser, measured from the
        # start of `encode`; `render_s` is what is left — the loop and the
        # decode. Those are the two boundaries section 4.2 declares.
        load_s = prepare_s + model.last_load_s
        render_s = (finished - started) - model.last_load_s

        # The render is over. The adapter has released everything it held, and
        # only now does the upscale stage take the card — it never shares it
        # with the transformer.
        stage: dict[str, Any] | None = None
        if plan.factor is not None:
            began = time.perf_counter()
            image, stage_model = _enlarge(plan, image)
            stage = {
                "model": stage_model,
                "scale": plan.factor,
                "from": [plan.base_width, plan.base_height],
                "to": [width, height],
                "upscale_s": round(time.perf_counter() - began, 3),
            }

        if destination is not None:
            image.save(destination, format="png")
        del image
        gc.collect()
        torch.cuda.empty_cache()
    finally:
        if owned:
            model.close()

    logger.info(
        "render: %s %dx%d%s seed=%d render_s=%.2f load_s=%.2f peak_alloc_mib=%.0f "
        "peak_reserved_mib=%.0f",
        destination if destination is not None else "(discarded)",
        width,
        height,
        f" (base {plan.base_width}x{plan.base_height}, upscale_s={stage['upscale_s']})"
        if stage
        else "",
        seed,
        render_s,
        load_s,
        torch.cuda.max_memory_allocated() / 2**20,
        torch.cuda.max_memory_reserved() / 2**20,
    )
    return {
        "out": str(destination) if destination is not None else "",
        "seed": seed,
        "width": width,
        "height": height,
        "model": entry.id,
        "census": observed,
        "render_s": round(render_s, 3),
        "load_s": round(load_s, 3),
        "upscale": stage,
    }
