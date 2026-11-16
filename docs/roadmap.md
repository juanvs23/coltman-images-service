# Roadmap

## Next step

**P9 — the web UI, inside this project.** P8 closed on 2026-11-15: `flock` on `run/server.lock` is taken before the entry is resolved, the `/proc` scan catches a server launched outside the CLI, and guard 12 proves that a deleted state file cannot buy a second instance. The suite is green.

The UI is declared in eight steps below. It is the first work in this project that is not a service primitive, and it is the first that adds a dependency tree — twenty packages on a closure of fifty, measured — to a venv that has been deliberately bare. **It cannot start until B1 and B2 are cleared**, and neither can P10 until B3 is.

No phase may start before the previous one has an **observed** exit: a command whose output is the proof. A document is not an exit criterion.

## Blockers

A blocker is a prerequisite that lives outside a phase and stops it at its first
step. They go **first, in this order**, and a phase whose blockers are open does
not start: P9 cannot be built while B1 and B2 are open, P10 cannot be built while
B3 is open, and U3 cannot be coded while B4 is open. Clearing a blocker is
finished when its exit criterion is an observed command, the same rule the phases
follow.

| # | Blocker | Blocks | What it needs | Exit criterion |
| --- | --- | --- | --- | --- |
| **B1** | **The submission seam — cleared 2026-11-16.** `WarmServer.submit(request)` owns validation, the plan, the enqueue and the wait, returns the section 4.2 object, and refuses with `InvalidRequest` / `ServerError` / `RenderFailed`; the handler only parses and maps. Declared in protocol section 9 rule 8 (one producer). Proof: `sha256 0065c34a…` for `a lighthouse at dusk`, seed 7, 512×512, identical to the pre-extraction baseline, and the suite green at sixteen methods. | P9 | An extraction, not a design — the validation, the plan, the enqueue and the wait move behind one callable on `WarmServer`. | `POST /generate` calls `submit()`; the suite is green; the recorded baseline is byte-identical (`sha256 0065c34a…`, `a lighthouse at dusk`, seed 7, 512×512). |
| **B2** | **The dependency — cleared 2026-11-16.** `gradio` 6.32.0 into `.venv` and `requirements.txt`: twenty new packages on a closure of fifty, `fastapi`, `starlette` and `uvicorn` among them, and **nothing already pinned moved** — torch, diffusers, transformers, numpy, pydantic and httpx are exactly what they were. The venv and `requirements.txt` agree pin for pin at 89, with torch outside the file because it comes from the cu130 index. | P9 | — | Observed: `import gradio` answers 6.32.0 under `.venv/bin/python`, `requirements.txt` pins it, the API still serves from `http.server`, the suite is green at sixteen methods, and `docs/context.md`'s sentence was rewritten in the same work unit. |
| **B3** | **The second model's weights and the sidecars the single file does not carry.** The checkpoint is not in `model/assets/` and not on this machine. The single file does carry the UNet, both CLIP encoders and the VAE — but **no configs and no tokenizers**, and diffusers resolves those from `stabilityai/stable-diffusion-xl-base-1.0` on the Hub when they are not supplied, which protocol section 2 refuses. So the blocker is 6,939,220,250 bytes of checkpoint **plus ~3.2 MB of declared sidecars**: `model_index.json`, `unet/config.json`, `vae/config.json`, the scheduler config, and both tokenizer directories. | P10 | A variant chosen by the operator, then a download of the file and its sidecars from the same pinned commit. | The checkpoint and its sidecars in `model/assets/`, digests recorded and verified against the downloaded bytes, and the format read well enough to say what the adapter must own — a census through that adapter is **P10's** exit, not this one. |
| **B4** | **D1–D3**, the three operator decisions: where entries live, how the served entry is chosen, and what a non-default entry with a missing asset does. | U3 | The operator's answers, one per line. | Three answers recorded in protocol section 12, and U3's row unblocked. |

### Deferred behind P9 — the operator's order of 2026-11-16

B3, P10 and U3 wait for P9. The ruling: **build the UI first, and test a new model through it when it works.** Nothing
about the UI's construction depends on them — P9 needs B1 and B2, both cleared — so this is an ordering decision and not
a dependency. The survey behind B3 is recorded here so the work resumes without repeating it.

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
   steps, against this system's `0.0` and `12`. Choosing 2 makes CFG active, which gives section 4.1's "there is no
   negative prompt" the qualifier it will then need in the same work unit.
3. **D2 alone**, to serve the new entry: `start --model <id>`. D1 (where entries live) and D3 (a non-default entry whose
   asset is missing) belong to U3, and **U3 can wait** — a second model can be *tested* through the UI without a
   per-request selector, because serving it is a choice made at `start`, not at submission.
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
| **P9** | The web UI, inside this project: `start --ui` serves a page from the same process and the same queue. Gradio is the first rendering of it, behind a seam so that what is on screen can be replaced without touching what the system does. The operator ruled that the UI belongs here rather than in a second repository: a system that needs another project to show itself is not independent. | A page renders a still through the queue; two concurrent submissions serialise; the screen states SD or HD, the base the stage started from, the census and the three timings; guard 13 proves the UI never renders outside the queue. | planned |
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

The UI is declared, not built. Its shape is fixed by three facts: a request costs 46 s, the queue is single-flight, and a browser cannot read a filesystem path.

1. **The dependency, declared (B2).** `gradio` into `.venv` and `requirements.txt` — twenty new packages on a closure of fifty, `fastapi` and `uvicorn` among them. That falsifies `context.md`'s "the venv has no fastapi, so the API uses `http.server`": the API stays stdlib **by decision**, and the UI brings its own server. The sentence is rewritten in the same work unit, not left to rot.
2. **The submission seam (B1).** One function on the warm server — `submit(request) -> response` — that `POST /generate` calls. It does **not** exist yet: the handler validates, plans, enqueues and waits inline, so this is an extraction and not a rewiring. The UI calls that seam and never the adapter. Without it the UI is a second renderer outside the queue, and two browser tabs are two models on one card.
3. **`coltman_images/ui.py`.** Gradio Blocks: prompt, seed, an SD/HD switch, progress, the still. Its presentation must be replaceable without touching the seam — a UI is allowed to be plain; it is not allowed to be load-bearing.
4. **The honest copy.** SD or HD stated; when the stage ran, the base it started from (`upscale.from`); the census; `render_s`, `load_s` and `duration_s` kept separate; and the queue depth while it waits, because a 46 s request behind another one must not look like a hang. Two constraints already hold today and must survive a second entry: **the census renders generically** — key and value exactly as the response declares them, never Z-Image's `float8`/`plain`/`other`/`total` written into the UI, because section 6.1 makes the adapter the owner of what a census key means and the next model has no FP8 at all (measured: 2516 tensors, every one F16); and **every size comes from the entry or the response** — `limits.max_pixels` and the defaults are per-entry, so the SD/HD switch must not carry 1280×720 as a constant.
5. **`start --ui [--ui-port 7860]`.** Three commands stay three: the UI is a flag on `start`, not a fourth verb.
6. **Guard 13.** Two concurrent UI submissions serialise, and the UI module imports no adapter — the same boundary guard 11 draws for the core.
7. **The law.** Section 1 gains the UI as a surface, section 5 a subsection, section 6 the flag, section 7 the option.
8. **The README.** A "use the browser" section beside the CLI and the curl examples.

## The entry-generalization brief

Three units, written from a read of the code and tracked here so they are not lost between phases. The brief is the operator's; this is its placement.

| Unit | What | Roadmap | Status |
| --- | --- | --- | --- |
| **U1** | A neutral entry schema: the law validates the envelope and the shape, the adapter owns the model's names | prerequisite of P10 | **done, 2026-11-15**, guard 14, `d2e9149` |
| **U2** | `steps` as a request field, with `limits.steps` bounding it | P11 | **done, 2026-11-15**, guard 15, `aa9b2ba` |
| **U3** | Select a model per request and swap on demand | the promise in §6.1 | **blocked** on D1–D3 below |

U3 needs three operator decisions before any code: where entries live (`model/entries/<id>.yaml`), how the served entry is chosen (`start --model <id>`), and what happens to a non-default entry whose assets are missing — the last one departing from §6.1's "an undeclared asset refuses at start", which is why it is asked rather than assumed.

U1 also found a coupling the brief did not know about: `server.py` formatted its warm-up log line from Z-Image's census keys, so `start` would have failed on a foreign census *after* loading. Fixed in the same unit, and guard 14c now holds the core to the rule the law states.

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

Both decisions that were open are closed. The FP8-against-INT8 quality question was ruled on 2026-11-16: the A/B was run to the end, the INT8 model was discarded and the system has one arm. `steps: 8` was adopted by U2 as a request field bounded by `limits.steps` at 8..16. The decisions that remain open live in `docs/protocol.md` section 12. A second entry is scheduled: the base Z-Image variant will be downloaded later and will serve the higher-quality tier, with its own entry file and its own swap cost — the time to unload, load and warm again. Until its weights exist, one entry serves the system and no request selects a model.
