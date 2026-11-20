# SDXL canonical — research report and preferred third-party quantization

**Status:** research only. No asset download, no adapter change, no runtime integration.  
**Date:** 2026-11-18  
**Candidate role:** compatibility baseline / non-primary candidate.  
**Purpose:** capture the verified disk cost, quantization options, license posture, and the best third-party quantization path for SDXL canonical under this project's 720p + LoRA-headroom rule.

## 1. Base facts

| Item | Verified value |
|---|---|
| Canonical artifact | `sd_xl_base_1.0.safetensors` |
| Disk size (canonical single-file) | `6,939,220,250 bytes` ≈ **6.94 GB** / 6.46 GiB |
| Sidecars (tokenizer + config) | ≈ **2.5–3.3 MB** |
| Optional refiner | ≈ **6.08 GB** extra |
| License | **CreativeML Open RAIL++-M / OpenRAIL-M** |
| Official FP8 / INT8 checkpoint | **not found** in the canonical Stability repo |
| Architecture | SDXL 1.0 base, dual CLIP encoders, VAE, UNet, native 1024×1024 |
| Community / ecosystem | very large, strong LoRA / ControlNet / refiner support |

## 2. What SDXL canonical offers

- Strong **generalist** text-to-image base.
- Native **1024×1024** output.
- Excellent **LoRA interoperability** and community ecosystem.
- Real **negative prompt** and **CFG** semantics.
- Broad support for:
  - ControlNets
  - refiner workflows
  - face/detail tooling
  - schedulers
  - image editing extensions.

## 3. Known limitations

- License is **not Apache 2.0**.
- The canonical weight is **~6.94 GB**, and runtime peak can exceed small-GPU limits at 1024².
- The VAE decode path can still push memory demand even when the UNet is quantized.
- Hands/fingers and micro-detail artifacts are a known weakness of the base family.
- A separate refiner (~6.08 GB) may be needed for maximum quality, but it is not part of the base artifact.
- No official Stability-published INT8/FP8 artifact was found in the canonical repo.

## 4. Third-party INT8 / GGUF options

| Source | Format | Size | Notes |
|---|---|---:|---|
| `kostakoff/stable-diffusion-xl-base-1.0-GGUF` | GGUF | **Q8_0 4.18 GB** / Q4_K 2.80 GB / Q4_0 2.71 GB | Most aligned with `stable-diffusion.cpp`; single-file GGUF; documented conversion |
| `HyperX-Sentience/SDXL-GGUF` | GGUF | UNet Q4_K_S **1.49 GB** / Q8 2.76 GB | Separate UNet/VAE/CLIP; more fragmented |
| `hum-ma/SDXL-models-GGUF` | GGUF | Base **Q4_0 1.39 GB** | ComfyUI custom-node oriented |
| `gpustack/stable-diffusion-xl-base-1.0-GGUF` | GGUF | Q8_0 **5.04 GB** / Q4_0 3.94 GB | Experimental llama-box path |
| `imgailab/sdxl-torch-int8` | PyTorch INT8 | ~**3.2 GB** memory | Very early, low confidence |

## 5. Preferred third-party quantization

**Recommended artifact:**  
**`kostakoff/stable-diffusion-xl-base-1.0-GGUF`**, using **Q8_0** (`4.18 GB`).

### Why this one
- It is a direct conversion of the canonical **SDXL base 1.0**.
- It is packaged as a **single-file GGUF** for `stable-diffusion.cpp`, the runtime this project already understands.
- It keeps the weight close to the original architecture while reducing disk footprint from ~6.94 GB to ~4.18 GB.
- The model card documents:
  - the conversion method,
  - runtime usage,
  - a VAE-decoder VRAM caveat.

### Fallback option
- **Q4_K 2.80 GB** from the same repo, only if the memory constraint becomes absolute and a quality loss is acceptable.

## 6. Memory and Stage 2 caveat

Even with the **4.18 GB Q8_0 GGUF** artifact:

- The **VAE decoder** can consume up to **~10 GB of VRAM** if left on the GPU.
- The model card therefore recommends running with `--vae-on-cpu` on consumer cards.
- The project’s 720p rule still requires a measured Stage 2 run:
  - `load_only`
  - `warm_render`
  - one LoRA probe
  - three distinct LoRA stack
  - cleanup
  - measured VRAM peak under the service contract.

Disk size alone does not prove runtime fit.

## 7. License posture for public content

`OpenRAIL++-M` generally permits commercial use, including:
- YouTube videos,
- advertising images,
- public distribution of generated content,

provided:
- the use falls inside the acceptable-use restrictions,
- attribution/redistribution terms are respected when the model or a derivative is redistributed,
- generated content does not violate third-party rights, likeness, trademark, or platform policy.

It is **not** an Apache 2.0 license and should not be treated as unconditional. For strict product use, the exact license text should be reviewed before integration.

## 8. Stage 2 status

Stage 2 has **not** been run for SDXL canonical.

Before promoting this artifact:
- pin exact checksum,
- verify `load_only` and `warm_render` VRAM,
- verify a 1-LoRA non-zero effect,
- verify a 3-distinct-LoRA stack,
- verify cleanup,
- confirm the VAE-decoder path does not break the 720p + LoRA-headroom rule.

## 9. Summary

- SDXL canonical is a strong **compatibility baseline**, but not the current primary candidate.
- The best third-party quantization path for this runtime is **`kostakoff/stable-diffusion-xl-base-1.0-GGUF`**, preferably **Q8_0 4.18 GB**.
- The VAE-decoder VRAM cost must be measured before any P10 promotion.
- License permits public/commercial use under OpenRAIL restrictions, but it is not Apache-clear.
- B3 remains open, P10 remains planned.

