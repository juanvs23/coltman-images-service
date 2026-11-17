# FLUX.2 [klein] 4B — two runtimes measured, one removed

Evidence, not law. `docs/protocol.md` is the law; this file records what was
measured, on which card, and with which harness, so a number can be checked
instead of believed.

**Status, 2026-11-17.** The tree holds **one** runtime for this model: the
community Q4_K_M GGUF through the vendored `sd-cli`, adapter `flux2klein_sd`. On
2026-11-17 the operator promoted it: the entry is **`model/entry.yaml`**, the
entry a service booted without `--model` serves, and it is selected with
`start --model flux2-klein-4b-gguf-q4`. Z-Image's entry moved unchanged to
`model/entries/zimage.yaml`; two entries coexist and one model is served at a
time, because the card is single. The other runtime — the official scaled-FP8
checkpoint read by diffusers, adapter `flux2klein` — was removed on 2026-11-17
together with its assets, its entry and the 467-byte transformer config copy.
This document is the measurement record of **both** paths and the evidence the
removal rests on. Everything below dated 2026-11-16 describes the tree as it
stood then; where a row belongs to the removed path it says so.

## Objective

Bring FLUX.2 [klein] 4B into the service as a second model, through two of the
three artefacts Black Forest Labs ships for it: the official scaled-FP8
safetensors, read by diffusers, and the community Q4_K_M GGUF, read by
`stable-diffusion.cpp`. Measure both, then let the operator adopt one. The
operator adopted one by removing the other on 2026-11-17.

Neither official artefact is a complete pipeline. Both are transformer-only, and
the text encoder — Qwen3-4B, `Qwen3ForCausalLM`, 2560 hidden and 36 layers, the
same shape Z-Image's encoder has — is 8.05 GB in bfloat16, so it cannot live on
the card beside anything else.

## The card, and why the encoder decides the design

The card is an RTX 4060 Laptop with 8188 MiB total and 7857 MiB usable. The
model card asks for ~13 GB.

The transformer fitted: 4.07 GB of FP8 is 3883 MiB of weights, measured 4045 MiB
of peak allocation at 256×256 and 4738 MiB at 1024×1024 with the VAE decode
included. The encoder did not fit, at 8.05 GB in bfloat16, and it was not
optional: it is the pipeline's own prompt encoder.

So the two runtimes did not differ in their transformer. They differed in where
the encoder runs:

- **diffusers path** — the encoder ran on the **CPU**, 91.6 s per prompt, and was
  dropped before the transformer took the card. The still itself was 6.8 s.
- **`ggml` path** — the encoder is a 2.50 GB Q4_K_M GGUF loaded by `sd-cli` beside
  the diffusion model. The still takes 9.7–15.5 s and the encoder costs nothing
  per prompt.

That asymmetry, not the transformer, is what the two runtimes actually traded,
and it is why the one that kept the encoder quantised survived.

## Measured (2026-11-16, this card)

| Runtime | Artefact | 1024² / 4 steps | Peak VRAM | Encoder |
| --- | --- | --- | --- | --- |
| diffusers 0.40.0, scaled-FP8 — **removed** | 4.07 GB | **6.8 s** | **6503 MiB** | Qwen3-4B bf16 on CPU, 91.6 s/prompt |
| sd.cpp, Q4_K_M, resident | 2.60 GB | **9.7 s** | **7170 MiB** | Qwen3-4B Q4_K_M, in-process |
| sd.cpp, Q4_K_M, `--offload-to-cpu` | 2.60 GB | **10.3 s** | **3916 MiB** | Qwen3-4B Q4_K_M, in-process |
| diffusers, bf16 + sequential offload — **removed** | 7.75 GB | 14.7 s | 2462 MiB | same as fp8 |

FP8 against bf16 over identical weights: PSNR 38.32 dB, mean per-channel
difference 1.30/255 — indistinguishable.

1280×720 on the FP8 path: 6.1 s, peak 6208 MiB.

The peak column is `torch.cuda.max_memory_allocated` for the diffusers rows and
device usage for the `ggml` rows; the two are not the same boundary and are not
converted into each other.

## What this tree measured, through the service

The table above is the operator's measurement of the two runtimes against each
other. It was repeated here through the project's own paths, because the service
adds boundaries the probe did not have: the adapter contract, the entry, the
census, the staging and the CLI.

**Command, both runtimes** (from the project root; peak sampled with
`tests/e2e/flux2-klein/sample_vram.py`, which polls
`nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits` every 250 ms).
The diffusers half no longer runs: its entry, its checkpoint and its encoder were
deleted on 2026-11-17. It is kept as the command that produced the row, not as a
recipe:

```sh
bin/coltman-images start --entry model/entries/flux2-klein-fp8.yaml        # entry deleted 2026-11-17
bin/coltman-images generate --prompt "a lighthouse at dusk, dramatic clouds" \
  --seed 7 --width 1024 --height 1024 \
  --out "$PWD/tests/e2e/flux2-klein/evidence/fp8-1024-seed7.png" \
  --entry model/entries/flux2-klein-fp8.yaml --json
bin/coltman-images stop
```

| Path | `render_s` | `load_s` | `duration_s` | Device peak | Boot |
| --- | --- | --- | --- | --- | --- |
| diffusers, scaled-FP8 — **removed** | **7.054 s** | **77.947 s** | 85.33 s | **5262 MiB** | 80.03 s |
| `ggml`, Q4_K_M, `--offload-to-cpu` | **15.508 s** | **0.0 s** | 15.786 s | **3822 MiB** | 11.32 s |

The boundaries, because they are not the same in the two rows and the difference
is the finding:

- **diffusers (removed)** — `load_s` is measured from the start of `encode`, as the
  contract declares, so it carries the Qwen3-4B load, the CPU encode and the
  transformer's move onto the card. `render_s` is the four-step loop plus the
  decode. The peak is `memory.used` sampled during the request, 316 samples, and
  the renderer's own `torch.cuda.max_memory_allocated` for the same request was
  4738 MiB (reserved 4910).
- **`flux2klein_sd`** — the child loads, samples, decodes and exits in one call,
  so the protocol's load boundary is not observable across it and `load_s` is
  zero by declaration, not by measurement. All of the child's wall time is
  `render_s`. The 250 ms sampler took 69 samples across the request and caught
  3822 MiB, close to the 3916 MiB the operator measured.

The boot column is the `start` cost: `prepare()` plus one discarded warm-up at
512×512. On the removed diffusers path that warm-up paid a second CPU encode,
which is why an 80 s boot was not a bug. On the `ggml` path there is nothing to
warm beyond the page cache the first child fills.

**Determinism, measured on both paths.** The same request twice, byte for byte:

| Path | Size | Seed | `sha256` | Two runs |
| --- | --- | --- | --- | --- |
| diffusers — **removed** | 256×256 | 7 | `c6c71328cb6375ae…` | identical, two separate processes |
| `flux2klein_sd` | 512×512 | 7 | `497219e8ee2748e6…` | identical, two child runs |

**The seed does not travel between runtimes.** The same prompt and seed on both
paths produced images whose PSNR against each other is **10.64 dB** — different
compositions, not different noise over one image. `torch.Generator` and
`sd-cli`'s RNG are different generators, so a cross-runtime comparison must be
made at the same *prompt*, and judged; it cannot be made by pixel difference at
one seed. That is how the comparison below was made.

## Why the diffusers path was removed — the operator's ruling of 2026-11-17

Measured whole, at the same request, through the service: 1024×1024, seed 7, one
prompt, sampling every 250 ms from before `start` until after `stop`
(`tests/e2e/flux2-klein/resource_profile.py`'s two-arm run of 2026-11-16; the
script now profiles the surviving entry only, and the two-arm result is kept as
`tests/e2e/flux2-klein/evidence/resource-profile.json`).

| Arm | Wall | `render_s` | `load_s` | Device peak | Δ over idle | Whole tree RSS | Δ system RAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| diffusers, scaled-FP8 — **removed** | 167.5 s | 7.1 | 76.3 | **5745 MiB** | 5438 | **10280 MiB** | 1968 |
| `ggml`, Q4_K_M | 22.4 s | 11.1 | 0.0 | **4305 MiB** | 3609 | **6349 MiB** | 5786 |

The four numbers the removal rests on, removed path first: wall **167.5 s against
22.4 s**, device peak **5745 against 4305 MiB**, whole-process-tree RSS **10280
against 6349 MiB**. Two boundaries, stated because they change the reading of the
numbers. Device memory is what the driver reports for the whole card, so the
baseline includes the operator's desktop (~700 MiB); the **Δ** column is the
arm's own share and is the one to compare. Host memory is the **whole process
tree**, not the server alone — the `ggml` path renders in an `sd-cli` child and a
server-only reading would charge it for nothing, which is precisely the comparison
this measurement exists to make.

**The peak on the diffusers path was the encoder, not the renderer.** 5438 MiB
over idle is the 4.84 GiB int8-shaped bf16 encoder, and it was taken before the
transformer loaded; the 10.3 GB of tree RSS is the same encoder resident while its
pages are touched, which is the 8.05 GB the section above explains cannot fit on
the card. The `ggml` path never rises above 4305 MiB because its encode and its
sampling share one quantised pair of artefacts.

**What went, in bytes.** `model/assets/flux2-klein/fp8/` (the 4.07 GB scaled-FP8
transformer), `official/text_encoder/` (the 8.05 GB bfloat16 Qwen3-4B, two
shards), `official/{tokenizer,scheduler,transformer}/`, `official/model_index.json`,
`model/flux2_klein.json`, and the adapter, entry and two test scripts named in the
changelog. Kept: `official/vae/` and `official/LICENSE.md`, because the surviving
entry names the VAE, and all of `gguf/`. Total freed: **11,569 MiB**.

## The blind comparison of 2026-11-17 — what it found, and why it is unbalanced

The protocol this document had written was run once, on 2026-11-17, by
`tests/e2e/flux2-klein/blind_ab.py` — since deleted, because it needs both
entries. Five prompts (a poker scene in a bar, a comic page of the same scene, an
`OPEN` shop sign, a cut-crystal glass, a Mediterranean alley), the same prompt on
both runtimes, 1024×1024, 4 steps, seed 7, five side-by-side sheets with no
runtime name on them. The ten stills, the five sheets, `key.json` and
`timings.json` are in `tests/e2e/flux2-klein/evidence/blind/`.

**The test is unbalanced and no document may quote it as a clean result.**
`key.json` shows the same arm on the same side in all five sheets — `left: gguf`,
`right: fp8`, every time — so the sheet's layout was confounded with the arm and
a reader's left/right preference cannot be separated from a quality difference.
The operator judged the sheets anyway and the removal followed; the honest record
is "the operator judged, with a confounded layout", not "one runtime won".

**The judgment, and the three defects it verified in the crops (the removed
path's):**

1. **The bartender's body crosses the bar counter.** The apron and hips are drawn
   in front of the counter while the torso is behind it — one figure, two depth
   planes, and the counter does not pass between them. **This defect is not the
   removed path's.** Measured on 2026-11-17 on the surviving runtime, four steps
   reproduce it verbatim and six and eight steps render the occlusion correctly
   (`tests/e2e/flux2-klein/evidence/staircase/bartender-crop.png`); every still in
   this comparison was rendered at four. The same caveat applies to the other two
   defects below: they are all four-step artefacts, and none of them is evidence
   about quantisation.
2. **A featureless black figure stands behind one player** in the comic page: a
   silhouette with no face, no clothing and no shading, where every other figure
   in the frame is built out of ink and halftone.
3. **The ice in the glass is an irregular lump, not a cube.** The prompt asks for
   one large clear ice cube; what is there is a melted, asymmetric mass.

**The survivor is not flawless, and the record says so.** On the same set the
`ggml` runtime wrote an **illegible scrawl beside the `OPEN` sign** — marks the
prompt did not ask for, next to the lettering it did. It is the one defect
recorded against the surviving path, it was verified in the crops, and it is the
reason this document does not present the survivor as clean.

## The step count, the size ladder and two knobs the entry cannot reach — 2026-11-17

After the removal, the surviving runtime was asked the questions its entry had only
declared an answer to. Two measurement runs, both on the `ggml` path and both at
seed 7: `tests/e2e/flux2-klein/staircase.py` (the poker prompt; T3 and T4) and
`tests/e2e/flux2-klein/sampler_sweep.py` (the poker scene and a cut-crystal
glass). Both call the vendored binary directly, because none of the values was
reachable through the entry as it stood on that date: it refused a step count
outside `{min: 4, max: 4}`, refused an area above 1,048,576 px, and declares no
`--sampling-method` and no `--flow-shift`. The first two were ruled the same day
(4..8 steps, a 1327104 px ceiling); the sampler and the flow shift remain
unreachable. The lock work below is the third run and it goes through the service.

Two boundaries are shared by every table below and none of them is converted
into another. **The child's own wall time**, not the service's `render_s`: the
adapter re-encodes the child's PNG through PIL, so a still written by the service
and a still written by `sd-cli` are not byte-comparable, and these numbers are
the child's. **Device memory is whole-card `memory.used`** from the 250 ms
sampler, so it includes the operator's desktop — 255 MiB of baseline in this run
— and the "Δ" column is the run's own share. On top of those, T3 and T4 rest on
**one prompt and one seed**, and the sweep on two prompts at one seed: each
section says what its own reading is worth.

### T3 — the step count, measured instead of asserted

1024×1024, four, six and eight steps, `--offload-to-cpu`, same prompt and seed:

| Steps | Wall | Δ over four steps | Device peak | Δ over baseline |
| --- | --- | --- | --- | --- |
| 4 | 10.8 s | — | 3865 MiB | 3610 |
| 6 | 14.1 s | +3.3 s (+31 %) | 3865 MiB | 3610 |
| 8 | 16.9 s | +6.1 s (+56 %) | 3865 MiB | 3610 |

The step count does not touch the peak: all three sit at 3865 MiB, because the
card holds one quantised pair whether it samples four times or eight. What it
buys is not more detail in the sense the law's sentence assumed. **At four steps
the bartender's body is merged into the bar counter** — apron and hips on the
near face of the furniture, torso behind it — and **at six and eight the
occlusion is correct**, with the most apron detail at eight. The operator
confirmed the reading on
`tests/e2e/flux2-klein/evidence/staircase/bartender-crop.png`. The defect is a
four-step artefact and not a property of the quantisation: the removed diffusers
path's stills were also rendered at four steps and carry the same merged figure,
which is why the defect appears in the blind comparison above and belongs to
neither runtime.

The marginal cost of a step is **1.65 s between four and six and 1.4 s between
six and eight**, against 2.7 s per step if the four-step wall were all sampling;
the difference is the child's load and encode, between 4.2 and 5.2 s of the
10.8 s, which the step count never moves. So four more steps cost 56 % of the
four-step wall and not 100 %.

What this does **not** decide — and this section took no ruling — was whether
the entry's `limits.steps` should move from `{min: 4, max: 4}` to admit 8. The
measurement said the wider range repaired a real defect at a measured price. **The
operator ruled on 2026-11-17 that it does: klein's entry declares `{min: 4, max:
8}`, defaults to 8 steps, and protocol section 4.1's sentence about sampling
outside a distilled model's regime was amended in the same work unit, marked as an
expectation this model failed to meet.** The range is bounded by what was
rendered: 8 is the largest count measured, and nothing above 8 is claimed.

### T4 — the size ladder and where it stops

Four steps, one prompt, one seed. The entry's ceiling was `max_pixels: 1048576` at
the time of the run, which is 1024²; 1152² sat deliberately **above** it, because a
ceiling is only a measurement if something outside it is tried:

| Shape | Pixels | Wall | Device peak | Δ over baseline | Against the declared ceiling |
| --- | --- | --- | --- | --- | --- |
| 512×512 | 262,144 | 5.3 s | 3221 MiB | 2966 | 25 % of it |
| 768×768 | 589,824 | 7.5 s | 3461 MiB | 3206 | 56 % |
| 1024×1024 | 1,048,576 | 11.1 s | 3865 MiB | 3610 | at it |
| 1152×1152 | 1,327,104 | 13.4 s | 4701 MiB | 4446 | **127 %** |
| 1280×720 | 921,600 | 10.3 s | 3761 MiB | 3506 | 88 % |

**1152² fits.** It ran at 4701 MiB, leaving **3156 MiB** of the card's 7857
usable, and cost 13.4 s against 11.1 s — 21 % more wall for 27 % more pixels.
The declared ceiling is therefore conservative for this card on this path, and
the operator read the ladder's contact sheet as the best distribution of figures
at the table at 1152². That last sentence is an **indication and not proof**: one
prompt, one seed, one scene with figures at a table. The same request appears in
both tables — 1024² at four steps — as **10.8 s** in T3 and **11.1 s** here; the
0.3 s is run-to-run variance on one card, not a second measurement of a different
thing.

Whether `max_pixels` should be raised now that 1,327,104 px is measured to fit was
**not decided then**. The measurement was recorded; the ceiling was the entry's
declaration and moving it was an operator ruling. **The operator ruled on
2026-11-17: the ceiling is `1327104`, and the promoted entry's defaults are that
box — 1152×1152 — because the operator asked for the best measured box by
default.** Two facts bound it, and the entry's own comment repeats them: the
1152² reading rests on **one prompt and one seed**, so it is an indication and not
a distribution; and it is square, while the same area is a 1536×864 box with both
sides on the 16-px grid, so raising the ceiling also admits shapes this ladder did
not render.

**The default pair was then measured on its own**, because two measured values are
not a measured pair: `1152×1152` at **eight** steps through the service is
**28.693 s** with the device peaking at **4815 MiB** — about two and a half times
the old `1024×1024` at four steps, and 114 MiB above the same box at four. That
last figure is worth keeping: at 1024² the step count left the peak flat (T3
measured 3865 MiB at four, six and eight), and at 1152² it does not. The peak is
flat in steps only while the box is not near the ceiling. No shape was sampled
above 1024² at a wide aspect.

### The sampler and the flow shift — two knobs the entry cannot reach

1024², four steps, seed 7, two prompts (the poker scene and a cut-crystal glass),
each method differenced against the default `euler` on the same prompt. The
distance is mean absolute difference in 8-bit RGB and the share of pixels whose
largest channel difference exceeds 16:

| Method | Poker MAD / >16 | Glass MAD / >16 | Reading |
| --- | --- | --- | --- |
| `euler` (default) | — | — | the baseline |
| `dpm++2m` | 19.41 / 44.1 % | 24.94 / 66.1 % | a different image, same order of quality |
| `res_multistep` | 19.70 / 44.8 % | 25.52 / 67.0 % | the same, slightly further |
| `ipndm` | 33.75 / 65.9 % | 29.68 / 66.3 % | **visibly the worst** — distorted faces, a ghost double rim on the glass |
| `heun` | 13.49 / 28.2 % | 13.50 / 33.0 % | the closest to the default |

`heun` is the closest and also the most expensive where the timing was taken
fresh: 16.0 s on the glass prompt against 11.2 s for `euler`, `dpm++2m`,
`res_multistep` and `ipndm` (11.1–11.2 s) — a two-evaluation method paying for
its second evaluation. The others sit within a tenth of a second of each other.
None of the four usable methods fixes the headcount: **all of them still put four
players at a table the prompt asked to seat six**, which is the defect the stress
prompt found and no sampler setting repairs.

**The flow shift is inert.** `--flow-shift` 1.0 and 6.0 produced **byte-identical
files** to the default on both prompts, and 3.0 differed on one of the two only
(poker, MAD 4.90, 6.0 % of pixels; the glass still identical to the byte). The
FLUX.2 scheduler computes its own `mu`-based shift and the flag does not move it,
so on this model the knob is a no-op with a measured signature rather than a
tuning surface. `sampler_sweep.py` renders each variant once; the poker rows for
`euler`, the four methods and two of the shifts are reused from an earlier run
(the script caches by file name and reports `cached: true`), which is why their
wall time in `sweep.json` is 0.0 s, and the glass prompt's fresh timings are the
ones quoted above.

## T5 — the lock and the queue under contention, 2026-11-17

`run/server.lock` had been proven in one direction only: an adapter refuses when
a running server owns the card. The other three directions were run through
`bin/coltman-images` as an operator uses it
(`tests/e2e/flux2-klein/contention.py`, evidence
`tests/e2e/flux2-klein/evidence/contention/contention.json`). Each scenario was
run once, so each number is one observation.

**Two `generate` calls at once.** Both answered `200`; `duration_s` was **11.48 s**
and **23.148 s** — a ratio of **2.016**, which is one render waiting behind
another with no overlap. `pgrep -c sd-cli`, sampled every 100 ms for the whole
25.1 s window (188 samples), **never exceeded 1**; device peak 3889 MiB. The
queue serialised them and one worker kept one child on the card.

**`stop` arriving mid-render.** The child was on the card when `stop` was sent.
`stop` answered `coltman-images: stopped` and exited 0 after **11.4 s**, the
in-flight request answered `200` with `duration_s` 11.168 and its still was
written — the render **completed** rather than being cut. Afterwards: no
`sd-cli` process, no `run/server.json`, no held lock, port silent. What this does
**not** prove is the 30 s deadline, because this entry cannot ask for a request
that outlasts it: the largest admissible box was 1024² (1,048,576 px) at the only
admissible step count, four, and the ladder measured that box at 11.1 s — its
slowest render among the boxes the entry admitted then (1280×720 is 10.3 s). The
drain path is proven; the release-anyway path is not reachable through this
entry, and the 2026-11-17 ruling — 4..8 steps, a 1327104 px ceiling — did not
re-measure the deadline.

**A fresh server against a bare `sd-cli`.** A hand-launched `sd-cli` was loading
the card at 1024²; `run/server.lock` was **free**, because the binary knows
nothing about it. `start --model flux2-klein-4b-gguf-q4` **exited 0** (the
`--model` flag did not exist on 2026-11-17; the run used
`--entry model/entries/flux2-klein-gguf.yaml`, since promoted) and was warm in
13.1 s, and **two `sd-cli` processes coexisted** (maximum
observed 2) with the device at **6854 MiB** of 8188. Both succeeded: the bare
child wrote its still and the server completed its warm-up.

**The finding: nothing prevents it.** The lock is a contract between this
project's processes, not a property of the card. Any `sd-cli` launched outside
the service — by hand, by a script, by another tool — holds the card without
holding the lock, and the server will boot beside it. What kept both alive here
is `--offload-to-cpu`, which holds each child near 3.2–3.9 GiB; the arithmetic
from the measured rows says a **resident** child (7170 MiB, measured on
2026-11-16) beside the server's own 512² warm-up (3221 MiB) would need
**10,391 MiB** on a 7857 MiB card. The mutex makes the crash impossible only for
the processes that ask for it, and `sd-cli` is not one of them.

## The same request, three times

The service's own determinism, re-measured on 2026-11-17 while the lock was under
test. The poker prompt, 1024×1024, seed 7, four steps, three stills produced by
three separate requests through the service — two on one server, the third on
the next — were `sha256 f15222b23879973d…` on all three, byte for byte. The
lighthouse request of 2026-11-16 reproduced on 2026-11-17 as the same
`482d2843418d5d6a…`, across a server started on another day. A still the child
wrote directly is a different digest from the service's still for the same
request (`f5e8377099e3c93c…` for `steps-4.png`), because the adapter re-encodes
the child's PNG; that is the re-encode boundary stated above, not nondeterminism.
The hand-launched child of T5 returned that same `f5e8377099e3c93c…` for the same
request as `steps-4.png`, so the child is deterministic too, and the distance
between the two digests is the service's re-encode and nothing else.

## The AdaLN finding — history of the removed adapter

`final_layer.adaLN_modulation.1` stores `(shift, scale)`; diffusers'
`AdaLayerNormContinuous` expects `(scale, shift)`. The shape is identical, so a
shape check — and a strict state-dict load — passes either way. Reversing the two
halves and correlating them against the official diffusers state dict gives
exactly **1.0**: the two halves are the same values in the other order, and a
map that does not swap them loads cleanly and renders a plausible, wrong image.

This is why the key map was validated numerically and not by shapes: seventeen
tensors from the official state dict were fetched by byte range and compared
against the mapped checkpoint, including the fused `qkv` rows, the QK-normalisation
scales and the two modulations. A shape check cannot see a permuted half.

## The map, in numbers — history of the removed adapter

- 309 tensors in the FP8 checkpoint: 80 quantised weights, their two scalar
  scales each (240 tensors in all), and 69 plain weights.
- 169 parameters in `Flux2Transformer2DModel`, of which 100 were replaced by the
  adapter's `FP8Linear`: twelve per double-stream block across five, two per
  single-stream block across twenty. The 80 fused BFL weights became 100 diffusers
  linears because each fused `qkv` splits into three.
- Census through the adapter: **100 float8 / 69 plain / 0 other / 169 total**,
  scales excluded, which is the same rule the `zimage` loader counts by.
- The fused `qkv` linears split by row into equal thirds of the hidden size, and
  the hidden size is read from the config (`24 × 128 = 3072`), never written as a
  constant.

## The load is the FP8 layer, and the activation scale is dynamic — history

Every quantised projection kept its `float8_e4m3fn` weight exactly as stored, and
`torch._scaled_mm` consumed it with a per-tensor weight scale. The activation side
was quantised at every call from the activation the forward was handed, floored at
`1e-8` so an all-zero activation cannot divide by zero.

The checkpoint also carried a static `input_scale` per projection. The adapter
loaded it — it was part of the layer's layout — and the forward never read it.
**Which of the two is more accurate was never measured**: the dynamic path is the
one every number above was produced with, and the removal closed the question
without answering it (protocol section 12).

## Provenance

The files, their sizes and their digests, verified in this tree on 2026-11-16.
Only the ones a declared component names are pinned in an entry; the rest are
recorded here so a later reader can verify what was measured (protocol section
6.1 lets an entry's `digests` name a component, and a checkpoint is not one).
Rows marked **deleted 2026-11-17** no longer exist on this machine; the digests
are kept as the record of the bytes that were measured.

| Artefact | Size | `sha256` |
| --- | --- | --- |
| `model/assets/flux2-klein/fp8/flux-2-klein-4b-fp8.safetensors` — **deleted 2026-11-17** | 4,070,624,520 | `97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6` |
| `model/assets/flux2-klein/gguf/flux-2-klein-4b-Q4_K_M.gguf` | 2,604,311,104 | `0b25d143c8469b342bc5af3bce92b783bf6b0636d285f7b2f75e38af63af9a15` |
| `model/assets/flux2-klein/gguf/Qwen3-4B-Q4_K_M.gguf` | 2,497,281,312 | `f6f851777709861056efcdad3af01da38b31223a3ba26e61a4f8bf3a2195813a` |
| `model/assets/flux2-klein/official/vae/diffusion_pytorch_model.safetensors` | 168,120,878 | `ca70d2202afe6415bdbcb8793ba8cd99fd159cfe6192381504d6c4d3036e0f04` |
| `model/flux2_klein.json` (pinned in the removed entry) — **deleted 2026-11-17** | 467 | `34ad7273b27bf5be235efc070ae0d08536dc99e439a7d519399527cb618b6d45` |
| `vendor/stable-diffusion.cpp/build/bin/sd-cli` (pinned in the surviving entry) | 126,873,080 | `a5f17d22af14d5f13715b6a7f6248f18eb42da2a1e479c684f2658c22f2fe295` |

Hashing costs, measured with the project's interpreter: 7.35 s for the FP8
checkpoint, 1.72 s and 2.36 s for the two GGUFs, 0.24 s for the VAE. That is why
the 4.07 GB and 2.60 GB files are recorded here and not pinned in the entry: a
pin is paid on every resolution of the entry, and the law lets a digest name only
a component.

`model/flux2_klein.json` was a copy of the exporter's transformer config with
`_name_or_path` removed — a build path on a machine this project does not read.
The copy under `model/assets/` carried the same bytes, so the two could not drift.
Both are gone; the digest is the record.

## What each path costs while it renders

`blind_ab.py` recorded time and nothing else, so the other two currencies were
measured separately, on the same prompt at 1024×1024 with seed 7, sampling every
250 ms from before `start` until after `stop`
(`tests/e2e/flux2-klein/resource_profile.py`, `evidence/resource-profile.json`).
The table is repeated here rather than only in the removal section because it is
the measurement, not a summary of one:

| Arm | Wall | `render_s` | `load_s` | Device peak | Δ over idle | Whole tree RSS | Δ system RAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| diffusers, scaled-FP8 — **removed** | 167.5 s | 7.1 | 76.3 | **5745 MiB** | 5438 | **10280 MiB** | 1968 |
| `ggml`, Q4_K_M | 22.4 s | 11.1 | 0.0 | **4305 MiB** | 3609 | **6349 MiB** | 5786 |

## What is not measured

- **A clean blind result.** The comparison of 2026-11-17 ran once and its layout
  is confounded: the same arm sat on the same side of all five sheets. A balanced
  re-run is impossible now — one arm's assets are gone — so the quality judgment
  stands as the operator's, with that limitation recorded rather than removed.
- **Static against dynamic activation scaling.** Only the dynamic path was
  measured, and the adapter that could have compared them no longer exists.
- **1280×720 through this service.** The ladder above measured the shape through
  the binary — 10.3 s, 3761 MiB — but no request has been served at 1280×720
  through the queue, so the service row for that shape does not exist.
- **A step count, a size or a sampler read on more than one prompt and seed.**
  T3's defect and T4's 1152² reading each rest on one prompt and one seed; the
  sampler distances rest on two prompts at one seed. They are indications with a
  stated boundary, not distributions.
- **`stop`'s 30 s deadline.** The drain path was proven; no request this entry
  admits outlasts the grace, so the release-anyway path was never entered.
- **A guard against an `sd-cli` launched outside the service.** The lock is
  cooperative and the bare-child scenario of T5 boots beside it; whether that
  should change is open.
- **The `ggml` path's internal boundary.** `load_s` is zero by declaration: the
  child's load and sampling are one call, and nothing in its stdout separates
  them reliably enough to report.
- **Multi-reference editing.** Out of scope for this unit. Both artefacts carried
  the capability; nothing here exercised it, and the artefact that could have is
  gone.

## The encoder: two copies of one model, and the ruling the removal overtook

This section is history twice over: the comparison's bfloat16 arm was deleted on
2026-11-17, and the ruling it produced no longer governs anything. It is kept
because the finding is real and because `encoder-parity.json` is the record of it.

The removed diffusers path's 78 s of `load_s` was the Qwen3-4B encoder on the
CPU, and the first question of the next session was whether it had to be. It did
not, and the system kept it anyway — for a day.

**They are the same model.** `merges.txt`, `vocab.json` and `tokenizer.json` are
byte-identical between `model/assets/qwen3/` (Z-Image's quantised copy, 4.41 GB)
and the FLUX.2 tree's bfloat16 copy (8.05 GB, two shards). `embed_tokens` and
`model.norm` agree bit for bit. Every one of the thirty-six layers correlates at
**1.0000** against the bfloat16 reference; the 0.0039 maximum difference on the
quantised tensors is int8's own error. Evidence:
`tests/e2e/flux2-klein/encoder-parity.json`. The script that produced it,
`encoder_parity.py`, was deleted on 2026-11-17 with the arm it compared against.

**One difference hides in the last layer.** `layers.35.mlp.up_proj` holds a zero
scale on 5770 of its 9728 rows and `layers.35.mlp.down_proj` on 404 of 2560 —
59.3 % and 15.8 % of two projections, the only two affected of 252 quantised
tensors, both in layer 35. The non-zero rows match the bfloat16 weights to the
last digit, so this is the same matrix with a structured pruning the export
carries, not another model. It did not reach FLUX.2: `Flux2KleinPipeline`
conditioned on the hidden states of layers **9, 18 and 27**, all three of which
correlate at 1.0000. It does reach Z-Image, which conditions on the final state.

**Reuse is 38× faster and was not adopted.** Encoding the same prompt with the
int8 copy on the card takes **2.5 s** against **95.8 s** on the CPU, at a cosine
of 0.99998 per layer — but the deviation is 0.11 to 0.16 absolute on reference
magnitudes of 1.1 to 2.3, five to ten per cent relative, accumulated over 27
layers of float32 activations against bfloat16. Whether that reaches a still has
not been judged, and an unjudged swap was not worth a coupling between two
entries.

**The RAM does not fall, and that is measured rather than argued.** The loader
materialises the model on the host before moving it: 5.05 GB peak resident as
written, 5.29 GB with a lazy state dict that never builds the dictionary, and an
out-of-memory failure when the empty shell is placed on the card first. The
encoder is 4.41 GB and it has to live somewhere — host memory or device memory.
What the bfloat16 copy cost instead was 8.05 GB of page cache, which is
reclaimable; what the int8 copy costs is the same 4.84 GiB of device memory
Z-Image already pays on every request.

**The ruling of 2026-11-17, and what superseded it.** The operator ruled that the
official bfloat16 encoder was what this system encoded with. On the same date the
removal of the path overtook the ruling: the same operator deleted that encoder
with the runtime it belonged to, so the ruling is moot rather than wrong — it
governed an encoder that no longer exists.
The comparison's other arm is gone, so the question it left open ("does the int8
swap reach a still") cannot be reopened without bringing the bfloat16 copy back,
which is a new download and a new measurement, not a re-reading of this file.
