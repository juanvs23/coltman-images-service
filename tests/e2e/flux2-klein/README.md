# FLUX.2 [klein] — two runtimes measured, one removed

The operator-level run for the second model: both entries that existed on
2026-11-16, both runtimes, the same request, on the real card, through
`bin/coltman-images` as an operator uses it. The numbers below are what the
installed system did, and `docs/reference/flux2-klein.md` carries them with their
boundaries.

**The diffusers runtime was removed on 2026-11-17.** Its adapter, its entry, its
checkpoint and its 8.05 GB encoder are gone, so the diffusers commands below can
no longer run. They are kept as the record of the commands that produced the
numbers, not as a recipe. What still runs is the `ggml` entry, promoted on
2026-11-17 to `model/entry.yaml` and served with `start --model
flux2-klein-4b-gguf-q4`.

- **Date:** 2026-11-16 for the cost run; 2026-11-17 for the blind comparison
- **Card:** RTX 4060 Laptop, 8188 MiB
- **Interpreter:** `.venv/bin/python` (Python 3.14.8, torch 2.13.0+cu130, diffusers 0.40.0)
- **Request:** `a lighthouse at dusk, dramatic clouds`, seed 7, 1024×1024, 4 steps
- **Verdict:** both entries rendered and both were deterministic per runtime. The
  diffusers runtime was removed on 2026-11-17, and the `ggml` runtime was promoted
  to `model/entry.yaml` the same day.

## What it proves

1. `start --entry` (the mechanism at the time) served the diffusers entry (since
   deleted) and answered
   `/health` warm with the entry's census — `{"float8": 100, "plain": 69,
   "other": 0, "total": 169}` — before the port bound.
2. `generate` through the CLI wrote a 1024×1024 still for that entry, printed its
   path, and reported `render_s`, `load_s` and the census.
3. The same for the `ggml` entry, now `model/entry.yaml`, whose census is the
   three artefacts it hands the child and their bytes.
4. A second process that asked for the card while a model held it was refused,
   not OOM-killed: the subprocess adapter refused with the holder's pid and
   started no child.
5. Both paths were byte-deterministic per runtime.
6. The seed does not transfer across runtimes, which is a fact the A/B protocol
   had to live with — and did, at the same prompt, in the run of 2026-11-17.

## Commands, and what they answered

Every command ran from the project root. Peak memory was sampled throughout by
`sample_vram.py`, which polls `nvidia-smi --query-gpu=memory.used
--format=csv,noheader,nounits` every 250 ms and writes `evidence/*-vram.csv`.

**The diffusers path — removed 2026-11-17; this command no longer runs:**

```sh
.venv/bin/python tests/e2e/flux2-klein/sample_vram.py \
  --csv tests/e2e/flux2-klein/evidence/fp8-vram.csv &
bin/coltman-images start --entry <the diffusers entry>                 # deleted 2026-11-17
bin/coltman-images generate --prompt "a lighthouse at dusk, dramatic clouds" \
  --seed 7 --width 1024 --height 1024 \
  --out "$PWD/tests/e2e/flux2-klein/evidence/fp8-1024-seed7.png" \
  --entry <the diffusers entry> --json                                 # deleted 2026-11-17
bin/coltman-images stop
```

- `start` answered in 81.2 s wall; the server logged `boot: warm in 80.03 s`, of
  which the discarded 512×512 warm-up was `render_s 2.42` and `load_s 74.63`.
- `generate` answered `200` with `duration_s 85.33`, `render_s 7.054`,
  `load_s 77.947`, census `100 / 69 / 0 / 169`, and an empty stderr.
- The sampler took 646 samples over the whole window and 316 inside the request;
  the peak was **5262 MiB**, and `torch.cuda.max_memory_allocated` for the same
  request was 4738 MiB (4910 reserved).
- The still is `evidence/fp8-1024-seed7.png`, `sha256 353a016cad21f2cc…`.

**The `ggml` path:**

```sh
.venv/bin/python tests/e2e/flux2-klein/sample_vram.py \
  --csv tests/e2e/flux2-klein/evidence/gguf-vram.csv &
bin/coltman-images start --model flux2-klein-4b-gguf-q4
bin/coltman-images generate --prompt "a lighthouse at dusk, dramatic clouds" \
  --seed 7 --width 1024 --height 1024 \
  --out "$PWD/tests/e2e/flux2-klein/evidence/gguf-1024-seed7.png" \
  --model flux2-klein-4b-gguf-q4 --json
bin/coltman-images stop
# 2026-11-16 ran this block with `--entry model/entries/flux2-klein-gguf.yaml`;
# `--model` is the mechanism since 2026-11-17.
```

- `start` answered in 12.6 s wall; `boot: warm in 11.32 s`, the warm-up costing
  `render_s 9.26`.
- `generate` answered `200` with `duration_s 15.786`, `render_s 15.508`,
  `load_s 0.0` — declared, not measured: the child's load and sampling are one
  call — census `{"artifacts": 3, "bytes": 5269713294}`.
- The sampler took 144 samples, 69 inside the request; the peak was **3822 MiB**.
- The still is `evidence/gguf-1024-seed7.png`, `sha256 482d2843418d5d6a…`.

**The refusal, while the card was held:**

```sh
# with the gguf server running (pid 728445, holding run/server.lock)
.venv/bin/python -c '… render the gguf entry from another process …'
# → Flux2KleinSdError: card: …/run/server.lock is held by pid 728445 — sd-cli must
#   not load a model while another instance owns this card; stop it with
#   `coltman-images stop` and retry
bin/coltman-images start --model z-image-turbo-fp8
# → --model z-image-turbo-fp8 ignored: the running server keeps the entry it was
#   started with and is serving flux2-klein-4b-gguf-q4; stop it first to change it
# → already running — pid 728445, port 8420, state warm   (exit 0)
```

No `sd-cli` process existed after the refusal, and no still was written.

**Determinism, the same request twice:**

```sh
# diffusers path (removed), 256×256, seed 7, two separate processes
c6c71328cb6375ae604be179e2db5c851ea97dfae0409c5bdef20cdff76776cf
c6c71328cb6375ae604be179e2db5c851ea97dfae0409c5bdef20cdff76776cf
# ggml path, 512×512, seed 7, two child runs
497219e8ee2748e6477ee7bfdb08885df565c6f249efba29aa9ad476c03353f1
497219e8ee2748e6477ee7bfdb08885df565c6f249efba29aa9ad476c03353f1
```

**The same seed across runtimes:** PSNR 10.64 dB, mean absolute difference 53.96
of 255 — two different compositions, not two versions of one image. The two
runtimes used different generators, so the A/B compared at the same prompt and
was judged, never differenced.

**The two-arm resource profile, 2026-11-16:** `evidence/resource-profile.json`
holds the run that measured both runtimes whole — wall 167.5 s against 22.4 s,
device peak 5745 against 4305 MiB, tree RSS 10280 against 6349 MiB. It is the
evidence for the removal and it cannot be produced again. `resource_profile.py`
now profiles the surviving entry only and writes
`evidence/resource-profile-gguf.json`, so a run today leaves that record alone.

## The blind comparison, 2026-11-17 — ran once, not reproducible

`blind_ab.py` (since deleted) rendered five prompts through both entries at
1024×1024, seed 7, and produced ten stills, five side-by-side sheets and
`key.json` under `evidence/blind/`. The operator read the sheets and judged; the
diffusers runtime was removed the same day.

**The comparison is unbalanced and is recorded as a limitation.** `key.json` puts
the same arm on the same side in all five sheets (`left: gguf`, `right: fp8`
throughout), so position and quality are confounded. It is not a clean result and
no document may quote it as one.

**The blind run cannot be reproduced.** One arm's checkpoint, encoder and entry
were deleted on 2026-11-17, so there is nothing to render the other half of a
sheet from. The stills and the key are kept as the record of what was looked at.

The three defects the operator verified in the crops belong to the **removed**
path: the bartender's body crossing the bar counter (apron and hips in front,
torso behind), a featureless black figure behind one player in the comic page, and
the ice in the glass as an irregular lump rather than a cube. The **survivor** has
one defect and the record says so: it wrote an illegible scrawl beside the `OPEN`
sign, lettering the prompt did not ask for.

## The encoder comparison — other arm no longer exists

`encoder_parity.py` (deleted 2026-11-17) compared Z-Image's int8 Qwen3-4B copy
with FLUX.2's bfloat16 copy and produced `encoder-parity.json`, which is kept.
The bfloat16 copy was deleted with the diffusers runtime, so the comparison
cannot be re-run: its other arm no longer exists on this machine. The finding —
same model, tokenizers byte-identical, all thirty-six layers at a correlation of
1.0000, a pruned last layer FLUX.2 never read — survives in the JSON and in
`docs/reference/flux2-klein.md`.

## The step count and the size ladder, 2026-11-17 (T3, T4)

`staircase.py` bypasses the service on purpose — at the time the entry refused anything but four steps and anything
above 1,048,576 px — and calls the vendored binary exactly as the adapter would. Device memory is the 250 ms sampler's
whole-card `memory.used`, baseline 255 MiB. One prompt (the poker scene), seed 7.

| Steps at 1024² | Wall | Device peak | | Shape at 4 steps | Pixels | Wall | Device peak |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 10.8 s | 3865 MiB | | 512×512 | 262,144 | 5.3 s | 3221 MiB |
| 6 | 14.1 s | 3865 MiB | | 768×768 | 589,824 | 7.5 s | 3461 MiB |
| 8 | 16.9 s | 3865 MiB | | 1024×1024 | 1,048,576 | 11.1 s | 3865 MiB |
| | | | | **1152×1152** | **1,327,104** | **13.4 s** | **4701 MiB** |
| | | | | 1280×720 | 921,600 | 10.3 s | 3761 MiB |

**The step count repairs a real defect and never moves the peak.** At four steps the bartender's body is merged into the
bar counter; at six and eight the occlusion is correct, with the most apron detail at eight
(`evidence/staircase/bartender-crop.png`, the operator's reading). The same defect appears in the removed runtime's
stills, which were also rendered at four steps, so it is not evidence about quantisation.

**The ceiling was conservative, and the operator raised it.** 1152² is 27 % above the entry's declared `max_pixels`
and ran with 3156 MiB of the 7857 usable still free. On 2026-11-17 the operator ruled: `max_pixels` is `1327104`, the
defaults are 1152×1152, and `limits.steps` is 4..8 with a default of 8. Both readings rest on one prompt and one seed.

## The sampler and the flow shift, 2026-11-17

`sampler_sweep.py` (two prompts, 1024², seed 7, four steps) measured two knobs the entry cannot reach. Distance from
`euler`, mean absolute difference / share of pixels differing by more than 16:

| Method | Poker | Glass | Reading |
| --- | --- | --- | --- |
| `dpm++2m` | 19.41 / 44.1 % | 24.94 / 66.1 % | a different image, same order |
| `res_multistep` | 19.70 / 44.8 % | 25.52 / 67.0 % | the same, slightly further |
| `ipndm` | 33.75 / 65.9 % | 29.68 / 66.3 % | **the worst** — distorted faces, a ghost double rim on the glass |
| `heun` | 13.49 / 28.2 % | 13.50 / 33.0 % | the closest to the default, and 16.0 s against 11.2 s on the glass |

**The flow shift is inert.** 1.0 and 6.0 are byte-identical to the default on both prompts; 3.0 differs on one prompt
only (poker, 4.90). The FLUX.2 scheduler computes its own `mu`-based shift and does not read the flag. **No sampler
fixes the headcount:** all four usable methods still seat four players at a table the prompt asked to seat six.

## The lock under contention, 2026-11-17 (T5)

`contention.py` runs three scenarios through `bin/coltman-images` and writes `evidence/contention/contention.json`. One
run each.

1. **Two `generate` calls at once.** Both `200`; `duration_s` **11.48 s** and **23.148 s**, ratio **2.016**. `pgrep -c
   sd-cli`, sampled 188 times over the 25.1 s window, **never exceeded 1**. The single worker serialised them.
2. **`stop` mid-render.** The child was on the card when `stop` was sent; `stop` exited 0 after **11.4 s**, the request
   answered `200` with its still (`duration_s` 11.168) and afterwards there was **no `sd-cli` process, no
   `run/server.json` and no held lock**. The render completed; it was not cut. The 30 s deadline was not reached —
   no request this entry admits outlasts it, so the release-anyway path was not entered.
3. **A fresh `start` against a bare `sd-cli`.** The hand-launched child holds no lock, so `start` took it, exited 0 and
   was warm in 13.1 s; **two `sd-cli` processes coexisted** and the device peaked at **6854 MiB** of 8188. Both
   succeeded. **Nothing prevents it.** The mutex is a contract between this project's processes, not a property of the
   card; what kept both alive was `--offload-to-cpu` (each child near 3.2–3.9 GiB), while the measured resident child
   (7170 MiB) beside the server's own 512² warm-up (3221 MiB) would need 10,391 MiB on a 7857 MiB card. Whether that
   should change is open.

## What is not here

- **A clean quality verdict.** The 2026-11-17 comparison is confounded by its own
  layout; see above.
- **No swap-on-demand.** Two entries coexist and one model is served at a time: the
  served entry is chosen by alias at `start`, and a request names no model.
- **No 1280×720 run through the service on the surviving path.** The ladder measured the shape through the binary
  (10.3 s, 3761 MiB), but no request has been served at that shape through the queue; the service's own runs were
  1024×1024 because that was what the entry declared then.
- **No reproducible two-arm run.** `resource_profile.py` is single-arm now and `blind_ab.py` is gone.
- **No distribution behind T3, T4 or the sweep.** One prompt and one seed for the ladders, two prompts for the sampler;
  they are indications with a stated boundary.
- **No guard against an `sd-cli` launched outside the service.** T5's third scenario is the finding: the lock is
  cooperative and a bare child boots beside the server.
- **No exercised `stop` deadline.** The drain path was proven at ~11 s; nothing this entry admits outlasts the 30 s
  grace.

## Where the run products are

`evidence/` is gitignored. It holds the two stills, the two VRAM samplers' CSVs
and their peak summaries, the two `generate` stderr transcripts (both empty), the
determinism pairs, the two-arm `resource-profile.json`, the blind run's ten
stills and five sheets with `key.json` and `timings.json`, and
`encoder-parity.json`. The `ggml` commands above regenerate their own half; the
diffusers half is history. Three subfolders belong to the tests of 2026-11-17:
`evidence/staircase/` (the step and size stills, the two contact sheets and
`staircase.json`), `evidence/sweep/` (the sampler and shift stills, the four
sheets, `poker-faces.png` and `sweep.json`), and `evidence/contention/` (the
three scenarios' stills and `contention.json`). The scripts — `staircase.py`,
`sampler_sweep.py`, `contention.py` — are committed beside this README.

## The stress prompt, 2026-11-17

A lighthouse is one subject and a sky. This run asked for the opposite: **six
people around a poker table in a bar, one dealing cards, a bartender behind the
counter**, twice — once realistic, once as a comic page.

| Still | Style | What it did |
| --- | --- | --- |
| `evidence/poker-realistic.png` | photoreal, tungsten light, 50 mm | materials, light, smoke and depth hold; **it fails the count** — four players at the table, not six |
| `evidence/poker-comic.png` | ink, flat cel shading, halftone | six at the table plus the bartender, the dealer's exaggerated lean, and the empty speech bubble it was asked for |

Both ran through the diffusers entry (removed 2026-11-17) at 1024×1024, seed 7,
4 steps: `load_s` 81.314 and 81.855 against `render_s` 7.028. The encoder is the
reason for that ratio, and `docs/reference/flux2-klein.md` carries the ruling
that kept it — and the removal that overtook the ruling.
