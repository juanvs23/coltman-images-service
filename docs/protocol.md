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

It never reads, imports, or resolves anything from another project. No import path, no module name, and no runtime lookup may point outside its own tree. Two reads are declared exceptions, and both are named and printed the same way — an exemption is a declared line, never a silent pass: **the kernel's own interfaces**, and **a caller's reference image**.

The kernel's interfaces are the first. `bin/coltman-images` reads `/proc/<pid>/cmdline` to decide whether the pid in the state file is its own server before it signals anything, and `--port` handling needs nothing else. The guard exempts `/proc`, `/sys` and `/dev` by name and prints every exemption it grants. A kernel interface is not another project's data store: it cannot break independent runnability.

The caller's reference image is the second, and it is the mirror of `out`. `out` is a declared **write** outside the tree — the request names a path and the server creates whatever parents it needs — and `image` is a declared **read** outside it: the request names a file, the file belongs to the caller, and the system has no way to know where the caller keeps it. Neither is the system reaching for another project's data; both are the caller naming a path and the system either writing it or reading it. `out` needs no separate exemption because section 4.1 states its rule directly. The read needs one because section 2 claims the system reads only its own tree, so the exception is written down and granted by name in one place — `CALLER_READ_EXEMPTIONS` in `coltman_images/entry.py`, covering the `image` field and nothing else — and guard 8 prints it beside the kernel exemption it already grants.

**Two paths reach that field, and only one of them is the exception.** Through the page, gradio copies the upload into its file cache, and the server points that cache at `run/ui/` (section 6) — inside the tree — so the page's reference is a path the tree already holds and **no exception is involved**. Measured on 2026-11-17: an upload posted to the page's own endpoint landed at `run/ui/<hash>/reference-512.png`, and the path the page handed the handler was that file. Through the CLI or the API, the path is the caller's own argument and may be anywhere, and that is the declared exception. The distinction is not pedantry: a page that could read anywhere would make this section unenforceable, while a caller who names a path is doing exactly what `out` already lets them do in the other direction. The page's upload cache is not pruned, like its still cache, and it is the operator's to delete.

A test enforces this by refusing any path outside its own tree (guard 8 in section 10). The guard reads the tree, not a declaration file, and it reports what it exempted alongside what it refused — including the caller's reference field, which it cannot see as a literal and therefore checks as a declaration.

Two things that live inside the tree are not this project's own source, and both are declared rather than discovered. The first is the interpreter and its dependencies, `.venv/`, created from pinned `requirements.txt`. The second is the `ggml` runtime at `vendor/stable-diffusion.cpp/`, built from source — commit `532d2c1`, with the system CUDA — and named by one entry's `components.cli` and pinned by that entry's digest. It carries **one patch**, `patches/0001-flux2-lora-name-conversion.patch`, applied after the clone and before the build: the runtime is installed and the patch is committed, so what this project changed inside a foreign copy travels as a declaration of its own instead of living in an ignored directory. Both are installed, not committed, exactly as a venv is; neither is a read of another project, because a copy inside the tree is not outside it. That is the distinction this section draws: a copy inside the tree is not an exception at all, and the only declared reads that reach outside it are the kernel's interfaces and a caller's reference image — neither of which is another project's data store.

It writes exactly two things: the stills the request asks for, and its own `run/` and `out/` directories — plus a path a request names in `out`, which is the caller's choice of destination and not a third kind of write.

## 3. Layout

| Path | Kind | State |
| --- | --- | --- |
| `README.md` | entry document | document |
| `AGENTS.md` | instructions for coding agents | document |
| `.gitignore` | ignore rules | document |
| `host.yaml` | the deployment's declaration — the card's memory, the `ggml` path's offload policy, the LoRA budget, and limits that may only tighten the served entry's (section 6.1). The server reads it at boot and there is no flag for it; absent, the entry's own limits apply and the budget is the measured linear arm | present |
| `docs/` | documents | document |
| `docs/protocol.md` | this law | document |
| `docs/context.md` | purpose, structure, environment | document |
| `docs/roadmap.md` | phases and debt schedule | document |
| `docs/changelog.md` | changelog | document |
| `docs/reference/` | the measurements and rulings the cost model is built on — evidence, not law | document |
| `model/entry.yaml` | the promoted model entry — FLUX.2 [klein]'s declaration of assets, regime and defaults; the entry a service booted without `--model` serves | present |
| `model/entries/` | the entries a caller names by `id` with `--model`: Z-Image Turbo FP8's, preserved unchanged. `--model` resolves an alias across this directory and `model/entry.yaml` (section 6.1) | present |
| `model/z_image.json` | pinned copy of the 473-byte transformer config | present |
| `model/assets/` | the checkpoint, the component files, the upscaler weights and the LoRA files the promoted entry's catalog declares, the project's own copies, gitignored | present |
| `model/assets/loras/<entry-id>/` | the LoRAs one entry declares, one folder per model, named by the entry's `id` — gitignored with the weights. A LoRA belongs to the model it was verified on (section 6.1) | present |
| `model/upscaler.yaml` | the upscale stage — its own declaration, because it serves every entry | present |
| `requirements.txt` | the pinned dependency set the venv is built from | present |
| `.venv/` | the project's own interpreter and dependencies, gitignored | present |
| `vendor/stable-diffusion.cpp/` | the `ggml` runtime, built from source and installed inside the tree, gitignored — never committed, and pinned by the digest of the entry that names its binary | present |
| `patches/` | the changes this project makes inside the vendored runtime, as patch files applied after the clone — committed, because `vendor/` is not | document |
| `bin/coltman-images` | CLI entry point | present |
| `coltman_images/` | the package — `entry.py` resolves the entry, `adapter.py` is the model contract and registry, `render.py` is the model-agnostic core (plan, output, seed, stage), `server.py` is the process, `upscale.py` is the declared stage; `loader.py`, `fp8.py` and `adapters/zimage.py` are Z-Image's; `adapters/flux2klein_sd.py` is FLUX.2's, on `ggml` | built through P8 and P11, with U1, U2, U4 and the second model landed; the guard matrix is green |
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
| `width` | integer | no | Default from the entry's `defaults.width` — 1152 on the promoted entry, 1280 on Z-Image's. A positive multiple of 16, at least 256. The vendor bounds the model by total pixel area, not by axis, so the limit that binds is the area: `width × height` must not exceed the effective ceiling — the smaller of the entry's `limits.max_pixels` and the host's cap (section 6.1) — unless the request permits the upscale stage (section 6.2). |
| `height` | integer | no | Default from the entry's `defaults.height` — 1152 on the promoted entry, 720 on Z-Image's. Same rule. |
| `out` | string | no | When given, must be an absolute path; the server creates missing parent directories. Absent means the default folder `out/`, filename `<UTC timestamp:YYYYMMDDTHHMMSSZ>-<seed>.png`. |
| `steps` | integer | no | Absent means the entry's `steps` — 8 on the promoted entry, 12 on Z-Image's. When given it must be an integer inside the effective step range — the entry's `limits.steps`, narrowed by the host's when the host declares one (section 6.1) — and a value outside that range is refused at the door before any adapter call. **The range is the entry's, not the law's.** Z-Image's entry declares 8 to 16, the ladder the operator ruled (section 12); FLUX.2 [klein]'s declares 4 to 8. A distilled model may declare a narrower range, because on a distilled model the step count is nominally the training regime it was distilled for, and moving it is expected to sample outside the regime rather than trade detail for time — **an expectation this tree's own measurement failed to meet for FLUX.2 [klein]**. Measured on 2026-11-17 at 1024², one prompt and one seed: 4 steps cost 10.8 s, 6 cost 14.1 s and 8 cost 16.9 s (+31 % and +56 % of the four-step wall), and four steps produce a defect that six and eight repair — the bartender's body merged into the bar counter (`docs/reference/flux2-klein.md`, T3). Klein's entry therefore declares `{min: 4, max: 8}`: the range is bounded by what was rendered, and nothing above eight is measured or declared. The law admits any positive range an entry declares, including a single value, and refuses what falls outside it. The same weights serve every value, so nothing swaps. |
| `upscale` | boolean | no | Absent means the native render and nothing else. `true` is the client's permission for the stage of section 6.2 to synthesize the pixels above `limits.max_pixels` — and only then. |
| `lora` | list of strings | no | `alias` or `alias:weight`, each an alias the served entry's catalog declares (section 6.1). A weight is a float in `(0, 1]` and replaces the catalog's default for this still. An alias the catalog does not declare, a weight outside that range, an alias named twice in one request, and a total size above the deployment's LoRA budget are each refused at the door, naming the field and the value. Absent means no LoRA. |
| `image` | list of strings | no | Reference images: absolute paths, in the order the model should read them. Each must be a file that exists, and the count must not exceed the entry's `image.max` (section 6.1) — refused at the door, naming the path or both numbers. The caller names a path and the system invents no transport, the same shape as `out`; this is the one read section 2 declares outside the tree. Absent means the render is conditioned on the prompt alone. |

An unknown field is a validation failure, not a field to ignore.

The closed vocabulary is `prompt`, `seed`, `width`, `height`, `out`, `steps`, `upscale`, `lora` and `image`. Each entry declares the subset it accepts, in `request_fields` (section 6.1); a field outside that subset is refused exactly like an unknown field, so the wire stays closed while a different model can accept a different subset. `upscale` is a permission, not a command: it says the client accepts pixels the model did not render, and only the declared stage of section 6.2 may produce them. `image` is a capability and not a command either: an entry declares how many references its model accepts, and an entry that declares none refuses the field by name. There is no negative prompt: the promoted entry runs `guidance: 1.0` and Z-Image's `0.0`; the installed diffusers ignores `negative_prompt` below `guidance_scale` 1, Z-Image's Turbo model is distilled with no CFG branch, and the `ggml` child is handed `--cfg-scale 1.0`, where a negative cannot act either. Steering happens in the prompt itself, positively and concretely.

**`lora` carries aliases, never paths.** The catalog belongs to the entry that declares it (section 6.1) and a request never names a file, a directory or a runtime flag — the same rule that keeps a request from naming a model. A LoRA is a per-model fact: the alias means what that entry's catalog says it means, an entry with no `loras` block accepts none, and the same alias on another entry is that entry's declaration or nothing. What a selection may cost is not the entry's to say: device memory is a property of the card, so it is the deployment's **budget** (section 7), and a request whose LoRAs exceed it is refused at the door with the sum, the budget, the largest single LoRA in the catalog and the measurement behind the number (section 11). The unit is memory and not a count, because a 76 MB LoRA and a 325 MB LoRA are not one unit each: the door sums the files' own sizes, read from disk when the entry was resolved, so a LoRA replaced by a bigger one is refused without anyone editing a declaration.

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
| `image` | list of strings | The reference paths this still was conditioned on, in the order the request named them; `[]` when it carried none. The response echoes this field and not the LoRA selection, which section 12 records as a gap: a caller that needs the record of what rendered its still reads it here. |

## 5. The surface

Three surfaces, one implementation. The CLI is a client of the HTTP API; it contains no rendering and no second implementation of anything. The web UI (§5.5) runs inside the server process and calls the same submission seam the API's handler calls; it contains no rendering either.

### 5.1 CLI

```
coltman-images start [--port N] [--foreground] [--idle-timeout SECONDS] [--ui [--ui-port N]] [--model ID] [--entry PATH]
coltman-images generate --prompt "..." [--seed N] [--width N] [--height N] [--out PATH] [--steps N] [--upscale] [--lora alias[:weight]] [--image PATH] [--json] [--model ID] [--entry PATH]
coltman-images stop
```

`start --model ID` serves the entry whose `id` is `ID`. The alias is the mechanism: `model/entry.yaml` and every `model/entries/*.yaml` are scanned for the `id`, and an unknown one is refused with the ids this tree declares — the same refusal `load_adapter` makes for an unknown adapter. The alias travels to the server process, which resolves it to the file; the CLI validates it first so a typo is refused before a child is spawned. A server started with neither flag serves `model/entry.yaml`, the promoted entry.

`start --entry PATH` remains as a **development shortcut**: it names the entry file directly and skips the id resolution. It is documented as a shortcut and not as the mechanism, because it is the one path that reaches a file the alias scan never sees. `--model` and `--entry` name the same choice, so passing both is refused with exit 2.

On `generate`, `--model` is the opposite statement: the caller says which entry it believes it is talking to, and the command refuses when the running server is serving another, naming the id it is actually serving. It resolves the alias through the project's own reader — the CLI re-parses nothing and imports no YAML — and it sends no request when it refuses. Absent, nothing is resolved and nothing is compared, because a request names no model. `generate --entry PATH` makes the same check through a file, as the shortcut's other half. A mismatch is exit 2 (a usage error that never reaches a request); an alias or an entry that cannot be resolved is exit 3.

`generate` never auto-starts the server. If the server is not running it fails with exit 4 and says so. Without `--json` it prints the returned path; with `--json` it prints the generation response object. Errors go to stderr; the path — or the full response object with `--json` — goes to stdout. Machine output never mixes with diagnostics.

`generate --lora alias[:weight]` is the request field of section 4.1, repeatable once per LoRA: each occurrence appends one item to the request's `lora` list, and the CLI adds no rule of its own — the alias, the weight and the budget are the door's to accept or refuse, and a refusal arrives as `400 → exit 2` with the server's sentence. A weight the caller omits is the entry's catalog default (section 6.1), not a number the command invents. The flag exists on `generate` only: the page does not carry it, because a control for it would have to read a catalog the page is not handed, and section 5.5 fixes what the page may read.

`generate --image PATH` is the same rule for the request's `image` field: each occurrence appends one path, in the order given, and the command makes each absolute before it crosses into the server process exactly as `--out` does — a relative path is resolved against the operator's working directory, the way a shell resolves it. The count and the file's existence are the door's to accept or refuse, and a refusal arrives as `400 → exit 2` naming the path or both numbers; an entry that declares no reference capability refuses the field by name. Measured: `--image` with a path that is not there exits 2 with `image: <path> does not exist …`, and eleven references against a cap of ten exits 2 with `image: 11 reference images were given and this entry declares at most 10 …`, both before any adapter was built. The page carries the same field as an image control (section 5.5).

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
| 3 | a declared asset is missing, or the entry — an `--model` alias or an `--entry` path — cannot be resolved |
| 4 | the server is not available (not running, unreachable, another instance already owns the card, or the port could not be claimed) |

A CLI failure maps the server's status as `400 → 2`, `500 → 1`; no state file or an unreachable port is `4`; a missing asset at `start` is `3`, and so is an unknown alias or an entry that will not resolve. A request the server never accepted is `4`; a request the server accepted and failed is `1`.

### 5.5 The web UI

The page is the third door onto the same implementation, and it is a door the operator opens at `start` time rather than one a client integrates against.

- **It calls the seam and nothing else.** `WarmServer.submit(request)` is its only route to a still (section 9, rule 8). No adapter, no render core, no queue: a page that reached any of them would be a second producer on one card, and two browser tabs would be two models.
- **It adds nothing to the contract.** No field the law does not already declare (section 4.1), no endpoint on the API, no fourth command. What the page shows is the section 4.2 response, rendered.
- **The form carries what the request carries.** A prompt, a seed, the SD/HD switch, the step count, a shape and a reference image — no field the vocabulary does not have, and no field the entry does not accept. The step control's range and its initial position come from the entry (`limits.steps` and `steps`), never from the page: the ladder is the entry's declaration, a second entry will have its own, and a page that carried today's 8..16 would refuse the next entry's range or offer one it refuses. A position equal to the entry's default is sent as an absence, because absent already means the entry's steps, so the page at rest sends exactly the request the API serves by default.
- **Shapes are a list, and every size is computed.** The page offers five: `16:9`, `1:1`, `4:3`, `3:4`, `9:16`, in that order. For the chosen shape it asks for the largest box that fits — both sides on the request's block grid (section 4.1), at least 256, area within the entry's `max_pixels` — and for HD the same at `max_pixels × factor²`. Nothing is carried in the page: a different entry or a different stage changes all ten boxes without a line of it. This is why the page offers a list and not two free fields: at `4:3` the next step up is `1152×864`, 73,728 px above the ceiling, so the shape cannot reach it and the page shrinks to the largest that fits rather than asking for something the card refuses. `16:9` at SD is `1280×720` on this entry — the box its own defaults declare — so the recorded baseline does not move because a control was added.
- **The reference is a path, and the page never looks inside it.** `gr.Image(type="filepath")` is the control — the same component the page uses to show a still — and it is an *input*: the path gradio hands over is the only thing the page knows about the file. The control's visibility is the entry's `image.max`, so a model that accepts no reference hides it rather than offering a control the door would refuse. The page sends that path only when a file is set, and sends no `image` field at all when the box is empty — so an empty box is exactly the request the API serves with no reference. It never opens the file, measures it or sizes the request from it: the box comes from the entry and the aspect, and guard 13 refuses a dimension read off that control and any import of an imaging library. The upload itself lands in gradio's cache under `run/ui/`, which is why the page's path needs no exception in section 2. Measured on 2026-11-17 through the page's own client: a reference produced `sha256 bff4ebbd…` where the same prompt, seed, box and step count without one produced `0b19b719…`, and the panel named the reference the response echoed.
- **It explains itself.** Every control states what it does in one line beneath it, and a guide collapsed at the foot of the controls carries the detail: what each control means, how the result panel is to be read, and what the status line is quoting. Every number in that copy is computed when the page is built — the ladder from `limits.steps` and `steps`, the ten boxes from `size_for` and the declared stage, the ceiling from the entry — because a number written into a label is a number the next entry inherits wrongly. The copy is presentation and nothing else: it reads the entry and the declaration, and never the seam.
- **It is presentation, and it is replaceable.** `coltman_images/ui.py` holds four things and nothing else — the pure request builder, the one line that calls the seam, the generator that reports while it waits, and the page — plus two private helpers: one that reduces a shape's ratio, one that sizes a box from the entry's ceiling. Gradio is the first rendering of it; swapping it is replacing the page inside that module, and the seam, the queue and the law do not move.
- **It renders what the response declares.** SD or HD is `upscale: null` against an `upscale` object; the base the stage started from is `upscale.from`; the census is key and value exactly as the entry's adapter declares them, never a key written into the page; `render_s`, `load_s` and `duration_s` stay separate, because the last one is where queue wait and load are visible. Every size comes from the entry or the response — the SD/HD switch multiplies the entry's defaults by the stage's declared scale, and carries no size of its own.
- **It has no queue of its own.** The server's single-flight queue is the only one, so the page's own concurrency limit is unlimited: every submission reaches the seam at once and waits where the depth is visible. Measured before the rule: with gradio's default limit of one, a second submission sat *in front of* the seam — tens of seconds, and the pre-fix transcript was not kept, so no figure is claimed — invisible to the status line, which made the page a queue of its own and hid the wait it was supposed to show. Gradio still dispatches through a thread pool bounded by its `max_threads` (40 by default), so beyond forty simultaneous submissions it holds one; that bound belongs to the rendering layer and is declared here rather than papered over. Everything that crosses the seam waits in the server's queue, which never refuses.
- **It reports while it waits.** A request costs ~46 s and may wait behind another, so the submission runs in a worker thread and the status line carries the server's queue depth — the number `/health` reports, quoted and never interpreted, because a depth cannot say whether the request ahead is waiting or already on the card, and it counts the caller's own request until the worker picks it up. A quiet page must not be indistinguishable from a hung one.
- **A failure is named for what happened.** The seam's three outcomes are three different sentences on the page: refused before any GPU work (`InvalidRequest`), accepted and then failed (`RenderFailed`), and not accepting work at all (`ServerError`). A page that called every one of them "refused" would lie about a render it actually ran.
- **It reaches nothing else.** The page is handed the warm server and may read `submit`, `depth`, `entry` and `declaration` — the seam and the declarations, never `adapter`, `_queue` or `_enqueue`. It imports no adapter, no loader, no render core and not the declared stage, and it carries none of the entry's sizes: guard 13 asserts all of it on the parsed module, with arithmetic folded, so `640 * 2` and `"1280x720"` are caught like a bare `1280`.
- **It telephones nothing.** Analytics and the version check are off: a page that called `api.gradio.app` or `huggingface.co` would be a runtime lookup outside this tree (section 2). Measured, the server's own log for a `--ui` boot contains no `https://` line at all. Gradio's file cache — where it copies a still to serve it — lives under `run/ui/`, inside the tree, for the same reason.

## 6. The lifecycle

The three commands are one state machine.

`start`:

1. Resolve and validate the entry the boot names — `--model <id>` resolves an alias across `model/entry.yaml` and `model/entries/*.yaml`, `--entry PATH` names a file, and naming neither means `model/entry.yaml`, the promoted entry. Validate every declared asset: the checkpoint, every component, and every digest. A missing or unreadable asset exits 3, before any GPU work.
2. Load the checkpoint and the components.
3. Run the warm-up: one full generation at the entry's declared warm-up shape (512×512), prompt and seed. Its output is discarded, never written.
4. Measure the census.
5. Write `run/server.json`.
6. Bind `127.0.0.1` on the requested port.

Binding after warm-up is deliberate: an answering port means the assets have been read once and the model has loaded end to end — not that 6.29 GB sits in VRAM. On Z-Image's entry the transformer occupies 6057 MiB and the text encoder 4207, so the card cannot hold both: each request brings in what it needs, and the peak is the larger of the two, not their sum. Moving the transformer off the card and back costs 2.8 s, while bringing it in from a warm page cache costs 0.9 s, so a server that kept it resident would be slower, not faster. The promoted entry never puts either half on the card as a Python tensor: the `ggml` child holds one quantised pair for the whole call.

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
| `id` | string | non-empty; the entry's name, and the alias `--model` matches (section 5.1) |
| `adapter` | string | the name of a model adapter (section 6.3) |
| `checkpoint` | path | the entry's checkpoint; must exist |
| `components` | mapping | free keys, chosen by the adapter. Each value is a path relative to the project root and every one must exist |
| `digests` | mapping, optional | component name → `sha256:<hex>`. Each key must name a component and each digest must match the file |
| `steps` | integer | the default a request inherits, and it must lie inside `limits.steps`. 8 on the promoted entry, 12 on Z-Image's |
| `guidance` | number | 1.0 on the promoted entry; 0.0 on Z-Image's, which is distilled with no CFG branch |
| `limits.max_pixels` | integer | the largest area measured to render on this card; validation refuses anything above it. 1327104 on the promoted entry (1152², 13.4 s, 4701 MiB); 921600 on Z-Image's (1280×720) |
| `limits.steps` | mapping | `{min, max}`; a request outside it is refused at the door, and the entry's own `steps` must lie inside it. `{min: 4, max: 8}` on the promoted entry — the largest count measured — and `{min: 8, max: 16}` on Z-Image's, the ladder the operator ruled (section 12) |
| `request_fields` | list of strings | a subset of the closed vocabulary (section 4.1) |
| `loras` | mapping, optional | alias → `{path, weight}`: the LoRAs this model may be asked for. `path` is relative to the project root, must live under `model/assets/loras/<this entry's id>/`, and must exist; `weight` is optional and is the default a request inherits, a number in `(0, 1]`. Absent means the entry accepts no LoRA at all. A catalog entry declares no size: the file's own, read with `stat`, is what the budget is spent on |
| `image` | mapping, optional | `{max: N}`: how many reference images this model accepts, `N` a positive integer. Present, `image` must be in `request_fields`; absent, it must not be — a capability no request can use, or a field with no capability, is refused at load. Absent means the entry accepts no reference image at all, and a request that carries the field is refused by name (section 4.1) |
| `expected_census` | mapping | string → non-negative integer. The adapter owns what the keys mean |
| `defaults.width` | integer | 1152 on the promoted entry; 1280 on Z-Image's |
| `defaults.height` | integer | 1152 on the promoted entry; 720 on Z-Image's |
| `defaults.format` | string | `png` |
| `warmup.width` | integer | 512 |
| `warmup.height` | integer | 512 |
| `warmup.prompt` | string | `warm up` |
| `warmup.seed` | integer | 0 |

Every asset path is relative to the project root. The interpreter is not a field: it is `.venv/bin/python`, the project's own, declared once in section 2.

**The law validates the envelope and the shape, never the model's identity.** It checks that `components` maps names to paths that exist, that every `digests` key names a component and every digest matches, and that `expected_census` maps names to non-negative integers. It does not know which components an adapter needs, and it does not know what a census key counts — those are the adapter's declaration, and section 6.3 lists Z-Image's.

**The catalog is per model, and a request carries aliases.** `loras` is the entry's own list of what its model may be asked for: an alias the caller uses, the file it resolves to, and the weight a request inherits when it names the alias alone (section 4.1). Every alias is declared by the entry that will serve it — `pixel-art`, `anime` and `background-remove` on the promoted entry — and an entry without the block accepts no LoRA at all, which is Z-Image's case. A path is checked exactly like a component's: relative to the project root, inside the tree, and present, so a missing LoRA refuses the boot with exit 3 instead of disappearing from a still later. The alias itself is constrained by the runtime that applies it — no `:` or `>`, and not the `|high_noise|` prefix the runtime reserves — and the adapter's own declaration (section 6.3) decides whether the file can be named at all. An entry that declares a catalog and names an adapter that applies no LoRA is refused at boot, with the adapter, the aliases and the reason named.

**Each model owns its LoRAs, and the folder is the rule.** A catalog path must live under `model/assets/loras/<this entry's id>/`, and one that does not is refused at boot with both the path and the folder it should have come from — the same shape of refusal a path outside the tree already gets. The reason is not that a LoRA cannot be reused: a LoRA whose base architecture matches will usually work on another checkpoint of that architecture. It is that **there is no certainty of it** — two checkpoints can share a family, a module tree and a generator and still disagree, and a LoRA that silently applies nothing is worse than one that is refused. Ownership by folder makes the uncertainty visible instead of hiding it behind a shared path: a LoRA verified on a second model is **copied** into that model's folder, and both copies then travel with the entry that declares them. Sharing a file between two entries would be a claim nobody measured.

**An alias is scoped to its entry.** Resolution is against the served entry's catalog only — there is no registry across entries — so a request naming an alias the served entry does not declare is refused with that entry's aliases and no other model's, and the same file name under two folders is two different LoRAs that happen to share it, never a duplicate.

**How many references a model accepts is the model's fact, and the entry is where it is declared.** `image: {max: N}` is a capability — FLUX.2 [klein]'s own documentation names up to ten reference images, so the promoted entry declares `max: 10`, and Z-Image's entry declares no block at all, because its pipeline takes a prompt and seeded noise and has no reference path. The law keeps its fields closed: the block is `{max}` and nothing else, the loader refuses a count that is not a positive integer, and it refuses the two halves disagreeing — `image` in `request_fields` with no block is a field with no capability, and a block without the field is a capability nobody can name. What the request may carry is declared in section 4.1; what a model accepts is here. A model that declares a count behind an adapter that cannot carry one is refused by `load_adapter` at boot, with the adapter and the count named — a capability the runtime would ignore is exactly the kind of declaration this law refuses to let stand (section 6.3).

An unknown field, a missing required field, a component path that does not exist, or a digest mismatch refuses at `start` with exit 3, before any GPU work. An adapter whose own required components are missing, or whose census declaration is incoherent for what it counts, refuses at construction with the same exit 3 and still before a weight is loaded: the words change hands, the guarantee does not. The entry the server is serving is the only declaration of the assets and the sampling regime behind its stills; the system's code resolves every asset path from it and declares none of its own.

The promoted entry declares FLUX.2 [klein]'s quantised GGUF and its regime: eight steps, guidance 1.0, a ceiling of 1327104 px and 1152×1152 by default. It is not the only entry, and coexistence is declared rather than implied: **Z-Image Turbo FP8 remains a fully runnable entry at `model/entries/zimage.yaml`**, with its checkpoint, its step ladder, its 921600 px ceiling and its 1280×720 defaults preserved unchanged. Z-Image is the historical production model and the reference the recorded baseline (`sha256 ff3b84a0…`) belongs to. Nothing is a fallback for anything else: the two entries declare two different models, and the INT8 arm was measured (section 11) and discarded by the operator on 2026-11-16, so neither entry has a second checkpoint to promote. The base Z-Image variant is not an entry either — a different checkpoint with full CFG, negative prompting and 28–50 steps, and a 12.31 GB BF16 transformer that does not fit this card.

**Two entries coexist; one model is served at a time.** The card is single, so the entry is chosen when the server boots — by `start --model <id>` (the mechanism, section 5.1), by `start --entry PATH` (the development shortcut), or `model/entry.yaml` when nothing is named — and changing it is `stop` and `start` again, which costs a boot and nothing else. A request names no model (section 4.1), so nothing swaps inside a request, and two entries never load together. The state file records which one is serving. An entry the caller did not select is read only for its `id`: a non-default entry whose asset is missing does not block another entry's boot, and refuses with exit 3 the moment it is selected. `docs/reference/flux2-klein.md` is the measurement record of both FLUX.2 runtimes, and of why the diffusers one was removed on 2026-11-17.

**The host declaration.** `host.yaml` at the tree root declares **the deployment**, kept apart from what a model is. The entry carries the model's facts — its assets, its regime, and the largest box it has been measured to render on this card; the host carries the machine's: how much device memory the card offers, whether the `ggml` path may offload to the CPU, and — optionally — limits tighter than the served entry's. The server reads it at boot, exactly as it reads the entry: there is no flag for it, and `start`/`generate` gained none.

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | non-empty; the deployment's name, quoted in the boot log |
| `vram_mib` | integer | positive; torch-usable device memory on this card, **7857** here. A reading of the machine, not a budget the system enforces |
| `offload` | boolean | whether the `ggml` child is handed `--offload-to-cpu`. `true` adds the flag, `false` leaves it out (section 6.3) |
| `lora_budget_mib` | integer, optional | the device memory this deployment dedicates to a request's LoRAs, in MiB; **3200** here. The door sums the requested LoRAs' file sizes against it, so it is a memory and not a count (section 11). It must not exceed the card's own `vram_mib` |
| `limits.max_pixels` | integer, optional | at most the served entry's measured ceiling and at least the area of its default box; the smaller of the two ceilings binds |
| `limits.steps` | mapping, optional | `{min, max}` inside the entry's range and containing the entry's default count; the two ranges are intersected |

`limits` is the one optional block, and it is all-or-nothing: a host either declares both its ceiling and its step range or declares neither. A host that declares neither describes the machine and tightens nothing.

**The LoRA budget is the deployment's, and it is a memory.** `lora_budget_mib` is not inside `limits` because it is not an entry fact at all: how much device memory a request's LoRAs may fill is a property of the card. The door sums what the requested LoRAs' **files** weigh — measured with `stat` when the entry is resolved — and refuses a request above the budget with the sum, the budget and the largest single LoRA in the catalog named. A count would be the wrong unit: a 76 MB LoRA and a 325 MB LoRA are not one unit each, and the same budget in MiB is a rule that stays true when one LoRA is replaced by a bigger file. `3200` on this deployment is reasoned, not measured as a cliff: the render's own peak is 4815 MiB at the default box and step count, the card reports 7857 MiB usable, and the runtime plateaus at ~7.6 GB with LoRAs loaded — so 3200 leaves the render untouched, keeps the arrangement under what the card reports, and stays clear of the plateau. A host cannot budget more than the card it declares reports usable: that is refused at boot, naming both numbers, because it is device memory the machine does not have. Neither `start` nor `generate` gained a flag for it; the declaration is read at boot with the rest of `host.yaml`.

**A host may tighten, never widen.** The effective `max_pixels` is the smaller of the host's and the entry's; the effective step range is their intersection; both are what the door validates against, in the same place `limits` was enforced before, and before any adapter call. A host declaring a ceiling **above** the entry's measured one, or a step range reaching outside the entry's, is refused **at boot** with exit 3 and a message naming the bound: the entry's ceiling is a measurement, and a host is not allowed to promise a box nobody rendered. Two conflicts inside the tightened set are refused the same way, both naming their numbers: a cap below the area of the box the entry renders by default (the system will not silently shrink every default request — the best box is a model fact and the machine's ceiling is a host fact, and it does not choose between them), and a step range that excludes the entry's default count (a request naming no steps would otherwise render outside the range that bounds it).

**A missing `host.yaml` is not an error.** The entry's own limits apply, `offload` is `true` and the LoRA budget is the measured linear arm — **3443 MiB**, the memory eleven 325 MB selections cost on this card — which is what this service did before the declaration existed, so a tree without one runs exactly as it did, and that is what portability means here. The guard that proves all of it is guard 17 (section 10), and guard 18 proves the LoRA half.

**This tree declares no `limits`, and the arithmetic is why.** Both entries render their default box exactly at their measured ceiling — FLUX.2 [klein] at 1152×1152 = 1,327,104 px, Z-Image at 1280×720 = 921,600 px — so any cap that tightens either entry is below that entry's default box and is refused by the rule above, while a cap above either ceiling widens a measurement and is refused by the other. No single cap fits both entries: klein's default box is larger than Z-Image's whole measured ceiling. A host declaration that carried a ceiling would therefore decide the deployment down to one entry, and this service serves two; the step ranges have the same shape. What is left for this deployment to declare — its memory and its offload policy — is declared. A deployment that wants a smaller box declares a cap **and** an entry whose defaults fit under it, and that entry's defaults are a model fact, changed by measurement and not by the host.

One consequence is declared rather than discovered: the page's boxes are computed from the entry's ceiling (section 5.5), so a host that tightens `max_pixels` below it would leave the page offering boxes the door refuses. Nothing in this tree tightens a ceiling today — no entry has the room — and the refusal is honest when it comes; wiring the page to the effective limits is a change to section 5.5 and to guard 13, and it is not made here.

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

`model/entry.yaml` names its adapter in one field. Three exist today:

| Adapter | What it owns |
| --- | --- |
| `zimage` | the unsloth FP8 checkpoint format, the per-row dequantisation and the root-tensor remap (`loader.py`, `fp8.py`), `ZImageTransformer2DModel`, the Qwen3 encoder, the VAE, the scheduler, and the staging order that keeps them from sharing the card. It declares `supports_loras = False` and `supports_images = False`, and `encode` refuses a reference it is handed rather than dropping it |
| `flux2klein_sd` | FLUX.2's quantised GGUF: `run/server.lock` held across the child's whole life, the `sd-cli` command line built from the entry and from the host's `offload` declaration (section 6.1), the prompt tags that select a LoRA and the directory they resolve against, the `-r` references it hands the child in the caller's order, the PNG it writes, and a census of the artefacts it handed over. It owns no tensor graph at all |
| `moss` | MOSS-Image's DMD int8 diffusion transformer with the three artefacts beside it (the FLUX.2 VAE, the GGUF text encoder and the tokenizer that encoder reads): the same subprocess discipline as `flux2klein_sd` — `run/server.lock` across the child's whole life, the command line built from the entry and the host's `offload`, the prompt tags that select a LoRA against **this entry's own LoRA folder**, a census of the four artefacts handed over — plus the boundary this model adds: a width or height that is not a multiple of 16 is refused before the child starts, because its latents are a sixteenth of the frame. It declares `supports_loras = True` and `supports_images = False` |

A second FLUX.2 runtime — the official scaled-FP8 checkpoint through diffusers — existed from 2026-11-16 and was removed with its assets on 2026-11-17. `docs/reference/flux2-klein.md` keeps its numbers because they are the measurement the removal rests on.

An entry naming an adapter the system does not have is refused at `start`, like any other undeclared asset. A second model is a second adapter plus a second entry, and the core does not change — which is what section 6.1 promised before the cut made it true.

**What the `zimage` adapter requires.** The law does not know these names; this section does, because the adapter owns them:

- components `transformer_config`, `vae`, `vae_config`, `text_encoder`, `text_encoder_dir` and `scheduler_config` — all six, and the adapter refuses at construction if one is absent.
- `expected_census` carrying `float8`, `plain`, `other` and `total`, with `float8` above zero and `total` equal to the sum. The census counts parameters and excludes the quantisation scales; a model with no Float8 weights is refused, because a silent downgrade still produces a plausible image (guard 4).
- the loader builds the FP8 weights from the checkpoint's own `qdata` and `_weight_scale` and owns the linear: it never copies the transformer to bfloat16 and never re-quantises. It floors the dynamic activation scale at `1e-12` itself — an all-zero activation row must not produce a zero scale (`docs/reference/upstream/`) — because torchao's `quantize_` was measured not to apply the configuration at all (section 12).

**What `flux2klein_sd` requires**, in the same terms:

- components `cli`, `vae` and `llm`, and its census is `artifacts` and `bytes` — the files it hands the child and their measured size. It declares no parameter census because it reads no parameters: the tensor graph belongs to the subprocess, and its stdout is prose, so the adapter declares what it can prove and claims nothing it cannot.
- it does not put the text encoder on the card: the child holds it quantised. That is the property `docs/reference/flux2-klein.md` measures, and the reason this runtime replaced the diffusers one, whose 8.05 GB encoder ran on the CPU.
- its `--offload-to-cpu` flag is read from the host declaration and not carried here (section 6.1): `offload: true` adds it, `false` leaves it out, and an absent host means `true`. The flag is a fact about the deployment's memory, so it belongs to the host and is asked for through `coltman_images/host.py`.
- **it applies the entry's LoRAs, and only the runtime's own syntax can do it.** `sd-cli` selects a LoRA from the prompt — `<lora:NAME:WEIGHT>`, resolved against `--lora-model-dir` and stripped before the text reaches the encoder — so the core hands the adapter the request's selection as aliases resolved against the catalog, and the adapter turns each one into a tag and names the project root as the directory. Nothing about that syntax reaches the law, the core or the CLI: a request carries aliases (section 4.1) and the adapter is the only thing that knows how its runtime spells one. Two consequences are refused rather than silently tolerated: a catalog path containing `:` or `>` cannot be expressed in the tag and refuses at `prepare`, and a tag whose file is missing would be *dropped by the runtime with a warning while the render continues*, so the adapter re-checks the file before it builds the command. The adapter declares `supports_loras`, and an entry that declares a catalog and names an adapter without it is refused by `load_adapter` at boot — exit 3, with the adapter, the aliases and the reason named — because an entry that declares LoRAs it cannot apply is a declaration the system would otherwise ignore. `zimage` applies none and says so, which is why Z-Image's entry declares no catalog.

- **it carries reference images as `-r <path>`, once per file, in the order the core resolved.** The runtime's flag is repeatable, and FLUX.2's model definition carries the `flux2` reference preset with `pass_to_dit` on and `ref_index_mode=increase` (`src/model/diffusion/model.hpp`, `src/model/integrations/flux2.cpp`), so each reference is VAE-encoded and passed to the denoiser as a latent and its index is what the model conditions on. Nothing about that reaches the law, the core or the CLI: a request carries absolute paths (section 4.1), and the adapter is the only thing that knows a reference reaches this runtime as a flag. Two facts are refused rather than discovered: the child **exits 1** on a reference it cannot read, so `encode` re-checks each file before the command is built; and the adapter declares `supports_images`, so an entry that declares a reference count and names an adapter without it is refused by `load_adapter` at boot — exit 3, with the adapter and the count named. `zimage` carries none and says so, and its `encode` refuses a reference it is handed rather than dropping it, so an entry that declares one behind it can only fail at the boot, not at the still.

**What the `moss` adapter requires**, in the same terms:

- components `cli`, `vae`, `llm` **and** `tokenizer`, and its census is `artifacts` and `bytes` — the four files it hands the child and their measured size. Like `flux2klein_sd` it declares no parameter census, because the tensor graph belongs to the subprocess and its stdout is prose; the fourth artefact is the external vocabulary the GGUF encoder reads, which is why this model declares one component more than klein.
- the same card discipline for the same reason: it takes `run/server.lock` before the child starts and accepts only its own process's server as the holder. `--offload-to-cpu` is read from the host declaration, not carried here (section 6.1).
- **a width and a height that are multiples of 16.** MOSS-Image's latents are a sixteenth of the frame — the FLUX.2 VAE downsamples by 8 and its decode unpacks a 2×2 patch — so a side off that grid is refused at the adapter's door, naming both numbers, rather than left to the runtime to fit to its own grid. The service's door already refuses the same shape; this is the rule at the adapter's boundary, because a direct `denoise` call does not pass the first gate.
- **it applies the entry's LoRAs through the same tag syntax, against the entry's own folder.** `--lora-model-dir` names `model/assets/loras/<id>/` — the one folder the loader already requires every catalog path to live under (section 6.1) — and each tag's `NAME` is that file's name inside it. The two refusals are klein's: a catalog path carrying `:` or `>` cannot be expressed in the tag and refuses at `prepare`, and a tag whose file is missing is dropped by the runtime with a warning while the render continues, so the adapter re-checks the file before it builds the command. A request that names no LoRA adds neither the tags nor the flag.
- **it carries no reference image, and says so.** MOSS-Image's path here is text-to-image: the adapter declares `supports_images = False`, so an entry that declares a reference count behind it is refused at boot — exit 3, with the adapter and the count named — and `encode` refuses a reference it is handed rather than dropping it.

## 7. Defaults and named options

Every option the system honours is named here. There is no hidden default anywhere.

| Option | Default | Scope |
| --- | --- | --- |
| port | 8420 | `start` |
| bind address | `127.0.0.1` | fixed at `start`, not an option |
| model | `model/entry.yaml` (the promoted entry) | `start --model <id>` — resolves the id across `model/entry.yaml` and `model/entries/*.yaml`; an unknown id is refused with the ids this tree declares |
| entry (shortcut) | none: no file is named, so nothing is skipped | `start --entry PATH` — the development shortcut that names the file directly |
| model check | none: `generate` compares nothing | `generate --model <id>` — refuses a server serving another entry, naming the id it serves |
| entry check (shortcut) | none: `generate` compares nothing | `generate --entry PATH` — the same check through a file |
| width | from the served entry's `defaults.width`: 1152 on the promoted entry, 1280 on Z-Image's | `generate` |
| height | from the served entry's `defaults.height`: 1152 on the promoted entry, 720 on Z-Image's | `generate` |
| default folder | `out/` | `generate` when `out` is absent |
| warm-up shape | 512×512 | `start` |
| warm-up prompt | `"warm up"` | `start` (value lives in `model/entry.yaml`, section 6.1) |
| warm-up seed | 0 | `start` (value lives in `model/entry.yaml`, section 6.1) |
| idle timeout | none: the server never self-terminates | `start` — at least the 15.1 s boot cost, refused below it |
| ui | off: no page and no gradio import | `start` |
| ui-port | 7860 | `start --ui`; refused without `--ui` |
| queue | unbounded FIFO; depth reported in `/health` | server |
| stop grace | 30 s | `stop` |
| steps | the entry's `steps`: 8 on the promoted entry, 12 on Z-Image's | model entry — the default; a request may override it inside the effective step range |
| guidance | the entry's: 1.0 on the promoted entry, 0.0 on Z-Image's | model entry |
| limits.max_pixels | the entry's: 1327104 on the promoted entry, 921600 on Z-Image's | model entry — the largest area rendered natively; the effective ceiling is the smaller of it and the host's cap |
| host declaration | `host.yaml` at the tree root; absent means the entry's own limits apply and the LoRA budget is the measured 3443 MiB | read at boot, never a flag; `limits` is optional and may only tighten (section 6.1) |
| offload | `true`: the `ggml` child is handed `--offload-to-cpu` | `flux2klein_sd`; the host's `offload` decides, and an absent host means `true` |
| lora | none: no LoRA is applied | `generate --lora alias[:weight]`, repeatable; an alias comes from the served entry's catalog and a weight from the request or from the catalog |
| image | none: no reference image | `generate --image PATH`, repeatable; the count is the served entry's `image.max` (10 on the promoted entry, none on Z-Image's), and the page's image control sends one path when a file is set and no field when it is not |
| lora_budget_mib | 3443 — the measured linear arm — when the tree declares none; 3200 here | `host.yaml`; optional, read at boot, never a flag; the requested LoRAs' file sizes are summed against it (sections 6.1 and 11) |
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
3. The system never reads another project. It reads its own tree, and — through the
   request field `image` — the reference file a caller names (section 2): a request's
   input, chosen per call, which is not a dependency and cannot break independent
   runnability.
4. The loader protocol has a single owner: this project's own module.
5. No prompt, channel or style logic lives here.
6. The tests live with the system.
7. Every component takes the resolved entry. No module reads a fixed path, and no steps, guidance or census value is hardcoded: they are the entry's data.
8. **One producer.** A still is reached through `WarmServer.submit(request)` and nowhere else: the HTTP handler parses the body and calls it, and the web UI (P9) will call it too. No module enqueues work of its own. There is one queue and one place where a second renderer could appear, and this rule is what keeps it at one.

## 10. The test matrix

Nineteen guards are declared, each with the failure it catches. All nineteen are written, and the suite collects twenty test methods, because guard 4 is written as two (`04` and `04b`). This section is the only place the count of the current matrix is declared: every other document names the guards without counting them. A dated record of a past run keeps that run's own numbers — how many methods it collected, how long it took — because that is what it measured; `tests/e2e/p6-guards/README.md` holds the P6 run of 2026-11-15, and its twelve test methods are that run's, not the matrix's.

**The matrix has a per-test deadline and refuses to finish with a live server**, because that is what makes the guards trustworthy: a test that overruns its budget — 420 s, `COLTMAN_TEST_DEADLINE_S` to change it — fails by name instead of hanging the run, and the module teardown kills any `coltman_images.server` process it finds and then fails on having found one, so a guard that leaves the card taken is a red run and not a phantom the next run inherits.

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
| 15 | The step count is a request field bounded by the entry: a value outside `limits.steps` is refused before any adapter call, a value inside appears in the response, and an absent value means the entry's default. The range is the entry's, so a distilled entry's single-value range is admitted and its neighbours are refused. | A speed control enforced nowhere, or a request that silently renders at the default while the caller believes it chose. |
| 16 | Idle timeout: a period below the boot cost is refused at the door and starts nothing; with one declared, a request that outlasts the period is served whole rather than cut; and once the server falls idle it retires on its own — port silent, state file removed, process gone — through the path `stop` uses, with the reason in its own log. | A server that never releases a forgotten port, or one whose timer cuts a render in flight. |
| 17 | The host declaration may tighten the deployment's limits and never widen them: a ceiling above the served entry's measured one, a step range reaching outside the entry's, and a cap below the box that entry renders by default are each refused at boot, with the two numbers named; a host that tightens is what the door validates against, so the tightened value is refused above the cap before any adapter call and a value inside it is served; a tree with no `host.yaml` still serves the entry's own limits; and the declaration's `offload` reaches the child's command line in both states. | A host that promises a box nobody rendered, or a machine's ceiling silently overriding a model's measurement — and a deployment whose limits cannot be declared without editing every entry. |
| 18 | A LoRA is a catalog on the entry and a budget on the host: an alias the catalog does not declare is refused with the known aliases listed, a request whose LoRAs exceed the deployment's `lora_budget_mib` is refused naming the sum, the budget and the largest single LoRA in the catalog, and a request that fits is served — one LoRA at 256×256 renders different bytes from the same request without it, so the selection reached the runtime, and the child's command line carries the tag and the directory it resolves against. | A request naming a LoRA the entry does not declare, a selection the card cannot afford in memory, and a selection that reaches the request parser but never the model — a still that quietly ignores what the caller asked for. |
| 19 | A request may carry a reference image: a path that does not exist is refused naming it, a count above the entry's `image.max` is refused with both numbers, and a request carrying one reference is served and renders different bytes from the same request without it, with the response echoing the path it used. The field belongs to the entry, so a model declaring no reference refuses it by name; the two halves of an entry's declaration must agree; and an entry declaring a count behind an adapter that cannot carry one is refused at boot. The child's command line carries one `-r` per file, in the caller's order. | A picture the caller sent and the runtime never saw — a still that ignored it — or a capability declared in an entry and enforced nowhere. |

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
| FLUX.2 klein, diffusers scaled-FP8, loop and decode — **removed path** | 6.8 s at 1024², 4 steps | measured 2026-11-16; 4.07 GB checkpoint, the encoder not in this row. The checkpoint and its encoder were deleted on 2026-11-17 and these rows are that path's record |
| FLUX.2 klein, the same request through this service — **removed path** | `render_s` 7.054 s, `load_s` 77.947 s (Qwen3-4B bf16 on the CPU, 8.05 GB, dropped before the transformer takes the card), 5262 MiB of device memory at the 250 ms sampler's peak | the diffusers adapter, seed 7, 1024², measured 2026-11-16, `docs/reference/flux2-klein.md` |
| FLUX.2 klein, the two runtimes measured whole | wall **167.5 s against 22.4 s**; device peak **5745 against 4305 MiB**; whole-process-tree RSS **10280 against 6349 MiB** | removed diffusers path against the surviving `ggml` path, 1024², seed 7, one prompt, 250 ms sampler, measured 2026-11-16 (`tests/e2e/flux2-klein/evidence/resource-profile.json`) |
| FLUX.2 klein, sd.cpp Q4_K_M, resident | 9.7 s at 1024², 4 steps, 7170 MiB | 2.60 GB GGUF, the encoder quantised inside the child |
| FLUX.2 klein, sd.cpp Q4_K_M, `--offload-to-cpu` | 10.3 s at 1024², 4 steps, 3916 MiB | the arm this service runs (decision 4 of the second model) |
| FLUX.2 klein, the same request through this service | `render_s` 15.508 s, `load_s` 0 (one subprocess call, its load not separable from its sampling), 3822 MiB at the sampler's peak | `flux2klein_sd`, seed 7, 1024², `--offload-to-cpu` |
| FLUX.2 klein, one reference image | **+1.6 s of `render_s`**: 7.176–7.510 s with a reference against 5.532–5.832 s without one, two runs each | `flux2klein_sd`, 512², four steps, one prompt and one seed, `background-remove` in both arms — so the delta is the reference's own encode and conditioning, not the LoRA; recorded in `docs/reference/lora-catalog.md` §5.2 |
| FLUX.2 klein, diffusers bf16 + sequential offload — **removed path** | 14.7 s at 1024², 4 steps, 2462 MiB | measured 2026-11-16; the arm with the largest disk footprint and the cheapest card |
| FLUX.2 klein, 1280×720 on the FP8 path — **removed path** | 6.1 s, 6208 MiB | measured 2026-11-16, before this service served it |
| FP8 against bf16 over identical FLUX.2 weights — **removed path** | PSNR 38.32 dB, mean per-channel difference 1.30/255 | measured 2026-11-16; the quantisation is not the variable |
| This path, render alone | 43.5 s warm for 12 forwards plus decode and write; the loop's own mean is 3.46 s/step | the project's own loader and `.venv`, 1280×720, whole transformer resident — a different boundary from the rows above, and not converted into one |
| This path, 512×512 | 11.0 s warm | same path, warm-up shape |
| The declared stage, ×2 | 4.6 s for 1280×720 → 2560×1440; seam 0.0029 max across 9 tiles | `realesrgan-x2plus`, tiled at 256 with 32 px of context |
| The whole HD path | 48 s end to end — 43.4 s render plus 4.6 s stage | 2560×1440 delivered from a 1280×720 render |
| LoRAs, per MiB of weights | **a 325 MB LoRA costs +313 MiB of device memory and +1.5 s**, linear to eleven selections | 512×512, eight steps, one prompt and one seed, that LoRA duplicated by hardlink to get distinct paths; 1 to 16 applied at once, measured 2026-11-17, the full ladder in `docs/reference/lora-catalog.md` |
| LoRAs, the linear arm | 11 selections: **7189 MiB and 23.6 s** — 3443 MiB of it the LoRAs' own, which is the default budget | same run |
| LoRAs, the plateau | **from 12 the memory plateaus at ~7.6 GB and the wall time doubles**: 39.9 s at 12 and 51.0 s at 16 | same run. The runtime stops growing and starts paying in time instead — not a count anybody should encode as a limit |
| LoRAs, survival | **no out-of-memory failure anywhere up to 16** | same run. The limit is throughput, not survival |
| Loader census | 239 float8 / 282 plain / 0 other / 521 total | loader on the production checkpoint |
| 60-still job at 56.6 s | 56.5 min, of which 18 min (32 %) is setup | estimate from the instrumented row |

The LoRA rows are one run, and the harness is part of the number: one 325 MB LoRA **duplicated by hardlink**, so 12 to 16 selections are 12 to 16 distinct paths carrying identical weights. What they measure is the cost of N selections, not the effect of N styles — the stills were not compared (section 12). They are **what this card does per MiB of LoRA weights**, and they are not a count the law encodes: `lora_budget_mib` is a memory, and what the door checks is the sum of the requested files' sizes.

The warm server is no longer justified by setup, and this project's own measurement says so. This loader pays **4.0 s of setup per request with the page cache warm**, and 3.0 s of that is interpreter start — a resident process therefore saves about 3 s of a 50 s still, not the ~18 s the predecessor paid when it spawned two Python processes per image. What the warm-up actually buys is the page cache: the first read of 6.29 GB costs ~17 s and nothing after it does. The server exists because the requirement is a service — one queue, one lifecycle, on, generate, off — and not because it is faster. The lever these measurements do support is the step count: 43.5 s of a 47.5 s request is twelve forwards plus decode and write, and at the loop's own 3.46 s/step the forwards alone are ~41.5 s — which is where the lever lives, and the operator has ruled it: `steps` is a request field bounded at 8..16 on Z-Image's entry, with 12 as its default (section 12), and at 4..8 with 8 as the default on the promoted entry. They do not support a profile change or a resolution change as production decisions: each is measured, and each is a separate ruling (section 12).

FP8 is Z-Image's production default and the only arm for that model, by the operator's ruling of 2026-11-16: the operator ran the A/B and discarded the INT8 model, so there is no fallback and no second build to promote. The speed, setup, VRAM and stability deltas above are what the ruling rests on. The quality axis does not support FP8: the blind adjudication of 2026-11-15 closed INT8 2, FP8 0, tie 1. Both facts are recorded here, and the measurement behind them is in `docs/reference/zimage-fp8-vs-int8.md` — evidence, and untouched by the decision.

## 12. What this document does not know yet

Every number in this document is either a measurement (section 11, plus one row it marks as an estimate) or a decision. The decisions are listed here so no later step mistakes them for measurements.

- The range `256..2048` is a decision, and the multiple-of-16 rule is derived from the two configs rather than measured — but a measurement now bounds it. At 1280×720 this path reserves 6698 MiB of the 7857 the card reports, leaving 1159 MiB of slack, and 2048×2048 is 4.55× the tokens of 1280×720 with attention that grows quadratically. `limits.max_pixels` therefore declares 921600 on Z-Image's entry — the largest area actually rendered for it — and validation refuses anything above it unless the request permits the upscale stage of section 6.2. Widening it is a measurement, not a configuration change, and the trade it makes (resolution against the headroom the operator's desktop needs) is the operator's to rule.
- The warm-up cost is not measured. Guard 3 measures it on the first run.
- The stop grace (30 s) and the guard-3 ratio (1.25×) are decisions. The queue has no depth cap and there is no per-request ceiling: refusing a request, or cutting off a render, would contradict the on-demand requirement. `stop` is the abort.
- FP8 is Z-Image's production default and the only arm for that model, by the operator's ruling of 2026-11-16: the operator ran the A/B, discarded the INT8 model, and closed the question. The quality adjudication against FP8 is recorded in section 11 and in `docs/reference/zimage-fp8-vs-int8.md`; it is the evidence the ruling rests on, and the question is not open.
- `steps` is the only speed lever these measurements support, and the operator ruled on it on 2026-11-15 on a prompt built to stress the model's weak anatomy — five people around a table, hands and faces visible, one pouring a drink. The ladder behind that ruling is `docs/reference/steps-ladder.md`: nine values from 4 to 24 across five seeds, timed and compared. **The curve turns at 12–14 and the usable ceiling is 16.** Twelve is the minimum where the scene and its principal detail settle, and it stays Z-Image's default. Fourteen is the cut if the criterion is visible gain for each 15 % of extra time. From 16 upward there is no convergence to gain: 16→24 costs +49 % and SSIM stays flat at 0.885–0.900, falling in four of five seeds at 16→20. Eight to ten is the fast mode, acceptable with a reframing risk on some seeds. Below eight is not adopted: it is under the distilled design of the model and visibly dirty at 4–6. What the ladder does **not** establish by measurement is quality — SSIM measures change, not correctness. The quality question was closed by judgment and not by a count: the operator's own eye read of the contact sheets is recorded in `docs/reference/steps-ladder.md` under "What the eye saw", the eight-category error count was never produced and is not owed, and no document may claim that it exists. The cost of the whole range is linear at 3.9 s per step (section 11), so the control costs nothing to use: the same weights serve every step count, nothing swaps, and with `steps` as a request field a different step count needs no second entry at all. And the range is enforced rather than merely recorded — `limits.steps` bounds it, and a request outside it is refused at the door (guard 15).
- **That ladder is Z-Image's, and its range is Z-Image's entry's.** The ruling above measures a quality dial, so 8..16 is what Z-Image's entry declares, and 12 stays its default. It is **not** a floor the law imposes: on a distilled model the step count is nominally the regime the model was trained for rather than a dial, and moving it is expected to leave the regime instead of buying detail — an expectation this tree measured and falsified for FLUX.2 [klein]. **Measured on 2026-11-17, the step count is a quality lever on this model and not an inert knob** — 10.8 s at four, 14.1 s at six and 16.9 s at eight, 1024², one prompt, one seed, on the `ggml` path. At four steps the bartender's body is merged into the bar counter — apron and hips rendered on the near face of the furniture while the torso stays behind it — and at six and eight the occlusion is correct and the apron carries more detail. The defect the four-step regime produces is the same one that `docs/reference/flux2-klein.md` records in the removed diffusers path's stills, which were also rendered at four. **The operator ruled on 2026-11-17 that the trade is worth taking: klein's entry declares `{min: 4, max: 8}` and defaults to 8 steps.** The range is bounded by what was rendered — 8 is the largest count measured, and the entry declares nothing above it. Evidence: `tests/e2e/flux2-klein/evidence/staircase/bartender-crop.png`.
- The vendor card states that 9 inference steps produce 8 DiT forwards. **Measured on 2026-11-15 with a global module forward hook: this stack runs exactly as many transformer forwards as the step count demands — 8 steps give 8, 12 give 12.** The off-by-one is the vendor's own example's, not this pipeline's, and section 11 no longer needs correcting.

- **The step range belongs to the entry** — this is the ruling section 4.1 states, taken on 2026-11-16 when FLUX.2 [klein] arrived at 4 steps and the law's prose read as if 8 were a floor. It is not: `limits.steps` is the entry's declaration, the law's rule is that a request outside it is refused at the door, and the two ranges in the tree today are Z-Image's measured ladder (8..16) and klein's measured range (4..8). The distinction is the kind of number each one is — a dial against a regime — and the law still admits a range of one value, because the range is the entry's and a distilled model may declare its regime as a point.

- **The second model has one runtime, by the operator's ruling of 2026-11-17.** The choice this section left open between FLUX.2 [klein]'s two runtimes was taken by removing one: the official scaled-FP8 checkpoint and its bfloat16 encoder were deleted on 2026-11-17, and with them the diffusers adapter, its entry, the 467-byte transformer config copy and `11,569 MiB` of assets. Measured through the service at 1024², seed 7, one prompt: wall **167.5 s against 22.4 s**, device peak **5745 against 4305 MiB**, whole-process-tree RSS **10280 against 6349 MiB**, removed path first. The removed path's device peak was its text encoder, not its renderer. `docs/reference/flux2-klein.md` keeps every one of those numbers, dated, because they are the evidence the removal rests on; the surviving runtime is `flux2klein_sd`, promoted on 2026-11-17 to `model/entry.yaml`, and Z-Image's entry moved unchanged to `model/entries/zimage.yaml`. The quality judgment behind the removal is recorded in that document; it rests on a blind comparison that was run once, on 2026-11-17, and that comparison is **unbalanced** — the shuffle put the same arm on the same side of all five sheets, so position and quality were confounded — and no document may quote it as a clean result. What the surviving runtime does not do well is recorded there too: it writes an illegible scrawl beside the `OPEN` sign its prompt did not ask for.

- **The two encoders are the same model, and the official bfloat16 copy stays anyway — the operator's ruling of 2026-11-17.** Measured: the three tokenizer files are byte-identical between `model/assets/qwen3/` and the FLUX.2 tree, `embed_tokens` and `norm` agree bit for bit, and all thirty-six layers correlate at 1.0000 against the bfloat16 state dict. Two facts came out of that comparison and neither is the reason for the ruling. First, Z-Image's int8 copy carries a **structurally pruned last layer** — 5770 of 9728 rows of `layers.35.mlp.up_proj` and 404 of 2560 of `layers.35.mlp.down_proj` hold a zero scale, the only two of 252 quantised tensors affected — and FLUX.2 never reads layer 35, because it conditions on layers 9, 18 and 27. Second, running that int8 copy on the card encodes in 2.5 s against 95.8 s on the CPU, at a cosine of 0.99998 per layer, and the RAM does not fall: `requantize` materialises the model on the host before moving it, measured at 5.05 GB today and 5.29 GB with a streaming state dict, and loading straight to the card exhausts it. The encoder is 4.41 GB and it has to live somewhere. The operator's ruling is that the official bfloat16 encoder is what this system encodes with: the reuse is faster and the parity is unjudged, and an unjudged swap is not worth 8.05 GB of disk and a coupling between two entries. What would reopen it is a blind comparison of the two encoders' stills, which has not been run. **Superseded on 2026-11-17, and the history kept:** the official bfloat16 encoder, the scaled-FP8 checkpoint and the diffusers adapter that used them were removed on 2026-11-17, so this ruling no longer describes a live capability and nothing in the tree encodes with that copy. The comparison it rests on survives as `tests/e2e/flux2-klein/encoder-parity.json`; the script that produced it is gone with the arm it compared against, and `docs/reference/flux2-klein.md` keeps the finding.

- **The served entry is chosen by alias — the operator's ruling of 2026-11-17, which closes D1–D3 and roadmap B4.** `start --model <id>` and `generate --model <id>` replace `--entry` as the mechanism. The alias is the entry's `id`; the resolver scans `model/entry.yaml` and `model/entries/*.yaml`, and an unknown alias is refused with the ids the tree declares, as `load_adapter` refuses an unknown adapter. The alias travels to the server process, which resolves it to a file; `--entry PATH` remains as a development shortcut and is documented as one. D1's answer is that entries live at `model/entry.yaml` and `model/entries/*.yaml`; D2's is the alias; D3's is that an entry the caller did not select is read only for its `id`, so a missing asset in it does not block another entry's boot and refuses only when that entry is selected. A request still names no model (section 4.1): `generate --model` is a check on what the server is serving, never a selector.

- **The deployment is declared separately from the model, and it may only tighten — landed 2026-11-17 as the fifth declared object, after the entry and the stage.** The two numbers that depend on the machine rather than on the model — the ceiling the card can render and the step range it tolerates — lived inside each entry, so moving the tree to another card meant editing every entry by hand. `host.yaml` at the tree root now declares the deployment: `id`, `vram_mib` (7857 here, the card's torch-usable memory), `offload` (whether the `ggml` child is handed `--offload-to-cpu`, which is the same 0.6 s and 3254 MiB the service has always paid), and optionally `limits` — a ceiling and a step range that may only narrow the served entry's. The rule is that **a host may tighten, never widen**: effective limits are the intersection, a host ceiling above the entry's measured one or a step range reaching outside the entry's is refused at boot with exit 3 naming the bound, and a cap below the entry's default box or a range excluding its default count is refused rather than silently reshaping a request. A missing `host.yaml` is not an error: the entry's own limits and `offload: true` apply, which is exactly what the system did before this unit. `coltman_images/host.py` owns the reader, the validation and the intersection; `entry.accepts`, `render._plan` and `WarmServer.boot` take the effective limits so the door enforces them where `limits` was always enforced; `flux2klein_sd` asks the host module for `offload` instead of hardcoding the flag. **This tree ships no `limits` block, and that is the finding of the unit**: both entries render their default box exactly at their measured ceiling (klein 1,327,104 px, Z-Image 921,600 px), so every cap that tightens either entry is below that entry's default box — refused by the conflict rule — and every cap above either ceiling widens a measurement — refused by the widening rule; no single cap fits both entries, because klein's default box is larger than Z-Image's whole measured ceiling. A host declaration with a ceiling would therefore decide the deployment down to one entry, and the matrix serves Z-Image while the promoted default is klein. Declaring one is legitimate the moment an entry's defaults sit under its ceiling, and guard 17 proves the machinery on exactly such an entry. What is **not** built, and is declared instead: the page's boxes still come from the entry's ceiling, so a host that tightened `max_pixels` below it would leave the page offering boxes the door refuses; wiring the page to the effective limits is a change to section 5.5 and guard 13 and is not made here.

- **`limits.max_pixels` at 1327104 is FLUX.2 [klein]'s measured ceiling, raised by the operator on 2026-11-17.** 1024×1024 was rendered through the service at 3822 MiB on the `ggml` path, and 1152² (1,327,104 px, 27 % above the previous 1048576) rendered in 13.4 s at a device peak of 4701 MiB, leaving 3156 MiB of the 7857 usable. That is the largest area measured, so it is the ceiling, and the promoted entry's defaults are that box — 1152×1152 — because the operator asked for the best measured box by default. The reading rests on **one prompt and one seed**, at four steps and on a square box: it is an indication and not a distribution, and the ceiling is an area, so it also admits wide shapes this ladder never rendered. Z-Image's entry keeps 921600: nothing above 1280×720 was measured for it, and a widening one entry's measurement supports is not evidence for another's.

- **The static `input_scale` in the FP8 checkpoint against the dynamic per-tensor scale was not compared, and the removal closed it.** The adapter carried the checkpoint's `input_scale` and its forward did not read it; every number in `docs/reference/flux2-klein.md` was produced with the scale measured from the activation. Which of the two is more accurate was never measured, and on 2026-11-17 the adapter, the checkpoint and the question were removed together. A later unit that brings a scaled-FP8 checkpoint back must measure it rather than assume it is free.
- The production stack is the project's own `.venv` (Python 3.14.8, torch 2.13.0+cu130, CUDA 13.0), created from pinned requirements. torchao's `quantize_` was measured on 2026-11-15 to traverse the model and leave every `Linear` in bfloat16 — on torchao 0.17.0 and 0.18.0, on CPU and CUDA, with and without explicit `PerRow` granularity, on a two-layer toy and on the real transformer (census 0 / 521 / 0 / 521) — even though `Float8DynamicActivationFloat8WeightConfig` is present in `_QUANTIZE_CONFIG_HANDLER`. Why is unmeasured, and the loader does not depend on it. `torch._scaled_mm` was measured to work on this card (sm_89) with per-row scales: `scale_a` float32 `(M,1)`, `scale_b` float32 `(1,N)`, agreeing with the exact dequantized product to 2.5e-3 against a 4.8e-2 spread against plain bfloat16.

- The render core was measured on 2026-11-15 with the whole transformer resident: the loader builds the FP8 weights directly from the checkpoint and the 5.86 GiB transformer sits on the card in 6057 MiB, with the weights never streamed. That is a different boundary from section 11's 4651 MiB, where the predecessor's memory manager streamed them; the rows are not comparable and the render time of this path is not yet measured. Two implementation facts worth keeping: `ZImageTransformer2DModel.from_config` materialises in float32 (24.6 GB), so the model is built on the meta device and materialised once; and widening an FP8 e4m3 weight to bfloat16 loses nothing, so the weight axis contributes no error — the ~2.7e-2 on a real layer is the dynamic quantisation of the activation, which FP8 requires.

- `model/z_image.json` carries `axes_lens: [1536, 512, 512]`; diffusers' own default for `ZImageTransformer2DModel` is `[1024, 512, 512]`. The vendor cards do not state the value, and the checkpoint cannot settle it — rope tables are not weights, so the strict state-dict load proves the other twelve fields and proves nothing about this one. The copy came from the predecessor's config directory, deleted on 2026-11-15, so the project now holds the only copy and its provenance is itself. It is kept because it is the permissive direction: a rope table longer than the positions actually used cannot corrupt a position, while a shorter one could. If a render at the top of the declared range ever misbehaves, this is the first line to check.

- **The reference image reaches the model, and what the model does with it is measured for one still and one LoRA.** The field is `image` (section 4.1), the count is the entry's `image.max`, and the adapter hands each path to the runtime as `-r`. Measured on 2026-11-17 on the promoted entry, 512×512 at four steps, one prompt and one seed: the request carrying a reference produced `sha256 829671e3…` against `d0a72ee3…` without it, and the still with the reference is **the vase the reference showed, with its background removed** — so the reference is klein's own conditioning and not a wrapper, and `background-remove` applied to it. **What is not measured, and no document may claim:** whether the other eight editing LoRAs in `docs/reference/lora-catalog.md` §5.2 behave as their cards describe — none of them has been rendered here; whether a **style** LoRA trained on text-to-image pairs behaves with a reference image or fights the instruction, which is the question the catalogue's §10 leaves open; whether a removed background would be an alpha channel, because this path writes RGB PNGs and the still renders the checkerboard; and how more than one reference behaves, since nothing here has rendered two at once. **The count is a declaration, not a measured limit:** ten is what the model's documentation says, the door refuses eleven, and whether ten references render coherently is untested.
- The declared stage is measured for cost and for seams, not for quality. No blind comparison exists between ×2 and ×4, nor between the stage and a plain Lanczos enlargement, so no document may claim one looks better. `model/assets/upscaler/realesrgan_x4plus.pth` is kept, and named here rather than left lying in the tree, as the other arm of that comparison; nothing reads it until a declaration names it.

- **The LoRA budget is a memory, and two questions the measurement does not answer are open.** Measured on 2026-11-17 (section 11): a 325 MB LoRA costs +313 MiB of device memory and +1.5 s, linear to eleven selections (7189 MiB and 23.6 s, 3443 MiB of it the LoRAs' own), from twelve the memory plateaus at ~7.6 GB while the wall time doubles (39.9 s at 12, 51.0 s at 16), and nothing runs out of memory up to 16. **The law encodes a budget and not a count**, because a count is only the shadow of the physical constraint: `lora_budget_mib` is 3200 on this deployment, reasoned from the render's 4815 MiB peak, the card's 7857 MiB and the ~7.6 GB plateau rather than measured as a cliff, and the door sums the requested LoRAs' file sizes against it. Those file sizes slightly under-count the device memory (`310 MiB` of file against `+313 MiB` of memory for the 325 MB LoRA), and the first selection carries a fixed cost of its own — measured at about 476 MiB in `docs/reference/lora-catalog.md` — so the budget is a rule about the files a request names, a shade permissive rather than optimistic, and not a promise about the peak. **What is not measured, and no document may claim it:** what several LoRAs do to each other in one still. The cost run duplicated a single LoRA by hardlink, so it measured the price of N *selections* and not the interaction of N *styles*; this tree's own stills applied one and three, in `tests/e2e/loras/`, and no document here compares them for quality. Whether three LoRAs interfere — or whether the last one at weight 0.3 is still doing anything — is open. **And why the plateau exists is open too:** that the runtime stops growing and starts paying in time from twelve is observed, not explained, and the explanation is the vendor's to give. The response object (section 4.2) does not echo the selection: no field on the wire says which aliases rendered a still, and a caller that needs the record keeps its own request.

A step that disproves a line here amends this document in the same work unit and records why in `docs/changelog.md`. The law is falsifiable: an unamended contradiction is the defect, not the discovery.