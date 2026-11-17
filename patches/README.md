# Patches to the vendored runtime

`vendor/` is installed, not committed (protocol section 2). Anything this
project changes inside it therefore has to travel as a patch file, applied after
the clone and before the build — otherwise the change is lost the next time the
runtime is installed.

## `0001-flux2-lora-name-conversion.patch`

**Against** `stable-diffusion.cpp` at commit `532d2c1` (2026-11-15), the commit
the tree is pinned to. It touches one file, `src/name_conversion.cpp`, and adds
seven name mappings.

**Why.** `sd.cpp` converts a diffusers checkpoint's tensor names to the names its
own model uses, and the conversion table was written for FLUX.1. FLUX.2 spells
four families differently, and the converter had no entry for any of them, so a
FLUX.2 LoRA loaded, reported `apply lora at runtime`, and then **discarded half
its tensors as unused** — 86 of 172 — while the render completed without an
error. The half it kept was attention; the half it dropped was every MLP and the
fused projection, which is where a style lives. Measured before the patch: a
pixel-art LoRA at weight 1.0 changed the still by a mean of 4.8 out of 255,
which is nothing.

| Diffusers spelling | The runtime's spelling |
| --- | --- |
| `transformer_blocks.N.ff.linear_in` | `img_mlp.0` |
| `transformer_blocks.N.ff.linear_out` | `img_mlp.2` |
| `transformer_blocks.N.ff_context.linear_in` | `txt_mlp.0` |
| `transformer_blocks.N.ff_context.linear_out` | `txt_mlp.2` |
| `single_transformer_blocks.N.attn.to_qkv_mlp_proj` | `single_blocks.N.linear1` |
| `single_stream_modulation.linear` | `single_stream_modulation.lin` |
| `double_stream_modulation_{img,txt}.linear` | `double_stream_modulation_{img,txt}.lin` |

**Measured after the patch:** zero unused tensors, and the same LoRA on its own
prompt — `pixel art sprite, a brave knight in shining armor holding a sword, game
asset, transparent background` — turns a photograph-style still into a pixel-art
sprite with a transparent background. Mean difference against the same prompt
without the LoRA: **40.2 of 255**.

## Build order

```sh
git clone https://github.com/leejet/stable-diffusion.cpp vendor/stable-diffusion.cpp
cd vendor/stable-diffusion.cpp
git checkout 532d2c1
git submodule update --init --recursive
patch -p1 < ../../patches/0001-flux2-lora-name-conversion.patch
cmake -S . -B build -DSD_CUDA=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=89
cmake --build build -j 8
```

## Maintenance

This is a fork of one file, and forks rot. On any upgrade of the vendored
runtime the patch either applies, or it is rebased by hand against the new
`name_conversion.cpp`, or the mapping has landed upstream and the patch is
deleted — which is the preferred ending. Nothing else in this project depends on
it: a tree built without the patch serves every entry and renders every still
exactly as before; only FLUX.2 LoRAs are half-applied.
