# Upstream documentation

Five vendor documents, fetched verbatim on 2026-11-15 and stored without edits:

| File | Source |
| --- | --- |
| `unsloth-Z-Image-Turbo-FP8.md` | `huggingface.co/unsloth/Z-Image-Turbo-FP8` |
| `Tongyi-MAI-Z-Image-Turbo.md` | `huggingface.co/Tongyi-MAI/Z-Image-Turbo` |
| `Tongyi-MAI-Z-Image.md` | `huggingface.co/Tongyi-MAI/Z-Image` |
| `Tongyi-MAI-Z-Image-github-README.md` | `github.com/Tongyi-MAI/Z-Image` |

They are reference, not law. `docs/protocol.md` is the law; this directory is where the vendor's own words live so a future step never has to recall them. Do not edit these files: if upstream changes, fetch again and record the new date here.

The FP8 card declares `license: apache-2.0` in its frontmatter; the base model cards carry their own terms. Read the card before redistributing anything.

## The two variants, by the vendor's own table

Verbatim from the Z-Image model card:

| Aspect | Z-Image | Z-Image-Turbo |
| --- | --- | --- |
| CFG | ✅ | ❌ |
| Steps | 28~50 | 8 |
| Fine-tunability | ✅ | ❌ |
| Negative prompting | ✅ | ❌ |
| Diversity | High | Low |
| Visual quality | High | Very High |
| RL | ❌ | ✅ |

These are **not two quantizations of one model**. They are two checkpoints with different training. What follows from the table:

- **Negative prompting exists only on Z-Image.** Turbo runs guidance 0.0, and the installed diffusers ignores `negative_prompt` below guidance 1 (protocol section 4.1).
- **Diversity is the axis that differs most**, and it differs by design: Z-Image varies composition, identity and lighting across seeds; Turbo commits to one plausible interpretation. That is the documented mechanism behind "the model invents things": a distilled, no-CFG model fills an under-specified prompt with confidence.
- **The vendor's own documents disagree on Z-Image's diversity**: the Hugging Face card says *High*, the GitHub model-zoo table says *Medium*. Only the direction (Z-Image more than Turbo) is consistent across both.
- **Cost**: 28–50 steps with CFG against 8 forwards without. CFG runs two passes per step, so the base variant performs 56–100 forward passes against Turbo's 8 — **7× to 12.5× the compute per image**, by arithmetic on this table, not by measurement. At this machine's measured 3.01 s per forward that is roughly 3–5 minutes per image, against Turbo's measured 36 s.
- **Size is the fixable half of that problem.** The base transformer is 12.31 GB in BF16; at FP8 it would be about 6.2 GB, which fits this card the same way Turbo's 6.29 GB does. The time is not fixable: quantization halves the bytes, not the step count or the CFG passes.
- **Fit**: the base checkpoint is 12.31 GB in BF16 against this machine's 8188 MiB card — it does not fit unquantized. Quantized it would. The reason this project is built on Turbo is the cost above, not the bytes.

## The two quantizations of Turbo, by the vendor's own card

- int8: `Int8DynamicActivationInt8WeightConfig` — per-token activation, per-channel weight, `torch._int_mm`.
- fp8: `Float8DynamicActivationFloat8WeightConfig` with **PerRow** granularity — e4m3, `torch._scaled_mm`.
- **The loader must floor the dynamic activation scale** (`activation_value_lb=1e-12` on torchao 0.13+) so an all-zero activation token row cannot produce a zero scale.
- Loading a pre-quantized checkpoint is **bit-identical** to quantizing the dense bf16 transformer on the fly; the checkpoint only skips the dense load and the quantize step.
- Validated on **torch 2.12.1 and torchao 0.17**, exactly what the checkpoint's header records.
- Vendor LPIPS against bf16: **0.130 FP8**, 0.181 INT8.

Same weights, same training, different numeric representation: the documented difference between the two quantizations is **representational, not behavioral**. Any claim that one of them "hallucinates more" has no vendor documentation behind it and is not measured in this project.

## What the Turbo card adds

- Turbo is distilled for **8 NFEs**, and **guidance must be 0**.
- The vendor example calls `num_inference_steps=9` with the comment *"This actually results in 8 DiT forwards"* — the scheduler performs one fewer forward than the step count. See `docs/protocol.md` section 12.
- The vendor's example resolution is 1024×1024. This project's production regime is 1280×720, which is legal under the multiple-of-16 rule.
- The prompt encoder is the pipeline's own `text_encoder` subfolder: **Qwen3ForCausalLM, Qwen3-4B** (hidden 2560, matching the transformer's `cap_feat_dim`). It is not a separate model bolted on, and it cannot be swapped for a different hidden size.
- The vendor publishes the quantized transformers as `.pt` state dicts; the file this project uses is a safetensors container declaring the same format id in its header.
