# P10 / B3 Candidate Fingerprint and Memory Constraint Matrix

**Status:** research-only. No asset download, no model promotion, no source code, no adapter, no entry, no test code, no documentation claim of runtime integration.  
**Date of this document:** 2026-11-18  
**Repository state:** P1-P9 and P11 are closed. P10 remains `planned`. B3 is open.  
**Owner:** operator/researcher, with this orchestrator kept to read-only inventory only.

## 1. Purpose

This document exists so B3 is treated as a **decision-boundary problem**, not as "download another model and try it." The expensive part of P10 is not the download. It is adapter code, sidecar policy, loader discipline, guard maintenance, and observability around a second family.

The goal is to answers these questions before P10:

1. Is there a need for a second model at all, or is the current FLUX.2 [klein] 4B + Z-Image Turbo FP8 pair already sufficient?
2. If yes, what is the smallest lawful candidate that genuinely improves the service under **memory plus LoRA load constraints**?
3. Does the candidate actually improve the commercial-licensing and compatibility picture enough to justify the cost?
4. What is the cheapest packet of evidence that can reject an unsuitable candidate?

## 2. Current anchoring material

No model change is justified unless it is measured against the current proof.

### Already closed in the project

| Anchor | Measurement |
|---|---|
| FLUX.2 [klein] 4B (Q4_K_M, `stable-diffusion.cpp`) | 5.10 GiB weights (2.60 GB diffusion model + 2.50 GB Qwen3 encoder), 1152x1152 default, steps 4..8, guidance 1.0, peak 4305 MiB at measured request scale |
| Z-Image Turbo FP8 (`zimage`) | 6057 MiB transformer, 1280x720 default, steps 8..16, guidance 0.0, warm-up 15.1 s total boot |
| LoRA budget | 3200 MiB of requested file size, measured against render peak of 4815 MiB |
| Card | 8188 MiB total, 7857 MiB torch-usable |
| Unit of review | one work-unit commit on the feature branch, not a GUI checkbox |

### Business constraints already fixed

- License must be Apache 2.0, MIT, or a derivative that is accepted without trademark or additional permission.
- No page or client may imply a model family exists unless it is served.
- Single-flight only; one model per process.
- No silent widening of `entry.accepts()`.
- No Hub/network dependency inside the boot path.
- Every B3 action must be reversible in `model/assets/` and observable via an explicit exit criterion.

## 3. Candidate shortlist and preliminary status

| Rank | Candidate | License | Single-file footprint (public truth) | Qualitative position |
|---:|---|---|---:|---|
| 1 | **Segmind SSD-1B** | Apache 2.0 | 4.46-4.47 GB fp16 | **Best license-first, memory-first option**, but still unverified for LoRA |
| 2 | **Segmind-Vega** | Apache 2.0 | 3.29 GB fp16 | Even more aggressive footprint, lower maturity |
| 3 | **SDXL canonical base (single-file)** | OpenRAIL-M | 6.94 GB fp16 | Maximum LoRA compatibility, poor fit for a lean adapter |
| 4 | **Community `v2-turbo` GGUF** | OpenRAIL (third-party) | Q8 4.18 GB, Q4 2.8 GB | Memory attractive, but provenance is the risk |
| 5 | **DreamShaper XL turbo** | OpenRAIL, commercial restriction for turbo | 6.94 GB | Style identity exists, but license notes swallow the advantage for our scope |

### Candidate removals

- `Alpha2 XL 1.0` currently looks like an optimization liability. It targets 28-50 steps proactively while the operator already ruled that distilled families should not be treated as tunable toy models.
- Base SDXL is not excluded, but it is no longer the shortlist leader. It is the **compatibility baseline**, not the target.

## 4. Hard filters (stop-or-not boundary)

Any candidate must pass all of the following:

### A. License boundary, operational

- Apache 2.0, MIT, or an explicit MIT-compatible license.
- A document link pinned by commit hash or digest.
- No separate permission required for commercial serving.
- No "Turbo requires permission from Stability" style clause unless the behavior is scoped and documented.

### B. Runtime boundary

- The weight file is a pinned single file with a hash.
- Registry docs do not force a 34 GB+ clone when only a pinned 4-7GB single file is required.
- Tokenizers, scheduler, and config sidecars must be exact, self-owned, and hashed.
- No third-party `from_single_file(...).to("cuda").from_pretrained(...)` boot path that introduces Hub-only assets by default.
- No second solver (for example, `ggml` remote) embedded into the same route unless it is a deliberately scoped sidecar.

### C. Memory boundary

- The candidate must leave explicit LoRA headroom.
- No "tiny because it is 3.29GB on disk but also 3GiB of VRAM" assumptions until stated load.
- If LoRA load requires extra memory that compromises the base render and the adapter already needs staging, it fails the test before integration.

## 5. Architecture fingerprint from public artifacts

This section intentionally uses only small, inspectable files. No model bytes are downloaded in this phase.

### 5.1 SSD-1B

Public raw config (fetched 2026-11-18):

- `UNet2DConditionModel`
- `block_out_channels`: `[320, 640, 1280]`
- `layers_per_block`: 2
- `transformer_layers_per_block`: `[[1], [2,2], [4,4]]`
- `num_attention_heads`: null (resolves via `attention_head_dim [5,10,20]`)
- `in_channels`: 4, `out_channels`: 4
- `cross_attention_dim`: 2048
- attention-root convention appears unchanged: CLIP1 size 768, CLIP2 size 1280.
- text normals use quick_gelu (CLIP1) and gelu (CLIP2).

**Interpretation:** SSD-1B is **not a base SDXL no-op**. It is a distilled, structurally pruned U-Net. Because the target shape differs (even when the data contract looks similar), a normal SDXL LoRA is not automatically authoritative on this adapter.

### 5.2 Stable facts about all mainstream SDXL-family candidates in this repo's existing language

- Standard SDXL text encoder 1 is 768.
- Standard SDXL text encoder 2 is 1280.
- VAE filters 128/256/512/512 downstream.
- The public components live in different formats and folders, and full repos are padded by fp32 copies.

### 5.3 Quality-speed observations inherited from public cards

- SSD-1B is described as 50% smaller, ~60% faster than SDXL.
- Prompt-level steerable negative-prompt path exists.
- SSD-1B reportedly expects CFG around 9.0 for best quality.
- Base SDXL is still canonical for ecosystem LoRAs.
- DreamShaper Turbo requires 1.5-2 CFG per public guidance.

These are public-product facts useful for rough triage only. They are **not project measurements** and do not count as runtime proof.

## 6. Memory accounting (planning, not proof)

### 6.1 Public footprint table

<|channel|> Material fact | Value |
|---|---:|
| SDXL canonical SINGLE-FILE | ~6.94 GB |
| DreamShaper XL single-file | same byte size base (6,939,220,250) |
| SSD-1B single-file | 4.46-4.47 GB |
| Segmind-Vega single-file | 3.29 GB |
| Community Q8 v2-turbo GGUF | 4.18 GB |
| Community Q4 v2-turbo GGUF | 2.80 GB |

### 6.2 Required asset accounting

The repo already has a dangerous source of confusion: total repository size versus practical single-file price. Discarded in advance:

- `34.7 GB` repo wide shallow clones
- `41.6 GB` v2-turbo clone
- `26.8 GB` SSD-1B full layout

Only the **pinned single-file plus declared sidecars** count in B3 planning.

Every candidate must list at least:

- checkpoint digest
- sidecars with sizes and digests
- tokenizer and scheduler version
- config digest
- expected RAM and VRAM from first run

Missing any row = no promotion, no matter how attractive the model name.

## 7. LoRA compatibility test plan (the real blocker)

LoRA load breakage is the most likely remaining cost. The prototype should explicitly look at **shape alignment**, not nominal compatibility.

### 7.1 Architecture shape ticket

For each candidate adapter:

1. Build the smallest loader that only touches U-Net, text encoders, and VAE and records block shapes.
2. Compare against one known LoRA expected dims.
3. Record whether `lora_xb` keys can resolve directly or require a weighted remap.

### 7.2 Three cheap protocols

- **L1 (name probe):** load a LoRA in read-only session, report whether the key-set matches directly.
- **L2 (effect probe):** confirm one output changes when an applied LoRA at scale > 0 is used, versus scale 0.
- **L3 (class probe):** confirm all adapter-target layers are present and that the loader did not silently ignore ~X keys.

### 7.3 Multi-style reality check

Do not claim several LoRAs behave perfectly together only because one LoRA renders. The project already makes this distinction in the LoRA budget row.

If only one LoRA changes output, document that fact literally. Do not extrapolate "three should be fine" into an implied quality result.

## 8. Evidence ladder (cheapest exact order)

| Stage | Cost class | What happens | Promotion gate |
|---|---|---|---|
| 0 | near-zero | license URLs + config inventory (no download) | stop if license is ambiguous |
| 1 | small | download only configs/tokenizers + digest baseline | stop if architecture mismatch |
| 2 | medium | download pinned single-file and record load VRAM | stop if memory beat exceeds event margin |
| 3 | medium | render one known still + one negative-prompt probe | stop if quality is below current anchor |
| 4 | medium | one LoRA probe in read-only mode | stop if non-loadable / silent mismatch |
| 5 | high | integration in a throwaway work unit, isolated temp | stop if adapter needs to touch `server.py`/`render.py` beyond bounded declarations |
| 6 | high | actual P10 implementation | only after replayed stage evidence |

The subsidy is cheap because failure is cheapest earlier.

## 9. Kill criteria

Stop immediately and record the negative result if any of these occur:

- license ambiguity or no commercial	path
- a runtime lookup outside the tree
- unsupported sampler (not configurable via deterministic path)
- LoRA target mismatch or zero weighted effect
- peak render plus LoRA run with no observable breathing room
- miss of required sidecars / bad pin
- P10 implementation pretending to be optional while actually rewriting core responsibilities

## 10. Required operator choices still open

These are the exact human decisions that cannot be inferred by research:

1. If SSD-1B's Apache benefit conflicts with runner complexity, how much adapter complexity is acceptable?
2. Is the target to preserve SDXL LoRA usability, or to replace adaptation budget and refocus on a lower-memory path?
3. Should negative-prompt capability become a user-facing contract, or just an observed latitude?
4. What is considered "enough" headroom for LoRAs under the chosen candidate?

## 11. Immediate next smallest action (recommended)

Do not do asset download now.

Run only the Stage 0–1 packet:

1. Save `license.txt` and clear commercial terms.
2. Save configs + exact sidecar manifest.
3. Build a report that states:
   - candidate selected for `P10` tryout
   - license summary
   - exact disk price
   - config total
   - predicted LoRA resolution mismatches, if known
   - explicit "does not integrate today"

Then stop again and return to the owner for one signed-off decision.

## 12. Deliverables produced by this research-only phase

- This file, as the first durable candidate fingerprint.
- A future companion `docs/research/...` only after `stage 2+4` pass.
- No commit payload, no essential artifacts, no loader, no test code, no UI badge.

## 13. Non-goals of this document

- No selected runtime.
- No confirmed independent LoRA test result.
- No claim that a candidate will remain below VRAM once layered with actual LoRAs.
- No assertion that any Apache 2.0 candidate is operationally identical to the current stack.

## 14. Related source anchors

Sources used in this fixture are the same public facts already reviewed:
- `docs/roadmap.md` (B3 row and P10 row)
- public Hugging Face configurations and model cards
- public model card wording for SSD-1B and Segmind-Vega
- received configuration fingerprint for the SSD-1B U-Net and text/image encoder layouts

## 15. Safety note

This research file must remain honest if later contradicted by a real run. If a real measurement contradicts it, add an amendment instead of rewriting prior statements.

---

If this document is accepted, `B3` stays open; `P10` stays planned. The only generated asset is documentation.

## Appendix A — Documentary evidence upgrade (2026-11-18)

This appendix converts the earlier hypotheses into **evidence-backed conjectures** where public sources support them, and removes claims that the first pass left under-grounded. It does not create a runtime result; it lowers the uncertainty class of several statements.

### A.1 Candidate-facing evidence upgrade table

| Statement area | Source kind (primary/secondary/internals) | Documentary support | Remaining gap |
|---|---|---|---|
| **License: SSD-1B / Vega are Apache 2.0** | Primary | `github.com/segmind/SSD-1B/blob/main/LICENSE` states Apache 2.0; HF tag `license: apache-2.0` | reviewed license under our exact serving wrapper; license intact yes |
| **License: SDXL canonical / DreamShaper / GGUF are OpenRAIL++** | Primary | HF metadata `license: openrail++`; DreamShaper Civitai text clearly flags **Turbo noncommercial** requirement | operator must decide commercial exceptions |
| **SSD single-file disk price** | Primary | HF file `SSD-1B.safetensors`: 4,465,671,506 bytes; Vega: 3,293,395,670 bytes; SDXL/Turbo: 6,939,220,250 bytes | no staging distribution prefix yet (real asset remains un-downloaded) |
| **Training scale / method** | Primary + paper | Segmind blog: 15M data points, 4x A100 / ~200 GPU-h; paper *Progressive Knowledge Distillation of Stable Diffusion XL Using Layer Level Loss* (arXiv 2401.02677); 251,000 steps, fp16 | training data and benchmark are public, but quality versus project baseline is unmeasured |
| **Architecture pruning** | Primary | Segmind README/model card: 1.3B Params, "several layers removed," and blog specifics: 40 transformer blocks and 1 ResNet removed from SDXL Base; block-out channels still `[320,640,1280]` | exact remaining `transformer_layers_per_block` must be verified, but public config `[1,[2,2],[4,4]]` matches it; see Section 5.1 |
| **Peak VRAM at 1024² (SDXL vs SSD)** | Primary | Segmind blog: idle loaded SDXL 7,810 MB vs SSD 5,338 MB; inference peak SDXL 15,214 MB vs SSD 12,780 MB | measured under their A100/TRT story; our host peaks under staged loader are unknown |
| **Weight-only memory estimate** | Secondary | Aquanode estimator: FP16 residues ~2.5 GB; FP32 ~5.0 GB | estimator abstracts our layout/offload; must be measured |
| **Customer LoRA support** | Primary | Hugging Face public LCM LoRA for SSD-1B (`latent-consistency/lcm-lora-ssd-1b`) exists, and community DreamBooth-LoRA examples on SSD-1B are documented | random SDXL LoRA key behavior still shape-suspicious due pruning and untargeted yet |
| **Speed narrative** | Primary / secondary | Segmind: 60% speed increase on A100 at stated benchmark and TRT optimizer; 4090 community reports ~20-30s per 1024 render with SSD vs ~1 minute base SDXL | benchmark depends on optimizer and hardware; public, not measured here |

### A.2 Evidence-tightened claims from document § 14

The original non-affirmation list has been reduced. The surviving unknowns are now only those that require a real run:

1. **Load-only peak in our service loader path**  
   Segmind's published inference peak is already high (12,780 MB at 1024² versus 7,810 idle, SDXL 15,214 potential at the same box), but that is vendor-level, not our staged result.
2. **LoRA target key exactness**  
   SSD-1B ships LoRA training support in public documents, but an arbitrary SDXL LoRA (not a Segmind-generated one) still needs a Python key-series probe; this is the principal remaining compatibility test.
3. **Quality/economics under this service's output contract**  
   Public comparison shots exist, but there is no measurement of `a lighthouse at dusk`-style baseline parity or rejection criteria.
4. **Multi-real LoRA production output behavior**  
   Public materials often show single adapters; interaction quality is still unmeasured.
5. **Staged-loader boot cost and peak after remapping**  
   `fp16 4.46GB` or `3.29GB` alone does not determine peak; staged load is still required for exact headroom.

### A.3 Documentary evidence sources used

- `https://github.com/segmind/SSD-1B/blob/main/LICENSE`
- `https://huggingface.co/segmind/SSD-1B`
- `https://huggingface.co/segmind/SSD-1B/tree/main`
- `https://huggingface.co/latent-consistency/lcm-lora-ssd-1b`
- `https://blog.segmind.com/introducing-segmind-ssd-1b`
- Segmind README model architecture and training sections
- Public article evidence (Ramsri Goutham / blog posts)
- Primary configuration captures in `/tmp/opencode/p10-stage` (outside tree)

### A.4 Readiness before Stage 2 (tightened)

Proceed only if all of these survive:

1. License verdict stays Apache 2.0 after exact file pinning.
2. Config mismatch vs SDXL is explicitly characterized and either:
   - straight targets pass
   - a remapping script determines a small adapter-side mapping without leaking into `server.py` / `render.py`
3. Load probe records load-only VRAM, warm render VRAM, and load-plus-LoRA VRAM.
4. Base render is compared against the existing Klein anchor on the same prompt and seed.
5. LoRA `L1-L3` probe dimensions are recorded.

### A.5 Updated verdict after A.4

- **SSD-1B** remains the cleanest license-first candidate, but its 1024² vendor peak makes it accuracy-flagged, not a win.
- **Segmind-Vega** would only enter if memory headroom remained absolute.
- **SDXL base** remains the compatibility baseline and license comparator.
- **DreamShaper XL** remains excluded by commercial restriction.
- **Community GGUF** remains a provenance and quality risk.

Use this appendix as the evidence boundary for the next run.
