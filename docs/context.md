# Context

## Purpose

`coltman-images` is an independent, self-owned image generation service. It turns a generation request into a still and owns its whole lifecycle: power on and warm up, serve generations, shut down. It carries its own connection layer for applications — a loopback HTTP API an application integrates against, with the CLI as its first client — and exposes three commands: `coltman-images start`, `coltman-images generate`, `coltman-images stop`. It is named for the service, not for a model: the core is model-agnostic, and Z-Image is one adapter behind it. The model is an asset its own entry declares and uses; it is not the model's owner. It runs with no other project present. The model assets, the entry, the render core, the Z-Image adapter, the upscale stage, the server and the CLI are all in place, and the guards that prove them are executable (`docs/protocol.md` section 10).

## Structure

The layout is declared once, in `docs/protocol.md` section 3. This document does not repeat it: a list in two places is a list that drifts.

## Vocabulary

- **service** — the whole system: three commands, one model entry, one API, one lifecycle.
- **server** — the process `coltman-images start` launches; it holds the GPU and serves `127.0.0.1:8420`.
- **warm-up** — one full generation at the entry's declared shape, prompt and seed, run before the port is bound; its output is discarded.
- **request** — one generation request object (protocol section 4.1).
- **response** — one generation response object (protocol section 4.2).
- **census** — the loader's count of parameter dtypes, scales excluded: 239 float8, 282 plain, 0 other, 521 total; proof that the FP8 weights loaded.
- **entry** — `model/entry.yaml`, the single declaration of which assets, sampling regime and defaults the service uses.
- **default folder** — `out/`, where a still is written when the request omits `out`.
- **stage** — the declared upscale pass (protocol section 6.2). It runs only when the request permits it and asks for an area the render cannot reach; it is the system's own capability, not a property of the model.
- **SD** and **HD** — SD is the native render with nothing synthesized; HD is a delivered size above the native ceiling, and it must be asked for. The response says which one you got: `upscale: null` is SD, a `upscale` object is HD and names the base it started from.

## Environment

The system owns its inputs. The checkpoint and every component live in `model/assets/` as the project's own copies — real bytes on this filesystem, not an alias into another project, so nothing another project does can change what this one renders. The transformer config is a copy too, `model/z_image.json`, 473 bytes, pinned by digest `06d49d1a…c06af8`.

Their origin, kept as provenance only — both paths are gone:

- the foreign model store (a checkpoint tree with its bench and runtime venvs) — deleted 2026-11-15 with the runtime it lent.
- the foreign component store — deleted 2026-11-15 on the operator's instruction. It held the VAE and its config, the scheduler config, the `Qwen3/` encoder and the only INT8 Z-Image checkpoint on the machine. The copies here are the only copies now, and the INT8 model is gone from the machine as well: the operator ran the A/B and discarded it on 2026-11-16, so the system has one arm.

The interpreter is the project's own: `.venv/bin/python` (Python 3.14.8, torch 2.13.0+cu130, CUDA 13.0). It is created from pinned requirements and lives inside the tree, so the system reads nothing outside itself. The foreign venv that store carried is no longer a dependency.

The checkpoint declares its own quantization recipe in its safetensors header: `unsloth_format = unsloth_prequant_transformer_state_dict_v1`; `unsloth_metadata` (`scheme: fp8`, `quant_backend: torchao`, `fp8_granularity: per_row`, `transformer_class: ZImageTransformer2DModel`, `torch_dtype: bfloat16`); and `unsloth_quant_layout` (`<fqn>._weight_qdata` F8_E4M3 `[out, in]` plus `<fqn>._weight_scale` F32 `[out, 1]`, dequantized as `weight = qdata * scale` per output row). The file stores 760 tensors: 239 `F8_E4M3` `_weight_qdata`, 239 `F32` `_weight_scale` and 282 `BF16` plain. The census counts parameters, not tensors: a quantized parameter is its `_weight_qdata`, counted as float8, and its `_weight_scale` is not a parameter and is not counted — so 239 + 282 = 521. Two root tensors travel with the `unsloth_root::` prefix (`cap_pad_token`, `x_pad_token`) and are remapped on load. The loader is derived from this header, not from inherited code. The vendor card adds one requirement the header does not state: the loader must floor the dynamic activation scale (`activation_value_lb=1e-12` on torchao 0.13+), so an all-zero activation row cannot produce a zero scale. It also states that loading a pre-quantized checkpoint is bit-identical to quantizing the dense bf16 transformer on the fly, and that the format was validated on torch 2.12.1 with torchao 0.17.

The text encoder is the pipeline's own prompt encoder, not a language model bolted on. `model/assets/qwen3/` holds `Qwen3ForCausalLM` — hidden size 2560, 36 layers, 32 heads with 8 KV heads, vocabulary 151936, which is Qwen3-4B — quantized to int8 (4.41 GB) with its tokenizer beside it. The transformer's `cap_feat_dim: 2560` is exactly that hidden size, which is why the encoder cannot be swapped for another size. The prompt is encoded once per request and the DiT is conditioned on those features; the encoder is not a variable of the render.

The project's own `.venv` carries `fastapi`, `starlette` and `uvicorn` now — `gradio` brought them for the UI of P9 — and the API still uses the standard library `http.server`, by decision and not for want of a framework: the surface is three endpoints and a queue, and the UI brings its own server beside it. It carries pydantic 2.14.3, PyYAML 6.0.3, httpx 0.28.1 and requests, and for the render torch 2.13.0+cu130, torchao 0.18.0, diffusers 0.40.0, transformers 5.17.0, safetensors 0.8.0, accelerate 1.12.0, optimum-quanto 0.2.7, Pillow 12.3.0 and numpy 2.4.6. `optimum-quanto` is what the int8 `Qwen3` weights need; the `optimum` name resolves through its namespace package. `gradio` 6.32.0 is the UI's rendering, installed on top of the same pins without moving any of them. Dependencies are pinned and installed into this venv, which the project owns.

The card is 8188 MiB: the 6.29 GB of FP8 weights fit with ~1.9 GiB left for activations, two models do not. Parallel workers are physically refused, so concurrency is single-flight.

Both quantization arms were measured on 2026-11-13 with the transformer as the only variable: FP8 at 36.14 s warm and 36.01 s cold per image, 3.01 s/step, 9.59 s setup, 4651 MiB peak, against INT8 at 42.65 s warm and 44.13 s cold, 3.56 s/step, 74.00 s setup, 6249 MiB peak. FP8 is faster by 15–18 %, lighter by 25.6 %, and pays 87 % less setup. The quality axis runs the other way: the blind adjudication of 2026-11-15 closed INT8 2, FP8 0, tie 1. The operator's closing ruling of 2026-11-16 closes the question: the operator ran the A/B and discarded the INT8 model, so FP8 is the production default and the system has one arm; the numbers and the adjudication are in `docs/reference/`.

## Known issues

- No idle timeout by default. The server never self-terminates unless `start --idle-timeout SECONDS` declares a period, and that is the operator's choice, not an omission: idle, the server costs a process, a port and ~165 MiB, and the GPU is free between requests (protocol section 6).
- The checkpoint's header records the exporter's stack — torch 2.12.1+cu130, torchao 0.17.0+cu130, diffusers 0.40.0.dev0 — while the production runtime is torch 2.13.0. P2 validates the loader against the runtime it actually runs on; the header is a record of the export, not a requirement.
- This project has no other home and no other name. Any other path or executable name claiming to be this system is stale.
- The model assets are inputs: the system reads them and nothing writes them. The interpreter is the project's own `.venv`, and the only dependencies in it are the ones `requirements.txt` pins.
