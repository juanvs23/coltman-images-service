"""The host declaration: what this deployment can afford, apart from what a model is.

`host.yaml` at the tree root is the machine's declaration, and it exists because
two numbers were living in the wrong place. `limits.max_pixels` and
`limits.steps` are facts about the card — the largest box it has been measured to
render, the step counts it tolerates — but they are declared inside each model's
entry, so moving the tree to another card would mean editing every entry by hand.
The host moves the deployment's half of that out: device memory, whether the
`ggml` path may offload to the CPU, and — optionally — limits tighter than the
served entry's.

The rule that keeps the pair honest points one way only: **a host may tighten,
never widen.** The effective `max_pixels` is the smaller of the host's and the
entry's; the effective step range is their intersection. A host that declares a
ceiling above the entry's, or a step range reaching outside it, is refused at
boot rather than clamped: the entry's number is a measurement, and a host is not
allowed to promise a box nobody rendered. Same for a host whose cap sits below
the entry's default box — boot refuses instead of silently shrinking every
default request, because the best box is the model's fact and the ceiling is the
machine's, and the system does not choose between them.

A missing `host.yaml` is not an error. The entry's own limits apply and the
system runs exactly as it did before this module existed — portability means a
tree without a host declaration still works. That is also what a direct
`render.render` call gets when it is not handed the effective limits: the host
binds at the door, and the door is `WarmServer.submit`.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

from .entry import LORA_BUDGET_MIB, PROJECT_ROOT, Entry

HOST_FILE = PROJECT_ROOT / "host.yaml"
"""Where the deployment's declaration lives. Never a flag, never an argument to
the CLI: the server reads it at boot, exactly as its reads the entry."""

# The closed envelope. `limits` and `lora_budget_mib` are the optional fields: a
# deployment that declares nothing tighter than the entry's numbers says so by
# leaving `limits` out, and the budget defaults to the measured linear arm.
_TOP_FIELDS = {"id", "vram_mib", "offload"}
_OPTIONAL_TOP_FIELDS = frozenset({"limits", "lora_budget_mib"})
_LIMIT_FIELDS = {"max_pixels", "steps"}
_STEP_LIMIT_FIELDS = {"min", "max"}

__all__ = [
    "HOST_FILE",
    "Effective",
    "Host",
    "HostError",
    "effective",
    "load_host",
    "offload",
]


class HostError(Exception):
    """The host declaration is malformed, or it would widen what it may not."""


def _refuse(message: str) -> HostError:
    return HostError(message)


def _exact_keys(
    name: str, given: Any, expected: set[str], optional: frozenset[str] = frozenset()
) -> None:
    """The entry's own rule, applied to this declaration: a closed key set."""
    if not isinstance(given, dict):
        raise _refuse(f"{name}: expected a mapping, got {type(given).__name__}")
    unknown = sorted(set(given) - expected - optional)
    missing = sorted(expected - set(given))
    if unknown:
        raise _refuse(f"{name}: unknown field(s) {unknown}")
    if missing:
        raise _refuse(f"{name}: missing field(s) {missing}")


def _positive(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise _refuse(f"{name}: expected a positive integer, got {value!r}")
    return int(value)


@dataclass(frozen=True, slots=True)
class Host:
    """What this deployment declares. `None` limits mean "the entry's own"."""

    id: str
    vram_mib: int
    offload: bool
    max_pixels: int | None
    steps_min: int | None
    steps_max: int | None
    lora_budget_mib: int = LORA_BUDGET_MIB
    source: pathlib.Path = HOST_FILE

    @property
    def declares_limits(self) -> bool:
        """Whether this host tightens anything, or only describes the machine."""
        return self.max_pixels is not None


@dataclass(frozen=True, slots=True)
class Effective:
    """The limits a request is validated against, at the door.

    It is the intersection of the host's declaration and the entry's, and it
    carries both sides so a refusal can say which one binds. `entry` is the
    resolved entry this deployment is serving; `host` is `None` when the tree has
    no host declaration, which is the portable case.

    `lora_budget_mib` is the deployment's LoRA budget, not the entry's: how much
    device memory a request's LoRAs may fill is a fact about the card, so it
    defaults to the measured linear arm and a host declares its own. It is a
    memory, not a count — the door sums the requested LoRAs' file sizes against
    it (sections 6.1 and 11).
    """

    max_pixels: int
    steps_min: int
    steps_max: int
    entry: Entry
    lora_budget_mib: int = LORA_BUDGET_MIB
    host: Host | None = None

    @property
    def tightened_pixels(self) -> bool:
        return self.max_pixels < self.entry.max_pixels

    @property
    def tightened_steps(self) -> bool:
        return (self.steps_min, self.steps_max) != (
            self.entry.steps_min,
            self.entry.steps_max,
        )

    @property
    def tightened_lora_budget(self) -> bool:
        return self.lora_budget_mib != LORA_BUDGET_MIB

    def pixels_note(self) -> str:
        """The sentence fragment a size refusal appends when the host binds."""
        if not self.tightened_pixels:
            return ""
        return (
            f" (host.yaml's cap; the entry measured {self.entry.max_pixels} px as the "
            f"largest box rendered on this card)"
        )

    def steps_note(self) -> str:
        """The sentence fragment a step refusal appends when the host binds."""
        if not self.tightened_steps:
            return ""
        return (
            f" (host.yaml's range; the entry declares "
            f"{self.entry.steps_min}..{self.entry.steps_max})"
        )

    def loras_note(self) -> str:
        """The sentence fragment a `lora` refusal appends when the host binds.

        The budget is the deployment's, so the note names it and the measured
        per-MiB behaviour the number rests on — the card spends +313 MiB of
        device memory for a 325 MB LoRA, linear to eleven, and from twelve the
        runtime plateaus and pays in time instead (section 11).
        """
        if not self.tightened_lora_budget:
            return ""
        return (
            f" (host.yaml's lora_budget_mib; this card spends +313 MiB of device memory for a "
            "325 MB LoRA, linear to eleven, and from twelve it plateaus and pays in time)"
        )


def load_host(path: str | pathlib.Path | None = None) -> Host | None:
    """Resolve and validate the declaration. `None` when the tree has none.

    A missing file is the portable case and not an error. Everything else is
    refused with the field and the value named, the way `load_entry` refuses a
    malformed entry: a closed key set, typed values, and no half-declared
    `limits` block.
    """
    source = HOST_FILE if path is None else pathlib.Path(path)
    if not source.is_file():
        return None
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _refuse(f"{source}: not valid YAML: {exc}") from exc

    _exact_keys("host", raw, _TOP_FIELDS, _OPTIONAL_TOP_FIELDS)

    host_id = raw["id"]
    if not isinstance(host_id, str) or not host_id:
        raise _refuse(f"id: expected a non-empty string, got {host_id!r}")
    vram_mib = _positive("vram_mib", raw["vram_mib"])
    offload_to_cpu = raw["offload"]
    if not isinstance(offload_to_cpu, bool):
        raise _refuse(f"offload: expected true or false, got {offload_to_cpu!r}")

    max_pixels: int | None = None
    steps_min: int | None = None
    steps_max: int | None = None
    # The budget defaults to the measured linear arm. `effective` refuses one
    # above the card's own memory: a budget is device memory, and a promise of
    # more of it than the machine reports is one it cannot keep.
    lora_budget_mib = LORA_BUDGET_MIB
    if "lora_budget_mib" in raw:
        lora_budget_mib = _positive("lora_budget_mib", raw["lora_budget_mib"])
    if "limits" in raw:
        limits = raw["limits"]
        _exact_keys("limits", limits, _LIMIT_FIELDS)
        max_pixels = _positive("limits.max_pixels", limits["max_pixels"])
        _exact_keys("limits.steps", limits["steps"], _STEP_LIMIT_FIELDS)
        steps_min = _positive("limits.steps.min", limits["steps"]["min"])
        steps_max = _positive("limits.steps.max", limits["steps"]["max"])
        if steps_min > steps_max:
            raise _refuse(f"limits.steps: min {steps_min} is above max {steps_max}")

    return Host(
        id=host_id,
        vram_mib=vram_mib,
        offload=offload_to_cpu,
        max_pixels=max_pixels,
        steps_min=steps_min,
        steps_max=steps_max,
        lora_budget_mib=lora_budget_mib,
        source=source,
    )


def effective(entry: Entry, host: Host | None = None) -> Effective:
    """The limits `entry` is served under on this deployment, or a refusal.

    The intersection, and never a widening: a host's ceiling above the entry's,
    or a step range reaching outside it, is refused here — at boot, before any
    weight is loaded — because the entry's numbers are measurements and a host
    may only narrow what they permit.

    Two conflicts inside the tightened set are refused too, both with the numbers
    named: a cap below the box the entry renders by default (the system will not
    silently shrink every default request), and a step range that excludes the
    entry's default count (a request that names no steps would render outside the
    range that bounds it, which is the invariant `load_entry` already enforces
    inside one entry).

    The LoRA budget follows the same coherence rule in its own dimension: it is
    device memory, so a host cannot dedicate more of it than the card it declares
    reports usable. It is a memory and not a count, and the door sums the
    requested LoRAs' file sizes against it (protocol sections 6.1 and 11).
    """
    if host is None:
        return Effective(
            max_pixels=entry.max_pixels,
            steps_min=entry.steps_min,
            steps_max=entry.steps_max,
            entry=entry,
            lora_budget_mib=LORA_BUDGET_MIB,
            host=None,
        )

    if host.lora_budget_mib > host.vram_mib:
        raise _refuse(
            f"lora_budget_mib: the host declares {host.lora_budget_mib} MiB for LoRAs on a card "
            f"it declares as {host.vram_mib} MiB — a budget is device memory, and a deployment "
            "cannot dedicate more of it than the card reports usable"
        )

    if host.max_pixels is None:
        # A host that describes only the machine tightens nothing but the budget.
        return Effective(
            max_pixels=entry.max_pixels,
            steps_min=entry.steps_min,
            steps_max=entry.steps_max,
            entry=entry,
            lora_budget_mib=host.lora_budget_mib,
            host=host,
        )

    assert host.steps_min is not None and host.steps_max is not None
    if host.max_pixels > entry.max_pixels:
        raise _refuse(
            f"limits.max_pixels: the host declares {host.max_pixels} px, above the "
            f"{entry.max_pixels} px entry {entry.id!r} measured on this card — a host may "
            "tighten what this deployment renders, never widen it; the entry's ceiling is a "
            "measurement, and a host is not allowed to promise a box nobody rendered. Lower "
            "the host's cap, or raise the entry's ceiling by measuring the larger box"
        )
    if host.steps_min < entry.steps_min or host.steps_max > entry.steps_max:
        raise _refuse(
            f"limits.steps: the host declares {host.steps_min}..{host.steps_max}, outside the "
            f"{entry.steps_min}..{entry.steps_max} entry {entry.id!r} declares — a host may "
            "tighten a step range, never widen it, because every count in the range must be "
            "one this model was measured at"
        )

    default_width = int(entry.defaults["width"])
    default_height = int(entry.defaults["height"])
    default_area = default_width * default_height
    if host.max_pixels < default_area:
        raise _refuse(
            f"limits.max_pixels: the host declares {host.max_pixels} px, below the "
            f"{default_width}x{default_height} box ({default_area} px) entry {entry.id!r} "
            "renders by default — lower the entry's defaults, or raise the host's cap; the "
            "best box is a model fact and the machine's ceiling is a host fact, and this "
            "system does not pick between them"
        )
    if not host.steps_min <= entry.steps <= host.steps_max:
        raise _refuse(
            f"limits.steps: the host declares {host.steps_min}..{host.steps_max}, which does "
            f"not contain the {entry.steps} steps entry {entry.id!r} renders by default — a "
            f"request that names no steps would render outside the range that bounds it; "
            f"widen the host's range to include {entry.steps}, or lower the entry's default "
            f"inside {host.steps_min}..{host.steps_max}"
        )

    warm_width, warm_height = int(entry.warmup["width"]), int(entry.warmup["height"])
    if warm_width * warm_height > host.max_pixels:
        raise _refuse(
            f"limits.max_pixels: the host declares {host.max_pixels} px, below the "
            f"{warm_width}x{warm_height} box ({warm_width * warm_height} px) entry "
            f"{entry.id!r} warms up at — the server would refuse its own boot"
        )

    return Effective(
        max_pixels=min(host.max_pixels, entry.max_pixels),
        steps_min=max(host.steps_min, entry.steps_min),
        steps_max=min(host.steps_max, entry.steps_max),
        entry=entry,
        lora_budget_mib=host.lora_budget_mib,
        host=host,
    )


def offload(host: Host | None = None) -> bool:
    """Whether the `ggml` path asks `sd-cli` for `--offload-to-cpu`.

    `True` when the tree has no host declaration, because that is what this
    service has always done: measured, the flag costs 0.6 s and returns 3254 MiB,
    which is the difference between fitting beside the operator's desktop and not
    (`docs/reference/flux2-klein.md`). A host that declares `offload: false` is
    the one way to turn it off, and the adapter reads the answer here rather than
    parsing YAML of its own. Passing `host` skips the file read.
    """
    if host is None:
        host = load_host()
    return True if host is None else host.offload
