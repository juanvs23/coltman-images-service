"""FLUX.2 [klein] 4B on the `ggml` path: the Q4_K_M GGUF, driven by `sd-cli`.

`ggml` is not readable by diffusers, and a second tensor loader inside Python
would be a third implementation of the same architecture. So this adapter is a
subprocess: it runs the vendored `stable-diffusion.cpp` binary with the artefacts
the entry declares and reads back the PNG the child wrote. Its stdout is the only
interface, and the child's own log is the only witness of what it did.

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
none is claimed: the census counts the artefacts handed to the child and their
bytes, which is what this adapter actually knows. For the same reason `load_s` is
zero — the child's load and its sampling are one call, and the protocol's load
boundary is not observable across it. `render_s` carries the child's whole wall
time, and the reference document says so (`docs/reference/flux2-klein.md`).
"""

from __future__ import annotations

import fcntl
import gc
import logging
import os
import pathlib
import subprocess
import time

from PIL import Image

from ..adapter import AdapterError
from ..entry import PROJECT_ROOT, Entry

logger = logging.getLogger(__name__)

RUN_DIR = PROJECT_ROOT / "run"
LOCK_FILE = RUN_DIR / "server.lock"
"""The instance mutex. Exactly the file the server takes in `server.main()`."""

OUTPUT_DIR = RUN_DIR / "sd"
"""Where the child writes. Inside the tree and inside `run/`, as section 2 allows."""

REQUIRED_COMPONENTS = ("cli", "vae", "llm")
"""The components this adapter needs: the binary, the VAE and the text encoder.

The diffusion model is the entry's `checkpoint`. The law does not know these
names; they are this adapter's declaration (protocol section 6.3).
"""

CENSUS_KEYS = ("artifacts", "bytes")
"""What this adapter's census counts: the files it hands the child, and their size."""

__all__ = ["CENSUS_KEYS", "Flux2KleinSdAdapter", "Flux2KleinSdError", "REQUIRED_COMPONENTS"]


class Flux2KleinSdError(Exception):
    """The subprocess path could not run, or the child produced no still."""


def _measure(entry: Entry) -> dict[str, int]:
    """The census this path can prove: which files went to the child, and how many bytes.

    It is measured, not declared: every file is `stat`ed on every call, so a
    replaced artefact changes the number the adapter reports and the entry's
    `expected_census` refuses it before a still is written.
    """
    files = [pathlib.Path(entry.checkpoint), entry.components.vae, entry.components.llm]
    total = 0
    for path in files:
        if not path.is_file():
            raise Flux2KleinSdError(f"census: {path} is not a file, so it cannot be handed to sd-cli")
        total += path.stat().st_size
    return {"artifacts": len(files), "bytes": total}


def _assert_census(observed: dict[str, int], entry: Entry) -> dict[str, int]:
    """The measured census must be the entry's census, before and after the child runs."""
    expected: dict[str, int] = {}
    for key in CENSUS_KEYS:
        if key not in entry.expected_census:
            raise AdapterError(
                f"expected_census: the flux2klein_sd adapter counts {list(CENSUS_KEYS)}; this "
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
            f"components: the flux2klein_sd adapter needs {list(REQUIRED_COMPONENTS)}; this "
            f"entry declares {sorted(entry.components.paths)} and is missing {missing}"
        )

    absent = [key for key in CENSUS_KEYS if key not in entry.expected_census]
    if absent:
        raise AdapterError(
            f"expected_census: the flux2klein_sd adapter counts {list(CENSUS_KEYS)}; this "
            f"entry declares {sorted(entry.expected_census)}, so {absent} cannot be compared"
        )
    if int(entry.expected_census["artifacts"]) < 1:
        raise AdapterError(
            "expected_census.artifacts: this path always hands the child the checkpoint, the "
            "VAE and the text encoder, so it cannot declare fewer than one artefact"
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
        raise Flux2KleinSdError(
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


class Flux2KleinSdAdapter:
    """FLUX.2 [klein] 4B behind the `ModelAdapter` contract, as one subprocess.

    Nothing stays loaded between requests: the child loads the quantised model,
    samples, decodes and exits, so the process holds no VRAM of its own. The
    warm part of this path is the page cache the child's first read fills.
    """

    name = "flux2klein_sd"

    def __init__(self, entry: Entry) -> None:
        self.entry = entry
        self.last_load_s = 0.0
        _refuse_incoherent_entry(entry)
        self._census: dict[str, int] = {}

    # --- the contract -------------------------------------------------------

    def prepare(self) -> None:
        """Check the runtime is runnable and establish the census, before the port binds.

        Nothing is loaded onto the card: the child does its own loading per
        request. What is refused here is a declared runtime that cannot run — an
        entry can name a binary that exists and is not executable, and that is an
        undeclared capability like any other (protocol 6.1).
        """
        cli = pathlib.Path(self.entry.components.cli)
        if not os.access(cli, os.X_OK):
            raise AdapterError(
                f"components.cli: {cli} is not executable — the ggml runtime is installed "
                "inside the tree and built there; rebuild it or declare the binary you have"
            )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._census = _assert_census(_measure(self.entry), self.entry)
        logger.info(
            "census: %s — %s driven by %s",
            self._census,
            pathlib.Path(self.entry.checkpoint).name,
            cli.name,
        )

    def census(self) -> dict[str, int]:
        """The census this adapter last measured."""
        return dict(self._census)

    def encode(self, prompt: str) -> str:
        """Hand the prompt through: the child tokenises and encodes it.

        `sd-cli` takes `-p <prompt>` and owns the encoder, so there is no feature
        tensor to carry across this boundary. The value this adapter returns is
        the prompt itself, which is the honest shape: the child is the model.
        """
        self.last_load_s = 0.0
        return prompt

    def denoise(
        self, features: object, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        """Run one `sd-cli` generation and read back the still it wrote.

        The child holds the card from the moment it starts until it exits, and
        `run/server.lock` is held across that whole window. `--offload-to-cpu`
        is unconditional: measured, it costs 0.6 s and returns 3254 MiB, which is
        the difference between fitting beside the operator's desktop and not
        (`docs/reference/flux2-klein.md`).
        """
        entry = self.entry
        prompt = str(features)
        destination = OUTPUT_DIR / f"{seed}-{width}x{height}.png"
        destination.unlink(missing_ok=True)

        command = [
            str(entry.components.cli),
            "--diffusion-model", str(entry.checkpoint),
            "--vae", str(entry.components.vae),
            "--llm", str(entry.components.llm),
            "-p", prompt,
            "--cfg-scale", repr(float(entry.guidance)),
            "--steps", str(int(steps)),
            "-W", str(int(width)),
            "-H", str(int(height)),
            "-s", str(int(seed)),
            "-o", str(destination),
            "--offload-to-cpu",
        ]

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
                raise Flux2KleinSdError(
                    f"sd-cli exited {completed.returncode} for {width}x{height}, seed {seed}: {tail}"
                )
            if not destination.is_file():
                tail = "\n".join(
                    (completed.stderr or completed.stdout or "").splitlines()[-6:]
                )
                raise Flux2KleinSdError(
                    f"sd-cli exited 0 but wrote no {destination}: {tail}"
                )
            with Image.open(destination) as handle:
                still = handle.convert("RGB")
        finally:
            if owned and lock is not None:
                _release_card(lock)
            destination.unlink(missing_ok=True)

        if still.size != (width, height):
            raise Flux2KleinSdError(
                f"sd-cli wrote {still.size[0]}x{still.size[1]}, the request asked for "
                f"{width}x{height}"
            )

        # The bytes it read are the bytes it declares: measured after the run, so
        # a file that changed under the child is caught rather than rendered.
        self._census = _assert_census(_measure(entry), entry)
        if self._census != before:
            raise Flux2KleinSdError(
                f"census: the artefacts changed while sd-cli ran ({before} → {self._census})"
            )
        logger.info(
            "sd-cli: %dx%d seed=%d steps=%d in %.2f s (census %s)",
            width,
            height,
            seed,
            steps,
            elapsed,
            self._census,
        )
        return still

    def close(self) -> None:
        """Nothing is held between requests: there is no model to release."""
        gc.collect()
