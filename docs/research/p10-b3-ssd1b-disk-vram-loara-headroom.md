# SSD-1B — Documento de consumo: disco, VRAM, y cabeza LoRA

**Status:** research-only. No implementation, no asset download, no readiness claim.  
**Date:** 2026-11-18  
**Candidate focus:** Segmind SSD-1B (Apache 2.0)

## 1. Residencia mínima necesaria (sólo bytes operativos)

### 1.1 Artifact a descargar en el árbol propio

Para SSD-1B no existe una cuantizada oficial verificada. El único artefacto de peso que tu `model/assets/` debería poseer es:

| Asset type | File name | Peso (bytes / bin) | Estimado humano | Why needed |
|---|---|---:|---:|---|
| Checkpoint | `SSD-1B.safetensors` | 4,465,671,506 | 4.47 GB (4.16 GiB) | Whole current transfer artifact; includes packed weights |
| Tokenizer 1 | `tokenizer/vocab.json` | 1,059,962 | 1.01 MiB | tokenizer vocab, not temp file |
| Tokenizer 1 | `tokenizer/merges.txt` | 524,619 | 0.50 MiB | merge tables |
| Tokenizer 1 | `tokenizer/tokenizer_config.json` | 737 | 0.0007 MiB | metadata/config pointer |
| Tokenizer 1 | `tokenizer/special_tokens_map.json` | 472 | 0.0004 MiB | special-token map |
| Text encoder 2 | `text_encoder_2/config.json` | 570 | 0.0005 MiB | structured loader params |
| VAE | `vae/config.json` | 602 | 0.0006 MiB | decode side activation |
| Scheduler | `scheduler/scheduler_config.json` | 474 | 0.0005 MiB | sampling plan |
| Model index | `model_index.json` | 577 | 0.0006 MiB | core resolution target |
| UNet config | `unet/config.json` | 1,768 | 0.0017 MiB | rebuild/load config (tiny) |
| Text encoder config 1 | `text_encoder/config.json` | 560 | 0.0005 MiB | rebuild/load config (tiny) |

### 1.2 Disk runtime footprint (no hidden repo blowup)

- **Checkpoint only:** 4.450–4.475 GiB
- **Config + tokenizer sidecars:** ~2.5 MiB
- **Total real (min):** **~4.48 GB** total (pinned single-file plus tiny declarations)

This is sharply lower than the **~26.8 GB** full repository layout, which is not a mandatory purchase.

## 2. VRAM consumption and capacity (critical)

### 2.1 Estimative memory vs measured signal

| Metric | Value | Status |
|---|---:|---|
| HF “weight size single-file” | 4,465,671,506 B | blob download; model written once |
| HF “unet/config structural `fp16` loss” | 1,768 bytes, small | structural loader side; not relevant VRAM |
| Host torch-usable (existing system) | 7,857 MiB | hard cap from runtime host |
| **Vendor-reported idle peak @ 1024²** | 5,338 MiB | public signal, not our probe |
| **Vendor-reported inference peak @ 1024²** | 12,780 MiB | public signal, not our probe |
| Independently modeled FP16 weight | ~2.5 GiB | aquanode class withdraw estimator |
| Runtime FP16 weight under our staging | **unknown** | probe staged load required |
| Project staged Z-Image peak @ default box | 4,815 MiB | measured project signal (using encoder/VAE stages) |

### 2.2 Why “fits 4.46 GB” is misleading on its own

The weight is ~4.46 GB, but:

- TensorFlow / PyTorch / Diffusers conserves activation buffers
- text encoders/VAE stages add transient burden
- scheduler/noise and block cache add extra memory
- LoRA at scale increases VRAM with loader bookkeeping

Vendor numbers publish **idle ~5.3 GiB / inference ~12.8 GiB at 1024 x 1024**, which already sits above **7,857 MiB**. Even fp8 `Aquanode`-type numbers (FP8 1.2 GiB weight / 1.5 GiB VRAM requirement) shift the theoretical ground, not the real inference peak.

### 2.3 Core distinction

- 4.46 GB is **download weight**.
- 5.3 GiB idle is **loaded cost** before request.
- 12.78 GiB is **peak under inference**.
- Those are not interchangeable.

## 3. LoRA headroom and model fit

This candidate can be considered successful only if all three LoRA probes pass on Stage 2:

| LoRA probe | Bad outcome | Candidate disqualification failure |
|---|---|---|
| L1 key-shape | missing target name or mismatch | adapter must remap aggressively |
| L2 effect | non-zero LoRA effect cannot be observed | useless silent failure |
| L3 stack | cannot hold a tiny fixed allowance | capacity margin is unusable |

### 3.1 LoRA memory reality from current system

From the project’s documented behavior:

- 325 MB LoRA ≈ +313 MiB memory + +1.5 s wall
- linear to ~11 distinct LoRAs, then plateau ~7.6 GiB with wall doubling
- only a 3,200 MiB request-level budget is nominally admitted
- if a LoRA applies without effect, that is treated as a worse result than refusal

That means:

1. Base model must leave headroom
2. LoRAs consume additional memory
3. At least 3 distinct LoRA layers need validation
4. Single-file weight size only is **not enough** to declare readiness

## 4. Practical reading in this system

| Metric | Target/Published | Reading for this machine |
|---|---:|---|
| fp16 weight (download) | ~4.465 GiB | not the runtime problem |
| Idle VRAM (vendor benchmark) | 5.338 GiB | already huge versus usable envelope |
| inference peak (vendor benchmark) | 12.78 GiB | likely impossible under 1024² on 8GB torch-usable card |
| fp8 theoretical weight (not verified) | ~2.2–2.5 GiB | helps deserialize, not automatically peak |
| measured project baseline (Z-Image) | 4.815 GiB peak | better local signal |
| usable card | 7.857 GiB | hard cap |
| minimum sensible LoRA headroom | reference 1 LoRA ~0.3 GiB + effect | leaves only ~1.5–2 GiB for load/activations |

Therefore, **SSD-1B is not an automatic fit on your 8GB card in any broad scale, despite 4.46 GB weight.** At the very least, target output must be lowered or offload/staging must be altered.

## 5. Excluded claims (explicitly retained)

This file does **not** assert:
- actual staged loader peak for SSD-1B on this host;
- LoRA key behavior on arbitrary SDXL LoRAs;
- realized cost/economics versus current models;
- quality under any prompt/seed contract.

If Stage 2 is run later, those must be appended and the values above must be compared to the true measured numbers.

## 6. Minimum requirement for candidate advancement (practical checklist)

- [ ] `Stage 2` has been run in an isolated harness.
- [ ] One pinned single-file (`SSD-1B.safetensors`) has been pinned with exact digest.
- [ ] Baseline load VRAM recorded.
- [ ] Warm render VRAM at target size recorded.
- [ ] 1 LoRA effect probe recorded.
- [ ] 3 distinct LoRA stack recorded.
- [ ] No load-time hidden remote Hallucination.
- [ ] Base / LoRA memory budget truly leaves headroom.
- [ ] Cleanup is untestable.

## 7. Final memory answer for the VRAM question

**SSD-1B spends on disk roughly ~4.5 GB (4.46–4.48 GB) plus ~2.5 MiB config sidecars** when staying limited to the necessary artifacts, not the full-HapingFace repo.

**On VRAM, the documented vendor peak is 12.8 GB at 1024²**, much above your usable 7,857 MiB. So **SSD-1B is not obviously viable at 1024²**, while its weight size alone is much smaller than people might assume.

This means:
- **disk cost:** reasonable
- **runtime cost:** potentially high
- **LoRa headroom:** unverified, and likely threatened by the peak
- **approval as a P10 candidate:** still pending Stage 2.
EOF
echo done