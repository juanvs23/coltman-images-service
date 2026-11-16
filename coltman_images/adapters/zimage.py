"""Everything this system knows about Z-Image, behind the adapter contract.

The core plans a request and writes a still; this module owns the model. Moved
here unchanged in behaviour from `render.py`: the text encoder build, the
scheduler, the VAE, the encode and the decode, the pipeline assembly, the
staging order, the caption dtype, the census measurement and the `torch.cuda`
housekeeping that keeps each model from sharing the card with the next.

The card is the constraint. The transformer alone occupies 6057 MiB of the 7857
MiB the device reports usable, and the int8 text encoder measures 4979 MiB: the
two do not fit together, so a request stages them — encode the prompt, drop the
encoder, build the transformer, sample, drop it, decode with the VAE. Peak
reserved stays under 7.4 GiB (6698 MiB at 1280x720).

`prepare` loads the tokenizer and the VAE and establishes the census before the
port binds; `encode` and `denoise` do the per-request work and release each
model before the next takes the card.
"""

from __future__ import annotations

# The FP8 linear's activation path asks the allocator for a 74-148 MiB float32
# block at every wide projection. PyTorch's default allocator caches by block
# size, so at 1280x720 the pool held 500 MiB it could not reuse while a 142 MiB
# request failed — measured with the operator's desktop holding 662 MiB of the
# card. Expandable segments make those blocks reusable: the same render then
# peaks at 6698 MiB reserved instead of failing.
#
# It has to be set before the CUDA allocator is initialised, and importing this
# module's third-party stack (optimum-quanto among them) is what would initialise
# it, so this line sits above every third-party import. `setdefault` never
# overrides a value the process already chose. The core imports `torch` first,
# but importing torch does not initialise the allocator; the first CUDA tensor
# does, and this module is imported by `load_adapter` before any of those.
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import base64
import gc
import json
import logging
import pathlib
import time
from typing import Any

import torch
from diffusers import AutoencoderKL, FlowMatchEulerDiscreteScheduler, ZImagePipeline
from optimum.quanto import QModuleMixin, QTensor, freeze, requantize
from PIL import Image
from safetensors import safe_open
from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM

from ..adapter import DEVICE, AdapterError
from ..entry import Entry
from ..loader import assert_census, census, load_transformer

logger = logging.getLogger(__name__)

TEXT_DTYPE = torch.bfloat16
"""The caption features' dtype — what the transformer's caption embedder expects."""

REQUIRED_COMPONENTS = (
    "transformer_config",
    "vae",
    "vae_config",
    "text_encoder",
    "text_encoder_dir",
    "scheduler_config",
)
"""The components this adapter needs. The law does not know these names; they are
the adapter's own declaration (protocol section 6.3), checked at construction so
a missing asset is exit 3 before any GPU work rather than a failure mid-render."""

CENSUS_KEYS = ("float8", "plain", "other", "total")
"""What this adapter's census counts. The entry's declaration must speak these names."""

__all__ = ["CENSUS_KEYS", "REQUIRED_COMPONENTS", "ZImageAdapter", "ZImageAdapterError"]


class ZImageAdapterError(Exception):
    """Z-Image's pieces do not fit the entry the adapter was handed."""


def _refuse_incoherent_entry(entry: Entry) -> None:
    """Refuse an entry that cannot describe this model, before anything is loaded.

    Two declarations are Z-Image's to check, not the law's: the components it
    builds from, and the census it must reproduce. Both are refused with
    `AdapterError`, which the server maps to exit 3 — the same exit a missing
    asset has always had, and still before a weight is read (protocol 6.1, 6.3).
    """
    missing: list[str] = []
    for name in REQUIRED_COMPONENTS:
        try:
            getattr(entry.components, name)
        except AttributeError:
            missing.append(name)
    if missing:
        raise AdapterError(
            f"components: the zimage adapter needs {list(REQUIRED_COMPONENTS)}; this entry "
            f"declares {sorted(entry.components.paths)} and is missing {missing}"
        )

    declared = entry.expected_census
    absent = [key for key in CENSUS_KEYS if key not in declared]
    if absent:
        raise AdapterError(
            f"expected_census: the zimage adapter counts {list(CENSUS_KEYS)}; this entry "
            f"declares {sorted(declared)}, so {absent} cannot be compared"
        )
    counts = {key: int(declared[key]) for key in CENSUS_KEYS}
    if counts["float8"] == 0:
        raise AdapterError("expected_census.float8: a model with no Float8 weights cannot load as FP8")
    if counts["float8"] + counts["plain"] + counts["other"] != counts["total"]:
        raise AdapterError(
            "expected_census: float8 + plain + other must equal total "
            f"({counts['float8']} + {counts['plain']} + {counts['other']} != {counts['total']})"
        )


class ZImageAdapter:
    """Z-Image behind the `ModelAdapter` contract.

    One instance is built at boot and reused: the tokenizer and the VAE stay in
    RAM, and each request builds and drops the text encoder and the transformer
    in the order the card requires.
    """

    name = "zimage"

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        self.last_load_s = 0.0

        # Construction is the door: a component this model needs that the entry
        # does not declare, or a census declaration this model cannot reproduce,
        # is refused here — before `prepare`, before a weight is read.
        _refuse_incoherent_entry(entry)

        self._tokenizer: Any = None
        self._vae: Any = None
        self._census: dict[str, int] = {}
        self._load_started = 0.0

    # --- the contract -------------------------------------------------------

    def prepare(self) -> None:
        """Load the warm pieces and establish the census before the port binds.

        The tokenizer and the VAE stay in RAM for the life of the process. The
        transformer is loaded once here, measured and asserted, and released
        immediately: the census is proof that the FP8 weights load, and it has
        to be true before `/health` can answer. The warm-up that follows reloads
        the same file from the page cache this load just filled, so it is not a
        second disk read.
        """
        self._tokenizer = AutoTokenizer.from_pretrained(
            str(self.entry.components.text_encoder_dir)
        )
        self._vae = _load_vae(self.entry)

        transformer = load_transformer(self.entry, device=DEVICE)
        self._census = assert_census(census(transformer), self.entry)
        del transformer
        gc.collect()
        torch.cuda.empty_cache()

    def census(self) -> dict[str, int]:
        """The census this adapter last measured."""
        return dict(self._census)

    def encode(self, prompt: str) -> list[torch.Tensor]:
        """Run the text encoder once and return the caption features.

        The encoder is built, used and dropped here so it never shares the card
        with the transformer. The load clock starts here: it is where the
        response's `load_s` begins.
        """
        self._load_started = time.perf_counter()
        encoder = _load_text_encoder(self.entry, DEVICE)
        # The pipeline owns the chat template; it is not re-implemented here.
        pipe = ZImagePipeline(
            scheduler=_scheduler(self.entry),
            vae=None,
            text_encoder=encoder,
            tokenizer=self._tokenizer,
            transformer=None,
        )
        try:
            with torch.no_grad():
                embeddings, _negative = pipe.encode_prompt(
                    prompt=prompt,
                    device=torch.device(DEVICE),
                    do_classifier_free_guidance=False,
                )
        finally:
            del pipe, encoder
            gc.collect()
            torch.cuda.empty_cache()
        # The checkpoint was trained with bf16 captions; transformers hands the
        # hidden state back in float32, and the transformer's caption embedder is
        # bf16, so the features are cast back to the dtype the regime was measured in.
        return [embedding.to(TEXT_DTYPE) for embedding in embeddings]

    def denoise(
        self, features: object, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        """Sample the latents at `steps` and decode them, releasing each model as it goes.

        The transformer is loaded, censused, used and dropped; only then does the
        VAE take the card for the decode. The VAE goes back to the CPU before
        this returns, because the next request starts with the text encoder.

        `steps` is the request's value or, when it named none, the entry's
        default — resolved by the core and passed in (protocol section 4.2). The
        weights are the same for every value, so the only thing that changes is
        how many forwards the loop runs.
        """
        entry = self.entry
        transformer = load_transformer(entry, device=DEVICE)
        self._census = assert_census(census(transformer), entry)
        pipe = ZImagePipeline(
            scheduler=_scheduler(entry),
            vae=self._vae,
            text_encoder=None,
            tokenizer=None,
            transformer=transformer,
        )
        generator = torch.Generator(device=DEVICE).manual_seed(seed)
        # Every weight the loop needs is resident now: hand the allocator's spare
        # blocks back to the driver. The loop asks for ~500 MiB of transient
        # activations at 1280x720 beside the 6057 MiB transformer, and a cache
        # still holding a few hundred idle megabytes is the difference between a
        # clean allocation and one that has to squeeze.
        torch.cuda.empty_cache()
        self.last_load_s = time.perf_counter() - self._load_started

        latents = None
        try:
            with torch.no_grad():
                latents = pipe(
                    prompt=None,
                    prompt_embeds=features,
                    height=height,
                    width=width,
                    num_inference_steps=steps,
                    guidance_scale=entry.guidance,
                    num_images_per_prompt=1,
                    generator=generator,
                    output_type="latent",
                    return_dict=False,
                )[0]
            # The forwards are done: release the transformer, and only now does
            # the VAE take the card.
            pipe.transformer = None
            del transformer
            gc.collect()
            torch.cuda.empty_cache()
            self._vae.to(DEVICE)
            image = _decode(self._vae, pipe.image_processor, latents)[0]
        finally:
            pipe.transformer = None
            del pipe
            gc.collect()
            torch.cuda.empty_cache()

        # The VAE goes back to the CPU: the next request starts with the encoder,
        # and the loop after that needs the room for its activations.
        self._vae.to("cpu")
        del latents
        del features
        gc.collect()
        torch.cuda.empty_cache()
        return image

    def close(self) -> None:
        """Drop the warm pieces and give the card back."""
        self._vae = None
        self._tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            try:
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
            except Exception as exc:  # noqa: BLE001 — a broken context must not block exit
                logger.warning("close: the CUDA context did not release cleanly: %s", exc)


# --- the model pieces -------------------------------------------------------
#
# These are the functions `render.py` used to own. They are unchanged: the move
# is the refactor, not a rewrite.


def _scheduler(entry: Entry) -> FlowMatchEulerDiscreteScheduler:
    config = json.loads(pathlib.Path(entry.components.scheduler_config).read_text("utf-8"))
    return FlowMatchEulerDiscreteScheduler.from_config(config)


def _load_text_encoder(entry: Entry, device: str) -> Qwen3ForCausalLM:
    """Build the int8 Qwen3 encoder from the entry's weights file.

    The file is named after its recipe, not `model.safetensors`, so
    `from_pretrained` cannot find it. The model is assembled on the meta device
    and its quantised layout is read from the file's own `quantization_map`,
    which is what optimum-quanto wrote it with: `requantize` is that recipe's
    loader, and it is the only path that materialises `_data` + `_scale` as a
    frozen quantised weight instead of dequantising to bfloat16 (an 8.6 GB copy
    this card does not have).

    The rope buffers are not in the file (`persistent=False`), so a meta-built
    model leaves them holding uninitialised memory after `requantize` — the
    first forward then returns NaN. They are recomputed from the same config.
    """
    directory = pathlib.Path(entry.components.text_encoder_dir)
    config = Qwen3Config.from_pretrained(str(directory))
    with torch.device("meta"):
        model = Qwen3ForCausalLM(config)

    with safe_open(str(entry.components.text_encoder), framework="pt", device="cpu") as handle:
        metadata = handle.metadata() or {}
        packed = metadata.get("quantization_map_base64")
        if packed is None:
            raise ZImageAdapterError(
                f"text_encoder: {entry.components.text_encoder} carries no "
                "quantization_map; the file is not an optimum-quanto checkpoint"
            )
        quantization_map = json.loads(base64.b64decode(packed))
        # `tie_word_embeddings: true` means the output head is not stored: the
        # file names it as a second name for the input embedding, and says so.
        tied = metadata.get("tied_weights_map_base64")
        tied_map = json.loads(base64.b64decode(tied)) if tied else {}
        state = {key: handle.get_tensor(key) for key in list(handle.keys())}

    requantize(model, state, quantization_map, device="cpu")
    # `requantize` loads with strict=False, so a key absent from the file would
    # leave uninitialised memory behind. Freezing first makes the module emit the
    # flattened `weight._data` / `weight._scale` keys, so the two key sets are
    # directly comparable and the mismatch is refused instead of rendered.
    freeze(model)
    aliases = {alias for targets in tied_map.values() for alias in targets}
    written = set(state)
    expected = set(model.state_dict()) - aliases
    del state
    if written != expected:
        missing = sorted(expected - written)[:5]
        unexpected = sorted(written - expected)[:5]
        raise ZImageAdapterError(
            "text_encoder: the file and the model disagree — "
            f"{len(expected - written)} key(s) missing ({missing}), "
            f"{len(written - expected)} unexpected ({unexpected})"
        )
    for name, module in model.named_modules():
        if (
            isinstance(module, QModuleMixin)
            and module.weight_qtype is not None
            and not isinstance(module.weight, QTensor)
        ):
            raise ZImageAdapterError(
                f"text_encoder: {name} is quantised but its weight is "
                f"{type(module.weight).__name__}, not a quantised tensor"
            )

    model.model.rotary_emb = type(model.model.rotary_emb)(config)
    model.tie_weights()
    for source, targets in tied_map.items():
        source_parameter = model.get_parameter(source)
        for alias in targets:
            if model.get_parameter(alias).data_ptr() != source_parameter.data_ptr():
                raise ZImageAdapterError(
                    f"text_encoder: {alias} is not tied to {source} — the output head "
                    "would run on uninitialised weights"
                )
    model.eval()
    model.requires_grad_(False)
    return model.to(device)


def _load_vae(entry: Entry) -> AutoencoderKL:
    """Build the decoding VAE from the entry's weights and config.

    The file is diffusers-formatted and bfloat16, which is how the reference
    pipeline ran it: this card's bf16 convolutions work and the decode is where
    the 1280x720 activations live.

    It stays on the CPU until the transformer is gone: 177 MiB of idle weights
    is 177 MiB the denoising loop cannot use, and the loop is the stage that is
    short of room.
    """
    config = json.loads(pathlib.Path(entry.components.vae_config).read_text("utf-8"))
    vae = AutoencoderKL.from_config(config)
    with safe_open(str(entry.components.vae), framework="pt", device="cpu") as handle:
        state = {key: handle.get_tensor(key) for key in list(handle.keys())}
    vae.load_state_dict(state, strict=True, assign=True)
    del state
    vae.eval()
    vae.requires_grad_(False)
    return vae


def _decode(vae: AutoencoderKL, image_processor: Any, latents: torch.Tensor) -> Any:
    """Decode the sampled latents — the pipeline's own last three lines.

    They are repeated here only so the transformer can be released before the
    decode: the VAE's 1280x720 activations do not fit beside the 6057 MiB
    transformer, and the decode is the one stage that needs the room.
    """
    latents = latents.to(vae.dtype)
    latents = (latents / vae.config.scaling_factor) + vae.config.shift_factor
    image = vae.decode(latents, return_dict=False)[0]
    return image_processor.postprocess(image, output_type="pil")
