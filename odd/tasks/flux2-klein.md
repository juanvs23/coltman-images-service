# FLUX.2 [klein] 4B — two runtimes, one model, one removed

## Objective

Bring FLUX.2 [klein] 4B into the service as a second model, through two of the
three artefacts Black Forest Labs ships for it: the official scaled-FP8
safetensors (read by diffusers) and the community Q4_K_M GGUF (read by
`stable-diffusion.cpp`). Measure both, then adopt one. **Closed 2026-11-17: the
operator adopted the `ggml` runtime and the diffusers path was removed with its
assets.**

## Problem

The card is an RTX 4060 Laptop with 8188 MiB total and 7857 MiB usable. The
model card asks for ~13 GB. Neither official artefact is a complete pipeline:
both are transformer-only, and the Qwen3-4B text encoder in bf16 is 8.05 GB, so
it cannot live on the card at all.

## Why

Z-Image is the only entry today and it costs 6698 MiB at 1280×720. A second
model at the same or lower cost, with text-to-image *and* multi-reference
editing from one checkpoint, is a real capability gain — but only if it fits
and only if its quality is measured, not assumed.

## Scope

In scope, and what became of each:

- the diffusers path over the official scaled-FP8 checkpoint — **built, measured,
  removed 2026-11-17** (module, entry and assets deleted; see
  `docs/reference/flux2-klein.md`).
- `coltman_images/adapters/flux2klein_sd.py` — the `ggml` path over the Q4_K_M
  GGUF, by subprocess. **Live.**
- The registry row, the entry file and whatever selects between entries.
- The guard that keeps a foreign binary inside the tree and inside the lock.
- The measurement in `docs/reference/`.

Out of scope: image editing (multi-reference), LoRAs, the 9B variants, and any
change to Z-Image.

## Constraints

- Protocol §2: the `ggml` runtime lives inside the tree at
  `vendor/stable-diffusion.cpp`, pinned to commit `532d2c1` (2026-11-15), built
  from source with the system CUDA 13.2 at `/usr/bin/nvcc`. It is installed,
  not committed, the same way `.venv/` is.
- Protocol §9 rule 8 / guard 12: the binary must take `run/server.lock` before
  it touches the card. `flock` is the only thing standing between this and two
  models on 8188 MiB.
- Protocol §4.1: `steps` range in the entry is today 8..16. klein runs at 4.
  The range has to admit 4 with a ruling, or the entry is invalid.
- `limits.max_pixels` today is 921600; 1024² needs 1048576.
- No model name, size or step count may reach `ui.py`.

## Measured (2026-11-16, this card)

| Runtime | Artefact | 1024² / 4 steps | Peak VRAM | Encoder |
| --- | --- | --- | --- | --- |
| diffusers 0.40.0, scaled-FP8 — **removed 2026-11-17** | 4.07 GB | **6.8 s** | **6503 MiB** | Qwen3-4B bf16 on CPU, 91.6 s/prompt |
| sd.cpp, Q4_K_M, resident | 2.60 GB | **9.7 s** | **7170 MiB** | Qwen3-4B Q4_K_M, in-process |
| sd.cpp, Q4_K_M, `--offload-to-cpu` | 2.60 GB | **10.3 s** | **3916 MiB** | Qwen3-4B Q4_K_M, in-process |
| diffusers, bf16 + sequential offload — **removed 2026-11-17** | 7.75 GB | 14.7 s | 2462 MiB | same as fp8 |

FP8 against bf16 over identical weights: PSNR 38.32 dB, mean per-channel
difference 1.30/255 — indistinguishable.

1280×720 on the FP8 path: 6.1 s, peak 6208 MiB.

## Decisions taken

1. **The fp8 checkpoint was not a plain state dict.** Every matmul carried a
   `float8_e4m3fn` weight plus scalar `weight_scale` and `input_scale`; it is
   the layout `torch._scaled_mm` consumes, and diffusers 0.40.0 has no
   single-file loader for Flux2. The adapter mapped 309 BFL keys onto 169
   diffusers keys and swapped the 100 quantized linears for a per-tensor scaled
   FP8 layer. **History: that adapter was removed 2026-11-17.**
2. **`final_layer.adaLN_modulation.1` swaps halves.** BFL stores `(shift,
   scale)`, `AdaLayerNormContinuous` expects `(scale, shift)`. Same shape, so
   only a numeric check against the official state dict exposes it; reversed,
   the correlation is exactly 1.0. **History with the same adapter.**
3. **The Q4_K_M path is a subprocess, not a tensor graph.** `ggml` is not
   readable by diffusers, and writing a second loader inside Python would be a
   third implementation of the same architecture. `sd-cli` is invoked, its
   stdout is the only interface, and it never loads weights the service has
   already loaded because it takes the same lock. **Live.**
4. **`--offload-to-cpu` is the default for the Q4 path.** It costs 0.6 s and
   returns 3254 MiB. **Live.**
5. **The encoder was the real bottleneck on the FP8 path.** 91.6 s per prompt in
   CPU. The Q4 path solves it by keeping a 2.50 GB encoder quantized inside
   `sd-cli`. This asymmetry, not the transformer, is what the two runtimes
   actually traded — and on 2026-11-17 it is what decided which one went.

## Task list

- [x] F1. Entry vocabulary: admit `steps: 4` and `max_pixels: 1048576`. Ruling
      in `docs/protocol.md` §4.1 and the guard that enforces it. Guard 15 gains
      the half that proves a single-value range loads, accepts 4 and refuses 3
      and 5 by name.
- [x] F2. The diffusers adapter: the scaled-FP8 loader, the FP8 linear, the key
      map, and the `ModelAdapter` implementation. **Removed 2026-11-17 with its
      assets.**
- [x] F3. `coltman_images/adapters/flux2klein_sd.py`: the subprocess adapter,
      holding `run/server.lock` for the child's lifetime.
- [x] F4. Registry rows and the entry files, with digests. **One row and one
      entry remain** after the removal; the registry's dead row went with it.
- [x] F5. Selection between entries — **implemented provisionally**: `start
      --entry PATH` and `generate --entry PATH`, the latter a check and not a
      selector. The operator's ruling between this and a per-request field is
      still B4/D1–D3 and this does not clear it.
- [x] F6. `docs/reference/flux2-klein.md`: the measurements, the blind
      comparison and its imbalance, the quality defects of both paths, and the
      AdaLN finding as history.
- [x] F7. Docs: protocol §2 (the vendor exception), §3 layout rows, §5.1, §6.1,
      §6.3, §7, §10, §11, §12, changelog, roadmap, `context.md`, `README.md`,
      `AGENTS.md`, and `.gitignore` for `vendor/`.

## Progress, as measured through the service

The core numbers are in `docs/reference/flux2-klein.md`; these are the ones the
work unit itself observed, 1024×1024, 4 steps, seed 7, one prompt.

| | diffusers, FP8 — **removed** | `ggml`, Q4_K_M |
| --- | --- | --- |
| `render_s` | 7.054 s | 15.508 s |
| `load_s` | 77.947 s (the encoder on the CPU) | 0 by declaration |
| Peak device memory | 5262 MiB | 3822 MiB |
| Boot | 80.03 s | 11.32 s |
| Census | `100 / 69 / 0 / 169` | `{"artifacts": 3, "bytes": 5269713294}` |

Both paths were deterministic per runtime across separate processes. **The seed
does not travel between them**: the same seed gives PSNR 10.64 dB and different
compositions, so a cross-runtime comparison is judged at the same prompt and
never differenced at one seed.

**Measured whole, 2026-11-16** (250 ms sampler, from before `start` to after
`stop`): wall **167.5 s against 22.4 s**, device peak **5745 against 4305 MiB**,
whole-process-tree RSS **10280 against 6349 MiB**, removed path first. The
removal freed **11,569 MiB**.

The matrix is green — `Ran 17 tests in 661.680 s`, `OK` — and guard 8 read the
two adapter modules and the two entries as they stood then.

## The blind comparison, 2026-11-17

The five-sheet comparison ran once. The operator's judgment put three verified
defects on the removed path — the bartender's body crossing the bar counter, a
featureless black figure behind one player in the comic page, and the ice in the
glass as an irregular lump rather than a cube — and recorded one on the survivor:
an illegible scrawl beside the `OPEN` sign its prompt did not ask for.

**The comparison is unbalanced**: the shuffle put the same arm on the same side
of all five sheets, so position and quality are confounded. It is a limitation of
the record, not a clean result, and it cannot be re-run now that one arm's assets
are gone. Evidence: `tests/e2e/flux2-klein/evidence/blind/`.

## What remains

- **T3–T6, the tests of 2026-11-17 that have no recorded run**, written in
  `docs/roadmap.md`: the step count outside the regime on the `ggml` path, the
  size ladder, the lock under real contention, and the closing record. T4 no
  longer sweeps two paths.
- **The operator's ruling** between `--entry` and a per-request field (B4).
- **Promotion** is not taken: `model/entry.yaml` is still Z-Image's.
- **The static-against-dynamic activation scale** was carried but unmeasured; the
  removal closed it without answering it.

## Acceptance criteria

- `coltman-images generate --prompt …` renders from the surviving entry and
  prints the path, with the card's peak VRAM reported.
- A second process that asks for the card while either model holds it is
  refused, not OOM-killed.
- The suite stays green.
- No path outside the tree is read by the vendored binary (guard 8).

## Checks

- ``.venv/bin/python -m unittest discover -s tests -v``
- Peak VRAM sampled with `nvidia-smi --query-gpu=memory.used` at 250 ms during
  every measurement.
- Quality: same prompt and seed across both runtimes, judged blind, recorded
  in `docs/reference/` — with the imbalance of 2026-11-17 recorded beside it.
