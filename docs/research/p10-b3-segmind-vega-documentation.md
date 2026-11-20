# Segmind-Vega — Documented Research Review (Stage 0/1 style)

**Status:** research-only; no asset, no adapter, no integration.  
**Date:** 2026-11-18  
**Candidate role in B3 race:** #1 after SSD-1B was ruled out due VRAM hazard under user's explicit 720p/LoRA headroom rule.

> **Update 2026-11-18 (post-Stage 2).** Two statements in this document are superseded and are kept here as the Stage 0/1 record, not as current fact:
> - *"FP8 available? No vendor fp8 publish; fp16 is the path."* — **A third-party Q8_0 GGUF does exist** (`vonjack/hyper-sd-v1_5-segmind-vegart-gguf`), and it renders 1280×768 and 1024×1024 on this host through the vendored `sd.cpp`. The fp16 path itself was measured and **died by OOM** at 1280×720.
> - The pending items below (load-only VRAM, warm render VRAM, LoRA behavior, cleanup) are **partly closed**: see `p10-b3-segmind-vega-gguf-stage2-report.md` for the measured numbers and for the LoRA gates that remain open.
>
> **Final status: the candidate was ELIMINATED on the same day**, by operator decision after the group-of-people quality test — hands fail in every image and the subject count misses. Both weight sets were deleted; this document and the two Stage 2 reports are retained as an archived, measured rejection.

---

## 1. What it is

Segmind-Vega is Segmind's distilled **SDXL** model family release, with a 70% image-generation footprint decrease versus base SDXL and billed as a 100% speedup. It was put out on Hugging Face under license `apache-2.0`, with tokenizer, scheduler, transfer and reference docs in parallel.

The most important public facts:

- **Apache 2.0** on both repo and GitHub README.
- **Single-file checkpoint:** `segmind-vega.safetensors = 3,293,395,670 bytes ~3.29 GB`.
- **Diffusers-compatible:** loads with `DiffusionPipeline.from_pretrained`.
- **VCPU / stack:** Standard SDXL latents (our project's remote runtime is not fixed to it).

### 1.1 Architectural sketch from published material
From the HF and blog docs, Vega presents:
- Down block: `247M`
- Mid block: `31M`
- Up block: `460M`
- Total: **~738M ≈ 0.74B**
- Same high-level U-Net shape as SDXL, so prompt/output expectations overlap with standard SDXL.

That smaller U-Net is why it is often called "70% smaller than SDXL" and "symmetrical distillation".

### 1.2 Tokenizer and config facts in our probe (Stage 0)
- `unet/config.json` 1762 bytes, sha256 `c9921241cb90b2bc6039b07d57f8720c77bd728078bfa83b92729f6d9be48713`
- `text_encoder/config.json`: `CLIPTextModel`, hidden size `768`, 12 layers, 12 heads, vocab 49,408
- `text_encoder_2/config.json`: `CLIPTextModelWithProjection`, `1280`, 32 layers, 20 heads, vocab 49,408
- `vae/config.json`: `AutoencoderKL`, `scaling_factor 0.13025`
- `unet/config.json` structural layout:
  - `block_out_channels [320, 640, 1280]`
  - `layers_per_block 2`
  - `transformer_layers_per_block [1, 1, 2]`

### 1.3 Size, weight and how to load
- Repo full size ~17.64GB, but operational minimum is:
  **3.29GB checkpoint + small configs/tokenizers**
- It supports fp16 model and standard `prompt, negative_prompt`.
- HF model card recommends **CFG ~9.0**.
- It is `diffusers` only; looting reports a `_class_name: StableDiffusionXLPipeline`.

---

## 2. Verifiable facts vs vendor claims

### 2.1 Solid facts from sources
- Apache 2.0 in the files and README. on HF metadata.
- Public load is the verifyable pattern via HF `from_pretrained`.
- License license text itself is Apache 2.0 (GitHub repository / HF).
- checkpoint itself: `segmind-vega.safetensors = 3,293,395,670 bytes` exact.
- Tokenizer dimensions match SDXL: 768 and 1280.
- Release date: created 2023-11-30, modified 2024-01-08.
- Downloads today: ~5,026.
- Community likes: 132.
- Datasets mentioned: GRIT + `wanng/midjourney-v5-202304-clean`.
- trained 540k steps, batch 16, gradient accumulation steps 8, lr 1e-5, 1024 resolution, fp16, knowledge distillation.
- Model source: citation ID arxiv `2401.02677`.

### 2.2 Documented but still partially imprecise
- “Vega is an LCM-LoRA model, so negative prompt and guidance scale parameters would not be applicable.” appears in the blog as limitation wording while the model card code **does** use `negative_prompt` and `CFG`.
- This seems to be either an inaccurate limitation line or a confusion with VegaRT.
- Do not assume Vega itself is fixed at LCM-style chat / guidance omission.
- The HF README and API code clearly show standard `pipe(prompt=..., negative_prompt=...)`.

---

## 3. What it gives and takes relative to the current system

### 3.1 Official capability highlights
- **70% reduction vs SDXL**
- **100% speedup** according to Segmind
- Up to 1024 resolution on a smaller A100-class graph
- Headed to use faster inference on modest GPU
- Style metrics include:
  - cyberpunk portrait
  - general artistic rendering
  - text-to-image
- This makes it a natural “hedge memory fit”.

### 3.2 Public benchmark claim (vendor only)
- A100 latency:
  - uncompiled Vega: 1.39 s at 1024x1024
  - compiled Vega: 0.86 s at 1024x1024
  - SDXL: 3.35 s uncompiled at same size; SD1.5 at 768 at 1.42 s
- Vega latency at 1024 is faster than SDXL.
- These are vendor-run numbers, not measured in this project.

### 3.3 Limitations from the actual documentation
- "close-up portraits of humans" are better; full-body prone to limbs/face deform.
- "variability of images tends to be low"
- Because of distillation, some style nuance is absent.
- SAI upstream was an OpenVINO path warning about memory size:
  - A 512x512 VegaRT path needed 27GB and base path 53GB at the upper end
  - but that is an OpenVINO IR path, not a project loader path.

---

## 4. FP8 status

### 4.1 Official / direct
- **No checked official fp8 file** in the HF repo `segmind/Segmind-Vega`.
- The surface is `safetensors` + diffusers.
- No release card, community comment, or repo file surfaced in this Stage 0-1 check with fp8.
- In the `automagically` report, only "binary, no fp8 mention".

### 4.2 Community
- No evidence surfaced in this research that there is a reliable third-party fp8 converter.
- There’s one `OpenVINO` INT8 conversion for VegaRT and VEGA-base, but that's irrelevant to the native project runtime.

### 4.3 What it means
- Vega must be evaluated on its **fp16 path** first.
- If a future fp8 converter arrives and remains compatible, the download would shrink, but:
  - weight size isn't the memory bottleneck
  - activation entropy / style loss / structural damage is harder to verify.

## 5. LoRA compatibility

## 5.1 Upstream evidence
- Vega is a distilled SDXL with the usual SDXL CLIP and VAE.
- Upstream says training is with a distillation-based retraining method.
- The HF card explicitly allows negative prompt and recommends **CFG ~9.0**.

### 5.2 If you want random SDXL LoRAs
- Key probes matter, **because the structural blocks differ**:
  - SSD pruning removes 40 transformer blocks + 1 resnet block and mid-block attention differences are declared
  - Vega transformer layer count `[1,1,2]`
- A standard SDXL LoRA is not guaranteed to directly resolve, even if the base looks SDXL-shaped.
- Vega's lower block count is even more problematic than SSD-1B on that same question.
- That means Vega is **compatible in spirit, risky in key parity**.

### 5.3 Conditional LoRA success tests (required)
- **L1 key accept / mismatch**
- **L2 measured non-zero effects**
- **L3 stack management**
- If any L fails, Vega is not ready regardless of memory.

---

## 6. Pros and cons

### 6.1 Pros
- **Apache 2.0 clean**
- very resource-light (~3.29 GB)
- explicit training metadata (540k steps, batch 16, grad 8, lr 1e-5, 1024, fp16)
- text-to-image on SDXL-compatible pipeline
- negative prompt available
- A100 fast latency (`1.39s` uncompiled / `0.86s` compiled at 1024)
- derived LCM LoRA adapter (`segmind/Segmind-VegaRT`)
- GFLOPs (?) not disclosed; community adapted or annotated with annotation tags (no fp8)
- open source licensing

### 6.2 Cons
- Existing user-facing docs are somewhat contradictory:
  - `negative_prompt` and `CFG` are supported, but an optimization-text confused Vega with LCM
  - that scares clean operational use if the docs contradict themselves
- Dist distill means narrower output variance.
- Slimmed-down transformer; LoRA mapping risk is high.
- Community of only ~5,026 downloads and closeout docs gave mixed signal (2023–2024 only).
- Harbor VRAM not exactly published; inference itself still likely peak-heavy.
- non 60% weight savings of SSD; the distillation's "70% reduction" excludes much internal FP16 inefficiency (transformer layers removed earlier in public note).

### 6.3 Required unresolved unknowns (real ones)
- load-only VRAM on our loader
- `1280x720` warm render VRAM on our service path
- L1 key behavior
- L2 non-zero effect behavior
- L3 stack behavior
- output quality under the project contract (prompt/seed/candidate width)
- licensed permission is clear
- downstream LoRA quality beyond “just works in notebook”

---

## 7. Stage-gate state with Vega

This document does **not** promote it.

### Passed:
- License
- Clearly Apache-like file set
- distil size small
- structural similarity (SDXL parent)
- basic negative-prompt declaration

### Pending:
- Loader-format in this service runtime
- exact byte signature
- load-only VRAM
- warm render VRAM
- LoRA behavior
- quality-economics
- cleanup/reversibility

If any one of these fails, Vega goes where Community GGUF sits: reference-only / no integration.

## 8. Final dignity assessment

Vega is **worth having in the race**, but only as a memory-pressure hedge. It is not a “drop-in replacement” and certainly not a definite win if SSD was already high-risk on architecture/part of the headroom.

### Short version
- **Cleaner licensing?** Apache 2.0 = yes.
- **Lower disk load?** Yes (~3.29 GB).
- **Predictable SDXL adaptation?** Maybe; block count lower means **possibly no**.
- **Proven quality in your project?** No.
- **LoRA safety confidence:** needs memory + keys stage.
- **FP8 available?** No vendor fp8 publish; fp16 is the path.

If SSD-1B is eliminated by VRAM, Vega becomes the first next test. That is the pragmatic board state.
EOF
echo done