"""MOSS-Image DMD int8 on the `ggml` path: four artefacts, driven by `sd-cli`.

MOSS-Image is a quantised diffusion transformer with a separate GGUF text
encoder, the FLUX.2 VAE and an external tokenizer. Python's model stack reads
none of that combination — not the int8 checkpoint, not the Q4_K encoder, not the
vocabulary the encoder needs — and a second tensor loader inside Python would be
a second implementation of the same architecture. So this adapter is a
subprocess: it runs the vendored `stable-diffusion.cpp` binary with the artefacts
the entry declares and reads back the PNG the child wrote. Its stdout is the only
interface, and the child's own log is the only witness of what it did. The shape
is `flux2klein_sd`'s, because the situation is the same one.

The card is shared by construction, not by convention. `sd-cli` and this service
must never both load a model onto 8188 MiB, so this adapter takes `run/server.lock`
— the same `flock` the server holds for its whole life — before it starts the
child, and holds it for the child's whole lifetime. When the lock is already held
this adapter refuses with the holder's pid instead of starting a second model.
The one holder it accepts is **its own process's server**: a server that is
rendering this entry already owns the card, and the lock file carries that
server's pid, so the pid that holds the lock is the pid reading it.

What this path can and cannot report is declared rather than invented. The
subprocess owns the tensor graph, so there is no parameter census to take and
none is claimed: the census counts the four artefacts handed to the child and
their bytes, which is what this adapter actually knows. For the same reason
`load_s` is zero — the child's load and its sampling are one call, and the
protocol's load boundary is not observable across it. `render_s` carries the
child's whole wall time.

**A side that is not a multiple of 16 is refused, never rounded.** This model's
latents are a sixteenth of the frame: the FLUX.2 VAE downsamples by 8
(`ch_mult = {1, 2, 4, 4}`) and the decode unpacks a 2×2 patch per latent token
(`auto_encoder_kl.hpp`, `p = 2`). The child does not fail on a side off that grid
— it fits the frame to it and says so in its log. Measured 2026-11-19: asked for
520x500 the runtime wrote `align generation request up 520x500 to 528x512
(multiple=16)` (`request.cpp:224`) and produced a 528x512 PNG. So the adapter
refuses an off-grid width or height before the child starts, naming both numbers,
instead of returning a still nobody asked for — and the post-run size check
catches the same substitution a second time. The service's own door already
refuses a side that is not a multiple of 16; this is the rule at the adapter's
door too, because a direct `denoise` call does not pass the first one. That
constraint is MOSS-specific and is why this paragraph is here rather than in the
contract.

**LoRAs are applied through the runtime's only selection syntax: a prompt tag.**
`sd-cli` reads `<lora:NAME:WEIGHT>` out of `-p`, resolves `NAME` against
`--lora-model-dir`, and strips the tag before the prompt reaches the encoder
(`examples/common/common.cpp`, `extract_and_remove_lora`). So the selection rides
on the prompt the core hands `encode`, and this adapter turns each resolved
catalog entry into one tag whose `NAME` is that file's name **inside this entry's
own LoRA folder** — `--lora-model-dir` names that folder, which is where the
loader already requires every catalog path to live (`model/assets/loras/<id>/`,
protocol sections 3 and 6.1). Two consequences are declared rather than
discovered: the tag grammar cannot carry `:` or `>`, so a catalog path containing
either is refused at `prepare` instead of being silently mangled; and a tag
naming a file the child cannot find is **dropped with a warning and the render
continues**, so `denoise` re-checks the file's existence before it builds the
command — a declared asset that disappeared is an error, not a quiet still
without the LoRA. A request that names no LoRA adds neither the tags nor
`--lora-model-dir`, so its command line is exactly what it was before LoRAs
existed.

**Reference images are not carried, and the adapter says so.** MOSS-Image's
path here is text-to-image: nothing in this adapter hands the child a picture in,
so `supports_images` is `False` and an entry that declared a reference block
behind this adapter is refused at boot by `load_adapter` (protocol section 6.3).
`encode` also refuses a reference it is handed rather than dropping it, so a
capability this path does not have can only fail at the door, not at the still.

**The negative prompt is the one the model was measured with.** It is a constant
of this invocation and not of the caller: the law's entry envelope has no field
for it and the request vocabulary has none either, and the measurements this
entry's comments carry were taken with this exact string
(`run/p10-stage2/probe.py`). Changing it changes what was measured.
"""

from __future__ import annotations

import dataclasses
import fcntl
import gc
import logging
import os
import pathlib
import subprocess
import time

from PIL import Image

from .. import host as host_module
from ..adapter import AdapterError
from ..entry import LORAS_DIR, PROJECT_ROOT, Entry, Lora

logger = logging.getLogger(__name__)

RUN_DIR = PROJECT_ROOT / "run"
LOCK_FILE = RUN_DIR / "server.lock"
"""The instance mutex. Exactly the file the server takes in `server.main()`."""

OUTPUT_DIR = RUN_DIR / "moss"
"""Where the child writes. Inside the tree and inside `run/`, as section 2 allows."""

REQUIRED_COMPONENTS = ("cli", "vae", "llm", "tokenizer")
"""The components this adapter needs: the binary, the VAE, the encoder, the vocabulary.

The diffusion model is the entry's `checkpoint`. The law does not know these
names; they are this adapter's declaration (protocol section 6.3).
"""

CENSUS_KEYS = ("artifacts", "bytes")
"""What this adapter's census counts: the files it hands the child, and their size."""

LORA_SEPARATOR = (":", ">")
"""The two characters the runtime's `<lora:NAME:WEIGHT>` tag cannot carry.

`extract_and_remove_lora` matches `NAME` with `<lora:([^:>]+):([^>]+)>`, so a
nested `:` would split the wrong field and a `>` would end the tag early. A
catalog path holding either is refused at `prepare`, because a mangled tag is a
LoRA that silently does not apply.
"""

DIMENSION_MULTIPLE = 16
"""The model's latent grid, in pixels. A side off it is refused at the door."""

NEGATIVE_PROMPT = "(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch)"
"""The negative prompt the measurements behind this entry were taken with.

The law's entry envelope has no field for it, so it cannot be the entry's data;
it is declared here, once, so the command this adapter builds is the command the
recorded numbers describe (`run/p10-stage2/probe.py`, `docs/changelog.md`).
"""

LORA_APPLY_MODE = "at_runtime"
"""How the child applies a LoRA.

`auto` — the runtime's default — chooses this mode for a quantised checkpoint
anyway, because the int8 weights cannot be merged ahead of the graph; naming the
mode declares it instead of leaving it to the loader's inference. The
stage-2 measurements were taken in this mode (`run/p10-stage2/moss-image/`).
"""

__all__ = [
    "CENSUS_KEYS",
    "MossAdapter",
    "MossError",
    "REQUIRED_COMPONENTS",
]


class MossError(Exception):
    """The subprocess path could not run, or the child produced no still."""


@dataclasses.dataclass(frozen=True, slots=True)
class _Selection:
    """One request as the child needs it: the prompt and the LoRAs.

    This is the opaque value `encode` hands `denoise`. It exists because the
    selection has to cross that boundary without the adapter keeping state
    between requests: the server reuses one adapter for every still, so a field
    on `self` would be a selection that survives its request.
    """

    prompt: str
    loras: tuple[Lora, ...] = ()


def _lora_folder(entry: Entry) -> pathlib.Path:
    """The directory `--lora-model-dir` names: this entry's own LoRA folder.

    The loader already requires every catalog path to live under
    `model/assets/loras/<id>/` and nowhere else, so naming that folder is how the
    tags stay short and how a tag can never point at another model's file.
    """
    return LORAS_DIR / entry.id


def _lora_name(path: pathlib.Path, entry: Entry) -> str:
    """A LoRA's `NAME` in the runtime's tag: its name inside the entry's folder.

    Relative and POSIX-spelled, because `--lora-model-dir` is that folder: the
    child joins the two (`fs::u8path(dir) / fs::u8path(raw_path)`), so the name
    must not be absolute and must not depend on the host's separator.
    """
    return pathlib.Path(path).resolve().relative_to(_lora_folder(entry).resolve()).as_posix()


def _tagged(selection: _Selection, entry: Entry) -> str:
    """The prompt with one tag per selected LoRA, appended after it.

    The runtime removes the tags before encoding, so their position does not
    reach the model; appending keeps a prompt that already contains text exactly
    as the caller wrote it.
    """
    if not selection.loras:
        return selection.prompt
    tags = " ".join(
        f"<lora:{_lora_name(lora.path, entry)}:{repr(float(lora.weight))}>"
        for lora in selection.loras
    )
    return f"{selection.prompt} {tags}"


def _measure(entry: Entry) -> dict[str, int]:
    """The census this path can prove: which files went to the child, and how many bytes.

    It is measured, not declared: every file is `stat`ed on every call, so a
    replaced artefact changes the number the adapter reports and the entry's
    `expected_census` refuses it before a still is written.
    """
    files = [
        pathlib.Path(entry.checkpoint),
        entry.components.vae,
        entry.components.llm,
        entry.components.tokenizer,
    ]
    total = 0
    for path in files:
        if not path.is_file():
            raise MossError(f"census: {path} is not a file, so it cannot be handed to sd-cli")
        total += path.stat().st_size
    return {"artifacts": len(files), "bytes": total}


def _assert_census(observed: dict[str, int], entry: Entry) -> dict[str, int]:
    """The measured census must be the entry's census, before and after the child runs."""
    expected: dict[str, int] = {}
    for key in CENSUS_KEYS:
        if key not in entry.expected_census:
            raise AdapterError(
                f"expected_census: the moss adapter counts {list(CENSUS_KEYS)}; this "
                f"entry declares {sorted(entry.expected_census)}, so {key!r} cannot be compared"
            )
        expected[key] = int(entry.expected_census[key])
    if observed != expected:
        differences = ", ".join(
            f"{key}: observed {observed[key]}, expected {expected[key]}"
            for key in CENSUS_KEYS
            if observed[key] != expected[key]
        )
        raise AdapterError(f"census: does not match the entry — {differences}")
    return observed


def _refuse_incoherent_entry(entry: Entry) -> None:
    """Refuse an entry that cannot describe this path, before anything runs.

    A component this adapter needs and the entry does not declare, or a census
    whose keys it cannot measure, is `AdapterError` — the server's exit 3, the
    same exit a missing asset has always had (protocol 6.1, 6.3).
    """
    missing: list[str] = []
    for name in REQUIRED_COMPONENTS:
        try:
            getattr(entry.components, name)
        except AttributeError:
            missing.append(name)
    if missing:
        raise AdapterError(
            f"components: the moss adapter needs {list(REQUIRED_COMPONENTS)}; this "
            f"entry declares {sorted(entry.components.paths)} and is missing {missing}"
        )

    absent = [key for key in CENSUS_KEYS if key not in entry.expected_census]
    if absent:
        raise AdapterError(
            f"expected_census: the moss adapter counts {list(CENSUS_KEYS)}; this "
            f"entry declares {sorted(entry.expected_census)}, so {absent} cannot be compared"
        )
    if int(entry.expected_census["artifacts"]) < 1:
        raise AdapterError(
            "expected_census.artifacts: this path always hands the child the checkpoint and the "
            "three components beside it, so it cannot declare fewer than one artefact"
        )


def _refuse_off_grid(width: int, height: int) -> None:
    """Refuse a side this model's latent grid cannot hold, naming both numbers.

    The service's door refuses a side that is not a multiple of 16 before an
    adapter is built, so this is reachable only by a direct call — which is
    exactly why it exists: the adapter must not depend on a caller having passed
    another gate.
    """
    off = [
        f"{name} {value}"
        for name, value in (("width", width), ("height", height))
        if int(value) % DIMENSION_MULTIPLE
    ]
    if not off:
        return
    if len(off) == 1:
        detail = f"{off[0]} is not a multiple of {DIMENSION_MULTIPLE}"
    else:
        detail = f"{off[0]} and {off[1]} are not multiples of {DIMENSION_MULTIPLE}"
    raise MossError(
        f"size: {width}x{height} is off this model's {DIMENSION_MULTIPLE}-pixel grid — {detail}; "
        "MOSS-Image's latents are a sixteenth of the frame — the FLUX.2 VAE downsamples by 8 and "
        "its decode unpacks a 2x2 patch — so a side off that grid is not a box this model renders "
        "as asked"
    )


def _take_card() -> tuple[object, bool]:
    """Take `run/server.lock` for the coming child, or refuse.

    Returns `(handle, owned)`. `owned` is False when the lock is already held by
    *this* process's own server: that server owns the card and is the one
    running this adapter, so nothing must be taken or released. Any other holder
    is a stranger, and the child is not started.
    """
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        text = handle.read().strip()
        handle.close()
        holder = int(text) if text.isdigit() else None
        if holder == os.getpid():
            # This process's own server took the mutex before it resolved the
            # entry and holds it for its life. The card is already ours.
            return None, False
        who = f"pid {holder}" if holder is not None else "another process"
        raise MossError(
            f"card: {LOCK_FILE} is held by {who} — sd-cli must not load a model while another "
            "instance owns this card; stop it with `coltman-images stop` and retry"
        )
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle, True


def _release_card(handle: object) -> None:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
    except OSError:
        pass
    try:
        handle.close()  # type: ignore[attr-defined]
    except OSError:
        pass


def _command(
    entry: Entry,
    prompt: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    destination: pathlib.Path,
    offload: bool,
    loras: tuple[Lora, ...] = (),
) -> list[str]:
    """The child's command line, built from the entry and the host's declaration.

    Four artefacts go on the line, all of them the entry's: the int8 diffusion
    model, the VAE, the GGUF encoder and the tokenizer that encoder needs. The
    checkpoint is `--diffusion-model` and not `-m` because this model is
    components, not one file.

    `offload` is never decided here: it arrives from `coltman_images/host.py`,
    which owns what the deployment can afford, and `true` is what this service
    has always done. Under `--offload-to-cpu` the weights live in RAM and are
    loaded into VRAM when needed, which is what lets the child fit beside the
    operator's desktop (`host.yaml`).

    `loras` is the request's selection, resolved by the core against the entry's
    catalog. The runtime's only way to select one is a prompt tag, so each
    selection becomes `<lora:NAME:WEIGHT>` inside `-p`, and `--lora-model-dir`
    names this entry's own LoRA folder, which is inside the tree (protocol
    section 2). A request that names none adds neither the tags nor the flag, so
    its command line is exactly what it was before LoRAs existed.

    `--lora-apply-mode` and the negative prompt are constants of this
    invocation, not of the request: the first is the only mode that can apply a
    LoRA to int8 weights, and the second is the string the model's measurements
    were taken with. Both are declared at the top of this module.

    It is a function of its own so the flags' presence is observable without
    starting the child: a test can build both command lines and read them.
    """
    command = [
        str(entry.components.cli),
        "--diffusion-model", str(entry.checkpoint),
        "--vae", str(entry.components.vae),
        "--llm", str(entry.components.llm),
        "--tokenizer", str(entry.components.tokenizer),
    ]
    if loras:
        command += ["--lora-model-dir", str(_lora_folder(entry))]
    command += [
        "-p", _tagged(_Selection(prompt=prompt, loras=tuple(loras)), entry),
        "-n", NEGATIVE_PROMPT,
        "--cfg-scale", repr(float(entry.guidance)),
        "--steps", str(int(steps)),
        "-W", str(int(width)),
        "-H", str(int(height)),
        "-s", str(int(seed)),
        "-o", str(destination),
    ]
    if offload:
        command.append("--offload-to-cpu")
    command += ["--lora-apply-mode", LORA_APPLY_MODE]
    return command


class MossAdapter:
    """MOSS-Image DMD int8 behind the `ModelAdapter` contract, as one subprocess.

    Nothing stays loaded between requests: the child loads the four artefacts,
    samples, decodes and exits, so the process holds no VRAM of its own. The
    warm part of this path is the page cache the child's first read fills.
    """

    name = "moss"
    supports_loras = True
    """`sd-cli` selects a LoRA from a prompt tag, so this adapter applies one.

    Declared as a class attribute because `load_adapter` reads it before a still
    exists: an entry with a catalog behind an adapter without this flag is
    refused at boot (protocol section 6.3).
    """

    supports_images = False
    """This adapter carries no reference image, and says so.

    MOSS-Image's path here is text-to-image — it takes a prompt and seeded noise,
    and nothing in this adapter's command hands the child a picture in. An entry
    that declares a reference block and names this adapter is refused by
    `load_adapter` at boot, so a request never reaches a still that quietly
    ignored the picture it carried (protocol sections 6.1 and 6.3).
    """

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        self.last_load_s = 0.0
        _refuse_incoherent_entry(entry)
        # The host declaration is the owner of this fact, so it is read through
        # it and never parsed here; absent a host declaration it is `true`,
        # which is what this path did before the declaration existed.
        self.offload = host_module.offload()
        self._census: dict[str, int] = {}

    # --- the contract -------------------------------------------------------

    def prepare(self) -> None:
        """Check the runtime is runnable and establish the census, before the port binds.

        Nothing is loaded onto the card: the child does its own loading per
        request. What is refused here is a declared runtime that cannot run — an
        entry can name a binary that exists and is not executable, and that is an
        undeclared capability like any other (protocol 6.1). The entry's LoRA
        catalog is checked the same way: every file must exist (the law already
        did that) and every name must be expressible in the runtime's tag
        grammar, or the alias is one this path cannot apply.
        """
        cli = pathlib.Path(self.entry.components.cli)
        if not os.access(cli, os.X_OK):
            raise AdapterError(
                f"components.cli: {cli} is not executable — the ggml runtime is installed "
                "inside the tree and built there; rebuild it or declare the binary you have"
            )
        for alias, lora in self.entry.loras.items():
            name = _lora_name(lora.path, self.entry)
            if any(character in name for character in LORA_SEPARATOR):
                raise AdapterError(
                    f"loras.{alias}.path: {name} contains ':' or '>', which the runtime's "
                    "<lora:name:weight> tag cannot carry — rename the file, or move it so its "
                    "path is expressible"
                )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._census = _assert_census(_measure(self.entry), self.entry)
        logger.info(
            "census: %s — %s driven by %s; loras %s",
            self._census,
            pathlib.Path(self.entry.checkpoint).name,
            cli.name,
            sorted(self.entry.loras) or "none",
        )

    def census(self) -> dict[str, int]:
        """The census this adapter last measured."""
        return dict(self._census)

    def encode(
        self,
        prompt: str,
        loras: tuple[Lora, ...] = (),
        images: tuple[pathlib.Path, ...] = (),
    ) -> _Selection:
        """Carry the prompt and the LoRAs across the boundary.

        `sd-cli` takes `-p <prompt>` and owns the encoder, so there is no feature
        tensor to carry across this boundary; the value this adapter returns is
        the selection itself, which is the honest shape: the child is the model.
        The LoRAs are not applied here — they are applied by the command line
        `denoise` builds — but they arrive through this value so the adapter
        never keeps a selection on itself between requests. They are re-checked
        for the same reason the file was checked at the door: the child drops a
        tag whose file it cannot find and renders anyway, so a file that
        disappeared between the door and the child is an error with a sentence,
        not a still that quietly lacks the LoRA the caller asked for.
        """
        self.last_load_s = 0.0
        if images:
            raise MossError(
                f"image: this adapter carries no reference image and was handed "
                f"{len(images)} — MOSS-Image's path here is text-to-image, so a reference is "
                "refused rather than dropped (protocol sections 6.1 and 6.3)"
            )
        for lora in loras:
            if not pathlib.Path(lora.path).is_file():
                # The child drops a tag whose file it cannot find and renders
                # anyway. A declared asset that is gone is an error, not a still
                # that quietly lacks the LoRA the caller asked for.
                raise MossError(
                    f"loras: {lora.alias!r} resolves to {lora.path}, which is not a file — the "
                    "runtime would drop the tag and render without it"
                )
        return _Selection(prompt=prompt, loras=tuple(loras))

    def denoise(
        self, features: object, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        """Run one `sd-cli` generation and read back the still it wrote.

        The child holds the card from the moment it starts until it exits, and
        `run/server.lock` is held across that whole window. `--offload-to-cpu`
        follows the host declaration, because offloading is a fact about the
        deployment's memory and not about the model.

        A side that is not a multiple of 16 is refused before the child starts —
        the model's latent grid is 16 pixels, so a refused side is a box this
        model cannot render as asked (see the module docstring).

        `features` is the `_Selection` `encode` returned. A bare string is
        accepted as a prompt with no LoRA, so this method stays callable on its
        own (the guards build command lines and one test drives it directly).
        """
        entry = self.entry
        selection = features if isinstance(features, _Selection) else _Selection(str(features))
        _refuse_off_grid(width, height)
        destination = OUTPUT_DIR / f"{seed}-{width}x{height}.png"
        destination.unlink(missing_ok=True)

        command = _command(
            entry,
            selection.prompt,
            width,
            height,
            seed,
            steps,
            destination,
            self.offload,
            selection.loras,
        )

        before = _measure(entry)
        lock, owned = _take_card()
        began = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )
            elapsed = time.perf_counter() - began
            if completed.returncode != 0:
                tail = "\n".join(
                    (completed.stderr or completed.stdout or "").splitlines()[-12:]
                )
                raise MossError(
                    f"sd-cli exited {completed.returncode} for {width}x{height}, seed {seed}: {tail}"
                )
            if not destination.is_file():
                tail = "\n".join(
                    (completed.stderr or completed.stdout or "").splitlines()[-6:]
                )
                raise MossError(f"sd-cli exited 0 but wrote no {destination}: {tail}")
            with Image.open(destination) as handle:
                still = handle.convert("RGB")
        finally:
            if owned and lock is not None:
                _release_card(lock)
            destination.unlink(missing_ok=True)

        if still.size != (width, height):
            raise MossError(
                f"sd-cli wrote {still.size[0]}x{still.size[1]}, the request asked for "
                f"{width}x{height}"
            )

        # The bytes it read are the bytes it declares: measured after the run, so
        # a file that changed under the child is caught rather than rendered.
        self._census = _assert_census(_measure(entry), entry)
        if self._census != before:
            raise MossError(
                f"census: the artefacts changed while sd-cli ran ({before} → {self._census})"
            )
        logger.info(
            "sd-cli: %dx%d seed=%d steps=%d offload=%s loras=%s in %.2f s (census %s)",
            width,
            height,
            seed,
            steps,
            "on" if self.offload else "off",
            [lora.alias for lora in selection.loras] or "none",
            elapsed,
            self._census,
        )
        return still

    def close(self) -> None:
        """Nothing is held between requests: there is no model to release."""
        gc.collect()
