# P10 / B3 Stage 2 Test Sheet (pre-execution, no integration)

**Status:** test plan / capture ledger only. No asset, no adapter, no guard, no source change.  
**Date:** 2026-11-18  
**Purpose:** Define the exact cheap, reproducible Stage 2 sequence that can either promote or eliminate a candidate, while preserving the project's existing VRAM/LoRA headroom gate.

## 1. Scope boundary

Stage 2 is allowed to create a temporary harness outside the project tree (`/tmp/opencode/p10-stage2/`); download the single pinned asset plus configs of one candidate at a time; record metadata, VRAM, wall time, generated artifacts and LoRA behavior; and produce a report.

Stage 2 is not allowed to place the asset in `model/assets/`; change `model/entry.yaml`, `model/entries/*.yaml`, `adapter.py`, or any adapter; add a route, a guard, a UI line, or a test method; depend on Hub lookups after asset acquisition; or reuse the live `run/server.lock` in a way that introduces a second owner.

## 2. Shared rules for every candidate

1. One candidate per run (no concurrent family changes).
2. One pinned file + one config set per run.
3. No output size above the candidate's declared box unless explicitly testing a residual path.
4. No LoRA result is counted unless it shows bytes or pixels changed.
5. No report claims a product success unless all three LoRA probes pass.
6. No memory claim is valid unless it includes a defined workload label: `load_only`, `warm_render`, `single_lora`, or `multi_lora`.

## 3. Minimum required measurement fields

Record all of the following into `stage2-run-report.md`:

- candidate name
- date of docs lock
- architecture label (single-file, diffusers fp16, etc.)
- exact source URL
- exact pin / revision / digest
- all downloaded artifact paths and checksums
- loader path (direct, staged, or third-party)
- target resolution and aspect
- fixed prompt used
- fixed seed
- `steps` used
- `cfg / guidance scale` used
- load-only VRAM peak
- warm render VRAM peak
- LoRA-inclusive peak (single + optional stack)
- wall clock load
- wall clock render
- resulting image artifact path
- load status
- render status
- whether negative prompt materially changed output
- whether CFG materially changed output
- whether LoRA key targets loaded
- whether LoRA non-zero effect was observed
- whether cleanup succeeded

## 4. Fixed comparison prompt and seed

Use a fixed style known in the project.

- **Prompt:** `a lighthouse at dusk, calm sea, dramatic sky, no text`
- **Seed:** 7
- **Primary resolution:** 1280 × 720
- **Fallback resolution set:** 1024², 768², 512² only if safety path changes.

**Reason:** this allows direct comparison with the surviving project anchors.

## 5. Fixed baseline anchor for comparison

Every candidate run must compare against one known project anchor already measured:

- Z-Image runtime: default/L8 baseline around `4815 MiB` relevant peak, default 1280×720.
- FLUX.2 Klein: measured near `4305 MiB`.

If no anchor page is rerun in the same Stage 2 physical session, cite the prior anchor as `anchor-derived`.

## 6. Candidate-by-candidate Stage 2 sheet

### 6.1 Segmind-Vega
Status at entry: current primary #1 after SSD-1B VRAM elimination.

Required assets: `model_index.json`, `scheduler/scheduler_config.json`, `text_encoder/config.json`, `text_encoder_2/config.json`, `tokenizer/*`, `tokenizer_2/*`, `vae/config.json`, `segmind-vega.safetensors` = 3,293,395,670 bytes

Required probes:
- `load_only`
- `warm_render (1280x720)`
- `negative_prompt_probe (same prompt with neg phrase vs without)`
- L1 LoRA key-shape probe
- L2 non-zero effect
- L3 3 distinct LoRA stack

Acceptance conditions:
- load-only peak <= 5.5 GiB
- warm render peak <= 6.0 GiB
- negative prompt visibly changes semantic output
- L1 emitted stable target family
- L2 has measured pixel or hash difference
- L3 finishes without silent drop

Known risks: aggressive `[1,1,2]` pruning, possible peak below published in 1024², poorer direct match to random SDXL LoRAs, docs ambiguity around negative guidance.

### 6.2 SDXL canonical base
Status at entry: compatibility baseline only.

Required asset: canonical single-file only `6,939,220,250` bytes plus one full config / tokenizer deck. No repository-wide clone.

Required probes:
- `load_only`
- `warm_render`
- `negative_prompt_probe`
- `cfg_probe` at recommended guidance
- L1, L2, L3 with at least:
  - 1 SDXL base LoRA
  - 1 SDXL realistic style LoRA
  - 1 community high-cap LoRA

Acceptance conditions:
- load-only under 5.5 GiB
- warm render under 6.5 GiB
- direct L1-L3 alignment
- no staged weight leak

Known risk: high memory pressure at 1024², OpenRAIL license restrictions, giant full-repo complexity if mis-scoped.

### 6.3 Hyper-SD (adapter, not a foundation)
Status at entry: optional seat only.

Required asset: Hyper-SD LoRA files only, with the exact base model already present and staged safely. No standalone foundation path.

Required probes:
- adapter key probe
- scheduler variant probe (1 vs 2 vs 4 vs 8), plus eta threshold if relevant
- one same-prompt / same-selarınd render with and without adapter
- one ControlNet or style extension if possible

Acceptance conditions:
- base/adapter pair remains under measured load
- scheduler problem is captured without guessing
- no patch requires editing `render.py` / `server.py` outside a documented seam
- if adapter needs user-side config, it is recorded rather than implicitly assumed

### 6.4 SDXL-Lightning
Status at entry: speed comparator only.

Required asset: one pinned `~6.94GB` base fp16 and the LoRA speed variant.

Required probes:
- negative prompt probe if recommended
- CFG probe
- 1-step vs 4-step output report
- L1, L2, L3 if extra headroom is available

Acceptance conditions:
- no hidden negative-prompt refusal when the README says otherwise
- quality gap versus anchor is stated explicitly
- cleanup stays clean

### 6.5 DreamShaper XL non-turbo base
Status at entry: style / ecosystem comparator only.

Required asset: one pinned single-file `6.94GB`, with configs only.

Required probes:
- load/warm
- style similarity vs current anchor
- community LoRA map
- explicit commercial-boundary statement

Acceptance conditions:
- no hidden commercial misuse against Turbo caveat
- adapter or adapter-like burden remains manageable
- LoRA mapping is better than pruned candidates

## 7. LoRA probe rules for every candidate

### L1 key probe
- instantiate loader in pure read-only mode
- output whether target keys map 1-to-1 or partial
- do not reinterpret missing targets as acceptable

### L2 non-zero effect
- render one prompt with parameter = 0 (baseline)
- render same prompt with parameter > 0
- compare selected hash or pixel crop metric
- if the hashes are equal, fail as non-effect
- non-effect is an explicit elimination outcome

### L3 stack
- use three distinct LoRA files, not hardlinks
- include one small LoRA and one ~200MB practical one
- preserve exact peak per stack depth
- record weak margins as "partial" rather than absorbing them

## 8. Decision and kill outcomes (tight, bounded)

### Pass
- all hard filters pass
- load peak recorded
- warm render peak recorded
- at least one productive L1/L2/L3 behavior recorded
- cleanup clean
- geometry leaves minimum inferred headroom (>= 2 LoRAs), based on measured margin

### Partial / retry once
- L2 or L3 barely exceeded
- load VRAM borderline but cleanup clean
- structural mismatch with a still-bounded key remap path

### Kill / reject at Stage 2
- load-only VRAM over safe bound
- warm render over safe bound
- failure to expose negative prompt when documented
- LoRA key mismatch not bounded
- adapter remap requires direct modification to `render.py` / `server.py` outside a documented seam
- unresolvable commercial ambiguity
- candidate does not produce anchor-relative value or clear value-add

## 9. Required report artifact for every candidate

Each candidate must produce:

- `stage2-run-report.md`
- in `/tmp/opencode/p10-stage2/<candidate>/`
- plus separated artifact captures under `evidence/`
- no imports from project tree
- no system-wide tests
- no undocumented numeric confidence

## 10. Stage 2 hard stop rule

Stage 2 stops automatically if either:
- B3/P10 would require changing `server.py` / `render.py` outside a documented seam, or
- candidate license is effectively restricted, or
- candidate introduces an unremovable external runtime (Hub/network/non-tree source), or
- a second model process is needed.

When any is hit, abort, record it, and return to the ledger.

## 11. Stage 2 entry / exit rule

Candidate can enter Adapter drafting only if:
- Stage 2 passes on all four report elements, **or**
- operator explicitly accepts "research adapter" tagging with bounded usage.

No candidate enters P10 by momentum alone.

## 12. Close-to-next-interaction

When Stage 2 returns, update:
- elimination ledger status
- research docs with exact numerical and semantic outcomes
- changelog line in one work-unit entry

At that point, either:
- the candidate enters Adapter drafting, or
- the candidate is eliminated and the next candidate in this ledger order is the replacement.

### Stage 2 order allowed (decided by this ledger)

1. Segmind-Vega
2. Hyper-SD (only if a permitted base exists)
3. SDXL canonical (license-controlled)
4. SDXL-Lightning
5. DreamShaper XL non-turbo (optional)

No Stage 2 step is authorized for Category 2 or 3 until Category 1 is cleared or explicitly waived.
EOF