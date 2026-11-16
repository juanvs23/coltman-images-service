"""The model entry: resolve it, validate it, and hand it to every component.

This module is the only reader of `model/entry.yaml`. Nothing else in the
system reads a path, a step count, a guidance value or a census from anywhere
but the object this module returns (protocol section 9, rule 7).

It validates the envelope and the shape, never the model. `components` is a map
of names the entry chooses to paths that must exist; `digests` pins whichever of
those files the entry wants pinned; `expected_census` is a map of names to
counts whose meaning belongs to the adapter. Which names an adapter needs is the
adapter's own declaration (protocol section 6.3) and this module never learns
one of them.

Asset paths are relative to the project root; an absolute path is allowed only
when the asset lives outside the tree (protocol section 6.1).
"""

from __future__ import annotations

import hashlib
import pathlib
import types
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_ENTRY = PROJECT_ROOT / "model" / "entry.yaml"

# The closed request vocabulary (protocol section 4.1). An entry declares the
# subset it accepts; nothing outside this tuple is ever a valid field.
VOCABULARY = ("prompt", "seed", "width", "height", "out", "upscale")

# The envelope every entry carries. `digests` is the one optional field: an
# entry pins the components it wants pinned and nothing forces it to pin one.
_TOP_FIELDS = {
    "id",
    "adapter",
    "checkpoint",
    "components",
    "steps",
    "guidance",
    "limits",
    "request_fields",
    "expected_census",
    "defaults",
    "warmup",
}
_OPTIONAL_TOP_FIELDS = frozenset({"digests"})
_DEFAULT_FIELDS = {"width", "height", "format"}
_LIMIT_FIELDS = {"max_pixels"}
_WARMUP_FIELDS = {"width", "height", "prompt", "seed"}


class EntryError(Exception):
    """The entry is malformed, or an asset it declares is not usable."""


def _refuse(message: str) -> EntryError:
    return EntryError(message)


def _exact_keys(
    name: str, given: Any, expected: set[str], optional: frozenset[str] = frozenset()
) -> None:
    if not isinstance(given, dict):
        raise _refuse(f"{name}: expected a mapping, got {type(given).__name__}")
    unknown = sorted(set(given) - expected - optional)
    missing = sorted(expected - set(given))
    if unknown:
        raise _refuse(f"{name}: unknown field(s) {unknown}")
    if missing:
        raise _refuse(f"{name}: missing field(s) {missing}")


def _mapping(name: str, given: Any) -> dict:
    if not isinstance(given, dict):
        raise _refuse(f"{name}: expected a mapping, got {type(given).__name__}")
    return given


def _resolve(path: Any, where: str) -> pathlib.Path:
    """Relative paths resolve against the project root; absolute stand alone."""
    if not isinstance(path, str) or not path:
        raise _refuse(f"{where}: expected a non-empty string, got {path!r}")
    p = pathlib.Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _digest_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class Components:
    """The entry's components, under the entry's own names.

    The law knows none of them. An adapter reaches the ones it needs by
    attribute (`entry.components.<name>`), so a name the entry does not declare
    raises `AttributeError` naming it, and the refusal arrives as a sentence
    instead of a bare `KeyError`.
    """

    paths: Mapping[str, pathlib.Path]

    def __getattr__(self, name: str) -> pathlib.Path:
        try:
            paths = object.__getattribute__(self, "paths")
        except AttributeError:  # not constructed yet: do not recurse into this method
            raise AttributeError(name) from None
        if name in paths:
            return paths[name]
        raise AttributeError(
            f"components: this entry declares no component named {name!r}; "
            f"it declares {sorted(paths)}"
        )


@dataclass(frozen=True)
class Entry:
    id: str
    adapter: str
    checkpoint: pathlib.Path
    components: Components
    steps: int
    guidance: float
    max_pixels: int
    request_fields: tuple[str, ...]
    expected_census: dict[str, int] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    warmup: dict[str, Any] = field(default_factory=dict)
    source: pathlib.Path = DEFAULT_ENTRY

    def accepts(self, request: dict[str, Any]) -> list[str]:
        """Return the validation failures for a request; empty means accepted."""
        problems: list[str] = []
        for key in sorted(request):
            if key not in self.request_fields:
                problems.append(f"{key}: not accepted by this entry")
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            problems.append("prompt: required and non-empty")
        for side in ("width", "height"):
            if side not in request:
                continue
            value = request[side]
            if not isinstance(value, int) or isinstance(value, bool):
                problems.append(f"{side}: expected an integer")
            elif value % 16 or value < 256:
                problems.append(f"{side}: expected a positive multiple of 16, at least 256")
        if "seed" in request and (
            not isinstance(request["seed"], int) or isinstance(request["seed"], bool)
        ):
            problems.append("seed: expected an integer")
        out = request.get("out")
        if out is not None and (not isinstance(out, str) or not pathlib.Path(out).is_absolute()):
            problems.append("out: expected an absolute path")
        if "upscale" in request and not isinstance(request["upscale"], bool):
            problems.append("upscale: expected true or false")
        width = request.get("width", self.defaults["width"])
        height = request.get("height", self.defaults["height"])
        if (
            isinstance(width, int)
            and isinstance(height, int)
            and not isinstance(width, bool)
            and not isinstance(height, bool)
            and width * height > self.max_pixels
            and not request.get("upscale")
        ):
            problems.append(
                f"size: {width}x{height} is {width * height} px, above the {self.max_pixels} px this "
                "entry renders natively; pass upscale: true to let the declared stage synthesize the rest"
            )
        return problems

    def dims(self, width: int | None, height: int | None) -> tuple[int, int]:
        return (
            width if width is not None else self.defaults["width"],
            height if height is not None else self.defaults["height"],
        )


def _components(declared: Any) -> Components:
    """`components`: free names, each a non-empty path. No name is known here."""
    _mapping("components", declared)
    paths: dict[str, pathlib.Path] = {}
    for name, value in declared.items():
        if not isinstance(name, str) or not name:
            raise _refuse(f"components: expected component names, got {name!r}")
        paths[name] = _resolve(value, f"components.{name}")
    return Components(paths=types.MappingProxyType(paths))


def _census(declared: Any) -> dict[str, int]:
    """`expected_census`: names to non-negative integers. The meaning is the adapter's."""
    _mapping("expected_census", declared)
    census: dict[str, int] = {}
    for key, value in declared.items():
        if not isinstance(key, str) or not key:
            raise _refuse(f"expected_census: expected string keys, got {key!r}")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise _refuse(f"expected_census.{key}: expected a non-negative integer")
        census[key] = int(value)
    return census


def _verify_digests(declared: Any, components: Components) -> None:
    """`digests`: optional. Every key names a component, every digest matches its file."""
    if declared is None:
        return
    _mapping("digests", declared)
    for name, digest in declared.items():
        if name not in components.paths:
            raise _refuse(
                f"digests.{name}: no component by that name; the entry declares "
                f"{sorted(components.paths)}"
            )
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise _refuse(f"digests.{name}: expected sha256:<hex>, got {digest!r}")
        asset = components.paths[name]
        if not asset.is_file():
            raise _refuse(f"digests.{name}: {asset} is not a file, so it has no digest")
        actual = _digest_of(asset)
        if digest != f"sha256:{actual}":
            raise _refuse(
                f"digests.{name}: mismatch — entry says {digest[7:19]}…, file is {actual[:12]}…"
            )


def load_entry(path: str | pathlib.Path | None = None) -> Entry:
    """Resolve and validate the entry. Raises EntryError on any defect."""
    source = pathlib.Path(path) if path is not None else DEFAULT_ENTRY
    if not source.is_file():
        raise _refuse(f"{source}: entry file not found")
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _refuse(f"{source}: not valid YAML: {exc}") from exc

    _exact_keys("entry", raw, _TOP_FIELDS, _OPTIONAL_TOP_FIELDS)
    _exact_keys("defaults", raw["defaults"], _DEFAULT_FIELDS)
    _exact_keys("limits", raw["limits"], _LIMIT_FIELDS)
    _exact_keys("warmup", raw["warmup"], _WARMUP_FIELDS)

    entry_id = raw["id"]
    if not isinstance(entry_id, str) or not entry_id:
        raise _refuse("id: expected a non-empty string")

    adapter = raw["adapter"]
    if not isinstance(adapter, str) or not adapter:
        raise _refuse("adapter: expected the name of a model adapter, got " + repr(adapter))

    for name in ("steps",):
        value = raw[name]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _refuse(f"{name}: expected a positive integer, got {value!r}")
    guidance = raw["guidance"]
    if not isinstance(guidance, (int, float)) or isinstance(guidance, bool):
        raise _refuse(f"guidance: expected a number, got {guidance!r}")

    max_pixels = raw["limits"]["max_pixels"]
    if not isinstance(max_pixels, int) or isinstance(max_pixels, bool) or max_pixels <= 0:
        raise _refuse(f"limits.max_pixels: expected a positive integer, got {max_pixels!r}")

    fields = raw["request_fields"]
    if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
        raise _refuse("request_fields: expected a list of strings")
    unknown = sorted(set(fields) - set(VOCABULARY))
    if unknown:
        raise _refuse(f"request_fields: outside the closed vocabulary: {unknown}")
    if "prompt" not in fields:
        raise _refuse("request_fields: prompt is required and must be accepted")

    components = _components(raw["components"])
    checkpoint = _resolve(raw["checkpoint"], "checkpoint")

    for name, asset in (("checkpoint", checkpoint), *components.paths.items()):
        if not asset.exists():
            raise _refuse(f"{name}: declared asset is missing: {asset}")

    _verify_digests(raw.get("digests"), components)
    census = _census(raw["expected_census"])

    return Entry(
        id=entry_id,
        adapter=adapter,
        checkpoint=checkpoint,
        components=components,
        steps=raw["steps"],
        guidance=float(guidance),
        max_pixels=max_pixels,
        request_fields=tuple(fields),
        expected_census=census,
        defaults=dict(raw["defaults"]),
        warmup=dict(raw["warmup"]),
        source=source,
    )
