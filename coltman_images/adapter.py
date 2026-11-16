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

from .entry import Entry

DEVICE = "cuda"
"""The one device this system renders on."""

_REGISTRY: dict[str, str] = {
    "zimage": "coltman_images.adapters.zimage:ZImageAdapter",
}
"""Adapter name → `module:attribute`. Resolved lazily by `load_adapter`."""

__all__ = ["DEVICE", "AdapterError", "ModelAdapter", "load_adapter"]


class AdapterError(Exception):
    """The entry names an adapter this system does not have, or it will not load."""


class ModelAdapter(Protocol):
    """What the core requires of every model.

    `prepare` warms the pieces that stay in RAM and establishes the census;
    `encode` turns a prompt into whatever `denoise` needs; `denoise` turns that
    opaque value, a shape, a seed and a step count into a still. The core never
    looks inside the value `encode` returns — that is the whole point of the
    boundary.
    """

    entry: Entry
    name: str

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

    def encode(self, prompt: str) -> object:
        """Turn a prompt into the opaque features `denoise` consumes."""
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
    return factory(entry)
