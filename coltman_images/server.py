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

The server never retires on its own unless the operator declares an idle
period at `start` time (`--idle-timeout`). Absent that declaration it keeps the
process and the port until `stop`, exactly as before. When the period is
declared, the server retires through the same path `POST /shutdown` uses: the
shutdown watcher wakes on a bounded wait, finds no request in flight and none
queued for the declared period, and asks for the shutdown it would have
received. There is no second retirement path and no second thread
(protocol section 6).

`coltman_images/render.py` owns one render — the plan, the output path, the
seed, the stage and the call into the adapter — and `coltman_images/adapter.py`
owns the model.
This module does not re-derive any of those decisions: it validates at the door,
enqueues, and calls `render.render` with the warm adapter it built at boot. The
sequencing that used to be mirrored here is gone: one worker, one adapter, one
implementation.

The web UI (P9) is a second surface of the same process, not a second
implementation: `--ui` brings `coltman_images/ui.py` up on its own port and its
own thread, holding this same `WarmServer` and calling the same
`submit(request)` seam the HTTP handler calls. Gradio is imported inside that
branch and never at module scope, so a server started without the flag is exactly
the stdlib service it was before (protocol sections 5.5 and 6).
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import gc
import json
import logging
import math
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
from .entry import PROJECT_ROOT, Entry, EntryError, find_entry, load_entry
from .upscale import UpscaleError, load_declaration

logger = logging.getLogger(__name__)

BIND = "127.0.0.1"
"""The only interface this server binds (protocol section 5.2). Not a flag."""

DEFAULT_PORT = 8420

DEFAULT_UI_PORT = 7860
"""The web UI's own port, beside the API's 8420 (protocol section 6).

The two never share a socket: the API stays a stdlib `http.server` on the main
thread, and gradio brings its own server in a second thread. The UI is off by
default — `--ui` asks for it — so a server without the flag imports nothing from
gradio and behaves exactly as it did before P9.
"""

RUN_DIR = PROJECT_ROOT / "run"
STATE_FILE = RUN_DIR / "server.json"

STOP_GRACE_S = 30.0
"""How long `stop` waits for in-flight work before releasing anyway (section 6)."""

IDLE_CHECK_TICK_S = 1.0
"""How often the shutdown watcher wakes to look at the idle condition.

The watcher is the thread that owns "the server is retiring". The idle period
adds a reason for it to wake, not a thread of its own: with no declaration the
wait is unbounded and the thread sleeps until a shutdown arrives; with one it
waits a second at a time and looks at the condition on every tick.
"""

MIN_IDLE_TIMEOUT_S = 15.1
"""The shortest idle period a retired server can be declared with (section 6).

It is the measured boot cost: 15.1 s, of which 11.0 s is the discarded 512x512
warm-up. A period below it is dominated by booting — the server retires before
it has served a request since it started, and the next request pays that boot
again — so `start` refuses it at the door with exit 2, before any work.
"""

EXIT_OK = 0
EXIT_RENDER_FAILED = 1
EXIT_INVALID_REQUEST = 2
EXIT_ASSET_MISSING = 3
EXIT_SERVER_UNAVAILABLE = 4

__all__ = ["main"]


class ServerError(Exception):
    """The server cannot come up: the port could not be claimed, or it broke."""


class InvalidRequest(Exception):
    """The request was refused before any GPU work (HTTP 400, CLI exit 2)."""


class RenderFailed(Exception):
    """The server accepted the request and the render raised (HTTP 500)."""


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
        "steps",
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
        steps: int | None,
        upscale: bool,
        out: str | None,
    ) -> None:
        self.accepted_at = accepted_at
        self.prompt = prompt
        self.seed = seed
        self.width = width
        self.height = height
        self.steps = steps
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
        self._ui: Any = None
        self._shutdown_requested = threading.Event()
        self._stop_thread: threading.Thread | None = None
        self._warm_s = 0.0
        self._state_written = False

        # The declared idle period, and the two counters that decide whether the
        # server is idle (protocol section 6). `_inflight` counts the requests
        # the server has accepted and not yet finished — the queue depth alone
        # would miss the one being rendered.
        self._idle_timeout: float | None = None
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._last_activity = 0.0

    # --- boot ---------------------------------------------------------------

    def boot(self, entry_path: str | pathlib.Path | None = None) -> None:
        """Resolve, validate, load the warm parts, warm up, and write the state.

        `entry_path` is the file the alias resolved to, or the path the operator
        named at `start --entry` (the development shortcut); absent means
        `model/entry.yaml`, the promoted default. Raises `EntryError` for
        anything the entry declares badly or cannot find — the caller turns that
        into exit 3, before any GPU work.
        """
        self.started_at = _utc_now()
        began = time.perf_counter()

        entry = load_entry(entry_path)
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
            json.dumps(result["census"], sort_keys=True),
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
                        steps=job.steps,
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
                    self._finish()
            finally:
                self._queue.task_done()

    def _finish(self) -> None:
        """One accepted job is done — rendered or failed. It is no longer in flight.

        Both paths end here: a render that raised still consumed the card, so
        the request it belongs to is over.

        When this is the last one, the server *becomes* idle and the declared
        period starts counting here. Counting it from the moment the request was
        accepted would let a 45 s render eat the whole idle budget, and the
        server would retire the instant the render finished instead of after the
        idle period the operator declared.
        """
        with self._inflight_lock:
            self._inflight = max(0, self._inflight - 1)
            if self._inflight == 0:
                self._last_activity = time.monotonic()

    def _enqueue(self, job: _Job) -> None:
        """Accept a job, unless the server is already stopping.

        The lock is what makes the sentinel the last thing in the FIFO: a job
        can never be queued behind it and wait forever.

        The in-flight counter is raised *before* the job reaches the queue, so
        the worker can never finish a job this server has not counted yet — a
        decrement that arrived first would leave the counter stuck above zero
        and the idle period would never expire.
        """
        with self._queue_lock:
            if self._stopping:
                raise ServerError("the server is stopping; no further work is accepted")
            with self._inflight_lock:
                self._inflight += 1
            self._last_activity = time.monotonic()
            self._queue.put(job)

    def depth(self) -> int:
        """Requests waiting for the worker. One in flight is not waiting."""
        return self._queue.qsize()

    # --- the submission seam (roadmap B1) -----------------------------------

    def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        """One request in, one response out. **The only path to a still.**

        `POST /generate` calls this and the web UI will call this; neither may
        reach the adapter or the queue any other way, or a second caller is a
        second renderer outside the single-flight queue. That is the whole
        reason this function exists (roadmap B1): the handler used to validate,
        plan, enqueue and wait inline, which made every future caller a copy of
        that code and a second producer on one card.

        Returns the protocol section 4.2 response object. Raises:

        - `InvalidRequest` — refused before any GPU work, so the handler can
          answer 400 without asking whether a model was touched.
        - `ServerError` — the server is stopping and accepted nothing.
        - `RenderFailed` — accepted, then the render raised (500).

        There is no timeout: the queue never refuses and there is no
        per-request ceiling, so `stop` is the only abort (section 6).
        """
        entry = self.entry
        if entry is None:
            raise ServerError("no entry is loaded")

        # Everything that can refuse without touching the card refuses here,
        # before the queue, so a malformed request never reaches the worker and
        # therefore never reaches the GPU (guard 1).
        problems = entry.accepts(request)
        if problems:
            raise InvalidRequest("; ".join(problems))

        prompt = request["prompt"]
        width, height = entry.dims(request.get("width"), request.get("height"))
        try:
            # `_plan` owns the ceiling and the stage's permission: it refuses a
            # size this card cannot render, and above the native ceiling it
            # refuses a request that did not permit the synthesis. Both are
            # validation, so both land as 400 rather than mid-render.
            render_module._plan(
                entry, prompt, width, height, bool(request.get("upscale", False))
            )
        except ValueError as exc:
            raise InvalidRequest(str(exc).removeprefix("invalid request: ")) from None

        seed = render_module._seed_or_pick(request.get("seed"))
        accepted_at = time.perf_counter()

        job = _Job(
            accepted_at=accepted_at,
            prompt=prompt,
            seed=seed,
            width=width,
            height=height,
            steps=request.get("steps"),
            upscale=bool(request.get("upscale", False)),
            out=request.get("out"),
        )
        self._enqueue(job)
        job.done.wait()

        if job.error is not None:
            raise RenderFailed(f"{type(job.error).__name__}: {job.error}")
        assert job.result is not None

        # The declared order of protocol section 4.2, with `duration_s` added and
        # the load split kept last: it is the one field this server reports that
        # `render.render` also reports, and it is where the per-request swap cost
        # is visible.
        return {
            "out": job.result["out"],
            "steps": job.result["steps"],
            "seed": job.result["seed"],
            "width": job.result["width"],
            "height": job.result["height"],
            "model": job.result["model"],
            "census": job.result["census"],
            "duration_s": round(time.perf_counter() - accepted_at, 3),
            "render_s": job.result["render_s"],
            "upscale": job.result["upscale"],
            "load_s": job.result["load_s"],
        }

    # --- lifecycle ----------------------------------------------------------

    def serve(
        self,
        port: int,
        idle_timeout: float | None = None,
        ui_port: int | None = None,
    ) -> None:
        """Bind, write the state, then serve until shutdown. Blocks.

        `idle_timeout` is the operator's declared idle period, in seconds.
        `None` — the default — means the server never retires on its own.

        `ui_port` brings the web UI up beside the API in its own thread; `None`
        — the default — means no page and no gradio import at all. The API keeps
        `serve_forever` on the main thread either way.
        """
        self.port = port
        self._idle_timeout = None if idle_timeout is None else float(idle_timeout)
        try:
            httpd = _HTTPServer((BIND, port), _Handler)
        except OSError as exc:
            self._remove_state()
            raise ServerError(f"bind: {BIND}:{port}: {exc}") from exc
        httpd.app = self  # type: ignore[attr-defined]
        self._httpd = httpd

        # Protocol section 6: the state file is written before the port binds.
        self._write_state()
        # The port binds: from here the server has accepted nothing, so this is
        # where the idle period starts counting.
        self._last_activity = time.monotonic()
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
        if self._idle_timeout is not None:
            logger.info(
                "idle: declared %.1f s — the server retires on its own when nothing is in flight",
                self._idle_timeout,
            )
        if ui_port is not None:
            # The page comes up before the API starts serving, so a failure here
            # is a refusal of the whole start rather than a server that answers
            # without the surface it was asked for.
            try:
                self._start_ui(ui_port)
            except ServerError:
                self._remove_state()
                httpd.server_close()
                raise
        httpd.serve_forever(poll_interval=0.2)
        # `serve_forever` returns as soon as a shutdown was requested, which is
        # *before* the drain finishes. The watcher owns the drain and exits the
        # process; waiting for it here keeps main from returning out from under
        # an in-flight render.
        if self._shutdown_requested.is_set() and self._stop_thread is not None:
            self._stop_thread.join()
        self._release()
        self._remove_state()

    def _start_ui(self, ui_port: int) -> None:
        """Bring the page up beside the API, in its own thread, on its own port.

        The page module and gradio are imported here, and `main()` imports gradio
        once before this is reached — for the capability check, so a missing
        `--ui` dependency is exit 3 before the mutex. Both of those happen inside
        the `--ui` branch: a server started without the flag never imports gradio,
        so the API stays a stdlib `http.server` service and the flag is the only
        thing that costs (protocol section 6).

        `prevent_thread_lock=True` is what keeps the API alive: `serve_forever`
        owns the main thread, and gradio hands its uvicorn server a background
        thread and returns. Without it `launch()` would block here and the port
        this process was started for would never accept a request.

        The page holds this same `WarmServer` and calls `submit()` — not the API
        over HTTP. A second client would be a second place where a request can be
        shaped, and one producer is the rule (section 9, rule 8).

        Gradio's file cache and its telemetry are pointed by the two environment
        variables `main()` sets before importing it: the cache under `run/ui/`,
        inside the tree, and the telemetry off, because a runtime request to
        `api.gradio.app` or `huggingface.co` would break section 2.
        """
        import gradio

        from . import ui as ui_module

        try:
            page = ui_module.build(self)
            page.launch(
                server_name=BIND,
                server_port=ui_port,
                prevent_thread_lock=True,
                show_error=True,
                quiet=True,
            )
        except OSError as exc:
            # A port another process holds is the operator's mistake, not a
            # broken server: the message names the port and the start is refused.
            raise ServerError(f"ui: {BIND}:{ui_port}: {exc}") from exc
        self._ui = page
        logger.info(
            "ui: serving http://%s:%d — gradio %s, the same queue as the API",
            BIND,
            ui_port,
            gradio.__version__,
        )

    def request_shutdown(self) -> None:
        """Ask the watcher to drain, release and exit (POST /shutdown, signals)."""
        with self._queue_lock:
            self._stopping = True
        self._shutdown_requested.set()

    def _watch_shutdown(self) -> None:
        self._await_shutdown()
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

    def _await_shutdown(self) -> None:
        """Wait until the server is asked to retire, and ask when it is idle.

        With no declared idle period this is the wait it always was: one
        unbounded wait, woken by `request_shutdown`. With one declared, the wait
        is bounded and the idle condition is checked on every tick — and the
        answer it gives is the same shutdown `POST /shutdown` gives, not a
        second retirement path.
        """
        if self._idle_timeout is None:
            self._shutdown_requested.wait()
            return
        while not self._shutdown_requested.wait(timeout=IDLE_CHECK_TICK_S):
            if not self._idle_expired():
                continue
            # A stop can arrive between the wait expiring and this line. If it
            # did, the retirement is already the caller's and the log must not
            # claim the idle period asked for it.
            if self._shutdown_requested.is_set():
                return
            logger.info(
                "idle: %.1f s with no request in flight and none queued — retiring",
                self._idle_timeout,
            )
            self.request_shutdown()
            return

    def _idle_expired(self) -> bool:
        """True when the declared idle period has passed with nothing to do.

        Idle means both conditions, always: no request in flight *and* none
        queued. The queue depth alone is not enough — it counts the jobs
        waiting, not the job being rendered — so the in-flight count is what
        keeps a 46 s render from being interrupted by a timeout.
        """
        timeout = self._idle_timeout
        if timeout is None:
            return False
        with self._inflight_lock:
            inflight = self._inflight
        if inflight > 0:
            return False
        if self._queue.qsize() > 0:
            return False
        return (time.monotonic() - self._last_activity) > timeout

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
        """`POST /generate`: parse the body, call the seam, map the outcome.

        The handler owns HTTP and nothing else. What a request *means* lives in
        `WarmServer.submit()`, which is the one path to a still (roadmap B1), so
        the web UI will share it instead of restating the pipeline.
        """
        try:
            request = self._body()
        except ValueError as exc:
            self._fail(400, "invalid_request", str(exc))
            return

        try:
            response = self.app.submit(request)
        except InvalidRequest as exc:
            self._fail(400, "invalid_request", str(exc))
            return
        except (RenderFailed, ServerError) as exc:
            self._fail(500, "render_failed", str(exc))
            return

        self._respond(200, response)


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
    parser.add_argument(
        "--model",
        default=None,
        metavar="ID",
        help=(
            "the entry to serve, named by its id; resolved across model/entry.yaml and "
            "model/entries/*.yaml. Absent: model/entry.yaml, the promoted default"
        ),
    )
    parser.add_argument(
        "--entry",
        default=None,
        metavar="PATH",
        help=(
            "the model entry file to serve — a development shortcut that skips the id "
            "resolution; absent: model/entry.yaml"
        ),
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help=(
            "serve the web UI from this process, on its own port and thread, calling "
            "the same submission seam the API calls"
        ),
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=None,
        help=f"the UI's loopback port when --ui is asked for (default {DEFAULT_UI_PORT})",
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help=(
            "seconds with no request in flight, and none queued, before the server "
            f"retires on its own; absent means never; at least {MIN_IDLE_TIMEOUT_S:.1f}"
        ),
    )
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
    if args.model is not None and args.entry is not None:
        logger.error(
            "model: --model names an entry by id and --entry names a file — two ways to "
            "choose the same thing, not two choices; pass one. Nothing was loaded"
        )
        return EXIT_INVALID_REQUEST
    # The declared idle period is refused here, before the mutex is taken and
    # long before a weight is loaded: a period shorter than the boot it saves is
    # a server that spends more time starting than serving (section 6).
    if args.idle_timeout is not None and not math.isfinite(args.idle_timeout):
        logger.error(
            "idle timeout: %r is not a finite number of seconds; nothing was loaded",
            args.idle_timeout,
        )
        return EXIT_INVALID_REQUEST
    if args.idle_timeout is not None and args.idle_timeout < MIN_IDLE_TIMEOUT_S:
        logger.error(
            "idle timeout: %.1f s is below the boot cost of %.1f s — a server that "
            "idles for less than it takes to start is worse than no server; nothing "
            "was loaded",
            args.idle_timeout,
            MIN_IDLE_TIMEOUT_S,
        )
        return EXIT_INVALID_REQUEST

    # The UI is a declared capability, and a declared capability that is absent
    # is an undeclared thing — exit 3, before the mutex and long before a weight
    # is loaded. The import is here, inside this branch, so a server started
    # without `--ui` never touches gradio (protocol section 6).
    #
    # `--ui-port` without `--ui` is a usage error and not a silent no-op: a flag
    # that declares nothing must not look like it did something.
    if args.ui_port is not None and not args.ui:
        logger.error(
            "ui: --ui-port names a port for a page that was not asked for; add --ui — "
            "nothing was loaded"
        )
        return EXIT_INVALID_REQUEST
    ui_port: int | None = None
    if args.ui:
        ui_port = DEFAULT_UI_PORT if args.ui_port is None else args.ui_port
        if not 1 <= ui_port <= 65535:
            logger.error("ui: port %d is outside 1..65535 — nothing was loaded", ui_port)
            return EXIT_SERVER_UNAVAILABLE
        if ui_port == args.port:
            logger.error(
                "ui: port %d is the API's port — the two surfaces never share a socket; "
                "pass a different --ui-port — nothing was loaded",
                ui_port,
            )
            return EXIT_INVALID_REQUEST
        # Both of these are set before gradio is imported and are assigned, not
        # defaulted, so an exported variable in the operator's shell cannot move
        # them: the page's file cache stays inside `run/` and its telemetry stays
        # off (protocol section 2 — no runtime lookup may point outside this tree).
        os.environ["GRADIO_TEMP_DIR"] = str(RUN_DIR / "ui")
        os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
        try:
            import gradio  # noqa: F401 — asked for, and must be there
        except Exception as exc:  # noqa: BLE001 — reported as the missing asset it is
            logger.error(
                "ui: --ui was asked for and gradio is not importable (%s: %s) — install it "
                "into the project's own interpreter with `.venv/bin/pip install gradio`; "
                "nothing was loaded",
                type(exc).__name__,
                exc,
            )
            return EXIT_ASSET_MISSING

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
        return _serve(args, ui_port)
    finally:
        _release_instance_lock(lock)


def _serve(args: argparse.Namespace, ui_port: int | None = None) -> int:
    app = WarmServer()
    try:
        # `--model` is the mechanism: the alias resolves across the promoted entry
        # and the entries directory. `--entry` is the development shortcut that
        # names the file directly, and its absence means the promoted entry.
        entry_path = find_entry(args.model) if args.model is not None else args.entry
    except EntryError as exc:
        logger.error("%s", exc)
        return EXIT_ASSET_MISSING
    try:
        app.boot(entry_path)
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
        app.serve(port=args.port, idle_timeout=args.idle_timeout, ui_port=ui_port)
    except ServerError as exc:
        logger.error("%s", exc)
        return EXIT_SERVER_UNAVAILABLE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
