# Roadmap

## Next step

**The second model now has one runtime, by the operator's ruling of 2026-11-17; what comes next is P10's blocker, not this.** FLUX.2 [klein] 4B was brought into the tree on 2026-11-16 through two runtimes — the official scaled-FP8 checkpoint on diffusers, the community Q4_K_M GGUF on a vendored `ggml` binary — and measured through the service. On 2026-11-17 the operator removed the diffusers runtime and its assets, and the measurements behind the removal are the ones that matter here: whole, the two runtimes cost **167.5 s against 22.4 s** of wall, **5745 against 4305 MiB** of device peak and **10280 against 6349 MiB** of whole-process-tree RSS, removed path first, and the removed path's peak was its text encoder rather than its renderer. **11,569 MiB** were freed. One adapter and one entry remain (`flux2klein_sd`), and on 2026-11-17 the operator promoted it: **`model/entry.yaml` is FLUX.2 [klein]'s entry**, Z-Image's moved unchanged to `model/entries/zimage.yaml`, and the served entry is chosen by alias (`start --model <id>`). The entry now declares eight steps (range 4..8, measured at 10.8 / 14.1 / 16.9 s at 4 / 6 / 8, and eight repairs the four-step occlusion defect), a ceiling of 1152² (measured at 13.4 s, 4701 MiB) and 1152×1152 defaults. The blind comparison that informed the ruling is recorded as a limitation, not a clean result — the shuffle put the same arm on the same side of all five sheets — and `docs/reference/flux2-klein.md` carries the numbers, the three verified defects of the removed path and the one defect of the survivor.

Behind that, **P10 — the second adapter, DreamShaper XL — cannot start: B3 is open.** P9 closed on 2026-11-16. `start --ui` serves a page from the same process and the same queue: the page produced this project's own baseline bytes — `a lighthouse at dusk`, seed 7, 1280×720, `sha256 ff3b84a0…` — two submissions fired **through the page** serialise at **1.997** (first status within 0.1 s of each click), the screen states SD or HD with the base the stage started from, the census and the three timings, and guard 13 holds the page to the seam. A `--ui` boot writes no `https://` line at all. The suite is green — `Ran 17 tests in 822.983 s`, `OK`.

What stands between here and P10 is not code. B3 is the checkpoint plus its sidecars, and the three answers its row lists — the variant, the regime the entry declares, and D2 alone. The operator's order of 2026-11-16 stands: build the UI first and test a new model through it once it works. The UI now works.

No phase may start before the previous one has an **observed** exit: a command whose output is the proof. A document is not an exit criterion.

## Blockers

A blocker is a prerequisite that lives outside a phase and stops it at its first
step. They go **first, in this order**, and a phase whose blockers are open does
not start: P9 cannot be built while B1 and B2 are open, P10 cannot be built while
B3 is open, and U3 waited on B4 until it cleared on 2026-11-17. Clearing a blocker is
finished when its exit criterion is an observed command, the same rule the phases
follow.

| # | Blocker | Blocks | What it needs | Exit criterion |
| --- | --- | --- | --- | --- |
| **B1** | **The submission seam — cleared 2026-11-16.** `WarmServer.submit(request)` owns validation, the plan, the enqueue and the wait, returns the section 4.2 object, and refuses with `InvalidRequest` / `ServerError` / `RenderFailed`; the handler only parses and maps. Declared in protocol section 9 rule 8 (one producer). Proof: `sha256 0065c34a…` for `a lighthouse at dusk`, seed 7, 512×512, identical to the pre-extraction baseline, and the suite green at sixteen methods. | P9 | An extraction, not a design — the validation, the plan, the enqueue and the wait move behind one callable on `WarmServer`. | `POST /generate` calls `submit()`; the suite is green; the recorded baseline is byte-identical (`sha256 0065c34a…`, `a lighthouse at dusk`, seed 7, 512×512). |
| **B2** | **The dependency — cleared 2026-11-16.** `gradio` 6.32.0 into `.venv` and `requirements.txt`: twenty new packages on a closure of fifty, `fastapi`, `starlette` and `uvicorn` among them, and **nothing already pinned moved** — torch, diffusers, transformers, numpy, pydantic and httpx are exactly what they were. The venv and `requirements.txt` agree pin for pin at 89, with torch outside the file because it comes from the cu130 index. | P9 | — | Observed: `import gradio` answers 6.32.0 under `.venv/bin/python`, `requirements.txt` pins it, the API still serves from `http.server`, the suite is green at sixteen methods, and `docs/context.md`'s sentence was rewritten in the same work unit. |
| **B3** | **The second model's weights and the sidecars the single file does not carry.** The checkpoint is not in `model/assets/` and not on this machine. The single file does carry the UNet, both CLIP encoders and the VAE — but **no configs and no tokenizers**, and diffusers resolves those from `stabilityai/stable-diffusion-xl-base-1.0` on the Hub when they are not supplied, which protocol section 2 refuses. So the blocker is 6,939,220,250 bytes of checkpoint **plus ~3.2 MB of declared sidecars**: `model_index.json`, `unet/config.json`, `vae/config.json`, the scheduler config, and both tokenizer directories. | P10 | A variant chosen by the operator, then a download of the file and its sidecars from the same pinned commit. | The checkpoint and its sidecars in `model/assets/`, digests recorded and verified against the downloaded bytes, and the format read well enough to say what the adapter must own — a census through that adapter is **P10's** exit, not this one. |
| **B4** | **D1–D3 — cleared 2026-11-17.** The three operator decisions were answered together: **D1** entries live at `model/entry.yaml` (the promoted one) and `model/entries/*.yaml`; **D2** the served entry is chosen by alias — `start --model <id>`, resolving the entry's own `id` across those files — and `--entry PATH` remains as a development shortcut; **D3** an entry the caller did not select is read only for its `id`, so a missing asset in it does not block another entry's boot and refuses only when that entry is selected. The mechanism is declared in protocol sections 5.1, 6.1 and 12, and the CLI refuses an unknown alias with the ids the tree declares. | U3 | — | Observed: `start --model flux2-klein-4b-gguf-q4` and `start --model z-image-turbo-fp8` each boot their entry, `start --model nonexistent` exits 3 listing both ids, and `generate --model` refuses a server serving another entry by naming it. |

### Deferred behind P9 — the operator's order of 2026-11-16

B3, P10 and U3 waited for P9. The ruling: **build the UI first, and test a new model through it when it works.**
Nothing about the UI's construction depended on them — P9 needed B1 and B2, both cleared — so this was an ordering
decision and not a dependency. **P9 closed on 2026-11-16, so the deferral is discharged**: what waits now waits only on
B3 for P10 and on B4 for U3, and the UI is the place the second model will be tried. The survey behind B3 is recorded here
so the work resumes without repeating it.

The three usable single-file checkpoints are the same 6,939,220,250 bytes with identical headers. The digests below are
the Hub's LFS oids, which are the files' `sha256`; they are **pins to verify against the downloaded bytes**, not declared
assets, and nothing here is adopted until an entry declares it.

| Variant | Revision | File | `sha256` to verify |
| --- | --- | --- | --- |
| `Lykon/dreamshaper-xl-v2-turbo` | `f70ad5bce436c640d23fc02cd0a6ccc787280b6e` | `DreamShaperXL_Turbo_v2.safetensors` | `4726d3bab1876f5c23734c871c47901fde305115e15fbfa3f33354ac45b11c67` |
| `Lykon/dreamshaper-xl-lightning` | `561086c22aba3925b1e8803a73857f061635c7c3` | `DreamShaperXL_Lightning.safetensors` | `fdbe56354b8f876b736f24d3ad867ecd4140c019f57642ec8ddd878088d44f64` |
| `Lykon/dreamshaper-xl-turbo` | `402d2e0210f3d6ea01d91a4485869f31be633dca` | `DreamShaperXL_Turbo_dpmppSdeKarras_half_pruned_6.safetensors` | `676f0d60c8e860146d5e8a0d802599cadd04e7cadf85c283f189f41f01c9e359` |

Each repo also carries an SFW variant at the same size; the sidecars sit in the same commit, so no further research is
needed before a download.

**What resuming needs, in this order:**

1. **The variant**, one line — which of the three, and SFW or general.
2. **The regime the entry declares** — `guidance` and `steps`. Every candidate's card says `guidance_scale=2` and 4–6
   steps, against Z-Image's `0.0` and `12` (the promoted entry runs `1.0` and `8`). Choosing 2 makes CFG active, which
   gives section 4.1's "there is no negative prompt" the qualifier it will then need in the same work unit.
3. **The entry, served by alias** — `start --model <id>`, declared on 2026-11-17 when B4 cleared. Nothing waits on U3:
   a second model is served by its `id`, and serving it is a choice made at `start`, not at submission.
4. **B3 then P10**, as their rows declare.

## Phases

| Phase | Scope | Exit criterion | Status |
| --- | --- | --- | --- |
| **P1** | The project and its law: these documents, the reference material and the upstream cards. | The documents exist, cite only their own sources, and every code artifact is marked declared. | done, 2026-11-15 |
| **P2** | The render core: `model/entry.yaml` (resolved by name, all model values inside it), the `z_image.json` copy with its digest, the loader module with the activation-scale floor and the root-tensor remap, the live census. | One cold render callable from a Python call writes one still and prints `239 / 282 / 0 / 521`. No server, no port, no CLI. | done, 2026-11-15 |
| **P3** | The declared upscale stage: its own declaration in `model/upscaler.yaml`, its own weights, the tiled pass, and the request field that permits it. It applies to every entry, so it does not live in one. | A request above the render ceiling is refused without the permission and served with it; the response declares the stage and the base size it started from; the census is still the render's. | done, 2026-11-15 |
| **P4** | The server process: warm-up, `run/server.json`, single-flight queue, `GET /health`, `POST /shutdown`, `POST /generate`, and the CLI's `start`/`stop`. `/generate` lands here rather than in P5 because a queue with no producer cannot be tested, and single-flight cannot be proven without two concurrent requests. | `start` returns after warm-up; `/health` answers warm; a second `start` exits 0 and reports the running server; `stop` releases the card and removes the state file; two concurrent requests both succeed and never run two models. | done, 2026-11-15 |
| **P5** | `coltman-images generate` as the CLI client of the API, and the parity proof. | One prompt through the CLI writes the still (default folder or the requested path) and prints its path; a direct POST for the same seed produces the same bytes. | done, 2026-11-15 |
| **P6** | The guards of protocol section 10 as they stood at the close of the phase (guard 12 landed in P8), at protocol section 10's thresholds. | The suite runs under the production interpreter; every guard passes or reports its failure as a failure. | done, 2026-11-15 |
| **P7** | The rename and the first commit: the project stops being named after its first adapter (`coltman-images-service`), and version control stops being a debt. | The suite is green under the new name, a still is byte-identical to the pre-rename one, and `git log` shows a first commit with no history invented before it. | done, 2026-11-15 |
| **P8** | One instance, one card: the `flock` mutex on `run/server.lock`, taken before any model work, plus the `/proc` scan that catches a server started outside the CLI. The old boot order made the port useless as a guard — load, warm up, then bind meant a second process exhausted the card before it could ever reach the bind. | Guard 12 proves three things: a deleted state file does not allow a second process, a direct `python -m coltman_images.server` is refused and names the holder's pid, and exactly one server process exists after each attempt. | done, 2026-11-15 |
| **P9** | The web UI, inside this project: `start --ui` serves a page from the same process and the same queue. Gradio is the first rendering of it, behind a seam so that what is on screen can be replaced without touching what the system does. The operator ruled that the UI belongs here rather than in a second repository: a system that needs another project to show itself is not independent. | A page renders a still through the queue; two concurrent submissions serialise; the screen states SD or HD, the base the stage started from, the census and the three timings; guard 13 proves the UI never renders outside the queue. | done, 2026-11-16 |
| **P10** | The second adapter: DreamShaper XL — a different family, a different checkpoint format, and no shared code beyond the contract. Its single-file checkpoint carries the UNet, both CLIP text encoders and the VAE — so no *separate* encoder download — but not the configs or tokenizers, and the checkpoint itself is not in this tree and is not on this machine (blocker B3). Measured on this card: the UNet is 4897 MiB, smaller than the 6057 MiB transformer this system already runs, so it fits; but loading the file the way every card shows it — `from_single_file(...).to("cuda")` — peaks at 6616 MiB of weights and **OOMs in the decode**, so the adapter must stage the parts the way `zimage` already stages its two models. | The same core serves it with one adapter module and one entry, and no change to `server.py`, `render.py`, `entry.py`, or the surface the law declares. | planned |
| **P11** | The step range as a declared contract: `limits.steps` in the entry, so a request outside the measured range is refused at the door instead of rendering outside it. The ladder behind the range is measured and recorded. | A request outside the declared range is refused at validation; `docs/reference/steps-ladder.md` and protocol section 12 carry the measurement and the ruling. | done, 2026-11-15 |
| **P12** | External clients. This phase lives outside this project: the surface is declared, and a client adapts to it. The first-party UI is not one of them — it is P9, and it lives here. | Nothing here. | outside |

## P2 in order

1. `model/z_image.json` — done: the 473-byte transformer config is copied in and its `sha256` (`06d49d1a…c06af8`) is pinned in the entry.
2. `model/entry.yaml` — done: every field of protocol section 6.1 (`request_fields`, `expected_census`), with every asset path relative to the project root and the assets in `model/assets/`.
3. `coltman_images/entry.py` — done: resolves and validates the entry, refuses an unknown field, a missing field, a missing asset, a digest mismatch, a field outside the closed vocabulary and an incoherent census, and answers `accepts()` for a request before any GPU work.
4. The loader — done: `coltman_images/fp8.py` and `coltman_images/loader.py` build the FP8 weights straight from the checkpoint's `qdata` and `_weight_scale` (bit-identical, with no bfloat16 copy), floor the dynamic activation scale at `1e-12` themselves, remap the two `unsloth_root::` tensors, and count 239 / 282 / 0 / 521. The load takes 0.07 s and the transformer fits on the card in 6057 MiB.
5. Guard 4 as a callable first, a test later — done: `assert_census` refuses a wrong census, a model with no Float8 weights, and an unexpected dtype.
6. One cold render — done: 11.0 s at 512×512 and 43.5 s at 1280×720, a 908 KB PNG, the census out, and the same seed gives byte-identical files across separate processes.

## P3 in order

1. The weights — done: `realesrgan_x2plus.pth` (67 MB, sha256 `49fafd45…`) copied in; `realesrgan_x4plus.pth` kept as the comparison arm.
2. `model/upscaler.yaml` — done: its own declaration, ×2, separate from the model entry because the stage serves both models.
3. `coltman_images/upscale.py` — done: RRDBNet in pure torch, `scale` as a constructor argument, both files strict-clean at 702 tensors, tiled at 256 with 32 px of context and a worst seam of 0.0029 over 9 tiles.
4. Wired into `render.py` — done: `width` and `height` are the delivered file, the base is derived under the ceiling, and the response declares the chain.
5. Measured — done: 4.6 s of stage on top of a 43.4 s render, deterministic across runs, and refusals land at the door for both missing permission and the 3,686,400 px cap.

## P8 in order

1. `flock` on `run/server.lock` — **in code**: taken at the top of the server's entry point, before the entry is resolved and long before a weight is loaded; held for the process's life, so the kernel drops it on `kill -9` and a stale lock cannot exist.
2. The `/proc` scan — **in code**: a process counts as this server only when its interpreter is Python *and* `coltman_images.server` is one of its own argument tokens. Matching the text anywhere on a command line made the shell that ran the check look like a server.
3. The CLI pre-check — **in code**: `start` asks the mutex before spawning. Held and answering → report it, exit 0. Held and silent → say so, exit 4. Nothing is spawned while the card is owned.
4. The guard — **done**: `test_0850_guard12_one_instance`, numbered so it runs before the lifecycle guard that stops the server. It deletes the state file, proves `start` reports instead of spawning and names the pid, launches `python -m coltman_images.server` on another port and proves exit 4 before any weight loads, then restores the state file the server only writes at boot.
5. The law — **done**: section 6 declares the mutex and why the boot order made the port useless as a guard; section 10 carries guard 12; exit code 4 covers "another instance already owns the card".
6. The GPU-free half — **done and observed**: the direct second server printed `instance: another server already owns this card (pid 520734)` and exited 4 in under a second, on a card that was busy.

## P9 in order

The UI is built. Its shape was fixed by three facts — a request costs ~46 s, the queue is single-flight, and a browser
cannot read a filesystem path — and the eight steps below are all in code, with the numbers this work unit measured.

1. **The dependency, declared (B2).** **Done.** `gradio` 6.32.0 into `.venv` and `requirements.txt` — twenty new packages
   on a closure of fifty, `fastapi` and `uvicorn` among them — and **nothing already pinned moved**. The API stays stdlib
   **by decision**: it is three endpoints and a queue, and the page brings its own server beside it.
2. **The submission seam (B1).** **Done.** `WarmServer.submit(request) -> response` owns validation, the plan, the enqueue
   and the wait. `POST /generate` calls it, the page calls it, and nothing else does — one producer (section 9 rule 8).
3. **`coltman_images/ui.py`.** **Done, and it is four things and nothing else**: `request_from_form` (pure, no I/O),
   `render` (one line into the seam), `generate` (a **generator**: the submission runs in a worker thread and a status
   string is yielded every 0.5 s until the response object arrives), and `build` (the page). The page is two equal columns
   — prompt, seed, the SD/HD switch, an **aspect** choice of five shapes (`16:9`, `1:1`, `4:3`, `3:4`, `9:16`), a
   **steps** slider whose range and initial position are the entry's `limits.steps` and `steps`, and the button on the
   left; the status line, the still and its details on the right. Every size is computed from the entry's ceiling and the
   stage's factor — nothing is carried in the page. The module imports gradio and nothing model-bearing, and gradio is
   imported inside the server's `--ui` branch and never at module scope — measured: `import coltman_images.server`
   leaves `gradio` out of `sys.modules`.
4. **The honest copy.** **Done, and both constraints survived.** SD is `upscale: null` and HD is an `upscale` object that
   names `from`; the census is rendered key by key exactly as the response declares it; `render_s`, `load_s` and
   `duration_s` are three separate lines; and the server's queue depth is on screen while a request waits — measured with
   two submissions at once, the waiting one naming `queue depth 1` for its whole wait. The census keys are not written into
   the page, and neither is a size: guard 13 parses `ui.py` and refuses 1280, 720, 2560, 1440 and 921600 as literals —
   folded, so `640 * 2` and `"1280x720"` are caught too. HD is derived from the entry's ceiling and aspect rather than
   from `defaults x factor`, which only clears the ceiling while the defaults sit at it — measured HD: 2560×1440 delivered
   from a 1280×720 render.
5. **`start --ui [--ui-port 7860]`.** **Done.** A flag on `start`, never a fourth verb; it travels to the server process as
   `--ui`/`--ui-port` exactly as `--idle-timeout` does; `start` echoes `ui http://127.0.0.1:7860` on its success line; a
   differing request on a running server is reported and ignored; `--ui-port` without `--ui`, or equal to the API's port,
   is exit 2; and gradio absent under `--ui` is exit 3 before the mutex and before any weight.
6. **Guard 13.** **Done and green.** Structural: no model import, no entry size, no attribute of the warm server beyond
   `submit`, `depth`, `entry` and `declaration`, and the positive control that the module does call `submit()` — with the
   same scan finding ten forbidden imports in the Z-Image adapter, so it can find something. Unit: the switch maps to the
   entry's own ceiling and aspect, as a property and on an entry whose defaults do not sit at that ceiling. Behavioural:
   the page answers `200 text/html` on its own port, two submissions fired **through the page** serialise at **1.997**
   (separator 1.5) with both reporting their first status within 0.1 s, and `stop` takes the page down. The shared
   fixture still starts its server **without** `--ui`, so the matrix proves the API needs nothing from gradio.
7. **The law.** **Done:** section 1 gains the page as a surface, section 3 the module, section 5.5 the subsection, section 6
   the flag, the two ports, the page's cache under `run/` and its telemetry off, section 7 the two options, section 10
   guard 13 and the counts.
8. **The README.** **Done:** a "Use the browser" section beside the CLI and the curl examples.

Three things were found by running it rather than reasoned about. **Gradio serialises event handlers by default**, so a
second page submission waited inside gradio, *before reaching the seam* — the page was a queue of its own and the depth
line could never see it; the page's concurrency limit is now unlimited and the server's queue is the only one (the pre-fix
transcript was not kept, so no figure is claimed for it). **Gradio serves a still by copying it into a cache of its own**,
which was landing in `/tmp`; `GRADIO_TEMP_DIR` now points at `run/ui/`, assigned by the server rather than defaulted, and
the cache is not pruned. And **gradio telephoned home on every mount** — `HEAD https://huggingface.co/api/telemetry/…`
and `GET https://api.gradio.app/pkg-version` — which section 2 refuses outright; analytics are off in the page and in the
environment, and a `--ui` boot now writes no `https://` line at all. The operator-level run is in `tests/e2e/p9-ui/`.

## The entry-generalization brief

Three units, written from a read of the code and tracked here so they are not lost between phases. The brief is the operator's; this is its placement.

| Unit | What | Roadmap | Status |
| --- | --- | --- | --- |
| **U1** | A neutral entry schema: the law validates the envelope and the shape, the adapter owns the model's names | prerequisite of P10 | **done, 2026-11-15**, guard 14, `d2e9149` |
| **U2** | `steps` as a request field, with `limits.steps` bounding it | P11 | **done, 2026-11-15**, guard 15, `aa9b2ba` |
| **U3** | Select a model per request and swap on demand | the promise in §6.1 | **closed, 2026-11-17** — by the operator's ruling, and not as swap-on-demand: the served entry is chosen by alias at `start` (`--model <id>`), and a request names no model (protocol section 4.1) |
| **U4** | The request learns to carry an image: `image`, a list of paths, bounded by the entry's `image.max`; `-r` in `flux2klein_sd`; the page's image control | the nine editing LoRAs and klein's own reference conditioning | **done, 2026-11-17**, guard 19, matrix green |

U3 needed three operator decisions before any code: where entries live, how the served entry is chosen, and what happens to a non-default entry whose assets are missing. B4 answered all three on 2026-11-17: entries live at `model/entry.yaml` and `model/entries/*.yaml`; the served entry is chosen by its `id` with `start --model`, with `--entry PATH` kept as a development shortcut; and an entry the caller did not select is read only for its `id`, so its missing asset refuses only when it is selected. Per-request selection and swap-on-demand were **not** built, and are not owed: the alias is a boot-time choice, and the card is single, so one model is served at a time.

U1 also found a coupling the brief did not know about: `server.py` formatted its warm-up log line from Z-Image's census keys, so `start` would have failed on a foreign census *after* loading. Fixed in the same unit, and guard 14c now holds the core to the rule the law states.

## U4 — the request learns to carry an image (2026-11-17)

**What it is.** The request's closed vocabulary gains `image`: a list of absolute
paths, the same shape as `out` — the caller names a file and the system invents no
transport. The door refuses a path that is not a file, naming it, and a count above
what the entry declares, with both numbers. The entry declares the capability as
`image: {max: N}` — klein's ten references, Z-Image's none — and the adapter carries
each path to its runtime as `-r`, once per file, in the caller's order. The
response echoes the paths the still was conditioned on; the CLI carries
`--image PATH`, repeatable; the page carries `gr.Image(type="filepath")` as an
input, sends its path only when a file is set, and hides the control on an entry
that declares no reference. Guard 19 proves the two refusals and one still that
differs from the same request without its reference.

**Why it exists.** Measured and recorded in `docs/reference/lora-catalog.md`: nine
of klein's LoRAs are editing tools — `background-remove`, `tryon`, `outpaint`,
`object-remove`, `zoom`, `consistence-edit`, `sim-to-real`, `texture-albedo` and the
two seasonal ones — ten rows of §5.2 and nine ideas, because the pair is two
files for one — and each expects a source image, a mask, a highlighted region or a
clothing-agnostic body. The request carried no image, so they were listed as
unusable. **What U4 unlocks, and it is two capabilities and not one:** those
editing LoRAs, and klein's own reference conditioning — the model was trained for
multi-reference editing and the vendored runtime exposes `-r, --ref-image`
repeatably (`src/model/integrations/flux2.cpp` names the `flux2` reference preset,
with `pass_to_dit` on and `ref_index_mode=increase`), so the pictures are the
model's own input and not a wrapper this project invented.

**The law's part, and why it is written the way it is.** Section 2 says the system
reads exactly one thing, its own tree. Accepting a client's image is a **declared
exception**, exactly as `out` already is for writing — and two paths reach it, of
which only one is the exception. Through the page, gradio copies the upload into
its file cache, which the server points at `run/ui/` inside the tree, so nothing
leaves it and no exception is involved; measured, an upload posted to the page's
own endpoint landed at `run/ui/<hash>/reference-512.png`. Through the CLI or the
API, the path is the caller's own and may be anywhere, so it needs the exception,
declared by name in `CALLER_READ_EXEMPTIONS` and printed by guard 8 beside the
kernel exemption it already grants. An exemption stays a declared line and not a
silent pass.

**What is not measured.** Whether the other nine editing LoRAs behave as their cards
claim — none of them has been rendered here; `background-remove` has, once. Whether
a **style** LoRA trained on text-to-image pairs behaves with a reference image or
fights the instruction, which is `docs/reference/lora-catalog.md` §10's open
question — this unit must not claim either way. Whether a removed background would
be an alpha channel: this path writes RGB PNGs and the still renders the
checkerboard. And how more than one reference behaves: nothing here has rendered
two at once, and ten is the model's documented count rather than a measured limit.

## The next measurements — styles, hands, faces

Written down on 2026-11-17 so the next session starts where this one stopped. **None of it is
code**: the architecture is in place and what follows is measuring what it produces.

**Styles.** The operator keeps a style catalogue of seventeen frames, each a prompt with its own
revision history and verdicts, and they were written for Z-Image at `guidance 0.0` — the frames
themselves say so ("the negative stays empty: inert on this distilled family"). Rendering them
through **klein at 1152×1152 and eight steps** answers two questions at once: whether the
promoted model holds a register the operator has already tuned, and **which styles break**. The
second is the only honest trigger for seeking a LoRA. Sixteen or seventeen renders, about twenty
seconds each, and the evidence belongs in the test folder of the model under test.

**Hands and faces.** On the poker frame at 1152×1152 and eight steps. Four steps is what produced
the bartender's body through the counter, and eight what repaired it; hands and faces are the
same family of defect. If faces repeat — which is the documented weakness of small models in a
crowd — the next arm is four `sig_*` identities at 0.6 in one request, now that the budget admits
them: not to make faces prettier, but to stop them being the same face.

**What would justify a LoRA, and what would not.** A style that fails on *both* models, or faces
that repeat after resolution and steps. **Not** a style that already works: a style LoRA brings
its own basin and would fight a prompt this carefully built. And the catalogue's own finding
stands — for klein there is **no** hand or face LoRA with a verifiable licence (the only one found
declares none), while Z-Image's candidates are blocked on the half of the contract that has not
been built.

## The second model: FLUX.2 [klein], one runtime since 2026-11-17

The unit before P10 brought a second model into the tree and measured it through the service, without promoting
anything. It arrived with two runtimes; the operator removed one on 2026-11-17, and this section records both the
measurement and the removal.

- **Two adapters, two runtimes, one model — then one.** The diffusers adapter read the official scaled-FP8 checkpoint
  (309 keys mapped onto 169 parameters, 100 of them `FP8Linear`, the AdaLN halves swapped); `flux2klein_sd` runs the
  community Q4_K_M GGUF as a subprocess, holding `run/server.lock` for the child's whole life so the binary and the
  service can never both load a model. The diffusers adapter, its entry and its assets were removed on 2026-11-17.
  The surviving entry was promoted to `model/entry.yaml` on 2026-11-17.
- **Measured through the service, 1024², 4 steps, seed 7, the same prompt.** The diffusers path — removed: `render_s`
  7.054 s against `load_s` 77.947 s (the 8.05 GB encoder on the CPU), 5262 MiB of device memory at the 250 ms
  sampler's peak, 80.03 s to boot. The `ggml` path: `render_s` 15.508 s, `load_s` 0 because the child's load is not
  separable from its sampling, 3822 MiB, 11.32 s to boot. Both were deterministic per runtime; the same seed does
  **not** produce the same still across runtimes (PSNR 10.64 dB), so a cross-runtime comparison had to be judged at the
  same prompt, not differenced at one seed. Evidence: `tests/e2e/flux2-klein/`, numbers in
  `docs/reference/flux2-klein.md`.
- **Why one was removed.** Measured whole at the same request, the diffusers path cost **167.5 s** of wall against
  **22.4 s**, **5745 MiB** of device peak against **4305**, and **10280 MiB** of whole-process-tree RSS against
  **6349**; its device peak was the text encoder, not the renderer. The operator's blind read of the five sheets on
  2026-11-17 put three verified defects on that path — the bartender's body crossing the bar counter, a featureless
  black figure behind one player in the comic page, and the ice in the glass as an irregular lump rather than a cube.
  The removal freed **11,569 MiB**. The blind test is recorded as **unbalanced** — the shuffle put the same arm on the
  same side of all five sheets, so position and quality were confounded — and it is a limitation of the record, not a
  clean result. The survivor is not flawless either: it writes an illegible scrawl beside the `OPEN` sign its prompt
  did not ask for.
- **What the law gained, and what it lost.** Section 2 declares the vendored runtime as a copy inside the tree (it does
  not widen the kernel exemption); section 3 gains the rows; section 4.1 states that `limits.steps` is the **entry's**
  range and that a distilled model's step count is its training regime, not a dial; sections 5.1, 6.1, 6.3 and 7
  declare `--entry` and the adapters; section 11 carries the costs; section 12 carries the rulings and what remains
  open. On 2026-11-17 the law also lost the removed adapter's row, its entry, its transformer-config copy and the
  section 12 bullets that described a live capability it no longer has; those bullets are amended, not deleted, and
  mark what superseded them.
- **What it left to the operator.** It did not settle how the served entry is chosen (B4/D1–D3), and it did not promote the
  remaining entry: `model/entry.yaml` was still Z-Image's. Both followed on 2026-11-17 — the alias became the mechanism and
  klein became the promoted entry.

## The tests of 2026-11-17, in order

Six tests, each with an exit criterion that is an observed command rather than a document. T1 came first because it
was the only one that could decide the operator's question; T2 came second because it could have changed what T1 was
comparing.

**T1 — the blind A/B — ran on 2026-11-17, and it is recorded as unbalanced.** The same prompt through both entries,
1024×1024, 4 steps, five prompts: a neutral scene, one with legible text, one with hands and faces, one with a
reflective or transparent material, and one the operator picked. **The seed does not travel between the runtimes**
(PSNR 10.64 dB at one seed, different compositions), so stills were paired at the same prompt and never differenced at
one seed. The verdict is recorded in `docs/reference/flux2-klein.md` beside the three defects the operator verified in
the crops. **The shuffle did not do its job**: it put the same arm on the same side of all five sheets, so position and
quality are confounded and the result is a limitation of the record rather than a clean preference. The ten stills, the
five sheets and `key.json` are in `tests/e2e/flux2-klein/evidence/blind/`, and the run is not reproducible now that one
arm's assets are gone.

**T2 — the encoder, which is the whole cost difference and may not need to be.** The diffusers path pays 75–95 s of
`load_s` because the 8.05 GB Qwen3-4B encoder runs on the CPU. Two questions, in this order:

1. **Is it the same encoder Z-Image already has?** `model/assets/qwen3/` holds `Qwen3ForCausalLM` — hidden size 2560,
   36 layers, 32 heads with 8 KV heads, vocabulary 151936 — quantized to int8 at 4.41 GB, and FLUX.2's `text_encoder/`
   is `Qwen3ForCausalLM` at 4.02 B parameters with the same shape. If the weights are the same, the second 8 GB asset
   is redundant. Exit: a tensor-by-tensor comparison, and the count of what differs if anything does.
2. **If it fits, encode on the card.** The encoder loads *before* the transformer, so 4.41 GB has the card to itself at
   that moment. Measured, `zimage` already runs this encoder quantized. Exit: `load_s` for the same request with the
   encoder on the card against the 77.947 s recorded, and the peak that comes with it. If the encoder has to stay on the
   CPU, that is the finding and it is written as one.

**T2 ran on 2026-11-17 and closed in the negative — the original encoder stays.** They are the same model: tokenizers
byte-identical, `embed_tokens` and `norm` bit for bit, all 36 layers at a correlation of 1.0000. Z-Image's int8 copy
carries a pruned last layer (5770/9728 rows of `layers.35.mlp.up_proj`, 404/2560 of `down_proj`) that FLUX.2 never reads,
because it conditions on layers 9, 18 and 27. Reuse measured **2.5 s against 95.8 s**, but the embeddings deviate five to
ten per cent relative, and the RAM does not fall: 5.05 GB today, 5.29 GB with a lazy state dict, out of memory when the
shell goes to the card first. The encoder is 4.41 GB and has to live somewhere. The operator ruled on 2026-11-17 that the
official bfloat16 copy is what this system encodes with; the reasoning is in protocol section 12 and the numbers in
`docs/reference/flux2-klein.md`. What would reopen it is a blind comparison of the two encoders' stills, not run.
**That ruling is overtaken on 2026-11-17 by the removal of the path it governed**: the bfloat16 copy, the scaled-FP8
checkpoint and the diffusers adapter were deleted together, so the decision no longer has a subject. The comparison's
other arm no longer exists and the script that produced it is gone; `tests/e2e/flux2-klein/encoder-parity.json` is kept
as the record.

**T3 — the step count, measured instead of asserted.** The entry declared `{min: 4, max: 4}` on the vendor's word at the
time. The
`ggml` path accepts an arbitrary `--steps`, so it is the one that can be sampled outside the regime: 4, 6 and 8, same
prompt and seed, three stills each. The claim the law now makes — that moving a distilled model's step count samples
outside its training regime rather than trading detail for time — is either observed or it is withdrawn from section 4.1.
Exit: the stills, their timings, and the eye's reading of them.

**T3 ran on 2026-11-17 and closed in the positive, on one prompt and one seed.** At 1024×1024 the three stills cost
**10.8 s, 14.1 s and 16.9 s** — +31 % for six steps and +56 % for eight — and the device peak is **flat at 3865 MiB**
because the card holds one quantised pair whatever the sample count. **At four steps the bartender's body is merged into
the bar counter** — apron and hips on the near face, torso behind — and **at six and eight the occlusion is correct**,
with the most apron detail at eight; the operator confirmed it on `bartender-crop.png`. The same defect sits in the
removed path's stills, which were also rendered at four steps, so it is a four-step artefact and not evidence about
quantisation. The measurement does **not** support the law's sentence as written: moving the step count did not sample a
useless regime, it repaired a real defect at a measured price. **The ruling was taken on 2026-11-17: klein's entry admits
4..8 and defaults to 8, and the law's sentence was amended in the same work unit (protocol section 4.1).**

**T4 — the size ladder and where it stops.** 512², 768², 1024², 1152² and 1280×720 on the surviving path, each with its
peak at the 250 ms sampler and its `render_s`; the removed path's 1024² readings survive as history and cannot be swept
again. `max_pixels: 1048576` was the operator's measurement for 1024²; what the ceiling should be is whatever this sweep
shows the card can hold. Exit: the table, and either a confirmation of 1048576 or a corrected entry.

**T4 ran on 2026-11-17 and closed with the ceiling conservative.** 512² 5.3 s / 3221 MiB · 768² 7.5 / 3461 · 1024²
11.1 / 3865 · **1152² 13.4 s / 4701 MiB** at 1,327,104 px · 1280×720 10.3 / 3761. **1152² is 27 % above the declared
ceiling and fits**, with **3156 MiB** of the card's 7857 usable still free, and the operator read the ladder's contact
sheet as the best distribution of figures at the table. The entry was **not** corrected in that unit: `max_pixels` is a
declaration and raising it was an operator ruling. **That ruling was taken on 2026-11-17: the ceiling is 1327104 and the
promoted entry defaults to 1152×1152.** The boundary stands: the 1152² row is one prompt, one seed, one square box at
four steps, and the ceiling is an area, so it also admits wide shapes this ladder never rendered.

**T5 — the lock under real contention.** The `ggml` adapter holds `run/server.lock` for the child's life, but it has only
been proven against a running server. Try the other directions: a server boot while a bare `sd-cli` holds the card, two
`generate` calls aimed at the `ggml` entry at once, and a `stop` arriving mid-render. Exit: each attempt either served or
refused with the holder's pid, and never two models on the card.

**T5 ran on 2026-11-17 and closed with one direction unguarded.** Run through the CLI by
`tests/e2e/flux2-klein/contention.py`, evidence `evidence/contention/contention.json`, one run per scenario. **Two
`generate` calls at once:** both `200`, `duration_s` **11.48 s and 23.148 s** — ratio **2.016**, one render behind the
other with no overlap — and `pgrep -c sd-cli`, sampled 188 times over 25.1 s, **never exceeded 1**. **`stop` mid-render:**
the child was on the card when `stop` was sent; `stop` exited 0 after **11.4 s** and the request answered `200` with its
still at `duration_s` 11.168 — the render completed rather than being cut — and afterwards there was no `sd-cli`, no
`run/server.json` and no held lock. **A fresh `start` against a bare `sd-cli`:** the lock was **free** (the binary never
takes it), `start` exited 0 and warmed in 13.1 s, **two `sd-cli` processes coexisted** and the device reached **6854 MiB**
of 8188; both children succeeded. **The finding is that nothing prevents it**: the mutex is a contract between this
project's processes and not a property of the card, and only `--offload-to-cpu` kept the two inside it — the measured
resident child (7170 MiB) beside the 512² warm-up (3221 MiB) would need 10,391 MiB. Whether that should change is open.
The 30 s deadline itself was not reached: no request this entry admits outlasts it.

**T6 — the record after the tests.** Two runs of the remaining entry at the same seed, digest compared; the suite
re-run; the numbers in `docs/reference/flux2-klein.md` updated with what T1–T5 measured. T6 promoted nothing: the
promotion was its own unit, with `model/entry.yaml` moved deliberately and the Z-Image baseline still
the reference — and it followed on the same date, recorded below.

**T6 ran on 2026-11-17 and closed.** Three requests of the poker prompt, 1024², seed 7, four steps, through the
service returned `sha256 f15222b23879973d…` byte for byte; the lighthouse request of 2026-11-16 reproduced as
`482d2843418d5d6a…` on 2026-11-17 through a server started on another day. `docs/reference/flux2-klein.md` carries T3,
T4, the sampler sweep and the flow shift with their boundaries, and this section carried the two rulings the tests left
open. The suite was green — `Ran 17 tests in 749.665 s`, `OK` — and that unit promoted nothing; the promotion followed on
the same date, below.

**Two rulings the tests left open, taken by the operator on 2026-11-17.** Both were recorded with their measurement so the decision was a reading and not a guess:

1. **`limits.steps` admits 8 — taken.** T3 measured +56 % of the four-step wall (16.9 s against 10.8 s) and a repaired occlusion at six and eight. klein's entry now declares `{min: 4, max: 8}` with `steps: 8`, bounded above by the largest count measured.
2. **`max_pixels` is raised — taken.** T4 measured 1,327,104 px at 4701 MiB with 3156 MiB still free, 27 % above the declared ceiling. The ceiling is now `1327104`, and the promoted entry defaults to that box, 1152×1152. The reading rests on one prompt and one seed.

**The promotion and the selection ruling followed on the same date.** `model/entry.yaml` is FLUX.2 [klein]'s entry; Z-Image's moved unchanged to `model/entries/zimage.yaml`. The served entry is chosen by alias — `start --model <id>` — which answers B4's three decisions and closes U3, as the blocker's row and U3's row record.

## The measurement that is not a guard

The guards are automatable and block. One question does **not** fit a guard, because it needs a judgment: which step count is worth its time. It is a **measurement protocol**, not a pass/fail test, and it lives in `tests/e2e/steps-ladder/`:

- a prompt built to break the model — countable fingers, six buttons, a watch dial, legible text, five cards, liquid being poured, glass reflections, skin and fabric at 200 % — because a flattering prompt measures nothing;
- five seeds, nine step values from 4 to 24: forty-five stills, their timings, and SSIM between consecutive values per seed;
- the error count is scored **from the stills**, by the operator or by a blind judge. A script produces images and numbers, never a verdict. **The obligation is closed**: the operator's own eye read of the contact sheets, recorded in `docs/reference/steps-ladder.md` under "What the eye saw", is the measurement. The eight-category error count was never produced and is not owed, and no document may claim that it exists.

Status: complete. All forty-five stills exist in `tests/e2e/steps-ladder/evidence/stills/`, `ssim.json` carries all five seeds across all eight pairs, and `timings.json` all forty-five entries. The ladder was interrupted once by a GPU collision and resumed from its own timing cache rather than re-rendering what it already had.

The operator's ruling is recorded in protocol section 12: **twelve steps show more detail; eight trade detail for speed and carry visibly more errors.** The ladder behind that ruling is complete, and the ends it looked for are the ones §12 names: twelve to settle, sixteen as the ceiling.

What the ladder measured per seed — the timing variance, the SSIM per seed, and the divergence that grows with the step count — is analysed in `docs/reference/steps-fidelity.md`. It is evidence, and it establishes no quality verdict: SSIM measures how much the image changes, not whether it is better.

The second half of the original question — whether FP8 invents more than INT8 — is **decided**: the operator ran the A/B and discarded the INT8 model on 2026-11-16, so the system has one arm and no fallback to promote. The blind adjudication the ruling rests on is recorded in `docs/reference/zimage-fp8-vs-int8.md`; it is evidence, and the measurement did not change when the decision did.

## Debt schedule

### `[DEBT] no-version-control` — closed 2026-11-15

Deferred because the operator's decision was open. Closed when the operator ordered version control: the repository exists, `git init` ran in the project root, and the first commit carries the state as it stood when the debt closed. No history was invented before it, and the ignore file keeps the weights, the venv, the run state and the test evidence out of the repository.

### `[DEBT] no-idle-timeout` — closed 2026-11-16

The server never self-terminated, so a forgotten server kept a process and its port indefinitely — and, measured on 2026-11-15, about 165 MiB: 770 MiB with the server idle against 605 without it. It did **not** hold the card; the GPU is free between requests. Justified because auto-stop changes the meaning of "warm" and the cost of the next request.

- Target spec: an `--idle-timeout` option that releases the process and the port after a declared idle period. There is no GPU to release.
- Steps: the boot cost is already measured — 15.1 s, of which 11.0 s is the discarded warm-up — so declare the option against that number.
- Closed by: `start --idle-timeout SECONDS`, declared in protocol sections 5.1, 5.4, 6 and 7, with the default unchanged — absent the option the server still never self-terminates, so nothing moves for an operator who does not ask for it. The floor is that measured 15.1 s, refused at the door with exit 2 before any work, because a server that idles for less than it takes to start is worse than no server. **Idle means no request in flight and none queued**, and the period counts from the moment the server *becomes* idle: an earlier draft counted it from the moment a request was accepted, and the first end-to-end run retired the server 0.05 s after a 45 s render instead of 16 s after it — the render's own duration had eaten the period. Guard 16 proves the three halves: a period below the floor is refused and starts nothing; a 28.366 s render against a 16 s period answers 200 with its still rather than being cut; and the server then retires on its own through the path `stop` uses, leaving no port, no state file and no process — port silent, `run/server.json` removed, process gone, the reason in its own log. The option is idempotent as `--port` is: a differing period on a running server is reported on stderr and ignored. Evidence in `tests/e2e/idle-timeout/`.

### `[DEBT] server-mirrors-render-sequencing` — closed 2026-11-15

`coltman_images/server.py` repeated about forty lines of
`coltman_images/render.py`'s ordering —
encode, denoise, decode — because `_encode` built its own tokenizer and `render`
accepted no warm VAE. The arithmetic was not duplicated, only the sequencing.

- Target spec: `render` and `_encode` accept the warm pieces, and the server calls them instead of restating them.
- Steps: give `_encode` a `tokenizer=` argument and `render` a `tokenizer=`/`vae=` argument; delete the mirror; re-run the P4 acceptance transcript, which is the proof the refactor changed nothing.
- Closed by the adapter cut: `coltman_images/adapter.py` is the contract and registry,
  `coltman_images/adapters/zimage.py` holds the sequencing once, and `server.py`'s worker calls `render.render` with the adapter it built at boot. The mirror and its `_encode`/`_render` methods are deleted. Proof: the P4 acceptance run is green again (seven checks, exit 0) and the seed-7 1280×720 still from `POST /generate` is byte-identical to the pre-cut file, `sha256 ff3b84a0…dbe5c4`; `render.py` fell from 519 to 317 lines and `server.py` from 786 to 644.

## Decisions that are not phases

Both decisions that were open are closed. The FP8-against-INT8 quality question was ruled on 2026-11-16: the A/B was run to the end, the INT8 model was discarded and Z-Image has one arm. `steps` was adopted by U2 as a request field bounded by `limits.steps` — 8..16 on Z-Image's entry, 4..8 on the promoted one. The decisions that remain open live in `docs/protocol.md` section 12. **What the tree holds today:** two entries — `model/entry.yaml` (FLUX.2 [klein], the promoted one, `limits.steps` 4..8) and MOSS-Image DMD int8's at `model/entries/moss.yaml` (4..16, default 8) — and `model/models.yaml` is the roster. Z-Image is `retired` in that roster with **no `entry` key**: its entry file and its weights were deleted on 2026-11-19, and `docs/reference/retired-models.md` carries the restore recipe. Either entry is served with `start --model <id>`; `--entry PATH` remains as the development shortcut. The second klein runtime — the official scaled-FP8 checkpoint on diffusers — was removed on 2026-11-17 with its assets. The base Z-Image variant is not a scheduled tier: it was never an entry, it was a different checkpoint with full CFG, negative prompting and 28–50 steps and a 12.31 GB BF16 transformer that does not fit this card, and the Z-Image line is retired. No request selects a model, and a change of model is still `stop` and `start`.
