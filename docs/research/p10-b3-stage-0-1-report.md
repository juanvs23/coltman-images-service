# P10 / B3 Stage 0-1 Report

**Status:** Stage 0 and Stage 1 research complete. Stage 2+ blocked by explicit operator decision.  
**Date:** 2026-11-18  
**Scope boundary:** No asset download, no model bytes, no adapter, no entry, no guard, no source change. Only public metadata, tiny configuration files, and repository facts were retrieved.  
**Sandbox evidence location:** `/tmp/opencode/p10-stage/` (outside the project tree; not committed, not referenced by code).

## 1. Outcome summary

- Apache 2.0 remains the effective license filter.
- All three SDXL-family candidates that are Apache 2.0 at repository level are **Segmind SSD-1B** and **Segmind-Vega**.
- DreamShaper XL, SDXL canonical, and community GGUF variants remain **OpenRAIL++** or carry an inherited commercial exception. They can be considered for capability research, but not as commercial-first replacement candidates unless the operator explicitly allows the exception.
- Stage 1 architecture fingerprinting found a real compatibility signal: **SSD and Vega retain the standard SDXL 1/2/3-stage block widths and cross-attention dims, but the transformer-layer count per level differs from SDXL canonical**. This does not prove a LoRA load failure, but it converts "should probably work" into an explicit test item instead of an assumption.
- B3 remains open. P10 remains `planned`.
- The deliverable exists only as documentation.

## 2. What was retrieved (Stage 0 ledger)

No model checkpoints were downloaded. The retrieved files are the same small metadata/config files that document loaders rely on.

| Candidate | Repository | License (public metadata) | Downloads observed | Last modified (public) | Candidate rank |
|---|---|---|---:|---|---|
| Segmind SSD-1B | `segmind/SSD-1B` | `apache-2.0` | 27,949 | 2024-01-08 | 1 |
| Segmind-Vega | `segmind/Segmind-Vega` | `apache-2.0` | 5,026 | 2024-01-08 | 2 |
| SDXL base | `stabilityai/stable-diffusion-xl-base-1.0` | `openrail++` | 4,794,303 | 2023-10-30 | baseline |
| DreamShaper XL `v2-turbo` | `Lykon/dreamshaper-xl-v2-turbo` | `openrail++` | 101,600 | 2024-02-19 | excluded on current constraints |
| DreamShaper XL lightning | `Lykon/dreamshaper-xl-lightning` | `openrail++` | 70,988 | 2024-03-01 | excluded on current constraints |
| Community `v2-turbo` GGUF | `off-grid-ai/dreamshaper-xl-v2-turbo-GGUF` | `openrail++` | 14,352 | 2026-10-21 | memory-interest, provenance-interest, license-interest conflict |

The practical source of gross repository size was also confirmed: public HF repos contain duplicated fp32 and fp16 component trees. For example, the SSD-1B full repository tree is roughly 26.8 GB, while the practical single-file entry is only the arithmetic delta of about 4.46-4.47 GB.

## 3. Stage 1 architecture fingerprint

### 3.1 Standard shared contract (all five candidates retrieved)

Every retrieved U-Net configuration shares:
- `block_out_channels`: `[320, 640, 1280]`
- `in_channels`: 4
- `out_channels`: 4
- `cross_attention_dim`: 2048
- `attention_head_dim`: `[5, 10, 20]`
- `norm_num_groups`: 32
- `resnet_out_scale_factor`: 1.0
- VAE `scaling_factor`: 0.13025
- CLIP1 text encoder hidden size 768
- CLIP2 text encoder hidden size 1280
- VAE sizes and structure (block-out `[128, 256, 512, 512]`)

### 3.2 The material divergence

| Candidate | `layers_per_block` | `transformer_layers_per_block` | Relationship to SDXL canonical (retrieved below) |
|---|---|---|---|
| SSD-1B | 2 | `[1, [2,2], [4,4]]` | pruned U-Net, fewer transformer tables but standard projections |
| Segmind-Vega | 2 | `[1, 1, 2]` | even more aggressive |
| SDXL base | 2 | `[1, 2, 10]` | canonical baseline |
| DreamShaper `v2-turbo` | 2 | `[1, 2, 10]` | unchanged layer count relative to base |
| DreamShaper lightning | 2 | `[1, 2, 10]` | unchanged layer count relative to base |

### 3.3 Practical implication

- Text encoders and projection dimensions look compatible with the SDXL computational vocabulary.
- The U-Net **geometry** still exposes the same channel budget, but the **position count and density of transformer layers is different**.
- Therefore, "it is an SDXL architecture" does not imply "an SDXL LoRA will resolve cleanly."

This is precisely the risk we already flagged in candidate ranking and now includes as an exact configuration signal.

## 4. LoRA compatibility inference from configuration (not a runtime result)

### A. What structure said

- The coarse target modules (`cross_attention_dim`, `block_out_channels`, `hidden_size 768/1280`) are aligned with SDXL-style LoRA dimensions.
- The transformer-layer table differs, which means the key set would at least need adaptation or selection logic.
- Standard LoRA checkpoints often enumerate blocks at a level count that does not match the pruned adapter.

### B. Current project comparison

The current project's LoRA loader is not an unconditional pass-through. The Flux2 example already required a runtime-specific name conversion patch when tensor names diverged:

- `patches/0001-flux2-lora-name-conversion.patch`
- zero unused tensors after the patch was applied

That precedent argues for caution on SSD-1B and Vega: their own schedules of transformer layers are already different enough that **naming or placement conversion may be necessary**.

### C. Conclusion

- There is no negative proof at this stage.
- There is also no runtime proof yet.  
- Thus, "SSD-1B should probably support LoRAs" remains a hypothesis, not a material fact.

## 5. Stage 0-1 hard/soft verdict

### 5.1 A-pass candidates by hard filters (before memory/\runtime cost)

- **SSD-1B:** passes Apache 2.0 + headers negotiable at Stage 0.
- **SSD-Vega:** passes Apache 2.0 + headers negotiable at Stage 0.

### 5.2 License conclusion

- Apache 2.0 candidates: SSD-1B, SSD-Vega.
- All other tracked candidates remain OpenRAIL++, and DreamShaper Turbo specifically carries a commercial-use caveat.
- **Recommendation based strictly on user's license constraint:** promote only Apache 2.0 candidates, keep the rest as capability comparators.

### 5.3 Candidate rank after Stage 0-1, evidence-backed only

| Candidate | License | Config fit | Sidecar burden | Community maturity | LoRA shape behavior | Evaluation conclusion |
|---|---:|---:|---:|---:|---:|---|
| SSD-1B | clean | close | ~4.46GB + small sidecars | medium | unknown, nonzero mismatch risk | still best trade-off candidate |
| Segmind-Vega | clean | closest channels, fewer layers | ~3.29GB + small sidecars | lower | high mismatch risk | useful secondary/hedge candidate |
| SDXL base | constrained | exact | 6.94GB + configs/tokenizers | very high | expected robust | capability baseline only for license conflict |
| DreamShaper XL | constrained | exact | 6.94GB + sidecars | higher | expected robust | license-active commercial restriction; strong reasons to avoid for B3 default |
| Community GGUF v2-turbo | inherited OpenRAIL | unknown via sd.cpp | Q8 4.18GB, Q4 2.8GB | medium | unverified | memory interest, provenance/asset quality risk |

## 6. Stage 1 sidecar fingerprint (research-only)

### 6.1 SSD-1B pinned config digests (retrieved 2026-11-18)

- `unet/config.json` 1768 bytes, `sha256 34e7893a088737536ce0accd3f9d891c01d092886f88bbfa64a9091cb2501d13`
- `text_encoder/config.json` 560 bytes, `sha256 32d8cadf544d77c231efa1381145ac7e8f4cc88f581455c3c5f6369364474c83`
- `text_encoder_2/config.json` 570 bytes, `sha256 79b0f15ad762cf9c2992d50f9679d08c6cb477a50c88d41e216fc2d886e37abb`
- `vae/config.json` 602 bytes, `sha256 2e425cbde02bdb63e43e8d49db7e14a941a76bb7b2058761200c72dc3d6344fd`

### 6.2 Segmind-Vega config digest (retrieved 2026-11-18)

- `unet/config.json` 1762 bytes, `sha256 c9921241cb90b2bc6039b07d57f8720c77bd728078bfa83b92729f6d9be48713`

### 6.3 Public source URLs used in the fingerprint

- `https://huggingface.co/segmind/SSD-1B`
- `https://huggingface.co/segmind/Segmind-Vega`
- `https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0`
- `https://huggingface.co/Lykon/dreamshaper-xl-v2-turbo`
- `https://huggingface.co/Lykon/dreamshaper-xl-lightning`
- `https://huggingface.co/off-grid-ai/dreamshaper-xl-v2-turbo-GGUF`

These URLs are references only. They are not attestation artifacts.

## 7. Stage-gate state after this report

| Gate | State | Why |
|---|---|---|
| 0 | passed | license and source feasibility are documented sufficiently to choose a pilot |
| 1 | passed | first architecture fingerprint without model download |
| 2 | blocked | no candidate single-file checksum was verified locally yet |
| 3 | not reached | no render test yet |
| 4 | not reached | no LoRA effect probe yet |

## 8. Operator decisions still required before Stage 2

1. Whether SSD-1B or a hybrid candidate is the intended pilot.
2. Whether "LoRA target correctness" means direct LoRA shape match or adapter remapping is acceptable.
3. Whether to keep a secondary candidate as fallback or enforce one-and-only-one.
4. Whether negative prompt should become part of the service contract or stay latent.

## 9. Recommended next command-level activity (still outside assets)

Permit `Stage 2`, but only as a read-only fingerprint extension:
- one selected fp16 single-file, if required
- one config/tokenizer manifest commit in `/tmp/opencode/p10-stage/`
- one local RAM/VRAM load probe
- one negative prompt / CFG behavioral probe

Do **not** integrate it into the project tree (`model/assets/`, entry, adapter, guard, UI).

## 10. Non-goals maintained by this report

- No claim that any candidate was rendered under the service.
- No claim that V303 (SSD-1B) loads and performs better than the current electron baseline.
- No claim that any license restriction is resolved by fiat.
- No claim that Stage 1 fingerprint equals a runtime proof.

If any later measurement contradicts this document, append an amendment instead of rewriting what now reads true.

## 11. End boundary

B3 remains open. P10 remains `planned`. The project tree remains unchanged except for documentation.

No asset, no source, no test, no guard was added.
## Appendix A — Evidence upgrade against the original Attest Claim list (2026-11-18)

This appendix shows which of the earlier “not affirmed / non-affirmation” items are converted from pure speculation to documentary evidence.

### A.1 Documented evidence that replaces some conjectures

| Item | Prior non-affirmation status | New documentary baseline |
|---|---|---|
| **LoRA support expectation** | unverified / not measured | **Confirmed as a product-level capability**: Segmind README describes downstream use with `train_text_to_image_lora_sdxl.py`; `latent-consistency/lcm-lora-ssd-1b` is a consumable LoRA-style targeted adapter for SSD-1B; community DreamBooth LoRA examples exist. |
| **High memory at 1024²** | extrapolated | **Supported by vendor docs**: Segmind reports 12,780 MB inference peak on SSD vs 15,214 MB for SDXL, and idle drop 5,338 MB vs 7,810 MB. |
| **Weight-only disk/F32 memory** | inferred | **Supported by independent estimator and published files**: SSD-1B `SSD-1B.safetensors` is 4,465,671,506 bytes (4.46–4.47 GB) and vendor/independent estimator gives FP16 2.5/3.0 weight/overhead; FP32 5.0/6.0. |
| **Training provenance** | not attested | **Supported by upstream docs**: Segmind states 15M pairs, 4x A100 / ~200 GPU hours, removal of 40 transformer blocks + 1 ResNet; arXiv paper supports the distillation framing; README provides concrete training params. |
| **Speed claims** | secondary anecdotal | **Supported by primary plus community**: Segmind benchmark claims 60%, and 4090 community reports show ~20-30s per generation; this is a public claim, not our own measurement. |
| **LoRA multi-real interaction** | unknown | still unverified, but no claim of certainty was introduced; only single-LoRA usage is documented by public adapters. |

### A.2 Section 11 rewritten (surviving unknowns only)

After this documentary pass, the only things still genuinely unknown for B3 / P10 are:

1. **Exact load-only and warm-render VRAM under our service loader and staged ZIP/cache assumptions.**  
   Vendor peak is strong for 1024² (12,780 MB vs 7,810 MB idle), but the actual staged path in our project may differ.
2. **Exact LoRA target key exactness vs arbitrary SDXL LoRA inputs.**  
   Upstream LoRA training is real, but direct random SDXL LoRA compatibility remains a shape/projection probe outcome, not a product guarantee.
3. **Side-by-side render value under our specific content contract (prompt, seed, quality bar).**  
   Public visual comparisons exist but are not ours.
4. **True boot cost and peak after any adapter remapping.**
5. **Whether the candidate adds capability beyond the current pairing rather than replacing it.**  
   This remains a real question of **need**, not only memory.

### A.3 tightened “does not affirm” wording

- **License boundary:** Apache 2.0 is evidenced primary. Affirmation remains valid.
- **Training boundary:** data scale and parameter removal are evidenced primary.
- **VRAM boundary:** vendor peak is documented; exact host peak not.
- **LoRA compatibility:** LoRA training is supported by product docs and public adapters, but cross-LoRA behavior is not yet evidenced.
- **Quality boundary:** benchmark data is published; project-local evidence is still needed.

If any of these later measurement results contradict this appendix, append an amendment rather than rewriting existing statements.
