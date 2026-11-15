# zimage-fp8-vs-int8 — the A/B that decides the Z-Image transformer

## Objective
Measure, on this machine's RTX 4060 Laptop, whether the Unsloth TorchAO FP8
candidate for Z-Image-Turbo beats the wired production transformer (QUANTO
weight-only INT8) on the three axes the operator named: **quality, speed,
stability**. Deliver a measured verdict with evidence in this repo. Production
does not change without a separate, explicit operator order.

## Problem
- **No cross-family A/B exists.** Unsloth's LPIPS vs bf16 (0.130 FP8 vs 0.181
  INT8) compares two of *their own* dynamic-activation torchao files. The
  production transformer is a different recipe: QUANTO weight-only INT8 with
  BF16 activations. Nobody has measured that pair.
- **The pair is not like-for-like.** FP8 quantizes 7 linears per main block and
  leaves the 30 `adaLN_modulation.0` linears in BF16; QUANTO quantizes 8 per
  block, `adaLN_modulation.0` included, and leaves the refiners BF16. The
  measurement compares two complete recipes, not "FP8 vs INT8" in isolation.
  That confound is disclosed, not hidden.
- **The FP8 file has no reader on this machine.** `torchao` is absent from
  Wan2GP's venv; `mmgp/fp8_quanto_bridge.py` expects per-channel `._scale`
  tensors plus a `scale_map`, while the file stores TorchAO `._weight_qdata` +
  `._weight_scale`. The load path must be established, not assumed.
- **The standing record is mislabelled.** `docs/model-vetoes.md:103` credits the
  measured production winner to *"z-image-turbo (WanGP, fp8)"*. The file that
  produced 17.5 s / 3719 MiB / judge 8.4/10 / 103/103 is the QUANTO INT8. The
  label is wrong. **The operator ordered the repair on 2026-11-13** (work unit:
  the registry entry + a changelog entry + a guard that fails when the label
  drifts from the checkpoint the catalog declares); it is in flight, and the
  verdict below does not depend on it.

## Why
- The operator's decision is conditional — *"si FP8 gana a int8 entonces
  mantengamos FP8"* — and the premise is unverified for this host and this
  pair. Only a same-host A/B settles it.
- 5,86 GiB sit on the operator's disk with no verdict. The bench either
  promotes the candidate or frees the space, both with evidence instead of
  folklore.
- The repo's own law allows re-evaluating a new quantization generation only
  *"with measured improvements"* (see `docs/model-vetoes.md`). This bench is
  that measurement.

## Machine (pinned)
- GPU: RTX 4060 Laptop, 8188 MiB VRAM, compute capability 8.9 (Ada) — FP8
  hardware support exists in principle.
- CPU: 12 cores. RAM ~31 GiB. Swap: zram 8 GiB + nvme 34 GiB.
- Wan2GP: `/home/juanvs23/tools/Wan2GP`, venv python 3.11, torch 2.14.0+cu130,
  diffusers 0.36.0, transformers 4.54.0, accelerate 1.15.0, `mmgp` present,
  `optimum.quanto` 0.2.7, **`torchao` absent**.
- System python3: 3.14.8, torch 2.13.0+cu130, diffusers 0.40.0 (it **has**
  `ZImagePipeline`, `ZImageTransformer2DModel`, `AutoencoderKL`),
  transformers 5.17.0, **torchao 0.18.0**, safetensors 0.8.0, skimage, PIL,
  torchvision. It lacks `optimum.quanto`, `mmgp` and `lpips`. On import it
  warns: *"Unable to import `torchao` Tensor objects. This may affect loading
  checkpoints serialized with `torchao`"* — whether that blocks the FP8 load
  is T1's open question.
- `torchao` wheels are small: 3.37 MB (cp310-abi3 manylinux) / 1.37 MB
  (py3-none-any). Putting it into Wan2GP's venv is a 3.4 MB change, not a
  build from source.
- The HF cache is **empty**, but the Qwen3 tokenizer (`tokenizer.json`,
  `tokenizer_config.json`, `vocab.json`, `merges.txt`), the text-encoder
  `config.json` and the 4.41 GB QUANTO encoder are already on disk under
  `Wan2GP/ckpts/Qwen3/`.
- `unsloth/Z-Image-Turbo-FP8` is **not** a diffusers layout: no
  `model_index.json`, no `transformer/`, `text_encoder/`, `vae/`, `tokenizer/`
  folders — single files only (plus a pre-cast FP8 text encoder of 5.19 GB
  that is a plain-tensor state dict, loadable with
  `torch.load(weights_only=True)`).

## Candidates (pinned by sha, as measured)
| Arm | Path | Size | Tensor census |
| --- | --- | --- | --- |
| Control (production, wired) | `/home/juanvs23/tools/Wan2GP/ckpts/ZImageTurbo_quanto_bf16_int8.safetensors` | 6 886 911 511 B | 1241 (1001 BF16 + 240 I8), `activations: none` |
| Treatment (candidate) | `<model store>/Z-Image-Turbo-FP8.safetensors` | 6 289 509 744 B | 760 (282 BF16 + 239 F8_E4M3 + 239 F32), TorchAO PerRow |

Shared companions already on disk: `ZImageTurbo_VAE_bf16.safetensors` (167 MB),
its config, `ZImageTurbo_scheduler_config.json`, and the Qwen3 text encoder
`ckpts/Qwen3/qwen3_quanto_bf16_int8.safetensors` (QUANTO INT8 — **reported as
not diffusers-loadable; T1 confirms**).

## Architecture decision (T1 — resolved 2026-11-13)
The FP8 arm can only be measured where torchao's dynamic-activation FP8 path
actually runs (`torch._scaled_mm`), which means **diffusers + torchao**, not
mmgp: the mmgp bridge (`fp8_quanto_bridge.py`) converts FP8 into **QUANTO FP8
weight-only** (`_QTYPE_NAME` carries `qfloat8_e4m3fn`) — *not* into int8, a
claim this document carried until 2026-11-13 and which the installed source
contradicts. Routing the FP8 arm through it would therefore measure a
**different recipe** (weight-only FP8 with a per-channel scale map) instead of
the candidate's TorchAO dynamic-activation FP8, and destroy the variable under
test: its detector recognises `._data`, `scale_weight` or a plain float8
`weight`, while the candidate stores `._weight_qdata` / `._weight_scale`.

**Both arms run in ONE runtime** (bench venv: python 3.14.8, torch 2.13.0+cu130,
diffusers 0.40.0, torchao 0.18.0, optimum-quanto 0.2.7, mmgp 3.8.2), so the
diffusers version, the VAE, the scheduler, the steps, the guidance, the seeds,
the dtype and the memory strategy are identical and the transformer is the
only variable:
- **control** = the QUANTO weight-only INT8 file loaded by the PRODUCTION
  loader — the script `network/adapters/zimage.py::build_render_script`
  generates, executed under the bench venv — so the control is
  production-identical code, not a re-implementation;
- **treatment** = the TorchAO FP8 file rebuilt as torchao `Float8Tensor`s
  (torchao 0.18: `torchao.quantization.quantize_.workflows.float8.float8_tensor.Float8Tensor`,
  whose `__new__(qdata, scale, block_size, mm_config, act_quant_kwargs, ...)`
  matches the file's recorded layout exactly) and loaded into the same
  `ZImageTransformer2DModel`.

**Load route (verified against the installed sources, 2026-11-13):** the FP8
arm must go through diffusers' metadata-aware safetensors path, NOT
`from_single_file` — the single-file path keeps only tensors and drops the
metadata the TorchAO quantizer needs. The staging directory needs
`diffusion_pytorch_model.safetensors` plus a `config.json` carrying
`quantization_config` (that is what sets `pre_quantized=True`), BUT a bare
symlink to the candidate is NOT sufficient: the root-tensor rename below must
happen first, so the loader must receive the already-renamed state dict
(manual `safe_open` → rename → `unflatten_tensor_state_dict` → assign, or a
staged copy whose keys are already renamed). The candidate's header carries
`unsloth_format = unsloth_prequant_transformer_state_dict_v1`,
`unsloth_quant_layout` v1, per-tensor `Float8Tensor` records and
`_tensor_data_names` — the last one **confirmed present in the local file**, so
torchao's canonical reader accepts it. Diffusers' warning *"Unable to import
`torchao` Tensor objects"* comes from its `torch.load` safe-globals path and
does NOT block this bench: the transformer is read as safetensors, never
`torch.load`ed. The control arm's faithful loader is
`optimum.quanto.requantize(model, state_dict, quantization_map)`, which
respects the exact mmgp map module by module.

**Control-arm trap — `requantize` OVERWRITES the quantization:** optimum's
`requantize(model, state_dict, quantization_map)` ends with
`model.load_state_dict(state_dict, strict=False)`. If the `state_dict` carries
DEQUANTIZED FLOATS under the quantized modules' keys, that load lands AFTER
the quantization and silently restores float weights — the "INT8 control"
would then be a float model, the A/B would quietly measure FP8-vs-BF16, and the
control's memory/speed profile would be wrong. Measured proof on this machine:
passing a float weight produced a forward identical to the float reference
(max abs error 0.000000 — the tell), while passing the checkpoint's own
`weight._data` (int8) + `weight._scale` (bf16 [out,1]) + `input_scale` /
`output_scale` pieces produced a real `WeightQBytesTensor` with an int8
`_data`. The harness MUST feed the RAW checkpoint pieces (what mmgp's
`load_model_data` feeds) and MUST assert that the loaded control weight is a
`WeightQBytesTensor` whose `_data` is int8, failing loudly otherwise. mmgp's
own `_requantize` is immune because it never calls `load_state_dict` — it
loads the state dict separately.

**Format gate (verified against the real file on 2026-11-13, header only,
zero weight bytes read):** `is_metadata_torchao(candidate_metadata)` returns
**True** — diffusers 0.40 therefore keeps the metadata and reconstructs the
`Float8Tensor` subclasses. All 519 logical tensors have their flattened
pieces present (`<fqn>._weight_qdata` F8_E4M3 `[out,in]` +
`<fqn>._weight_scale` F32 `[out,1]`, `block_size [1,3840]`, per-row
granularity), and `Float8Tensor.__new__` accepts exactly the recorded `_data`
keys (`act_quant_kwargs`, `block_size`, `dtype`, `kernel_preference`,
`mm_config`, `qdata`, `scale`). Name mapping against the real
`ZImageTransformer2DModel` (521 parameters) leaves **zero** unexpected keys;
the `-1` suffixes in `all_x_embedder.2-1.*` / `all_final_layer.2-1.*` are the
model's OWN module names, not a rename artefact. No tensor without a `.` in
its name exists, so diffusers' root-tensor special case is a no-op.

**Root-tensor rename — MANDATORY, or the A/B measures the wrong thing:** the
candidate does NOT carry the two learned pad tokens under the model's names.
It carries `unsloth_root::cap_pad_token` and `unsloth_root::x_pad_token`, and
its own metadata declares the mapping (`unsloth_root_tensors = ["x_pad_token",
"cap_pad_token"]`). The model expects `cap_pad_token` / `x_pad_token` and
initialises both to `torch.zeros((1, dim))`, while the INT8 control carries
TRAINED non-zero values (norms 7.855447 / 6.858116). A plain
`from_pretrained(<staged dir>)` therefore leaves the FP8 arm's pad tokens at
ZERO and the arms differ in more than quantisation — a silent false negative
that would blame FP8 for a packaging artefact. The rename is provably
lossless: the FP8 values are **bitwise equal** to the control's
(`torch.equal` → True, max abs diff 0). The harness MUST rename the two keys
before the state dict reaches the model and MUST assert that both arms
report identical pad tokens, failing loudly otherwise.

The text encoder is NOT a variable: both arms consume the SAME embeds, produced
by the production encode path (Qwen3 quanto int8 via mmgp, `hidden_states[-2]`)
and cached under the evidence folder.

The production mmgp path is used only as a **calibration cross-check**: the
control arm is also rendered through the production adapter in the same session
and compared against the bench control (time + output). If the two controls
disagree, the harness is the suspect and no comparison is drawn. The historical
reference (17,5 s/still at 8 NFEs from the P5 log parse; warm mean 14,76 s,
n=8, p95 16,1 s in the P5 summary) is context, not the gate: the catalog
declares 12 steps today, so the like-for-like gate is same-session, never a
number measured at a different step count.

**Therefore both arms run in the same stack** (system python, diffusers 0.40.0,
identical pipeline, VAE, text encoder, scheduler, steps, guidance, seeds):
- **control** = the QUANTO weight-only INT8 file loaded into the same
  `ZImageTransformer2DModel`;
- **treatment** = the TorchAO FP8 file loaded into the same model class.

The production mmgp path is used only as a **calibration cross-check**: the
control arm is also rendered through the production adapter and compared
against the diffusers control (time + output). If the two controls disagree,
the harness is the suspect and no comparison is drawn.

## Scope (authorized)
1. **T1 — Feasibility reconciliation (read-only).** Establish: the FP8 file's
   real tensor layout; what `mmgp`/Wan2GP expects for an FP8 transformer; the
   diffusers route and its missing pieces; `torchao` availability per python;
   the headless render path per arm; the minimum download+install budget.
2. **T2 — Declare the budget, wait for the word.** Present the operator the
   exact installs and downloads (sizes, URLs, sha256) the bench needs. Execute
   nothing until the operator answers. **Answered 2026-11-13**: the operator's
   word is *"no es un simple se queda es probar el fp8 y el int8 y ver cual da
   mejores resultados y es mas rapido y cual es mas estable con el hardware"*
   plus *"seguimos"* — the bench is authorised. The declared budget was
   executed inside an ISOLATED venv (nothing installed into the operator's
   system python, nothing touched in production):

   | Item | Size | Where | Why |
   | --- | --- | --- | --- |
   | `optimum-quanto` 0.2.7 | 0,16 MB wheel | bench venv | the control arm's int8 format |
   | `mmgp` 3.8.2 | 0,07 MB wheel | bench venv | the production loader, reused instead of rewritten |
   | `torchao` 0.18.0 | already installed | system site-packages | the FP8 path |
   | downloads | **0 bytes** | — | every weight the bench needs is already on disk |

   The optional LPIPS metric (0,05 MB wheel + ~550 MB of VGG weights) is NOT
   installed: the quality layer rides on SSIM (skimage, already present) and
   on the blind VLM judge, which is already running on this host
   (`ollama` at 127.0.0.1:11434, `glm-5.3:cloud`).
3. **T3 — Build the bench harness** at `tests/e2e/zimage-fp8-vs-int8/`:
   `README.md` (the e2e contract), gitignored `evidence/`, the runner, the
   metrics collector, and the pinned prompt/seed fixture.
4. **T4 — Run the control arm** (QUANTO INT8, production) with the identical
   fixture: same prompts, seeds, steps, guidance, resolution, VAE, text
   encoder, scheduler.
5. **T5 — Run the treatment arm** (FP8) with the byte-identical fixture.
   **The transformer is the only variable**; a run whose knobs differ between
   arms is invalid, not a result.
6. **T6 — Quality.** Same-seed LPIPS + SSIM (CLIP if a scorer is available
   offline), plus a blind side-by-side sheet of the renders. Confound stated
   in the verdict.
7. **T7 — Speed.** Per-image wall time, cold vs warm, per-step cost.
8. **T8 — Stability.** VRAM peak, `MemAvailable` floor, swap activity,
   black/blank frames, non-finite outputs, failure rate, watchdog events.
9. **T9 — Verdict** on the three axes, with the evidence paths and every
   residual confound named.
10. **T10 — Report.** Operator-facing report in Spanish. Any production,
    catalog or veto-record change is a separate, explicitly ordered task.

## Constraints
- **Single variable.** Every other knob is pinned in the fixture and published
  with the evidence. A run whose knobs differ between arms is invalid, not a
  result.
- **No downloads, installs, deletions or production edits without an explicit
  operator order.** T2 declares; the operator answers; only then executes.
- **Production is untouchable**: no change to
  `network/assets/catalogs/image_models.yaml`, no change to
  `docs/model-vetoes.md`, no change to `Wan2GP/ckpts/`.
- **Evidence lives in this repo** (`tests/e2e/zimage-fp8-vs-int8/evidence/`,
  gitignored). Never `/tmp`.
- **Watchdog**: abort an arm when `MemAvailable` < 2 GiB or when one image
  exceeds its declared timeout. The known freeze signature (llama-server at
  325–407 % CPU with `kswapd0` at 88 %) means the bench must not run beside a
  hot `llama-server`; check before each arm.
- **TDD mode: off.** Source: this repo declares functional checks in
  `AGENTS.md` and declares no strict-TDD configuration (same reading as
  `odd/tasks/core-catalogs.md`). Runner: `python3 -m unittest discover -s
  tests -v`. Ordinary functional checks apply, not RED-GREEN-REFACTOR.
- **RDD is OFF (global).** No native review is started; verification is
  functional and structural.
- **Commits, push and PR are the operator's decision** (standing operator
  constraint): no automatic commit, push or PR. The document and harness land
  as working-tree changes until the operator decides.
- **Artifact language: English.** Operator report: Spanish.

## Checklist
- [x] T1 — Feasibility reconciled; load path and budget written down
- [x] T2 — Install/download budget declared; operator order recorded
- [x] T3 — Harness built and self-checked (dry run, no GPU) — GREEN 4/4, verified 2026-11-13
- [x] T4 — Control arm (QUANTO INT8) run; evidence on disk — 3 cells, 2026-11-13
- [x] T5 — Treatment arm (FP8) run; evidence on disk — 3 cells, 2026-11-13 (needed the mmgp protocol adapter)
- [x] T6 — Quality analysis (same-seed metrics + blind sheet) — SSIM/PSNR per cell + blind sheets
- [x] T7 — Speed analysis (per-image wall time, cold vs warm) — FP8 -15…-18 % per image, -87 % setup
- [x] T8 — Stability analysis (VRAM, MemAvailable, swap, black frames, non-finite) — FP8 uses LESS VRAM and 10x less swap
- [x] T9 — Verdict on quality / speed / stability with confounds — quality INDISTINGUISHABLE-but-different, speed FP8 WINS, stability FP8 WINS
- [x] T10 — Operator report delivered; follow-up decisions listed — 3 production follow-ups + 2 findings for the other lane

## Route declaration
Delegated direct (no SDD; the operator did not ask for it).
- **Mapping trigger (T1)**: understanding needs 4+ files (the `mmgp` bridge,
  Wan2GP's model manager, its configuration plugin, the safetensors header,
  the public HF/PyPI APIs) → one narrow delegated exploration. In flight:
  session `ses_e29684b86ffeiyX7LgYs0x6rdQ`.
- **Preparation trigger**: reading that prepares the harness write is delegated
  together with the write, never in the parent.
- **Writer trigger (T3)**: runner + metrics collector + README + fixture =
  3+ non-trivial files → one delegated writer. Lineage: writer #1
  (`ses_e2912015bffePyLz2NzXa2Djti`) and writer #2
  (`ses_e29037d9fffeYkLd907pl7fe7p`) died with zero output (no files, no
  memory, no completion notification) — the runtime's background subagents
  are the recurring failure class (the first T1 worker died the same way,
  HTTP 429). Writer #3 (`ses_e28e6d747ffeJ50YVdZP2vCYSr`) carries the same
  brief, pointed at this document instead of a restatement of the facts.
- **Per-action rule (T4/T5)**: the GPU arms run as fresh bounded workers; the
  parent never holds a GPU job inline.
- Parent keeps a thin thread, verifies structurally, and re-runs one reported
  command as a spot check before delivering.

## Verification (applicable checks)
- `ruff check .`
- `python3 -m unittest discover -s tests -v`
- Harness self-check: the runner must fail loudly on a black frame, on a
  non-finite pixel, and on a watchdog abort — a silent pass is a failed run.
- Harness calibration: the control rendered through the BENCH stack must land
  within ±20 % of the control rendered through the PRODUCTION stack (catalog
  interpreter), on the same machine and the same day, and both must show the
  same scene (SSIM ≳ 0.9). Measured 2026-11-13: 112,07 s (bench cold) vs
  104,22 s (production) → **7,0 %** delta, SSIM **0,916340** → PASS. The
  legacy **17,5 s/image** figure is a per-image number from other hardware and
  a different loading regime: it is NOT comparable to a full-process wall time
  (each arm run is a fresh process that loads the model from disk) and must
  not be used to diagnose the harness. If the same-day comparison fails, the
  harness is the suspect, not the model, and T4 is re-diagnosed before any
  comparison is drawn.

## Run book (T4–T6, parent-owned)
The order is mandatory; each step gates the next one:
1. `self_check.py` (no GPU) green — otherwise no arm runs.
2. Preconditions: GPU idle (only the desktop compositor), no hot `llama-server`
   (freeze signature: 325–407 % CPU with kswapd0 at 88 %), MemAvailable >= 2 GiB.
3. Encode step ONCE (production interpreter), embeds cached under
   `evidence/embeds/` — both arms consume the same files.
4. Control arm (QUANTO INT8) over the fixture → `evidence/control/`.
5. Treatment arm (FP8) over the byte-identical fixture → `evidence/treatment/`.
6. Calibration cross-check in the same session: the control rendered through
   the production adapter (catalog interpreter) versus the bench control. They
   must agree on time (±20 %) and output sanity, or NO comparison is drawn.
7. Quality (T6): SSIM per cell (skimage) plus a BLIND side-by-side sheet — arms
   anonymised as A/B, order randomised per cell, judged by the ollama cloud VLM
   with the legacy RUBRIC (strict anatomy-and-craft). Judge passes run
   SEQUENTIALLY (the relay caps overlapped passes: HTTP 503 at 16/16). Judge
   models verified alive on this host: `deepseek-v4.1-flash:cloud` (primary),
   `glm-5.3-flash:cloud` (second opinion).
8. Speed (T7) and stability (T8) come from the per-arm metrics JSON and the
   VRAM CSV. LPIPS stays OUT (no VGG download) unless the operator asks for it.

## Forecast
Authored lines ~350–550 (runner, metrics collector, fixture, README).
Delivery strategy: `ask-on-risk` — and no delivery action at all until the
operator's word.

## Evidence
- **T1 — closed 2026-11-13.** Facts measured on this machine (read-only):
  - The FP8 file is TorchAO-native: metadata `unsloth_format =
    unsloth_prequant_transformer_state_dict_v1`, `unsloth_quant_layout` v1
    (`<fqn>._weight_qdata` float8_e4m3fn [out, in] + `<fqn>._weight_scale`
    float32 [out, 1], dequant `weight = qdata * scale` per output row) and a
    `tensor_names` map holding, per module, the exact `Float8Tensor` record
    (`block_size`, `Float8MMConfig`, `act_quant_kwargs`). 760 tensors:
    282 BF16 + 239 F8_E4M3 + 239 F32.
  - The control file is quanto-native: `quantization_format=quanto`,
    `quantization_map_base64` (`qint8` weights, `activations: none`),
    `config_base64` carrying the `ZImageTransformer2DModel` config. 1241
    tensors: 1001 BF16 + 240 I8.
  - torchao 0.18 moved the float8 API: `torchao.dtypes.float8` is GONE; the
    classes live at `torchao.quantization.quantize_.workflows.float8.float8_tensor`
    and `torchao.quantization.granularity`. The diffusers warning *"Unable to
    import `torchao` Tensor objects"* comes from diffusers' own `torch.load`
    safe-globals path and does NOT block this bench: the transformer is read
    as safetensors, never `torch.load`ed.
  - The `Float8Tensor.__new__` signature
    `(qdata, scale, block_size, mm_config, act_quant_kwargs, ...)` matches the
    file's recorded layout field for field: the candidate can be rebuilt
    exactly, without a dense bf16 intermediate.
  - The legacy bench folder holds a TRANSSPORT bench (diffusers vs WanGP vs
    ComfyUI), not a quantization A/B: no two-arm mechanism exists anywhere,
    so the harness has to be built (once) and pinned here.
  - The legacy P5 harness is reusable as METHOD: `benchmon.ResourceSampler`
    (VRAM/RSS sampling), the `prompts.json` fixture shape, the
    `aggregate.py` summary schema and the VLM judge backend.
  - Two numbers that are NOT the same metric: 17,5 s/still is the P5 log
    parse at 8 NFEs; the P5 summary records warm mean 14,76 s (n=8, p95
    16,1 s). The bench pins its own steps and compares same-session.
  - The judge relay must run SEQUENTIALLY: two overlapping passes hit the
    ollama cloud worker limit (HTTP 503, 16/16).
  - The bench must not run beside a hot `llama-server` (known freeze
    signature: 325-407 % CPU with kswapd0 at 88 %).
- **T2 — closed 2026-11-13.** Operator order recorded above; the declared
  budget executed inside the isolated bench venv, now living **next to the
  model**: `<model store>/bench/venv`
  (`--system-site-packages` on python 3.14.8), with the staging directory at
  `<model store>/bench/stage` (`config.json` +
  `diffusion_pytorch_model.safetensors` symlinked to the candidate). The
  operator moved it there on 2026-11-13 ("lo que instalaste en tmp, hazlo en
  la carpeta donde está el modelo"). The old path
  `<bench>/venv` is now a SYMLINK to the new
  venv, so the in-flight harness keeps working; the new path is canonical.
  `optimum-quanto` / `mmgp` / `ninja` were uninstalled from the python 3.14
  user site so the venv is their ONLY owner. Production untouched: no change
  to the catalog, to `docs/model-vetoes.md` or to `Wan2GP/`. Zero model-weight
  downloads.
  - The operator additionally authorised the runtime install on 2026-11-13
    (`pip install optimum-quanto==0.2.7` + `mmgp==3.8.2`, pure-python wheels,
    350 kB total, **no model weights**). It was installed into the python 3.14
    USER SITE as well, so the system interpreter is now a complete bench
    runtime. The isolated venv keeps its own copies and still wins on
    `sys.path` — identical versions, no skew — but two copies now exist.
  - Bench runtime verified functional on python 3.14.8: torch 2.13.0+cu130
    (CUDA OK, RTX 4060 Laptop), diffusers 0.40.0, transformers 5.17.0,
    accelerate 1.12.0, safetensors 0.8.0, torchao 0.18.0, optimum-quanto
    0.2.7, mmgp 3.8.2, psutil 7.2.2. `requantize` exercised end to end with
    the control's real int8 pieces; all 240 entries of the control's
    `quantization_map` resolve against the real `ZImageTransformer2DModel`
    (240/240, none missing). Repo untouched by the install: 488 tests OK,
    ruff baseline unchanged (255).
  - **T4 smoke (2026-11-13, GPU) — the FP8 arm LOADS and COMPUTES on this
    machine.** Staged dir
    `<model store>/bench/stage` (symlink
    `diffusion_pytorch_model.safetensors` -> the candidate, plus the
    `config.json` carrying `quantization_config`) loaded with
    `ZImageTransformer2DModel.from_pretrained(stage, torch_dtype=bfloat16,
    local_files_only=True)`:
    - loads in **0.6 s**; 521 parameters of which **239 are `Float8Tensor`**
      (`qdata=float8_e4m3fn`, `scale=float32`, `block_size=[1,3840]`,
      per-row). Diffusers reports ONLY the two pad tokens as newly
      initialized.
    - `torch._scaled_mm` with `float8_e4m3fn` **works on this RTX 4060**
      (CC 8.9): the feared `CUBLAS_STATUS_NOT_SUPPORTED` does NOT occur.
    - a real FP8 `F.linear` with the model's own weights returns finite
      values.
    - weights on GPU: **5.91 GiB peak / 6.26 GiB reserved of 8.19 GiB** -> only
      ~1.9 GiB left for activations. The FP8 arm needs the production memory
      strategy (profile 4 / group offload) exactly like the control.
    - the pad patch must be **META-aware**: after `from_pretrained` the two pads
      are META tensors (not zeros), so they must be REPLACED
      (`setattr(model, r, torch.nn.Parameter(value))`), not written through
      `.data`. After the patch both pads are bitwise equal to the control's.
    - the transformer must be driven **through the pipeline** (or with the
      pipeline-derived masks): calling `forward` with dummy tensors raises a
      CUDA device-side assert (`vectorized gather kernel index out of bounds`),
      because the position/mask metadata is derived from the real latents and
      text features.
    - `ZImagePipeline.__call__` accepts `prompt_embeds` and returns them
      untouched when supplied, so the production embeds (mmgp Qwen3,
      `hidden_states[-2]`) can be injected and the text encoder stays out of
      the A/B.
    - VAE and text encoder are local: `ZImageTurbo_VAE_bf16.safetensors` (+ its
      `_config.json`) and `Qwen3/qwen3_quanto_bf16_int8.safetensors`.
  - **Read-back review of the in-flight harness (2026-11-13, the parent's
    review of `loader.py` as written by the other session's writer) — three
    defects to fix before the first GPU run:**
    1. `assert_treatment_invariants` computes `expected_plain` as
       `stats["plain_modules"] + stats.get("root_tensors", 0)`, but
       `load_treatment_state_dict` never sets a `root_tensors` key: it
       expects **280** while the live count is **282** (280 plain module
       weights + the 2 root pads) → the invariant raises `AssertionError` on
       its first call. The 2 root tensors must be added.
    2. The module docstring repeats the claim this document already
       corrected — *"the mmgp fp8 bridge converts FP8 into quanto int8"*. The
       installed source says **QUANTO FP8 weight-only** (`qfloat8_e4m3fn`).
       The conclusion (do not route the candidate through mmgp) stands; the
       reason must be stated correctly.
    3. `_metadata_counts` is dead and broken: it calls `_path_of(meta)`,
       which raises `NotImplementedError`, and `fw_dtype`, which does not
       exist. Implement it or delete it.
    What is already right and must be kept: torchao's own
    `unflatten_tensor_state_dict`, the `unsloth_root::` merge, the
    `leftover` and `state_dict_entries == model_entries` assertions,
    `load_state_dict(..., assign=True)` (this route materialises the pads as
    real parameters, so the meta-tensor trap does not apply to it), and the
    float8/plain census that fails loudly if the arm silently degrades to
    BF16.
- **T3 — GREEN (2026-11-13, verified by the parent).** The harness at
  `tests/e2e/zimage-fp8-vs-int8/` (README, fixture, loader, render, metrics,
  self-check) passes its dry no-GPU self-check **4/4** under the bench venv:
  the fixture resolves to one byte-identical knob set for both arms (3 cells,
  1280x720); the black / non-finite / watchdog detectors fail loudly; the
  loader wiring rebuilds one recorded `Float8Tensor` (`cap_embedder.1.weight`,
  `block_size=[1, 2560]`); the control metadata resolves the quanto checkpoint
  with 240 quantized modules; and the treatment script is derived from the
  production script with ONLY the loader differing — the single-variable
  property the whole A/B rests on. The three defects reported in the
  read-back review above are fixed, and the fixture schema (`knobs` /
  `transformers` / `watchdog` / `cells`) now matches what `render.py` reads.
- **T4 — control arm CALIBRATED (2026-11-13, parent lane).** The control
  (QUANTO weight-only int8) was rendered through the PRODUCTION recipe (the
  repo's own `build_encode_script` / `build_render_script`, driven by the
  catalog entry `z-image-turbo`) in a folder of its own,
  `tests/e2e/zimage-control-calibration/` (README, fixture, runner;
  `evidence/` gitignored), so the other session's writers were never touched:
  - encode (production Qwen3 quanto int8 TE, `hidden_states[-2]`): **26,73 s
    cold / 32,95 s warm**, peak GPU used 6316 MiB (includes the ~779 MiB of
    the desktop compositor). Embeds frozen: bfloat16, `[27, 2560]`,
    139 746 B.
  - render (12 steps, guidance 0.0, bf16, offload profile 4, 1280x720,
    seed 20261021): **112,07 s cold / 128,86 s warm**, peak GPU used
    **5142 MiB** (the transformer itself ≈4,4 GiB under profile 4).
  - output `evidence/control.png`, 1280x720, 1 068 387 B, sha256
    `5021cea708b999d590ab1746c937ce501ae05f5cd117050c2701bd683b1d7847`.
  - **DETERMINISM PROVEN**: the cold run and the warm run produced the same
    sha256 byte for byte, so any later divergence is the treatment's, not the
    pipeline's.
  - **cross-check against the production stack** (run book step 6): the same
    control through `ZImageAdapter.render` on the catalog interpreter (Wan2GP
    venv, python 3.11, torch 2.14, diffusers 0.36) took **104,22 s** → time
    delta **7,0 %** (cold) / **19,1 %** (warm), both inside the ±20 %
    tolerance; output **SSIM 0,916340** (same scene, different numerics →
    the stacks are not byte identical). Sanity holds, so the bench stack may
    carry both arms.
  - the warm run was SLOWER than the cold one: host contention (swap
    14 899 → 15 836 MiB, concurrent sessions loading models), not GPU state.
    Both runs are full reloads. `MemAvailable` 20 918 → 22 155 MiB: no
    exhaustion.
- **T5 — the FP8 arm RAN (2026-11-13), after two real blockers.**
  - **Blocker 1 — mmgp vs torchao.** The first attempt died inside mmgp's
    pinned-memory shuttle: mmgp supports quantized parameters through a
    duck-typed protocol (`get_quantized_subtensors()` /
    `set_quantized_subtensors()`) that it patches onto quanto's `QTensor`;
    torchao's `Float8Tensor` does not implement it, so mmgp fell into the
    plain-tensor branch and called `view(torch.uint8)` on the subclass —
    `NotImplementedError: Float8Tensor dispatch: ... aten.view(dtype)`.
    Fix: `tests/e2e/zimage-ab-analysis/fp8_offload_protocol.py` teaches mmgp
    the protocol for `Float8Tensor` (its PUBLIC `qdata` / `scale` pieces are
    plain tensors), mirroring mmgp's own quanto patch. Guard:
    `tests/test_fp8_offload_protocol.py` (4 tests; the mmgp one SKIPS in the
    canonical runner because mmgp lives in the bench venv). After the fix
    mmgp logged *"The whole model was pinned to reserved RAM: 25 large blocks
    spread across 5997.84 MB"*.
  - **Blocker 2 — the harness's own half-renames.** `render.py` called
    `_install_finite_guard`, `_render_payload` and `_raise_render_failure`
    after those functions had moved to `metrics.py` as `install_finite_guard`,
    `read_render_payload` and `raise_render_failure` → `NameError` on every
    arm. The parent's own `self_check.py` did NOT catch it (it only derives
    scripts; it never enters the render loop). Three call sites were
    repaired surgically; an AST scan now finds no dead names in `render.py`.
    **This is a finding for the other session: its dry self-check does not
    cover the render path.**
  - Result: **3/3 cells rendered**, loader census **239 float8 / 282 plain**
    (the weights stayed real FP8 after the offload — no silent BF16
    degradation), setup **9.59 s**, no black frame, no non-finite, no
    watchdog abort.
- **T6–T9 — the verdict (2026-11-13).** Single variable VERIFIED by the
  analysis: same embeds (sha256), same seeds, same prompts, same knob set;
  the only difference is the transformer checkpoint.
  - **Quality (T6) — different, not better.** SSIM per cell 0.8401 /
    0.8261 / 0.9348 (mean **0.867**), PSNR 22.56 / 19.50 / 27.37 dB. The arms
    preserve semantics, composition and style; they diverge in fine detail
    (web geometry, shelf layout, ridge profile). Both arms PASS the legacy
    anatomy-and-craft rubric on all three cells; cell-02 carries gibberish
    signage in BOTH arms (a text artifact in both, not a discriminator).
    Blind read (parent's vision pass, rubric v2, sheets judged before opening
    the mapping): marginal edge to INT8 in 2 of 3 cells, a wash in the third
    — **not decisive**. With no BF16 reference on this machine, SSIM/PSNR
    measure DIVERGENCE, never absolute fidelity.
  - **Speed (T7) — FP8 wins.** Per image: **44.13 s cold / 42.65 s warm**
    (control, ~3.56 s per step) vs **36.01 s cold / 36.14 s warm** (FP8,
    ~3.01 s per step) → **-18.4 % cold, -15.3 % warm**. Setup: **74.00 s →
    9.59 s (-87 %)** — the FP8 candidate needs no quanto requantize.
    End-to-end for the three cells: **203.5 s → 117.8 s (-42 %)**.
  - **Stability (T8) — FP8 wins.** Peak GPU memory **6249 → 4651 MiB
    (-25.6 %)**; `MemAvailable` floor 11 670 → 12 407 MiB; swap pressure
    **-229 MB → -22.8 MB (10x gentler)**; memory floor never breached; zero
    black frames, zero non-finite pixels, zero watchdog aborts in either arm.
  - **Confounds (must travel with the verdict):** (1) the text encoder is NOT
    a variable (same embeds, sha256-verified); (2) the quantization recipes
    are inherently different (quanto 8 linears per block vs FP8 7) — this is
    a PRODUCT comparison, not a same-granularity comparison; (3) the FP8 arm
    needs the mmgp protocol adapter — a production integration cost the
    numbers do not capture; (4) there is no BF16 reference here, so neither
    arm can be called "more faithful", only "different"; (5) the blind judge
    was the parent's own vision pass with the legacy rubric, not a
    third-party VLM (ollama had no quota) — the operator's own read of the
    sheets is the tiebreaker; (6) the box was shared with other sessions
    during the run.
  - **Verdict:** FP8 is **faster (-15…-42 %)**, **lighter (-26 % VRAM)** and
    **equally stable**, with quality that is indistinguishable at a glance
    but measurably different in detail. It is a viable production candidate
    ONLY with three follow-ups: the protocol adapter inside the production
    loader, a Wan2GP catalog + venv that can select it (it cannot today),
    and the operator's blind judgement of the sheets.
- **T10 — the operator report was delivered (2026-11-13).** Three axes, one
  verdict: **quality indistinguishable-but-different (FP8 not better)**,
  **speed FP8 wins (-15…-42 %)**, **stability FP8 wins (-26 % VRAM, 10x less
  swap, zero failures)**. The report carried the six confounds with it, so
  the verdict cannot travel without them.
  - **Three production follow-ups (each needs the operator's order):**
    (a) the mmgp↔torchao protocol adapter must live inside the PRODUCTION
    loader — today it exists only as a bench-time runtime patch
    (`tests/e2e/zimage-ab-analysis/fp8_offload_protocol.py`), so Wan2GP
    cannot load the FP8 candidate at all; (b) Wan2GP's `z_image` catalog
    offers only BF16/QUANTO INT8 and its venv (torch 2.14, diffusers 0.36)
    has no torchao — the catalog and the venv must learn to select FP8;
    (c) the operator's own blind read of the sheets
    (`tests/e2e/zimage-ab-analysis/evidence/blind/*.png`, judged BEFORE
    `mapping.json`) is the tiebreaker the parent's vision pass cannot
    replace.
  - **Two findings for the other session (their lane, not ours):**
    (i) `self_check.py` does NOT cover the render path — it derives scripts
    and never enters the render loop, so the half-renamed call sites
    (`_install_finite_guard`, `_render_payload`, `_raise_render_failure`)
    shipped a 4/4 GREEN self-check over a harness that raised `NameError`
    on every arm; (ii) `loader.py` (436 lines), `metrics.py` (408) and
    `render.py` (406) are OVER the repo's ~400-line budget
    (project rule 12). They are untracked today, so `tests/test_file_budget.py`
    cannot see them yet; the moment they are committed the guard FAILS and
    the three must be split by RESPONSIBILITY or registered in
    `docs/context.md` with reason and slot. We did NOT register them: those
    files belong to the other lane, and one rule has one owner.

## Machine-readable record
The full task state is mirrored in Engram under topic
`odd/zimage-fp8-vs-int8/tasks` (project `<the calling project>`).

## Parallel-session notes (2026-11-13, session `ses_e2bab60f`)
Written by the parallel orchestrator that owned the bench harness
(`tests/e2e/zimage-fp8-vs-int8/`) while the other session owned the verdict
lane (`tests/e2e/zimage-ab-analysis/`). Additive; it records what that
session measured and did NOT soften any claim.

- **Harness gate repaired, then GREEN.** `self_check.py` demanded
  `loader.build_control_render_script` and `loader.script_without_loader`
  — the functions that prove the treatment differs from production ONLY in
  the transformer-loader line. The loader did not implement them, so the
  guard failed 3/4. The loader now owns both, and `render.py` routes the
  control through the same named entry point the guard checks (the runner
  and the guard now share ONE code path). `SELF_CHECK PASS (4/4)`.
- **The undefined-name defect was in the render path, not the loader**
  (`_install_finite_guard`, `_render_payload`, `_raise_render_failure`).
  Repaired to the `metrics.*` names. **Finding that outlives this bench:**
  the no-GPU self-check never enters the render loop, so it cannot catch
  this class of defect — the render path needs its own guard.
- **Independent verification of the treatment arm.** The loader census
  read `{"float8": 239, "plain": 282}` AFTER the offload, matching the
  checkpoint's 239 recorded FP8 modules: the FP8 arm rendered in real FP8,
  with no silent BF16 degradation.
- **Repository guards after the harness edits:** `ruff check
  tests/e2e/zimage-fp8-vs-int8/` clean; `python3 -m unittest discover -s
  tests -v` → **492 tests, OK (1 skipped)**.
- **The third-party VLM judge is blocked by the relay's quota, not by
  choice.** Probed on this host: `POST http://127.0.0.1:11434/api/generate`
  → **HTTP 429** `you (juanvs23) have reached your monthly usage limit`
  (text prompt and image prompt alike). Every judge tag available on this
  relay is a `:cloud` tag (`deepseek-v4.1-flash:cloud`,
  `glm-5.3-flash:cloud`, `glm-5.3:cloud`, `gemma4:cloud`, `beam:cloud`),
  so there is NO local judge to fall back to. The quality axis therefore
  rests on the blind sheet plus SSIM/PSNR divergence, and the operator's
  own read is still the tiebreaker.
- **Two ways to close the quality axis, both needing the operator's word:**
  1. run the legacy judge through its PROVEN hosted NVIDIA route
     (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`; the key exists in
     the legacy repo's `core/configs/.env`) — a different vendor and an
     off-machine transfer of the sheets, so it needs explicit
     authorization; 2. download the BF16 base checkpoint (~12 GB; only the
     quanto INT8 control, the VAE and the scheduler exist locally) and
     measure ABSOLUTE fidelity of both arms against truth — the budget for
     this bench was zero downloads, so it needs a new order.

## Blind third-party judge (2026-11-15, session `ses_e2bab60f`)
The relay's monthly quota was restored, so the quality axis could finally be
closed with the operator's own instruments: the blind sheets, the legacy
anatomy-and-craft rubric, and the two specified judge models.

- **Instrument** (`tests/e2e/zimage-ab-analysis/judge_blind.py`): the blind
  phase reads ONLY the sheets; the mapping is opened afterwards, in a
  separate phase, to tally. One request per cell, SEQUENTIALLY (the relay
  caps overlapping passes). The harness computes the winner deterministically
  from the defect grades (anatomy failure -> failed; composition/text/
  watermark -> degraded); the model's own opinion is kept for comparison but
  never trusted, and an unparsable answer is reported, never counted. Each
  sheet is sent as its two full-resolution labeled halves, so the anatomy
  audit is not done on a downscaled composite.
- **Raw verdict (6 votes over 3 cells x 2 models):**
  `deepseek-v4.1-flash:cloud` -> control 1, treatment 1, tie 1;
  `glm-5.3-flash:cloud` -> control 2, tie 1;
  combined -> **control 3, treatment 1, tie 2**. No unparsable answers.
- **Human adjudication of the deciding defects** (the legacy judge's own
  honest limit: "a FAILED here deserves a human glance before acting on
  it"):
  - cell-02: the INT8 sign reads "Eubacia" (coherent lettering); the FP8
    sign reads "Caln Pcanare" (garbled pseudo-text). **The FP8 arm loses.**
  - cell-03: the FP8 arm carries an isolated dark diagonal streak on the
    lower snow slope; the INT8 slope is clean. **The FP8 arm loses.**
  - cell-01: the single treatment vote rests on deepseek reading the INT8
    web's dark hub as a "malformed blob"; the second judge called both
    halves clean, and that dark hub reads as a small spider sitting on the
    web. **Best read: tie.** The treatment's one win does not survive
    adjudication.
  - Adjudicated tally: **INT8 2, FP8 0, tie 1.**
- **Correction to this document's earlier T6 claim.** It said cell-02
  carried gibberish signage in BOTH arms and was therefore "not a
  discriminator". That is wrong: the INT8 sign is coherent lettering and
  the gibberish is specific to the FP8 arm. The claim came from a parent's
  own vision pass that did not read the signage closely.
- **What this does and does not change.** It does not change speed (FP8
  -15...-42 %) or stability (FP8 -26 % VRAM, 10x gentler swap): those
  measurements are untouched. It closes the quality axis, and it closes it
  AGAINST the FP8 candidate on objective craft defects, with both deciding
  artifacts verified by eye. It still does NOT say which arm is closer to
  the BF16 truth: there is no BF16 reference on this machine, and the
  rubric measures defects, not fidelity.
- **Power.** n = 3 cells, 2 judges, and one artifact decides a cell. The
  difference is real but small in magnitude: 2 of 3 cells, one defect each.
- **Nothing in production was changed.** The operator's 2026-11-14 ruling
  (FP8 as the production default, INT8 as the declared fallback) stands
  until the operator says otherwise; this section is evidence, not a
  decision.
