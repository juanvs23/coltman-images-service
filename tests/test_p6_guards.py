"""P6 — the eleven guards of protocol section 10, as an executable test matrix.

Runs under the production interpreter and the declared command:

    .venv/bin/python -m unittest discover -s tests -v

Two classes, because the matrix has two kinds of guard.

`ContractCase` needs no service: it reads the tree (guard 8), asks a subprocess
what the core imports (guard 11), and calls the census guard directly (the second
half of guard 4). It costs seconds.

`ServiceCase` needs the live service, so it owns its lifecycle: one server, started
once in `setUpClass` and stopped by the last test, which is guard 2's own
assertion. Every render it makes is listed here with the guard that owns it:

    renders                              guard
    4 x 1280x720 POST, same prompt/seed  guard 3 (owns); guard 5 borrows the bytes
    1 x CLI, no --out, same prompt/seed  guard 6 (owns); guard 7 borrows the bytes
    2 x 1280x720 concurrent POSTs        guard 9 (owns)
                                         one of them carries `upscale: true` and
                                         guard 10 borrows `upscale: null` from it
    1 x 2560x1440 POST with upscale      guard 10 (owns)

That is eight stills. Guard 3 costs four by protocol; guard 9 costs two because
concurrency cannot be borrowed; guard 10 costs one base render; the CLI still
doubles as guard 7's second half. Nothing renders twice for the same guard and
nothing here is a proxy for a render it did not make.

Ordering is explicit, not incidental: methods are numbered because unittest runs
them alphabetically, and guard 3 has to see the first render after `start`.
"""

from __future__ import annotations

import ast
import datetime
import filecmp
import hashlib
import json
import pathlib
import statistics
import struct
import subprocess
import sys
import threading
import time
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
    """Pids whose argv is `python … -m coltman_images.server …`, matched on NULs."""
    pids: list[int] = []
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if b"\x00-m\x00coltman_images.server\x00" in argv:
            pids.append(int(entry.name))
    return sorted(pids)


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
    """Shared access to the recorded observations, and per-test timing."""

    def setUp(self) -> None:
        self._t0 = time.perf_counter()

    def tearDown(self) -> None:
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
    documents = [ROOT / "model" / "entry.yaml", ROOT / "model" / "upscaler.yaml", ROOT / "model" / "z_image.json"]
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


class ContractCase(GuardCase):
    """Guards 4b, 8 and 11 — the ones a service would only slow down."""

    def test_guard04b_assert_census_refuses_a_model_with_no_float8_weights(self) -> None:
        """Guard 4, second half: `assert_census` refuses float8 == 0. No GPU needed."""
        from coltman_images.entry import load_entry
        from coltman_images.loader import CensusError, assert_census

        entry = load_entry()
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
        """Guard 8: refusal of any import or absolute path leaving the project's tree."""
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

        _put(
            "guard08",
            {
                "sources_read": len(sources),
                "documents_read": [str(path.relative_to(ROOT)) for path in documents],
                "imports": imports_report,
                "paths_inside": paths_inside,
                "paths_kernel": paths_kernel,
                "paths_outside": paths_outside,
            },
        )
        print(
            f"guard 8: {len(sources)} python sources, {len(documents)} declarations, "
            f"{len(imports)} imported modules; {len(paths_inside)} in-tree paths, "
            f"{len(paths_kernel)} kernel, {len(paths_outside)} outside"
        )
        for finding in paths_kernel:
            print(f"guard 8: exempted kernel interface — {finding}")

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


# ===========================================================================
# ServiceCase — the guards that need the live service
# ===========================================================================


class ServiceCase(GuardCase):
    """One server for the whole class; guard 2's own test stops it at the end."""

    @classmethod
    def setUpClass(cls) -> None:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        FILES.mkdir(parents=True, exist_ok=True)
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
        workers = [threading.Thread(target=fire, args=(label,), name=f"p6-{label}") for label in requests]
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

    # --- 7: guard 1, on a quiet queue -------------------------------------

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

    # --- 8: guard 4, the measured half ------------------------------------

    def test_0800_guard04_census_measured(self) -> None:
        """Guard 4: the measured census equals the entry's, in /health and in every response."""
        from coltman_images.entry import load_entry

        status, health = self.obs("guard02.health")
        self.assertEqual(status, 200, f"/health did not answer: {health}")

        entry = load_entry()
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

    # --- 9: guard 2, last, because it stops the server --------------------

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
    began = time.perf_counter()
    completed = _cli("start", timeout=600)
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
    """Write the run's evidence, then refuse to leave the machine changed."""
    notes = _force_clean()
    _put("teardown", notes)
    path = _write_evidence()
    print(f"p6: evidence written to {path.relative_to(ROOT)}")

    leftovers = []
    if STATE_FILE.exists():
        leftovers.append("run/server.json")
    remaining = _server_pids()
    if remaining:
        leftovers.append(f"server process(es) {remaining}")
    if _health()[0] == 200:
        leftovers.append(f"a listener on {BIND}:{PORT}")
    if leftovers:
        raise AssertionError("the suite did not leave the machine as it found it: " + ", ".join(leftovers))


if __name__ == "__main__":
    unittest.main()
