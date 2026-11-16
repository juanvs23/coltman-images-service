# Design contract — P9, the web UI

The decisions the roadmap's eight steps do not make. Steps say *what*; this says
*how*, so a writer does not have to invent the seams.

B1 and B2 are cleared: `WarmServer.submit(request) -> dict` is the only path to a
still, and gradio 6.32.0 is installed on top of the same pins.

## 1. Where the UI runs

**In the server process, on its own port, in its own thread.** The API stays
`http.server` on 8420; gradio brings its own server on 7860. The two never share
a socket.

`WarmServer.serve()` owns the API's `serve_forever` in the main thread. Gradio
must not take that thread, so it is launched with
`prevent_thread_lock=True`, which hands uvicorn a background thread and returns.

The UI holds a reference to the same `WarmServer` and calls `submit()`. Not a
client of the API over HTTP: a second client would be a second place where a
request can be shaped, and the whole point of B1 is that there is one.

## 2. The shape of `coltman_images/ui.py`

Four things, in this order, and nothing else:

1. **`request_from_form(prompt, seed, hd) -> dict`** — pure, no I/O. Builds the
   protocol section 4.1 request. `hd` True means `upscale: true` and a size above
   the entry's ceiling; False means the entry's defaults and no `upscale`. It
   takes the entry (or its ceiling) as an argument rather than reading a
   constant, because `limits.max_pixels` is per-entry.
2. **`render(app, request) -> dict`** — one line: `return app.submit(request)`.
   This is the UI's only route to a still, and its existence is what guard 13
   asserts structurally.
3. **`generate(app, prompt, seed, hd)`** — a **generator**. `submit()` blocks for
   ~46 s and the roadmap requires the queue depth to show while it waits, so the
   work runs in a worker thread and the generator yields a status string every
   half second until the result is ready, then yields it. A request behind
   another one must not look like a hang.
4. **`build(app) -> gradio.Blocks`** — prompt, seed, an SD/HD switch, the status
   line, the still. Presentation only: no validation logic, no request shaping,
   no knowledge of a model.

**The module imports gradio and nothing model-bearing.** No `diffusers`, no
`transformers`, no `safetensors`, no `coltman_images.loader`, `fp8`, `adapter`,
`adapters.*` or `render`. A UI is allowed to be plain; it is not allowed to be
load-bearing.

## 3. The honest copy (roadmap step 4, plus the two constraints)

The status line and the result panel state, from the response and never from a
constant:

- **SD or HD** — `upscale: null` is SD, an `upscale` object is HD.
- **The base it started from** — `upscale.from`, when the stage ran.
- **The census, generically** — key and value exactly as the response declares
  them. Never `float8`/`plain`/`other`/`total` written in: section 6.1 makes the
  adapter the owner of what a key means, and the next model has no FP8 at all.
- **`render_s`, `load_s` and `duration_s` kept separate** — the last one is the
  only place queue wait and load are visible.
- **The queue depth while it waits**, from `app.depth()`.

## 4. The flag

`start --ui [--ui-port 7860]` — a flag on `start`, never a fourth verb. It
travels to the server process as `--ui` / `--ui-port N`, exactly as
`--idle-timeout` does.

`start` echoes the UI address on its success line when it asked for one, so the
operator sees where to point a browser.

**Idempotency:** a differing `--ui-port` on an already-running server is reported
and ignored, like `--port` and `--idle-timeout`.

**If gradio is not importable** when `--ui` is asked: exit 3, naming what is
missing and how to install it, before any weight is loaded. The flag declares a
capability; if the capability is absent, that is a missing declared thing and 3
is the code the law already gives it. Do not import gradio at module scope in
`server.py` — import it inside the branch, so a server without `--ui` never pays
for it and never needs it.

## 5. Guard 13, and what it can honestly prove

Guard 13 is reserved for this phase. It proves the boundary in three parts,
because the three parts are what can be observed without driving gradio's own
protocol:

1. **Structural — the UI cannot render.** Parse `coltman_images/ui.py` with `ast`
   and refuse any import of `diffusers`, `transformers`, `safetensors`,
   `coltman_images.loader`, `coltman_images.fp8`, `coltman_images.adapter`,
   `coltman_images.adapters.*` or `coltman_images.render`; and assert, as a
   positive control, that the module calls `submit(` — a module that reaches
   neither the seam nor the model stack would pass the first half vacuously.
2. **Behavioural — the queue is still single-flight with the UI mounted.** Start
   the server with `--ui`, POST two concurrent `/generate` requests, and require
   the serialisation ratio the matrix already uses (≥1.5×, guard 9's threshold).
   The UI shares that queue; if the UI had a producer of its own, this is where
   it would show. The UI's own HTTP protocol is not driven — gradio's client
   contract is not this project's to pin.
3. **Unit — the request builder maps the switch correctly.** `hd` True yields
   `upscale: true` and a size above the ceiling; False yields the entry's
   defaults and no `upscale`. No GPU, no server.

Guard 13 is written in `tests/test_p6_guards.py` like its siblings, and the count
in protocol section 10 moves: seventeen guards declared, guard 13 no longer
reserved, sixteen written, seventeen test methods.

## 6. The law, in this same work unit

- **§1** gains the UI as a surface, beside the CLI and the API.
- **§3** the layout table gains `coltman_images/ui.py`.
- **§5** a subsection: the UI is a third door onto the same implementation, it
  calls the seam and never the adapter, and it is replaceable.
- **§6** the flag: what `--ui` starts, which port, and that the API stays stdlib.
- **§7** the option: `--ui` (default off) and `--ui-port` (7860).
- **§10** guard 13's row and the counts.
- **§4.1** is untouched: the UI adds no field to the request.

## 7. The README and the evidence

A "use the browser" section beside the CLI and the curl examples: the command,
what appears, and the honest copy's meaning in one line each.

Evidence under `tests/e2e/p9-ui/`: a committed `README.md` with the date, the
commands, what answered, and how to regenerate; a gitignored `evidence/` holding
the page's HTML as served, the response of a still submitted through the UI, and
the serialisation transcript.

## 8. What this work unit must not do

- Do not change the request vocabulary, the response shape, the queue, or the
  render path. The UI adds no field and no endpoint to the API.
- Do not call the adapter, `render`, or the queue from `ui.py`.
- Do not make the API depend on gradio. A server without `--ui` must import
  nothing from it.
- Do not invent a fourth command.
- Do not pin gradio's internal HTTP API in a test.
- Do not push, open a PR, or touch the remote.
