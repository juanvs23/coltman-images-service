# zimage-fp8-speed — measure the FP8 speed levers and recommend a catalog change

## Objective

Measure the two production levers that can reduce FP8 image-generation time —
`steps` and `offload_profile` — through the real production render, then
recommend whether the image-model catalog should change.

The objective is **measurement and recommendation**, NOT a catalog change. The
catalog stays unchanged until the operator decides, because `steps` changes the
production output bytes and `offload_profile` changes the VRAM behaviour.

## Problem

The production FP8 path is slow enough to matter, and the catalog currently
pays for a regime that the model card does not claim as its distilled regime.
There is no measured, per-axis answer to either question:

1. Can another mmgp offload profile reduce the time or memory cost while
   preserving the production bytes?
2. What time and output does the model's distilled 8-step regime produce on
   this machine?

Treating both levers as one experiment would be a scientific error. They have
different contracts: an offload profile changes where weights live, while the
step count changes the sampling arithmetic.

## Why

The measured and documented facts that make the experiment necessary are:

- The official `Tongyi-MAI/Z-Image-Turbo` model card describes the distilled
  model for **8 NFEs** (8 DiT forwards), CFG 0, at 1024x1024, with sub-second
  inference on an enterprise H800 and a stated fit within 16 GB VRAM.
- The installed diffusers 0.40.0 `ZImagePipeline` defaults to
  `num_inference_steps=8`. In that version, N steps produce N transformer
  forwards; the scheduler still applies the model's static `shift: 3.0`.
- The production catalog entry `z-image-turbo-fp8` declares **`steps: 12`** —
  50 % more DiT forwards than the distilled count — and
  **`offload_profile: 4`**.
- mmgp profile 4 is `LowRAM_LowVRAM_Slow`: it keeps only
  `budgets["transformer"] = 1200` MiB of the transformer in VRAM and shuttles
  the rest CPU-to-GPU every step. Profiles 1 and 3 put the whole model in VRAM.
- The GPU is an RTX 4060 Laptop with 8188 MiB VRAM; the FP8 transformer
  checkpoint is 6.29 GB.
- The measured production path takes 78–82 s warm and 95–99 s cold end to end.
  The render alone takes 36.0–36.2 s at 12 steps (about 3.0 s per step), setup
  takes 9.6 s, and encoding takes 8.3–18.1 s.

No number is invented here. These are the facts the matrix must test against.

## Scope

### In

- Generalize the production proof's catalog-copy mechanism so a copy can carry
  arbitrary overrides of the `z-image-turbo-fp8` entry.
- Render one cell through the production path for the matrix of
  `(steps, offload_profile)` combinations.
- Measure wall time, peak VRAM, peak swap, output sha256, pixel delta against
  the pinned 12-step baseline, and loader census per combination.
- Judge the two axes independently and recommend a catalog change from the
  measured evidence.

### Out

- Changing `network/assets/catalogs/image_models.yaml`.
- Selecting a new production default before the operator decides.
- Re-implementing the production render or the loader census.
- Rendering additional cells by default; the matrix measures one cell.
- Changing the text encoder, the checkpoint, the guidance value, or the
  scheduler.
- Committing, pushing, or opening a pull request.

## Constraints

- The real catalog is read and copied, never written. Every copy lives under
  the experiment's gitignored `evidence/` directory.
- The production render has one owner:
  `tests/e2e/zimage-fp8-production/run_production.py::render`.
- A 12-step combo under an offload profile other than 4 must reproduce the
  pinned still byte for byte. A difference is a reported finding.
- An 8-step combo is expected to produce different bytes. Its pixel delta is
  measured and reported, not treated as a failure.
- A failed combo is a measurement: record its error and continue the matrix.
- Every successful combo must report the exact measured loader census
  `239/282/0/521`; a different census is a failure to report.
- The delegated implementation does not run the GPU matrix; the parent session
  owns that measurement.
- Non-documentary files stay under approximately 400 lines.
- Canonical artifacts are written in English. No AI attribution.

## Authorized scope

- `tests/e2e/zimage-fp8-production/run_production.py`
- `tests/e2e/zimage-fp8-speed/run_speed.py`
- `tests/e2e/zimage-fp8-speed/README.md`
- `odd/tasks/zimage-fp8-speed.md`

No other tracked file is authorized for modification.

## Acceptance criteria

- The real image-model catalog is unchanged.
- The default production path with no overrides keeps its existing behaviour
  and pinned proof.
- A catalog copy names its overrides deterministically, so distinct matrix rows
  cannot collide, and the helper refuses a target equal to the real catalog.
- The experiment renders through `run_production.render`; it does not duplicate
  the production render.
- Each matrix row reports wall time, idle and peak VRAM, idle and peak swap,
  sha256, pixel delta, and loader census, or its failure text.
- Every 12-step profile variant is byte-identical to the pinned baseline; any
  exception is a reported failure.
- Every 8-step row is marked as expected different bytes and reports its pixel
  divergence and measured time.
- `evidence/speed.json` contains the whole matrix and a per-axis verdict.
- The recommendation names the measured trade-off and leaves the catalog change
  to the operator's explicit decision.

## Checks

```sh
cd <the calling project>

ruff check tests/e2e/zimage-fp8-production/run_production.py
ruff check tests/e2e/zimage-fp8-speed/run_speed.py

python3 -m unittest discover -s tests -p "test_zimage_fp8_runtime.py" -v
python3 -m unittest discover -s tests -p "test_referenced_paths.py" -v
python3 -m unittest discover -s tests -p "test_file_budget.py" -v

git diff --check

python3 tests/e2e/zimage-fp8-speed/run_speed.py --dry-run
```

The GPU matrix is run separately by the parent session:

```sh
python3 tests/e2e/zimage-fp8-speed/run_speed.py
```

## Tasks

- [x] T1 — Generalize `run_production.py`'s catalog-copy mechanism to arbitrary
  `z-image-turbo-fp8` overrides, retain `catalog_with_interpreter` as a thin
  wrapper, refuse the real catalog as a target, and record the resolved entry
  plus applied overrides in the render payload.
- [x] T2 — Build the speed matrix experiment with the default
  `(12,4), (12,3), (12,2), (8,4), (8,3), (8,2)` order, subset selection,
  dry-run mode, per-row evidence folders, GPU/host sampling, pixel delta,
  census checks, failure continuation, and a per-axis verdict.
- [x] T3 — Document the experiment's contract in
  `tests/e2e/zimage-fp8-speed/README.md` and this ODD contract.
- [x] T4 — Run the GPU matrix in the parent session and record the complete
  evidence in `tests/e2e/zimage-fp8-speed/evidence/speed.json`.
- [x] T5 — Interpret the measured per-axis results and write the catalog
  recommendation without changing the catalog.
- [ ] T6 — If the operator approves a change, open a separate work unit for
  the catalog edit, its contract change, and its guard.

## Progress

- 2026-11-14 — T1–T3 implemented in the working tree. The production proof
  can now render through a catalog copy carrying sampling and offload
  overrides; the speed experiment owns the matrix, measurements, evidence and
  verdict; the experiment contract and this ODD document describe the two axes
  separately.
- 2026-11-14 — The delegated writer did not run the GPU matrix (the parent
  session owns that measurement).
- 2026-11-14 — **The matrix is measured (two passes, cell-01).** Pass 1 ran the
  matrix cold (its first row paid the 6.29 GB checkpoint read) and profile 3
  OOMed; pass 2 ran the same matrix warm and every row succeeded. Pass 2 is
  the stable state and the one the recommendation rests on. The interpretation
  is in *Verification evidence* below and the recommendation in *Next step*.
  The catalog was NOT changed: the decision is the operator's.
- 2026-11-15 — **Session paused by the operator** ("guarda todo, continuamos
  mañana"), with the machine shut down at the end. Nothing was left running
  and no file was deleted. The open decision is the one in *Next step*: open
  the BATCHING work unit (one process per video) first, or settle the stage's
  shape first (the `ceil(N/2)` stills contract against a 30–60 still video).
  The catalog is still UNCHANGED, the working tree is still the delivery (no
  commits, no push, no PR), and the 8-step stills still await the operator's
  visual verdict at
  `tests/e2e/zimage-fp8-speed/evidence/steps-8-profile-2/cell-0{1,2}-production.png`.
  **Resume protocol**: `mem_context`, then `mem_search` for
  `odd/zimage-fp8-speed` and `odd/zimage-fp8-production` in this project,
  then `mem_get_observation` on the task mirror (#2033) and on the product
  scale (#2036), then read this file, then reconcile with the working tree
  before touching anything.

## Verification evidence

- `ruff check tests/e2e/zimage-fp8-production/run_production.py
  tests/e2e/zimage-fp8-speed/run_speed.py` → **All checks passed!**
- `python3 -m unittest discover -s tests -p "test_zimage_fp8_runtime.py" -v` →
  **2 tests, OK**.
- `python3 -m unittest discover -s tests -p "test_referenced_paths.py" -v` →
  **2 tests, OK**.
- `python3 -m unittest discover -s tests -p "test_file_budget.py" -v` →
  **4 tests, OK**.
- `git diff --check` → **clean** (no output).
- `python3 -m unittest discover -s tests -v` → **520 tests, OK (0 skips)**, re-run
  after the recommendation was rewritten.
- `ruff check .` → **255 findings, all pre-existing** in files this work unit
  did not touch; `ruff check tests/e2e/zimage-fp8-speed/
  tests/e2e/zimage-fp8-production/` → **All checks passed!**.
- `python3 tests/e2e/zimage-fp8-speed/run_speed.py --dry-run` → **6 matrix rows
  materialized their catalog copies under `evidence/`; no render was started**.
- Catalog-resolution smoke check → all six rows resolved the requested
  `(steps, offload_profile)` from their copies; the real catalog path was not a
  copy target; the default catalog still resolves to `(12, 4)`.
- GPU matrix, **pass 2 (warm batch, cell-01)** — reported as an OBSERVATION of
  that batch, not as a verdict. The order of the batch is part of the
  measurement: the first row of a batch pays a cost the following rows do not,
  so the first row's number is not comparable with the rest.

  | steps | profile | wall_s | VRAM peak (MiB) | still sha256 | census |
  | ---: | ---: | ---: | ---: | --- | --- |
  | 12 | **4** (production today) | 76.909 | 6234 | `7a323918…` pinned | 239/282/0/521 |
  | 12 | 3 | 52.534 | 7824 | `7a323918…` pinned | 239/282/0/521 |
  | 12 | **2** | **57.486** | **5818** | `7a323918…` pinned | 239/282/0/521 |
  | 8 | 4 | 55.766 | 5818 | `52d60643…` (expected different) | 239/282/0/521 |
  | 8 | 3 | 46.618 | 7824 | `52d60643…` (expected different) | 239/282/0/521 |
  | 8 | **2** | **46.699** | **5818** | `52d60643…` (expected different) | 239/282/0/521 |

  - **The profile axis preserves the bytes**: every 12-step profile variant is
    **byte-identical** to the pinned baseline (max abs diff 0.0, 0 of
    2 764 800 elements differing), and the loader census stays exactly
    239/282/0/521 in every successful row — no silent BF16 degradation under a
    different placement. The profile changes WHERE the weights live, not the
    arithmetic.
  - **Profile 3 OOMed cold.** It succeeded in this warm batch (52.534 s, a
    7824 MiB peak = **4 % headroom** on an 8188 MiB card) and **failed in the
    cold pass** with `memory allocation failed with OOM on device 0` (free:
    98 MB / 56 MB / 133 MB at the first allocations). A configuration whose
    success depends on the page cache's warmth is not production-grade.
  - **8 steps is deterministic and materially different**: the same sha256
    `52d60643…` in every profile, with 2 532 115 of 2 764 800 pixels differing
    from the 12-step image (91.6 %), mean abs diff 8.23/255, max 206. Not a
    subtle refinement: it needs the operator's eye and a re-pinned evidence set.
- GPU matrix, **pass 1 (cold)**: the first row paid the cold checkpoint read
  (104.168 s for the baseline); profile 3 OOMed in both of its rows; the
  remaining rows ran warm (79.420 s / 47.693 s / 46.149 s). Evidence:
  `tests/e2e/zimage-fp8-speed/evidence/speed-pass1.json` and
  `speed-pass2.json` (gitignored).
- **Paired, interleaved measurement — the verdict on the profile axis.**
  Three rounds alternating `(12,4), (12,2)`, so every pair is measured in the
  same machine state (cell-01):

  | round | (12, profile 4) | (12, profile 2) |
  | ---: | ---: | ---: |
  | 1 | 58.081 s | 56.498 s |
  | 2 | 55.999 s | 56.189 s |
  | 3 | 56.531 s | 56.711 s |
  | **median** | **56.531 s** | **56.498 s** |

  **Difference: 0.033 s (0.06 %).** The profile axis is NOT a speed lever on
  this machine. The batch reading of "profile 2 is −25 %" was an order
  artefact: in that batch, profile 4 was the FIRST row and paid a cost the
  following rows did not.
- **cell-02 confirmation** (three rows, warm): `(12,4)` 57.334 s, `(12,2)`
  57.217 s — the same 0.117 s difference, the same bytes `21ebf781…`; `(8,2)`
  46.725 s with sha256 `6ff41b9e…` (1 059 947 pixels differing from the
  12-step still). The 8-step saving reproduces across cells: −10.5 s
  (cell-02) and −10.8 s (cell-01) with profile 2.
- **Instrumentation of one full render** (56.6 s, 2 s sampling):
  - **Disk**: 0.01 GiB read during the render (0.00 GiB/s). The disk is not a
    bottleneck.
  - **Swap**: 10 012 168 192 → 10 008 199 168 bytes used (flat, shrinking).
    **RAM**: MemAvailable 21.6 → 21.5 GiB. The swap is not a bottleneck.
  - **GPU**: utilisation 2 % for the first 18 s (text encoder + encode +
    transformer setup), 100 % from t=18 s to t=52 s (the 12 DiT forwards,
    **34 s → 2.83 s per step**), then 2 % for the last 4 s (write + census +
    close). SM clock 1 830–2 115 MHz of a 3 105 MHz maximum; temperature
    39–54 °C with no thermal throttle.
  - **Power**: the render draws **42–43 W** against `power.max_limit = 45 W`
    (`power.default_limit = 35 W`). The card is already at its power ceiling,
    so raising the limit would buy roughly 5 %, not the +35 % the clock
    deficit suggests.
- **Unreconciled observation**: the FP8 cut measured the production path at
  78–82 s warm and 95–99 s cold, while this experiment's render measures
  56.5 s for the same 12-step configuration. The two figures have different
  harness boundaries (full production path vs. one rendered cell through
  `run_production.render`) and the difference has NOT been decomposed. It is
  recorded here rather than explained away, because an unexplained 35 % gap
  is a fact the next work unit must reconcile before trusting either number
  as a baseline.
- **Warm-up decomposes into two different costs, and only one of them is
  large.** The controlled comparison in
  `tests/e2e/zimage-fp8-runtime-parity/` isolates the page-cache cost:
  with the cache evicted, the production runtime takes **99.1 s**; the same
  configuration with a warm cache takes **82.0 s** → **≈ 17 s**. The
  historical runtime shows the same gap (94.9 s cold vs 77.5 s warm →
  17.4 s), and both runtimes read the same checkpoint, so this is the
  machine's cost and not the runtime swap's. The GPU clock ramp is marginal:
  the SM clock idles at **1 470 MHz** and runs at **1 830–2 115 MHz** under
  load, and the ramp happens during the ~18 s setup phase, so the DiT
  forwards already start at full clock (≤ 2–3 s). **Within a warm batch there
  is no warm-up penalty at all**: the first row of the paired rounds measured
  58.081 s against 55.999 s and 56.531 s for the following ones, and
  cell-02's first row 57.334 s against 57.217 s — inside the noise, with the
  sign changing between configurations. The very first render of a session
  (104.168 s in the cold pass) pays ~27 s over the warm figure: ~17 s of that
  is the page cache and the remaining ~10 s is NOT isolated (a first CUDA
  context and kernel-module load are the likely candidates). It affects only
  the first render after boot.
  **The consequence for the recommendation: the cold cost is already
  amortised by the page cache — it is paid ONCE per cold machine state, not
  once per image. The cost that is NOT amortised is the ~18 s of per-image
  setup (interpreter + imports + text encoder + transformer load), which every
  image pays today and which the batching lever removes.**
  **The operator's operating model confirms this shape**: the machine is
  turned on, warmed up, left on during use and turned off at the end. The
  ~17 s cold read is therefore paid once per boot, outside the steady state,
  and nothing in the recommendation may be built on it. What repeats is the
  per-image process setup, and a warm MACHINE does not warm the PROCESS.

## Next step

**The catalog is unchanged. The decision is the operator's.** The
recommendation was rewritten after the paired measurement refuted its own
first candidate: the offload profile is NOT a speed lever here.

### The operator's ruling (2026-11-15) — the batch proposal is REJECTED

The operator rejected the "one sequential batch per video" proposal: *"algo
determinista y secuencial no es la mejor opción; el sistema debe permitir
cantidades irregulares en lugar de un patrón fijo; un sistema basado en
comandos y cableado con varias opciones es, si bien lo menos simple, la más
flexible"*. The MEASUREMENTS behind the rejected proposal stay true — 18 s of
per-image setup, 32 % of a 60-still render spent re-loading the same model —
but the SHAPE of the fix is now a command layer with selectable executors, not
a fixed batching rule.

**The repo is already a command-and-wiring system**, which is why the ruling
lands on existing ground rather than on a new architecture:

- `network/application/runtime/wiring.yaml` is "the ONLY declaration of what
  runs and in what order": each stage is DATA (`use_case`, `ports` injected at
  bind time, `artifact`, `waits_for`, `emits`), and `wiring.py` is its only
  reader. "Several options" is the house style: the ORDER lives in data, not
  in Python.
- The operator's operating model — on, warm, left on during use, off at the
  end — is ALREADY WIRED as four stages: `gpu_power_on` -> `gpu_warmup` ->
  `image` (which emits `image.done` AND `gpu.release`) -> `gpu_shutdown`.
- The gap is inside that ONE wired stage. `image`'s use case loops over the
  scenes and calls the image port once per still, so each call pays the ~18 s
  load. The fix is therefore not a new rule about how many stills a video
  has; it is (a) an explicit, IRREGULAR list of render COMMANDS as data, and
  (b) a set of wired EXECUTOR options that decide how those commands are
  fulfilled: one process per command, one process for the whole list, a
  resident worker across runs, parallel workers. The quantity is then data,
  and every executor is an option.

**The wiring consequence that must be settled in the design:** `montage`
waits_for `[image.done, narration.done]`, so the timeline exists AFTER the
images. The commands therefore CANNOT be declared by the montage — they must
come from upstream (the visual artifact or a dedicated commands stage), or the
wiring order must change. That is a contract decision, not a performance
decision.

### The operator's second ruling (2026-11-15) — the model system must stand ALONE

*"El modelo y su sistema debe poder utilizarse separado del sistema
<the calling project>."* The command layer and its executors are
therefore not an internal detail of the `image` stage: they are a **first-class
unit with its own surface**, and the pipeline is one of its clients, not its
owner.

The repo already has the two conventions this needs:

- **`network/tools/` is the outside layer** ("may import anything") and already
  carries standalone CLI surfaces (`network/tools/write_script.py`,
  `network/tools/fetch_source.py` — both with `argparse`/`__main__`). That is
  the house place for a program you can run by hand.
- **The adapter already emits a self-contained program.** `build_script()`
  (`network/adapters/zimage.py:231-239`) returns an encode script + a render
  script as one program for the runtime interpreter. The "model and its
  system" already exists in a runnable form; what it lacks is a vocabulary and
  a way to run it over a LIST.

The emerging shape, subject to the seam mapping:

- **Input**: a list of render commands (data), each with its prompt, seed,
  size, direction/style and output path. The quantity is whatever the list
  says — irregular by construction.
- **Options**: the executor (one process per command / one process for the
  whole list / a resident worker across runs / parallel workers), the model
  entry (FP8 / INT8), and the sampling regime.
- **Surface**: (a) a callable unit the pipeline's `image` stage binds to
  through its port, and (b) a CLI under `network/tools/` that takes a command
  file and renders it with no knowledge of the pipeline, the profile or the
  wiring. A separate cron, another project or a human with a JSON file can use
  it unchanged.
- **Output**: the stills plus the same receipt artifact the stage writes
  today (`images.json`), so the pipeline's contract does not fork.

**The open fork this ruling leaves** (the operator owns it): "usable
separately" can mean (a) an autonomous INTERFACE inside this repo — the
library + CLI above, with `network` as one client among several — or (b)
genuinely separate CODE, another package or repository, with this repo
consuming it. The repo's own law ("One package, `network`", enforced by
`tests/test_network_law.py`) argues for (a) now and makes (b) a later
extraction across the seam this design would create. Recommendation: design
and ship the seam in (a); (b) stays possible because the interface is already
a boundary.

### Rule 11 satisfied — the legacy already solved this, on the TTS side

`docs/porting-ledger.md:85` records the legacy's narration mechanic crossing
this repo, and `network/adapters/qwen3_tts_adapter.py:60-69` states its
status in full:

> `synthesize_many` + the batch lever (`tts_batch`, legacy :408-519): one warm
> subprocess amortising the model load across a phase's items — the legacy
> narration loop's mechanic; the narration use case landed driving the
> per-scene `synthesize` one call at a time — the BATCH form stays uncarried
> until its declared consumer asks for it (per-scene provenance is already the
> record the manifest makes).

That is the precedent, and it is the operator's own mechanic, not a new
architecture:

1. **One warm subprocess amortises the model load across a phase's items** —
   the exact cost the image stage pays 60 times today.
2. **The single-item call stays.** The port keeps `synthesize`; the batch form
   is ADDED (`synthesize_many`). Same shape the image port needs: `render`
   stays, `render_many` is added.
3. **The batch form only activates when its declared consumer asks for it** —
   a DECLARED lever read at bind time, never a hidden default. This is the
   repo's law ("behavioural levers live in YAML, not in Python") and it is
   what makes "several options" legal rather than a rewrite.
4. **Per-item provenance stays in the manifest** — the batch does not lose the
   record that makes each item auditable.

**Rule 11 is therefore satisfied by porting behaviour with its measurement**,
not by inventing a mechanism. The image side mirrors the TTS side: a
`render_many` on the port, a declared lever that selects the executor, the
per-still record kept in `images.json`.

### The seams, mapped (2026-11-15)

The surface was mapped file by file. The load-bearing facts:

| Seam | Where | Fact |
|---|---|---|
| Command list enters | `network/application/image/use_case.py:71-75` + the runtime's artifact convention | The runtime injects a stage's artifact as `<artifact>_path` (`network/application/runtime/use_case_node.py:217-220`), so a `commands` artifact would arrive automatically IF a stage declared one. |
| Execution crosses the port | `network/ports/image.py:45-47` | `ImagePort.render(request) -> str` is single-item. A list MUST cross the port: `render_many(commands)` is the addition. |
| The executor option's home | `network/application/runtime/wiring.yaml` + `network/application/runtime/graph.py:85-90` | **The wiring cannot choose an adapter class.** It declares use case + PORT NAMES; the concrete adapter is bound at the composition root (`tests/e2e/first-network-video/run.py:80-88`). So "several options" must be a DATA lever the adapter reads (the catalog, as `preload`/`steps`/`offload_profile` already are), with the adapter implementing every executor behind one port. |
| The count's source | `network/application/writer/visual.schema.yaml:56-69`, `use_case.py:92,125-137,142-143` | The visual artifact is ONE row per scene, and the pair rule derives `ceil(N/2)`. An irregular count cannot come from today's visual artifact without changing its schema and its guard. It CANNOT come from `montage` (it waits for `image.done` → cycle). |
| What the manifest must keep | `network/application/assembly/direct.py:107-123`, `_io.py:61-80` | Assembly joins scenes to stills. An irregular command list must still cover every scene, so each command declares the scene it serves. |
| The pair law | `docs/contracts.md:657-660` (L3) | "one image per pair of scenes … Hardcoded by design (legacy `media_assembler.py:471-479` …), guarded by tests." L3 must become "the command list decides; the pair rule is ONE producer of commands" — and `tests/test_image_use_case.py::TestPairRule` (lines 166-203) must KEEP guarding the pair producer. |
| The resident executor's cost | `network/adapters/gpu_manager.py:77-88,121-128`; `wiring.yaml:136-141` | `power_on()` clears the lease, `shutdown()` refuses while leased, and `gpu_shutdown` waits for `gpu.release`. A child process holding the GPU escapes the parent's lease: the log would record a release while the card stays occupied (E8). Resident state is also not an on-disk artifact (E3/E5). **The resident executor is a contract change of a different order.** |

Dead ends ruled out by the map: `visual.json` cannot be reused as a command
list (schema + `test_visual_pass`); "one process per command" is not today's
behaviour (it is TWO subprocesses per command); `build_script()` is not used
by `render()`; parallel workers can exceed the physical card while one
logical lease is held; the timeout is per subprocess, so a list needs its own
aggregate timeout.

### The operator's third correction (2026-11-15) — the SYSTEM first, then the adapter

*"No sería mejor iniciar por el sistema del ZIMAGE, prepararlo y luego generar
todo el adaptador… estás iniciando por el adaptador es como hacer el enchufe y
dejar para luego el toma corriente."* The criticism is correct, and the map
proves it: **the proposed unit 1 started from the adapter side.**

**There is no "Z-Image system" today to prepare.** It is split across three
homes, and no single one owns it:

| Piece | Home today | Consequence |
|---|---|---|
| model (6.29 GB) + runtime venv | `<model store>/` (outside the repo) | the model's own environment already lives apart |
| loader protocol (mmgp↔torchao), census | repo: `network/adapters/zimage_fp8.py` | the worker reaches BACK into the repo for it |
| render recipe | repo: `network/adapters/zimage.py`, as **generated strings** | there is no module to import, only text rebuilt per request |
| vocabulary | repo: `network/ports/image.py` (`StillRequest`) | the system's own language is defined by the pipeline's port |
| executors | implicit: two `subprocess.run` per image | no named option, no list form, no timeout of its own |
| CLI / entry point | **none** | there is nothing to run by hand |
| guards | repo: `tests/` | they guard the pieces, not the system |

The worker script proves the seam is backwards: the generated script does
`sys.path.insert(0, REPO_ROOT)` and then `from network.adapters import
zimage_fp8` (`network/adapters/zimage.py:155-162`) — **the model system's
worker imports the pipeline's repository to do its job.**

**The corrected order** (the operator owns it; this is the consequence):

1. **PREPARE THE Z-IMAGE SYSTEM** — a real package with a real module (not
   generated strings), its own command vocabulary, its own worker protocol,
   its own executors, its own CLI and its own tests. Runnable alone with no
   knowledge of the pipeline, the profile or the wiring: a command file in,
   stills and a receipt out. **Nothing of the pipeline is required to use it.**
2. **THEN GENERATE THE ADAPTER** — the repo's `ImagePort` implementation
   becomes a thin client of the system: resolve the catalog entry, write the
   command file, call the system, read the receipt, return the path. The repo
   stops owning model internals.
3. **THEN the pipeline integration** — the port's `render_many`, the pair rule
   as ONE producer of commands, the declared executor lever in the wiring.
4. **THEN the irregular authoring** — the visual pass deciding how many stills
   a video carries.

The order is not only tidier, it is safer: the port's shape should be DERIVED
from a working system's vocabulary, not invented before the system exists.
That is the plug/socket argument, and it is right.

**The fork this leaves** (the operator owns it): where the prepared system
LIVES.

- **(A) Next to the model** — `<model store>/system/`.
  Model + runtime + system become one deployable; the worker imports its own
  home (no `sys.path` hack back into the repo); the repo's adapter is a pure
  CLI client; the catalog pins the system's version and path, exactly as it
  already pins the interpreter. Cost: the system is OUTSIDE git, so its
  delivery is the filesystem, and the loader's guards (`tests/
  test_fp8_offload_protocol.py`, `test_zimage_fp8_loader.py`,
  `zimage_fp8_oracle.py`, `test_zimage_fp8_adapter.py`) must travel with it
  or become contract guards from this side.
- **(B) Inside the repo** — `network/adapters/zimage/` as a package. Git
  remains the delivery, the laws and guards apply unchanged, the FP8 cut's
  guards do not move, and the worker imports it the way it imports the loader
  today. Cost: the system is inside the network package, so "separate from
  the network system" is logical rather than physical, and the pipeline's
  contracts can leak into it unless the boundary is policed.

The repository already references an external, repo-unguarded thing — the
runtime interpreter, declared by absolute path in the catalog — so (A) has
precedent; but (A) breaks the standing rule "the working tree IS the
delivery" for the system's own code, which is the operator's call and not the
parent's.

### Proposed first work unit — "the command layer" (SUPERSEDED by the operator's third correction)

**This unit as written started from the adapter side and is superseded.** Its
items 1–4 (port, catalog lever, adapter, use case) now belong to steps 2–3 of
the corrected order above. What survives from it, verbatim:
- the port shape: `render` STAYS, `render_many` is ADDED, the single-item call
  is never removed (the legacy's `synthesize` / `synthesize_many` precedent);
- the declared lever: the executor is a DATA lever the adapter reads, because
  the wiring CANNOT choose an adapter class (it declares port NAMES; the
  concrete adapter is bound at the composition root);
- the legacy precedent and its filter: the list form only activates when its
  declared consumer asks for it;
- the pair rule stays as ONE producer of commands, with `TestPairRule` still
  guarding it, and L3's contract change still ships complete;
- the standalone CLI — which under the corrected order is not "item 5" but
  **the system's own entry point, and therefore the first thing built**;
- the exclusions: the resident executor (changes E8's lease and E3/E5's
  artifact state), parallel workers (the card cannot hold two models), the
  visual pass authoring irregular quantities (L3's semantics and the visual
  schema — a later unit), and the 8-step change (waits on the operator's
  visual verdict).

Under the corrected order the first work unit is therefore **"prepare the
Z-Image system"**: the package, the vocabulary, the worker protocol, the
executors, the CLI and the system's own tests — prepared and exercised ALONE,
with the adapter generated only afterwards.

**That unit is now OPENED as `odd/tasks/zimage-fp8-system.md`** (the operator's
ruling of 2026-11-15: *"vamos a legalizar el sistema Z-image, coloca en el todo
el protocolo para el desarrollo"*). Its first deliverable is PAPER, not code:
the development protocol (which landed in the SYSTEM's own project, at
`<predecessor>/docs/protocol.md`) and the legalizing
clauses inside `docs/contracts.md` contract 3, with every guard that cannot
exist yet registered as a violation rather than hidden. The system's CODE is
the unit after that, built against the protocol.

### Original unit-1 detail, kept for the record

Scope, small enough to review and complete enough to be real:

1. **`network/ports/image.py`** — a `RenderCommand` shape (an id, the scene it
   serves, and the existing `StillRequest` fields) and `ImagePort.render_many`
   beside the existing `render`. The single-item call stays.
2. **`network/assets/catalogs/image_models.yaml`** — a DECLARED lever that
   selects the executor, read at bind time, with the legacy's filter: the
   list form only activates when its declared consumer asks for it. Executors
   shipped in this unit: `per_command` (today's behaviour, byte-identical)
   and `warm_process` (one warm subprocess for the whole list — the legacy's
   proven mechanic, the one that amortises the ~18 s).
3. **`network/adapters/zimage.py`** — both executors behind the one port, with
   an aggregate timeout for the list and the same per-still provenance.
4. **`network/application/image/use_case.py`** — the pair rule becomes ONE
   producer of commands (unchanged behaviour, unchanged guard); the stage
   accepts a command list as input.
5. **`network/tools/` — the standalone CLI.** A command file (JSON/YAML) in,
   stills + the receipt out, with no knowledge of the pipeline, the profile or
   the wiring. **Irregular quantities work here from the first commit.**
6. **L3's contract change, shipped complete**: the contract text, the catalog
   lever, the extension procedure and a guard that fails when the semantics
   drift — while `TestPairRule` keeps guarding the pair producer.
7. **Same work unit**: `docs/contracts.md`, `docs/context.md`,
   `docs/roadmap.md`, `docs/changelog.md`.

Explicitly OUT of this unit, each for a named reason: the **resident**
executor (changes E8's lease and E3/E5's artifact state), **parallel**
workers (the card cannot hold two models), the **visual pass authoring
irregular quantities** (that is L3's semantics and the visual artifact's
schema — the next unit), and the **8-step** change (it waits on the operator's
visual verdict).

Checks: the canonical runner `python3 -m unittest discover -s tests -v`,
`ruff check .` at the pre-existing baseline (255 findings, none in the
touched files), `git diff --check`, plus a GPU proof that the list form
renders the same bytes as today's per-command path and that the warm-process
executor pays the load once.

### Measured and rejected:

- **`offload_profile: 4 → 2`** — refuted by a paired, interleaved measurement
  (3 rounds, cell-01): profile 4 median **56.531 s**, profile 2 median
  **56.498 s**, a difference of **0.033 s (0.06 %)**. The earlier "−25 %" was
  the first render of a batch paying a cost the following renders did not.
  **The catalog keeps `offload_profile: 4`.**
- **`offload_profile: 4 → 3`** — rejected: it OOMed in the cold pass and
  peaked at 7824 MiB on an 8188 MiB card (4 % headroom) for at most −7 %.
- **More GPU power** — refuted: the render draws **42-43 W** against a 45 W
  maximum, so the card is already at its power ceiling. Raising the limit
  would buy ~5 %, not the +35 % the clock deficit suggested.
- **Disk or swap as the bottleneck** — refuted: the render read **0.01 GiB**
  from disk, the swap stayed flat, and 21.5 GiB of RAM stayed available.

**Measured and still open:**

1. **`steps: 12 → 8`** — the only lever that is both measured and stable:
   **−10.5 s / −10.8 s** (≈ −18 %), reproduced on two cells. The model is
   distilled for 8 NFEs. It changes **91.6 % of the pixels**
   (2 532 115 of 2 764 800 differ; mean 8.23/255, max 206), so it needs the
   operator's eye on
   `tests/e2e/zimage-fp8-speed/evidence/steps-8-profile-2/cell-0{1,2}-production.png`
   and, if approved, a re-measured and re-pinned evidence set in its own work
   unit. The INT8 fallback should move with it or the two entries stop being
   comparable.
2. **The structural cost, and the operator's ruling on its shape.** Each
   still spawns TWO fresh subprocesses (`network/adapters/zimage.py` runs the
   encode script, then the render script), so every image pays an interpreter
   start, a text-encoder load and a transformer setup from scratch. The
   measured split of a 56.6 s image: **~18 s before the first DiT forward**
   (text encoder + encode + transformer setup), **34 s of forwards**
   (12 × 2.83 s), ~4 s of writing and closing. **At the operator's real scale
   this is the shape of the stage, not an optimisation**: the operator ruled
   (2026-11-14) that Z-Image is an IMAGE model and that a video carries
   **at least 30–60 stills** (60 ≈ a 15-minute video, one still every ~15 s).
   At the measured steady state (56.5 s per image), one 60-image video costs
   **56.5 min**, of which **18 min (32 %) is re-loading the same model 60
   times**; a 30-image video costs 28.3 min with 9 min of re-loading. The
   catalog's `preload` lever is NOT a seam for this: it declares modules
   imported before the pipeline class, not a resident process.

   | 60-image video | setup | forwards | wall |
   | --- | ---: | ---: | ---: |
   | today (one process per image) | 60 × 18 s = 18 min | 60 × 34 s = 34 min | **56.5 min** |
   | one process for the whole list | 18 s once | 34 min | **~42 min** (−26 %) |
   | + 8 steps | 18 s once | 23 min | **~31 min** (−45 %) |
   | + 8 steps + 1024×576 | 18 s once | 14.5 min | **~23 min** (−60 %) |

   The rows are estimates, and the uncertainty is named: the split between the
   text encoder's LOAD and its per-prompt ENCODE is not measured. What IS
   measured is the whole per-image load block (~18 s) and the transformer
   setup alone (9.6 s, from the bench). The estimate charges ~15 s saved per
   image, inside that range. **These rows justify the COMMAND LAYER; they do
   not choose an executor.** Which executor is wired is the operator's call,
   and the quantity of commands is data, not a rule.
3. **Resolution** (1280×720, fixed in `network/application/image/use_case.py`
   lines 108-109, not in the catalog): the DiT cost scales with pixels, so
   1024×576 is ≈ −36 % of the compute. A product decision — it changes the
   channel's output format.
4. **`torch.compile` and a Flash Attention backend** — both recommended by the
   official model card, neither measured here. `flash-attn` is not among the
   77 pins, so it would need a download and a build against torch 2.13+cu130.
5. **A RESIDENT worker across videos** — the operator's operating model (the
   machine is turned on, warmed, left on during use and turned off at the end)
   makes the strongest version of this lever obvious: a process that keeps the
   model loaded between videos would remove the load from the FIRST image too,
   not just amortise it inside one video. It is NOT recommended in this unit:
   it gives the long-lived process ownership of the GPU (the use case takes a
   lease per run today), it needs crash/restart and flush semantics, and it
   introduces a second owner of the model lifecycle — a contract change, not a
   performance change. It is named here so the option is not lost, not
   recommended so it is not smuggled in.
6. **The stage's shape is itself suspect at this scale.**
   `network/application/image/use_case.py` renders one still per scene and
   REUSES the previous one for the odd scenes (`if index % 2 == 0:`), so a
   script of N scenes yields **ceil(N/2)** images — that is the stage's own
   stated contract (its module docstring, line 5, and the function contract at
   line 58). The measured scripts carry **27–42 scenes** (`odd/tasks/
   script-stage-brief-text-cut.md` records a 27-scene baseline and a 42-scene
   verdict round), so the stage currently delivers **14–21 stills** for a
   script. The operator's second ruling (2026-11-14): **60 images is roughly
   a 15-minute video** — one still every ~15 s — and a video must carry at
   least 30–60 of them. So for the same script, the image stage produces
   roughly a third to a half of the stills the video needs. Either the video
   fills the rest from elsewhere, or the stage's `ceil(N/2)` contract is
   wrong. That is a product decision the operator owns; it changes the
   batching unit and the total image count, so the next work unit must settle
   it before it can promise a wall time.
   **The consequence for the wall time, at the operator's scale:** producing a
   15-minute video with 60 stills costs **56.5 min of GPU today — 3.8× the
   video's own duration**. Batched it is ~42 min (2.8×); batched with 8 steps
   ~31 min (2.1×); batched with 8 steps and 1024×576 ~23 min (1.5×). The
   video spends more time being rendered than being watched, and that ratio
   is the number the next work unit has to move.

**What the measurements say about the hardware:** the render is GPU-bound
(100 % utilisation, ~2 100 MHz of a 3 105 MHz maximum, 42-43 W, 39-54 °C) and
the per-forward cost is 2.83 s at 1280×720. The remaining headroom is in
kernel efficiency and in the work requested, not in the weight transport, the
disk, the swap or the power ceiling.
