# Protocol

The law of `coltman-images`. Every other document defers to this one. Where this document and any other document disagree, this document wins.

## 1. What this system is

1. `coltman-images` turns one generation request into one still.
2. It owns itself: its vocabulary, its lifecycle, its connection layer, its CLI, its model entry and its tests. The model is an asset it declares and uses — it is not the model's owner, and it is nobody's annex.
3. The connection layer is a part of the system, not a by-product: an application integrates against the HTTP API, and the CLI is the first client of that API.
4. It is independently runnable with no other project present.
5. It declares its surface; nothing outside defines it for the system.
6. Its three commands are exactly `coltman-images start`, `coltman-images generate`,
   `coltman-images stop`.
7. It shows itself. The CLI and the HTTP API are two doors onto one implementation,
   and `start --ui` adds a third — a page served by the same process, from the same
   queue. The page is replaceable and is never a second renderer: it calls the same
   submission seam the API calls and reaches no model (section 5.5).

## 2. Self-containment

The system reads exactly one thing: its own tree.

Everything it needs is inside that tree: the model entry, the assets in `model/assets/` (the project's own copies), the transformer config, and its own interpreter at `.venv/bin/python`, which carries its pinned dependencies.

It never reads, imports, or resolves anything from another project. No import path, no module name, and no runtime lookup may point outside its own tree — with one declared exception: **the kernel's own interfaces**. `bin/coltman-images` reads `/proc/<pid>/cmdline` to decide whether the pid in the state file is its own server before it signals anything, and `--port` handling needs nothing else. The guard exempts `/proc`, `/sys` and `/dev` by name and prints every exemption it grants, so an exemption is a declared line and not a silent pass. A kernel interface is not another project's data store: it cannot break independent runnability.

It writes exactly two things: the stills the request asks for, and its own `run/` and `out/` directories.

A test enforces this by refusing any path outside its own tree (guard 8 in section 10). The guard reads the tree, not a declaration file, and it reports what it exempted alongside what it refused.

## 3. Layout

| Path | Kind | State |
| --- | --- | --- |
| `README.md` | entry document | document |
| `AGENTS.md` | instructions for coding agents | document |
| `.gitignore` | ignore rules | document |
| `docs/` | documents | document |
| `docs/protocol.md` | this law | document |
| `docs/context.md` | purpose, structure, environment | document |
| `docs/roadmap.md` | phases and debt schedule | document |
| `docs/changelog.md` | changelog | document |
| `docs/reference/` | the measurements and rulings the cost model is built on — evidence, not law | document |
| `model/entry.yaml` | model entry — the only declaration of assets, regime and defaults | present |
| `model/z_image.json` | pinned copy of the 473-byte transformer config | present |
| `model/assets/` | the checkpoint, the component files and the upscaler weights, the project's own copies, gitignored | present |
| `model/upscaler.yaml` | the upscale stage — its own declaration, because it serves every entry | present |
| `requirements.txt` | the pinned dependency set the venv is built from | present |
| `.venv/` | the project's own interpreter and dependencies, gitignored | present |
| `bin/coltman-images` | CLI entry point | present |
| `coltman_images/` | the package — `entry.py` resolves the entry, `adapter.py` is the model contract and registry, `render.py` is the model-agnostic core (plan, output, seed, stage), `server.py` is the process, `upscale.py` is the declared stage; `loader.py`, `fp8.py` and `adapters/zimage.py` are Z-Image's | built through P8 and P11, with U1 and U2 landed; the guard matrix is green |
| `coltman_images/ui.py` | the web page — presentation for the submission seam, gradio as its only dependency, no model | built at P9 |
| `run/` | server state, gitignored | present when a server runs |
| `out/` | default output folder, gitignored | present |
| `tests/` | the test matrix — the guards of section 10 | green |

## 4. Vocabulary

Two objects cross the surface: the generation request and the generation response. The CLI and the HTTP API carry the same two objects; there is no third shape.

A request never carries a prompt to compose. It carries the prompt it wants rendered.

### 4.1 Generation request

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `prompt` | string | yes | Non-empty. The text to render. |
| `seed` | integer | no | Absent means the server picks one and returns it in the response. |
| `width` | integer | no | Default from the entry: 1280. A positive multiple of 16, at least 256. The vendor bounds the model by total pixel area, not by axis, so the limit that binds is the area: `width × height` must not exceed the entry's `limits.max_pixels`, unless the request permits the upscale stage (section 6.2). |
| `height` | integer | no | Default from the entry: 720. Same rule. |
| `out` | string | no | When given, must be an absolute path; the server creates missing parent directories. Absent means the default folder `out/`, filename `<UTC timestamp:YYYYMMDDTHHMMSSZ>-<seed>.png`. |
| `steps` | integer | no | Absent means the entry's `steps` — 12 today. When given it must be an integer inside the entry's `limits.steps`, 8 to 16 by the operator's ruling (section 12), and a value outside that range is refused at the door before any adapter call. The same weights serve every value, so nothing swaps. |
| `upscale` | boolean | no | Absent means the native render and nothing else. `true` is the client's permission for the stage of section 6.2 to synthesize the pixels above `limits.max_pixels` — and only then. |

An unknown field is a validation failure, not a field to ignore.

The closed vocabulary is `prompt`, `seed`, `width`, `height`, `out`, `steps` and `upscale`. Each entry declares the subset it accepts, in `request_fields` (section 6.1); a field outside that subset is refused exactly like an unknown field, so the wire stays closed while a different model can accept a different subset. `upscale` is a permission, not a command: it says the client accepts pixels the model did not render, and only the declared stage of section 6.2 may produce them. There is no negative prompt: the production entry runs `guidance: 0.0`, the installed diffusers ignores `negative_prompt` below `guidance_scale` 1, and the Turbo model is distilled with no CFG branch — a negative could not act. Steering happens in the prompt itself, positively and concretely.

### 4.2 Generation response

| Field | Type | Meaning |
| --- | --- | --- |
| `out` | string | Absolute path actually written. |
| `steps` | integer | The step count this still was rendered with: the request's value, or the entry's default when the request named none. |
| `seed` | integer | Seed used for this still. |
| `width` | integer | Width rendered. |
| `height` | integer | Height rendered. |
| `model` | string | The `id` of the entry that served the still. |
| `census` | object | The census the render measured; guard 4 compares it against that entry's `expected_census`. |
| `duration_s` | number | Wall seconds from the moment the server accepted the request to the moment the response was written — includes queue wait and any load. |
| `render_s` | number | Wall seconds of the render alone, excluding queue wait and load. This is the number guard 3 measures. |
| `load_s` | number | Wall seconds spent putting the model on the card, outside the render. It is where the swap shows: 2.6–2.8 s through a warm server, 4.0 s from a cold callable that pays the page-cache read too. |
| `upscale` | object or null | `null` when the still came straight from the render. Otherwise `{"model": <id>, "scale": 2, "from": [w, h], "to": [w, h], "upscale_s": <number>}` — the stage that ran, the base it started from, and its own cost. The census is the render's; this object is the record of the pixels the model did not produce. |

## 5. The surface

Three surfaces, one implementation. The CLI is a client of the HTTP API; it contains no rendering and no second implementation of anything. The web UI (§5.5) runs inside the server process and calls the same submission seam the API's handler calls; it contains no rendering either.

### 5.1 CLI

```
coltman-images start [--port N] [--foreground] [--idle-timeout SECONDS] [--ui [--ui-port N]]
coltman-images generate --prompt "..." [--seed N] [--width N] [--height N] [--out PATH] [--steps N] [--upscale] [--json]
coltman-images stop
```

`generate` never auto-starts the server. If the server is not running it fails with exit 4 and says so. Without `--json` it prints the returned path; with `--json` it prints the generation response object. Errors go to stderr; the path — or the full response object with `--json` — goes to stdout. Machine output never mixes with diagnostics.

### 5.2 API

Loopback only: `127.0.0.1`. Default port 8420, configurable at `start`. The server never binds any other interface — binding elsewhere is refused, not offered as a flag.

Three endpoints.

`GET /health` — 200 while the port is bound:

```json
{
  "status": "warm",
  "model": "z-image-turbo-fp8",
  "census": {"float8": 239, "plain": 282, "other": 0, "total": 521},
  "pid": 12345,
  "port": 8420,
  "started_at": "<UTC timestamp>",
  "warm_at": "<UTC timestamp>",
  "queue": {"depth": 0}
}
```

`status` is always `"warm"`: the port is bound only after warm-up, so an answering port means a warm server.

`POST /generate` — body is the generation request (section 4.1); 200 body is the generation response (section 4.2):

```json
{
  "out": "/absolute/path/out/20261115T100230Z-42.png",
  "seed": 42,
  "width": 1280,
  "height": 720,
  "model": "z-image-turbo-fp8",
  "census": {"float8": 239, "plain": 282, "other": 0, "total": 521},
  "duration_s": <number>,
  "render_s": <number>
}
```

`POST /shutdown` — 200, body `{"status": "stopping"}`; in-flight work drains before the GPU is released.

### 5.3 Status codes

| Code | Body | Condition |
| --- | --- | --- |
| 200 | response object, or `{"status": "stopping"}` for `/shutdown` | the request succeeded; for `/generate`, the still was written |
| 400 | `{"error": {"code": "invalid_request", "message": "..."}}` | any request validation failure |
| 500 | `{"error": {"code": "render_failed", "message": "..."}}` | the render raised |

Errors are always `{"error": {"code": ..., "message": ...}}` — never a bare string, never a different envelope.

### 5.4 Exit codes

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | render failed |
| 2 | invalid request — or an `--idle-timeout` value the system refuses, a usage error that never reaches a request |
| 3 | a declared asset is missing |
| 4 | the server is not available (not running, unreachable, another instance already owns the card, or the port could not be claimed) |

A CLI failure maps the server's status as `400 → 2`, `500 → 1`; no state file or an unreachable port is `4`; a missing asset at `start` is `3`. A request the server never accepted is `4`; a request the server accepted and failed is `1`.

### 5.5 The web UI

The page is the third door onto the same implementation, and it is a door the operator opens at `start` time rather than one a client integrates against.

- **It calls the seam and nothing else.** `WarmServer.submit(request)` is its only route to a still (section 9, rule 8). No adapter, no render core, no queue: a page that reached any of them would be a second producer on one card, and two browser tabs would be two models.
- **It adds nothing to the contract.** No field on the request (section 4.1 is untouched), no endpoint on the API, no fourth command. What the page shows is the section 4.2 response, rendered.
- **The form carries what the request carries.** A prompt, a seed, the SD/HD switch and the step count — no field the vocabulary does not have, and no field the entry does not accept. The step control's range and its initial position come from the entry (`limits.steps` and `steps`), never from the page: the ladder is the entry's declaration, a second entry will have its own, and a page that carried today's 8..16 would refuse the next entry's range or offer one it refuses. A position equal to the entry's default is sent as an absence, because absent already means the entry's steps, so the page at rest sends exactly the request the API serves by default.
- **It is presentation, and it is replaceable.** `coltman_images/ui.py` holds four things and nothing else — the pure request builder, the one line that calls the seam, the generator that reports while it waits, and the page — plus one private helper that sizes HD from the entry's ceiling. Gradio is the first rendering of it; swapping it is replacing the page inside that module, and the seam, the queue and the law do not move.
- **It renders what the response declares.** SD or HD is `upscale: null` against an `upscale` object; the base the stage started from is `upscale.from`; the census is key and value exactly as the entry's adapter declares them, never a key written into the page; `render_s`, `load_s` and `duration_s` stay separate, because the last one is where queue wait and load are visible. Every size comes from the entry or the response — the SD/HD switch multiplies the entry's defaults by the stage's declared scale, and carries no size of its own.
- **It has no queue of its own.** The server's single-flight queue is the only one, so the page's own concurrency limit is unlimited: every submission reaches the seam at once and waits where the depth is visible. Measured before the rule: with gradio's default limit of one, a second submission sat *in front of* the seam — tens of seconds, and the pre-fix transcript was not kept, so no figure is claimed — invisible to the status line, which made the page a queue of its own and hid the wait it was supposed to show. Gradio still dispatches through a thread pool bounded by its `max_threads` (40 by default), so beyond forty simultaneous submissions it holds one; that bound belongs to the rendering layer and is declared here rather than papered over. Everything that crosses the seam waits in the server's queue, which never refuses.
- **It reports while it waits.** A request costs ~46 s and may wait behind another, so the submission runs in a worker thread and the status line carries the server's queue depth — the number `/health` reports, quoted and never interpreted, because a depth cannot say whether the request ahead is waiting or already on the card, and it counts the caller's own request until the worker picks it up. A quiet page must not be indistinguishable from a hung one.
- **A failure is named for what happened.** The seam's three outcomes are three different sentences on the page: refused before any GPU work (`InvalidRequest`), accepted and then failed (`RenderFailed`), and not accepting work at all (`ServerError`). A page that called every one of them "refused" would lie about a render it actually ran.
- **It reaches nothing else.** The page is handed the warm server and may read `submit`, `depth`, `entry` and `declaration` — the seam and the declarations, never `adapter`, `_queue` or `_enqueue`. It imports no adapter, no loader, no render core and not the declared stage, and it carries none of the entry's sizes: guard 13 asserts all of it on the parsed module, with arithmetic folded, so `640 * 2` and `"1280x720"` are caught like a bare `1280`.
- **It telephones nothing.** Analytics and the version check are off: a page that called `api.gradio.app` or `huggingface.co` would be a runtime lookup outside this tree (section 2). Measured, the server's own log for a `--ui` boot contains no `https://` line at all. Gradio's file cache — where it copies a still to serve it — lives under `run/ui/`, inside the tree, for the same reason.

## 6. The lifecycle

The three commands are one state machine.

`start`:

1. Resolve and validate `model/entry.yaml`. Validate every declared asset: the checkpoint, the VAE, the VAE config, the scheduler config, the `Qwen3/` text encoder directory, and the digest of `model/z_image.json`. A missing or unreadable asset exits 3, before any GPU work.
2. Load the checkpoint and the components.
3. Run the warm-up: one full generation at the entry's declared warm-up shape (512×512), prompt and seed. Its output is discarded, never written.
4. Measure the census.
5. Write `run/server.json`.
6. Bind `127.0.0.1` on the requested port.

Binding after warm-up is deliberate: an answering port means the assets have been read once and the model has loaded end to end — not that 6.29 GB sits in VRAM. The transformer occupies 6057 MiB and the text encoder 4207, so the card cannot hold both: each request brings in what it needs, and the peak is the larger of the two, not their sum. Moving the transformer off the card and back costs 2.8 s, while bringing it in from a warm page cache costs 0.9 s, so a server that kept it resident would be slower, not faster.

`start` is idempotent: if the server is already running the running server wins — `start` reports its pid, port and state and exits 0; a `--port` that differs from the running server's is reported on stderr and ignored, never treated as an error, and never starts a second server.

**One instance, one card.** `start` takes `run/server.lock` with `flock` before it resolves the entry and long before it loads a weight, and holds it for the life of the process. The kernel drops it when the process dies, including on `kill -9`, so a stale lock cannot exist — which is why this is a lock and not a PID file. The boot order decides this: load, warm up, then bind, so the port cannot be the guard, because a second process exhausts the card before it ever tries to bind and the bind error would arrive after the damage. A second `start`, a hand-launched `python -m coltman_images.server` on any port, and a state file deleted while a server is running are all refused with exit 4 and the holder's pid. `run/server.json` is a convenience for operators; the lock is the truth. The default is background; `--foreground` keeps it attached to the terminal.

`generate`:

1. Read `run/server.json`.
2. POST the request to `POST /generate`.
3. Print the returned path, or the full response object with `--json`.

`generate` never starts a server by itself.

`stop`:

1. POST `/shutdown`.
2. Wait up to 30 s for in-flight work.
3. Release the GPU.
4. Remove `run/server.json`.

If in-flight work has not drained within 30 s, release and exit anyway. `stop` exits 0 in both cases.

`stop` is idempotent: stopping a stopped server is a no-op.

Failure handling: a stale `run/server.json` — pid not alive, or port not answering — is detected and the operator is told to `start` again. Nothing repairs a stale state file by starting a server implicitly.

Single-flight: one worker and one FIFO queue that never refuses a request; its depth is reported by `/health`. There is no per-request ceiling: a render runs until it finishes, and `stop` is the only abort — it releases the card after its 30 s grace. Two simultaneous requests never load two models. The whole transformer is resident (6057 MiB measured, section 12), so the single worker is a decision rather than a capacity report: it keeps one queue, one census and one VRAM budget.

**Declared absence, unless declared otherwise.** By default the server never self-terminates on idle: a forgotten server keeps the port and the process until `stop`. What it holds while idle is a process, a bound port and about 165 MiB — measured at 770 MiB with the server up against 605 without it — and **not the card**: every request brings its model in and takes it out again, so the peak exists only inside a request.

`start --idle-timeout SECONDS` declares the other behavior. **Idle means no request in flight and none queued**, both conditions at once — a 45 s render leaves the queue empty while the card is busy, so a period measured on the queue alone would cut a render. When the declared period passes with nothing to do, the server retires through the same path `POST /shutdown` uses: it drains, releases, removes `run/server.json` and exits 0. There is no second retirement path. The period counts from the moment the server *becomes* idle, not from the moment a request was accepted, or a long render would eat the whole period and the server would retire the instant it finished.

The floor is the measured boot cost, **15.1 s** (11.0 s of it a discarded warm-up), and `start` refuses anything below it with exit 2 before any work: a server that idles for less than it takes to start is worse than no server. The trade the option makes is exactly that boot — the next request after a retirement pays it again. `start` is idempotent for this option as it is for `--port`: a period given while a server is already running is reported on stderr and ignored, and the running server keeps the period it was started with — the period is not recorded in `run/server.json` or `/health`, so the CLI reports what it was given rather than a comparison it cannot make.

`start --ui` serves the web page from the same process (section 5.5). The page is a second server — gradio's own, not this project's — on `127.0.0.1:7860` by default, in its own thread, while the API stays the stdlib `http.server` on its own port in the main thread. **The two never share a socket**, and nothing about the API changes when the page is mounted: the handler, the queue, the state file and the endpoints are the same ones. `--ui-port N` names the page's port and is refused without `--ui` (exit 2, a usage error): a flag that declares nothing must not look like it did something.

A server started **without** `--ui` imports nothing from gradio. The import happens inside that branch and never at module scope, so the API's dependency set is exactly what it was before P9 and a page is never a reason for the service to need a second framework. **If gradio is not importable when `--ui` is asked for, `start` exits 3** — naming what is missing and how to install it — before the mutex is taken and before any weight is loaded: the flag declares a capability, and an absent declared capability is an undeclared thing. `stop` takes the page down with the process; there is no second shutdown path. `start --ui` is idempotent as `--port` and `--idle-timeout` are: asking for a page or a different port on an already-running server is reported on stderr and ignored, because the running surface is not recorded in `run/server.json` or `/health` and the CLI will not claim a comparison it cannot make.

Two ports on one host, and neither may be the other: `--ui-port` equal to `--port` is refused with exit 2 before the mutex, because the two surfaces never share a socket. The page writes one thing inside the tree: gradio serves a still by copying it into a file cache, and `GRADIO_TEMP_DIR` points that cache at `run/ui/` — declared here because section 2 allows writes to the stills, `run/` and `out/`, and to nothing else, and a cache in `/tmp` would be an undeclared write. **The cache is not pruned**; it holds one copy of every still the page has shown, and it is the operator's to delete — the page re-creates a copy the next time it serves that file. The page's analytics and version check are off for the same reason, and both settings are assigned by the server process rather than inherited, so an exported `GRADIO_TEMP_DIR` or `GRADIO_ANALYTICS_ENABLED` in the operator's shell cannot move them.

`run/server.json`:

```json
{
  "pid": 12345,
  "port": 8420,
  "model": "z-image-turbo-fp8",
  "started_at": "<UTC timestamp>",
  "warm_at": "<UTC timestamp>",
  "census": {"float8": 239, "plain": 282, "other": 0, "total": 521}
}
```

### 6.1 The model entry

`model/entry.yaml`:

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | non-empty; the entry's name |
| `adapter` | string | the name of a model adapter (section 6.3) |
| `checkpoint` | path | the production checkpoint; must exist |
| `components` | mapping | free keys, chosen by the adapter. Each value is a path relative to the project root and every one must exist |
| `digests` | mapping, optional | component name → `sha256:<hex>`. Each key must name a component and each digest must match the file |
| `steps` | integer | 12 — the default a request inherits, and it must lie inside `limits.steps` |
| `guidance` | number | 0.0 |
| `limits.max_pixels` | integer | 921600 — the largest area measured to render on this card (1280×720); validation refuses anything above it |
| `limits.steps` | mapping | `{min: 8, max: 16}` — the range the ladder measured and the operator ruled (section 12). A request outside it is refused at the door, and the entry's own `steps` must lie inside it |
| `request_fields` | list of strings | a subset of the closed vocabulary (section 4.1) |
| `expected_census` | mapping | string → non-negative integer. The adapter owns what the keys mean |
| `defaults.width` | integer | 1280 |
| `defaults.height` | integer | 720 |
| `defaults.format` | string | `png` |
| `warmup.width` | integer | 512 |
| `warmup.height` | integer | 512 |
| `warmup.prompt` | string | `warm up` |
| `warmup.seed` | integer | 0 |

Every asset path is relative to the project root. The interpreter is not a field: it is `.venv/bin/python`, the project's own, declared once in section 2.

**The law validates the envelope and the shape, never the model's identity.** It checks that `components` maps names to paths that exist, that every `digests` key names a component and every digest matches, and that `expected_census` maps names to non-negative integers. It does not know which components an adapter needs, and it does not know what a census key counts — those are the adapter's declaration, and section 6.3 lists Z-Image's.

An unknown field, a missing required field, a component path that does not exist, or a digest mismatch refuses at `start` with exit 3, before any GPU work. An adapter whose own required components are missing, or whose census declaration is incoherent for what it counts, refuses at construction with the same exit 3 and still before a weight is loaded: the words change hands, the guarantee does not. This file is the only declaration of the assets and the sampling regime; the system's code resolves every asset path from it and declares none of its own.

The production entry declares the Turbo FP8 checkpoint and its regime, and that checkpoint is the only arm: INT8 was measured (section 11) and then discarded by the operator on 2026-11-16, so there is nothing to promote and nothing to fall back to. The base Z-Image variant is not a fallback either — a different checkpoint with full CFG, negative prompting and 28–50 steps, and a 12.31 GB BF16 transformer that does not fit this card. This system renders Turbo.

One entry is loaded at a time, and the state file records which one. A request names the tier it wants; the server serves it from the loaded entry or swaps — unload, load, warm-up — and because `render_s` measures the render alone, the swap's cost appears as the gap between `duration_s` and `render_s` instead of hiding inside one number. Today one entry exists and it accepts no tier field, so nothing can be selected. A second entry is a second file plus its tier name and its place in that mapping — and that is enough only while the second checkpoint speaks the same format and drives the same pipeline: every model-specific *value* already lives in the file, but the *code* that reads a checkpoint, builds a pipeline and drives its stages belongs to the adapter (section 6.3).

### 6.2 The upscale stage

One stage, declared once, serving every entry — it does not live inside a model entry, because it is not a property of a model.

`model/upscaler.yaml`:

| Field | Type | Value |
| --- | --- | --- |
| `id` | string | `realesrgan-x2plus` |
| `weights` | path | `model/assets/upscaler/realesrgan_x2plus.pth` |
| `scale` | integer | 2 |
| `architecture.num_feat` | integer | 64 |
| `architecture.num_block` | integer | 23 |
| `architecture.num_grow_ch` | integer | 32 |

The network is RealESRGAN's RRDBNet, owned by this project: the loader builds it, loads the file strictly — 702 tensors, none missing, none unexpected — and refuses a mismatch. `scale` is a constructor argument and not a different network: at `scale: 2` the input is pixel-unshuffled by 2, the body and both ×2 stages run, and the output is pixel-shuffled by ½; at `scale: 4` `conv_first` takes three channels and nothing is shuffled. Both files carry the same 702 key names and differ in exactly one shape, which is why swapping them is a declaration and not a code change.

The stage runs only when the request asks for an area the render cannot reach: `width × height` above `limits.max_pixels`. It then renders at the largest same-aspect size under that ceiling, snapped down to a multiple of 16, applies the network once, and resizes to exactly the requested size. The output is capped at `limits.max_pixels × scale²`.

The default is the native render with no synthesis: a request that fits gets exactly what the model rendered and the response says `upscale: null`. HD is opt-in, and it is the client's permission — never a decision the server takes on its own.

Two facts are declared instead of implied. The model's documentation proposes no upscaler at all, so this stage is the system's own capability and not a property of Z-Image. And every pixel the stage adds is synthesized, not rendered: the response records the base size it started from so no reader can mistake one for the other.

### 6.3 The model adapter

The core serves requests; an adapter serves a model. The core — the server, the entry, the size plan, the output and the declared stage — imports none of `diffusers`, `transformers`, `safetensors` or the loader; an adapter is the only thing that does. That is what makes a second model an addition instead of surgery.

`model/entry.yaml` names its adapter in one field. Exactly one exists today:

| Adapter | What it owns |
| --- | --- |
| `zimage` | the unsloth FP8 checkpoint format, the per-row dequantisation and the root-tensor remap (`loader.py`, `fp8.py`), `ZImageTransformer2DModel`, the Qwen3 encoder, the VAE, the scheduler, and the staging order that keeps them from sharing the card |

An entry naming an adapter the system does not have is refused at `start`, like any other undeclared asset. A second model is a second adapter plus a second entry, and the core does not change — which is what section 6.1 promised before the cut made it true.

**What the `zimage` adapter requires.** The law does not know these names; this section does, because the adapter owns them:

- components `transformer_config`, `vae`, `vae_config`, `text_encoder`, `text_encoder_dir` and `scheduler_config` — all six, and the adapter refuses at construction if one is absent.
- `expected_census` carrying `float8`, `plain`, `other` and `total`, with `float8` above zero and `total` equal to the sum. The census counts parameters and excludes the quantisation scales; a model with no Float8 weights is refused, because a silent downgrade still produces a plausible image (guard 4).
- the loader builds the FP8 weights from the checkpoint's own `qdata` and `_weight_scale` and owns the linear: it never copies the transformer to bfloat16 and never re-quantises. It floors the dynamic activation scale at `1e-12` itself — an all-zero activation row must not produce a zero scale (`docs/reference/upstream/`) — because torchao's `quantize_` was measured not to apply the configuration at all (section 12).

## 7. Defaults and named options

Every option the system honours is named here. There is no hidden default anywhere.

| Option | Default | Scope |
| --- | --- | --- |
| port | 8420 | `start` |
| bind address | `127.0.0.1` | fixed at `start`, not an option |
| width | from `model/entry.yaml` (`defaults.width`, 1280 today) | `generate` |
| height | from `model/entry.yaml` (`defaults.height`, 720 today) | `generate` |
| default folder | `out/` | `generate` when `out` is absent |
| warm-up shape | 512×512 | `start` |
| warm-up prompt | `"warm up"` | `start` (value lives in `model/entry.yaml`, section 6.1) |
| warm-up seed | 0 | `start` (value lives in `model/entry.yaml`, section 6.1) |
| idle timeout | none: the server never self-terminates | `start` — at least the 15.1 s boot cost, refused below it |
| ui | off: no page and no gradio import | `start` |
| ui-port | 7860 | `start --ui`; refused without `--ui` |
| queue | unbounded FIFO; depth reported in `/health` | server |
| stop grace | 30 s | `stop` |
| steps | 12 | model entry — the default; a request may override it inside `limits.steps` |
| guidance | 0.0 | model entry — distilled, no CFG branch |
| limits.max_pixels | 921600 | model entry — the largest area rendered natively |
| upscale | none: the native render | `generate`, when the request permits it and exceeds that ceiling |

## 8. The order of the work

Six steps, each built and exercised alone before the next begins.

1. The model entry, the loader, the census and one cold render callable.
2. The declared upscale stage: its own declaration, its own weights, the tiling, and the request field that permits it — so the surface is settled before a server implements it.
3. The server process and its lifecycle: start, warm-up, the state file, single-flight, and the two endpoints that make the lifecycle observable — `GET /health` and `POST /shutdown`.
4. `POST /generate`.
5. The CLI as its client.
6. The test matrix.

## 9. Rules for touching it

1. One rule, one owner.
2. The census is proof, not decoration: a render whose census shows no Float8 weights FAILS.
3. The system never reads another project.
4. The loader protocol has a single owner: this project's own module.
5. No prompt, channel or style logic lives here.
6. The tests live with the system.
7. Every component takes the resolved entry. No module reads a fixed path, and no steps, guidance or census value is hardcoded: they are the entry's data.
8. **One producer.** A still is reached through `WarmServer.submit(request)` and nowhere else: the HTTP handler parses the body and calls it, and the web UI (P9) will call it too. No module enqueues work of its own. There is one queue and one place where a second renderer could appear, and this rule is what keeps it at one.

## 10. The test matrix

Sixteen guards are declared, each with the failure it catches. All sixteen are written, and the suite collects seventeen test methods, because guard 4 is written as two (`04` and `04b`). This section is the only place the count of the current matrix is declared: every other document names the guards without counting them. A dated record of a past run keeps that run's own numbers — how many methods it collected, how long it took — because that is what it measured; `tests/e2e/p6-guards/README.md` holds the P6 run of 2026-11-15, and its twelve test methods are that run's, not the matrix's.

| # | Guard | Failure it catches |
| --- | --- | --- |
| 1 | Request validation refuses unknown fields, a missing prompt, a non-multiple-of-16 size, and a relative `out` — before any GPU work. | A malformed request reaching the loader and wasting a model load. |
| 2 | Lifecycle: start → health answers warm → generate → stop; double start exits 0; stop when stopped is a no-op; generate when stopped exits 4. | A lifecycle that is not idempotent, or a client that silently starts a hidden server. |
| 3 | The warm-up is real: the first `generate` after `start` costs steady state, not a fresh load. The first `generate` after `start` must report a `render_s` within 1.25× the median `render_s` of the next three identical requests; a first call at several times the steady state fails the guard. | A port bound before warm-up, so the first request pays the setup cost. |
| 4 | The measured census equals the entry's `expected_census` — 239 / 282 / 0 / 521 today — and a render with no Float8 weights fails. | A silent downgrade to a plain-precision load that still produces plausible images. |
| 5 | Determinism: the same request and seed produce byte-identical files. | Nondeterministic sampling or an unpinned seed path. |
| 6 | Default folder: `generate` without `--out` writes into `out/` and returns an absolute path that exists and is non-empty. | A default that writes nowhere, or returns a path that was never created. |
| 7 | CLI/API parity: the CLI produces the same bytes as a direct POST for the same seed — one implementation, no duplicate. | A second renderer hidden in the CLI that drifts from the server. |
| 8 | Self-containment: no import and no path outside its own tree — the guard reads the tree and prints every exemption it grants. Kernel interfaces (`/proc`, `/sys`, `/dev`) are exempt by name; another project's data store never is. | A stray dependency on another project that breaks independent runnability. |
| 9 | Single-flight: two concurrent requests both succeed and never run two models. | A second worker that doubles the load and splits the VRAM budget. |
| 10 | The upscale stage runs only when the request permits it and exceeds the native ceiling; when it runs, the response declares the base it started from and the stage's own cost, and the census stays the render's. | A stage that silently synthesizes pixels, or a response that lets a reader believe the model rendered them. |
| 11 | The core imports nothing from the model stack: no `diffusers`, `transformers`, `safetensors`, `coltman_images.loader` or `coltman_images.fp8` is reachable from `server.py`, `entry.py` or `render.py`. | A core that must be edited for every new model, which is the coupling an adapter exists to remove. |
| 12 | One instance, one card: with the state file deleted, `start` reports the running server instead of spawning a second; a hand-launched `python -m coltman_images.server` on another port is refused before it loads a weight; exactly one server process exists after each attempt. | A second process loading a second transformer onto a card that holds one, which is an out-of-memory crash rather than a slow request. |
| 13 | The web UI is a surface on the seam, never a second renderer: `coltman_images/ui.py` imports nothing from the model stack and carries none of the entry's sizes, reads only `submit`, `depth`, `entry` and `declaration` from the server it is handed, maps the SD/HD switch to the entry's own ceiling and aspect, names a refused request and a failed render differently, and — fired through the page itself — two concurrent submissions still serialise by a whole render. | A page that renders beside the queue — two browser tabs, two models, one card. |
| 14 | Entry neutrality: an entry with arbitrary component names, no transformer config and no float8 census loads through `entry.py` and renders through a stub adapter; and no model-specific name survives in `coltman_images/entry.py`, checked on the parsed code rather than on prose. | A law only one model can satisfy, which turns a second model into surgery on the core. |
| 15 | The step count is a request field bounded by the entry: a value outside `limits.steps` is refused before any adapter call, a value inside appears in the response, and an absent value means the entry's default. | A speed control enforced nowhere, or a request that silently renders at the default while the caller believes it chose. |
| 16 | Idle timeout: a period below the boot cost is refused at the door and starts nothing; with one declared, a request that outlasts the period is served whole rather than cut; and once the server falls idle it retires on its own — port silent, state file removed, process gone — through the path `stop` uses, with the reason in its own log. | A server that never releases a forgotten port, or one whose timer cuts a render in flight. |

## 11. The cost model the system is built against

Every row below is a measurement recorded in `docs/reference/`, except the row marked estimate. The harness is part of the number: rows that measure different boundaries are not comparable, and no row is silently converted into another row's boundary.

| Measurement | Value | Condition |
| --- | --- | --- |
| Instrumented render, per image | 56.6 s | predecessor stack, 1280×720, 12 steps |
| — per-image setup (interpreter, imports, text encoder, transformer) | ~18 s | same run; this system pays it once per server, not once per still |
| — 12 DiT forwards | 34 s (2.83 s/step) | same run |
| — write and close | ~4 s | same run |
| The predecessor's end-to-end path — a fresh interpreter per still | 78–82 s warm, 95–99 s cold | not this system's boundary. `reference/zimage-fp8-speed.md` records the distance to the instrumented row as unexplained, which is why guard 3 measures `render_s` and not an end-to-end number |
| FP8 arm, render alone | 36.14 s warm, 36.01 s cold, 3.01 s/step | bench venv, same recipe |
| INT8 arm, render alone | 42.65 s warm, 44.13 s cold, 3.56 s/step | bench venv, same recipe |
| FP8 against INT8 | −15.3 % warm, −18.4 % cold, −87 % setup (9.59 s against 74.00 s), −42 % end to end, −25.6 % peak VRAM | A/B, the transformer the only variable |
| Peak VRAM | 4651 MiB FP8, 6249 MiB INT8 | A/B |
| Card | 8188 MiB; ~1.9 GiB left for activations at the FP8 peak | measured |
| GPU | 42–43 W of 45 W, SM 1830–2115 MHz of 3105, 39–54 °C | instrumented |
| Disk and swap | 0.01 GiB read, swap flat | instrumented |
| Cold page-cache read | ≈17 s (99.1 s cold against 82.0 s warm) | controlled eviction |
| Offload profile 4 against 2 | 0.06 % (medians 56.531 s against 56.498 s) | paired interleaved, three rounds |
| Offload profile 3 | 7824 MiB peak, cold-pass OOM | measured |
| Steps 8 against 12 | −10.5 s and −10.8 s per image; 91.6 % of pixels differ | predecessor stack, measured, not adopted |
| Steps 8 against 12, this path | 29.4 s against 43.7 s — **−14.4 s, −33 %** at 1280×720, 8 forwards against 12 | this path and `.venv`, seed 42, one prompt, measured 2026-11-15 |
| Steps against time, this path | **linear at 3.87 s per step**: 4 → 16.5 s, 6 → 24.1 s, 8 → 31.8 s, 10 → 39.5 s, 12 → 47.1 s, 14 → 55.1 s, 16 → 62.9 s, 20 → 78.4 s, 24 → 93.9 s | 1280×720, nine values × five seeds, `docs/reference/steps-ladder.md` |
| Steps against convergence | SSIM between consecutive values rises from 0.772 to 0.900 at 14→16, then stays flat at 0.885–0.900; it never approaches 1, and 16→20 falls in four of five seeds | same ladder, forty-five stills |
| This path, render alone | 43.5 s warm for 12 forwards plus decode and write; the loop's own mean is 3.46 s/step | the project's own loader and `.venv`, 1280×720, whole transformer resident — a different boundary from the rows above, and not converted into one |
| This path, 512×512 | 11.0 s warm | same path, warm-up shape |
| The declared stage, ×2 | 4.6 s for 1280×720 → 2560×1440; seam 0.0029 max across 9 tiles | `realesrgan-x2plus`, tiled at 256 with 32 px of context |
| The whole HD path | 48 s end to end — 43.4 s render plus 4.6 s stage | 2560×1440 delivered from a 1280×720 render |
| Loader census | 239 float8 / 282 plain / 0 other / 521 total | loader on the production checkpoint |
| 60-still job at 56.6 s | 56.5 min, of which 18 min (32 %) is setup | estimate from the instrumented row |

The warm server is no longer justified by setup, and this project's own measurement says so. This loader pays **4.0 s of setup per request with the page cache warm**, and 3.0 s of that is interpreter start — a resident process therefore saves about 3 s of a 50 s still, not the ~18 s the predecessor paid when it spawned two Python processes per image. What the warm-up actually buys is the page cache: the first read of 6.29 GB costs ~17 s and nothing after it does. The server exists because the requirement is a service — one queue, one lifecycle, on, generate, off — and not because it is faster. The lever these measurements do support is the step count: 43.5 s of a 47.5 s request is twelve forwards plus decode and write, and at the loop's own 3.46 s/step the forwards alone are ~41.5 s — which is where the lever lives, and the operator has ruled it: `steps` is a request field bounded at 8..16, with 12 as the default (section 12). They do not support a profile change or a resolution change as production decisions: each is measured, and each is a separate ruling (section 12).

FP8 is the production default and the only arm, by the operator's ruling of 2026-11-16: the operator ran the A/B and discarded the INT8 model, so there is no fallback and no second build to promote. The speed, setup, VRAM and stability deltas above are what the ruling rests on. The quality axis does not support FP8: the blind adjudication of 2026-11-15 closed INT8 2, FP8 0, tie 1. Both facts are recorded here, and the measurement behind them is in `docs/reference/zimage-fp8-vs-int8.md` — evidence, and untouched by the decision.

## 12. What this document does not know yet

Every number in this document is either a measurement (section 11, plus one row it marks as an estimate) or a decision. The decisions are listed here so no later step mistakes them for measurements.

- The range `256..2048` is a decision, and the multiple-of-16 rule is derived from the two configs rather than measured — but a measurement now bounds it. At 1280×720 this path reserves 6698 MiB of the 7857 the card reports, leaving 1159 MiB of slack, and 2048×2048 is 4.55× the tokens of 1280×720 with attention that grows quadratically. `limits.max_pixels` therefore declares 921600 — the largest area actually rendered — and validation refuses anything above it unless the request permits the upscale stage of section 6.2. Widening it is a measurement, not a configuration change, and the trade it makes (resolution against the headroom the operator's desktop needs) is the operator's to rule.
- The warm-up cost is not measured. Guard 3 measures it on the first run.
- The stop grace (30 s) and the guard-3 ratio (1.25×) are decisions. The queue has no depth cap and there is no per-request ceiling: refusing a request, or cutting off a render, would contradict the on-demand requirement. `stop` is the abort.
- FP8 is production and the system has one arm, by the operator's ruling of 2026-11-16: the operator ran the A/B, discarded the INT8 model, and closed the question. The quality adjudication against FP8 is recorded in section 11 and in `docs/reference/zimage-fp8-vs-int8.md`; it is the evidence the ruling rests on, and the question is not open.
- `steps` is the only speed lever these measurements support, and the operator ruled on it on 2026-11-15 on a prompt built to stress the model's weak anatomy — five people around a table, hands and faces visible, one pouring a drink. The ladder behind that ruling is `docs/reference/steps-ladder.md`: nine values from 4 to 24 across five seeds, timed and compared. **The curve turns at 12–14 and the usable ceiling is 16.** Twelve is the minimum where the scene and its principal detail settle, and it stays the production default. Fourteen is the cut if the criterion is visible gain for each 15 % of extra time. From 16 upward there is no convergence to gain: 16→24 costs +49 % and SSIM stays flat at 0.885–0.900, falling in four of five seeds at 16→20. Eight to ten is the fast mode, acceptable with a reframing risk on some seeds. Below eight is not adopted: it is under the distilled design of the model and visibly dirty at 4–6. What the ladder does **not** establish by measurement is quality — SSIM measures change, not correctness. The quality question was closed by judgment and not by a count: the operator's own eye read of the contact sheets is recorded in `docs/reference/steps-ladder.md` under "What the eye saw", the eight-category error count was never produced and is not owed, and no document may claim that it exists. The cost of the whole range is linear at 3.9 s per step (section 11), so the control costs nothing to use: the same weights serve every step count, nothing swaps, and with `steps` as a request field a different step count needs no second entry at all. And the range is enforced rather than merely recorded — `limits.steps` bounds it, and a request outside it is refused at the door (guard 15).
- The vendor card states that 9 inference steps produce 8 DiT forwards. **Measured on 2026-11-15 with a global module forward hook: this stack runs exactly as many transformer forwards as the step count demands — 8 steps give 8, 12 give 12.** The off-by-one is the vendor's own example's, not this pipeline's, and section 11 no longer needs correcting.
- The production stack is the project's own `.venv` (Python 3.14.8, torch 2.13.0+cu130, CUDA 13.0), created from pinned requirements. torchao's `quantize_` was measured on 2026-11-15 to traverse the model and leave every `Linear` in bfloat16 — on torchao 0.17.0 and 0.18.0, on CPU and CUDA, with and without explicit `PerRow` granularity, on a two-layer toy and on the real transformer (census 0 / 521 / 0 / 521) — even though `Float8DynamicActivationFloat8WeightConfig` is present in `_QUANTIZE_CONFIG_HANDLER`. Why is unmeasured, and the loader does not depend on it. `torch._scaled_mm` was measured to work on this card (sm_89) with per-row scales: `scale_a` float32 `(M,1)`, `scale_b` float32 `(1,N)`, agreeing with the exact dequantized product to 2.5e-3 against a 4.8e-2 spread against plain bfloat16.

- The render core was measured on 2026-11-15 with the whole transformer resident: the loader builds the FP8 weights directly from the checkpoint and the 5.86 GiB transformer sits on the card in 6057 MiB, with the weights never streamed. That is a different boundary from section 11's 4651 MiB, where the predecessor's memory manager streamed them; the rows are not comparable and the render time of this path is not yet measured. Two implementation facts worth keeping: `ZImageTransformer2DModel.from_config` materialises in float32 (24.6 GB), so the model is built on the meta device and materialised once; and widening an FP8 e4m3 weight to bfloat16 loses nothing, so the weight axis contributes no error — the ~2.7e-2 on a real layer is the dynamic quantisation of the activation, which FP8 requires.

- `model/z_image.json` carries `axes_lens: [1536, 512, 512]`; diffusers' own default for `ZImageTransformer2DModel` is `[1024, 512, 512]`. The vendor cards do not state the value, and the checkpoint cannot settle it — rope tables are not weights, so the strict state-dict load proves the other twelve fields and proves nothing about this one. The copy came from the predecessor's config directory, deleted on 2026-11-15, so the project now holds the only copy and its provenance is itself. It is kept because it is the permissive direction: a rope table longer than the positions actually used cannot corrupt a position, while a shorter one could. If a render at the top of the declared range ever misbehaves, this is the first line to check.

- The declared stage is measured for cost and for seams, not for quality. No blind comparison exists between ×2 and ×4, nor between the stage and a plain Lanczos enlargement, so no document may claim one looks better. `model/assets/upscaler/realesrgan_x4plus.pth` is kept, and named here rather than left lying in the tree, as the other arm of that comparison; nothing reads it until a declaration names it.

A step that disproves a line here amends this document in the same work unit and records why in `docs/changelog.md`. The law is falsifiable: an unamended contradiction is the defect, not the discovery.
