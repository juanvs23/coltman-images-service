# P10 / B3 — Temporary Viable Candidate Elimination Ledger

**Status:** research ledger only. Live working document for iterative elimination; not an implementation artifact.  
**Confidence scope:** configuration, licensing and published footprint only until Stage 2+ is intentionally promoted.  
**Rule under this ledger:** no model is considered "selected" until it survives the interaction with its hard filters and evidence ladder.  
**Operational constraint:** candidates may be added temporarily and removed by explicit interaction; removal reasons must be retained in the "Eliminated" appendix.

## 1. Purpose

This ledger exists to solve the selection problem without losing trace.  
P10 cannot start until B3 is described as an evidence-based candidate boundary. This document is the machine-readable record of:

- who is still in the race,
- why each candidate was retained or removed,
- which exact gate still lacks evidence,
- what the next cheapest rejection is.

This file is intentionally short on narrative and long on bounded facts.

## 2. Hard filter (no candidate passes without all six)

1. **Commercial posture:** Apache 2.0 / MIT preferred, or OpenRAIL with license text and commercial boundary explicitly acceptable.
2. **No disguised asset explosion:** the practical runtime price must be the single-file pinned bytes + declared sidecars, not the whole repository clone.
3. **Memory fit with LoRA headroom:** measured peak must leave at least one validated LoRA-loading + render margin, not rationalized post hoc.
4. **Community stability:** at least a published paper, multiple adapters, or a maintained toolchain.
5. **LoRA compatibility or bounded remap:** either direct LoRA applicability or a remap of acceptable complexity.
6. **Reversibility / no core breakage:** no widening of `entry.accepts()`, no `server.py`/`render.py` hidden change.

Any candidate failing (1), (2), or (3) on observed evidence is removed, not debated at length.

## 3A. Dependencies to review (non-foundational / accelerator-only)

This section is for code/adapter layers, *not* B3 entry decisions.

- **Hyper-SD (support only)**
  - Role: accelerator / LoRA-friendly booster over an already compliant base.
  - Dependency, not foundation
  - Needs:
    - exact base, active and licensed
    - 1-8 step scheduler handling
    - lawful adapter-validation gate
    - key matching over the base's native layers
  - Does **not** solve:
    - license conflict
    - VRAM constraint
    - free base missing.
  - Status: retained for later adapter review only.


## 3. Current surviving candidates

### Tier 1 — Apache-first, license-secure

#### C1 — Segmind SSD-1B [ELIMINATED 2026-11-18]
- **License:** Apache 2.0
- **Single-file price:** 4,465,671,506 bytes (~4.46–4.47 GB)
- **Declared host memory pattern:** vendor idle 5,338 MiB, inference 12,780 MiB (`1024²`)
- **Public LoRA evidence:** upstream training support + published LCM LoRA adapter (`latent-consistency/lcm-lora-ssd-1b`) + DreamBooth community example
- **LoRA compatibility status:** provisional, needs key-level probe
- **Community:** 27,949 downloads, 851 likes, paper/arXiv, implementation examples
- **Status:** eliminated — vendor VRAM peak exceeds the 720p + LoRA-headroom rule
- **Next cheapest rejection test:** none; removed from candidate field
- **Hard-filter note:** passes license and ecosystem, fails the memory/headroom gate as published

#### C2 — Segmind-Vega
- **License:** Apache 2.0
- **Single-file price:** 3,293,395,670 bytes (~3.29 GB)
- **Declared host memory pattern:** expected < SSD-1B
- **Public LoRA evidence:** shallower than SSD-1B; training instructions also exist upstream, but fewer targeted ecosystem artifacts
- **LoRA compatibility status:** highest risk due highest transformer-block pruning
- **Community:** 5,026 downloads, 132 likes, technically defined, lower ecosystem depth
- **Status:** retained, endgame-only
- **Next cheapest rejection test:** architecture key probe
- **Hard-filter note:** passes (1), (2), (4 lower group), unproven (3), very unproven (5)

### Tier 2 — Compatibility baseline (not preferred for license purity)

#### C3 — SDXL canonical single-file (baseline)
- **License:** `openrail++` / OpenRAIL-M (commercial under acceptable-use, not pure Apache-clear)
- **Single-file price:** 6,939,220,250 bytes (~6.94 GB)
- **Declared host memory pattern:** OpenVINO-mode path reports 53 GB at 1024² on that backend
- **Community:** enormous (4.79M downloads, strong cross-jury)
- **LoRA compatibility:** best nominal compatibility
- **Status:** retained as compatibility and license comparator
- **Next cheapest rejection test:** only if operator accepts OpenRAIL licensing or it serves as baseline for internal comparison

#### C3A — SDXL canonical `Q8_0` GGUF
- **Source:** `kostakoff/stable-diffusion-xl-base-1.0-GGUF`
- **Artifact:** `sd_xl_base_1.0_0_Q8_0.gguf`
- **Disk cost:** **4,180,186,816 bytes ≈ 4.18 GB**
- **Runtime:** direct `stable-diffusion.cpp` single-file
- **Sidecars required:** none for the model itself
- **License:** inherited **OpenRAIL++**
- **Quality posture:** best balance among the verified GGUF variants
- **Memory caveat:** VAE decoder can still demand ~10 GB VRAM if left on GPU; `--vae-on-cpu` is recommended
- **Status:** candidate — retained for Stage 2
- **Next cheapest rejection test:** `load_only` + `warm_render` at 1280×720 with one LoRA and a 3-LoRA stack

#### C3B — SDXL canonical `Q4_K` GGUF
- **Source:** `kostakoff/stable-diffusion-xl-base-1.0-GGUF`
- **Artifact:** `sd_xl_base_1.0_0_Q4_K.gguf`
- **Disk cost:** **2,797,752,960 bytes ≈ 2.80 GB**
- **Runtime:** direct `stable-diffusion.cpp` single-file
- **Sidecars required:** none for the model itself
- **License:** inherited **OpenRAIL++**
- **Quality posture:** lighter than Q8_0, with a higher expected quality loss
- **Memory caveat:** same VAE-decoder constraint as Q8_0; `--vae-on-cpu` is recommended
- **Status:** candidate — retained as the low-disk hedge
- **Next cheapest rejection test:** same as Q8_0, plus an explicit quality comparison against Q8_0

#### C4 — Hyper-SD (adapter, not a foundation by itself)
- **License:** ByteDance research code + base license
- **Asset price:** LoRA-sized only (typically low hundreds of MBs to ~100MB), but base SDXL is the real asset
- **Memory:** itself light, base model is true cost
- **Community:** moderate-high
- **LoRA compatibility:** explicit, built as LoRA and stackable with itself
- **Status:** retained as accelerator, not as candidate foundation
- **Next cheapest rejection test:** none unless a use case requires 1-8 step generation with no base isolation

#### C5 — SDXL-Lightning (ByteDance)
- **License:** `openrail++`
- **Asset price:** ~6.94 GB; recommended by the project for 4-step use and CFG 1-2
- **Memory:** OFT-baseline but FastSSDs show lower (project project lore: 4GB-4GB at 4-step)
- **Community:** moderate-high
- **LoRA compatibility:** good nominal compatibility
- **Status:** retained for quality/speed contrast only
- **Next cheapest rejection test:** compare against SSD candidates if the use case is speed, not compatibility

### Tier 3 — retained as excluded policy / weak-local review only

#### C6 — DreamShaper XL (non-turbo base family only) [ELIMINATED 2026-11-18 — family excluded by operator]
- **License:** OpenRAIL-M (Turbo variant carries an upstream noncommercial caveat)
- **Asset price:** ~6.94 GB
- **Community:** very high
- **LoRA compatibility:** expected robust
- **Status:** eliminated — the whole DreamShaper family is out of the candidate field by operator instruction
- **Next cheapest rejection test:** none; removed from candidate field

#### C7 — Community GGUF `v2-turbo` [ELIMINATED 2026-11-18]
- **License:** inherited from upstream Lykon/OpenRAIL
- **Asset price:** Q8 4.18 GB / Q4 2.80 GB
- **Memory:** practical low footprint on `sd.cpp`
- **Community:** low-moderate
- **LoRA compatibility:** same as upstream but uncertain provenance
- **Status:** held as research-only
- **Next cheapest rejection test:** license boundary statement

#### C8 — FLUX.2 Base 4B (future fine-tune boundary, not runtime candidate today)
- **License:** Apache 2.0
- **Asset price:** future (models often heavier)
- **Memory:** Base typically larger and 9.2 GiB; heavier
- **LoRA:** excellent official fine-tuning/openness
- **Status:** retained as future anchor and license comparator
- **Next cheapest rejection test:** none needed for now (not part of near-term B3)

#### C9 — MOSS-Image Base/SFT
- **License:** Apache 2.0
- **Operational disk (Comfy-Org INT8 path):** **~15.4 GB** (DiT 5.41 GB + Qwen3.5-9B encoder 9.75 GB + VAE 0.25 GB)
- **Repo total:** ~27 GB, but only the 3 operational files are needed
- **Quantized variants:** Q8_0 ~5.5–5.7 GB, Q4_K_M ~3.2–3.7 GB — **DiT only**
- **Memory:** 5B DiT + 9B text encoder; likely needs offload on 8 GB
- **LoRA:** Base is explicitly intended for LoRA training
- **Community:** strong, recent, active ComfyUI support
- **Status:** candidate — retained
- **Next cheapest rejection test:** load-only VRAM, 720p render, 1-LoRA non-zero effect

#### C10 — Lumina-Image 2.0 [ELIMINATED 2026-11-18 — user request]
- **License:** Apache 2.0
- **Operational disk (bf16):** **~10.8 GB** (DiT 5.22 GB + Gemma-2-2B 5.23 GB + VAE 0.34 GB)
- **Quantized path:** FP8 DiT **~2.61 GB**, INT8 DiT **~2.88 GB**; text encoder FP8 **~3.2 GB**
- **Memory:** 2.6B DiT; most likely of the three to fit 8 GB with offload
- **LoRA:** supported
- **Community:** moderate; smaller ecosystem than MOSS/SDXL
- **Status:** eliminated — removed from candidate field by user instruction
- **Next cheapest rejection test:** none; retained only as archived research reference

#### C11 — Kandinsky 3.1 [ELIMINATED 2026-11-18 — user request]
- **License:** Apache 2.0
- **Operational disk:** **~48 GB** (U-Net 12.15 GB + Flan-UL2 encoder ~34.9 GB + MoVQ 1.08 GB)
- **Quantized variants:** **none verified**; Flash only reduces steps, not size
- **Memory:** heavy; unlikely to fit 8 GB with LoRA headroom
- **LoRA:** moderate ecosystem
- **Community:** moderate
- **Status:** eliminated — removed from candidate field by user instruction
- **Next cheapest rejection test:** none; retained only as archived research reference

## 4. Eliminated candidates (with reason)

### E1 — FLUX.2 [klein] 4B (runtime anchor)
- **Eliminated reason:** already the served anchor / current promoted path
- Open-source? Apache 2.0. Still, it is in the system and therefore not a candidate to add.

### E2 — Z-Image Turbo/Base
- **Eliminated reason:** already in the system (installed anchor)
- Open-source? Apache 2.0. It is already local and therefore not a B3 candidate to introduce.

### E3 — DreamShaper XL Turbo variant
- **Eliminated reason:** licencing, Turbo variant explicitly noncommercial in its guidance
- Remaining non-turbo base can stay for ecosystem style comparisons and cost trade-offs.

### E4 — SDXL Turbo (Stability)
- **Eliminated reason:** explicit noncommercial restriction
- It is low-cost in memory and high-speed but useless as a commercial default.

### E5 — Community GGUF `v2-turbo` selected for production use today
- **Eliminated reason:** license and provenance not sufficiently clean for a commercial default
- It remains interesting in cost trade-offs but not as a public production candidate.

## 5. Elimination interaction skeleton (append as we go)

Maintain this table exactly as we remove a candidate. Empty cells mean "not asked yet."

| Candidate | Elimination round | Removed by | Reason text |
|---|---|---|---|
| FLUX.2 Klein 4B | fixed | system anchor | Already in runtime |
| Z-Image | fixed | system anchor | Already in runtime/blocker outcome |
| DreamShaper XL Turbo | round 1 candidate | user/team definition | noncommercial clause |
| Community GGUF v2-turbo | round 1 candidate | risk policy | OpenRAIL/provenance risk |
| SDXL Turbo | round 1 candidate | risk policy | noncommercial |

## 6. Current decision path (temporary)

The default route, unless the research and lifecycle push another direction:

1. Test `SSD-1B` first.
2. Fallback only when:
   - memory ceiling fails (very likely with 12GB vector), or
   - LoRA key probe fails irrecoverably.
3. If fallback triggers, the top successor is:
   - `SSD-Vega` (memory hedge)
   - `SDXL canonical` (compatibility baseline)
   - else exit B3 as not justified.
4. B3 remains open and P10 remains planned until something passes and is integrated.

## 7. Optional annotation symbols

- `[L]` — license clearance pending
- `[M]` — memory verification pending
- `[K]` — key probe pending
- `[C]` — community evidence sufficient
- `[R]` — reversible temporarily

## 8. Permit Note

This ledger can be updated only through the interaction rule you defined: one removal per turn or one bounded addition per turn, with explicit reasoning text.

## 9. Memory and LoRA Headroom (explicit runtime law)

This section exists because "fits the model" is **not** the same as "fits the model while leaving a LoRA budget intact."

### 9.1 Current observed project law (not rhetoric)

| Quantity | Observed or declared value in this project |
|---|---:|
| Torch-usable card | 7,857 MiB |
| LoRA budget (host declaration) | 3,200 MiB |
| Z-Image render peak at default box and default step count | ~4,815 MiB |
| Single 325 MB LoRA marginal memory cost | ~313 MiB + ~1.5 s wall |
| Linear region for distinct LoRAs | 1–11, then plateau at ~7.6 GiB while wall doubles hard |
| Refusal quality rule | a request doing nothing (silently ignored LoRA) is worse than a refusal |

### 9.2 What a candidate is allowed to consume

A viable candidate must leave at least:

1. one base-request peak that is lower than the card’s usable memory after current service overhead,
2. at least one LoRA selection with visible non-zero effect,
3. explicit headroom for a small controlled stack (one 325 MB LoRA = ~313 MiB marginal),
4. no event where the inference load goes so close to the ceiling that the LoRA load silently fails.
5. any LoRA inserted must not require a hidden base-adapter switch, because then it is a second model under the same name.

### 9.3 Candidate memory/LoRA heads (derived, not hardware-confirmed)

| Candidate | Base memory signal | Est. residual headroom after base peak (as published) | LoRA practical risk | Read |
|---|---|---:|---|---|
| SSD-1B | vendor inference peak 12,780 MiB @ 1024² vs idle 5,338 MiB | negative if taken literally at same scale, unless our staged stack proves materially lower | **Highest real risk**: shape mismatch + peak collision | `V303` is only worthwhile if Stage 2 shows a materially lower staged peak or target scale changes |
| Segmind-Vega | estimated < SSD-1B | may improve, still unverified | high | next hedge, mostly a memory play |
| SDXL base | OpenVINO 1024² claim (~53 GB); native fp16 claim lower but conflicts | very tight | low if run properly | excellent LoRA baseline, bad headroom |
| Hyper-SD | itself light, base model is truth | unchanged base cost | guarded | good only when a base already fits and LoRA ratio target remains |
| Community GGUF | Q8 4.18GB, Q4 2.8GB practical on `sd.cpp`; native 5-7GB region | uncertain with LoRAs | uncertain/untruncated | may win on disk, not confidence |
| DreamShaper XL base | project peak ~5.3 GiB staged measurement; whole fp16 6.94GB | tight-to-warning, but measured narrower local | good nominal compatibility | license probe only |

### 9.4 Candidate-specific LoRA behavior lines

- **SSD-1B**: explicit upstream LoRA support and published training path; pruning means not every SDXL LoRA can be a direct target call.
- **Segmind-Vega**: even more pruning; LoRA support is conceivable but less defended publicly.
- **SDXL base**: best direct LoRA world, highest compatibility risk accepted.
- **Hyper-SD**: arguably the clearest LoRA-first candidate, but only if the base model beneath it is itself allowed for the candidate cluster.
- **Community GGUF**: no direct evidence that arbitrary SDXL LoRA applies cleanly without proving target names first; this is a framing issue, not proven.
- **DreamShaper XL**: strong ecosystem and LORA adaptation path; license and Turbo provenance complicate public use.

### 9.5 Hard rule derived from the current system

No B3 candidate that:

1. does not carry at least 1–2 LoRA selections in Stage 2+, or
2. silently leaves the LoRA count hollow, can progress.

That means every candidate retained gets three machine probes:
- LoRA L1 (name probe)
- LoRA L2 (effect probe)
- LoRA L3 (non-zero class probe)

Failure on any LoRA matrix step kills the candidate. Pass on all three gates the model into P10.

### 9.6 Immediate operating rule

For the remaining candidates:
- `SSD-1B`: number 1 for license + data scale
- `Vega`: number 2 only if `SSD-1B` fails memory
- `SDXL base`: number 3 only as compatibility and license comparator
- `Vega` and remaining candidates may be removed by one at a time at your explicit request
- `FLUX`, `Z-Image` are anchors and no longer candidates for replacement
## 10. Elimination applied — 2026-11-18 (live interaction)

### Removed from candidate field:
- **Community GGUF `v2-turbo` (`off-grid-ai/dreamshaper-xl-v2-turbo-GGUF`)**
  - **Why removed**: It is just a community re-export of `Lykon/dreamshaper-xl-v2-turbo`, carrying upstream `OpenRAIL++` and DreamShaper Turbo noncommercial caveat. Not a clean derivative.
  - **Memory attractive, but not enough**: Q8 4.18GB / Q4 2.8GB, but no certified LoRA target behavior, no certified provenance, and a documentation quality gap.
  - **Result**: off the commercial candidate shortlist; kept only in archived appendix as `research-only`.

### Live post-removal state
After this explicit interaction, the remaining ladder is unchanged except the removal:
1. SSD-1B
2. SSD-Vega (candidate-only hedge)
3. SDXL canonical (license/license-copy comparator)
4. Hyper-SD (accelerator-oriented)
5. SDXL-Lightning (speed comparator)
6. DreamShaper XL non-turbo base (ecosystem / style reference)
7. eliminate has been formalized.


## 11. Elimination applied — 2026-11-18 (live interaction, VRAM gate)

### Removed from candidate field:
- **Segmind SSD-1B**
  - Removed because its vendor-published inference peak is **12,780 MiB at 1024²**, far above the **7,857 MiB** usable host ceiling and the user's stated minimal requirement of a safe 720p path with LoRA headroom.
  - The staged-first-lane requirement has not yet disproven the peak, and the current projected residual on `1280x720` does not leave a safe ~2.5 GiB LoRA margin.
  - **Result**: dropped as a primary candidate; retained only as `research appendix / license-contract reference` when an offload or lower-resolution proof exists.

### Live post-removal state
Students after SSD-1B hard-dropped:
1. Segmind-Vega (current primary)
2. SDXL canonical (compat/license baseline)
3. Hyper-SD (accelerator, only if a compliant base fits)
4. SDXL-Lightning (speed comparator)
5. Vega can now only be challenged by true headroom evidence; if it fails, the next practical route is Hyper-SD over a permitted base, not numeric "auto promote".

## 12. Elimination applied — 2026-11-18 (live interaction, family exclusion)

### Removed from candidate field:
- **DreamShaper XL family — base, Lightning, Turbo, SFW and all derivatives**
  - **Why removed**: operator instruction — no DreamShaper-family model is to remain in the candidate list.
  - **Scope**: base alpha2/xl1.0, Lightning, Turbo, SFW, and third-party conversions.
  - **Result**: out of the B3 candidate field; retained only as archived research references.



## 13. Elimination applied — 2026-11-18 (live interaction, additional candidate removal)

### Removed from candidate field:
- **Lumina-Image 2.0**
  - **Why removed:** user instruction.
  - **Final documented facts remain archived for reference only.**
- **Kandinsky 3.1**
  - **Why removed:** user instruction.
  - **Final documented facts remain archived for reference only.**

### Live candidate field after this removal
1. Segmind-Vega (current primary #1)
2. SDXL canonical Q8_0 GGUF
3. SDXL canonical Q4_K GGUF
4. SDXL-Lightning (speed comparator)
5. Hyper-SD (support / accelerator only)

## 14. Removal of the archive candidates
The following candidates remain documented in their respective reports only, and are **not** in the running candidate pool unless explicitly re-added:
- DreamShaper XL family (already removed)
- SSD-1B (already removed)
- Community GGUF v2-turbo (already removed)
- Lumina-Image 2.0 (removed now, consult `docs/research/reports` if needed)
- Kandinsky 3.1 (removed now, consult `docs/research/reports` if needed)

This means the runway is currently reduced to three active runtime-compliant candidates:
- Segmind-Vega
- SDXL canonical Q8_0 GGUF
- SDXL canonical Q4_K GGUF
with SDXL-Lightning as a speed comparator and Hyper-SD as support.

## 15. Stage 2 executed on Segmind-Vega — 2026-11-18 (GGUF route)

### Correction to a previous claim
The earlier statement that **no GGUF conversion of Segmind-Vega exists** was **wrong**. A third-party conversion exists and was found through a structured query of the Hugging Face API (model tree + tag search), not through web search: `vonjack/hyper-sd-v1_5-segmind-vegart-gguf` → `segmind-vega-q8_0.gguf`. Full evidence: `p10-b3-segmind-vega-gguf-stage2-report.md`.

### Artifacts
- `segmind-vega-q8_0.gguf` — `2,132,007,776 bytes`
- LFS SHA-256 `189bbfe7b33e2a55c8f0f631e36e1e0b96d5ee3e96d595f9f2e1a354c51841a1` — **verified locally**
- Complete model in one file: UNet (564 tensors) + CLIP-L (196) + CLIP-G (517) + VAE (248); 1,379 Q8_0 + 146 F16; **zero GGUF metadata**
- Third-party repo: 246 downloads, 4 likes, last updated 2024-05-07, README of 31 bytes — **community below the "medium-high, stable" bar; provenance not documented**

### Measured on the project's own runtime (`sd.cpp` @ `532d2c1`, `sd-cli`)
The runtime detects the model with no external hints: `Version: SDXL (Vega)`.

| Profile | Resolution requested | Rendered | exit | Wall | Peak GPU | LoRA budget (3.200 MiB) |
|---|---|---|---:|---:|---:|---|
| resident | 1280×720 | **1280×768** | 0 | 5,92 s | 6.482 MiB | not met (~1.706 MiB free) |
| `--offload-to-cpu` | 1280×720 | 1280×768 | 0 | 6,10 s | 4.602 MiB | met (~3.586 MiB free) |
| resident | 1024×1024 | 1024×1024 | 0 | 6,16 s | 6.754 MiB | not met (~1.434 MiB free) |
| `--offload-to-cpu` | 1024×1024 | 1024×1024 | 0 | 6,29 s | **4.874 MiB** | **met (~3.314 MiB free)** |

The runtime rounds the request up to a multiple of 64, so a "720p" request on this path is **1280×768**, not 1280×720.

### Where the peak comes from
Weights occupy only 2.041 MiB in VRAM. The **VAE decoder compute buffer is 3.600 MiB** and the UNet buffer 461 MiB. **The peak is the VAE decode, not the weights.** This is the same risk already recorded for canonical SDXL.

### What did NOT change
- The fp16/diffusers measurement stays valid **for the fp16 path**: 6.724 MiB peak and an OOM 18 MiB short of the render at 1280×720.
- Quantizing alone rescued nothing: the GGUF resident peak is only **242 MiB** below the diffusers fp16 peak. What made the render possible is **`sd.cpp`'s memory layout**, not the smaller file.

### Quality: corrected on the same day
The first quality read in this round used **4 steps and CFG 2.0**. The Vega model card requires **CFG ≈ 9.0 with a negative prompt**; 4 steps with CFG 2 is the regime of an LCM (VegaRT), not of the base checkpoint. That configuration produced a flat, under-converged image and the wrong conclusion.

Re-measured properly — prompt is the project's canonical bar/poker group scene, negative prompt from the card, **CFG 9.0, 25 steps, three seeds (7, 1234, 42), 1024×1024 and 1280×768**:

- **Photorealism: good.** Skin, cloth, wood, glass and tungsten light read as photograph, not illustration. Lighting is coherent and the requested shallow depth of field actually appears.
- **Faces: solid** across all three seeds.
- **Hands: the consistent failure.** Every one of the four images has at least one hand with fused fingers, missing articulation, or no discernible hand shape at all.
- **Subject count: fails.** The prompt asks for six players plus a bartender; three, four or five are produced, never seven.
- **Costume collapse:** almost every figure wears the white shirt the prompt assigns to the bartender, because the role attribute spreads to the scene.
- **Physical coherence: intermittent failure.** One seed renders a **glass floating in mid-air** with no hand holding it.
- **Card faces: illegible**, exactly as the card warns about text.
- **Seed consistency: passes** — same visual language and finish level across seeds.
- **Contrast:** luminance σ goes from **29,1** (CFG 2 / 4 steps) to **66,0–67,7** (CFG 9 / 25 steps). The earlier "low contrast" was the bad configuration, not the model.

The card's own two warnings both reproduce: human depiction is the weak spot, and complex compositions lose fidelity.

**Cost of the honest configuration:** 16,4–16,6 s at 1024×1024 (vs 6,2 s at 4 steps) at a **6.766 MiB** peak — the peak does **not** grow with step count, it stays bound by the 3.600 MiB VAE decoder buffer. With `--offload-to-cpu`: 16,6 s at a **4.886 MiB** peak and a **bit-identical** image (0 of 1.048.576 pixels differ).

Full evidence: `p10-b3-segmind-vega-quality-group-test.md`.

### Live candidate field after this Stage 2
1. **Segmind-Vega, via third-party Q8_0 GGUF** — current primary #1, **pending L1/L2/L3**
2. SDXL canonical Q8_0 GGUF
3. SDXL canonical Q4_K GGUF
4. SDXL-Lightning (speed comparator)
5. Hyper-SD (support / accelerator only)

**Only the `--offload-to-cpu` profile at 1024×1024 meets the VRAM + LoRA-budget floor today.** LoRA L1/L2/L3 have **not** been run: L2 (non-null effect) is the mandatory kill gate and it is still open.

### Collateral finding
The same third-party repo carries `segmind-vegart-q8_0.gguf` — **identical byte size** (`2,132,007,776`) and **identical tensor structure** (1,525 tensors) to the Vega file. It is most likely Vega with the VegaRT LCM-LoRA merged in (1–4 step variant). **Not downloaded, not measured, not rendered.** It inherits the same VAE-decoder memory risk.

## 16. Elimination applied — 2026-11-18 (Segmind-Vega, operator decision after the quality test)

### Removed from candidate field:
- **Segmind-Vega — both routes.**
  - **Why removed:** operator decision, taken after the serious group-of-people test in `p10-b3-segmind-vega-quality-group-test.md`. The evidence it rests on: **hands fail in every one of the four images** (fused fingers, missing articulation, or no discernible hand shape), the **subject count misses** (six players plus a bartender asked for; three to five produced), one seed renders a **glass floating in mid-air**, and card faces are illegible. Photorealism and faces were good; the failures are in the axes this use needs.
  - **What this closes:** with Vega out, the **LoRA L1/L2/L3 gate is dropped** — it was the only thing that could still have made Vega a pass, and it was never run. That is recorded as a gate closed by decision, not as a gate passed.
  - **Weights deleted:** `segmind-vega-q8_0.gguf` (`2,132,007,776 B`) and, earlier the same day, the fp16 `segmind-vega.safetensors` (`3,293,395,670 B`). **5,4 GB reclaimed in total.** No model weights of this candidate remain on disk.
  - **What is kept:** the **11 renders, 15 `sd-cli` logs, `stage2-gguf-report.md`, `stage2_gguf_probe.py`, `stage2-run-report.md`** and the fp16 configs/tokenizers. The evidence stays so every number and every defect claim in the reports remains checkable; only the weights are gone, and they are recoverable from the pinned LFS SHA-256 `189bbfe7b33e2a55c8f0f631e36e1e0b96d5ee3e96d595f9f2e1a354c51841a1`.
  - **Retained as:** archived research reference — the Vega reports stay as the record of a measured rejection, not as a recommendation.

### Live candidate field after this elimination

1. **MOSS-Image Base/SFT (C9)** — Apache 2.0, `~15,4 GB` operational on the INT8 path, **candidate: retained**. This entry had been missing from the field lists in §13 and §15; it is restored here, which is a correction of those lists rather than a new candidate.
2. **SDXL canonical Q8_0 GGUF** (`kostakoff`, `4,18 GB`) — compatibility baseline, never measured on this host.
3. **SDXL canonical Q4_K GGUF** (`2,80 GB`) — same, smaller.
4. **SDXL-Lightning** — speed comparator only.
5. **Hyper-SD** — support / accelerator only; not a foundation model.

**Nothing in the live field has been run on this card.** Vega was the only candidate ever measured, and it has been rejected. Stage 2 evidence for every remaining candidate is still zero.


## 17. Stage 2 executed on SDXL canonical Q8_0 (C3A) — 2026-11-19

### Artifact
- `kostakoff/stable-diffusion-xl-base-1.0-GGUF` → `sd_xl_base_1.0_0_Q8_0.gguf`, **4,180,186,816 bytes**
- SHA-256 `c25a143954d00f6eed6235cbe0f26d2a4e68c9f3452bef33bc6ffa3b3073856b` — **verified locally**
- Complete model in one file: GGUF v3, **2,513 tensors** (UNet 1,680 + both CLIPs 585 + VAE 248), 1,370 Q8_0 + 1,143 F16, zero metadata. No sidecars.
- Uses the **diffusers** naming (`conditioner.embedders.0/1.*`), which `sd.cpp` maps internally to `cond_stage_model`/`cond_stage_model.1`.

### Measured (`sd.cpp` @ `532d2c1`), group-of-people prompt, CFG 7,0, 30 steps, 1024×1024

| Profile | seed | exit | Wall | Peak | Free at peak | Rendered |
|---|---:|---:|---:|---:|---:|---|
| `--offload-to-cpu` | 7 | 0 | 38,6 s | 5.188 MiB | 3.000 MiB | 1024×1024 |
| resident | 7 | 0 | 37,1 s | **7.170 MiB** | 1.018 MiB | 1024×1024 |
| `--offload-to-cpu` | 1234 | 0 | 37,1 s | 5.300 MiB | 2.888 MiB | 1024×1024 |
| `--offload-to-cpu` | 42 | 0 | 37,1 s | 5.300 MiB | 2.888 MiB | 1024×1024 |

`--offload-to-cpu` produces a **bit-identical** image (0 of 1.048.576 pixels differ) for **4% more wall time** and ~2 GB less peak.

### Where the peak comes from
Weights are **3.996 MB, all in RAM** under offload (UNet 2.910 MB — nearly 3× Vega's 1.046 MB). The ceiling is again the **VAE decoder compute buffer: 3.840 MiB at 1024²** (Vega: 3.600 MiB at 1280×768 — it scales with pixels, not with model size). UNet buffer 492 MiB.

### Quality — the decisive difference against Vega
- **Hands: the anatomy is right, the surface is wrong.** Five fingers and articulation in all three seeds, no fusion, no floating object — the structural failure that killed Vega does not reproduce. But at 3× the **skin is gummy**: uniform, no pores, no creases, no knuckle redness, silicone highlights. The operator called it and was right. Structure correct, surface not.
- **Skin investigated, and quantization is exonerated.** Step count (50 vs 30) does not fix it and melts the chips; CFG 5 does not fix it and adds false leather texture on the table rim; and the same repo's **bf16** file (6.937.943.840 B, `34dd7323…ad43`, verified, **zero quantized tensors** — UNet 1.046 BF16 + 634 F16, VAE decoder 69 BF16 + 69 F16) at the same seed and configuration (51,5 s, 6.314 MiB peak) is **not better and its hands are worse**: the centre hands merge into one mass and the cards become noisy blobs. **The gummy skin is SDXL base's skin rendering in this pipeline, not quantization, not steps, not CFG.**
- **Against the project's own anchor it loses.** FLUX.2 [klein] 4B Q4_K_M on the same prompt renders **knuckles, creases, nail, tendons and matte skin texture**; SDXL renders smooth glossy cylinders. SDXL canonical is therefore **not a replacement for the anchor** — its only real value is the LoRA ecosystem, which is exactly what the gate would test.
- Photorealism good; the requested shallow depth of field actually appears; faces solid and differentiated (5 / 4 / 3 distinct faces).
- No floating objects; seed 7 even renders a bartender **reflected in the mirror** behind the bar.
- **Still fails:** subject count (six players plus a bartender asked, 3–5 produced), costume collapse onto the bartender's white shirt, and the unreadable gold lettering on the table inlay.

### Comparison with the eliminated candidate
SDXL costs **2,2× the wall time** (37,1 s vs 16,5 s) and ~400 MiB more peak than Vega, and in exchange **fixes the hands**. For this project's use the hands outweigh twenty seconds.

### LoRA headroom — open, and the arithmetic is only a bound
Free at peak is 1.018 MiB resident and 2.888–3.000 MiB with offload, against a declared budget of 3.200 MiB: **neither profile clears the budget on paper.** But under offload the 3.996 MB of weights sit in RAM, so a LoRA merged into the UNet may cost RAM rather than VRAM. The bound does not decide anything; **L1/L2/L3 does.**

### Live candidate field after this measurement
1. **SDXL canonical Q8_0 (C3A) — measured, viable on VRAM, best quality seen so far. LoRA gate open.**
2. SDXL canonical Q4_K (C3B, `2.797.752.960 B`) — unmeasured; the fallback if Q8_0's margin is too tight.
3. MOSS-Image Base/SFT (C9) — unmeasured; 9B text encoder makes it the worst fit for 8 GB.
4. SDXL-Lightning — speed comparator only.
5. Hyper-SD — support only.

**`docs/research/p10-b3-sdxl-canonical-stage2-report.md` carries the full record.**

## 18. The age hypothesis — 2026-11-19

The operator's suspicion that the gummy skin is a matter of the model's **age** was tested with the four models the project has measured, on the same group-of-people prompt. Full record: `p10-b3-model-age-hypothesis.md`.

| Model | Released | Hands | Skin | Prompt satisfied | Peak | Time |
|---|---|---|---|---|---|---|
| SDXL base Q8_0 | 2023-07-25 | anatomy OK | gummy | no — 3–5 of 7 people | 7.170 MiB | 37,1 s |
| Segmind-Vega Q8_0 | 2023-11-30 | fused | gummy | no — 3–5 of 7 | 6.766 MiB | 16,5 s |
| **Z-Image Turbo fp8** | **2025-11-25** | **correct** | **matte, creases, nails, arm hair** | **yes — 6 people + aproned bartender** | ~4.815 MiB | 45,0 s |
| FLUX.2 [klein] 4B Q4_K_M | 2026 | correct | knuckles, tendons, matte | — (current anchor) | ~4.305 MiB | — |

**The trend is monotonic with the release date**, and age is a proxy for five concrete changes: epsilon-prediction UNet versus flow-matching DiT, CLIP-only versus Qwen-class text conditioning, training-data curation, parameter scale, and a softer SDXL VAE.

### Consequence for the field
- **Z-Image Turbo is already installed and resolves this scene better than any B3 candidate measured so far, with less memory than SDXL, Vega or klein.** If B3's goal is "a model that renders people well", the project already owns one; if it is something else — LoRA breadth, another aesthetic, another step regime — the field must be judged against that criterion instead.
- **SDXL Q4_K (C3B) loses its quality justification.** If Q8_0 and bf16 both fail on skin, a coarser quantization will not fix it; it only buys memory.
- **MOSS-Image (C9) becomes the only field entry still worth testing for quality**, because it is 2025-generation; its obstacle is the 9B Qwen3.5 encoder and ~15,4 GB operational, not its age.
- The only known route for a 2023 model to close the surface gap is a **detail/skin LoRA** — which is exactly what the open L1/L2/L3 gate measures.

## 19. DreamShaper re-entry and MOSS-Image measured — 2026-11-19

### Reversal recorded, not hidden
The DreamShaper XL family was removed on 2026-11-18 **by operator instruction** (§12). On 2026-11-19 the operator re-added **Lightning** and **v2** by name. This is a partial reversal of that decision and is recorded as one; the technical evidence below is what it is.

### Measured (`sd.cpp` @ `532d2c1`), group-of-people prompt, seed 7, 1024×1024, offload

| Model | Config | exit | Wall | Peak | Free | People (7 asked) | Hands | Skin |
|---|---|---:|---:|---:|---:|---|---|---|
| DreamShaper Lightning | 6 steps, CFG 2 | 0 | 24,7 s | 5.922 MiB | 2.266 MiB | 4 | claws | gummy |
| DreamShaper v2 Turbo | 8 steps, CFG 2 | 0 | 27,0 s | 5.922 MiB | 2.266 MiB | 4 | claws / fused | mixed |
| **MOSS-Image SFT** | CFG 3,0, 20 steps | 0 | **102,5 s** | **4.294 MiB** | **3.894 MiB** | **7 + bartender** | **correct** | **wrinkles, stubble, pores** |

All six artifacts verified against pinned LFS SHA-256 (`run/p10-stage2/verify.sh`, `ALL_VERIFIED`).

### Why MOSS is the cheapest in VRAM despite being the largest model
Weights are 7.946 MB in RAM under offload (DiT 3.174 Q4_K, encoder 4.611, VAE 160) — **more than DreamShaper's 6.624 MB**. The peak is lower because **SDXL's VAE decoder costs 3.840 MiB and MOSS uses the FLUX.2 VAE**. Third confirmation that the SDXL family's memory wall is the VAE, not the UNet.

### DreamShaper verdict
Both are 2024 fine-tunes of SDXL. They raise face quality and lighting — what a fine-tune fixes — and **leave the 2023 structural ceiling intact**: claw hands, wrong subject count, role collapse (the bartender's apron migrates onto seated players) and no bartender behind a bar. They confirm the age hypothesis from the negative side: improving a 2023 base does not move it out of 2023.

### MOSS-Image verdict
**The only model in the whole field that satisfies the full prompt and whose skin survives magnification.** Seven people at the table plus an aproned bartender leaning on a wooden counter, smoke, bottles, readable suits, real bokeh. Lowest VRAM peak of every candidate measured including the installed anchors.

**Its price is time: 102,5 s per image**, 4× SDXL and 2,3× Z-Image, because the Qwen3.5-9B encoder (4.611 MB) streams from RAM on every prompt.

### Live candidate field after this round
1. **MOSS-Image SFT — measured, best quality, lowest peak. LoRA gate open.**
2. MOSS-Image Base — the LoRA-training variant; unmeasured.
3. Z-Image Turbo — installed anchor; better than every 2023–2024 candidate.
4. SDXL canonical Q8_0 — measured; only value is the LoRA ecosystem.
5. SDXL Q4_K, SDXL-Lightning, Hyper-SD — no quality justification left.
- **DreamShaper Lightning and v2 — measured and rejected on quality.** Retained as archived measurement.

`docs/research/p10-b3-dreamshaper-and-moss-stage2-report.md` carries the full record.

### 19.1 Second round on MOSS — steps, quantization, tiny VAE (2026-11-19)

DreamShaper Lightning and v2 **weights deleted** on operator instruction (13 GB reclaimed); their renders and logs are kept as measurement evidence.

**Where the 102,5 s goes** (from the runtime's own log, 20 steps): weights load 15,3 s · Qwen3.5-9B conditioning 10,8 s · **sampling 88,0 s (4,05 s/step)** · **VAE decode 2,14 s**. The model is `steps × 4,05 s + ~15 s`.

| Steps | Wall | Peak | Quality |
|---:|---:|---:|---|
| 20 | 102,5 s | 4.294 MiB | 7 people + bartender, real skin |
| 12 | 68,8 s | 5.030 MiB | intermediate |
| **8** | **52,8 s** | 5.062 MiB | **holds** — 7 people + aproned bartender, usable hands |

**Halving the steps halves the time with no collapse on this prompt.** Peak rises as steps fall (4.294 → 5.062 MiB, delta 3.999 → 4.755); the cause is not established and is recorded as an observation, not an explanation.

**Quantization.** Q4_K (3,33 GB) is what runs and is the smallest sane width. Q3_K (2,70) and Q2_K (2,21) exist and **buy no time** — sampling is 4,05 s/step regardless — and RAM is not the constraint. The only quantized upgrade that matters is a **DMD 8-step distill**: `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot`, a single 5.413.723.302 B file (`sha256 df80b9fe…b0f4`) in a format `sd.cpp` supports, with the distillation baked in so 8 steps are native rather than a concession.

**Tiny VAE.** `AcademiaSD/TAE_Flux2_AcademiaSD` publishes a 3.333.534 B TAE for FLUX.2. **It does not load in this build** — `[E] VAE tensor 'tae.encoder.layers.9.conv.0.weight' not in model metadata`, exit 1, no image. And even if it loaded it could save at most the 2,14 s the decoder takes. **The quantized-VAE route is closed on both counts.**

### 19.2 DMD int8 measured — the field closes (2026-11-19)

`Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot` → `moss_image_sft_8stepdmd_int8_convrot.safetensors`, **5.413.723.302 B**, SHA-256 `df80b9fe08f6118c76adac33b00229ece3953200be9bccedf0371bace04eb0f4` **verified locally**. Single file, int8-convrot (supported by `sd.cpp`), DMD distillation baked into the weights — loaded as `--diffusion-model` with the same three components.

| Config | Steps | Wall | Peak | Free |
|---|---:|---:|---:|---:|
| Q4_K, non-distilled | 20 | 102,5 s | 4.294 MiB | 3.894 MiB |
| Q4_K, non-distilled | 12 | 68,8 s | 5.030 MiB | 3.158 MiB |
| Q4_K, non-distilled | 8 | 52,8 s | **5.062 MiB** | 3.126 MiB |
| **DMD int8** | 8 | **47,6 s** | 5.994 MiB | 2.194 MiB |
| DMD int8 | 6 | 37,8 s | 5.994 MiB | 2.194 MiB |
| DMD int8 | 4 | **34,3 s** | 5.994 MiB | 2.194 MiB |

**The DMD peak is constant across step counts — weight width fixes it, not sampling.** Int8 costs ~930 MiB more than Q4_K.

**Quality.** At **8 steps** it is the best image of the whole field alongside the 20-step render: six players plus an aproned bartender serving behind the bar, skin with stubble, wrinkles and age variation, hands with fingers and nails, readable bottles, glasses and cards, blurred patrons behind. That is its native regime, so it is not a concession. At **6 steps** intermediate, no new defects. At **4 steps** it still holds — six players and the bartender, usable skin and faces, softer shadows and finger detail in the foreground. Usable, not optimal.

**The final trade.** Best quality: DMD int8 at 8 steps (47,6 s). Best speed in the entire field with usable quality: DMD int8 at 4 steps (**34,3 s**). Most VRAM headroom: Q4_K at 8 steps (**5.062 MiB**). **DMD at 8 steps is the balance point** — 47,6 s against Z-Image's 45,0 s, with markedly better prompt adherence and skin.

**LoRA headroom remains unmet on paper:** 2.194 MiB free at the DMD peak and 3.126 MiB with Q4_K, both under the declared 3.200 MiB budget. As everywhere else in this field the sum is only a bound, because under offload the weights live in RAM and a merged LoRA may cost RAM. L1/L2/L3 has still never run.

### The field, closed
**MOSS-Image SFT is the only model that satisfies the full prompt, renders skin that survives magnification, and drops below 50 s without degrading.** It pays for that with a higher peak than Q4_K and a 9B encoder that dominates conditioning time. Every other entry in B3 is either measured and rejected (Vega, SDXL canonical, SDXL-Lightning, DreamShaper Lightning, DreamShaper v2) or superseded by the installed anchors (Z-Image Turbo, FLUX.2 klein).

## 20. Purge — 2026-11-19

The operator ruled that **only `Spectrallic/MOSS-Image-SFT-8step-DMD-int8-convrot` survives**. Everything else in the Stage 2 workspace was deleted.

### Removed
- **SDXL canonical Q8_0** (`4.180.186.816 B`) and **SDXL canonical bf16** (`6.937.943.840 B`) — the whole `sdxl-canonical/` workspace, weights, renders and logs.
- **MOSS-Image SFT Q4_K** (`3.327.400.800 B`) — superseded by the DMD file.
- **TAE for FLUX.2** (`3.333.534 B`) — the dead end.
- **Segmind-Vega** workspace — renders, logs, configs and the fp16 report.
- **DreamShaper Lightning** and **v2** workspaces — renders, logs and reports.
- All renders and logs of MOSS's discarded configurations (20, 12, 8 non-distilled steps; the TAE failure) and the two Z-Image probe renders.
- **14 GB reclaimed** (25 GB → 11 GB in `run/p10-stage2`); 327 GB free on the volume.

### Kept — and why the companions are not optional
- `moss_image_sft_8stepdmd_int8_convrot.safetensors` — `5.413.723.302 B`, SHA-256 `df80b9fe08f6118c76adac33b00229ece3953200be9bccedf0371bace04eb0f4`.
- `flux2-vae.safetensors` — `336.211.292 B`.
- `Qwen3.5-9B-Q4_K_M.gguf` — `5.680.522.464 B`.
- `tokenizer.json` — `19.989.325 B`.

**The DMD file alone does not run.** It is a DiT-only checkpoint: `sd-cli` refuses it without `--vae`, `--llm` and `--tokenizer`, and the tokenizer is mandatory because Qwen3.5 uses a different vocabulary from the embedded Qwen one. The three companions are the model's runtime, not other candidates, and deleting them would leave 5,4 GB of unusable weights.

- Three DMD renders and three DMD logs kept as evidence of the surviving configuration.
- `fetch.sh`, `verify.sh`, `probe.py` and `MANIFEST.md` kept: they reproduce the fetch, verify the digests and re-run the measurement.

### What this means for the docs
Every report's artifact list is now **historical**. Notes were added to the five affected research documents so no section reads as a description of what is on disk today.

### 20.1 LoRA gate on the surviving model — L1 and L2 pass (2026-11-19)

First real LoRA on the model that survived: `axiomofmind/Moss-image-anime-lora-GGUF` → `MOSS-Image-Anime-LoRA-F16.gguf`, **74.365.536 B**, SHA-256 `AC90C81F9463E64CF9BE0AA87FEE00C2315DBF2AF089EF62725FEDB58E8F6989` **verified**. Rank 16, alpha 16, GGUF F16, **504 LoRA tensors**. Loaded via `--lora-model-dir` plus the `<lora:MOSS-Image-Anime-LoRA-F16:1.0>` prompt tag, with `--lora-apply-mode at_runtime`.

Prompt is the LoRA's own documented action scene, seed 7, 1024×1024, 8 steps, CFG 3,0, offload. **Both runs use the identical prompt**; the tag is the only difference.

**L1 — key mapping: PASS.**
```
[I] (504 / 504) LoRA tensors have been applied
```
**504 of 504, zero tensors discarded.** This is the check the project demands and precisely the one that failed on FLUX.2 [klein], where a LoRA loaded, printed `apply lora at runtime` and **silently discarded 86 of 172 tensors** until the converter was patched. On MOSS the converter maps cleanly.

**L2 — non-null effect: PASS.**

| Run | Wall | Peak |
|---|---:|---:|
| A — no LoRA | 41,9 s | 6.004 MiB |
| B — LoRA at 1.0 | 60,6 s | 6.592 MiB |

**Mean difference 50,35 / 255**, max 255, **1.047.420 of 1.048.576 pixels differ**. Project reference: 4,8/255 was "nothing", 40,2/255 was "a real effect". **50,35 clears the threshold with margin** — and it is the declared style, not noise: A is soft-shaded anime illustration, B is **cel-shaded with hard black linework, low diagonal framing and action composition**, exactly the "seinen action, cinematic lighting, strong silhouettes" of its card. The blue energy streak of A disappears in B: composition changes, not just a filter.

**Cost of applying one LoRA:** **+18,7 s (+45%)** and **+588 MiB**.

**Peak with one LoRA is 6.592 MiB, leaving 1.596 MiB free** — far under the 3.200 MiB budget `host.yaml` declares. `at_runtime` is not cheap in either time or memory.

**L3 — still open.** Stacking three distinct LoRAs requires two more downloads of ~74 MB each. No second or third LoRA is on disk.

**What this gate does not cover.** The published LoRAs are trained and validated on **MOSS-Image SFT**, not on the **DMD distill**, and there is no SFT control render, so it cannot be claimed that the effect on the DMD matches what the author documents. L1 and L2 passing does show the distillation did not break the adapter's targets.

### 20.2 Performance LoRAs — one rejected as incompatible, one adopted (2026-11-19)

Operator set **8 steps** as the standard after seeing the DMD at 4 steps degrade, and asked for the speed adapters.

**`Epyan/MOSS-Image_4-step_adapter_lora` — rejected without downloading.** On paper it is the best fit: 4 steps, CFG-free, and it **continues from `lodestones/MOSS-Image-SFT-8-steps-dmd`**, our exact starting point. Its own README disqualifies it for this runtime: `time_embedding.safetensors` must **replace** `time_embedding.*`, `shared_block_modulation.bias` and `video_head_modulation.bias` ("applying only the LoRA does not work correctly"); it needs a **custom sampler** (`x = z + Q·x0`, repeated 4 times, with `step_codes` and a `dataspace.safetensors` holding `Q`); and it **explicitly excludes merge-style loaders**. `sd.cpp` implements neither the sampler nor a time-embedding swap. **Rejected for runtime incompatibility, not quality.** The 1,2 GB were never fetched.

**`anyMODE/moss-image-12step-turbo-lora` — adopted.** Flat LoRA, rank 64, designed for **CFG 1.0** with CFG-Zero* projection against contrast burn. File `12_step_turbo_moss_1024_distill_v8_r64_weightsx2.safetensors`, **284.147.832 B**, SHA-256 `873f6de07cf21ae3a373c009383da3d120092a8f3a0ba92c9dc5815693ca24df` **verified**.

**L1: `(552 / 552) LoRA tensors have been applied`** — zero discarded.

| Config | Steps | CFG | Wall | Peak | Luminance σ |
|---|---:|---:|---:|---:|---:|
| DMD alone (baseline) | 8 | 3,0 | 47,6 s | **5.994 MiB** | 57,53 |
| **DMD + turbo LoRA** | **8** | **1,0** | **40,4 s** | 6.686 MiB | **60,40** |
| DMD + turbo LoRA | 12 | 1,0 | 49,7 s | 6.686 MiB | — |

**At 8 steps it wins 7,2 s (−15%) with equal or better quality.** The reason is structural: at CFG 1,0 there is no negative branch, so each step costs one pass instead of two. At 12 steps it loses its point — slower than the 8-step baseline. Mean difference from the baseline **31,90/255**, i.e. a different sampling path rather than noise, and contrast rises slightly (σ 57,53 → 60,40) as the adapter claims. **Cost: +692 MiB of peak**, leaving 1.502 MiB free.

**Recommended configuration: DMD int8 · 8 steps · CFG 1,0 · turbo LoRA at 1.0 → 40,4 s** — faster than Z-Image (45,0 s) with better prompt adherence and better skin. When VRAM headroom outweighs time, the LoRA-free baseline at 8 steps and CFG 3,0 gives 47,6 s with 692 MiB less peak.

### 20.3 KV-cache — closed on both routes (2026-11-19)

The operator asked about `p1atdev/MOSS-Image-SFT-KV-Cache-LoRA`. Both possible routes were investigated and **both are closed**, for different reasons.

**The LoRA is a correction, not an accelerator.** Its README says it bluntly: *"an experimental correction LoRA for fixed-timestep text KV caching"*, and **"the adapter alone does not enable caching"**. The mechanism — computing text-only attention K/V once and reusing them during denoising — lives in a **ComfyUI node** (`comfy-moss-image-kv-cache`, `text_timestep` 1000); the LoRA only compensates for the error that approximation introduces. **`sd.cpp` does not implement that approximation**, so the adapter has nothing to correct, and applying it blind would inject a correction for an error we are not making. **Not downloaded.**

**The runtime's equivalent exists but does not pay at 8 steps.** `sd.cpp` ships `--cache-mode` with DiT strategies — `dbcache` (block-level L1 residual threshold), `taylorseer`, `cache-dit`, `easycache`. Measured on the recommended configuration (8 steps, CFG 1,0, turbo LoRA):

| Configuration | Wall | Result |
|---|---:|---|
| No cache | **40,4 s** | reference |
| `dbcache` (threshold 0,25, warmup 4) | 41,1 s | **slower** |
| `cache-dit` | 42,0 s | **slower** |
| `dbcache` aggressive (threshold 0,5, warmup 1) | **38,7 s** | −1,75 s but **degrades** |

The aggressive setting darkens and flattens: mean luminance **49,22 → 40,42**, sigma **60,40 → 50,58**, mean difference **23,03/255**. Four percent of time for visible contrast and detail loss.

**Why:** caching pays at high step counts, where states change little between iterations. At 8 steps there is almost nothing to reuse and the warmup eats a large share of the budget.

**The recommended configuration is unchanged: DMD int8 · 8 steps · CFG 1,0 · turbo LoRA → 40,4 s**, already faster than Z-Image with better quality.

### 20.4 Full LoRA catalogue measured — L3 passes, KV-cache fails on measurement, my 4-step prediction was wrong (2026-11-19)

Operator asked for the rest of the catalogue and asked point-blank whether the cache LoRA had been tested. **It had not been: I had rejected it by reasoning.** This round replaces that with measurement, and corrects one prediction of mine that was wrong.

**Catalogue downloaded, sizes verified** (2,8 GB total): Anime, Beauty, Gouache, Psychedelic (74.365.536 B each), Pose control and Depth control (290.254.336 B each), Editing (297.328.736 B), Manga alpha (132.162.296 B), KV-cache v2 (148.726.512 B), Epyan 4-step adapter (1.189.176.832 B), plus the 12-step turbo already held.

**L3 — three LoRAs stacked: PASS.** Anime + Beauty + Gouache in one prompt at 8 steps, CFG 1,0:
```
(504 / 504) → Anime
(504 / 504) → Beauty
(504 / 504) → Gouache
```
**All three apply completely, zero tensors discarded.** 60,6 s, peak 7.086 MiB (1.102 MiB free), image differs 43,95/255 from turbo alone with lower contrast (σ 60,40 → 47,80), as expected from mixing three styles. **L3 measures mechanism, not aesthetics** — stacking three styles on a photographic prompt is not a use case but a proof that the runtime applies several adapters without losing any.

**KV-cache — tested and rejected by measurement.**

| | Turbo alone | Turbo + KV-cache |
|---|---:|---:|
| Wall | **40,4 s** | **63,9 s** |
| Peak | 6.686 MiB | 6.828 MiB |
| σ | 60,40 | 59,18 |
| Tensors | 552/552 | 552/552 + **756/756** |

It applies completely and makes both worse: **+58% time** and a flatter image (difference 34,79/255). The README's claim is confirmed — it corrects an error this runtime never makes — but now **measured rather than argued**.

**The 4-step adapter — my prediction was wrong.** §12.1 predicted garbage without its custom sampler. **It is not.** At 4 steps, CFG 1,0: `(756 / 756)` applied, **42,3 s**, peak **7.308 MiB**, and a **usable image** — six players plus the bartender, coherent. But it is **softer** than the turbo at 8 steps (σ 54,35 against 60,40; faces and hands less defined) and **slower** (42,3 s against 40,4 s) with 622 MiB more peak.

**The conclusion stands — it is not used — but the reason changes:** not "it does not work", but **it wins nothing and costs more on all three currencies**. Its sampler incompatibility is still real for reaching its full regime, but partial application does not break.

**Final configuration unchanged: DMD int8 · 8 steps · CFG 1,0 · turbo LoRA at 1.0 → 40,4 s.** None of the nine remaining adapters improves it.

### 20.5 Correction: 12 steps is worth it, and the turbo barely helps there (2026-11-19)

Two corrections raised by the operator.

**Cache LoRA deleted, and no replacement is worth hunting.** `moss_image_sft_kv_cache_v2_step000500.safetensors` removed. The blocker is not the adapter but the runtime: `sd.cpp` does not implement text K/V caching, so **any correction LoRA for that mechanism has nothing to correct**. Substituting another file would repeat the same mistake.

**The 12-step dismissal was lazy.** §12.2 said 12 steps "loses its point: slower than the 8-step baseline" — a time-versus-time comparison in which **the 12-step image was never looked at**. Seen, it is **better**: sharper faces and hands, crisper background bottles, higher contrast (σ 61,18 against 60,40). The operator was right.

**The comparison that was missing:**

| Config | Steps | CFG | Wall | Peak | Luminance σ |
|---|---:|---:|---:|---:|---:|
| DMD alone | 4 | 3,0 | 34,3 s | 5.994 MiB | — |
| DMD alone | 6 | 3,0 | 37,8 s | 5.994 MiB | — |
| DMD alone | 8 | 3,0 | 47,6 s | 5.994 MiB | 57,53 |
| **turbo LoRA** | 8 | 1,0 | **40,4 s** | 6.686 MiB | 60,40 |
| **turbo LoRA** | 12 | 1,0 | 49,7 s | 6.686 MiB | 61,18 |
| **no LoRA** | **12** | **3,0** | 52,2 s | **6.394 MiB** | **63,24** |

**The turbo at 12 steps saves only 2,5 s** (49,7 against 52,2) while costing 292 MiB more peak and some contrast. At 8 steps it saved 7,2 s. **Fixed cost dominates:** loading the weights (≈15 s) plus the Qwen3.5 encoder (≈11 s) is ~26 s that does not depend on step count, so at 12 steps the room CFG 1,0 can cut is proportionally smaller.

**Consequence: the decision is about steps, not about the LoRA.**
- **Best quality:** 12 steps **without** the LoRA → 52,2 s, **6.394 MiB** (lowest peak of the three), σ 63,24.
- **Fastest:** 8 steps with the turbo → 40,4 s, 6.686 MiB.
- **12 steps with turbo** lands in between: 2,5 s of gain for 292 MiB and less contrast.

**What remains is an operator decision, not a measurement:** whether 9 s justify the visible quality jump from 8 to 12 steps.

**Method note:** these are single runs under variable GPU load, so the ordering is sound but 2–3 s deltas should not be read as precise.

### 20.6 Sharpness is not quality: the operator saw grain, not anatomy (2026-11-19)

The operator pointed at the **no-LoRA 8-step CFG 3,0 render** (47,6 s, 5.994 MiB) saying the quality shows there. Checked on an identical crop, both readings are compatible but they are different things.

**The metric half-agrees.** Laplacian variance on the same crop (valid here because the content is identical):

| Config | Sharpness (lap var) | Wall | Peak |
|---|---:|---:|---:|
| no LoRA · 8 steps · CFG 3,0 — *the operator's pick* | 849,1 | 47,6 s | 5.994 MiB |
| turbo · 8 steps · CFG 1,0 | 620,3 | 40,4 s | 6.686 MiB |
| turbo · 12 steps · CFG 1,0 | 710,3 | 49,7 s | 6.686 MiB |
| **no LoRA · 12 steps · CFG 3,0** | **952,4** | 52,2 s | **6.394 MiB** |

The image is sharper than the turbo by metric — but the metric measures **local high-frequency contrast**, and CFG 3,0 adds **grain** to the felt and skin, inflating the number without adding anatomical detail.

**At 3,5× the order inverts.** On the hands crop: the operator's pick has readable anatomy but **waxy skin, soft fingertips, no nails, no knuckle creases**; the **turbo at 8 steps shows knuckle creases and fingernails and has the best hands of the three**; the no-LoRA 12-step is close behind the turbo.

**Conclusion:** what the operator saw is real — the image has **photographic texture and grain** and reads best at full size — but that grain **is not detail**. On hand anatomy the turbo at 8 steps wins.

**Two defensible configurations:**
- **Photographic texture and lowest peak:** no LoRA · 12 steps · CFG 3,0 → 52,2 s, **6.394 MiB** (sharpest at 952,4, second-best hands).
- **Best hands and fastest:** turbo · 8 steps · CFG 1,0 → **40,4 s**, 6.686 MiB.

The operator's instinct pointed at CFG 3,0 without the LoRA, and **taken to 12 steps that is the best of the four on texture and peak**. The turbo keeps the edge on hands and time.

**Third method correction of the day:** Laplacian variance **rewards grain**. Using it alone as a quality proxy is the same class of mistake as judging from the full image or dismissing 12 steps without looking. In this document it is used to **describe texture only**, never to conclude anatomy, and anatomy is decided by looking at the magnified crop.

### 20.7 The turbo buys speed by dropping the negative branch — and it shows (2026-11-19)

The operator insisted his image has better detail, colouration, style and bottles, and that **the skins do not look gummy**. He was right, and the cause is mechanical rather than aesthetic.

**The proof is in the log.**

| Config | Conditioning passes | Negative prompt |
|---|---:|---|
| CFG 3,0 (no LoRA) | **2** | encoded: `(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch)` |
| CFG 1,0 (turbo) | **1** | **never encoded** |

At CFG 1,0 **there is no negative branch at all**: the negative prompt is inert. That explains both observations at once:

- **Why the turbo is fast:** half the conditioning passes and, per step, one evaluation instead of two. **The speed does not come from the LoRA; it comes from removing guidance.**
- **Why the skin changes:** the negative prompt is precisely what pushes away from *illustration, 3d, 2d, painting*. Without it the model's default tendency toward plastic surfaces is unopposed.

**What is and is not measurable in the colour.** Global saturation and colorfulness are nearly identical: 61,4 % / 54,2 for no-LoRA at 8 steps, 61,3 % / 55,3 for turbo at 8, **63,4 % / 58,1 for no-LoRA at 12**. So what the operator calls "better colouration" **is not saturation** — it is **object and material variety** (the CFG 3,0 crop has bottles of different silhouettes and glasses — amber, green, clear — while the CFG 1,0 crop drifts to uniform elongated bottles with pale labels) and **matte versus sheen**: CFG 3,0 skin is matte where the turbo's carries an oily gloss on forehead and cheekbone.

**Verdict corrected.** §16 put hands first and called the turbo "better hands". That remains true **on the hands crop**, but **weighting it as the main criterion was a proportion error**: the hands are one region of the frame; skin, bottles, style and colour are the whole frame.

**Quality configuration: CFG 3,0 without the LoRA.** At 12 steps it is also the sharpest (952,4) and has the **lowest peak of all** (6.394 MiB) at 52,2 s. **The turbo is a speed option with a declared cost:** 40,4 s in exchange for losing the negative prompt.

**For deployment:** if the served images care about skin and materials — and they appear to — **CFG 3,0 is the correct configuration and the turbo is a concession, not an improvement.** The real choice is *material quality against 12 seconds*.

### 20.8 Animation design: what exists, what verified, what is blocked (2026-11-19)

**The animation LoRA is verified.** `axiomofmind/Moss-image-animated-lora` → `MOSS-Image-Animated-LoRA-ComfyUI.safetensors`, **74.379.584 B**, SHA-256 `A99173F545271DCD43BBB79483C60FECEAB447B80841D2391936A60672E41934`. **L1 `(504 / 504)`**, and at 12 steps with CFG 3,0 it renders in **67,9 s at a 6.922 MiB peak** as what its card promises: **a 3D animated film frame** — polished materials, clean speculars, idealized faces, six players plus the bartender. It is dimensional cartoon treatment, not 2D cel. **Note the tension with the operator's stated taste:** this LoRA **smooths skin deliberately**, which is the opposite of the matte photographic skin he asked for. Choosing animation means choosing that surface.

**The RGBA VAE is incompatible with this build.** `paralaif/MOSS-Manga-Alpha-Image-LoRA` → `vae/flux2_klein_alpha_rgba_vae.safetensors`, **336.222.776 B**, fails as `--vae`:
```
[E] VAE tensor 'first_stage_model.decoder.conv_out.weight': got [3,3,128,4], expected [3,3,128,3]
[E] model metadata validation failed
```
It is a **4-channel (RGBA)** VAE and the loader **requires 3**; exit 1 in 1,0 s with no image. The runtime handles RGBA images as **input** and in the upscaler, but **there is no alpha-output flag** — `--help` mentions alpha only for schedulers. **Transparency is closed in this build**, and with it the designed use of `moss_manga_alpha_image_lora` and `moss_alpha_v1`. Frames can be generated; **assets with a transparent background cannot**, so compositing would need post-hoc cutout or a different runtime.

**Style inventory.** Pure style: Anime/seinen (GGUF, verified), Animated Character 3D (verified, this round), Gouache, Psychedelic, Beauty (all GGUF, downloaded), **Impressionism** (`Kandoo`, 74.470.552), **Blue Archive style** (`RunningHubAI`, 129.017.232), **Fizgig Look** (`ShootTheSound`, 2.221.764.612), kale-img-1 (`suhaaspk`, 148.697.160), myjc/myjs/mylow (`deadman44`, ~300 MB each), Gabriel DropOut (`quarterturn`, 297.333.192).

**Technical, not style but useful for design:** the **Hires LoRA** by `comfyanonymous` (7 versions, 132–182 MB), **NextScene** (`AdwolfCzar`, 145.157.240) for scene continuity, and the speed adapters.

**Line and structure control** (`thedeoxen`, 290 MB each): **lineart**, **scribble**, canny, normal, depth, segmentation, pose. The first two are the basis of an animation design flow — line drawing to image. **Neither has been tested.**

**Copyrighted characters:** Frieren, Alya, Emilia, Marin (`tachiyumi`), 83 celebrities (`pmczip`), `shuiwu22` (`ACCC1380`). **Not usable in commercial delivery without rights.**

### 20.9 License audit of the style catalogue — 3,17 GB survives (2026-11-19)

Applied rule: **a LoRA has no independent license.** It inherits the base model's — MOSS-Image is Apache 2.0, so the base is not a blocker — and adds whatever its author declares. **Absence of a license is not permission:** with no license, copyright applies by default and no commercial right is granted. Each repo's card was checked for `license`, and its tree for a `LICENSE` file when the card declared nothing.

**Not legal advice:** a conservative engineering read; a serious commercial use deserves legal review.

**Survives (Apache 2.0):**

| Adapter | Size |
|---|---:|
| Impressionism (`Kandoo`) | 74.470.552 |
| NextScene v1 (`AdwolfCzar`) | 145.157.240 |
| myjc / myjs / mylow (`deadman44`) | 915.941.960 (3 files) |
| thedeoxen × 7 — lineart, scribble, canny, normal, depth, segmentation, pose | 2.031.780.352 |

**Total: 3.167.350.104 B = 3,17 GB** (2,95 GiB).

**Discarded:** **Blue Archive style** (`RunningHubAI`) — no declared license and no LICENSE file, plus game IP; **Gabriel DropOut** (`quarterturn`) — **`cc-by-nc-4.0`**, the NC clause forbids commercial use explicitly, plus character IP; **Hires LoRA** (`comfyanonymous`) — no declared license and no LICENSE file; **Frieren / Alya / Emilia / Marin** (`tachiyumi`) — no license plus copyrighted characters; **83 celebrities** (`pmczip`) — licence `other` plus likeness rights; **shuiwu22** (`ACCC1380`) — no license plus character IP.

**Two warnings not to bury.**
- **The Hires LoRA is the painful loss.** It is the one the operator flagged as the fix "where the other models fail", and it falls **only on paperwork**: `comfyanonymous` declared no license and included no file. The remedy is not technical — **ask the author**. One message, not a negotiation; if they grant Apache or MIT it enters unchanged.
- **`deadman44` passes on license but its subject is doubtful.** Names `myjc`, `myjs`, `mylow` suggest personal or character styles. Apache 2.0 on the weights **grants no likeness or character rights**: if trained on a real person or an IP, the file license does not cover commercial use of the output. **Verify before delivery.**

**What the filter leaves standing:** four style/structural entries — Impressionism, NextScene (scene continuity, the one that matters for video), three personal styles of doubtful subject, and **the complete `thedeoxen` control set**, by far the most valuable part and the only one enabling a production flow (lineart and scribble still untested). **None of the discarded ones was an irreplaceable capability; the only one with unique technical value was the Hires LoRA, and its blocker is administrative.**

### 20.10 The unlicensed ones tested, and the per-frame cost that decides (2026-11-19)

Downloaded and tested at the operator's request, **for internal evaluation only**. All at 12 steps, CFG 3,0, offload, seed 7.

| LoRA | L1 | Wall | Peak | Verdict |
|---|---|---:|---:|---|
| **Hires v0.7** at **1280×1280** | 600/600 | **222,9 s** | **7.482 MiB** | works: clean 1280², no duplicated heads, defined faces and hands |
| **Blue Archive** at 1024² | 328/328 | 72,0 s | 7.218 MiB | delivers the style: clean anime illustration, detailed eyes, pastel palette |
| **Frieren** at 1024² (portrait) | 492/492 | 64,7 s | 6.566 MiB | **the character is recognisable**: elf ears, twintails, green eyes, robe |

**All three map without losing a tensor.** Hires is the only one that also solves the high-resolution problem: at 1280² there are no duplicated heads or broken anatomy, the usual failure mode when resolution goes up.

**The number that decides.** If the destination is YouTube video, the per-image cost becomes brutal:

| Config | s/frame | 5 s of video (40 frames) | 10 s (80) |
|---|---:|---:|---:|
| turbo · 8 steps · CFG 1,0 | **40,4** | **26,9 min** | 53,9 min |
| base · 12 steps · CFG 3,0 | 52,2 | 34,8 min | 69,6 min |
| Frieren · 12 steps | 64,7 | 43,1 min | 86,3 min |
| Blue Archive · 12 steps | 72,0 | 48,0 min | 96,0 min |
| **Hires · 1280²** | **222,9** | **148,6 min** | 297,2 min |

**Five seconds of video with Hires is two and a half hours.** With turbo, half an hour. Hires is not an option for video however good its quality; it is an option for stills.

**On characters, the problem is not the file.** Character LoRAs **work technically** and Frieren is unmistakable, but **no file licence grants rights over the character**: Frieren, Marin, Emilia, Alya and Gabriel DropOut are commercial anime IP. On a monetised channel that is **infringement risk**, whatever the repo declares. For "faceless with faces" the split is: **generic faces, no problem — the base model already does them well; recognisable third-party characters, fine to test, not to publish.**

**What this leaves for the pruning.** With the declared criterion — **two survivors, one for quality and one for speed**:

| Slot | Candidate | Why |
|---|---|---|
| **Quality** | **base · 12 steps · CFG 3,0 · no LoRA** | best skin and materials; the active negative prompt is what prevents the plastic look |
| **Speed** | **turbo · 8 steps · CFG 1,0** | 40,4 s per frame, 23 % less than base |

**And the warning:** **none of the tested style LoRAs improves skin.** Anime and Animated smooth it deliberately; Blue Archive stylises it. If "quality" means photographic skin, the winner is not a LoRA but **the naked model with its negative prompt**.

### 20.11 The real cadence dissolves the volume/quality tension (2026-11-19)

The operator corrected the assumption: **these are not frame-by-frame videos.** They are faceless 15-minute videos with **60–70 images** — 4,0–4,7 images per minute of video, one every 13–15 seconds. Documentary rhythm, not animation.

| Model | 60 images | 65 | 70 |
|---|---:|---:|---:|
| klein, 8 steps | 22 min | **24 min** | 26 min |
| **MOSS, 12 steps, CFG 3,0** | 52 min | **57 min** | 61 min |
| MOSS + Hires 1280² | 3,7 h | 4,0 h | 4,3 h |

**Per 8-hour machine day:** klein **19,8** videos, MOSS in quality **8,5**, MOSS+Hires 2,0. **Eight and a half quality videos a day is more than any channel publishes, so volume stops being a constraint** — and the earlier premise "klein for volume" is refuted by the operator's own numbers.

**Corrected two-model allocation:**

| Slot | Model | Why |
|---|---|---|
| **Production** | **MOSS**, 12 steps, CFG 3,0 | the final video; 57 min each is affordable |
| **Draft** | **klein**, 8 steps | cheap prompt and framing exploration: 10 variants cost 4 h against 9,5 h with MOSS |
| Retired | Z-Image | wins neither slot |

**Hires enters as a special-piece option, not routine:** 4 hours per video.

**Consequence for the model pruning: MOSS is the primary model, not the secondary. Z-Image leaves because it is dominated in both slots. Two models are kept, with distinct roles — production and draft.** This inverts the previous recommendation, and the reason is recorded: the earlier one rested on an fps assumption the operator never gave. **Same lesson as the earlier corrections — deciding on one's own assumption instead of the user's data.**
