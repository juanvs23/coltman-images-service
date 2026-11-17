"""The model entry: resolve it, validate it, and hand it to every component.

This module is the only reader of the entries — `model/entry.yaml` and every
`model/entries/*.yaml`. Nothing else in the system reads a path, a step count, a
guidance value or a census from anywhere but the object this module returns
(protocol section 9, rule 7).

An entry is chosen by its `id`: `find_entry` scans the promoted entry and the
entries directory, matches one `id`, and hands the file to `load_entry`. The id
is the model's alias on the command line (protocol sections 5.1 and 6.1), and
`--entry PATH` remains the development shortcut that skips the scan.

It validates the envelope and the shape, never the model. `components` is a map
of names the entry chooses to paths that must exist; `digests` pins whichever of
those files the entry wants pinned; `expected_census` is a map of names to
counts whose meaning belongs to the adapter. Which names an adapter needs is the
adapter's own declaration (protocol section 6.3) and this module never learns
one of them.

`loras` is the entry's **catalog**: the LoRAs this model may be asked for, under
aliases the caller uses and this entry owns (protocol section 6.1). A catalog is
per model — an entry without one accepts no LoRA at all — and a request names an
alias, never a path (section 4.1). What an alias is *applied* by, and in which
syntax, is the adapter's business (section 6.3); this module resolves aliases to
declared files and their weights, and knows no tag.

`image` is the entry's **reference capability**: how many images the model accepts
in, declared as `{max: N}` (sections 4.1 and 6.1). Absent, the entry accepts no
reference image and a request that carries one is refused by name. The field a
request carries is a list of absolute paths, the same shape as `out`; the one read
this system performs outside its own tree is declared in `CALLER_READ_EXEMPTIONS`
and printed by guard 8 beside the kernel exemption (section 2).

Asset paths are relative to the project root; an absolute path is allowed only
when the asset lives outside the tree (protocol section 6.1) — except a LoRA,
which lives inside the tree by declaration (section 6.1).
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
ENTRIES_DIR = PROJECT_ROOT / "model" / "entries"
"""Where the other entries live (protocol sections 3 and 6.1)."""

LORAS_DIR = PROJECT_ROOT / "model" / "assets" / "loras"
"""Where a model's LoRAs live: one folder per entry, named by its `id` (section 3).

Each model owns its LoRAs. That is not because a LoRA cannot be reused — a LoRA
whose base architecture matches will usually work on another checkpoint of that
architecture — but because **there is no certainty of it**: two checkpoints can
share a family and a module tree and still disagree, and a LoRA that silently
applies nothing is worse than one that is refused. Ownership by folder makes the
uncertainty visible: a LoRA verified on a second model is **copied** into that
model's folder, never shared by path (section 6.1).
"""

# The closed request vocabulary (protocol section 4.1). An entry declares the
# subset it accepts; nothing outside this tuple is ever a valid field.
VOCABULARY = ("prompt", "seed", "width", "height", "out", "steps", "upscale", "lora", "image")

CALLER_READ_EXEMPTIONS = {
    "image": (
        "a reference image is the caller's own file, named by path, and it may live "
        "outside this tree — the declared read exception that mirrors `out`'s write "
        "exception (protocol section 2). A path that arrives through the page is not "
        "this exception: gradio copies the upload into `run/ui/`, inside the tree"
    ),
}
"""The one thing a request may name that the system reads from outside its tree.

Section 2 says the system reads exactly one thing, its own tree, and names the
kernel's interfaces as the only exception that reaches outside. A request that
carries a reference image names a file the caller owns, and the caller may keep it
anywhere, so the read is a **declared exception** and not a silent pass: it is
declared here, by field name, and guard 8 prints it beside the kernel exemption it
already grants. `out` is the mirror image — a declared *write* exception — and it
is not in this mapping, because a write is not a read.

The page's path is not an exception at all: gradio copies the upload into its file
cache, which the server points at `run/ui/` inside the tree, so nothing leaves it.
"""

LORA_BUDGET_MIB = 3443
"""The device-memory budget a request's LoRAs may fill when no host declares one.

The constraint is memory, not a count: a 76 MB LoRA and a 325 MB LoRA are not one
unit each. Measured on this card on 2026-11-17, 512x512, eight steps, one 325 MB
LoRA duplicated by hardlink to get distinct paths: **each such LoRA costs +313
MiB of device memory and +1.5 s, linear to eleven** — 3443 MiB and 23.6 s, which
is the number below, and why it is what it is. **From twelve the memory plateaus
at ~7.6 GB and the wall time doubles** (39.9 s at 12, 51.0 s at 16), so past that
point the runtime stops growing and starts paying in time instead; there is no
out-of-memory failure anywhere up to sixteen.

This default is a memory, and it is the shadow of the largest count the linear
arm measured: a deployment that dedicates another amount declares it in
`host.yaml` (`lora_budget_mib`), and the door sums the requested LoRAs' file
sizes against that budget. It is declared here, once, because the request
vocabulary needs it when no host is present; the host reads it as its default.
"""

MIB = 1 << 20
"""Bytes in a mebibyte, the unit the budget is declared in."""

# The envelope every entry carries. `digests`, `loras` and `image` are the
# optional fields: an entry pins the components it wants pinned, declares a
# catalog only when its model may be asked for LoRAs, and declares a reference
# block only when its model accepts images in.
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
_OPTIONAL_TOP_FIELDS = frozenset({"digests", "loras", "image"})
_DEFAULT_FIELDS = {"width", "height", "format"}
_LIMIT_FIELDS = {"max_pixels", "steps"}
_STEP_LIMIT_FIELDS = {"min", "max"}
_WARMUP_FIELDS = {"width", "height", "prompt", "seed"}
_IMAGE_FIELDS = {"max"}
"""`image`: how many reference images the model accepts. One field, and the law's
fields stay closed: a model's capability is declared here, not inferred (section 6.1)."""
_LORA_FIELDS = {"path"}
_OPTIONAL_LORA_FIELDS = frozenset({"weight"})
_LORA_HIGH_NOISE_PREFIX = "|high_noise|"
"""Reserved by the runtime: a selection whose name starts with it is applied to
the high-noise half of a model. An alias may not start with it."""


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


@dataclass(frozen=True, slots=True)
class Lora:
    """One LoRA this entry declares: its alias, the file, its default weight, its size.

    `alias` is what a request names and `path` is the file that alias resolves
    to, both declared by the entry (protocol section 6.1). `weight` is the
    default a request inherits when it names the alias without one. `size_bytes`
    is the file's own size, measured with `stat` when the entry is resolved — a
    LoRA's cost is a memory, so the door sums these against the deployment's
    budget, and the number is the file's so that a LoRA replaced by a bigger one
    is refused without anyone editing a declaration. How the file is handed to
    the runtime — a tag, a flag, a directory — is the adapter's (section 6.3),
    and this object carries no syntax.
    """

    alias: str
    path: pathlib.Path
    weight: float
    size_bytes: int

    @property
    def mib(self) -> int:
        """The file's size in whole MiB, rounded up: what a budget is spent on."""
        return -(-self.size_bytes // MIB)


def _split_lora_item(item: Any) -> tuple[str, float | None]:
    """`alias` or `alias:weight` -> `(alias, weight or None)`.

    The one parser for the request's `lora` items, so validation and resolution
    cannot disagree about what an item means. A weight outside `(0, 1]` is
    refused — including a NaN or an infinity, which fail the comparison — and an
    alias may not contain `:` because that is the item's own separator.
    """
    if not isinstance(item, str) or not item:
        raise ValueError(f"expected alias or alias:weight, got {item!r}")
    alias, separator, raw = item.partition(":")
    if not alias:
        raise ValueError(f"{item!r}: the alias is empty")
    if not separator:
        return alias, None
    if ":" in raw:
        raise ValueError(f"{item!r}: expected alias or alias:weight — at most one ':'")
    try:
        weight = float(raw)
    except ValueError:
        raise ValueError(f"{item!r}: {raw!r} is not a weight") from None
    if not 0.0 < weight <= 1.0:
        raise ValueError(f"{item!r}: weight {raw} is outside (0, 1]")
    return alias, weight


def _lora_catalog(declared: Any, entry_id: str) -> dict[str, Lora]:
    """`loras`: alias -> {path, weight}. A closed set of aliases and fields.

    Every path is relative to the project root, stays **under this entry's own
    folder** `model/assets/loras/<id>/`, and must exist — a catalog entry is a
    declared asset like a component, checked at load, before any weight is
    loaded, so a missing one is exit 3. The folder is the ownership rule and not
    a convention: a LoRA belongs to the model it was verified on, so a path to
    another model's folder is refused with both the path and the folder it should
    have come from (sections 3 and 6.1).
    """
    _mapping("loras", declared)
    if pathlib.PurePosixPath(entry_id).name != entry_id or entry_id in (".", ".."):
        raise _refuse(
            f"loras: this entry's id {entry_id!r} names its LoRA folder, so it cannot contain a "
            "path separator or be a relative step — one id, one folder (protocol sections 3 and 6.1)"
        )
    own_folder = LORAS_DIR / entry_id
    own_relative = own_folder.relative_to(PROJECT_ROOT).as_posix()
    catalog: dict[str, Lora] = {}
    for alias, value in declared.items():
        if not isinstance(alias, str) or not alias:
            raise _refuse(f"loras: expected alias names, got {alias!r}")
        if any(character in alias for character in ":>"):
            raise _refuse(
                f"loras.{alias}: an alias cannot contain ':' or '>' — the runtime selects a "
                "LoRA from a prompt with <lora:name:weight>, so those two characters are its own"
            )
        if alias.startswith(_LORA_HIGH_NOISE_PREFIX):
            raise _refuse(
                f"loras.{alias}: the prefix {_LORA_HIGH_NOISE_PREFIX!r} is reserved by the "
                "runtime for the high-noise half of a model, so an alias may not start with it"
            )
        _exact_keys(f"loras.{alias}", value, _LORA_FIELDS, _OPTIONAL_LORA_FIELDS)
        raw_path = value["path"]
        if not isinstance(raw_path, str) or not raw_path:
            raise _refuse(f"loras.{alias}.path: expected a non-empty string, got {raw_path!r}")
        if pathlib.Path(raw_path).is_absolute():
            raise _refuse(
                f"loras.{alias}.path: expected a path relative to the project root, got "
                f"{raw_path!r} — a LoRA asset lives inside the tree (protocol section 2)"
            )
        path = _resolve(raw_path, f"loras.{alias}.path")
        resolved = path.resolve()
        try:
            inside = resolved.is_relative_to(PROJECT_ROOT)
        except OSError:
            inside = False
        if not inside:
            raise _refuse(
                f"loras.{alias}.path: {raw_path!r} resolves outside the project tree — a LoRA "
                "asset lives inside the tree (protocol section 2)"
            )
        if not resolved.is_relative_to(own_folder):
            raise _refuse(
                f"loras.{alias}.path: {raw_path!r} is not under {own_relative}/ — a LoRA belongs "
                f"to the model it was verified on, so entry {entry_id!r} may only name files in "
                "that folder. Reuse across models is possible but unverified, so a LoRA that "
                "works on a second model is copied into its folder, never shared by path"
            )
        if not path.is_file():
            raise _refuse(f"loras.{alias}.path: declared asset is missing: {path}")
        weight = value.get("weight", 1.0)
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            raise _refuse(f"loras.{alias}.weight: expected a number in (0, 1], got {weight!r}")
        weight = float(weight)
        if not 0.0 < weight <= 1.0:
            raise _refuse(f"loras.{alias}.weight: expected a number in (0, 1], got {weight!r}")
        catalog[alias] = Lora(
            alias=alias, path=path, weight=weight, size_bytes=path.stat().st_size
        )
    return catalog


@dataclass(frozen=True)
class Entry:
    id: str
    adapter: str
    checkpoint: pathlib.Path
    components: Components
    steps: int
    steps_min: int
    steps_max: int
    guidance: float
    max_pixels: int
    request_fields: tuple[str, ...]
    expected_census: dict[str, int] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    warmup: dict[str, Any] = field(default_factory=dict)
    loras: Mapping[str, Lora] = field(default_factory=dict)
    images_max: int = 0
    """How many reference images this model accepts; 0 means it accepts none.

    The capability is the entry's to declare (protocol sections 6.1 and 6.3): the
    adapter is what carries a reference to its runtime, and `load_adapter` refuses
    an entry that declares a count behind an adapter that cannot carry one, so a
    capability the system would ignore never becomes a request field.
    """
    source: pathlib.Path = DEFAULT_ENTRY

    def accepts(self, request: dict[str, Any], limits: Any | None = None) -> list[str]:
        """Return the validation failures for a request; empty means accepted.

        `limits` is the deployment's effective limits for this entry — the
        intersection of the host declaration and this entry, resolved once at
        boot by `coltman_images/host.py`. Absent, the entry's own limits apply,
        which is both the portable case (a tree with no `host.yaml`) and every
        call that predates the host declaration. The object is read for
        `max_pixels`, `steps_min`, `steps_max` and `lora_budget_mib` only; the law
        does not import the host and does not know what else it carries.
        """
        cap = self.max_pixels if limits is None else limits.max_pixels
        steps_min = self.steps_min if limits is None else limits.steps_min
        steps_max = self.steps_max if limits is None else limits.steps_max
        budget_mib = LORA_BUDGET_MIB if limits is None else limits.lora_budget_mib
        pixels_note = "" if limits is None else limits.pixels_note()
        steps_note = "" if limits is None else limits.steps_note()
        loras_note = "" if limits is None else limits.loras_note()

        problems: list[str] = []
        for key in sorted(request):
            if key in self.request_fields:
                continue
            if key == "image":
                # A field the model does not accept is refused by name, and this
                # one says why in the model's own terms: no reference capability
                # is declared, so there is nothing to send a picture to.
                problems.append(
                    "image: this entry accepts no reference image — a model declares how many "
                    "references it carries, and this one declares none (protocol sections 4.1 "
                    "and 6.1)"
                )
                continue
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
        if "steps" in request:
            steps = request["steps"]
            if not isinstance(steps, int) or isinstance(steps, bool):
                problems.append("steps: expected an integer")
            elif not steps_min <= steps <= steps_max:
                problems.append(
                    f"steps: expected an integer inside {steps_min}..{steps_max}, "
                    f"got {steps!r}{steps_note}"
                )
        out = request.get("out")
        if out is not None and (not isinstance(out, str) or not pathlib.Path(out).is_absolute()):
            problems.append("out: expected an absolute path")
        if "upscale" in request and not isinstance(request["upscale"], bool):
            problems.append("upscale: expected true or false")
        if "lora" in request and "lora" in self.request_fields:
            problems.extend(self._lora_problems(request["lora"], budget_mib, loras_note))
        if "image" in request and "image" in self.request_fields:
            problems.extend(self._image_problems(request["image"]))
        width = request.get("width", self.defaults["width"])
        height = request.get("height", self.defaults["height"])
        if (
            isinstance(width, int)
            and isinstance(height, int)
            and not isinstance(width, bool)
            and not isinstance(height, bool)
            and width * height > cap
            and not request.get("upscale")
        ):
            problems.append(
                f"size: {width}x{height} is {width * height} px, above the {cap} px this "
                f"deployment renders natively{pixels_note}; pass upscale: true to let the "
                "declared stage synthesize the rest"
            )
        return problems

    def dims(self, width: int | None, height: int | None) -> tuple[int, int]:
        return (
            width if width is not None else self.defaults["width"],
            height if height is not None else self.defaults["height"],
        )

    def _image_problems(self, declared: Any) -> list[str]:
        """The `image` field's failures: the shape, the count, and the files.

        The field carries **paths**, the same shape as `out`: the caller names a
        file and the system invents no transport (protocol section 4.1). The count
        is the entry's declaration — how many references *this model* accepts —
        so a request above it is refused with both numbers, and a path that does
        not exist is refused naming it, before any adapter is built. Nothing here
        reads the image: a file that cannot be opened at the door is a file the
        runtime would fail on later, with a worse sentence.

        An entry whose `request_fields` carry `image` with no count cannot reach
        this method: the loader refuses that pair, and a count of zero therefore
        means the field itself was refused before validation got here.
        """
        if not isinstance(declared, list):
            return [
                f"image: expected a list of absolute paths, got {type(declared).__name__}"
            ]

        problems: list[str] = []
        for item in declared:
            if not isinstance(item, str) or not item:
                problems.append(f"image: expected a non-empty path, got {item!r}")
                continue
            if not pathlib.Path(item).is_absolute():
                problems.append(
                    f"image: expected an absolute path, got {item!r} — the caller names the file, "
                    "as `out` does, and the system adds no transport of its own"
                )
        if problems:
            return problems

        if len(declared) > self.images_max:
            return [
                f"image: {len(declared)} reference images were given and this entry declares at "
                f"most {self.images_max} — the count is the model's capability, declared by its "
                "entry and refused at the door (protocol sections 4.1 and 6.1)"
            ]

        for item in declared:
            path = pathlib.Path(item)
            if not path.is_file():
                problems.append(
                    f"image: {item} does not exist — a reference image is a file the caller names, "
                    "and the door refuses a path it cannot serve (protocol section 4.1)"
                )
        return problems

    def _lora_problems(self, declared: Any, budget_mib: int, note: str) -> list[str]:
        """The `lora` field's failures: aliases, weights, repetition, and the budget.

        A request carries aliases, never paths (protocol section 4.1), so an
        alias the catalog does not declare is refused with the ones it does. The
        budget is a **memory**, not a count: the requested LoRAs' files are
        summed by the sizes measured when the entry was resolved, and a request
        above the deployment's budget is refused with the sum, the budget and the
        largest single LoRA the catalog declares — the arithmetic a caller can
        act on. The measured per-MiB behaviour behind the number is section 11.
        """
        if not isinstance(declared, list):
            return [f"lora: expected a list of alias or alias:weight, got {type(declared).__name__}"]
        if not self.loras:
            return [
                "lora: this entry declares no LoRAs, so it accepts none — a catalog belongs to "
                "the entry that declares it (protocol section 6.1)"
            ]

        problems: list[str] = []
        selected: dict[str, Lora] = {}
        repeated: set[str] = set()
        for item in declared:
            try:
                alias, _weight = _split_lora_item(item)
            except ValueError as exc:
                problems.append(f"lora: {exc}")
                continue
            if alias not in self.loras:
                problems.append(
                    f"lora: this entry declares no LoRA named {alias!r}; it declares "
                    f"{sorted(self.loras)}"
                )
                continue
            if alias in selected:
                if alias not in repeated:
                    repeated.add(alias)
                    problems.append(
                        f"lora: {alias!r} is named more than once in one request; name it once "
                        "with the weight you want"
                    )
                continue
            selected[alias] = self.loras[alias]

        total = sum(lora.size_bytes for lora in selected.values())
        if total > budget_mib * MIB:
            largest = max(self.loras.values(), key=lambda lora: lora.size_bytes)
            problems.append(
                f"lora: these {len(selected)} LoRAs need {-(-total // MIB)} MiB of device memory "
                f"and this deployment's budget is {budget_mib} MiB{note}; the largest single "
                f"LoRA in this catalog is {largest.alias!r} at {largest.mib} MiB. A LoRA's size "
                "is its file's, read from disk, so the budget is a memory and not a count"
            )
        return problems

    def resolve_loras(self, request: dict[str, Any]) -> tuple[Lora, ...]:
        """The catalog entries a request names, in the order it named them.

        Call it after `accepts`: the request is assumed valid, so every alias is
        declared and no alias repeats. A request that names an alias without a
        weight gets the catalog's own, which is the default the entry declares
        (protocol section 6.1).
        """
        selected: list[Lora] = []
        for item in request.get("lora") or ():
            alias, weight = _split_lora_item(item)
            declared = self.loras[alias]
            selected.append(
                declared
                if weight is None
                else Lora(
                    alias=alias,
                    path=declared.path,
                    weight=weight,
                    size_bytes=declared.size_bytes,
                )
            )
        return tuple(selected)

    def resolve_images(self, request: dict[str, Any]) -> tuple[pathlib.Path, ...]:
        """The reference files a request names, in the order it named them.

        Call it after `accepts`: every item is then a string, absolute, and a file
        that exists. The order is the caller's and it is preserved all the way to
        the runtime, because a reference's index is what the model conditions on.
        """
        return tuple(pathlib.Path(item) for item in request.get("image") or ())


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


def _image_block(declared: Any) -> int:
    """`image`: `{max: N}` — how many reference images this model accepts.

    One field, and the law's set stays closed. The count is the entry's because a
    capability is a property of the model: this tree serves a model that documents
    up to ten references, and the number is a declaration the door enforces, not a
    limit the core invents (protocol sections 4.1 and 6.1).
    """
    _exact_keys("image", declared, _IMAGE_FIELDS)
    maximum = declared["max"]
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        raise _refuse(f"image.max: expected a positive integer, got {maximum!r}")
    return int(maximum)


def _step_limits(declared: Any) -> tuple[int, int]:
    """`limits.steps`: exactly `min` and `max`, positive integers, `min <= max`."""
    _exact_keys("limits.steps", declared, _STEP_LIMIT_FIELDS)
    low, high = declared["min"], declared["max"]
    for name, value in (("min", low), ("max", high)):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _refuse(f"limits.steps.{name}: expected a positive integer, got {value!r}")
    if low > high:
        raise _refuse(f"limits.steps: min {low} is above max {high}")
    return low, high


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


def entry_files() -> list[pathlib.Path]:
    """Every entry file the alias scan reads: the promoted entry, then `model/entries/`.

    `model/entry.yaml` comes first because it is the promoted default, and the
    directory is read in sorted order so the same tree resolves the same way on
    every boot.
    """
    files: list[pathlib.Path] = []
    if DEFAULT_ENTRY.is_file():
        files.append(DEFAULT_ENTRY)
    if ENTRIES_DIR.is_dir():
        files.extend(sorted(ENTRIES_DIR.glob("*.yaml")))
    return files


def declared_id(path: pathlib.Path) -> str | None:
    """The `id` an entry file declares, or None when it is not readable as one.

    This is deliberately not `load_entry`: resolution must not hash a 6 GB
    checkpoint, and an entry the caller did not select has no say over this boot
    (protocol section 6.1) — a missing asset in another entry refuses only when
    that entry is selected. The selected file is validated in full by
    `load_entry`.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get("id")
    return value if isinstance(value, str) and value else None


def available_ids() -> list[str]:
    """Every alias this tree declares, sorted."""
    found = {entry_id for entry_id in (declared_id(path) for path in entry_files()) if entry_id}
    return sorted(found)


def find_entry(alias: str) -> pathlib.Path:
    """The entry file whose `id` is `alias`; refuses with the ids this tree has.

    The same refusal `load_adapter` makes for an unknown adapter: the caller
    named something this system does not have, and the message lists what it
    does have. One id, one entry — two files declaring the same id are a defect
    this refuses rather than resolves by order.
    """
    if not isinstance(alias, str) or not alias:
        raise _refuse(f"model: expected a non-empty entry id, got {alias!r}")
    matches = [path for path in entry_files() if declared_id(path) == alias]
    if not matches:
        known = ", ".join(available_ids()) or "none"
        raise _refuse(
            f"model: this system has no entry with id {alias!r} (known ids: {known}); "
            "entries live at model/entry.yaml and model/entries/*.yaml"
        )
    if len(matches) > 1:
        where = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in matches)
        raise _refuse(f"model: id {alias!r} is declared by more than one entry ({where}); one id, one entry")
    return matches[0]


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
    steps_min, steps_max = _step_limits(raw["limits"]["steps"])
    if not steps_min <= raw["steps"] <= steps_max:
        raise _refuse(
            f"steps: {raw['steps']} is outside limits.steps {steps_min}..{steps_max}; the default "
            "a request inherits must lie inside the range that bounds it"
        )

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
    # A catalog is per model and this entry owns it: the paths are checked here,
    # exactly as a component's is — under this entry's own folder, and present —
    # so a missing or borrowed LoRA refuses the boot instead of disappearing from
    # a still later (protocol sections 3 and 6.1).
    loras = _lora_catalog(raw["loras"], entry_id) if "loras" in raw else {}
    # A reference capability is the entry's declaration, and the two halves must
    # agree: a field nobody can use and a capability nobody can name are both
    # declarations the system would silently half-honour (section 6.1).
    images_max = _image_block(raw["image"]) if "image" in raw else 0
    if images_max and "image" not in fields:
        raise _refuse(
            f"image: this entry declares that it accepts {images_max} reference image(s) and its "
            "request_fields do not carry 'image' — a declared capability no request can use"
        )
    if "image" in fields and not images_max:
        raise _refuse(
            "request_fields: 'image' is accepted and this entry declares no image block — the "
            "count is the model's capability and the entry must declare it (protocol section 6.1)"
        )

    return Entry(
        id=entry_id,
        adapter=adapter,
        checkpoint=checkpoint,
        components=components,
        steps=raw["steps"],
        steps_min=steps_min,
        steps_max=steps_max,
        guidance=float(guidance),
        max_pixels=max_pixels,
        request_fields=tuple(fields),
        expected_census=census,
        defaults=dict(raw["defaults"]),
        warmup=dict(raw["warmup"]),
        loras=types.MappingProxyType(loras),
        images_max=images_max,
        source=source,
    )
