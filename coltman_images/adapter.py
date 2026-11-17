"""The model adapter contract and its registry.

The core — the entry, the server, the size plan, the output path and the
declared stage — knows a request and an entry. It does not know what a
checkpoint format is, how a text encoder is built, or which pipeline drives the
denoiser. That knowledge belongs to an adapter, and `model/entry.yaml` names the
one its entry uses.

This module is the boundary. It imports the entry and Pillow (for the still an
adapter hands back) and nothing from the model stack: no `diffusers`, no
`transformers`, no `safetensors`, and neither `coltman_images.loader` nor
`coltman_images.fp8`.
The adapter module named in the registry is imported only when `load_adapter`
resolves it, so importing the core never pulls the model stack into the process
(protocol section 6.3, guard 11).

The registry is a plain table, not a discovery mechanism: a second model is a
second line here plus a second entry, and the core does not change.
"""

from __future__ import annotations

import importlib
from typing import Protocol

from PIL import Image

from .entry import Entry, Lora

DEVICE = "cuda"
"""The one device this system renders on."""

_REGISTRY: dict[str, str] = {
    "zimage": "coltman_images.adapters.zimage:ZImageAdapter",
    "flux2klein_sd": "coltman_images.adapters.flux2klein_sd:Flux2KleinSdAdapter",
}
"""Adapter name → `module:attribute`. Resolved lazily by `load_adapter`.

Two rows, two different ways of owning a model: Z-Image's own FP8 loader, and
FLUX.2's quantised GGUF behind a subprocess. The core does not know which is
which — that is what the rows are for (protocol section 6.3).
"""

__all__ = ["DEVICE", "AdapterError", "ModelAdapter", "load_adapter"]


class AdapterError(Exception):
    """The entry names an adapter this system does not have, or it will not load."""


class ModelAdapter(Protocol):
    """What the core requires of every model.

    `prepare` warms the pieces that stay in RAM and establishes the census;
    `encode` turns a prompt — and the request's LoRA selection — into whatever
    `denoise` needs; `denoise` turns that opaque value, a shape, a seed and a
    step count into a still. The core never looks inside the value `encode`
    returns — that is the whole point of the boundary.

    `supports_loras` is the adapter's declaration that it can apply a catalog
    entry's LoRAs. It is not a hint: an entry that declares a catalog and names
    an adapter without it is refused at construction (protocol section 6.3), so
    a selector the runtime cannot honour never becomes a still that quietly
    ignored it.
    """

    entry: Entry
    name: str
    supports_loras: bool
    """Whether this adapter applies a request's LoRA selection (section 6.3)."""

    last_load_s: float
    """Seconds the last `denoise` spent putting its model on the card.

    Measured from the `encode` that preceded it, so it is the response's
    `load_s`: the text encoder plus the denoiser, outside the render. The core
    reads it to keep `load_s` and `render_s` on the boundaries section 4.2
    declares.
    """

    def prepare(self) -> None:
        """Make the warm, RAM-resident pieces ready and set the census."""
        ...

    def census(self) -> dict[str, int]:
        """The measured parameter census of the model this adapter loaded."""
        ...

    def encode(self, prompt: str, loras: tuple[Lora, ...] = ()) -> object:
        """Turn a prompt and the request's LoRAs into the opaque `denoise` value.

        `loras` is the request's selection, already resolved by the core against
        the entry's catalog and validated at the door — aliases, files and
        weights (section 4.1). How an adapter applies one is its own business
        (a tag, a flag, a separate pass); the core passes the selection and
        knows no syntax.
        """
        ...

    def denoise(
        self, features: object, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        """Render one still at `width`x`height` from `features`, `seed` and `steps`."""
        ...

    def close(self) -> None:
        """Drop everything this adapter holds and give the card back."""
        ...


def load_adapter(entry: Entry) -> ModelAdapter:
    """Resolve `entry.adapter` against the registry and build it.

    The adapter module is imported here, not at the top of this file, so a
    process that only imports the core never loads `diffusers` or
    `transformers`. An unknown name is refused with the names this system does
    have, like any other undeclared asset.

    An entry that declares a LoRA catalog is only servable through an adapter
    that applies one: the check is here because this is the one place an adapter
    is built, so the server's boot and the cold callable are both covered and
    the refusal is exit 3 before a weight is loaded (protocol section 6.3).
    """
    target = _REGISTRY.get(entry.adapter)
    if target is None:
        known = ", ".join(sorted(_REGISTRY))
        raise AdapterError(
            f"adapter: this entry names {entry.adapter!r}, which this system does not "
            f"have (known adapters: {known})"
        )

    module_name, _, attribute = target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AdapterError(
            f"adapter: {entry.adapter!r} needs {module_name}, which did not import: {exc}"
        ) from exc

    factory = getattr(module, attribute, None)
    if factory is None:
        raise AdapterError(
            f"adapter: {module_name} does not define {attribute!r}; the registry and "
            "the adapter module disagree"
        )
    adapter = factory(entry)
    if entry.loras and not getattr(adapter, "supports_loras", False):
        raise AdapterError(
            f"adapter: entry {entry.id!r} declares a LoRA catalog {sorted(entry.loras)} and the "
            f"{entry.adapter!r} adapter applies no LoRA — an entry that declares LoRAs its "
            "adapter cannot apply is refused at boot rather than silently ignored; remove the "
            "catalog or serve this entry through an adapter that applies it (protocol section 6.3)"
        )
    return adapter
