"""P6 — the guards of protocol section 10, as an executable test matrix.

Runs under the production interpreter and the declared command:

    .venv/bin/python -m unittest discover -s tests -v

Every test runs under a per-test deadline — 420 s, `COLTMAN_TEST_DEADLINE_S` to change
it — that turns a hang into a failure naming the test instead of a run nobody can end,
and `tearDownModule` kills any `coltman_images.server` that outlived its guard and fails
if it found one. A guard that can hang the matrix, or leave the card taken, is a guard
whose green means nothing.

Two classes, because the matrix has two kinds of guard.

`ContractCase` needs no service: it reads the tree (guard 8), asks a subprocess
what the core imports (guard 11), calls the census guard directly (the second
half of guard 4), and writes a synthetic entry for a stub adapter, loads it and
renders it in a child process (guard 14). It costs seconds.

`ServiceCase` needs the live service, so it owns its lifecycle: one server, started
once in `setUpClass` and stopped by guard 2's own test. Guards 16, 13, 17, 18 and
19 run after it and start servers of their own, because the instance mutex allows
one at a time (guard 12). Every render the class makes is listed here with the
guard that owns it:

    renders                              guard
    4 x 1280x720 POST, same prompt/seed  guard 3 (owns); guard 5 borrows the bytes
    1 x CLI, no --out, same prompt/seed  guard 6 (owns); guard 7 borrows the bytes
    2 x 1280x720 concurrent POSTs        guard 9 (owns)
                                         one of them carries `upscale: true` and
                                         guard 10 borrows `upscale: null` from it
    1 x 2560x1440 POST with upscale      guard 10 (owns)
    4 x 512x512 POST, 8/8/12/12 steps    guard 15 (owns); each value twice, because
                                         determinism per value is part of it
    1 x 1024x576 POST, plus 2 servers    guard 16 (owns); the render must outlast
                                         the idle period it declares
    2 x 1280x720 page submissions,    guard 13 (owns); both through the page's own
      plus 1 server with --ui            client, against a server started with --ui,
                                         because the page is where a second producer
                                         would have to live
    2 x 1152x1152 POST, plus 2 servers guard 17 (owns); one under a tightened host
                                         declaration, one with no host.yaml at all
    2 x 256x256 POST, plus 1 server      guard 18 (owns); one with a LoRA, one
                                         without, on the promoted entry whose
                                         catalog declares it
    3 x 256x256 POST, plus 1 server      guard 19 (owns); one reference still, then
                                         the same request with it and without it, on
                                         the promoted entry whose model is an editor

That is twenty-two stills. Guard 3 costs four by protocol; guard 9 costs two because
concurrency cannot be borrowed; guard 10 costs one base render; the CLI still
doubles as guard 7's second half; guard 15 costs four because two step counts
must each be proved stable and then proved different; guard 13 costs two because
serialisation cannot be borrowed either, and it pays its own server because the
shared one is started without `--ui` — the matrix must stay green on a server
that never imports gradio. Guard 17 costs two because the host is read at boot
and there is no flag to point the server at another file, so the two cases are
two boots. Guard 18 costs two because "the selection reached the runtime" is a
claim about bytes, and a still cannot be compared with itself: it pays its own
server too, since the shared one serves Z-Image, whose entry declares no catalog.
Guard 19 costs three for the same reason in the other direction — a reference
cannot be compared with itself — and the reference it edits is rendered by the
service, because this tree adds no downloaded image. Nothing renders twice for
the same guard. Guard 14 writes one more still, 256×256, and it is the stub's:
no model is loaded for it.

Ordering is explicit, not incidental: methods are numbered because unittest runs
them alphabetically, and guard 3 has to see the first render after `start`.
"""

from __future__ import annotations

import ast
import datetime
import filecmp
import hashlib
import json
import os
import pathlib
import re
import signal
import statistics
import struct
import subprocess
import sys
import threading
import time
import types
import unittest
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
# `unittest discover -s tests` imports this module with `tests/` on sys.path; the
# package under test must be importable regardless of how the run was started.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BIN = ROOT / "bin" / "coltman-images"
PYTHON = ROOT / ".venv" / "bin" / "python"
RUN_DIR = ROOT / "run"
STATE_FILE = RUN_DIR / "server.json"
LOG_FILE = RUN_DIR / "server.log"
OUTPUT_DIR = ROOT / "out"
EVIDENCE = ROOT / "tests" / "e2e" / "p6-guards" / "evidence"
FILES = EVIDENCE / "files"

BIND = "127.0.0.1"
PORT = 8420

# Protocol section 10, guard 4 and section 6.1: the entry's expected census.
PROTOCOL_CENSUS = {"float8": 239, "plain": 282, "other": 0, "total": 521}

# Protocol section 6.1 and 10, guard 15: the entry's step range, and its default.
#
# These are **Z-Image's declaration** (`model/entries/zimage.yaml`), the entry the
# shared fixture serves, not a range of the law's: `limits.steps` belongs to the
# entry, and the law's rule is that a request outside it is refused at the door
# (protocol section 4.1). The promoted entry — FLUX.2 [klein], at
# `model/entry.yaml` — declares its own, different range.
PROTOCOL_STEPS = {"min": 8, "max": 16}
PROTOCOL_DEFAULT_STEPS = 12

ZIMAGE_ID = "z-image-turbo-fp8"
"""Z-Image's entry id, the alias the shared fixture serves (`start --model`)."""

ZIMAGE_ENTRY = ROOT / "model" / "entries" / "zimage.yaml"
"""Z-Image's entry file. Its census, ceiling and ladder are the ones guards 2-7,
9, 10, 13 and 16 were written against, and the recorded baseline is its still."""

POINT_STEPS = {"min": 4, "max": 4}
"""A synthetic single-value range, not any entry's real declaration.

The law has to admit it (protocol section 4.1): `limits.steps` is the entry's
range, and a range of one value is a range. The guard proves the law admits it
and refuses its neighbours, which is what keeps a distilled model's regime
expressible by an entry rather than hardcoded in the law.
"""

# One prompt and one seed for every still that has to be comparable. Nothing
# declares this prompt: it is test input, not a system default.
PROMPT = "a brass compass on a wooden table"
SEED = 4242
WIDTH, HEIGHT = 1280, 720
MAX_PIXELS = 921600

HTTP_TIMEOUT_S = 600.0
"""One 1280x720 render is ~46 s and a 2560x1440 delivery ~50 s; 600 s is slack, not a ceiling."""

HEALTH_TIMEOUT_S = 3.0

# Guard 3's declared threshold (protocol section 10, section 12).
WARMUP_RATIO = 1.25

# Guard 9's separator: serialised requests differ by a whole render, a second
# worker's would differ by contention only.
SERIAL_RATIO = 1.5

_RUN_STARTED = time.perf_counter()

OBS: dict[str, object] = {}
"""What the run measured. Written to the evidence file whether the run is green or red."""

ERR: dict[str, str] = {}
"""Why a key was never measured. A guard whose input is missing fails with this text."""


# --- the per-test deadline --------------------------------------------------

DEADLINE_S = float(os.environ.get("COLTMAN_TEST_DEADLINE_S", "420"))
"""One test's budget, 420 s unless `COLTMAN_TEST_DEADLINE_S` sets another number of seconds.

420 is 2.2x the slowest test measured on 2026-11-17 (guard 3, four 1280x720 renders,
192.6 s). A budget barely above the real cost turns a contended card into a false red,
and a false red costs more than a slow one.
"""


class TestDeadline(AssertionError):
    """A test overran its budget: it hung, it did not merely run long.

    An `AssertionError` and not a bare exception, because unittest reports an
    `AssertionError` as a failure attributed to the test that raised it — the run
    names what hung instead of stopping on a traceback from the harness.
    """


def _deadline_message(label: str, started: float, budget: float) -> str:
    return (
        f"{label} overran the matrix's per-test deadline of {budget:g} s after "
        f"{time.perf_counter() - started:.1f} s: it hung, it did not merely run long. "
        f"Where the answer lives: run/server.log (the last thing the service did) and "
        f"`ss -tnp` (the socket it is waiting on)."
    )


def _arm_deadline(label: str, started: float, budget: float | None = None) -> None:
    """Turn an overrun into a failure in this thread, instead of a hang for the whole run.

    The runners execute every test in the main thread, which is the thread `SIGALRM`
    is delivered to. A plain `signal.alarm`-style timer is enough here: the budget is
    seconds, not deadlines of sub-second precision.
    """
    seconds = DEADLINE_S if budget is None else budget

    def _trip(_signum: int, _frame: object) -> None:
        raise TestDeadline(_deadline_message(label, started, seconds))

    signal.signal(signal.SIGALRM, _trip)
    signal.setitimer(signal.ITIMER_REAL, max(0.1, seconds))


def _disarm_deadline() -> None:
    signal.setitimer(signal.ITIMER_REAL, 0.0)


# --- small plumbing ---------------------------------------------------------


def _put(key: str, value: object) -> None:
    OBS[key] = value


def _record_error(key: str, exc: BaseException) -> None:
    ERR[key] = f"{type(exc).__name__}: {exc}"


def _http(
    method: str, path: str, payload: dict | None = None, timeout: float = HTTP_TIMEOUT_S
) -> tuple[int, dict]:
    """Return (status, body). A dead port is status 0 with a transport error."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"http://{BIND}:{PORT}{path}", data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
        exc.close()
    except (urllib.error.URLError, OSError) as exc:
        return 0, {"error": {"code": "transport", "message": str(exc)}}
    if not raw:
        return status, {}
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw.decode("utf-8", "replace")}
    return status, body if isinstance(body, dict) else {"raw": body}


def _health() -> tuple[int, dict]:
    return _http("GET", "/health", timeout=HEALTH_TIMEOUT_S)


def _generate(payload: dict) -> tuple[int, dict]:
    return _http("POST", "/generate", payload)


def _cli(*args: str, timeout: float = 600.0) -> subprocess.CompletedProcess:
    """Run `bin/coltman-images` as an operator would: as an executable, not via the venv."""
    return subprocess.run(
        [str(BIN), *args], cwd=str(ROOT), capture_output=True, text=True, timeout=timeout
    )


def _server_pids() -> list[int]:
    """Every live process that is really this server, matched the way the server matches itself.

    `coltman_images.server._other_server_pids` is the authority on what a server is:
    the interpreter — the first token's basename starts with `python` — and
    `coltman_images.server` as one of its own argument tokens. Matching the text
    anywhere on a command line would count the shell that ran the check, which is
    exactly the mistake the server's own scan was written to avoid.
    """
    pids: list[int] = []
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
        if not argv:
            continue
        if not os.path.basename(argv[0]).startswith("python"):
            continue
        if "coltman_images.server" not in argv:
            continue
        pids.append(int(entry.name))
    return sorted(pids)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _terminate(pids: list[int], grace: float = 15.0) -> list[str]:
    """Kill the servers in `pids`: SIGTERM, then SIGKILL for what outlives the grace.

    A server holds `run/server.lock` for its whole life, so an orphan is not a stray
    process — it is the card taken and every later `start` exiting 4 with "another
    instance already owns this card" for a reason nobody caused. It is killed either
    way; whether it existed is a separate question, and the caller reports it.
    """
    notes: list[str] = []
    targets = [pid for pid in pids if _pid_alive(pid)]
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
            notes.append(f"SIGTERM {pid}")
        except OSError as exc:
            notes.append(f"SIGTERM {pid} failed: {exc}")

    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and any(_pid_alive(pid) for pid in targets):
        time.sleep(0.2)

    for pid in [pid for pid in targets if _pid_alive(pid)]:
        try:
            os.kill(pid, signal.SIGKILL)
            notes.append(f"SIGKILL {pid}")
        except OSError as exc:
            notes.append(f"SIGKILL {pid} failed: {exc}")

    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and any(_pid_alive(pid) for pid in targets):
        time.sleep(0.2)
    return notes


def _stop_if_running(grace: float = 45.0) -> None:
    """Stop whatever server is up and wait until the port, the state file and the pid are gone.

    Registered with `addCleanup` before a test's first `start`, so a failing
    assertion cannot leave the card taken for the rest of the matrix. It never
    raises: the guard's own assertions are the ones that speak, and a cleanup that
    also failed would only hide which one did.
    """
    if _state() is None and not _server_pids():
        return
    try:
        _cli("stop", timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        pass
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if not STATE_FILE.exists() and not _server_pids() and _health()[0] != 200:
            return
        time.sleep(0.5)
    remaining = _server_pids()
    if remaining:
        _terminate(remaining)


def _state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return {}


def _log_count(needle: str) -> int:
    """Occurrences of a message in the server's own log.

    The server logs every still it serves and every render that raised, so this
    counter is how guard 1 proves a refused request never reached the worker:
    a request that reached it would move one of these two numbers.

    The logger is named `__main__` in these lines, not `coltman_images.server`:
    the process is launched with `python -m coltman_images.server`, so it runs as a
    script and `logging.getLogger(__name__)` gets `__main__`. The needle is the
    message itself, which does not depend on how the process was launched.
    """
    try:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 0
    return sum(1 for line in text.splitlines() if needle in line)


def _render_count() -> int:
    return _log_count(": served: ")


def _render_failure_count() -> int:
    return _log_count(": render failed: ")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_size(path: pathlib.Path) -> tuple[int, int] | None:
    """The IHDR size, read from the file. `None` when it is not a PNG."""
    blob = path.read_bytes()[:33]
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", blob[16:24])
    return width, height


def _write_evidence() -> pathlib.Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "suite": "p6-guards",
        "generated_at": stamp,
        "project_root": str(ROOT),
        "interpreter": sys.version.split()[0],
        "total_s": round(time.perf_counter() - _RUN_STARTED, 2),
        "observations": OBS,
        "errors": ERR,
    }
    text = json.dumps(payload, indent=2, default=str) + "\n"
    path = EVIDENCE / f"guards-{stamp}.json"
    path.write_text(text, encoding="utf-8")
    (EVIDENCE / "latest.json").write_text(text, encoding="utf-8")
    return path


class GuardCase(unittest.TestCase):
    """Shared access to the recorded observations, and per-test timing under a deadline."""

    def setUp(self) -> None:
        self._t0 = time.perf_counter()
        _arm_deadline(self._testMethodName, self._t0)

    def tearDown(self) -> None:
        _disarm_deadline()
        _put(f"duration.{self._testMethodName}", round(time.perf_counter() - self._t0, 2))

    def obs(self, key: str):
        if key in OBS:
            return OBS[key]
        self.fail(f"{key} was never measured — {ERR.get(key, 'the run did not reach it')}")


# ===========================================================================
# ContractCase — the guards that need no service
# ===========================================================================


_KERNEL_ROOTS = ("/proc", "/sys", "/dev")
"""Kernel pseudo-filesystems.

`bin/coltman-images` reads `/proc/<pid>/cmdline` to decide whether the pid in the state
file is its own server before it signals anything. That is the kernel's process
table, not another project's data store: it exists on every Linux host this
service runs on, so it neither breaks independent runnability nor makes the
system depend on anything it does not own. The exemption is this narrow, it is
named, and the guard prints every literal it exempted so the reader can judge it.
"""

_REQUIRED_SOURCES = (
    "coltman_images/__init__.py",
    "coltman_images/entry.py",
    "coltman_images/render.py",
    "coltman_images/server.py",
    "coltman_images/adapter.py",
    "coltman_images/loader.py",
    "coltman_images/fp8.py",
    "coltman_images/upscale.py",
    "coltman_images/adapters/__init__.py",
    "coltman_images/adapters/zimage.py",
    "coltman_images/adapters/flux2klein_sd.py",
    "bin/coltman-images",
)
"""Guard 8 must not pass by scanning nothing. These files must all be read."""

_FORBIDDEN_IMPORTS = (
    "diffusers",
    "transformers",
    "safetensors",
    "coltman_images.loader",
    "coltman_images.fp8",
)
"""Guard 11: the model stack the core must never reach."""

_IMPORT_PROBE = """
import importlib
import json
import sys

name = sys.argv[1]
importlib.import_module(name)
forbidden = sorted(m for m in {forbidden!r} if m in sys.modules)
print(json.dumps({{"module": name, "loaded": name in sys.modules, "forbidden": forbidden}}))
"""


def _within(path: str, root: pathlib.Path) -> bool:
    """Is `path` a real location under `root`? Only absolute strings qualify."""
    if not str(path).startswith("/"):
        return False
    try:
        return pathlib.Path(path).resolve().is_relative_to(root)
    except (OSError, ValueError):
        return False


_TOP_LEVEL_DIRS = frozenset(entry.name for entry in pathlib.Path("/").iterdir() if entry.is_dir())
"""Every single-segment absolute literal is a path only if it names a real top-level
directory on this host. That is what separates `/tmp` (a path) from `/health` (an
HTTP route), without a hand-written allowlist of either."""


def _looks_like_path(text: str) -> bool:
    if not text.startswith("/") or text.startswith("//"):
        return False
    rest = text[1:]
    if "/" in rest:
        return True
    return rest.rstrip("/") in _TOP_LEVEL_DIRS


def _python_sources() -> list[pathlib.Path]:
    sources: list[pathlib.Path] = []
    for base in (ROOT / "coltman_images", ROOT / "bin"):
        for path in sorted(base.rglob("*")):
            if "__pycache__" in path.parts or not path.is_file():
                continue
            if path.suffix == ".py" or path.parent == ROOT / "bin":
                sources.append(path)
    return sources


def _declaration_documents() -> list[pathlib.Path]:
    """The project's own declarations, plus the small vendor configs it carries.

    Binary weights and the multi-megabyte tokenizer vocabulary are inputs, not
    declarations; the size cap keeps the scan to documents that could hold a path.
    """
    documents = [
        ROOT / "model" / "entry.yaml",
        ROOT / "model" / "upscaler.yaml",
        ROOT / "model" / "z_image.json",
        *sorted((ROOT / "model" / "entries").glob("*.yaml")),
    ]
    for path in sorted((ROOT / "model" / "assets").rglob("*")):
        if path.is_file() and path.suffix in (".json", ".yaml", ".yml") and path.stat().st_size <= 256 * 1024:
            documents.append(path)
    return documents


def _string_values(document: object, trail: str = ""):
    """Yield (where, text) for every string in a loaded YAML/JSON document."""
    if isinstance(document, dict):
        for key, value in document.items():
            yield from _string_values(value, f"{trail}.{key}")
    elif isinstance(document, list):
        for index, value in enumerate(document):
            yield from _string_values(value, f"{trail}[{index}]")
    elif isinstance(document, str):
        yield trail, document


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """The `id()` of every docstring constant.

    A docstring is prose, not a runtime lookup: it may name the historical origin
    of an asset without making the system read it. Every other string is scanned.
    """
    skip: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                skip.add(id(first.value))
    return skip


def _literal_strings(tree: ast.AST):
    """Every string a source carries, f-strings reconstructed as one template."""
    skip = _docstring_nodes(tree)
    # A literal inside an f-string is a fragment, not a string of its own: the
    # whole template is what a path or a URL is made of, so the fragments are
    # not counted twice.
    fragments = {
        id(value)
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        for value in node.values
        if isinstance(value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in skip or id(node) in fragments:
                continue
            yield node.lineno, node.value
        elif isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                else:
                    parts.append("{}")
            yield node.lineno, "".join(parts)


def _imported_modules(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # A relative import stays inside this package by construction.
            if node.level == 0 and node.module:
                names.add(node.module)
    return names


def _classify_import(name: str) -> tuple[str, str]:
    """('inside'|'stdlib'|'missing'|'outside', detail) for one imported module."""
    import importlib.util
    import sysconfig

    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError) as exc:
        return "missing", f"{type(exc).__name__}: {exc}"
    if spec is None:
        return "missing", "no module spec"
    origin = spec.origin or ""
    locations = list(spec.submodule_search_locations or [])
    for candidate in ([origin] if origin else []) + locations:
        if _within(str(candidate), ROOT):
            return "inside", str(candidate)
    if origin in ("built-in", "frozen"):
        return "stdlib", origin
    stdlib = sysconfig.get_paths()["stdlib"]
    for candidate in ([origin] if origin else []) + locations:
        if str(candidate).startswith(stdlib):
            return "stdlib", str(candidate)
    return "outside", origin or str(locations)


# --- guard 14: a model the law has never heard of ---------------------------
#
# The fixture is generated into the run's evidence folder, never into the tree
# and never into /tmp: two component files with real bytes under names no model
# owns, a synthetic entry that pins one of them by digest, and a stub adapter
# whose only model is the contract itself.

U1_EVIDENCE = ROOT / "tests" / "e2e" / "u1-entry-neutrality" / "evidence"
U1_STUB = "u1stub"
U1_PROMPT = "a thing that is not a lighthouse"
U1_SEED = 11
U1_SIDE = 256

_NEUTRALITY_NAMES = ("transformer_config", "text_encoder", "vae", "scheduler_config", "float8")
"""The names guard 14 forbids in `coltman_images/entry.py` (protocol section 6.1, 10).

The law validates an envelope; these five are what Z-Image's identity was made
of inside it. `float8` is included because a census key is the adapter's
declaration, not the law's.
"""


def _u1_colour(prompt: str, seed: int) -> tuple[int, int, int]:
    """The stub's pixel rule: the still is a function of the features and the seed."""
    digest = hashlib.sha256(f"{prompt}|{seed}".encode("utf-8")).digest()
    return digest[0], digest[1], digest[2]


class _U1StubAdapter:
    """A model that is only the contract: no weights, no stack, no assets.

    Registered under `U1_STUB` for guard 14. It is deliberately not an adapter of
    anything — that is the point: the core must serve it without being told what
    it is. `instances` keeps the one `render.render` builds, so the guard can read
    the calls the core actually made instead of trusting that it made them.
    """

    name = U1_STUB
    instances: list[_U1StubAdapter] = []

    def __init__(self, entry) -> None:
        self.entry = entry
        self.last_load_s = 0.0
        self.seen: list[str] = []
        type(self).instances.append(self)

    def prepare(self) -> None:
        self.seen.append("prepare")

    def census(self) -> dict[str, int]:
        self.seen.append("census")
        return dict(self.entry.expected_census)

    def encode(self, prompt: str, loras: tuple = (), images: tuple = ()) -> str:
        # The signature is the contract's, references included: `render` passes
        # the resolved tuple to every adapter. This entry declares no reference,
        # so the tuple is empty and the recorded call is the one it always was.
        assert images == (), f"this entry declares no reference, and got {len(images)}"
        self.seen.append(f"encode {prompt!r}")
        return prompt

    def denoise(self, features, width: int, height: int, seed: int, steps: int):
        from PIL import Image

        self.seen.append(f"denoise {width}x{height} seed={seed}")
        return Image.new("RGB", (width, height), _u1_colour(str(features), seed))

    def close(self) -> None:
        self.seen.append("close")


def _u1_entry(digest: str) -> dict:
    """The synthetic entry: arbitrary component names, no model-specific census."""
    evidence = U1_EVIDENCE.relative_to(ROOT)
    return {
        "id": "u1-stub-model",
        "adapter": U1_STUB,
        "checkpoint": str(evidence / "thing_a.bin"),
        "components": {
            "thing_a": str(evidence / "thing_a.bin"),
            "thing_b": str(evidence / "thing_b.json"),
        },
        "digests": {"thing_b": f"sha256:{digest}"},
        "steps": 4,
        "guidance": 1.5,
        "limits": {"max_pixels": U1_SIDE * U1_SIDE, "steps": {"min": 3, "max": 9}},
        "request_fields": ["prompt", "seed", "width", "height", "out"],
        "expected_census": {"parameters": 2, "tensors": 3},
        "defaults": {"width": U1_SIDE, "height": U1_SIDE, "format": "png"},
        "warmup": {"width": U1_SIDE, "height": U1_SIDE, "prompt": "warm up", "seed": 0},
    }


def _u1_probe() -> dict:
    """Load the synthetic entry and render through the stub. Runs in a child process.

    The child is not decoration: `render.render` initialises a CUDA context, and
    a context held by the test process would take memory from the card the later
    guards need (the transformer alone measures 6057 MiB of 8188). Here it dies
    with the child.
    """
    from coltman_images import adapter as adapter_module
    from coltman_images.entry import load_entry
    from coltman_images.render import render

    entry = load_entry(U1_EVIDENCE / "entry.yaml")
    adapter_module._REGISTRY[U1_STUB] = f"{__name__}:_U1StubAdapter"

    # The wrapper's other half: a name the entry does not declare is a sentence.
    missing = ""
    try:
        entry.components.thing_c
    except AttributeError as exc:
        missing = str(exc)

    destination = U1_EVIDENCE / "stub-render.png"
    destination.unlink(missing_ok=True)
    response = render(
        entry,
        prompt=U1_PROMPT,
        seed=U1_SEED,
        width=U1_SIDE,
        height=U1_SIDE,
        out=str(destination),
    )
    calls = list(_U1StubAdapter.instances[-1].seen) if _U1StubAdapter.instances else []
    return {
        "entry_id": entry.id,
        "adapter": entry.adapter,
        "components": sorted(entry.components.paths),
        "thing_a": str(entry.components.thing_a),
        "census_declared": dict(entry.expected_census),
        "missing_component_said": missing,
        "calls": calls,
        "response": response,
    }


def _code_names(path: pathlib.Path) -> list[dict[str, object]]:
    """Every occurrence of a neutrality name in the code of `path`, from the AST.

    The parsed code, not the prose: a comment is absent from an AST by
    construction, and a docstring is a string constant that describes rather than
    reaches (`_literal_strings` already excludes it, as guard 8 and 11 do). What
    is scanned is what a coupling is made of — identifiers, attribute names,
    argument and keyword names, definition names, imported names and the other
    string constants.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[dict[str, object]] = []

    def scan(where: str, line: int, candidate: str) -> None:
        for needle in _NEUTRALITY_NAMES:
            if needle in candidate:
                findings.append({"where": where, "line": line, "name": needle, "code": candidate})

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            scan("identifier", node.lineno, node.id)
        elif isinstance(node, ast.Attribute):
            scan("attribute", node.lineno, node.attr)
        elif isinstance(node, ast.arg):
            scan("argument", node.lineno, node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            scan("keyword", node.lineno, node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scan("definition", node.lineno, node.name)
        elif isinstance(node, ast.alias):
            scan("import", node.lineno, node.name)
    for line, text in _literal_strings(tree):
        scan("string", line, text)
    return findings


class ContractCase(GuardCase):
    """Guards 4b, 8 and 11 — the ones a service would only slow down."""

    def test_guard04b_assert_census_refuses_a_model_with_no_float8_weights(self) -> None:
        """Guard 4, second half: `assert_census` refuses float8 == 0. No GPU needed."""
        from coltman_images.entry import load_entry
        from coltman_images.loader import CensusError, assert_census

        entry = load_entry(ZIMAGE_ENTRY)
        findings: dict[str, object] = {"expected_census": entry.expected_census}

        # The entry's own census must pass, or the comparison below proves nothing.
        self.assertEqual(assert_census(PROTOCOL_CENSUS, entry), PROTOCOL_CENSUS)

        # The failure this guard exists for: a silent downgrade to plain
        # precision still produces a plausible still, so the census is the only
        # witness. Every parameter plain, no Float8 weight at all.
        plain_load = {"float8": 0, "plain": 521, "other": 0, "total": 521}
        with self.assertRaises(CensusError) as refused:
            assert_census(plain_load, entry)
        findings["refusal"] = str(refused.exception)
        self.assertIn("Float8", str(refused.exception))

        # And a census that merely differs from the entry is refused too.
        off_by_one = {"float8": 238, "plain": 282, "other": 0, "total": 520}
        with self.assertRaises(CensusError) as drifted:
            assert_census(off_by_one, entry)
        findings["drift_refusal"] = str(drifted.exception)

        _put("guard04.assert_census", findings)
        print(f"guard 4b: float8=0 refused ({findings['refusal']})")

    def test_guard08_no_import_or_path_outside_the_tree(self) -> None:
        """Guard 8: refusal of any import or absolute path leaving the project's tree.

        Two kinds of exemption, and both are declared by name. The kernel's
        interfaces (`/proc`, `/sys`, `/dev`) are what `bin/coltman-images` reads to
        tell its own server from a stranger's pid, and they are printed below. The
        second is the **caller's reference image**: `image` is the one request
        field whose path may point anywhere, because the file belongs to the
        caller and the system invents no transport (protocol sections 2, 4.1). A
        caller-named path is not a literal, so the scan cannot see one — what this
        half proves is that the permission is a single declaration, named once,
        covering exactly the field the law admits, instead of a silent pass
        somewhere in the code.
        """
        from coltman_images.entry import CALLER_READ_EXEMPTIONS, VOCABULARY

        sources = _python_sources()
        documents = _declaration_documents()

        found_names = {str(path.relative_to(ROOT)) for path in sources}
        missing = [name for name in _REQUIRED_SOURCES if name not in found_names]
        self.assertEqual(missing, [], f"guard 8 did not read these files: {missing}")

        imports: dict[str, str] = {}
        paths: list[dict[str, str]] = []
        parse_errors: list[str] = []

        for path in sources:
            relative = str(path.relative_to(ROOT))
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relative)
            except SyntaxError as exc:  # a file the guard cannot read is a finding, not a skip
                parse_errors.append(f"{relative}: {exc}")
                continue
            for name in _imported_modules(tree):
                imports.setdefault(name.split(".")[0], f"{relative}: {name}")
            for line, text in _literal_strings(tree):
                if _looks_like_path(text):
                    paths.append({"where": f"{relative}:{line}", "literal": text})

        for path in documents:
            relative = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.suffix in (".yaml", ".yml"):
                document = yaml.safe_load(text)
            else:
                document = json.loads(text)
            for trail, value in _string_values(document):
                if _looks_like_path(value):
                    paths.append({"where": f"{relative}{trail}", "literal": value})

        self.assertEqual(parse_errors, [], f"the guard could not read: {parse_errors}")

        imports_outside: list[str] = []
        imports_report: dict[str, str] = {}
        for name in sorted(imports):
            kind, detail = _classify_import(name)
            imports_report[name] = f"{kind}: {detail}"
            if kind in ("outside", "missing"):
                imports_outside.append(f"{name} ({imports[name]}) resolves {kind}: {detail}")

        paths_inside: list[str] = []
        paths_kernel: list[str] = []
        paths_outside: list[str] = []
        for record in paths:
            literal = record["literal"]
            probe = literal.replace("{}", "0")
            if _within(probe, ROOT):
                paths_inside.append(record["where"] + " → " + literal)
                continue
            if any(probe == root or probe.startswith(root + "/") for root in _KERNEL_ROOTS):
                paths_kernel.append(record["where"] + " → " + literal)
                continue
            paths_outside.append(record["where"] + " → " + literal)

        read_exemptions = dict(CALLER_READ_EXEMPTIONS)
        _put(
            "guard08",
            {
                "sources_read": len(sources),
                "documents_read": [str(path.relative_to(ROOT)) for path in documents],
                "imports": imports_report,
                "paths_inside": paths_inside,
                "paths_kernel": paths_kernel,
                "paths_outside": paths_outside,
                "caller_read_exemptions": read_exemptions,
            },
        )
        print(
            f"guard 8: {len(sources)} python sources, {len(documents)} declarations, "
            f"{len(imports)} imported modules; {len(paths_inside)} in-tree paths, "
            f"{len(paths_kernel)} kernel, {len(paths_outside)} outside"
        )
        for finding in paths_kernel:
            print(f"guard 8: exempted kernel interface — {finding}")
        for field, reason in read_exemptions.items():
            print(f"guard 8: exempted caller path — {field}: {reason}")

        self.assertEqual(
            sorted(read_exemptions),
            ["image"],
            "the declared read exception is not exactly the request's `image` field: "
            f"{sorted(read_exemptions)} — a second field reaching outside the tree is an "
            "undeclared read (protocol section 2)",
        )
        self.assertIn(
            "image",
            VOCABULARY,
            "the exemption names a field the closed vocabulary does not have",
        )

        self.assertEqual(
            imports_outside,
            [],
            "an import resolves outside the project's tree and the interpreter: " + "; ".join(imports_outside),
        )
        self.assertEqual(
            paths_outside, [], "an absolute path leaves the project's tree: " + "; ".join(paths_outside)
        )

    def test_guard11_core_imports_nothing_from_the_model_stack(self) -> None:
        """Guard 11: no model stack reachable from server, render or entry.

        Each module is imported in its own subprocess, so this test's own imports
        cannot pollute the answer and a failure names the module that pulled the
        stack in.
        """
        code = _IMPORT_PROBE.format(forbidden=list(_FORBIDDEN_IMPORTS))
        results: dict[str, dict] = {}
        for name in ("coltman_images.server", "coltman_images.render", "coltman_images.entry"):
            completed = subprocess.run(
                [str(PYTHON), "-c", code, name],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"importing {name} failed: {completed.stderr[-2000:]}",
            )
            results[name] = json.loads(completed.stdout.strip().splitlines()[-1])

        _put("guard11", results)
        for name, result in results.items():
            print(f"guard 11: {name} loaded={result['loaded']} forbidden={result['forbidden']}")
            # Not vacuous: the module really was imported in that subprocess.
            self.assertTrue(result["loaded"], f"{name} was not in sys.modules after importing it")
            self.assertEqual(result["forbidden"], [], f"{name} reaches the model stack: {result['forbidden']}")

    def test_guard14_entry_neutrality(self) -> None:
        """Guard 14: an entry for a model this system does not have loads and renders.

        Part (a) is behavioural. A synthetic entry is written to the run's evidence
        folder: component names of its own choosing (`thing_a`, `thing_b`), no
        transformer config, a census with none of Z-Image's keys, and an adapter
        name registered for this test. If `entry.py` still carried a model's
        schema, that entry would be refused before the stub was ever built — so
        loading it and rendering one still through `render.render` is the proof
        that the law's only subject is the envelope.

        Part (b) is a source scan on the parsed code of `coltman_images/entry.py`,
        asserting none of the five model-specific names survives there. The brief
        said "a source scan"; scanning prose would forbid the *word* rather than
        the coupling — a docstring cannot read a component — so the scan reads the
        AST: identifiers, attribute names, argument and keyword names, definition
        names, imported names and the string constants that are not docstrings.
        It is not vacuous: the same scan is run over the Z-Image adapter, which
        names all five, and must find all five.

        It lives in `ContractCase` on purpose: it needs no service (it builds its
        own entry and adapter), and it runs before any server exists, so a CUDA
        context of its own — kept in a child process — cannot share the card with
        the transformer the later guards load.
        """
        U1_EVIDENCE.mkdir(parents=True, exist_ok=True)
        thing_a = U1_EVIDENCE / "thing_a.bin"
        thing_b = U1_EVIDENCE / "thing_b.json"
        thing_a.write_bytes(b"guard 14: a component that is not a checkpoint\n")
        thing_b.write_bytes(b'{"guard": 14, "kind": "a second component"}\n')
        digest = hashlib.sha256(thing_b.read_bytes()).hexdigest()
        entry_file = U1_EVIDENCE / "entry.yaml"
        entry_file.write_text(
            yaml.safe_dump(_u1_entry(digest), sort_keys=False), encoding="utf-8"
        )

        code = (
            "import json, sys; "
            f"sys.path.insert(0, {str(ROOT / 'tests')!r}); "
            "import test_p6_guards as g; "
            "print('U1-PROBE ' + json.dumps(g._u1_probe()))"
        )
        began = time.perf_counter()
        completed = subprocess.run(
            [str(PYTHON), "-c", code],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        probe_wall = round(time.perf_counter() - began, 2)

        probe: dict = {}
        probe_error = ""
        if completed.returncode != 0:
            probe_error = f"the probe exited {completed.returncode}: {completed.stderr[-1500:]}"
        else:
            lines = [line for line in completed.stdout.splitlines() if line.startswith("U1-PROBE ")]
            if not lines:
                probe_error = f"the probe printed no result: {completed.stdout[-800:]}"
            else:
                probe = json.loads(lines[-1][len("U1-PROBE ") :])

        entry_source = ROOT / "coltman_images" / "entry.py"
        findings = _code_names(entry_source)
        core_sources = [
            entry_source,
            ROOT / "coltman_images" / "render.py",
            ROOT / "coltman_images" / "server.py",
            ROOT / "coltman_images" / "adapter.py",
        ]
        core_findings = {
            str(source.relative_to(ROOT)): _code_names(source) for source in core_sources
        }
        adapter_source = ROOT / "coltman_images" / "adapters" / "zimage.py"
        adapter_findings = _code_names(adapter_source)
        adapter_names = sorted({str(finding["name"]) for finding in adapter_findings})

        _put(
            "guard14",
            {
                "evidence": str(U1_EVIDENCE.relative_to(ROOT)),
                "entry_file": str(entry_file.relative_to(ROOT)),
                "probe_wall_s": probe_wall,
                "probe_error": probe_error,
                "probe": probe,
                "neutrality": {
                    "file": str(entry_source.relative_to(ROOT)),
                    "findings": findings,
                    "core_findings": core_findings,
                    "control_file": str(adapter_source.relative_to(ROOT)),
                    "control_names": adapter_names,
                    "control_findings": adapter_findings[:20],
                },
            },
        )

        response = probe.get("response", {})
        print(
            f"guard 14a: entry {probe.get('entry_id')} (adapter {probe.get('adapter')!r}) loaded from "
            f"{entry_file.relative_to(ROOT)} with components {probe.get('components')} and census "
            f"{probe.get('census_declared')} in {probe_wall} s"
        )
        print(
            f"guard 14a: rendered {response.get('width')}x{response.get('height')} through the stub → "
            f"{response.get('out')} (model {response.get('model')!r}, seed {response.get('seed')})"
        )
        print(f"guard 14a: the core called the stub {probe.get('calls')}")
        print(f"guard 14a: a name the entry does not declare → {probe.get('missing_component_said')!r}")
        print(
            f"guard 14b: {entry_source.relative_to(ROOT)} parsed — 0 of "
            f"{len(_NEUTRALITY_NAMES)} model names in code; the same scan finds {adapter_names} "
            f"in {adapter_source.name} ({len(adapter_findings)} occurrences)"
        )

        with self.subTest(part="14a: a synthetic entry loads and renders"):
            self.assertEqual(probe_error, "", probe_error)
            self.assertEqual(probe.get("entry_id"), "u1-stub-model")
            self.assertEqual(probe.get("adapter"), U1_STUB)
            self.assertEqual(probe.get("components"), ["thing_a", "thing_b"])
            self.assertEqual(sorted(probe.get("census_declared", {})), ["parameters", "tensors"])
            self.assertNotIn("float8", probe.get("census_declared", {}))
            self.assertIn("thing_a", probe.get("thing_a", ""))

            said = str(probe.get("missing_component_said", ""))
            self.assertIn("thing_c", said, f"the wrapper did not name the missing component: {said}")
            self.assertIn("thing_a", said, f"the wrapper did not list what the entry declares: {said}")

            self.assertEqual(response.get("model"), "u1-stub-model")
            self.assertEqual((response.get("width"), response.get("height")), (U1_SIDE, U1_SIDE))
            self.assertEqual(response.get("seed"), U1_SEED)
            self.assertEqual(response.get("census"), {"parameters": 2, "tensors": 3})
            self.assertIsNone(response.get("upscale"), "the stub asked for the upscale stage")

            self.assertEqual(
                probe.get("calls"),
                [
                    "prepare",
                    f"encode {U1_PROMPT!r}",
                    f"denoise {U1_SIDE}x{U1_SIDE} seed={U1_SEED}",
                    "census",
                    "close",
                ],
                "the core did not drive the stub through its whole contract",
            )

            still = pathlib.Path(response.get("out", ""))
            self.assertTrue(still.is_file(), f"{still} was not written")
            self.assertEqual(_png_size(still), (U1_SIDE, U1_SIDE))

            # The bytes are the stub's, not a real render's: the pixel is what the
            # stub's own rule says it must be.
            from PIL import Image

            with Image.open(still) as image:
                pixel = image.convert("RGB").getpixel((0, 0))
            self.assertEqual(pixel, _u1_colour(U1_PROMPT, U1_SEED), "the still did not come from the stub")

        with self.subTest(part="14b: the law names no model"):
            self.assertEqual(
                findings,
                [],
                "coltman_images/entry.py still knows a model: "
                + "; ".join(f"{f['where']} {f['code']!r} at line {f['line']}" for f in findings),
            )
            # Not vacuous: the same scan, over the file that does the coupling.
            self.assertEqual(
                adapter_names,
                sorted(_NEUTRALITY_NAMES),
                f"the scan found {adapter_names} in {adapter_source.name}, not all five names",
            )

        print(
            "guard 14c: the core names no model — "
            + ", ".join(f"{name}: {len(entries)}" for name, entries in core_findings.items())
        )

        with self.subTest(part="14c: the core names no model either"):
            # U1 found one: `server.py` built its warm-up log line from
            # `census["float8"]` and three siblings, so a foreign census raised
            # KeyError *after* the model loaded and boot reported exit 1. The
            # line is fixed; this keeps it fixed, and holds the other core
            # modules to the same rule the law states.
            for name, entries in core_findings.items():
                self.assertEqual(
                    entries,
                    [],
                    f"{name} still knows a model: "
                    + "; ".join(f"{f['where']} {f['code']!r} at line {f['line']}" for f in entries),
                )


# ===========================================================================
# ServiceCase — the guards that need the live service
# ===========================================================================


# --- guard 15: the step count is a request field, bounded by the entry ------
#
# The refusal half needs an adapter that records whether it was ever built, so
# the proof is "no instance, therefore no call" rather than "the render did not
# finish". The stub is guard 15's own, not guard 14's, so neither guard depends
# on the other's fixture, and it is written into the run's evidence folder like
# every other fixture this suite creates.

G15_STUB = "g15stub"
G15_SIDE = 256
"""The stub's render size: it never touches the card, so the shape is cosmetic."""

G15_RENDER_SIDE = 512
"""Guard 15's real stills. Steps are the variable; the size is kept small so the
guard costs four short renders instead of four 1280x720 ones."""

G15_STEPS = (8, 8, 12, 12)
"""Two runs at each of the two values, interleaved by value: the pair proves
determinism per value, the two pairs prove the values differ."""


class _G15StubAdapter:
    """A model that exists only to be counted: zero instances means zero calls."""

    name = G15_STUB
    instances: list["_G15StubAdapter"] = []

    def __init__(self, entry) -> None:
        self.entry = entry
        self.last_load_s = 0.0
        type(self).instances.append(self)

    def prepare(self) -> None:
        pass

    def census(self) -> dict[str, int]:
        return dict(self.entry.expected_census)

    def encode(self, prompt: str, loras: tuple = (), images: tuple = ()) -> str:
        # The contract's signature, references included, even though this guard
        # never asks for one.
        return prompt

    def denoise(self, features, width: int, height: int, seed: int, steps: int):
        from PIL import Image

        return Image.new("RGB", (width, height), (1, 2, 3))

    def close(self) -> None:
        pass


def _g15_entry(
    steps: int = PROTOCOL_DEFAULT_STEPS,
    name: str = "g15-entry.yaml",
    steps_range: dict | None = None,
) -> pathlib.Path:
    """A synthetic entry the law accepts, with a range this guard can straddle."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    asset = EVIDENCE / "g15-asset.bin"
    asset.write_bytes(b"guard 15: a component the stub never reads\n")
    document = {
        "id": "g15-stub-model",
        "adapter": G15_STUB,
        "checkpoint": str(asset),
        "components": {"weights": str(asset)},
        "steps": steps,
        "guidance": 0.0,
        "limits": {
            "max_pixels": G15_SIDE * G15_SIDE,
            "steps": dict(PROTOCOL_STEPS if steps_range is None else steps_range),
        },
        "request_fields": ["prompt", "seed", "width", "height", "out", "steps"],
        "expected_census": {"parameters": 1},
        "defaults": {"width": G15_SIDE, "height": G15_SIDE, "format": "png"},
        "warmup": {"width": G15_SIDE, "height": G15_SIDE, "prompt": "warm up", "seed": 0},
    }
    path = EVIDENCE / name
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


# --- guard 13: the UI is a surface, never a second renderer -----------------
#
# Three parts, because three parts are what can be observed without pinning
# gradio's HTTP contract: the module cannot reach a model and cannot reach past
# the seam (parsed, not trusted), the request builder maps the switch (no GPU),
# and the queue is still single-flight *with the page mounted* — two submissions
# fired through the page's own client, at guard 9's threshold.

UI_PORT = 7860
"""The page's default port (protocol sections 6 and 7)."""

# Guard 13's two submissions go through the page's form, and the form has no size
# field: SD is the entry's own defaults, whatever they are. That costs two
# ~46 s renders rather than the ~25 s a 512x512 pair would, and it is the honest
# shape — a page that accepted a size the entry does not declare would be shaping
# a request the API could not have sent.

G13_FORBIDDEN_IMPORTS = (
    "diffusers",
    "transformers",
    "safetensors",
    "coltman_images.loader",
    "coltman_images.fp8",
    "coltman_images.adapter",
    "coltman_images.adapters",
    "coltman_images.render",
    "coltman_images.upscale",
    "PIL",
)
"""Guard 13: what the UI must never reach. `coltman_images.adapters.*` matches by
prefix, so an adapter module of the future is covered by the same entry; the
declared stage is on the list because a page that ran it would be a second
producer of synthesized pixels, which is the one thing the seam exists to stop.
`PIL` is on it because the reference control hands the page a path: a page that
opened the file to read its size would be sizing a request from the caller's
picture instead of from the entry and the aspect (section 5.5)."""

G13_APP_ATTRIBUTES = frozenset({"submit", "depth", "entry", "declaration"})
"""Guard 13: everything the page may read from the warm server it is handed.

`WarmServer`'s public surface also carries `adapter` and the queue's own
`_queue`/`_enqueue`, and reaching any of them from the page would be a producer
outside the seam. The names are listed positively so a new attribute has to be
declared here, in the law's vocabulary, before the page may use it."""

G13_FORBIDDEN_SIZE_CONSTANTS = (
    720,
    768,
    960,
    1024,
    1152,
    1280,
    1440,
    1536,
    1920,
    2560,
    921600,
    1327104,
)
"""The entry's numbers, which the page must not carry (roadmap P9 step 4).

`limits.max_pixels` and the boxes it permits are per-entry, so a size written into
the UI is a size the next entry inherits wrongly — and with an aspect control the
temptation is a table of ten. Every one of these is ≥ 256, so none can collide
with the page's own small numbers (`precision=0`, `lines=2`, `step=1`,
`height=540`, `STATUS_TICK_S = 0.5`, a column's `min_width`).

The scan is on the parsed code, with arithmetic folded (`640 * 2` is 1280), on
integral floats (`1280.0`), and on the non-docstring strings (`"1280x720"`);
docstrings are prose, and that is where the current entry's numbers may appear.
The *step* ladder is not scanned as numbers: `16` is also the request's block
unit (protocol section 4.1), which `size_for` needs to put a box on the grid, so
the integer scan would refuse a legitimate literal. The ladder's provenance is
proved by the positive check instead — the page must read `steps_min`, `steps_max`
and `steps` from the entry — and that check cannot collide with anything.
"""


def _ui_imports(path: pathlib.Path) -> set[str]:
    """Every module `path` imports, relative imports resolved to their package.

    `_imported_modules` skips relative imports because they stay inside the
    package by construction — true for guard 8, and useless here: `from . import
    render` is exactly the coupling this guard exists to refuse.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 1:
                module = f"coltman_images.{module}" if module else "coltman_images"
            elif node.level > 1:
                module = f"coltman_images.{'pkg.' * (node.level - 1)}{module}".rstrip(".")
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def _ui_forbidden(imports: set[str]) -> list[str]:
    """The imports of `ui.py` that reach the model stack, by exact name or prefix."""
    found: list[str] = []
    for name in sorted(imports):
        for needle in G13_FORBIDDEN_IMPORTS:
            if name == needle or name.startswith(needle + "."):
                found.append(name)
                break
    return found


def _ui_calls(tree: ast.AST, attribute: str) -> bool:
    """Does the parsed module call `something.<attribute>(...)` anywhere?"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == attribute:
            return True
        if isinstance(func, ast.Name) and func.id == attribute:
            return True
    return False


def _ui_app_attributes(tree: ast.AST) -> set[str]:
    """Every attribute the module reads from the name `app`, methods included.

    The page is handed the whole `WarmServer`, so "it calls submit()" is not the
    boundary on its own: `app.adapter.encode(...)` or `app._enqueue(...)` would
    both satisfy that and neither is the seam. What the page may touch is a closed
    list (protocol section 5.5), and this is the scan that closes it.
    """
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "app"
    }


def _ui_entry_attributes(tree: ast.AST) -> set[str]:
    """Every attribute the module reads from the resolved entry.

    `entry.x` and `app.entry.x` both count. This is the positive direction of the
    "no constant" rule: the ladder's bounds and its default must come *from the
    entry*, and asserting that they do is stronger than only asserting that the
    numbers are absent.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        owner = node.value
        if isinstance(owner, ast.Name) and owner.id == "entry":
            names.add(node.attr)
        elif isinstance(owner, ast.Attribute) and owner.attr == "entry":
            names.add(node.attr)
    return names


def _ui_numbers(tree: ast.AST) -> list[float | int]:
    """Every numeric literal in the module, arithmetic folded and deduplicated."""

    def folded(node: ast.AST) -> float | int | None:
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = folded(node.operand)
            return None if inner is None else -inner
        if isinstance(node, ast.BinOp):
            left, right = folded(node.left), folded(node.right)
            if left is None or right is None:
                return None
            try:
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Div):
                    return left / right
                if isinstance(node.op, ast.FloorDiv):
                    return left // right
            except ZeroDivisionError:
                return None
        return None

    values: list[float | int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            values.append(node.value)
        elif isinstance(node, ast.BinOp):
            value = folded(node)
            if value is not None:
                values.append(value)
    return sorted(set(values), key=float)


def _ui_matching(values: list[float | int], forbidden: tuple[int, ...]) -> list[float | int]:
    """The values that name one of `forbidden`, floats compared by value."""
    return [value for value in values if any(abs(float(value) - needle) < 1e-9 for needle in forbidden)]


def _ui_string_size_literals(tree: ast.AST, forbidden: tuple[int, ...]) -> list[str]:
    """Non-docstring strings that spell one of `forbidden` (`"1280x720"`)."""
    hits = {
        text
        for _line, text in _literal_strings(tree)
        if any(str(needle) in text for needle in forbidden)
    }
    return sorted(hits)


def _ui_gradio_calls(tree: ast.AST, attribute: str) -> list[dict[str, object]]:
    """Every `gr.<attribute>(...)` bound to a name, with its literal keywords.

    `attribute` is the gradio class as the page spells it (`Image`). The bound
    name is what the wiring is made of: a component that is an event's input or
    output is the one the page uses, and a call nobody wires is decoration. A
    keyword whose value is not a literal is reported as `<expr>`, which no
    assertion accepts as a literal type.
    """
    found: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if not isinstance(func, ast.Attribute) or func.attr != attribute:
            continue
        target = node.targets[0]
        found.append(
            {
                "bound_to": target.id if isinstance(target, ast.Name) else None,
                "line": node.lineno,
                "keywords": {
                    keyword.arg: (
                        keyword.value.value
                        if isinstance(keyword.value, ast.Constant)
                        else "<expr>"
                    )
                    for keyword in node.value.keywords
                    if keyword.arg
                },
            }
        )
    return found


def _ui_click_wiring(tree: ast.AST) -> tuple[list[str], list[str]]:
    """The names a `*.click(...)` event takes as inputs, and hands back as outputs."""
    inputs: list[str] = []
    outputs: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "click"):
            continue
        for keyword in node.keywords:
            if keyword.arg not in ("inputs", "outputs"):
                continue
            if not isinstance(keyword.value, ast.List):
                continue
            names = [
                element.id
                for element in keyword.value.elts
                if isinstance(element, ast.Name)
            ]
            (inputs if keyword.arg == "inputs" else outputs).extend(names)
    return inputs, outputs


def _ui_size_reads(tree: ast.AST, names: set[str]) -> list[str]:
    """Every `name.size` / `.width` / `.height` / `.shape` read of `names`.

    The reference control hands the page a **path**, and the box is the entry's
    and the aspect's to decide: a page that opened the file or read a dimension
    off it would be sizing a request from the caller's picture instead of from
    the entry (protocol section 5.5).
    """
    dimensions = {"size", "width", "height", "shape"}
    return sorted(
        f"{node.value.id}.{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in dimensions
        and isinstance(node.value, ast.Name)
        and node.value.id in names
    )


def _ui_page(port: int, path: str = "/") -> tuple[int, str, bytes]:
    """GET the page. (0, "", b"") when nothing answers — the refusal is the answer."""
    try:
        with urllib.request.urlopen(f"http://{BIND}:{port}{path}", timeout=10.0) as response:
            return int(response.status), response.headers.get("Content-Type", ""), response.read()
    except (urllib.error.URLError, OSError):
        return 0, "", b""


# --- guard 17: the host may tighten, never widen ----------------------------
#
# `host.yaml` at the tree root is the deployment's declaration, and the server
# reads that one path at boot — there is no flag to point it elsewhere, which is
# the wiring the guard has to exercise. So the live halves rewrite the tree's
# file, and the bytes the tree shipped are recorded here at import and asserted
# back in `tearDownModule`: a guard that rewrites a declaration cannot leave the
# tree changed, and the assertion is what makes that true rather than intended.

HOST_FILE = ROOT / "host.yaml"
"""The deployment's declaration — the one file guard 17 rewrites and restores."""

HOST_DECLARATION = HOST_FILE.read_bytes() if HOST_FILE.is_file() else None
"""What the tree declares, captured before any test can rewrite it."""

G17_DIR = EVIDENCE / "g17"
G17_KLEIN_ID = "flux2-klein-4b-gguf-q4"
G17_KLEIN_ENTRY = ROOT / "model" / "entry.yaml"
G17_PROMPT = "a brass compass on a wooden table"

G17_SIDE = 512
"""The synthetic entry's measured ceiling side (512² = 262,144 px)."""

G17_DEFAULTS = 256
"""Its default box (256² = 65,536 px) — deliberately under the ceiling."""

G17_CAP = 196608
"""The host cap the size half tightens to: above the default box, below the ceiling.

That window is the only place a `max_pixels` may tighten, and neither shipped
entry has one — both render their default box exactly at their measured ceiling
(klein 1152² = 1,327,104; Z-Image 1280×720 = 921,600). This synthetic entry is
what makes the tightening observable at all; the live half proves the same rule
through the service on the step range, which both entries can tighten.
"""


def _g17_host_document(**overrides: object) -> dict:
    """A host declaration this guard can change one field at a time."""
    document: dict = {"id": "p6-guard-17", "vram_mib": 7857, "offload": True}
    document.update(overrides)
    return document


def _g17_write_declaration(document: dict, where: pathlib.Path | None = None) -> pathlib.Path:
    """Write a host declaration. Defaults to the guard's scratch folder."""
    if where is None:
        G17_DIR.mkdir(parents=True, exist_ok=True)
        where = G17_DIR / "host.yaml"
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return where


def _g17_restore_declaration() -> None:
    """Put the tree's declaration back exactly as it was found."""
    if HOST_DECLARATION is None:
        HOST_FILE.unlink(missing_ok=True)
        return
    HOST_FILE.write_bytes(HOST_DECLARATION)


def _g17_entry(name: str = "g17-entry.yaml") -> pathlib.Path:
    """A synthetic entry whose default box leaves room under its ceiling."""
    G17_DIR.mkdir(parents=True, exist_ok=True)
    asset = G17_DIR / "g17-asset.bin"
    asset.write_bytes(b"guard 17: a component no adapter here reads\n")
    document = {
        "id": "g17-stub-model",
        "adapter": "g17stub",
        "checkpoint": str(asset),
        "components": {"weights": str(asset)},
        "steps": 4,
        "guidance": 1.0,
        "limits": {"max_pixels": G17_SIDE * G17_SIDE, "steps": {"min": 3, "max": 9}},
        "request_fields": ["prompt", "seed", "width", "height", "out", "steps"],
        "expected_census": {"parameters": 1},
        "defaults": {"width": G17_DEFAULTS, "height": G17_DEFAULTS, "format": "png"},
        "warmup": {
            "width": G17_DEFAULTS,
            "height": G17_DEFAULTS,
            "prompt": "warm up",
            "seed": 0,
        },
    }
    path = G17_DIR / name
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


# --- guard 18: a catalog on the entry, a budget on the host -----------------
#
# A LoRA is per model: the entry declares the aliases a caller may name, and a
# request names an alias, never a path (protocol sections 4.1 and 6.1). What a
# selection may cost in device memory is the deployment's — a budget, not a
# count, because a 76 MB LoRA and a 325 MB LoRA are not one unit each (section
# 11). The three halves below are the door's two refusals and the one still that
# proves a selection reaches the runtime.

G18_ID = "flux2-klein-4b-gguf-q4"
G18_ENTRY = ROOT / "model" / "entry.yaml"
G18_DIR = EVIDENCE / "g18"
G18_ALIAS = "pixel-art"
"""The catalog's first alias: the 325 MB LoRA the runtime patch was measured on."""
G18_SIDE = 256
"""The still's size: a LoRA is the variable here, the box is not."""
G18_PROMPT = (
    "pixel art sprite, a brave knight in shining armor holding a sword, game asset, "
    "transparent background"
)
"""The pixel-art LoRA's own card prompt, from `patches/README.md`."""


def _g18_no_catalog_entry() -> pathlib.Path:
    """A synthetic entry that accepts the field and declares no catalog.

    The law's rule is per model: an entry without a `loras` block accepts no LoRA
    at all. This fixture is small enough to prove it without hashing a
    checkpoint (guard 15 shows the same shape for `limits.steps`).
    """
    G18_DIR.mkdir(parents=True, exist_ok=True)
    asset = G18_DIR / "g18-asset.bin"
    asset.write_bytes(b"guard 18: a component the stub never reads\n")
    document = {
        "id": "g18-no-catalog",
        "adapter": G15_STUB,
        "checkpoint": str(asset),
        "components": {"weights": str(asset)},
        "steps": 4,
        "guidance": 1.0,
        "limits": {"max_pixels": G18_SIDE * G18_SIDE, "steps": {"min": 3, "max": 9}},
        "request_fields": ["prompt", "seed", "width", "height", "out", "lora"],
        "expected_census": {"parameters": 1},
        "defaults": {"width": G18_SIDE, "height": G18_SIDE, "format": "png"},
        "warmup": {"width": G18_SIDE, "height": G18_SIDE, "prompt": "warm up", "seed": 0},
    }
    path = G18_DIR / "g18-no-catalog.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _g18_foreign_lora_entry() -> pathlib.Path:
    """A synthetic entry whose catalog borrows another model's folder.

    The ownership rule is structural (protocol sections 3 and 6.1): a LoRA
    belongs to the model it was verified on, so a path under
    `model/assets/loras/<some other id>/` refuses at load, naming the path and
    the folder it should have come from. The file need not exist — the folder is
    checked before the file is, so the refusal is about ownership.
    """
    G18_DIR.mkdir(parents=True, exist_ok=True)
    asset = G18_DIR / "g18-asset.bin"
    asset.write_bytes(b"guard 18: a component the stub never reads\n")
    document = {
        "id": "g18-foreign-lora",
        "adapter": G15_STUB,
        "checkpoint": str(asset),
        "components": {"weights": str(asset)},
        "steps": 4,
        "guidance": 1.0,
        "limits": {"max_pixels": G18_SIDE * G18_SIDE, "steps": {"min": 3, "max": 9}},
        "request_fields": ["prompt", "seed", "width", "height", "out", "lora"],
        "expected_census": {"parameters": 1},
        "defaults": {"width": G18_SIDE, "height": G18_SIDE, "format": "png"},
        "warmup": {"width": G18_SIDE, "height": G18_SIDE, "prompt": "warm up", "seed": 0},
        "loras": {
            "pixel-art": {
                "path": "model/assets/loras/another-model/pixel-art.safetensors",
                "weight": 1.0,
            }
        },
    }
    path = G18_DIR / "g18-foreign-lora.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _g18_host(name: str, lora_budget_mib: int, vram_mib: int = 7857) -> pathlib.Path:
    """A host declaration that differs from the shipped one in the budget only."""
    G18_DIR.mkdir(parents=True, exist_ok=True)
    path = G18_DIR / name
    path.write_text(
        yaml.safe_dump(
            {
                "id": "p6-guard-18",
                "vram_mib": vram_mib,
                "offload": True,
                "lora_budget_mib": lora_budget_mib,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _g18_restore_host() -> None:
    """Put the tree's declaration back exactly as it was found."""
    if HOST_DECLARATION is None:
        HOST_FILE.unlink(missing_ok=True)
        return
    HOST_FILE.write_bytes(HOST_DECLARATION)


# --- guard 19: a request may carry an image --------------------------------
#
# FLUX.2 [klein] is trained for multi-reference editing and the vendored runtime
# takes `-r, --ref-image` repeatably, so the request gained `image`: a list of
# paths, the same shape as `out` (protocol section 4.1). The entry declares how
# many references its model accepts; the adapter carries them, in order, to the
# runtime. Three halves below — the door's two refusals and one still that proves
# a reference reached the model — plus the contract checks that need no card.

G19_ID = "flux2-klein-4b-gguf-q4"
"""The promoted entry's id: the only entry in this tree whose model is an editor."""

G19_DIR = ROOT / "tests" / "e2e" / "image-input" / "evidence"
"""The stills and the synthetic entries: a run product, inside the repo and
gitignored by the same rule every other evidence folder follows."""

G19_SIDE = 256
G19_STEPS = 4
"""The cheapest still the promoted entry admits: its own 256x256 floor at the
floor of its step range. The reference is the variable here, the box is not."""

G19_REFERENCE_PROMPT = "a red ceramic vase on a white table, studio light"
"""The picture the service renders first, and then edits: cheap, and its subject
is unambiguous in the still, so the eye can tell the reference was read."""

G19_EDIT_PROMPT = "Turn this scene into a real photograph"
G19_SEED = 1901

G19_STUB = "g19noimages"
"""A registered adapter that declares no reference capability.

Used only to prove the boot refusal: an entry that declares a count behind an
adapter that cannot carry one is refused by `load_adapter`, not served with the
picture dropped (protocol section 6.3).
"""


class _G19NoImageAdapter:
    """An adapter that carries no reference image and says so, as Z-Image's does."""

    name = G19_STUB
    supports_loras = False
    supports_images = False

    def __init__(self, entry) -> None:
        self.entry = entry
        self.last_load_s = 0.0


def _g19_entry(name: str, *, image_block: bool, image_field: bool) -> pathlib.Path:
    """A synthetic entry whose reference declaration is spelled by the caller.

    `image_block` and `image_field` are the two halves that must agree: the
    capability and the request field. An entry with one and not the other is a
    declaration the system would half-honour, so the loader refuses it.
    """
    G19_DIR.mkdir(parents=True, exist_ok=True)
    asset = G19_DIR / "g19-asset.bin"
    asset.write_bytes(b"guard 19: a component no adapter here reads\n")
    fields = ["prompt", "seed", "width", "height", "out"]
    if image_field:
        fields.append("image")
    document: dict[str, object] = {
        "id": f"g19-{name.replace('.yaml', '').replace('_', '-')}",
        "adapter": G19_STUB,
        "checkpoint": str(asset),
        "components": {"weights": str(asset)},
        "steps": 4,
        "guidance": 1.0,
        "limits": {"max_pixels": G19_SIDE * G19_SIDE, "steps": {"min": 4, "max": 4}},
        "request_fields": fields,
        "expected_census": {"parameters": 1},
        "defaults": {"width": G19_SIDE, "height": G19_SIDE, "format": "png"},
        "warmup": {"width": G19_SIDE, "height": G19_SIDE, "prompt": "warm up", "seed": 0},
    }
    if image_block:
        document["image"] = {"max": 2}
    path = G19_DIR / name
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


class ServiceCase(GuardCase):
    """One shared server for the class, stopped by guard 2; guards 16 and 13 start theirs."""

    @classmethod
    def setUpClass(cls) -> None:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        FILES.mkdir(parents=True, exist_ok=True)
        # The fixture pays a boot, so it gets the same budget as a test: a `start`
        # that never returns must fail here by name instead of hanging the matrix.
        _arm_deadline(f"{cls.__name__}.setUpClass", time.perf_counter())
        try:
            try:
                _preflight()
            except Exception as exc:  # noqa: BLE001 — recorded, then reported per guard
                _record_error("fixture", exc)
                return

            # Guard 2, first half: a client with no server must not start one.
            try:
                _put("guard02.generate_without_server", _generate_without_server())
            except Exception as exc:  # noqa: BLE001
                _record_error("guard02.generate_without_server", exc)

            try:
                _put("guard02.start", _start())
            except Exception as exc:  # noqa: BLE001
                _record_error("guard02.start", exc)
                return

            try:
                _put("guard02.health", _health())
                _put("guard02.state", _state())
                _put("baseline.render_count", _render_count())
                _put("baseline.render_failure_count", _render_failure_count())
                _put("baseline.pids", _server_pids())
            except Exception as exc:  # noqa: BLE001
                _record_error("guard02.after_start", exc)
        finally:
            _disarm_deadline()

    @classmethod
    def tearDownClass(cls) -> None:
        # Safety net only: guard 2 already stopped the server and asserted it.
        try:
            _put("cleanup", _force_clean())
        except Exception as exc:  # noqa: BLE001
            _record_error("cleanup", exc)

    # --- 1: guard 3 owns the four stills ------------------------------------

    def test_0100_guard03_the_warmup_is_real(self) -> None:
        """Guard 3: the first render after `start` costs steady state, not a fresh load.

        The four requests are identical in everything that can affect the render
        — prompt, seed, width, height, no upscale — and differ only in the
        destination path, because four stills must exist for guard 5 to compare.
        """
        self.obs("guard02.health")
        baseline = self.obs("baseline.render_count")

        renders = []
        for index in range(1, 5):
            destination = FILES / f"g3-warmup-{index}.png"
            if destination.exists():
                destination.unlink()
            payload = {
                "prompt": PROMPT,
                "seed": SEED,
                "width": WIDTH,
                "height": HEIGHT,
                "out": str(destination),
            }
            began = time.perf_counter()
            status, body = _generate(payload)
            renders.append(
                {
                    "status": status,
                    "body": body,
                    "wall_s": round(time.perf_counter() - began, 3),
                    "out": str(destination),
                }
            )
        _put("guard03.renders", renders)

        for index, render in enumerate(renders, start=1):
            self.assertEqual(render["status"], 200, f"render {index} failed: {render['body']}")
            self.assertEqual(render["body"].get("seed"), SEED)
            self.assertEqual((render["body"].get("width"), render["body"].get("height")), (WIDTH, HEIGHT))
            self.assertGreater(render["body"].get("render_s", 0), 0.0, f"render {index} reported no render_s")

        # The instrument guard 1 relies on, checked where the count is known:
        # four successful requests must move the served counter by exactly four.
        after = _render_count()
        _put("guard03.render_count_delta", {"baseline": baseline, "after": after})
        self.assertEqual(after - baseline, 4, "the served counter did not move by four")

        first = renders[0]["body"]["render_s"]
        rest = [render["body"]["render_s"] for render in renders[1:]]
        median = statistics.median(rest)
        _put(
            "guard03",
            {"first_render_s": first, "next_render_s": rest, "median_next_s": median, "ratio": round(first / median, 4)},
        )
        print(
            f"guard 3: first {first:.3f} s; next three "
            + ", ".join(f"{value:.3f}" for value in rest)
            + f"; median {median:.3f} s; ratio {first / median:.3f} (limit {WARMUP_RATIO})"
        )
        self.assertLessEqual(
            first,
            WARMUP_RATIO * median,
            f"the first render after start cost {first:.3f} s against a {median:.3f} s median "
            f"({first / median:.2f}x): the port was bound before the warm-up finished",
        )

    # --- 2: guard 5 borrows those bytes ------------------------------------

    def test_0200_guard05_determinism(self) -> None:
        """Guard 5: the same request and seed produce byte-identical files.

        Borrows guard 3's four stills: they are four separate renders of one
        request, so any nondeterminism in the sampling or the seed path shows up
        as four different files.
        """
        renders = self.obs("guard03.renders")
        paths = [pathlib.Path(render["out"]) for render in renders]
        for path in paths:
            self.assertTrue(path.is_file(), f"{path} was not written")

        reference = paths[0]
        reference_bytes = reference.read_bytes()
        digests = [_sha256(path) for path in paths]

        _put(
            "guard05",
            {
                "files": [{"path": str(path), "bytes": path.stat().st_size, "sha256": digest} for path, digest in zip(paths, digests)],
            },
        )
        print(f"guard 5: 4 stills, sha256 {digests[0][:16]}…, {len(set(digests))} distinct digest(s)")

        self.assertEqual(len(set(digests)), 1, f"the four stills differ: {digests}")
        for path in paths[1:]:
            self.assertEqual(path.read_bytes(), reference_bytes, f"{path} differs from {reference}")
            self.assertEqual(path.stat().st_size, reference.stat().st_size)

    # --- 3: guard 6 owns the CLI still -------------------------------------

    def test_0300_guard06_default_folder(self) -> None:
        """Guard 6: `generate` with no `--out` writes into `out/` and says where."""
        before = set(OUTPUT_DIR.glob("*.png")) if OUTPUT_DIR.is_dir() else set()
        completed = _cli("generate", "--prompt", PROMPT, "--seed", str(SEED))
        after = set(OUTPUT_DIR.glob("*.png")) if OUTPUT_DIR.is_dir() else set()

        _put(
            "guard06",
            {
                "exit": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "new_files": sorted(str(path) for path in after - before),
            },
        )
        print(f"guard 6: exit {completed.returncode}, stdout {completed.stdout.strip()!r}")
        if completed.stderr:
            print(f"guard 6: stderr {completed.stderr.strip()!r}")

        self.assertEqual(completed.returncode, 0, f"generate failed: {completed.stderr}")
        self.assertEqual(completed.stderr, "", "the CLI put diagnostics on stderr for a successful request")

        printed = completed.stdout.strip()
        self.assertTrue(printed, "generate printed no path")
        path = pathlib.Path(printed)
        self.assertTrue(path.is_absolute(), f"{printed} is not an absolute path")
        self.assertEqual(
            path.parent.resolve(), OUTPUT_DIR.resolve(), f"{printed} is not inside the default folder {OUTPUT_DIR}"
        )
        self.assertTrue(path.is_file(), f"{printed} does not exist")
        self.assertGreater(path.stat().st_size, 1024, f"{path} is {path.stat().st_size} bytes")

        # Protocol 4.1: `out/` names the still `<UTC timestamp>-<seed>.png`.
        self.assertRegex(path.name, rf"^\d{{8}}T\d{{6}}Z-{SEED}\.png$")

        # The guard is about a path that exists, so it has to be a real still.
        self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG")
        _put("guard06.path", str(path))

    # --- 4: guard 7 borrows that still and one of guard 3's ---------------

    def test_0400_guard07_cli_api_parity(self) -> None:
        """Guard 7: the CLI and a direct POST for the same seed produce one file's bytes.

        `cmp`, not a similarity metric: the CLI must be a client with no renderer
        of its own, and a renderer that drifted would not survive a byte compare.
        """
        cli_path = pathlib.Path(self.obs("guard06.path"))
        post_path = pathlib.Path(self.obs("guard03.renders")[0]["out"])

        for path in (cli_path, post_path):
            self.assertTrue(path.is_file(), f"{path} is missing")

        identical = filecmp.cmp(cli_path, post_path, shallow=False)
        cli_digest = _sha256(cli_path)
        post_digest = _sha256(post_path)
        _put(
            "guard07",
            {
                "cli": {"path": str(cli_path), "bytes": cli_path.stat().st_size, "sha256": cli_digest},
                "post": {"path": str(post_path), "bytes": post_path.stat().st_size, "sha256": post_digest},
                "identical": identical,
            },
        )
        print(f"guard 7: cli {cli_digest[:16]}… against post {post_digest[:16]}… → identical={identical}")

        self.assertEqual(cli_digest, post_digest, "the CLI and the API wrote different bytes for the same seed")
        self.assertTrue(identical, "cmp says the two stills differ")

    # --- 5: guard 9 owns two concurrent stills -----------------------------

    def test_0500_guard09_single_flight(self) -> None:
        """Guard 9: two concurrent requests both succeed and never run two models.

        Duration is admissible evidence here, and the reason is physical: one
        transformer occupies 6057 MiB of an 8188 MiB card, so a second worker
        could not overlap two 1280x720 renders — it would fail with an
        allocation error rather than report a duration. Serialisation therefore
        shows as the second request waiting a whole render (`duration_s` near
        2x the first), while a second worker that somehow shared the card would
        report two near-equal durations. The queue depth sampled while both are
        in flight is the same fact seen directly: one worker means one request
        waits.

        The second request also carries `upscale: true` at the native size, which
        guard 10 borrows: a request that fits must deliver `upscale: null` even
        when the client permits the stage.
        """
        self.obs("guard02.health")
        pids_before = _server_pids()

        requests = {
            "A": {
                "prompt": PROMPT,
                "seed": 91,
                "width": WIDTH,
                "height": HEIGHT,
                "out": str(FILES / "g9-concurrent-a.png"),
            },
            "B": {
                "prompt": PROMPT,
                "seed": 92,
                "width": WIDTH,
                "height": HEIGHT,
                "upscale": True,
                "out": str(FILES / "g9-concurrent-b.png"),
            },
        }
        for request in requests.values():
            pathlib.Path(request["out"]).unlink(missing_ok=True)

        barrier = threading.Barrier(2)
        results: dict[str, dict] = {}
        depths: list[int] = []
        stop_polling = threading.Event()

        def fire(label: str) -> None:
            barrier.wait()
            began = time.perf_counter()
            status, body = _generate(requests[label])
            results[label] = {
                "status": status,
                "body": body,
                "wall_s": round(time.perf_counter() - began, 3),
            }

        def poll() -> None:
            while not stop_polling.is_set():
                status, body = _health()
                if status == 200:
                    depths.append(int(body.get("queue", {}).get("depth", -1)))
                stop_polling.wait(0.5)

        poller = threading.Thread(target=poll, name="p6-depth", daemon=True)
        # Daemon threads: if the deadline aborts this test mid-join, a worker blocked
        # on a socket must not keep the interpreter alive past the failure.
        workers = [
            threading.Thread(target=fire, args=(label,), name=f"p6-{label}", daemon=True)
            for label in requests
        ]
        poller.start()
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=HTTP_TIMEOUT_S + 120)
        stop_polling.set()
        poller.join(timeout=10)

        _put(
            "guard09",
            {
                "requests": requests,
                "results": results,
                "peak_queue_depth": max(depths) if depths else None,
                "depth_samples": len(depths),
                "pids_before": pids_before,
                "pids_after": _server_pids(),
            },
        )

        for label, result in results.items():
            self.assertEqual(result["status"], 200, f"request {label} failed: {result['body']}")
            path = pathlib.Path(requests[label]["out"])
            self.assertTrue(path.is_file(), f"request {label} wrote no file")
            self.assertEqual(_png_size(path), (WIDTH, HEIGHT))
        self.assertEqual(sorted(results), ["A", "B"], "a concurrent request never returned")

        durations = {label: float(result["body"]["duration_s"]) for label, result in results.items()}
        short, long = sorted(durations.values())
        peak = max(depths) if depths else -1
        print(
            f"guard 9: duration_s {durations['A']:.3f} / {durations['B']:.3f} s, "
            f"ratio {long / short:.3f} (separator {SERIAL_RATIO}); peak queue depth {peak} "
            f"over {len(depths)} samples"
        )

        self.assertGreaterEqual(
            long / short,
            SERIAL_RATIO,
            f"the two requests did not serialise ({short:.3f} s and {long:.3f} s): "
            "a second worker would overlap them",
        )
        self.assertGreaterEqual(
            peak,
            1,
            "the queue never held a waiting request: two workers would leave the depth at zero",
        )
        self.assertEqual(_server_pids(), pids_before, "a second server process appeared")
        self.assertEqual(len(pids_before), 1, f"expected exactly one server process, found {pids_before}")

    # --- 6: guard 10 owns the HD still ------------------------------------

    def test_0600_guard10_the_upscale_stage(self) -> None:
        """Guard 10: the stage runs only when permitted and above the native ceiling.

        Three refusals and one delivery: a size above the ceiling without the
        permission, a size beyond the stage's own declared reach even with it,
        and then the delivery — whose response must declare the base it started
        from, its own cost, and the render's census rather than its own.
        """
        self.obs("guard02.health")
        declaration = yaml.safe_load((ROOT / "model" / "upscaler.yaml").read_text(encoding="utf-8"))
        factor = int(declaration["scale"])
        ceiling = MAX_PIXELS * factor * factor

        baseline_renders = _render_count()
        baseline_failures = _render_failure_count()

        refusals = {
            "above the ceiling without permission": {"prompt": PROMPT, "width": 2560, "height": 1440},
            "beyond the stage's declared reach": {
                "prompt": PROMPT,
                "width": 4096,
                "height": 2048,
                "upscale": True,
            },
        }
        refused: dict[str, dict] = {}
        for reason, payload in refusals.items():
            status, body = _generate(payload)
            refused[reason] = {"status": status, "body": body}
            self.assertEqual(status, 400, f"{reason}: expected a refusal, got {status} {body}")
            error = body.get("error", {})
            self.assertEqual(error.get("code"), "invalid_request", f"{reason}: {body}")

        first = refused["above the ceiling without permission"]["body"]["error"]["message"]
        second = refused["beyond the stage's declared reach"]["body"]["error"]["message"]
        self.assertIn(str(MAX_PIXELS), first, f"the refusal does not name the ceiling: {first}")
        self.assertIn("upscale", first, f"the refusal does not name the permission: {first}")
        self.assertIn(str(ceiling), second, f"the refusal does not name the stage's reach: {second}")

        # A refusal is validation, so it never reaches the worker.
        self.assertEqual(_render_count(), baseline_renders, "a refused request reached the worker")
        self.assertEqual(_render_failure_count(), baseline_failures, "a refused request reached the renderer")

        destination = FILES / "g10-upscaled-2560x1440.png"
        destination.unlink(missing_ok=True)
        target_width, target_height = 2560, 1440
        status, body = _generate(
            {
                "prompt": PROMPT,
                "seed": SEED,
                "width": target_width,
                "height": target_height,
                "upscale": True,
                "out": str(destination),
            }
        )
        _put("guard10", {"declaration": declaration, "refusals": refused, "status": status, "render": body})

        self.assertEqual(status, 200, f"the permitted HD request failed: {body}")
        self.assertEqual((body.get("width"), body.get("height")), (target_width, target_height))

        stage = body.get("upscale")
        self.assertIsInstance(stage, dict, f"the response declares no stage: {stage}")
        print(f"guard 10: stage {stage}; census {body.get('census')}")

        self.assertEqual(stage.get("model"), declaration["id"])
        self.assertEqual(stage.get("scale"), factor)
        # The base the render reached, not the size the client asked for.
        self.assertEqual(stage.get("from"), [WIDTH, HEIGHT])
        self.assertEqual(stage.get("to"), [target_width, target_height])
        self.assertGreater(float(stage.get("upscale_s", 0.0)), 0.0, "the stage reports no cost")

        # The census is the render's: the stage synthesises pixels, not parameters.
        self.assertEqual(body.get("census"), PROTOCOL_CENSUS)

        self.assertTrue(destination.is_file(), f"{destination} was not written")
        self.assertEqual(_png_size(destination), (target_width, target_height))
        print(
            f"guard 10: refused without permission ({first[:60]}…); delivered "
            f"{target_width}x{target_height} from {stage.get('from')} in {stage.get('upscale_s')} s"
        )

        # Borrowed from guard 9's request B: permitted, but at the native size,
        # so the stage must not run.
        concurrent = self.obs("guard09")
        native_permitted = concurrent["results"]["B"]["body"]
        self.assertIsNone(
            native_permitted.get("upscale"),
            f"a request at the native size ran the stage anyway: {native_permitted.get('upscale')}",
        )

    # --- 7: guard 15 owns four stills -------------------------------------

    def test_0650_guard15_steps(self) -> None:
        """Guard 15: the step count is a request field bounded by the entry.

        Four facts, in the order the door sees them:

        1. The law at load. The entry's own `steps` is the default a request
           inherits, so a default outside `limits.steps` refuses the entry — a
           range that does not contain its own default is not a range.
        2. The door and the adapter. A step outside the range, passed through
           `render.render` to a synthetic entry naming a stub, raises before the
           stub is built: zero instances is the proof that no adapter call was
           made. A render would only prove the still was not written.
        3. The service. The same two out-of-range values over HTTP are
           `400 invalid_request` naming the range, and the worker counters do not
           move; an in-range value appears in the response as the value used; a
           request without `steps` reports the entry's default (borrowed from
           guard 3, which names none).
        4. The bytes. 8 and 12 steps at one seed produce different files, and
           each is identical across two runs — the response saying `8` proves
           nothing if the sampler ran twelve forwards anyway.
        """
        self.obs("guard02.health")
        from coltman_images import adapter as adapter_module
        from coltman_images.entry import EntryError, load_entry
        from coltman_images.render import render

        entry = load_entry(ZIMAGE_ENTRY)
        low, high = PROTOCOL_STEPS["min"], PROTOCOL_STEPS["max"]
        outside = (low - 1, high + 1)
        self.assertEqual(
            (entry.steps_min, entry.steps_max),
            (low, high),
            "the entry's limits.steps does not carry the range the law declares",
        )
        self.assertEqual(
            entry.steps, PROTOCOL_DEFAULT_STEPS, "the entry's default is not the declared 12"
        )

        # 1. the entry's default must lie inside the range it is bounded by.
        with self.assertRaises(EntryError) as loose:
            load_entry(_g15_entry(steps=low - 1, name="g15-entry-outside.yaml"))
        self.assertIn("limits.steps", str(loose.exception), "the refusal did not name the range")
        self.assertIn(f"{low}..{high}", str(loose.exception), "the refusal did not name the bounds")

        # 1b. the range belongs to the entry, and a single-value range is one.
        # A distilled model may declare a point as its regime: the law must admit
        # that range (protocol section 4.1), and admit nothing outside it either.
        distilled = load_entry(
            _g15_entry(
                steps=POINT_STEPS["min"],
                name="g15-entry-distilled.yaml",
                steps_range=POINT_STEPS,
            )
        )
        self.assertEqual(
            (distilled.steps_min, distilled.steps_max),
            (POINT_STEPS["min"], POINT_STEPS["max"]),
            "the law refused or moved a distilled model's declared range",
        )
        self.assertEqual(
            distilled.accepts({"prompt": "x", "steps": POINT_STEPS["min"]}),
            [],
            "the law refused the step count a distilled entry declares as its regime",
        )
        for off in (POINT_STEPS["min"] - 1, POINT_STEPS["min"] + 1):
            said = " ".join(distilled.accepts({"prompt": "x", "steps": off}))
            self.assertIn("steps", said, f"steps {off} was not refused by name: {said}")
            self.assertIn(
                f"{POINT_STEPS['min']}..{POINT_STEPS['max']}",
                said,
                f"steps {off}: the refusal did not name the entry's own range: {said}",
            )

        # 2. the door: out of range refused before the adapter exists.
        adapter_module._REGISTRY[G15_STUB] = f"{__name__}:_G15StubAdapter"
        stub_entry = load_entry(_g15_entry())
        _G15StubAdapter.instances.clear()
        never_written = EVIDENCE / "g15-refused.png"
        never_written.unlink(missing_ok=True)
        with self.assertRaises(ValueError) as refused:
            render(
                stub_entry,
                prompt="a step count outside the range",
                seed=SEED % 100,
                width=G15_SIDE,
                height=G15_SIDE,
                steps=low - 1,
                out=str(never_written),
                write=False,
            )
        adapter_refusal = str(refused.exception)
        self.assertIn("steps", adapter_refusal, f"the refusal does not name the field: {adapter_refusal}")
        self.assertIn(f"{low}..{high}", adapter_refusal, f"the refusal does not name the range: {adapter_refusal}")
        self.assertEqual(
            _G15StubAdapter.instances, [], "a refused step reached the adapter: the stub was built"
        )
        self.assertFalse(never_written.exists(), "a refused step wrote a still")

        # 3. the service: same refusal at the HTTP door, no worker involvement.
        def _service_counters() -> tuple[int, int]:
            return _render_count(), _render_failure_count()

        counters_before = _service_counters()
        service_refusals: dict[int, dict] = {}
        for bad in outside:
            status, body = _generate({"prompt": PROMPT, "steps": bad})
            service_refusals[bad] = {"status": status, "body": body}
            self.assertEqual(status, 400, f"steps {bad}: expected 400, got {status} {body}")
            error = body.get("error", {})
            self.assertEqual(error.get("code"), "invalid_request", f"steps {bad}: {body}")
            message = str(error.get("message", ""))
            self.assertIn("steps", message, f"steps {bad}: the refusal does not name the field: {message}")
            self.assertIn(
                f"{low}..{high}", message, f"steps {bad}: the refusal does not name the range: {message}"
            )
        self.assertEqual(
            _service_counters(), counters_before, "a refused step reached the worker"
        )
        counters_after_refusals = _service_counters()

        # An absent `steps` means the entry's default: guard 3's requests name none.
        defaulted = self.obs("guard03.renders")[0]["body"].get("steps")
        self.assertEqual(
            defaulted, PROTOCOL_DEFAULT_STEPS, f"a request without steps rendered at {defaulted}"
        )

        # 4. the bytes: 8 and 12 differ, each stable across two runs.
        runs: list[dict] = []
        for index, steps in enumerate(G15_STEPS, start=1):
            destination = FILES / f"g15-run{index}-steps{steps}.png"
            destination.unlink(missing_ok=True)
            began = time.perf_counter()
            status, body = _generate(
                {
                    "prompt": PROMPT,
                    "seed": SEED,
                    "width": G15_RENDER_SIDE,
                    "height": G15_RENDER_SIDE,
                    "steps": steps,
                    "out": str(destination),
                }
            )
            runs.append(
                {
                    "steps": steps,
                    "status": status,
                    "body": body,
                    "wall_s": round(time.perf_counter() - began, 3),
                    "path": str(destination),
                    "sha256": _sha256(destination) if destination.is_file() else "",
                }
            )

        _put(
            "guard15",
            {
                "range": PROTOCOL_STEPS,
                "default": PROTOCOL_DEFAULT_STEPS,
                "entry": {"steps": entry.steps, "min": entry.steps_min, "max": entry.steps_max},
                "entry_refusal": str(loose.exception),
                "adapter_refusal": adapter_refusal,
                "adapter_instances": len(_G15StubAdapter.instances),
                "refused_still_written": never_written.exists(),
                "service_refusals": service_refusals,
                "render_counters": {"before": counters_before, "after_refusals": counters_after_refusals},
                "defaulted_response_steps": defaulted,
                "runs": runs,
            },
        )

        print(
            f"guard 15: entry steps {entry.steps} inside limits.steps "
            f"{entry.steps_min}..{entry.steps_max}; a default of {low - 1} refused at load "
            f"({loose.exception})"
        )
        print(
            f"guard 15: steps {low - 1} refused before the adapter existed — "
            f"{len(_G15StubAdapter.instances)} stub instance(s) built ({adapter_refusal})"
        )
        print(
            f"guard 15: POST steps {outside[0]} and {outside[1]} → 400 invalid_request; "
            f"worker counters {counters_before} → {counters_after_refusals}"
        )
        print(f"guard 15: a request without steps rendered at the entry default ({defaulted})")

        by_steps: dict[int, list[dict]] = {}
        for run in runs:
            by_steps.setdefault(run["steps"], []).append(run)
        for steps, pair in sorted(by_steps.items()):
            digests = {run["sha256"] for run in pair}
            render_s = " / ".join(f"{run['body'].get('render_s')}" for run in pair)
            print(
                f"guard 15: steps {steps} → {len(digests)} distinct digest(s) over "
                f"{len(pair)} runs, sha256 {pair[0]['sha256'][:16]}…, render_s {render_s} s"
            )
            self.assertEqual(len(digests), 1, f"steps {steps} is not deterministic: {sorted(digests)}")

        for run in runs:
            self.assertEqual(run["status"], 200, f"steps {run['steps']} failed: {run['body']}")
            self.assertEqual(
                run["body"].get("steps"),
                run["steps"],
                f"the response says {run['body'].get('steps')} for a request of {run['steps']}",
            )
            still = pathlib.Path(run["path"])
            self.assertTrue(still.is_file(), f"{still} was not written")
            self.assertEqual(_png_size(still), (G15_RENDER_SIDE, G15_RENDER_SIDE))

        eight = by_steps[8][0]["sha256"]
        twelve = by_steps[12][0]["sha256"]
        self.assertNotEqual(
            eight, twelve, "8 and 12 steps produced the same bytes: the step count never reached the sampler"
        )
        print(f"guard 15: steps 8 {eight[:16]}… against steps 12 {twelve[:16]}… → different bytes")

    # --- 8: guard 1, on a quiet queue -------------------------------------

    def test_0700_guard01_request_validation(self) -> None:
        """Guard 1: four malformed requests refused, none of them reaching the card.

        "Before any GPU work" is proved by the render counter, not by the clock:
        the server logs every still it serves and every render that raised, so a
        request that reached the worker would move one of those two numbers. The
        queue depth is the same fact at the door. Latency is printed for the
        record and asserted on by nothing.
        """
        self.obs("guard02.health")

        cases = [
            ("unknown field", {"prompt": "x", "bogus": 1}),
            ("missing prompt", {"width": WIDTH, "height": HEIGHT}),
            ("size is not a multiple of 16", {"prompt": "x", "width": 1001, "height": HEIGHT}),
            ("out is a relative path", {"prompt": "x", "out": "p6-relative.png"}),
        ]

        renders_before = _render_count()
        failures_before = _render_failure_count()
        relative_candidate = ROOT / "p6-relative.png"
        relative_candidate.unlink(missing_ok=True)

        results = []
        for reason, payload in cases:
            began = time.perf_counter()
            status, body = _generate(payload)
            elapsed = round(time.perf_counter() - began, 3)
            health_status, health_body = _health()
            results.append(
                {
                    "reason": reason,
                    "payload": payload,
                    "status": status,
                    "body": body,
                    "wall_s": elapsed,
                    "queue_depth_after": health_body.get("queue", {}).get("depth") if health_status else None,
                }
            )

        renders_after = _render_count()
        failures_after = _render_failure_count()
        _put(
            "guard01",
            {
                "cases": results,
                "render_count": {"before": renders_before, "after": renders_after},
                "render_failure_count": {"before": failures_before, "after": failures_after},
            },
        )

        for result in results:
            label = result["reason"]
            self.assertEqual(result["status"], 400, f"{label}: expected 400, got {result['status']} {result['body']}")
            error = result["body"].get("error")
            self.assertIsInstance(error, dict, f"{label}: the body is not the declared envelope: {result['body']}")
            self.assertEqual(sorted(result["body"]), ["error"], f"{label}: the envelope carries more than `error`")
            self.assertEqual(error.get("code"), "invalid_request", f"{label}: {error}")
            self.assertTrue(error.get("message"), f"{label}: the refusal says nothing")
            self.assertEqual(result["queue_depth_after"], 0, f"{label}: the queue moved")
            print(f"guard 1: {label} → 400 {error.get('code')} in {result['wall_s']} s (not asserted)")

        self.assertFalse(relative_candidate.exists(), "a relative `out` wrote a file anyway")
        self.assertEqual(renders_after, renders_before, "a refused request reached the worker")
        self.assertEqual(failures_after, failures_before, "a refused request reached the renderer")

    # --- 9: guard 4, the measured half ------------------------------------

    def test_0800_guard04_census_measured(self) -> None:
        """Guard 4: the measured census equals the entry's, in /health and in every response."""
        from coltman_images.entry import load_entry

        status, health = self.obs("guard02.health")
        self.assertEqual(status, 200, f"/health did not answer: {health}")

        entry = load_entry(ZIMAGE_ENTRY)
        observed = {
            "health": health.get("census"),
            **{f"guard3.render{i + 1}": render["body"].get("census") for i, render in enumerate(self.obs("guard03.renders"))},
            **{
                f"guard9.{label}": result["body"].get("census")
                for label, result in self.obs("guard09")["results"].items()
            },
            "guard10.hd": self.obs("guard10")["render"].get("census"),
        }
        _put("guard04", {"observed": observed, "entry_expected": entry.expected_census, "protocol": PROTOCOL_CENSUS})

        for where, census in observed.items():
            print(f"guard 4: {where} census {census}")
            self.assertEqual(census, PROTOCOL_CENSUS, f"{where} reports {census}, not the declared census")
            self.assertEqual(census, dict(entry.expected_census), f"{where} disagrees with the entry")

    # --- 10: guard 2, last, because it stops the server -------------------

    def test_0850_guard12_one_instance(self) -> None:
        """Guard 12: one card, one instance — a deleted state file cannot buy a second.

        The mutex is the truth and the state file is a convenience. Two things are
        proved: `start` reports the running server instead of spawning a second
        once the state file is gone, and a server launched by hand on another port
        is refused **before it loads a weight**, because the lock is taken before
        the entry is even resolved.

        The state file is restored at the end: the server writes it only at boot,
        and guard 2's `stop` reads it.
        """
        pids_before = _server_pids()
        self.assertEqual(len(pids_before), 1, f"expected exactly one server, saw {pids_before}")
        self.assertIsNotNone(_state(), "guard 12 needs the state file the fixture recorded")

        STATE_FILE.unlink()
        self.assertFalse(STATE_FILE.exists(), "the state file survived its deletion")

        again = _cli("start", timeout=120)
        print(
            f"guard 12: state file deleted, start exit {again.returncode}, "
            f"pids {_server_pids()} (was {pids_before})"
        )
        self.assertEqual(
            _server_pids(), pids_before, f"a second instance appeared: {_server_pids()}"
        )
        self.assertEqual(
            again.returncode, 0, f"start failed instead of reporting: {again.stderr.strip()}"
        )
        self.assertIn(
            str(pids_before[0]),
            again.stdout + again.stderr,
            "start did not name the running server",
        )

        direct = subprocess.run(
            [str(PYTHON), "-m", "coltman_images.server", "--port", "8599"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        message = (direct.stdout + direct.stderr).strip()
        last_line = message.splitlines()[-1][:110] if message else "(silent)"
        print(f"guard 12: direct second server exit {direct.returncode} — {last_line}")
        self.assertEqual(
            direct.returncode,
            4,
            f"a hand-launched second server exited {direct.returncode}: {message}",
        )
        self.assertIn("instance", message.lower(), "the refusal did not name the reason")
        self.assertEqual(_server_pids(), pids_before, "the refused start left a process behind")

        # The server writes the state file only at boot, so the test puts it back
        # from /health — guard 2's stop reads it, and a deleted file would make
        # `stop` report "not running" while a server is still holding the card.
        status, body = _health()
        self.assertEqual(status, 200, "/health stopped answering during guard 12")
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(
                {
                    key: body[key]
                    for key in ("pid", "port", "model", "started_at", "warm_at", "census")
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(_server_pids(), pids_before, "more than one instance after the restore")

    def test_0900_guard02_lifecycle(self) -> None:
        """Guard 2: start → health warm → generate → stop, and the idempotent edges.

        `start` and `/health` were recorded by the fixture and are re-asserted
        here; `generate` is the CLI still guard 6 already made; what remains is
        the double start, the stop, and the stop of a stopped server.
        """
        state = self.obs("guard02.state")
        health_status, health = self.obs("guard02.health")

        # start: exit 0, and the port answers warm only after the warm-up.
        start = self.obs("guard02.start")
        print(f"guard 2: start exit {start['exit']} in {start['wall_s']} s; /health {health.get('status')}")
        self.assertEqual(start["exit"], 0, f"start failed: {start['stdout']}{start['stderr']}")
        self.assertEqual(health_status, 200, f"/health did not answer: {health}")
        self.assertEqual(health.get("status"), "warm")
        self.assertEqual(health.get("pid"), state.get("pid"))
        self.assertEqual(health.get("port"), PORT)
        self.assertEqual(_server_pids(), [state.get("pid")], "one start, one process")
        for field in ("model", "started_at", "warm_at", "census"):
            self.assertEqual(state.get(field), health.get(field), f"the state file and /health disagree on {field}")
        self.assertEqual(state.get("census"), PROTOCOL_CENSUS)
        self.assertEqual(start["stderr"], "", "start printed diagnostics on a clean boot")

        # generate: without a server, exit 4 and no server started.
        missing = self.obs("guard02.generate_without_server")
        print(f"guard 2: generate without a server → exit {missing['exit']}, stdout {missing['stdout']!r}")
        self.assertEqual(missing["exit"], 4, "a request with no server must exit 4")
        self.assertEqual(missing["stdout"], "", "a failed generate wrote to stdout")
        self.assertTrue(missing["stderr"].strip(), "a failed generate said nothing on stderr")
        self.assertFalse(missing["state_file_after"], "generate started a server")
        self.assertEqual(missing["pids_after"], [], "generate left a server process behind")

        # generate: the CLI still guard 6 made is this half of the lifecycle.
        self.assertTrue(pathlib.Path(self.obs("guard06.path")).is_file(), "generate wrote no still")

        # double start: exit 0, same pid, no second process.
        pid = state.get("pid")
        second = _cli("start")
        print(f"guard 2: second start → exit {second.returncode}, pids {_server_pids()}")
        self.assertEqual(second.returncode, 0, f"a second start must exit 0: {second.stderr}")
        self.assertEqual(_state().get("pid"), pid, "a second start replaced the running server")
        self.assertEqual(_server_pids(), [pid], "a second start created a second process")

        # double start with a differing --port: reported, ignored, exit 0.
        third = _cli("start", "--port", "9999")
        print(f"guard 2: start --port 9999 → exit {third.returncode}, stderr {third.stderr.strip()!r}")
        self.assertEqual(third.returncode, 0, f"a differing --port must not be an error: {third.stderr}")
        self.assertIn("9999", third.stderr, "the ignored port was not reported")
        self.assertEqual(_server_pids(), [pid], "a differing --port started a second server")

        # stop: exit 0, port silent, state removed, process gone.
        began = time.perf_counter()
        stopped = _cli("stop", timeout=180)
        stop_wall = round(time.perf_counter() - began, 2)
        print(f"guard 2: stop → exit {stopped.returncode} in {stop_wall} s, stdout {stopped.stdout.strip()!r}")
        self.assertEqual(stopped.returncode, 0, f"stop failed: {stopped.stderr}")

        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if _health()[0] != 200 and not STATE_FILE.exists() and not _server_pids():
                break
            time.sleep(0.5)
        after_status, after_body = _health()
        self.assertNotEqual(after_status, 200, f"the port still answers after stop: {after_body}")
        self.assertFalse(STATE_FILE.exists(), "run/server.json survived stop")
        self.assertEqual(_server_pids(), [], "a server process survived stop")

        # stop again: a no-op, exit 0.
        again = _cli("stop", timeout=120)
        print(f"guard 2: stop when stopped → exit {again.returncode}, stdout {again.stdout.strip()!r}")
        self.assertEqual(again.returncode, 0, f"stop of a stopped server must exit 0: {again.stderr}")
        self.assertFalse(STATE_FILE.exists(), "a no-op stop recreated the state file")
        self.assertEqual(_server_pids(), [], "a no-op stop started a process")

        _put("guard02.stop", {"exit": stopped.returncode, "wall_s": stop_wall, "second_stop_exit": again.returncode})

    # --- 13: guard 16 owns the idle timeout, and it runs last ----------------

    def test_0950_guard16_idle_timeout(self) -> None:
        """Guard 16: a declared idle period retires the server, and never cuts a render.

        This guard runs after guard 2 has stopped the shared server, and that
        ordering is load-bearing: `run/server.lock` is one instance per card
        (guard 12), so a second server cannot start while the first holds it.
        `unittest` sorts test methods alphabetically and `0950` sorts after
        `0900`, which is why the name is what it is.

        It proves three things the law now declares: a period below the boot cost
        is refused at the door and starts nothing; a request in flight outlasts
        the period without being cut, because idle means no request in flight
        *and* none queued; and once the server does fall idle it retires on its
        own — port silent, state file removed, process gone — through the same
        path `stop` uses.
        """
        timeout = 16.0
        # The render has to outlast the declared period, or it would prove
        # nothing: 1024x576 is 589,824 px, about 28 s on this card against the
        # 16 s the guard declares.
        width, height = 1024, 576

        # 0. One instance per card (guard 12). The class fixture starts a shared
        #    server and guard 2 normally stops it before this guard runs; under
        #    `-k guard16` guard 2 is filtered out and the shared server is still
        #    up, so it goes first. This guard must not depend on the order it
        #    happens to be run in.
        if _state() is not None or _server_pids():
            cleared = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and (_state() is not None or _server_pids()):
                time.sleep(0.5)
            self.assertEqual(_server_pids(), [], f"the shared server would not stop: {cleared.stderr}")
            self.assertIsNone(_state(), "the shared server left its state file behind")

        # 1. Below the boot cost: refused at the door, and nothing is started.
        refused = _cli("start", "--idle-timeout", "5", timeout=120)
        print(f"guard 16: start --idle-timeout 5 → exit {refused.returncode}")
        _put("guard16.refused", {
            "exit": refused.returncode,
            "stderr": refused.stderr[-400:],
            "pids": _server_pids(),
            "state": _state(),
        })
        self.assertEqual(refused.returncode, 2, f"a period below the boot cost must exit 2: {refused.stderr}")
        self.assertIn("boot cost", refused.stderr, "the refusal did not name what it refused against")
        self.assertEqual(_server_pids(), [], "a refused idle timeout started a server")
        self.assertIsNone(_state(), "a refused idle timeout wrote a state file")

        # The server's log is opened in append mode and never truncated, so any
        # count taken here is cumulative across every run this machine has ever
        # done. Guard 1 baselines its two counters for exactly this reason, and
        # without the baseline the assertion below could not fail: it would pass
        # on a retirement that logged nothing, because an older one had.
        declared_before = _log_count("idle: declared")
        retiring_before = _log_count("— retiring")

        # 2. A declared period the system accepts, and a warm server. The stop is
        #    registered before the start: a failing assertion below must not leave
        #    the card taken for the rest of the matrix.
        self.addCleanup(_stop_if_running)
        started = _cli("start", "--idle-timeout", f"{timeout:g}", "--model", ZIMAGE_ID, timeout=600)
        print(f"guard 16: start --idle-timeout {timeout:g} → exit {started.returncode}; {started.stdout.strip()}")
        _put("guard16.start", {"exit": started.returncode, "stdout": started.stdout, "stderr": started.stderr})
        self.assertEqual(started.returncode, 0, f"start failed: {started.stderr}")
        self.assertIn(f"idle timeout {timeout:g} s", started.stdout, "the started server did not echo its deadline")
        status, health = _health()
        self.assertEqual(status, 200, f"/health did not answer: {health}")
        pid = health.get("pid")
        self.assertEqual(_server_pids(), [pid], "one start, one process")

        # 3. A second `start` with a different period: reported, ignored, and the
        #    running server keeps its own — the same rule `--port` follows.
        again_start = _cli("start", "--idle-timeout", "600", timeout=120)
        print(f"guard 16: second start --idle-timeout 600 → exit {again_start.returncode}, {again_start.stderr.strip()!r}")
        _put("guard16.ignored", {"exit": again_start.returncode, "stderr": again_start.stderr})
        self.assertEqual(again_start.returncode, 0, f"a differing period must not be an error: {again_start.stderr}")
        self.assertIn("idle-timeout 600 ignored", again_start.stderr, "the ignored period was not reported")
        self.assertEqual(_server_pids(), [pid], "a differing period started a second server")

        # 3. A request that outlasts the period is served whole, not cut.
        still = FILES / "g16-in-flight.png"
        if still.exists():
            still.unlink()
        began = time.perf_counter()
        code, body = _generate({
            "prompt": "a brass compass on a wooden table",
            "seed": 7,
            "width": width,
            "height": height,
            "out": str(still),
        })
        wall = round(time.perf_counter() - began, 2)
        print(
            f"guard 16: a {body.get('render_s')} s render against a {timeout:g} s period → "
            f"HTTP {code}, wall {wall} s"
        )
        _put("guard16.in_flight", {"status": code, "render_s": body.get("render_s"), "wall_s": wall, "out": body.get("out")})
        self.assertEqual(code, 200, f"the render was cut or refused: {body}")
        self.assertTrue(still.is_file(), "the render wrote no still")
        self.assertGreater(
            float(body.get("render_s") or 0), timeout,
            "the guard's render did not outlast the declared period, so it proved nothing",
        )
        self.assertEqual(_server_pids(), [pid], "the server did not survive its own render")

        # 4. It stays up for the period *after* the render, not for a moment.
        #    Counting the period from the moment the request was accepted would
        #    retire the server the instant the render finished.
        time.sleep(timeout / 2)
        self.assertTrue(STATE_FILE.exists(), "the server retired while still inside its idle period")
        self.assertEqual(_server_pids(), [pid], "the server retired while still inside its idle period")

        # 5. Then it retires by itself: port silent, state gone, process gone.
        deadline = time.monotonic() + timeout + 45
        retired_at = None
        while time.monotonic() < deadline:
            if _health()[0] != 200 and not STATE_FILE.exists() and not _server_pids():
                retired_at = round(time.perf_counter() - began, 2)
                break
            time.sleep(0.5)
        after_status, after_body = _health()
        print(f"guard 16: after {retired_at} s from the request — /health {after_status}, state {STATE_FILE.exists()}")
        _put("guard16.retired", {
            "after_s": retired_at,
            "health": after_status,
            "state_exists": STATE_FILE.exists(),
            "pids": _server_pids(),
        })
        self.assertIsNotNone(retired_at, "the server never retired on its declared idle period")
        self.assertNotEqual(after_status, 200, f"the port still answers after the idle retirement: {after_body}")
        self.assertFalse(STATE_FILE.exists(), "the state file survived the idle retirement")
        self.assertEqual(_server_pids(), [], "a server process survived the idle retirement")

        # 6. The reason is in the server's own log, not inferred from silence.
        #    Counted as a delta: the log is append-only, so an absolute count
        #    would be answering about some earlier run.
        declared = _log_count("idle: declared") - declared_before
        retired = _log_count("— retiring") - retiring_before
        print(f"guard 16: this run's server logged {declared} declaration(s) and {retired} retirement(s)")
        _put("guard16.log", {"declared": declared, "retired": retired})
        self.assertGreaterEqual(declared, 1, "the server did not log the idle period it was started with")
        self.assertGreaterEqual(retired, 1, "the server did not log why it retired")

        # 7. The ordinary paths still hold afterwards.
        again = _cli("stop", timeout=120)
        print(f"guard 16: stop after the retirement → exit {again.returncode}, {again.stdout.strip()!r}")
        _put("guard16.stop_after", {"exit": again.returncode, "stdout": again.stdout})
        self.assertEqual(again.returncode, 0, f"stopping a retired server must exit 0: {again.stderr}")
        self.assertEqual(_server_pids(), [], "a no-op stop started a process")


    # --- 14: guard 13 owns the page, and it runs last -----------------------

    def test_0960_guard13_ui_never_renders_outside_the_queue(self) -> None:
        """Guard 13: the page is a surface on the seam, never a second renderer.

        Three parts, because three parts are what can be observed without driving
        gradio's own protocol — the UI's HTTP contract is not this project's to
        pin — plus the status line, which needs neither gradio nor a card:

        1. **Structural.** `coltman_images/ui.py` is parsed and may import nothing
           from the model stack — not the encoder, not the adapter, not the render
           core, not the declared stage — and it may carry none of the entry's
           numbers, so the SD/HD switch cannot inherit 1280x720 into a different
           entry. Arithmetic is folded, so `640 * 2` is read as 1280. It is handed
           the whole `WarmServer`, so the scan also closes the boundary from the
           other side: every attribute it reads from `app` must be one of
           `submit`, `depth`, `entry` and `declaration`. The positive control is
           that it does call `submit(`: a module that reached neither the seam nor
           the model would pass the rest vacuously. The same scan over the Z-Image
           adapter must find what the blacklist forbids, which is what shows the
           scan can find anything at all.

           The reference control is asserted in the same positive direction: the
           page must build exactly one `gr.Image` that is an event **input** and
           hand `type="filepath"` to the seam (the request carries a path), the
           still must still be the one image component wired as an output, and no
           dimension may be read off the control — `size`, `width`, `height` or
           `shape` — because the box is the entry's and the aspect's to decide.
           An imaging library is on the forbidden-import list for the same reason,
           and the control's absence would make every "carries no size" assertion
           pass vacuously, which is the hole this half closes.
        2. **Unit.** `request_from_form` maps the switch: SD is the entry's own
           defaults with no permission, HD is a size above that entry's ceiling
           and inside what the stage can serve — asserted as a property, on an
           entry whose defaults do **not** sit at its ceiling. It also carries the
           reference: a file becomes a one-item `image` list, an empty control
           sends no field at all, and the box is identical either way — so the
           page's picture can never move the size the entry and the aspect set.
        3. **Behavioural.** The server is started with `--ui`, the page answers
           HTML on its own port, and two submissions fired **through the page**
           (gradio's own client, the same endpoint the button calls) serialise by
           a whole render at guard 9's 1.5x — with each one reporting its first
           status within seconds, so a page that queueed in front of the seam
           fails here rather than passing. `stop` takes the page down with the
           process.

        The status line and the three failure sentences are asserted beside the
        unit half: a request behind another one must say so — the depth is the
        only thing that tells an operator the page is waiting rather than hung —
        and a refusal, a failed render and a stopping server must each say which
        they were, not be flattened into "refused".

        It runs after guard 2 has stopped the shared server and after guard 16,
        and it pays its own boot: the shared fixture is started **without**
        `--ui`, because the matrix must stay green on a server that imports
        nothing from gradio.
        """
        # 0. One instance per card (guard 12). Under `-k guard13` the fixture's
        #    shared server is still up, so it goes first.
        if _state() is not None or _server_pids():
            cleared = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and (_state() is not None or _server_pids()):
                time.sleep(0.5)
            self.assertEqual(_server_pids(), [], f"the shared server would not stop: {cleared.stderr}")
            self.assertIsNone(_state(), "the shared server left its state file behind")

        # 1. Structural — the parsed module, not the prose around it.
        ui_source = ROOT / "coltman_images" / "ui.py"
        self.assertTrue(ui_source.is_file(), f"{ui_source} does not exist")
        tree = ast.parse(ui_source.read_text(encoding="utf-8"), filename=str(ui_source))
        imports = _ui_imports(ui_source)
        forbidden = _ui_forbidden(imports)
        calls_submit = _ui_calls(tree, "submit")
        app_attributes = _ui_app_attributes(tree)
        entry_attributes = _ui_entry_attributes(tree)

        # Not vacuous: the same scan over the file that does the coupling.
        adapter_source = ROOT / "coltman_images" / "adapters" / "zimage.py"
        adapter_forbidden = _ui_forbidden(_ui_imports(adapter_source))

        numbers = _ui_numbers(tree)
        size_numbers = _ui_matching(numbers, G13_FORBIDDEN_SIZE_CONSTANTS)
        size_strings = _ui_string_size_literals(tree, G13_FORBIDDEN_SIZE_CONSTANTS)

        # The reference control: an `Image` the page feeds a file *into*, wired as
        # an event input, and the still it hands back is the one wired as an
        # output. The input is what the request's `image` field is made of, and
        # the check is positive — a component that exists and reaches the seam —
        # because "the page carries no size" passes vacuously on a page with no
        # control at all.
        image_calls = _ui_gradio_calls(tree, "Image")
        click_inputs, click_outputs = _ui_click_wiring(tree)
        reference_controls = [
            call for call in image_calls if call["bound_to"] in click_inputs
        ]
        still_controls = [
            call for call in image_calls if call["bound_to"] in click_outputs
        ]
        reference_names = {
            str(call["bound_to"]) for call in reference_controls if call["bound_to"]
        }
        reference_size_reads = _ui_size_reads(tree, reference_names)

        # 2. Unit — the switch, on a synthetic entry and on the real declaration.
        from coltman_images import ui as ui_module

        # The stub's ceiling is deliberately **not** its defaults' area, and low
        # enough that multiplying the defaults by the factor would still sit under
        # it — so a page that multiplied instead of deriving fails the assertion
        # below on this entry. The sub-assertion in 13b keeps the fixture
        # discriminating, because an entry whose defaults sit at its ceiling would
        # let the multiplication pass. Its ladder is not the real entry's either,
        # so a page that carried 8..16 would refuse this one.
        stub = types.SimpleNamespace(
            defaults={"width": 256, "height": 256, "format": "png"},
            max_pixels=300000,
            steps=10,
            steps_min=4,
            steps_max=13,
            images_max=10,
        )
        factor = 2
        stub_prompt = "a thing that is not a lighthouse"
        stub_aspect = "1:1"
        stub_sd = ui_module.request_from_form(
            stub_prompt, 11, False, stub.steps, stub_aspect, stub, factor
        )
        stub_hd = ui_module.request_from_form(
            stub_prompt, 11, True, stub.steps, stub_aspect, stub, factor
        )
        stub_absent_seed = ui_module.request_from_form(
            stub_prompt, None, False, stub.steps, stub_aspect, stub, factor
        )
        stub_steps = ui_module.request_from_form(
            stub_prompt, 11, False, stub.steps_min, stub_aspect, stub, factor
        )
        stub_reference = "/nowhere/stub-reference.png"
        stub_with_reference = ui_module.request_from_form(
            stub_prompt, 11, False, stub.steps, stub_aspect, stub, factor, stub_reference
        )
        stub_empty_reference = ui_module.request_from_form(
            stub_prompt, 11, False, stub.steps, stub_aspect, stub, factor, None
        )

        # The real numbers, read as a declaration rather than resolved: a full
        # `load_entry` would hash 6.29 GB for a fact this guard only needs to
        # compare, and guard 4 already owns the resolution. It is Z-Image's entry
        # that this half is about — the recorded baseline and the sizes the page's
        # five shapes were fixed against.
        declaration = yaml.safe_load(ZIMAGE_ENTRY.read_text(encoding="utf-8"))
        stage = yaml.safe_load((ROOT / "model" / "upscaler.yaml").read_text(encoding="utf-8"))
        real = types.SimpleNamespace(
            defaults=dict(declaration["defaults"]),
            max_pixels=int(declaration["limits"]["max_pixels"]),
            steps=int(declaration["steps"]),
            steps_min=int(declaration["limits"]["steps"]["min"]),
            steps_max=int(declaration["limits"]["steps"]["max"]),
        )
        real_factor = int(stage["scale"])
        real_hd = ui_module.request_from_form(
            "a lighthouse at dusk", 7, True, real.steps, "16:9", real, real_factor
        )
        real_default = ui_module.request_from_form(
            "a lighthouse at dusk", 7, False, real.steps, "16:9", real, real_factor
        )
        real_low = ui_module.request_from_form(
            "a lighthouse at dusk", 7, False, real.steps_min, "16:9", real, real_factor
        )

        # The five shapes, each at both halves of the switch, computed. The
        # expectations are this entry's measured sizes: `16:9`, `1:1` and `9:16`
        # sit exactly on the ceiling and on the stage's reach, and `4:3`/`3:4` are
        # the pair that cannot — their next step up is 1152x864, 73,728 px over
        # `max_pixels`, so they stop one step lower and the algorithm must shrink
        # rather than force the area. A different entry or factor moves every one
        # of these, which is why they are computed here and not carried in ui.py.
        shapes = {
            "16:9": ((1280, 720), (2560, 1440)),
            "1:1": ((960, 960), (1920, 1920)),
            "4:3": ((1088, 816), (2176, 1632)),
            "3:4": ((816, 1088), (1632, 2176)),
            "9:16": ((720, 1280), (1440, 2560)),
        }
        computed = {
            shape: (
                ui_module.size_for(real, shape, 1),
                ui_module.size_for(real, shape, real_factor),
            )
            for shape in ui_module.ASPECT_PRESETS
        }

        # The status line carries the queue depth while it waits — the roadmap's
        # "a 46 s request behind another one must not look like a hang" — and a
        # failure is reported by what actually happened. Pure Python: a stand-in
        # app whose `submit` blocks or raises, so the generator is exercised with
        # no gradio, no GPU and no server.
        class InvalidRequest(Exception):
            """The seam's refusal: refused before any GPU work (HTTP 400)."""

        class RenderFailed(Exception):
            """The seam's failure: accepted, then the render raised (HTTP 500)."""

        class ServerError(Exception):
            """The seam's unavailability: the server is stopping and took nothing."""

        class _Waiting:
            """A stand-in for the warm server: one queued request, one response."""

            entry = stub
            declaration = None

            def __init__(self) -> None:
                self.error: BaseException | None = None

            def depth(self) -> int:
                return 1

            def submit(self, request: dict) -> dict:
                time.sleep(0.15)
                if self.error is not None:
                    raise self.error
                return {
                    "out": "/nowhere/stub.png",
                    "steps": 1,
                    "seed": request.get("seed", 0),
                    "width": request["width"],
                    "height": request["height"],
                    "model": "stub",
                    "census": {},
                    "duration_s": 0.2,
                    "render_s": 0.1,
                    "load_s": 0.05,
                    "upscale": None,
                }

        waiting = _Waiting()
        updates = list(ui_module.generate(waiting, "a thing", 11, False, waiting.entry.steps, "1:1"))
        statuses = [update for update in updates if isinstance(update, str)]
        failures: dict[str, list] = {}
        for error_class in (InvalidRequest, RenderFailed, ServerError):
            waiting.error = error_class("the seam said so")
            failures[error_class.__name__] = list(
                ui_module.generate(waiting, "a thing", 11, False, waiting.entry.steps, "1:1")
            )
        waiting.error = None

        _put(
            "guard13",
            {
                "structural": {
                    "source": str(ui_source.relative_to(ROOT)),
                    "imports": sorted(imports),
                    "forbidden": forbidden,
                    "calls_submit": calls_submit,
                    "app_attributes": sorted(app_attributes),
                    "entry_attributes": sorted(entry_attributes),
                    "numbers": numbers,
                    "size_numbers": size_numbers,
                    "size_strings": size_strings,
                    "image_components": image_calls,
                    "click_inputs": click_inputs,
                    "click_outputs": click_outputs,
                    "reference_controls": reference_controls,
                    "reference_size_reads": reference_size_reads,
                    "control_file": str(adapter_source.relative_to(ROOT)),
                    "control_forbidden": adapter_forbidden,
                },
                "unit": {
                    "stub": {
                        "sd": stub_sd,
                        "hd": stub_hd,
                        "absent_seed": stub_absent_seed,
                        "steps": stub_steps,
                        "with_reference": stub_with_reference,
                        "empty_reference": stub_empty_reference,
                        "reference": stub_reference,
                        "factor": factor,
                        "ladder": [stub.steps_min, stub.steps_max, stub.steps],
                        "images_max": stub.images_max,
                    },
                    "shapes": {
                        "presets": list(ui_module.ASPECT_PRESETS),
                        "expected": shapes,
                        "computed": {shape: [list(sd), list(hd)] for shape, (sd, hd) in computed.items()},
                        "ceiling": real.max_pixels,
                        "cap": real.max_pixels * real_factor * real_factor,
                    },
                    "real": {
                        "defaults": real.defaults,
                        "max_pixels": real.max_pixels,
                        "factor": real_factor,
                        "hd": real_hd,
                        "default_request": real_default,
                        "low_request": real_low,
                        "ladder": [real.steps_min, real.steps_max, real.steps],
                    },
                    "waiting": {
                        "statuses": statuses,
                        "result": updates[-1] if updates else None,
                        "failures": {name: values[-1] if values else None for name, values in failures.items()},
                    },
                },
            },
        )

        print(
            f"guard 13: {ui_source.name} parsed — {len(imports)} imports, "
            f"{len(forbidden)} reaching the model stack; calls submit() = {calls_submit}; "
            f"app attributes {sorted(app_attributes)}; entry attributes {sorted(entry_attributes)}; "
            f"{len(size_numbers)} entry sizes and {len(size_strings)} size strings written in code"
        )
        print(f"guard 13: every numeric literal in {ui_source.name}: {numbers}")
        print(
            f"guard 13: {len(image_calls)} gr.Image components — "
            f"{[(call['bound_to'], call['keywords'].get('type')) for call in image_calls]}; "
            f"inputs {click_inputs}; outputs {click_outputs}"
        )
        print(
            f"guard 13: the same scan finds {len(adapter_forbidden)} forbidden imports in "
            f"{adapter_source.name} — {adapter_forbidden}"
        )
        print(
            f"guard 13: SD {stub_sd} · HD {stub_hd} on a {stub.defaults['width']}x"
            f"{stub.defaults['height']} entry with a {stub.max_pixels} px ceiling and a "
            f"{stub.steps_min}..{stub.steps_max} ladder defaulting to {stub.steps}"
        )
        print(
            f"guard 13: the stub at {stub.steps_min} steps asks {stub_steps.get('steps')!r}, "
            f"at its default {stub.steps} it asks {stub_sd.get('steps')!r} (absent means the entry's)"
        )
        waiting_status = statuses[0] if statuses else "(nothing)"
        print(
            f"guard 13: the real entry gives SD {real.defaults['width']}x{real.defaults['height']} "
            f"and HD {real_hd['width']}x{real_hd['height']} above its {real.max_pixels} px ceiling; "
            f"a default-position request carries steps={real_default.get('steps')!r} and a "
            f"{real.steps_min}-step one carries steps={real_low.get('steps')!r}"
        )
        for shape, (sd, hd) in computed.items():
            expected_sd, expected_hd = shapes[shape]
            mark = "" if (sd, hd) == (expected_sd, expected_hd) else "  ← differs from the expectation"
            print(
                f"guard 13: {shape:>5} → SD {sd[0]}x{sd[1]} ({sd[0] * sd[1]} px, ceiling "
                f"{real.max_pixels}) · HD {hd[0]}x{hd[1]} ({hd[0] * hd[1]} px, cap "
                f"{real.max_pixels * real_factor * real_factor}){mark}"
            )
        print(f"guard 13: while one request waits the status says {waiting_status!r}")
        for name, values in failures.items():
            last = values[-1] if values else "(nothing)"
            print(f"guard 13: a {name} is reported as {str(last)[:70]!r}")

        with self.subTest(part="13a: the UI reaches no model"):
            self.assertEqual(
                forbidden,
                [],
                f"{ui_source.name} reaches the model stack: {forbidden}",
            )
            self.assertTrue(calls_submit, f"{ui_source.name} calls no submit(): the scan proved nothing")
            self.assertGreaterEqual(
                len(adapter_forbidden),
                3,
                f"the scan found nothing in {adapter_source.name} either, so it cannot find anything: "
                f"{adapter_forbidden}",
            )

        with self.subTest(part="13a: the UI touches only the seam"):
            self.assertEqual(
                sorted(app_attributes - G13_APP_ATTRIBUTES),
                [],
                f"{ui_source.name} reaches past the seam into {sorted(app_attributes - G13_APP_ATTRIBUTES)}; "
                f"the page may read {sorted(G13_APP_ATTRIBUTES)} and nothing else",
            )

        with self.subTest(part="13a: the UI carries no entry size, no ladder"):
            self.assertEqual(
                size_numbers,
                [],
                f"{ui_source.name} writes the entry's sizes into the page: {size_numbers}",
            )
            self.assertEqual(
                size_strings,
                [],
                f"{ui_source.name} writes the entry's sizes into a string: {size_strings}",
            )

        with self.subTest(part="13a: the reference control exists and reaches the seam"):
            # Positive direction: the page must *have* the control, wired as an
            # event input, and it must hand the seam a path. A page with no
            # control passes every "carries no size" assertion vacuously, which is
            # exactly the hole this closes.
            self.assertEqual(
                len(reference_controls),
                1,
                "the page has no single image control wired into the form as an input: "
                f"{[(call['bound_to'], call['keywords']) for call in image_calls]} — "
                f"the event's inputs are {click_inputs}",
            )
            self.assertEqual(
                reference_controls[0]["keywords"].get("type"),
                "filepath",
                "the reference control does not hand the page a path — the request carries a "
                f"path, so the component must be `type='filepath'`: {reference_controls[0]}",
            )
            self.assertEqual(
                len(still_controls),
                1,
                "the scan finds no image component among the event's outputs, so it cannot be "
                f"trusted to find the input either: {image_calls}",
            )
            self.assertEqual(
                still_controls[0]["keywords"].get("type"),
                "filepath",
                f"the still's component changed type: {still_controls[0]}",
            )
            self.assertEqual(
                reference_size_reads,
                [],
                "the page reads a dimension off the reference control: "
                f"{reference_size_reads} — the box is the entry's and the aspect's to decide",
            )

        with self.subTest(part="13a: the ladder comes from the entry"):
            missing = sorted({"steps_min", "steps_max", "steps"} - entry_attributes)
            self.assertEqual(
                missing,
                [],
                f"{ui_source.name} does not read {missing} from the entry, so its control carries "
                "the ladder instead of asking for it",
            )

        with self.subTest(part="13b: the switch maps to the entry"):
            # SD is the shape's box at factor 1, not the entry's defaults: the
            # aspect decides the shape and the ceiling decides the size, so a
            # square request on an entry defaulting to 16:9 is a square.
            self.assertEqual(
                (stub_sd["width"], stub_sd["height"]),
                ui_module.size_for(stub, "1:1", 1),
                "SD is not the largest square inside the stub's ceiling",
            )
            self.assertNotEqual(
                (stub_sd["width"], stub_sd["height"]),
                (stub.defaults["width"], stub.defaults["height"]),
                "the fixture cannot tell a computed box from the entry's defaults",
            )
            self.assertNotIn("upscale", stub_sd, "SD asked for the stage")
            self.assertIn("seed", stub_sd)
            self.assertNotIn("seed", stub_absent_seed, "an absent seed must let the server pick one")

            # The ladder. A value at the entry's default is **omitted**, so the
            # page at its initial position sends exactly the request the API
            # serves with no `steps` at all (section 4.1: absent means the
            # entry's); any other value rides along and the entry bounds it.
            self.assertNotIn(
                "steps", stub_sd, "the slider's default position wrote a steps field into the request"
            )
            self.assertNotIn(
                "steps", real_default, "the real entry's default position wrote a steps field"
            )
            self.assertEqual(
                set(real_default),
                {"prompt", "seed", "width", "height"},
                "the default-position request is not the request the API serves with no steps at all",
            )
            self.assertEqual(stub_steps.get("steps"), stub.steps_min, "a moved slider did not reach the request")
            self.assertEqual(real_low.get("steps"), real.steps_min, "a moved slider did not reach the request")

            # The reference. A file on the control rides to the request as a
            # one-item `image` list, and an empty control sends **no field at
            # all** — so the page at rest is the request the API serves with no
            # reference. The box does not move either way: the page never reads a
            # dimension off the file (section 5.5).
            self.assertEqual(
                stub_with_reference.get("image"),
                [stub_reference],
                f"a file on the control did not reach the request: {stub_with_reference}",
            )
            self.assertNotIn(
                "image",
                stub_empty_reference,
                f"an empty control wrote an image field into the request: {stub_empty_reference}",
            )
            self.assertNotIn("image", stub_sd, f"the form's request grew an image field: {stub_sd}")
            self.assertEqual(
                (stub_with_reference.get("width"), stub_with_reference.get("height")),
                (stub_sd["width"], stub_sd["height"]),
                "the reference control changed the requested box: the size is the entry's and the "
                "aspect's to decide, not the picture's",
            )

            naive = (stub.defaults["width"] * factor, stub.defaults["height"] * factor)
            self.assertLessEqual(
                naive[0] * naive[1],
                stub.max_pixels,
                "this fixture cannot tell a derivation from a multiplication: its defaults x factor "
                f"({naive[0]}x{naive[1]}) already clears its {stub.max_pixels} px ceiling",
            )

            # The property, not the multiplication: HD is above the entry's ceiling
            # and inside what the stage can serve, on an entry whose defaults do
            # *not* sit at that ceiling.
            for label, entry, factor_used, request in (
                ("stub", stub, factor, stub_hd),
                ("real", real, real_factor, real_hd),
            ):
                area = request["width"] * request["height"]
                cap = entry.max_pixels * factor_used * factor_used
                self.assertIs(request.get("upscale"), True, f"{label}: HD did not permit the stage")
                self.assertGreater(
                    area,
                    entry.max_pixels,
                    f"{label}: HD {request['width']}x{request['height']} is not above the "
                    f"{entry.max_pixels} px ceiling, so a native render would be labelled HD",
                )
                self.assertLessEqual(
                    area,
                    cap,
                    f"{label}: HD {request['width']}x{request['height']} is beyond the {cap} px the "
                    "declared stage can serve, so every HD submission would be refused",
                )
                self.assertEqual(request["width"] % 16, 0, f"{label}: HD width is not a multiple of 16")
                self.assertEqual(request["height"] % 16, 0, f"{label}: HD height is not a multiple of 16")
                self.assertGreaterEqual(request["width"], 256, f"{label}: HD width is below 256")
                self.assertGreaterEqual(request["height"], 256, f"{label}: HD height is below 256")

        with self.subTest(part="13b: the five shapes, both halves"):
            self.assertEqual(
                tuple(ui_module.ASPECT_PRESETS),
                ("16:9", "1:1", "4:3", "3:4", "9:16"),
                "the page offers a different list of shapes than the operator asked for",
            )
            for shape in ui_module.ASPECT_PRESETS:
                across, down = (int(side) for side in shape.split(":"))
                sd, hd = computed[shape]
                expected_sd, expected_hd = shapes[shape]
                self.assertEqual(
                    (sd, hd),
                    (expected_sd, expected_hd),
                    f"{shape}: the page computes {sd} at SD and {hd} at HD, not "
                    f"{expected_sd} and {expected_hd} — it shrank less or more than the ceiling allows",
                )
                for label, box, cap in (
                    ("SD", sd, real.max_pixels),
                    ("HD", hd, real.max_pixels * real_factor * real_factor),
                ):
                    self.assertEqual(box[0] % 16, 0, f"{shape} {label}: {box[0]} is not a multiple of 16")
                    self.assertEqual(box[1] % 16, 0, f"{shape} {label}: {box[1]} is not a multiple of 16")
                    self.assertGreaterEqual(box[0], 256, f"{shape} {label}: {box[0]} is below 256")
                    self.assertGreaterEqual(box[1], 256, f"{shape} {label}: {box[1]} is below 256")
                    self.assertLessEqual(
                        box[0] * box[1], cap, f"{shape} {label}: {box[0]}x{box[1]} is above {cap} px"
                    )
                    self.assertEqual(
                        box[0] * down,
                        box[1] * across,
                        f"{shape} {label}: {box[0]}x{box[1]} is not the shape asked for",
                    )
                self.assertLessEqual(
                    sd[0] * sd[1], real.max_pixels, f"{shape}: SD is above the entry's ceiling"
                )
                self.assertGreater(
                    hd[0] * hd[1],
                    real.max_pixels,
                    f"{shape}: HD {hd[0]}x{hd[1]} does not clear the ceiling, so the stage would not run "
                    "and the page would say SD",
                )
            # 16:9 at SD is the shape the entry itself renders by default, so the
            # recorded baseline's request is unchanged by this control.
            self.assertEqual(
                computed["16:9"][0],
                (int(real.defaults["width"]), int(real.defaults["height"])),
                "16:9 at SD is not the entry's own default box, so the baseline would move",
            )
            with self.assertRaises(ValueError):
                ui_module.size_for(real, "5:4", 1)

        with self.subTest(part="13c: the status line and the failures"):
            # The generator's halves, with no gradio and no card: it reports the
            # depth while the seam blocks, and it says which of the three things
            # happened instead of calling every failure a refusal.
            self.assertTrue(statuses, "generate yielded no status while the seam was busy")
            self.assertIn(
                "queue depth 1",
                statuses[0],
                f"a request behind another one shows {statuses[0]!r} — it would look like a hang",
            )
            self.assertIsInstance(updates[-1], dict, "generate did not end with the response object")
            self.assertEqual(updates[-1]["out"], "/nowhere/stub.png")

            for name, values in failures.items():
                self.assertTrue(values, f"generate yielded nothing for a {name}")
                self.assertIsInstance(values[-1], str, f"a {name} reached the page as an exception")
                self.assertIn(name, values[-1], f"the {name} sentence does not name the class: {values[-1]}")
            self.assertIn("refused", failures["InvalidRequest"][-1], "a refusal is not called a refusal")
            self.assertIn("render failed", failures["RenderFailed"][-1], "a failed render is not called one")
            self.assertIn("not accepting work", failures["ServerError"][-1], "a stopping server is not named")
            self.assertEqual(
                len({values[-1].split(" — ")[0] for values in failures.values()}),
                3,
                "two of the three failures share a sentence, so at least one of them is a lie",
            )

        # 3. Behavioural — the page mounted, and the queue still single-flight.
        page_status, page_type, page_was = _ui_page(UI_PORT)
        self.assertEqual(
            page_status,
            0,
            f"{BIND}:{UI_PORT} already answers ({page_status}) before the guard started anything — "
            "free it first, or the guard would be measuring somebody else's page",
        )

        # The stop is registered before the start: a failing assertion below must
        # not leave the page's process, and the card, taken for the rest of the matrix.
        self.addCleanup(_stop_if_running)
        started = _cli("start", "--ui", "--model", ZIMAGE_ID, timeout=600)
        print(f"guard 13: start --ui → exit {started.returncode}; {started.stdout.strip()}")
        _put("guard13.start", {"exit": started.returncode, "stdout": started.stdout, "stderr": started.stderr})
        self.assertEqual(started.returncode, 0, f"start --ui failed: {started.stderr}")
        self.assertIn(
            f"ui http://{BIND}:{UI_PORT}",
            started.stdout,
            "start did not echo the page's address on its success line",
        )
        status, health = _health()
        self.assertEqual(status, 200, f"/health did not answer: {health}")
        pid = health.get("pid")
        self.assertEqual(_server_pids(), [pid], "one start, one process")

        page_status, page_type, page = _ui_page(UI_PORT)
        _put(
            "guard13.page",
            {
                "status": page_status,
                "content_type": page_type,
                "bytes": len(page),
                "head": page[:300].decode("utf-8", "replace"),
            },
        )
        print(f"guard 13: page on {BIND}:{UI_PORT} → {page_status} {page_type}, {len(page)} bytes")
        self.assertEqual(page_status, 200, "the page did not answer on its own port")
        self.assertIn("text/html", page_type, f"the page answered {page_type!r}")
        self.assertGreater(len(page), 1024, "the page answered with an empty document")

        # Two submissions **through the page**, not through the API. The API pair
        # would stay serialised even if the page reached `app.adapter` or
        # `app._queue` behind its back, which is the failure this half exists to
        # catch; these two enter where a browser enters. They also carry two
        # different ladder positions — A at the entry's default, B at its ceiling —
        # and two different shapes — A the one the entry renders by default, B a
        # square, which is not the entry's own — so both new controls are proved
        # end to end: A omits `steps` and lands on the baseline's box, B's value and
        # shape reach the render, and the slower second render keeps the
        # serialisation signal wide.
        from gradio_client import Client

        seeds = {"A": 71, "B": 72}
        steps = {"A": real.steps, "B": real.steps_max}
        aspects = {"A": "16:9", "B": "1:1"}
        expected_boxes = {label: ui_module.size_for(real, aspects[label], 1) for label in aspects}
        barrier = threading.Barrier(2)
        results: dict[str, dict] = {}
        depths: list[int] = []
        stop_polling = threading.Event()

        def fire(label: str) -> None:
            client = Client(f"http://{BIND}:{UI_PORT}/", verbose=False, download_files=None)
            barrier.wait()
            began = time.perf_counter()
            first_status_after = None
            panel = ""
            updates = 0
            job = client.submit(
                "a brass compass on a wooden table",
                # The reference control is the second input. Z-Image's entry
                # declares no reference capability, so the page hides the control
                # and this submission carries none — the request is exactly the
                # one it sent before the control existed.
                None,
                seeds[label],
                "SD",
                steps[label],
                aspects[label],
                api_name="/generate",
            )
            for update in job:
                if updates == 0:
                    first_status_after = round(time.perf_counter() - began, 3)
                updates += 1
                if isinstance(update, (list, tuple)) and len(update) >= 3 and isinstance(update[2], str):
                    panel = update[2] or panel
            results[label] = {
                "wall_s": round(time.perf_counter() - began, 3),
                "first_status_after_s": first_status_after,
                "updates": updates,
                "panel": panel,
            }

        def poll() -> None:
            while not stop_polling.is_set():
                code, body = _health()
                if code == 200:
                    depths.append(int(body.get("queue", {}).get("depth", -1)))
                stop_polling.wait(0.5)

        poller = threading.Thread(target=poll, name="p13-depth", daemon=True)
        # Daemon, for the same reason as guard 9: a deadline that aborts the join must
        # not be held open by a worker still blocked on the page's socket.
        workers = [
            threading.Thread(target=fire, args=(label,), name=f"p13-{label}", daemon=True)
            for label in seeds
        ]
        poller.start()
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=HTTP_TIMEOUT_S + 120)
        stop_polling.set()
        poller.join(timeout=10)

        walls = {label: float(result["wall_s"]) for label, result in results.items()}
        peak = max(depths) if depths else -1
        _put(
            "guard13.behaviour",
            {
                "seeds": seeds,
                "aspects": aspects,
                "boxes": {label: list(box) for label, box in expected_boxes.items()},
                "results": results,
                "peak_queue_depth": peak,
                "depth_samples": len(depths),
                "pids": _server_pids(),
            },
        )
        print(
            f"guard 13: two submissions through the page — wall {walls['A']:.3f} / {walls['B']:.3f} s, "
            f"ratio {max(walls.values()) / min(walls.values()):.3f} (separator {SERIAL_RATIO}); "
            f"first status after {results['A']['first_status_after_s']} / "
            f"{results['B']['first_status_after_s']} s; peak queue depth {peak} over {len(depths)} samples"
        )

        self.assertEqual(sorted(results), ["A", "B"], "a concurrent page submission never returned")
        for label, result in results.items():
            expected = expected_boxes[label]
            self.assertIn(
                f"**SD** — {expected[0]}x{expected[1]}",
                result["panel"],
                f"submission {label}'s page panel does not state what was delivered: {result['panel'][:200]!r}",
            )
            self.assertIn("census —", result["panel"], f"submission {label} showed no census")
            self.assertNotIn(
                "reference —",
                result["panel"],
                f"submission {label} carries no reference and its panel claims one: "
                f"{result['panel'][:200]!r}",
            )
            self.assertIn(
                f"steps {steps[label]}",
                result["panel"],
                f"submission {label} asked for {steps[label]} steps and its panel states "
                f"{result['panel'][:220]!r} — the panel must report the count the still was rendered with",
            )
            still = re.search(r"written to `([^`]+)`", result["panel"])
            self.assertIsNotNone(still, f"submission {label}'s panel names no file: {result['panel'][:200]!r}")
            written = pathlib.Path(still.group(1))
            self.assertTrue(written.is_file(), f"the page said {written} and it is not there")
            self.assertEqual(
                _png_size(written),
                expected,
                f"{written} is not the {aspects[label]} box the entry permits "
                f"({expected[0]}x{expected[1]})",
            )
            # The page does not queue in front of the seam: both submissions were
            # being reported on within seconds of the click, not after the other
            # one's render. This is the observable the page's own queue broke.
            self.assertIsNotNone(result["first_status_after_s"], f"submission {label} showed no status")
            self.assertLessEqual(
                float(result["first_status_after_s"]),
                10.0,
                f"submission {label} waited {result['first_status_after_s']} s before its first status: "
                "the page is queueing in front of the seam",
            )
        self.assertGreaterEqual(
            max(walls.values()) / min(walls.values()),
            SERIAL_RATIO,
            f"the two page submissions did not serialise ({walls['A']:.3f} s and {walls['B']:.3f} s): "
            "a second worker would overlap them",
        )
        self.assertEqual(_server_pids(), [pid], "a second server process appeared while the page was up")

        # 4. The page shares the process's life: `stop` takes it down too.
        stopped = _cli("stop", timeout=180)
        print(f"guard 13: stop → exit {stopped.returncode}, {stopped.stdout.strip()!r}")
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if _health()[0] != 200 and _ui_page(UI_PORT)[0] != 200 and not STATE_FILE.exists() and not _server_pids():
                break
            time.sleep(0.5)
        page_after = _ui_page(UI_PORT)[0]
        _put("guard13.stop", {"exit": stopped.returncode, "page_status_after": page_after, "stdout": stopped.stdout})
        self.assertEqual(stopped.returncode, 0, f"stop failed: {stopped.stderr}")
        self.assertNotEqual(page_after, 200, "the page still answers after stop")
        self.assertFalse(STATE_FILE.exists(), "run/server.json survived stop")
        self.assertEqual(_server_pids(), [], "a server process survived stop")

    # --- 15: guard 17 owns the host declaration, and it runs last -----------

    def test_0970_guard17_the_host_may_tighten_never_widen(self) -> None:
        """Guard 17: a host may tighten the deployment's limits, never widen them.

        Three halves, and one more subTest for the other field the same
        declaration carries.

        1. **A host that widens is refused at boot**, naming the bound: a ceiling
           above the served entry's measured one, a step range reaching outside
           the entry's, and — the same family — a ceiling below the box that
           entry renders by default. None of the three may start a server, and
           each message names the offending value and what bounds it.
        2. **A host that tightens changes what a request may ask for.** The
           tightened value is refused above the cap at the door, before any
           adapter call, and the value inside it is served. The size half runs on
           a synthetic entry (neither shipped entry has room to tighten a
           ceiling: both render their default box exactly at their measured one),
           and the live half runs through the service on the step range, which
           both entries can tighten.
        3. **A tree with no `host.yaml` still serves the entry's own limits**:
           the declaration is moved aside, the promoted entry boots, and its own
           default box is served — portability is a tree without a host.
        4. **`offload` rides the same declaration**: it comes from the host module
           and not from the adapter, `true` adds `--offload-to-cpu` and `false`
           leaves it out.

        It runs after guards 2, 16 and 13 stopped their servers, and it pays two
        boots of its own because the host is read at boot and there is no flag to
        point the server at another file — that is the wiring, and the file's
        shipped bytes are restored in `finally` and asserted in `tearDownModule`.
        """
        from coltman_images import host as host_module
        from coltman_images.entry import load_entry
        from coltman_images.render import _plan
        from coltman_images.adapters.flux2klein_sd import _command

        G17_DIR.mkdir(parents=True, exist_ok=True)
        entry = load_entry(G17_KLEIN_ENTRY)
        measured_cap = entry.max_pixels
        default_width = int(entry.defaults["width"])
        default_height = int(entry.defaults["height"])
        default_area = default_width * default_height
        offload_before = _log_count("offload=on")

        # 1. A host that widens is refused, and the message names the bound.
        def refusal(document: dict, name: str):
            declared = _g17_write_declaration(document, G17_DIR / name)
            with self.assertRaises(host_module.HostError) as caught:
                host_module.effective(entry, host_module.load_host(declared))
            return str(caught.exception)

        widening = {
            "ceiling": refusal(
                _g17_host_document(
                    limits={
                        "max_pixels": measured_cap * 2,
                        "steps": {"min": entry.steps_min, "max": entry.steps_max},
                    }
                ),
                "widens-ceiling.yaml",
            ),
            "ceiling-below-defaults": refusal(
                _g17_host_document(
                    limits={
                        "max_pixels": default_area - 16 * 16,
                        "steps": {"min": entry.steps_min, "max": entry.steps_max},
                    }
                ),
                "conflicts-with-defaults.yaml",
            ),
            "steps": refusal(
                _g17_host_document(
                    limits={
                        "max_pixels": measured_cap,
                        "steps": {"min": entry.steps_min - 1, "max": entry.steps_max + 1},
                    }
                ),
                "widens-steps.yaml",
            ),
        }
        malformed = refusal(
            _g17_host_document(extra=1),
            "malformed.yaml",
        )

        # 2a. The size half, on an entry with room between its default box and
        #     its ceiling: the tightened cap is what the door refuses against.
        stub_entry = load_entry(_g17_entry())
        tight_host = host_module.load_host(
            _g17_write_declaration(
                _g17_host_document(limits={"max_pixels": G17_CAP, "steps": {"min": 3, "max": 9}}),
                G17_DIR / "tightens-cap.yaml",
            )
        )
        tight_limits = host_module.effective(stub_entry, tight_host)
        refused_size = stub_entry.accepts(
            {"prompt": "x", "width": G17_SIDE, "height": G17_SIDE}, tight_limits
        )
        served_size = stub_entry.accepts({"prompt": "x", "width": 384, "height": 384}, tight_limits)
        with self.assertRaises(ValueError) as planned:
            _plan(stub_entry, "x", G17_SIDE, G17_SIDE, False, tight_limits)
        entry_limits = host_module.effective(stub_entry, None)
        unbound_size = stub_entry.accepts(
            {"prompt": "x", "width": G17_SIDE, "height": G17_SIDE}, entry_limits
        )

        # 4. The same declaration's other field: the child's own command line.
        sample = G17_DIR / "g17-child.png"
        command_on = _command(entry, G17_PROMPT, 1024, 1024, 7, 4, sample, True)
        command_off = _command(entry, G17_PROMPT, 1024, 1024, 7, 4, sample, False)

        _put(
            "guard17",
            {
                "refusals": {**widening, "malformed": malformed},
                "entry": {
                    "id": entry.id,
                    "ceiling": measured_cap,
                    "defaults": [default_width, default_height],
                    "steps": [entry.steps_min, entry.steps_max, entry.steps],
                },
                "size_half": {
                    "entry_ceiling": stub_entry.max_pixels,
                    "entry_defaults": G17_DEFAULTS,
                    "host_cap": G17_CAP,
                    "effective": tight_limits.max_pixels,
                    "refused": refused_size,
                    "served": served_size,
                    "plan_refusal": str(planned.exception),
                    "without_host": entry_limits.max_pixels,
                    "without_host_accepted": unbound_size,
                },
                "offload": {
                    "true_has_flag": "--offload-to-cpu" in command_on,
                    "false_has_flag": "--offload-to-cpu" in command_off,
                    "tail_true": command_on[-1],
                    "tail_false": command_off[-1],
                },
            }
        )

        print(
            f"guard 17a: a ceiling of {measured_cap * 2} px refused against the entry's "
            f"{measured_cap} px measurement"
        )
        print(
            f"guard 17a: a cap of {default_area - 16 * 16} px refused against the "
            f"{default_width}x{default_height} default box ({default_area} px)"
        )
        print(
            f"guard 17a: steps {entry.steps_min - 1}..{entry.steps_max + 1} refused against the "
            f"entry's {entry.steps_min}..{entry.steps_max}"
        )
        print(f"guard 17a: a malformed declaration refused — {malformed}")
        print(
            f"guard 17b: cap {G17_CAP} on a {stub_entry.max_pixels} px entry — "
            f"{G17_SIDE}x{G17_SIDE} refused ({str(planned.exception)[:90]}…), 384x384 accepted"
        )
        print(
            "guard 17d: offload true → "
            f"{'--offload-to-cpu' in command_on}, false → {'--offload-to-cpu' in command_off}"
        )

        with self.subTest(part="17a: a host that widens is refused"):
            self.assertIn(str(measured_cap * 2), widening["ceiling"])
            self.assertIn(str(measured_cap), widening["ceiling"])
            self.assertIn("never widen", widening["ceiling"])
            self.assertIn(str(default_area - 16 * 16), widening["ceiling-below-defaults"])
            self.assertIn(str(default_area), widening["ceiling-below-defaults"])
            self.assertIn("defaults", widening["ceiling-below-defaults"])
            self.assertIn(f"{entry.steps_min - 1}..{entry.steps_max + 1}", widening["steps"])
            self.assertIn(f"{entry.steps_min}..{entry.steps_max}", widening["steps"])
            self.assertIn("never widen", widening["steps"])
            self.assertIn("unknown field", malformed)

        with self.subTest(part="17b: a host that tightens is enforced at the door"):
            self.assertEqual(tight_limits.max_pixels, G17_CAP, "the effective cap is not the host's")
            self.assertTrue(refused_size, "a size above the host's cap was accepted")
            self.assertIn(str(G17_CAP), " ".join(refused_size), "the refusal does not name the cap")
            self.assertIn("host.yaml", " ".join(refused_size), "the refusal does not name which declaration binds")
            self.assertIn(str(G17_CAP), str(planned.exception), "the plan does not refuse against the cap")
            self.assertEqual(served_size, [], "a size under the host's cap was refused")
            # The same request without a host declaration is the entry's own
            # ceiling, so the tightening is what changed the answer.
            self.assertEqual(entry_limits.max_pixels, stub_entry.max_pixels)
            self.assertEqual(unbound_size, [], "the entry's own ceiling refused its own box")

        with self.subTest(part="17d: offload is carried, not hardcoded"):
            self.assertTrue(
                "--offload-to-cpu" in command_on, "offload: true did not reach the child's command"
            )
            self.assertNotIn(
                "--offload-to-cpu", command_off, "offload: false still asked the child to offload"
            )
            self.assertEqual(
                command_on[:-1], command_off, "the two command lines differ by more than the flag"
            )

        # One instance per card (guard 12), as guards 13 and 16 do under `-k`.
        if _state() is not None or _server_pids():
            cleared = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and (_state() is not None or _server_pids()):
                time.sleep(0.5)
            self.assertEqual(_server_pids(), [], f"the shared server would not stop: {cleared.stderr}")
            self.assertIsNone(_state(), "the shared server left its state file behind")

        def _stop_server() -> None:
            stopped = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if not STATE_FILE.exists() and not _server_pids() and _health()[0] != 200:
                    return
                time.sleep(0.5)
            self.fail(f"the server would not stop: {stopped.stderr}")

        live: dict[str, object] = {}
        try:
            # 2b. The live half: the tightened range is what the door enforces.
            tightened_before = _log_count("limits tightened by host.yaml")
            _g17_write_declaration(
                _g17_host_document(
                    limits={
                        "max_pixels": measured_cap,
                        "steps": {"min": entry.steps_min + 2, "max": entry.steps_max},
                    }
                ),
                HOST_FILE,
            )
            tightened_steps = (entry.steps_min + 2, entry.steps_max)
            declared = host_module.effective(entry, host_module.load_host())
            self.assertEqual(
                (declared.steps_min, declared.steps_max),
                tightened_steps,
                "the tightened range is not the intersection the host declared",
            )

            started = _cli("start", "--model", G17_KLEIN_ID, timeout=600)
            print(f"guard 17b: start under a tightened host → exit {started.returncode}")
            self.assertEqual(started.returncode, 0, f"start under a tightened host failed: {started.stderr}")
            status, health = _health()
            self.assertEqual(status, 200, f"/health did not answer: {health}")

            refused_status, refused_body = _generate(
                {"prompt": G17_PROMPT, "steps": entry.steps_min}
            )
            served_status, served_body = _generate(
                {"prompt": G17_PROMPT, "out": str(G17_DIR / "g17-tightened.png")}
            )
            live = {
                "host": {
                    "limits": {"max_pixels": measured_cap, "steps": dict(zip(("min", "max"), tightened_steps))}
                },
                "refused": {"status": refused_status, "body": refused_body},
                "served": {"status": served_status, "body": served_body},
                "tightened_logged": _log_count("limits tightened by host.yaml") - tightened_before,
            }
            print(
                f"guard 17b: steps {entry.steps_min} → HTTP {refused_status}; "
                f"the default request → HTTP {served_status} at "
                f"{served_body.get('width')}x{served_body.get('height')} in {served_body.get('render_s')} s"
            )

            self.assertEqual(
                refused_status, 400, f"a step below the host's range was not refused: {refused_body}"
            )
            message = str(refused_body.get("error", {}).get("message", ""))
            self.assertIn(
                f"{tightened_steps[0]}..{tightened_steps[1]}",
                message,
                f"the refusal does not name the tightened range: {message}",
            )
            self.assertIn("host.yaml", message, f"the refusal does not say which declaration binds: {message}")
            self.assertEqual(
                served_status, 200, f"a request inside the tightened range failed: {served_body}"
            )
            self.assertEqual(
                (served_body.get("width"), served_body.get("height")),
                (default_width, default_height),
                "the served request is not the entry's default box",
            )
            self.assertEqual(
                served_body.get("steps"),
                entry.steps,
                "an absent step count did not land on the entry's default",
            )
            self.assertGreater(float(served_body.get("render_s", 0)), 0.0)
            self.assertGreaterEqual(
                int(live["tightened_logged"]),
                1,
                "the boot did not log the tightening it applied",
            )
            self.assertGreaterEqual(
                _log_count("offload=on") - offload_before,
                1,
                "the child ran without the host's offload flag",
            )
            _stop_server()

            # 3. A tree with no host.yaml still serves the entry's own limits.
            HOST_FILE.unlink()
            self.assertIsNone(host_module.load_host(), "the declaration survived its own removal")
            without = host_module.effective(entry, None)
            self.assertEqual(
                (without.max_pixels, without.steps_min, without.steps_max),
                (entry.max_pixels, entry.steps_min, entry.steps_max),
                "with no host declaration the entry's own limits did not apply",
            )
            portable = _cli("start", "--model", G17_KLEIN_ID, timeout=600)
            print(f"guard 17c: start with no host.yaml → exit {portable.returncode}")
            self.assertEqual(portable.returncode, 0, f"start without a host failed: {portable.stderr}")
            portable_status, portable_body = _generate(
                {"prompt": G17_PROMPT, "out": str(G17_DIR / "g17-portable.png")}
            )
            live.update(
                {
                    "without_host": {
                        "start_exit": portable.returncode,
                        "status": portable_status,
                        "body": portable_body,
                        "limits": {
                            "max_pixels": without.max_pixels,
                            "steps": [without.steps_min, without.steps_max],
                        },
                    }
                }
            )
            print(
                f"guard 17c: the promoted entry served "
                f"{portable_body.get('width')}x{portable_body.get('height')} at "
                f"{portable_body.get('steps')} steps in {portable_body.get('render_s')} s "
                "with no host declaration"
            )
            self.assertEqual(
                portable_status, 200, f"the promoted entry did not serve without a host: {portable_body}"
            )
            self.assertEqual(
                (portable_body.get("width"), portable_body.get("height")),
                (default_width, default_height),
                "the served request is not the box the entry's own defaults declare",
            )
            self.assertTrue(
                pathlib.Path(str(portable_body.get("out"))).is_file(), "the portable still was not written"
            )
            _stop_server()
        finally:
            _g17_restore_declaration()
            if _state() is not None or _server_pids():
                _stop_server()

        _put("guard17.live", live)
        self.assertEqual(
            HOST_FILE.read_bytes() if HOST_FILE.is_file() else None,
            HOST_DECLARATION,
            "guard 17 left the tree's host declaration changed",
        )


    # --- 16: guard 18 owns the catalog and the cap, and it runs last --------

    def test_0980_guard18_loras(self) -> None:
        """Guard 18: a catalog on the entry, a budget on the host, three halves.

        1. **An alias the catalog does not declare is refused, and the known
           aliases are listed.** The same rule the entry applies to a step
           range: a name this model does not have is a sentence with the names
           it does have, not a silent no-op. The request field also belongs to
           the entry — an entry with no `loras` block accepts none — a weight
           outside `(0, 1]` is refused by name, and a catalog path outside this
           entry's own folder is refused, naming the path and the folder it
           should have come from: a LoRA belongs to the model it was verified on
           (sections 3 and 6.1).
        2. **A request whose LoRAs exceed the deployment's budget is refused with
           the arithmetic.** The budget is `lora_budget_mib` — 3200 MiB here, a
           memory and not a count — and the door sums the requested LoRAs' file
           sizes, measured when the entry was resolved. A host that declares 512
           tightens it, and the refusal names the sum, the budget and the largest
           single LoRA in the catalog; a budget larger than the card the host
           declares is refused at boot, because it is memory the machine does not
           have. Refusals are the door's: the worker counts do not move.
        3. **A request that fits is served.** One LoRA at 256x256 — 311 MiB of a
           3200 MiB budget — renders, and the same request without it renders
           different bytes, which is the only proof that the selection reached the
           runtime instead of stopping at the request parser. The command line is
           asserted too: the tag the runtime reads (`<lora:NAME:WEIGHT>`) and the
           directory it resolves `NAME` against are both built from the catalog.

        It runs after guard 17 has restored `host.yaml` and stopped its servers.
        It pays its own boots because the shared fixture serves Z-Image, whose
        entry declares no catalog — exactly the per-model rule this guard states
        — and because a tightened budget is read at boot and there is no flag to
        point the server at another file.
        """
        from coltman_images import host as host_module
        from coltman_images.entry import LORAS_DIR, EntryError, load_entry
        from coltman_images.adapters.flux2klein_sd import _command

        entry = load_entry(G18_ENTRY)
        catalog = sorted(entry.loras)
        self.assertEqual(
            catalog, ["anime", "background-remove", "pixel-art"], "the entry's catalog changed"
        )
        own_folder = LORAS_DIR / entry.id
        for alias, lora in entry.loras.items():
            self.assertTrue(lora.path.is_file(), f"{alias}: {lora.path} is not a file")
            self.assertTrue(
                lora.path.resolve().is_relative_to(ROOT),
                f"{alias}: {lora.path} resolves outside the tree",
            )
            # The ownership rule, on the shipped tree: one folder per model.
            self.assertEqual(
                lora.path.resolve().parent,
                own_folder.resolve(),
                f"{alias}: {lora.path} is not in this model's own folder {own_folder}",
            )
            # The budget is spent on what the file weighs, and the number is read
            # from disk rather than declared: a LoRA replaced by a bigger one is
            # refused without anyone editing the entry.
            self.assertEqual(
                lora.size_bytes, lora.path.stat().st_size, f"{alias}: cached size is not the file's"
            )
            self.assertGreater(lora.size_bytes, 0, f"{alias}: a LoRA of zero bytes")
        largest = max(entry.loras.values(), key=lambda lora: lora.size_bytes)
        # The budget this tree actually serves under, resolved the way the server
        # resolves it: the guard prints the number the door used, not a copy.
        shipped = host_module.effective(entry, host_module.load_host())

        # 1. The alias, the field, the weight, and the folder.
        foreign_path = _g18_foreign_lora_entry()
        with self.assertRaises(EntryError) as foreign:
            load_entry(foreign_path)
        foreign_said = str(foreign.exception)
        self.assertIn(
            "another-model/pixel-art.safetensors", foreign_said, f"the refusal does not name the path: {foreign_said}"
        )
        self.assertIn(
            "model/assets/loras/g18-foreign-lora/",
            foreign_said,
            f"the refusal does not name the folder it should have come from: {foreign_said}",
        )

        unknown = entry.accepts({"prompt": "x", "lora": ["no-such-alias"]})
        unknown_said = " ".join(unknown)
        self.assertIn("no-such-alias", unknown_said, f"the refusal does not name the alias: {unknown_said}")
        for alias in catalog:
            self.assertIn(alias, unknown_said, f"the refusal does not list {alias!r}: {unknown_said}")

        no_catalog = load_entry(_g18_no_catalog_entry())
        self.assertEqual(sorted(no_catalog.loras), [], "the fixture declares a catalog")
        refused_field = no_catalog.accepts({"prompt": "x", "lora": ["pixel-art"]})
        self.assertIn("declares no LoRAs", " ".join(refused_field), f"{refused_field}")

        weight_refusals = {}
        for item in ("anime:0", "anime:1.01", "anime:not-a-number"):
            said = " ".join(entry.accepts({"prompt": "x", "lora": [item]}))
            self.assertIn("weight", said, f"{item} was not refused by name: {said}")
            weight_refusals[item] = said
        self.assertEqual(
            entry.accepts({"prompt": "x", "lora": ["anime", "pixel-art:1", "background-remove:0.25"]}),
            [],
            "the entry refused a request inside its own catalog and weight rule",
        )

        # 2. The budget: a memory, summed from the files, with the arithmetic named.
        tight_host = host_module.load_host(_g18_host("g18-host-512.yaml", 512))
        tight = host_module.effective(entry, tight_host)
        self.assertEqual(tight.lora_budget_mib, 512, "the host's budget is not the effective one")
        whole_catalog = ["anime", "background-remove", "pixel-art"]
        tightened = entry.accepts({"prompt": "x", "lora": whole_catalog}, tight)
        tightened_said = " ".join(tightened)
        needed = sum(entry.loras[alias].size_bytes for alias in whole_catalog)
        needed_mib = -(-needed // (1 << 20))
        self.assertIn(f"{needed_mib} MiB", tightened_said, f"the refusal does not name the sum: {tightened_said}")
        self.assertIn("budget is 512 MiB", tightened_said, f"the refusal does not name the budget: {tightened_said}")
        self.assertIn("host.yaml", tightened_said, f"the refusal does not say which declaration binds: {tightened_said}")
        self.assertIn(largest.alias, tightened_said, f"the refusal does not name the largest LoRA: {tightened_said}")
        self.assertIn(f"{largest.mib} MiB", tightened_said, f"the refusal does not give its size: {tightened_said}")
        self.assertEqual(
            entry.accepts({"prompt": "x", "lora": [G18_ALIAS]}, tight),
            [],
            "a single LoRA that fits the tightened budget was refused",
        )

        with self.assertRaises(host_module.HostError) as incoherent:
            host_module.effective(
                entry, host_module.load_host(_g18_host("g18-host-9000.yaml", 9000, vram_mib=7857))
            )
        self.assertIn("9000", str(incoherent.exception))
        self.assertIn("7857", str(incoherent.exception))
        self.assertIn("device memory", str(incoherent.exception))

        # 3. The command line, and then the still.
        sample = G18_DIR / "g18-child.png"
        selected = entry.resolve_loras({"lora": ["pixel-art:0.75"]})
        with_tag = _command(entry, "a knight", G18_SIDE, G18_SIDE, 7, 8, sample, True, selected)
        without_tag = _command(entry, "a knight", G18_SIDE, G18_SIDE, 7, 8, sample, True)
        tagged_prompt = with_tag[with_tag.index("-p") + 1]
        self.assertIn("<lora:", tagged_prompt, f"the child was given no tag: {tagged_prompt}")
        self.assertIn("pixel-art.safetensors:0.75>", tagged_prompt, f"{tagged_prompt}")
        self.assertIn("--lora-model-dir", with_tag, "the tags have no directory to resolve against")
        self.assertEqual(
            with_tag[with_tag.index("--lora-model-dir") + 1], str(ROOT), "the LoRA directory is not the tree"
        )
        self.assertNotIn("--lora-model-dir", without_tag, "a request with no LoRA gained the flag")
        self.assertNotIn("<lora:", without_tag[without_tag.index("-p") + 1], "a request with no LoRA gained a tag")

        # One instance per card, as guards 13, 16 and 17 do under `-k guard18`.
        if _state() is not None or _server_pids():
            cleared = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and (_state() is not None or _server_pids()):
                time.sleep(0.5)
            self.assertEqual(_server_pids(), [], f"the shared server would not stop: {cleared.stderr}")
            self.assertIsNone(_state(), "the shared server left its state file behind")

        def _stop_server() -> None:
            stopped = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if not STATE_FILE.exists() and not _server_pids() and _health()[0] != 200:
                    return
                time.sleep(0.5)
            self.fail(f"the server would not stop: {stopped.stderr}")

        live: dict[str, object] = {}
        try:
            # 1b. The alias refusal, and 3. the still, on the shipped budget.
            started = _cli("start", "--model", G18_ID, timeout=600)
            print(f"guard 18: start --model {G18_ID} → exit {started.returncode}")
            self.assertEqual(started.returncode, 0, f"start failed: {started.stderr}")
            status, health = _health()
            self.assertEqual(status, 200, f"/health did not answer: {health}")

            counters_before = (_render_count(), _render_failure_count())
            alias_status, alias_body = _generate({"prompt": "x", "lora": ["no-such-alias"]})
            counters_after = (_render_count(), _render_failure_count())
            live["unknown_alias"] = {"status": alias_status, "body": alias_body}
            live["worker_counters"] = {"before": counters_before, "after": counters_after}
            self.assertEqual(alias_status, 400, f"unknown alias: expected 400, got {alias_status} {alias_body}")
            self.assertEqual(
                alias_body.get("error", {}).get("code"), "invalid_request", f"{alias_body}"
            )
            live_alias_said = str(alias_body.get("error", {}).get("message", ""))
            self.assertIn("no-such-alias", live_alias_said)
            for alias in catalog:
                self.assertIn(alias, live_alias_said, f"the refusal does not list {alias!r}")
            self.assertEqual(
                counters_after, counters_before, "a refused LoRA request reached the worker"
            )
            print(f"guard 18: unknown alias → 400 {live_alias_said[:90]}…")

            with_lora = FILES / "g18-one-lora-256.png"
            without_lora = FILES / "g18-no-lora-256.png"
            for path in (with_lora, without_lora):
                path.unlink(missing_ok=True)
            lo_status, lo_body = _generate(
                {
                    "prompt": G18_PROMPT,
                    "seed": SEED,
                    "width": G18_SIDE,
                    "height": G18_SIDE,
                    "lora": [G18_ALIAS],
                    "out": str(with_lora),
                }
            )
            plain_status, plain_body = _generate(
                {
                    "prompt": G18_PROMPT,
                    "seed": SEED,
                    "width": G18_SIDE,
                    "height": G18_SIDE,
                    "out": str(without_lora),
                }
            )
            live["served"] = {"status": lo_status, "body": lo_body, "out": str(with_lora)}
            live["plain"] = {"status": plain_status, "body": plain_body, "out": str(without_lora)}
            self.assertEqual(lo_status, 200, f"a request inside the budget failed: {lo_body}")
            self.assertEqual(plain_status, 200, f"the comparison render failed: {plain_body}")
            self.assertTrue(with_lora.is_file(), f"{with_lora} was not written")
            self.assertEqual(_png_size(with_lora), (G18_SIDE, G18_SIDE))
            self.assertGreater(float(lo_body.get("render_s", 0.0)), 0.0, "the still reports no render_s")
            with_digest = _sha256(with_lora)
            plain_digest = _sha256(without_lora)
            live["digests"] = {"with": with_digest, "without": plain_digest}
            print(
                f"guard 18: one LoRA at {G18_SIDE}x{G18_SIDE} ({entry.loras[G18_ALIAS].mib} MiB of "
                f"{shipped.lora_budget_mib} MiB) → 200 in {lo_body.get('render_s')} s; "
                f"sha256 {with_digest[:16]}… against {plain_digest[:16]}… without it"
            )
            self.assertNotEqual(
                with_digest,
                plain_digest,
                "the same request with and without the LoRA produced the same bytes: the selection "
                "never reached the runtime",
            )
            _stop_server()

            # 2b. The tightened budget, at the door of a live server.
            HOST_FILE.write_text(
                _g18_host("g18-host-512.yaml", 512).read_text(encoding="utf-8"), encoding="utf-8"
            )
            started_tight = _cli("start", "--model", G18_ID, timeout=600)
            print(f"guard 18: start under a 512 MiB budget → exit {started_tight.returncode}")
            self.assertEqual(started_tight.returncode, 0, f"start under a budget failed: {started_tight.stderr}")
            counters_before = (_render_count(), _render_failure_count())
            budget_status, budget_body = _generate({"prompt": "x", "lora": whole_catalog})
            counters_after = (_render_count(), _render_failure_count())
            live["over_budget"] = {"status": budget_status, "body": budget_body, "host": "512 MiB"}
            live["over_budget_counters"] = {"before": counters_before, "after": counters_after}
            budget_said = str(budget_body.get("error", {}).get("message", ""))
            self.assertEqual(
                budget_status, 400, f"a request above the budget was not refused: {budget_body}"
            )
            self.assertIn(f"{needed_mib} MiB", budget_said, f"the refusal does not name the sum: {budget_said}")
            self.assertIn("budget is 512 MiB", budget_said, f"the refusal does not name the budget: {budget_said}")
            self.assertEqual(
                counters_after, counters_before, "a refused LoRA request reached the worker"
            )
            print(f"guard 18: 512 MiB budget, three LoRAs → 400 …{budget_said[:150]}…")
        finally:
            _g18_restore_host()
            if _state() is not None or _server_pids():
                _stop_server()

        self.assertEqual(
            HOST_FILE.read_bytes() if HOST_FILE.is_file() else None,
            HOST_DECLARATION,
            "guard 18 left the tree's host declaration changed",
        )
        _put(
            "guard18",
            {
                "entry": {
                    "id": entry.id,
                    "catalog": catalog,
                    "sizes_mib": {alias: lora.mib for alias, lora in entry.loras.items()},
                    "folder": own_folder.relative_to(ROOT).as_posix(),
                    "foreign_refusal": foreign_said,
                },
                "unknown_alias": unknown_said,
                "no_catalog": refused_field,
                "weights": weight_refusals,
                "budget": {
                    "needed_mib": needed_mib,
                    "tight": 512,
                    "message": tightened_said,
                    "largest": [largest.alias, largest.mib],
                },
                "incoherent": str(incoherent.exception),
                "command": {
                    "prompt_with_tag": tagged_prompt,
                    "has_dir": "--lora-model-dir" in with_tag,
                    "prompt_without_tag": without_tag[without_tag.index("-p") + 1],
                },
                "live": live,
            },
        )

    # --- 17: guard 19 owns the reference image, and it runs last -----------

    def test_0990_guard19_image_input(self) -> None:
        """Guard 19: a request may carry a reference image, and the model sees it.

        Three halves, and the third is the one that matters because the first two
        could both hold while every reference was silently dropped:

        1. **A path that is not there is refused, naming it.** The door stats the
           file before any adapter is built, so a typo is a sentence about the
           file and not a render that failed inside the child — `sd-cli` exits 1
           on a reference it cannot read, and that exit arrives long after a
           model was loaded.
        2. **A count above the entry's is refused, with both numbers.** The count
           is the model's declared capability (`image: {max: N}`), so the refusal
           quotes the request's count and the entry's, the same way the step range
           quotes its bounds. The field itself belongs to the entry: Z-Image
           declares no reference block and its refusal says so, and an entry that
           declares one behind an adapter that cannot carry it is refused at boot.
        3. **A request with one reference is served, and its still differs from
           the same prompt without it.** 256x256 at the entry's four-step floor,
           rendered twice at one seed with one reference between them: different
           bytes is the only proof the file reached the runtime instead of
           stopping at the request parser, and the response echoes the path so a
           caller can read back what conditioned its still.

        It runs after guard 18 and pays its own boot: the shared fixture serves
        Z-Image, whose entry declares no reference at all — the per-model rule
        this guard states.
        """
        from coltman_images import adapter as adapter_module
        from coltman_images.adapters.flux2klein_sd import _command
        from coltman_images.entry import EntryError, load_entry

        G19_DIR.mkdir(parents=True, exist_ok=True)
        adapter_module._REGISTRY[G19_STUB] = f"{__name__}:_G19NoImageAdapter"
        self.addCleanup(adapter_module._REGISTRY.pop, G19_STUB, None)

        entry = load_entry(G18_ENTRY)
        self.assertEqual(entry.id, G18_ID, "the promoted entry changed")
        self.assertEqual(entry.images_max, 10, "the entry's declared reference count changed")
        self.assertIn("image", entry.request_fields, "the entry does not accept the image field")

        # 1. A path that does not exist, at the door, naming it.
        absent = G19_DIR / "g19-never-rendered.png"
        absent.unlink(missing_ok=True)
        missing_refusal = " ".join(entry.accepts({"prompt": "x", "image": [str(absent)]}))
        self.assertIn(str(absent), missing_refusal, f"the refusal does not name the file: {missing_refusal}")
        self.assertIn("does not exist", missing_refusal, f"{missing_refusal}")

        # A relative path is refused the same way `out` is: the caller names the
        # file, and the system invents no transport.
        relative_refusal = " ".join(entry.accepts({"prompt": "x", "image": ["g19-relative.png"]}))
        self.assertIn("absolute", relative_refusal, f"{relative_refusal}")

        # 2. The count, with both numbers.
        reference = G19_DIR / "g19-reference-256.png"
        over = [str(reference)] * (entry.images_max + 1)
        count_refusal = " ".join(entry.accepts({"prompt": "x", "image": over}))
        self.assertIn(str(len(over)), count_refusal, f"the refusal does not name the count: {count_refusal}")
        self.assertIn(
            f"at most {entry.images_max}", count_refusal, f"the refusal does not name the cap: {count_refusal}"
        )

        # The field is the entry's: a model with no reference block says so.
        zimage = load_entry(ZIMAGE_ENTRY)
        self.assertEqual(zimage.images_max, 0, "Z-Image's entry declares references")
        zimage_refusal = " ".join(zimage.accepts({"prompt": "x", "image": [str(reference)]}))
        self.assertIn("accepts no reference image", zimage_refusal, f"{zimage_refusal}")

        # Both halves of the declaration must agree, or the system would honour
        # half of it: a capability nobody can name, or a field with no capability.
        with self.assertRaises(EntryError) as block_without_field:
            load_entry(_g19_entry("g19-block-only.yaml", image_block=True, image_field=False))
        self.assertIn("request_fields do not carry 'image'", str(block_without_field.exception))
        with self.assertRaises(EntryError) as field_without_block:
            load_entry(_g19_entry("g19-field-only.yaml", image_block=False, image_field=True))
        self.assertIn("declares no image block", str(field_without_block.exception))

        # A declaration the runtime cannot honour is refused at boot, not served
        # with the picture dropped (protocol section 6.3).
        declaring = load_entry(_g19_entry("g19-declaring.yaml", image_block=True, image_field=True))
        self.assertEqual(declaring.images_max, 2, "the synthetic entry did not declare its count")
        with self.assertRaises(adapter_module.AdapterError) as cannot_carry:
            adapter_module.load_adapter(declaring)
        boot_refusal = str(cannot_carry.exception)
        self.assertIn("reference image", boot_refusal, f"{boot_refusal}")
        self.assertIn(G19_STUB, boot_refusal, f"the refusal does not name the adapter: {boot_refusal}")

        # The command line: `-r` once per image, in the order the caller named
        # them, and none at all for a request that carries no reference.
        sample = G19_DIR / "g19-child.png"
        first = G19_DIR / "g19-first.png"
        second = G19_DIR / "g19-second.png"
        plain_command = _command(entry, "x", G19_SIDE, G19_SIDE, 7, G19_STEPS, sample, True)
        one_command = _command(
            entry, "x", G19_SIDE, G19_SIDE, 7, G19_STEPS, sample, True, (), (first,)
        )
        two_command = _command(
            entry, "x", G19_SIDE, G19_SIDE, 7, G19_STEPS, sample, True, (), (first, second)
        )
        self.assertNotIn(
            "-r", plain_command, f"a request with no reference gained -r: {plain_command}"
        )
        self.assertEqual(
            [one_command[index + 1] for index, token in enumerate(one_command) if token == "-r"],
            [str(first)],
            f"one reference did not produce exactly one -r: {one_command}",
        )
        self.assertEqual(
            [two_command[index + 1] for index, token in enumerate(two_command) if token == "-r"],
            [str(first), str(second)],
            f"two references did not keep their order: {two_command}",
        )

        # 3. Through the service. One instance per card, as guards 13, 16, 17 and
        #    18 do under `-k guard19`.
        if _state() is not None or _server_pids():
            cleared = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and (_state() is not None or _server_pids()):
                time.sleep(0.5)
            self.assertEqual(_server_pids(), [], f"the shared server would not stop: {cleared.stderr}")
            self.assertIsNone(_state(), "the shared server left its state file behind")

        def _stop_server() -> None:
            stopped = _cli("stop", timeout=180)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if not STATE_FILE.exists() and not _server_pids() and _health()[0] != 200:
                    return
                time.sleep(0.5)
            self.fail(f"the server would not stop: {stopped.stderr}")

        live: dict[str, object] = {}
        try:
            started = _cli("start", "--model", G19_ID, timeout=600)
            print(f"guard 19: start --model {G19_ID} → exit {started.returncode}")
            self.assertEqual(started.returncode, 0, f"start failed: {started.stderr}")
            status, health = _health()
            self.assertEqual(status, 200, f"/health did not answer: {health}")

            # 1b. The missing file, at a live door, with the worker untouched.
            counters_before = (_render_count(), _render_failure_count())
            missing_status, missing_body = _generate({"prompt": "x", "image": [str(absent)]})
            counters_after = (_render_count(), _render_failure_count())
            live["missing"] = {"status": missing_status, "body": missing_body}
            live["missing_counters"] = {"before": counters_before, "after": counters_after}
            self.assertEqual(missing_status, 400, f"a missing reference was not refused: {missing_body}")
            missing_said = str(missing_body.get("error", {}).get("message", ""))
            self.assertIn(str(absent), missing_said, f"the refusal does not name the file: {missing_said}")
            self.assertEqual(
                counters_after, counters_before, "a refused image request reached the worker"
            )
            print(f"guard 19: a missing reference → 400 {missing_said[:80]}…")

            # 2b. The count, at a live door.
            counters_before = (_render_count(), _render_failure_count())
            count_status, count_body = _generate({"prompt": "x", "image": over})
            counters_after = (_render_count(), _render_failure_count())
            live["count"] = {"status": count_status, "body": count_body}
            live["count_counters"] = {"before": counters_before, "after": counters_after}
            self.assertEqual(count_status, 400, f"a request above the count was served: {count_body}")
            count_said = str(count_body.get("error", {}).get("message", ""))
            self.assertIn(str(len(over)), count_said, f"{count_said}")
            self.assertIn(f"at most {entry.images_max}", count_said, f"{count_said}")
            self.assertEqual(counters_after, counters_before, "a refused image request reached the worker")
            print(f"guard 19: {len(over)} references → 400 …{count_said[:110]}…")

            # 1c. The same field through the CLI: `--image` reaches the request,
            #     and the command adds no rule of its own — the door's sentence
            #     arrives as exit 2 with nothing on stdout.
            cli = _cli("generate", "--prompt", "x", "--image", str(absent), timeout=120)
            live["cli_missing"] = {
                "exit": cli.returncode,
                "stdout": cli.stdout,
                "stderr": cli.stderr,
                "counters": [_render_count(), _render_failure_count()],
            }
            self.assertEqual(cli.returncode, 2, f"the CLI did not map the refusal: {cli.stderr}")
            self.assertIn(str(absent), cli.stderr, f"the CLI's refusal does not name the file: {cli.stderr}")
            self.assertEqual(cli.stdout, "", f"a refusal wrote to stdout: {cli.stdout!r}")
            self.assertEqual(
                live["cli_missing"]["counters"],
                list(counters_before),
                "a refused CLI image request reached the worker",
            )
            print(f"guard 19: the CLI's --image on a missing file → exit {cli.returncode}")

            # 3b. The reference still, then the same request twice: once carrying
            #     the reference and once without it. The reference is rendered by
            #     the service itself — this tree adds no downloaded image.
            reference.unlink(missing_ok=True)
            reference_status, reference_body = _generate(
                {
                    "prompt": G19_REFERENCE_PROMPT,
                    "seed": G19_SEED,
                    "width": G19_SIDE,
                    "height": G19_SIDE,
                    "steps": G19_STEPS,
                    "out": str(reference),
                }
            )
            live["reference_render"] = {"status": reference_status, "body": reference_body}
            self.assertEqual(reference_status, 200, f"the reference still failed: {reference_body}")
            self.assertTrue(reference.is_file(), f"{reference} was not written")
            self.assertEqual(_png_size(reference), (G19_SIDE, G19_SIDE))

            with_reference = G19_DIR / "g19-with-reference.png"
            without_reference = G19_DIR / "g19-without-reference.png"
            for path in (with_reference, without_reference):
                path.unlink(missing_ok=True)
            refs_before = _log_count("refs=1")
            carried_status, carried_body = _generate(
                {
                    "prompt": G19_EDIT_PROMPT,
                    "seed": G19_SEED + 1,
                    "width": G19_SIDE,
                    "height": G19_SIDE,
                    "steps": G19_STEPS,
                    "image": [str(reference)],
                    "out": str(with_reference),
                }
            )
            refs_after = _log_count("refs=1")
            plain_status, plain_body = _generate(
                {
                    "prompt": G19_EDIT_PROMPT,
                    "seed": G19_SEED + 1,
                    "width": G19_SIDE,
                    "height": G19_SIDE,
                    "steps": G19_STEPS,
                    "out": str(without_reference),
                }
            )
            live["carried"] = {"status": carried_status, "body": carried_body, "out": str(with_reference)}
            live["plain"] = {"status": plain_status, "body": plain_body, "out": str(without_reference)}
            self.assertEqual(carried_status, 200, f"a request with a reference failed: {carried_body}")
            self.assertEqual(plain_status, 200, f"the comparison render failed: {plain_body}")
            self.assertTrue(with_reference.is_file(), f"{with_reference} was not written")
            self.assertEqual(_png_size(with_reference), (G19_SIDE, G19_SIDE))
            self.assertEqual(
                carried_body.get("image"),
                [str(reference)],
                f"the response does not echo the reference it used: {carried_body.get('image')}",
            )
            self.assertEqual(
                plain_body.get("image"),
                [],
                f"a request with no reference echoed one: {plain_body.get('image')}",
            )
            self.assertGreater(float(carried_body.get("render_s", 0.0)), 0.0, "the still reports no render_s")
            self.assertGreaterEqual(
                refs_after - refs_before,
                1,
                "the child's log records no reference: the tuple never reached the command line",
            )
            carried_digest = _sha256(with_reference)
            plain_digest = _sha256(without_reference)
            live["digests"] = {"with": carried_digest, "without": plain_digest}
            print(
                f"guard 19: one reference at {G19_SIDE}x{G19_SIDE} → 200 in "
                f"{carried_body.get('render_s')} s; sha256 {carried_digest[:16]}… against "
                f"{plain_digest[:16]}… without it"
            )
            self.assertNotEqual(
                carried_digest,
                plain_digest,
                "the same request with and without a reference produced the same bytes: the file "
                "never reached the model",
            )
            _stop_server()
        finally:
            if _state() is not None or _server_pids():
                _stop_server()

        _put(
            "guard19",
            {
                "entry": {
                    "id": entry.id,
                    "images_max": entry.images_max,
                    "field": "image" in entry.request_fields,
                },
                "missing": missing_refusal,
                "relative": relative_refusal,
                "count": count_refusal,
                "zimage": zimage_refusal,
                "declaration": {
                    "block_without_field": str(block_without_field.exception),
                    "field_without_block": str(field_without_block.exception),
                },
                "boot_refusal": boot_refusal,
                "command": {
                    "no_reference": plain_command,
                    "one_reference": one_command,
                    "two_references": two_command,
                },
                "live": live,
            },
        )



# --- the fixture's raw steps -----------------------------------------------


def _preflight() -> None:
    """The suite owns the lifecycle, so nothing may already own it."""
    problems = []
    if STATE_FILE.exists():
        problems.append(f"{STATE_FILE} exists — a server may be running; run `bin/coltman-images stop` first")
    pids = _server_pids()
    if pids:
        problems.append(f"server process(es) already running: {pids} — run `bin/coltman-images stop` first")
    status, body = _health()
    if status:
        problems.append(f"{BIND}:{PORT} already answers /health ({body}) — this suite must own the lifecycle")
    if problems:
        raise RuntimeError("; ".join(problems))


def _generate_without_server() -> dict:
    completed = _cli("generate", "--prompt", "x")
    return {
        "exit": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "state_file_after": STATE_FILE.exists(),
        "pids_after": _server_pids(),
    }


def _start() -> dict:
    """Start the shared server on Z-Image, the entry this matrix measures.

    `--model` is the mechanism (protocol section 5.1), and the alias is explicit
    on purpose: the promoted default is FLUX.2 [klein], while the census, the
    ladder and the recorded baseline these guards assert are Z-Image's.
    """
    began = time.perf_counter()
    completed = _cli("start", "--model", ZIMAGE_ID, timeout=600)
    return {
        "exit": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "wall_s": round(time.perf_counter() - began, 2),
    }


def _force_clean() -> list[str]:
    """Stop whatever this run left behind. The guard already asserted the clean path."""
    notes: list[str] = []
    if STATE_FILE.exists() or _server_pids():
        completed = _cli("stop", timeout=180)
        notes.append(f"stop exit={completed.returncode}")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if not STATE_FILE.exists() and not _server_pids() and _health()[0] != 200:
            notes.append("clean")
            return notes
        time.sleep(0.5)
    notes.append(f"leftovers: state={STATE_FILE.exists()} pids={_server_pids()} port_answers={_health()[0] == 200}")
    return notes


def tearDownModule() -> None:
    """Write the run's evidence, then refuse to leave the machine changed.

    A server that outlived its guard is killed here before anything is asserted, so
    it cannot poison the next run: it holds `run/server.lock`, and every later
    `start` would exit 4 with "another instance already owns this card" for a reason
    no product caused. Killing it is not the same as forgiving it — a leaked server
    is reported below, and the run fails.
    """
    notes = _force_clean()
    leaked = _server_pids()
    if leaked:
        notes.extend(_terminate(leaked))
    _put("teardown", notes)
    path = _write_evidence()
    print(f"p6: evidence written to {path.relative_to(ROOT)}")

    leftovers = []
    if leaked:
        leftovers.append(f"{len(leaked)} server process(es) outlived their guard: {leaked}")
    if STATE_FILE.exists():
        leftovers.append("run/server.json")
    remaining = _server_pids()
    if remaining:
        leftovers.append(f"server process(es) survived termination: {remaining}")
    if _health()[0] == 200:
        leftovers.append(f"a listener on {BIND}:{PORT}")
    if leftovers:
        raise AssertionError("the suite did not leave the machine as it found it: " + ", ".join(leftovers))

    # Guard 17 rewrites `host.yaml` because the server reads that one path at
    # boot, so the declaration is part of the state this suite must not change.
    current = HOST_FILE.read_bytes() if HOST_FILE.is_file() else None
    if current != HOST_DECLARATION:
        raise AssertionError(
            "the suite rewrote host.yaml and did not restore it — the deployment's declaration "
            "is not test state"
        )

    # The refusal this file exists for: the matrix does not finish with a server on
    # the card. Asserted last, on a fresh scan, after every kill above.
    survivors = _server_pids()
    if survivors:
        raise AssertionError(
            f"the matrix finished with {len(survivors)} coltman_images.server process(es) alive: {survivors}"
        )


if __name__ == "__main__":
    unittest.main()
