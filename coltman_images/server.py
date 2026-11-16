"""The server process: one resident process, one queue, three endpoints.

The card decides this design. The 7857 MiB it reports usable cannot hold the
transformer (6057 MiB) and the int8 text encoder (4207 MiB) at once, so the
server keeps the *process* warm and lets the two models take turns: per request
the encoder is built, used and dropped, then the transformer is built, used and
dropped, and only then does the VAE decode. Peak VRAM is the larger of the two,
never their sum. What stays loaded for the life of the process is the cheap,
CPU-resident part — the entry, the upscale declaration, the tokenizer and the
VAE — plus the imports, which cost 3.0 s of interpreter start that a resident
process pays once instead of once per still.

Keeping the transformer resident would be *slower*, not faster: measured, off
the card and back costs 2.8 s, while bringing it in from a warm page cache costs
0.9 s. So the port being bound means the assets were read once and the model
loaded end to end, not that 6.29 GB sits in VRAM (protocol section 6).

The lifecycle is fixed: resolve and validate the entry (a missing asset is exit
3 before any GPU work), validate the census against the entry's
`expected_census` (guard 4), run one warm-up generation at the entry's declared
shape (discarded, never written), write `run/server.json`, and only then bind
`127.0.0.1`. Binding last is deliberate: an answering port is proof of a warm
server.

`coltman_images/render.py` owns one render — the plan, the output path, the
seed, the stage and the call into the adapter — and `coltman_images/adapter.py`
owns the model.
This module does not re-derive any of those decisions: it validates at the door,
enqueues, and calls `render.render` with the warm adapter it built at boot. The
sequencing that used to be mirrored here is gone: one worker, one adapter, one
implementation.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import gc
import json
import logging
import os
import pathlib
import queue
import signal
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from . import render as render_module
from .adapter import AdapterError, load_adapter
from .entry import PROJECT_ROOT, Entry, EntryError, load_entry
from .upscale import UpscaleError, load_declaration

logger = logging.getLogger(__name__)

BIND = "127.0.0.1"
"""The only interface this server binds (protocol section 5.2). Not a flag."""

DEFAULT_PORT = 8420

RUN_DIR = PROJECT_ROOT / "run"
STATE_FILE = RUN_DIR / "server.json"

STOP_GRACE_S = 30.0
"""How long `stop` waits for in-flight work before releasing anyway (section 6)."""

EXIT_OK = 0
EXIT_RENDER_FAILED = 1
EXIT_INVALID_REQUEST = 2
EXIT_ASSET_MISSING = 3
EXIT_SERVER_UNAVAILABLE = 4

__all__ = ["main"]


class ServerError(Exception):
    """The server cannot come up: the port could not be claimed, or it broke."""


def _utc_now() -> str:
    """A UTC timestamp, ISO 8601 in seconds — the shape every state field uses."""
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error(code: str, message: str) -> dict[str, Any]:
    """The one error envelope (protocol section 5.3)."""
    return {"error": {"code": code, "message": message}}


class _Job:
    """One accepted generation request, waiting for the single worker."""

    __slots__ = (
        "accepted_at",
        "done",
        "error",
        "height",
        "out",
        "prompt",
        "result",
        "seed",
        "upscale",
        "width",
    )

    def __init__(
        self,
        *,
        accepted_at: float,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        upscale: bool,
        out: str | None,
    ) -> None:
        self.accepted_at = accepted_at
        self.prompt = prompt
        self.seed = seed
        self.width = width
        self.height = height
        self.upscale = upscale
        self.out = out
        self.result: dict[str, Any] | None = None
        self.error: BaseException | None = None
        self.done = threading.Event()


_SENTINEL = object()
"""Marks the end of the FIFO. Nothing is ever queued behind it — see `_enqueue`."""


class WarmServer:
    """The process: warm parts loaded once, models per request, one worker."""

    def __init__(self) -> None:
        self.entry: Entry | None = None
        self.declaration: Any = None
        self.adapter: Any = None
        self.census: dict[str, int] = {}
        self.started_at = ""
        self.warm_at = ""
        self.port = DEFAULT_PORT

        self._queue: queue.Queue[Any] = queue.Queue()
        self._queue_lock = threading.Lock()
        self._stopping = False
        self._worker: threading.Thread | None = None
        self._httpd: ThreadingHTTPServer | None = None
        self._shutdown_requested = threading.Event()
        self._stop_thread: threading.Thread | None = None
        self._warm_s = 0.0
        self._state_written = False

    # --- boot ---------------------------------------------------------------

    def boot(self) -> None:
        """Resolve, validate, load the warm parts, warm up, and write the state.

        Raises `EntryError` for anything the entry declares badly or cannot find
        — the caller turns that into exit 3, before any GPU work.
        """
        self.started_at = _utc_now()
        began = time.perf_counter()

        entry = load_entry()
        # The stage's declaration is validated here too: its weights are a
        # declared asset like any other, so a missing one is exit 3 at start
        # rather than a 500 on the first request that needs it.
        declaration = load_declaration()

        adapter = load_adapter(entry)

        self.entry = entry
        self.declaration = declaration
        self.adapter = adapter

        logger.info(
            "boot: entry %s — %d steps, guidance %s, ceiling %d px; stage %s x%d",
            entry.id,
            entry.steps,
            entry.guidance,
            entry.max_pixels,
            declaration.id,
            declaration.scale,
        )
        # The adapter loads the warm pieces and establishes the census before
        # the port binds. A name this system does not have is an undeclared
        # asset (exit 3); a census that does not match the entry fails guard 4
        # here, before any request is accepted.
        adapter.prepare()
        self.census = adapter.census()
        self._warm_up()

        self.warm_at = _utc_now()
        self._warm_s = time.perf_counter() - began
        logger.info("boot: warm in %.2f s", self._warm_s)

    def _warm_up(self) -> None:
        """One full generation at the entry's declared shape, discarded.

        Its output is never written: `write=False` stops before the save, so no
        file exists even for an instant. The census guard (4) is answered by the
        transformer this pass loads, which is also the load the page cache keeps
        warm for every request after it.
        """
        assert self.entry is not None
        entry = self.entry
        warm = entry.warmup
        width, height = int(warm["width"]), int(warm["height"])
        prompt = str(warm["prompt"])
        seed = int(warm["seed"])

        problems = entry.accepts({"prompt": prompt, "width": width, "height": height, "seed": seed})
        if problems:
            raise EntryError("warmup: the entry's own warm-up values are refused: " + "; ".join(problems))

        began = time.perf_counter()
        result = render_module.render(
            entry,
            prompt=prompt,
            seed=seed,
            width=width,
            height=height,
            adapter=self.adapter,
            write=False,
        )
        elapsed = time.perf_counter() - began
        self.census = dict(result["census"])
        logger.info(
            "warmup: %dx%d rendered in %.2f s (render_s %.2f, load_s %.2f), census %s — discarded",
            width,
            height,
            elapsed,
            result["render_s"],
            result["load_s"],
            " / ".join(str(result["census"][k]) for k in ("float8", "plain", "other", "total")),
        )

    # --- the queue ----------------------------------------------------------

    def _start_worker(self) -> None:
        self._worker = threading.Thread(
            target=self._work, name="coltman-images-render", daemon=True
        )
        self._worker.start()

    def _work(self) -> None:
        """The single worker: one job at a time, for the life of the process."""
        assert self.entry is not None
        while True:
            job = self._queue.get()
            try:
                if job is _SENTINEL:
                    self._release()
                    return
                try:
                    job.result = render_module.render(
                        self.entry,
                        prompt=job.prompt,
                        seed=job.seed,
                        width=job.width,
                        height=job.height,
                        out=job.out,
                        upscale=job.upscale,
                        adapter=self.adapter,
                    )
                    logger.info(
                        "served: %s seed=%d render_s=%.2f load_s=%.2f",
                        job.result["out"],
                        job.seed,
                        job.result["render_s"],
                        job.result["load_s"],
                    )
                except BaseException as exc:  # noqa: BLE001 — reported, never hidden
                    logger.exception("render failed: %s", exc)
                    job.error = exc
                finally:
                    job.done.set()
            finally:
                self._queue.task_done()

    def _enqueue(self, job: _Job) -> None:
        """Accept a job, unless the server is already stopping.

        The lock is what makes the sentinel the last thing in the FIFO: a job
        can never be queued behind it and wait forever.
        """
        with self._queue_lock:
            if self._stopping:
                raise ServerError("the server is stopping; no further work is accepted")
            self._queue.put(job)

    def depth(self) -> int:
        """Requests waiting for the worker. One in flight is not waiting."""
        return self._queue.qsize()

    # --- lifecycle ----------------------------------------------------------

    def serve(self, port: int) -> None:
        """Bind, write the state, then serve until shutdown. Blocks."""
        self.port = port
        try:
            httpd = _HTTPServer((BIND, port), _Handler)
        except OSError as exc:
            self._remove_state()
            raise ServerError(f"bind: {BIND}:{port}: {exc}") from exc
        httpd.app = self  # type: ignore[attr-defined]
        self._httpd = httpd

        # Protocol section 6: the state file is written before the port binds.
        self._write_state()
        self._start_worker()

        self._stop_thread = threading.Thread(
            target=self._watch_shutdown, name="coltman-images-stop", daemon=True
        )
        self._stop_thread.start()
        logger.info(
            "listening on http://%s:%d — pid %d, state %s",
            BIND,
            port,
            os.getpid(),
            STATE_FILE,
        )
        httpd.serve_forever(poll_interval=0.2)
        # `serve_forever` returns as soon as a shutdown was requested, which is
        # *before* the drain finishes. The watcher owns the drain and exits the
        # process; waiting for it here keeps main from returning out from under
        # an in-flight render.
        if self._shutdown_requested.is_set() and self._stop_thread is not None:
            self._stop_thread.join()
        self._release()
        self._remove_state()

    def request_shutdown(self) -> None:
        """Ask the watcher to drain, release and exit (POST /shutdown, signals)."""
        with self._queue_lock:
            self._stopping = True
        self._shutdown_requested.set()

    def _watch_shutdown(self) -> None:
        self._shutdown_requested.wait()
        deadline = time.monotonic() + STOP_GRACE_S
        logger.info("stop: draining in-flight work (grace %.0f s)", STOP_GRACE_S)

        if self._httpd is not None:
            self._httpd.shutdown()
        with self._queue_lock:
            self._queue.put(_SENTINEL)

        if self._worker is not None:
            self._worker.join(max(0.0, deadline - time.monotonic()))
            if self._worker.is_alive():
                logger.warning("stop: in-flight work did not drain in %.0f s — releasing anyway", STOP_GRACE_S)

        self._release()
        self._remove_state()
        logger.info("stop: card released, state file removed, exiting")
        logging.shutdown()
        os._exit(EXIT_OK)

    def _release(self) -> None:
        """Give the card back: nothing of this process stays resident."""
        if self.adapter is not None:
            try:
                self.adapter.close()
            except Exception as exc:  # noqa: BLE001 — a broken context must not block exit
                logger.warning("release: the adapter did not close cleanly: %s", exc)
        self.adapter = None
        gc.collect()

    def _write_state(self) -> None:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "pid": os.getpid(),
            "port": self.port,
            "model": self.entry.id if self.entry is not None else "",
            "started_at": self.started_at,
            "warm_at": self.warm_at,
            "census": dict(self.census),
        }
        # Written beside the target and renamed: a reader never sees half a file.
        staging = STATE_FILE.with_suffix(".json.tmp")
        staging.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        staging.replace(STATE_FILE)
        self._state_written = True
        logger.info("state: %s", json.dumps(state))

    def _remove_state(self) -> None:
        try:
            STATE_FILE.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:  # noqa: BLE001 — reported, not raised from a path
            logger.warning("state: could not remove %s: %s", STATE_FILE, exc)
            return
        if self._state_written:
            logger.info("state: removed %s", STATE_FILE)

    # --- the two readouts ---------------------------------------------------

    def health(self) -> dict[str, Any]:
        """The `/health` body. `status` is always warm: the port is bound last."""
        return {
            "status": "warm",
            "model": self.entry.id if self.entry is not None else "",
            "census": dict(self.census),
            "pid": os.getpid(),
            "port": self.port,
            "started_at": self.started_at,
            "warm_at": self.warm_at,
            "queue": {"depth": self.depth()},
        }


class _HTTPServer(ThreadingHTTPServer):
    """Loopback, threaded, no reverse DNS.

    `ThreadingHTTPServer` runs one thread per connection so two clients can be
    accepted at once; the GPU still has exactly one worker. `server_bind` is
    overridden to skip `socket.getfqdn`, which would put a DNS lookup on the
    boot path of a service that only ever answers on 127.0.0.1.
    """

    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


class _Handler(BaseHTTPRequestHandler):
    """Three endpoints, one error envelope, and nothing else on the wire."""

    server_version = "coltman-images"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def app(self) -> WarmServer:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("http: " + fmt, *args)

    def _respond(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # The client gave up while the render ran. The render is not cut —
            # there is no per-request ceiling — so only the reply is lost.
            logger.info("http: the client closed the connection before the reply")

    def _fail(self, status: int, code: str, message: str) -> None:
        self._respond(status, _error(code, message))

    def do_GET(self) -> None:  # noqa: N802 — the base class names it
        path = urlsplit(self.path).path
        if path != "/health":
            self._fail(404, "not_found", f"no GET {path}; this server has /health, /generate and /shutdown")
            return
        self._respond(200, self.app.health())

    def do_POST(self) -> None:  # noqa: N802 — the base class names it
        path = urlsplit(self.path).path
        if path == "/shutdown":
            self._shutdown()
            return
        if path != "/generate":
            self._fail(404, "not_found", f"no POST {path}; this server has /health, /generate and /shutdown")
            return
        self._generate()

    # --- endpoints ----------------------------------------------------------

    def _shutdown(self) -> None:
        self._drain_body()
        # The body goes out before the drain starts: the process is about to
        # exit and the client has to see a 200 it can trust.
        self._respond(200, {"status": "stopping"})
        self.app.request_shutdown()

    def _drain_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(length)

    def _body(self) -> dict[str, Any]:
        """Read, parse and shape-check the body. Raises ValueError with the reason."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError as exc:
            raise ValueError("body: Content-Length is not a number") from exc
        if length <= 0:
            raise ValueError("body: expected a JSON object, got an empty body")
        raw = self.rfile.read(length)
        try:
            request = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"body: not valid JSON: {exc}") from exc
        if not isinstance(request, dict):
            raise ValueError(f"body: expected a JSON object, got {type(request).__name__}")
        return request

    def _generate(self) -> None:
        app = self.app
        entry = app.entry
        assert entry is not None

        # Everything that can refuse without touching the card is refused here,
        # before the queue: a malformed request never reaches the worker and
        # therefore never reaches the GPU (guard 1).
        try:
            request = self._body()
        except ValueError as exc:
            self._fail(400, "invalid_request", str(exc))
            return

        problems = entry.accepts(request)
        if problems:
            self._fail(400, "invalid_request", "; ".join(problems))
            return

        prompt = request["prompt"]
        width, height = entry.dims(request.get("width"), request.get("height"))
        try:
            # `_plan` owns the ceiling and the stage's permission: it refuses a
            # size this card cannot render, and above the native ceiling it
            # refuses a request that did not permit the synthesis. Both are
            # validation, so both land here as 400 rather than mid-render.
            render_module._plan(
                entry, prompt, width, height, bool(request.get("upscale", False))
            )
        except ValueError as exc:
            self._fail(400, "invalid_request", str(exc).removeprefix("invalid request: "))
            return

        seed = render_module._seed_or_pick(request.get("seed"))
        accepted_at = time.perf_counter()

        job = _Job(
            accepted_at=accepted_at,
            prompt=prompt,
            seed=seed,
            width=width,
            height=height,
            upscale=bool(request.get("upscale", False)),
            out=request.get("out"),
        )
        try:
            app._enqueue(job)
        except ServerError as exc:
            self._fail(500, "render_failed", str(exc))
            return

        # No timeout: the queue never refuses and there is no per-request
        # ceiling. `stop` is the only abort (protocol section 6).
        job.done.wait()

        if job.error is not None:
            self._fail(500, "render_failed", f"{type(job.error).__name__}: {job.error}")
            return
        assert job.result is not None
        # The declared order of protocol section 4.2, with `duration_s` added and
        # the load split kept last: it is the one field this server reports that
        # `render.render` also reports, and it is where the per-request swap cost
        # is visible.
        self._respond(
            200,
            {
                "out": job.result["out"],
                "seed": job.result["seed"],
                "width": job.result["width"],
                "height": job.result["height"],
                "model": job.result["model"],
                "census": job.result["census"],
                "duration_s": round(time.perf_counter() - accepted_at, 3),
                "render_s": job.result["render_s"],
                "upscale": job.result["upscale"],
                "load_s": job.result["load_s"],
            },
        )


LOCK_FILE = RUN_DIR / "server.lock"
"""The instance mutex.

Not a PID file: a PID file lies the moment its process dies. This one is held
with `flock` for the life of the process, and the kernel drops it on exit —
including `kill -9` — so a stale lock is impossible by construction. One card,
one instance, whatever port or state file says.
"""


def _other_server_pids() -> list[int]:
    """Every live process that is really this server, and is not this one.

    Matching the string anywhere on a command line is not enough: a shell whose
    argument happens to mention the module — the one that ran this very check,
    for instance — would match. The test is that the process is a Python
    interpreter and the module is one of its own argument tokens.
    """
    mine = os.getpid()
    found: list[int] = []
    try:
        entries = list(pathlib.Path("/proc").iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == mine:
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
        found.append(pid)
    return found


def _take_instance_lock() -> Any | None:
    """Take the card, or return None when somebody else already has it."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def _release_instance_lock(handle: Any) -> None:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        handle.close()
    except OSError:
        pass


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="coltman-images server",
        description="The coltman-images server process. Normally launched by `coltman-images start`.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not 1 <= args.port <= 65535:
        logger.error("port: %d is outside 1..65535", args.port)
        return EXIT_SERVER_UNAVAILABLE

    # The mutex comes before any model work. The boot order is load, warm up,
    # then bind, so a second process would exhaust the card *before* the port
    # could refuse it — the bind is far too late to be the guard.
    lock = _take_instance_lock()
    if lock is None:
        others = _other_server_pids()
        holder = f" (pid {others[0]})" if others else ""
        logger.error(
            "instance: another server already owns this card%s — one instance serves "
            "this project; run `coltman-images stop` first",
            holder,
        )
        return EXIT_SERVER_UNAVAILABLE

    try:
        others = _other_server_pids()
        if others:
            logger.error(
                "instance: pid %s is already running as this server — refusing a second",
                others[0],
            )
            return EXIT_SERVER_UNAVAILABLE
        return _serve(args)
    finally:
        _release_instance_lock(lock)


def _serve(args: argparse.Namespace) -> int:
    app = WarmServer()
    try:
        app.boot()
    except (AdapterError, EntryError, UpscaleError) as exc:
        logger.error("%s", exc)
        return EXIT_ASSET_MISSING
    except Exception:
        logger.exception("boot failed")
        return EXIT_RENDER_FAILED

    def _signal(signum: int, _frame: Any) -> None:
        logger.info("signal: %s — stopping", signal.Signals(signum).name)
        app.request_shutdown()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _signal)

    try:
        app.serve(port=args.port)
    except ServerError as exc:
        logger.error("%s", exc)
        return EXIT_SERVER_UNAVAILABLE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
