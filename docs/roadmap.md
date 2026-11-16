# Roadmap

## Next step

**P8 — one instance, one card.** It is already half-built: the `flock` mutex and the `/proc` scan are in `coltman_images/server.py` and `bin/coltman-images`, and the mutex was proven by hand — a stub holding the lock makes `start` refuse and name the holder's pid. What is missing is the guard that keeps it true, and the law that records it.

Running beside it, and not a phase: **the steps ladder** (see *the measurement that is not a guard*). Thirty-five of forty-five stills exist; the rest are rendering.

No phase may start before the previous one has an **observed** exit: a command whose output is the proof. A document is not an exit criterion.

## Phases

| Phase | Scope | Exit criterion | Status |
| --- | --- | --- | --- |
| **P1** | The project and its law: these documents, the reference material and the upstream cards. | The documents exist, cite only their own sources, and every code artifact is marked declared. | done, 2026-11-15 |
| **P2** | The render core: `model/entry.yaml` (resolved by name, all model values inside it), the `z_image.json` copy with its digest, the loader module with the activation-scale floor and the root-tensor remap, the live census. | One cold render callable from a Python call writes one still and prints `239 / 282 / 0 / 521`. No server, no port, no CLI. | done, 2026-11-15 |
| **P3** | The declared upscale stage: its own declaration in `model/upscaler.yaml`, its own weights, the tiled pass, and the request field that permits it. It applies to every entry, so it does not live in one. | A request above the render ceiling is refused without the permission and served with it; the response declares the stage and the base size it started from; the census is still the render's. | done, 2026-11-15 |
| **P4** | The server process: warm-up, `run/server.json`, single-flight queue, `GET /health`, `POST /shutdown`, `POST /generate`, and the CLI's `start`/`stop`. `/generate` lands here rather than in P5 because a queue with no producer cannot be tested, and single-flight cannot be proven without two concurrent requests. | `start` returns after warm-up; `/health` answers warm; a second `start` exits 0 and reports the running server; `stop` releases the card and removes the state file; two concurrent requests both succeed and never run two models. | done, 2026-11-15 |
| **P5** | `coltman-images generate` as the CLI client of the API, and the parity proof. | One prompt through the CLI writes the still (default folder or the requested path) and prints its path; a direct POST for the same seed produces the same bytes. | done, 2026-11-15 |
| **P6** | The eleven guards of protocol section 10, at protocol section 10's thresholds. | The suite runs under the production interpreter; every guard passes or reports its failure as a failure. | done, 2026-11-15 |
| **P7** | The rename and the first commit: the project stops being named after its first adapter (`coltman-images-service`), and version control stops being a debt. | The suite is green under the new name, a still is byte-identical to the pre-rename one, and `git log` shows a first commit with no history invented before it. | done, 2026-11-15 |
| **P8** | One instance, one card: the `flock` mutex on `run/server.lock`, taken before any model work, plus the `/proc` scan that catches a server started outside the CLI. The old boot order made the port useless as a guard — load, warm up, then bind meant a second process exhausted the card before it could ever reach the bind. | Guard 12 proves three things: a deleted state file does not allow a second process, a direct `python -m coltman_images.server` is refused and names the holder's pid, and exactly one server process exists after each attempt. | current |
| **P9** | The web UI, inside this project: `start --ui` serves a page from the same process and the same queue. Gradio is the first rendering of it, behind a seam so that what is on screen can be replaced without touching what the system does. The operator ruled that the UI belongs here rather than in a second repository: a system that needs another project to show itself is not independent. | A page renders a still through the queue; two concurrent submissions serialise; the screen states SD or HD, the base the stage started from, the census and the three timings; guard 13 proves the UI never renders outside the queue. | planned |
| **P10** | The second adapter: DreamShaper XL — a different family, a different checkpoint format, and no shared code beyond the contract. Its single-file checkpoint carries its own text encoders, so it needs no download. | The same core serves it with one adapter module and one entry, and no change to `server.py`, `render.py`, `entry.py`, or the surface the law declares. | planned |
| **P11** | The step range as a declared contract: `limits.steps` in the entry, so a request outside the measured range is refused at the door instead of rendering outside it. The ladder behind the range is measured and recorded. | A request outside the declared range is refused at validation; `docs/reference/steps-ladder.md` and protocol section 12 carry the measurement and the ruling. | planned |
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
4. The guard — **missing**: three assertions, numbered so they run before the lifecycle guard that stops the server.
5. The law — **missing**: section 6 and section 10 must record the mutex and guard 12.
6. The GPU-free half — **provable now, on a busy card**: a stub holding the lock must make the server refuse *without loading anything*, which is the property that matters and the one that needs no render to check.

## P9 in order

The UI is declared, not built. Its shape is fixed by three facts: a request costs 46 s, the queue is single-flight, and a browser cannot read a filesystem path.

1. **The dependency, declared.** `gradio` into `.venv` and `requirements.txt` — 53 packages, with `fastapi` and `uvicorn` among them. That falsifies `context.md`'s "the venv has no fastapi, so the API uses `http.server`": the API stays stdlib **by decision**, and the UI brings its own server. The sentence is rewritten in the same work unit, not left to rot.
2. **The submission seam.** One function on the warm server — `submit(request) -> response` — is what `POST /generate` already calls. The UI calls that and never the adapter. Without this the UI is a second renderer outside the queue, and two browser tabs are two models on one card.
3. **`coltman_images/ui.py`.** Gradio Blocks: prompt, seed, an SD/HD switch, progress, the still. Its presentation must be replaceable without touching the seam — a UI is allowed to be plain; it is not allowed to be load-bearing.
4. **The honest copy.** SD or HD stated; when the stage ran, the base it started from (`upscale.from`); the census; `render_s`, `load_s` and `duration_s` kept separate; and the queue depth while it waits, because a 46 s request behind another one must not look like a hang.
5. **`start --ui [--ui-port 7860]`.** Three commands stay three: the UI is a flag on `start`, not a fourth verb.
6. **Guard 13.** Two concurrent UI submissions serialise, and the UI module imports no adapter — the same boundary guard 11 draws for the core.
7. **The law.** Section 1 gains the UI as a surface, section 5 a subsection, section 6 the flag, section 7 the option.
8. **The README.** A "use the browser" section beside the CLI and the curl examples.

## The measurement that is not a guard

The eleven guards are automatable and block. One question does **not** fit a guard, because it needs a judgment: which step count is worth its time. It is a **measurement protocol**, not a pass/fail test, and it lives in `tests/e2e/steps-ladder/`:

- a prompt built to break the model — countable fingers, six buttons, a watch dial, legible text, five cards, liquid being poured, glass reflections, skin and fabric at 200 % — because a flattering prompt measures nothing;
- five seeds, nine step values from 4 to 24: forty-five stills, their timings, and SSIM between consecutive values per seed;
- the error count is scored **from the stills**, by the operator or by a blind judge. A script produces images and numbers, never a verdict.

Status: thirty-five of forty-five stills exist; the ladder was interrupted once by a GPU collision and resumes from its own timing cache rather than re-rendering what it already has.

The operator's partial ruling is already recorded in protocol section 12: **twelve steps show more detail; eight trade detail for speed and carry visibly more errors.** The ladder's job is to find where those two ends actually are.

The second half of the original question — whether FP8 invents more than INT8 — is now **unmeasurable here**: the INT8 weights were deleted with the foreign store they lived in, so that comparison would begin with a download, and no document may claim its result in the meantime.

## Debt schedule

### `[DEBT] no-version-control` — closed 2026-11-15

Deferred because the operator's decision was open. Closed when the operator ordered version control: the repository exists, `git init` ran in the project root, and the first commit carries the state as it stood when the debt closed. No history was invented before it, and the ignore file keeps the weights, the venv, the run state and the test evidence out of the repository.

### `[DEBT] no-idle-timeout`

The server never self-terminates, so a forgotten server keeps a process and its port indefinitely — and, measured on 2026-11-15, about 165 MiB: 770 MiB with the server idle against 605 without it. It does **not** hold the card; the GPU is free between requests. Justified because auto-stop changes the meaning of "warm" and the cost of the next request.

- Target spec: an `--idle-timeout` option that releases the process and the port after a declared idle period. There is no GPU to release.
- Steps: the boot cost is already measured — 15.1 s, of which 11.0 s is the discarded warm-up — so declare the option against that number.

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

Open operator decisions live in `docs/protocol.md` section 12 and block no phase: the FP8-against-INT8 quality tension, and `steps: 8` measured but not adopted. A second entry is scheduled: the base Z-Image variant will be downloaded later and will serve the higher-quality tier, with its own entry file and its own swap cost — the time to unload, load and warm again. Until its weights exist, one entry serves the system and no request selects a model.
