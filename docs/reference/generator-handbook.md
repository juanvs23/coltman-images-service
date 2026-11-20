# Generator handbook — using this service as an image generator

For another project that wants stills from this repository. It states what is
installed, what is measured, and what is not yet true.

**The law is `docs/protocol.md`.** This file is the practical view; if the two ever
disagree, the protocol wins and this file is wrong.

---

## 1. What serves

Two models are installed, and `model/models.yaml` is the roster. One is served at a
time, because the card is single.

| Model | Role | Default box | Measured |
|---|---|---|---|
| `moss-dmd-int8` | **production** | **1280×720** | **40,9 s / 41,7 s**, peak **6.188 MiB** |
| `flux2-klein-4b-gguf-q4` | draft | 1152×1152 | 22,4 s, peak 4.305 MiB |
| `z-image-turbo-fp8` | retired | — | weights deleted; see `retired-models.md` |

**Use production when the still ships. Use the draft model to explore prompts**, because
ten variations cost 4 h on the draft against 9,5 h on production.

The card is 8 188 MiB total, 7 857 torch-usable. Both models fit with the offload the
adapters pass; neither is run twice — the adapters take `run/server.lock` and refuse with
the holder's pid.

---

## 2. What it costs for the real workload

The deployment's shape is **60–70 stills per 15-minute faceless video**, which is
**4,0–4,7 stills per minute of video**.

| | Per still | 65 stills (one video) | Videos per 8 h |
|---|---:|---:|---:|
| `moss-dmd-int8` at 1280×720 | 41 s | **~44 min** | ~10,9 |
| `flux2-klein` | 22,4 s | ~24 min | ~21,4 |

Hires work (the MOSS Hires LoRA at 1280×1280) measured **222,9 s** per still — **4 hours
per video**. It is a stills option, not a video option.

---

## 3. The two configurations

| Criterion | Configuration | Why |
|---|---|---|
| **Quality** | **CFG 3,0, 12 steps, no LoRA** | the active negative prompt is what prevents the plastic skin that a LoRA-free CFG-1.0 render shows |
| **Speed** | CFG 1,0 with the 12-step turbo LoRA, 8 steps | removes the negative branch, which is where the time goes — and the matte skin with it |

**The speed configuration is a concession, not an upgrade.** At CFG 1.0 the negative
prompt is never encoded: the log shows one conditioning pass instead of two. That is why
it is faster and why skin and material variety suffer.

**Not yet reachable through the service:** `moss.yaml` declares `guidance: 3.0` and one
catalogue alias, `realism` — not the turbo adapter — so the turbo path needs either a
`guidance` override or a second entry. Both are one-line changes once that decision is
made.

---

## 4. What is installed, with licence status

### MOSS adapters — `model/assets/loras/moss-dmd-int8/` (24 files)

**Verified in this runtime:** `MOSS-Image-Anime-LoRA-F16` (504/504 tensors, L1 and L2
passed) and `12_step_turbo_moss_1024_distill_v8_r64_weightsx2` (552/552, L1 passed).
Neither is declared: the entry's catalogue is `realism` alone.

**Present but not declared:** the control adapters (`depth`, `pose`) — a control LoRA
needs a control image, and this adapter cannot send one, so they cannot work here yet.
Character LoRAs (Frieren, Alya, Emilia, Marin, Gabriel DropOut) are **copyrighted IP** and
must not be used in commercial delivery. `moss_alpha_v1` and the manga alpha pair need a
4-channel RGBA VAE that this build refuses. `epyan_4step_lora` needs its own sampler.

**Absent although named in the plan:** Impressionism, NextScene and five of the seven
`thedeoxen` controls were never downloaded. The catalogue declares one alias, `realism`;
the rest of the step is not done.

### klein adapters — `model/assets/loras/flux2-klein-4b-gguf-q4/`

`pixel-art`, `anime`, `background-remove`. All three are in the promoted entry's
catalogue and covered by the guard matrix.

### Licence rule applied

**A LoRA has no independent licence.** It inherits the base model's — MOSS-Image and
FLUX.2 are Apache 2.0 — and adds whatever its author declares. **Absence of a licence is
not permission:** default copyright applies. Verified commercial-clean in this tree:
Impressionism, NextScene and the `deadman44` styles (subject unclear), all Apache 2.0.

---

## 5. How another project uses this

```sh
./bin/coltman-images start --model moss-dmd-int8          # boots and warms
./bin/coltman-images generate --prompt "…" --seed 7 \
    --width 1280 --height 720 --out /abs/path.png --json
./bin/coltman-images stop                                  # releases the card
```

- `--model <id>` resolves an entry id across `model/entry.yaml` and
  `model/entries/*.yaml`. An unknown id is refused with the ids the tree declares.
- `--width/--height` are optional; absent, the entry's defaults apply (1280×720 for MOSS).
- **Sides must be multiples of 16.** The MOSS adapter refuses off-grid sides before the
  child starts and names both numbers; the runtime would otherwise round up silently
  (520×500 becomes 528×512).
- `--out` must be an absolute path. The service writes nothing outside it and `run/`.
- `--json` returns the whole response including `render_s`, `duration_s`, `census` and the
  echo of the request. **There is no device-memory field**: the subprocess adapters own no
  torch allocator, so peak VRAM is measured from outside with `nvidia-smi`.

**Crossing a project boundary:** this repository does not read or write outside its own
tree. A consumer in another project should call the HTTP surface or copy the artefacts it
needs, and the card is single, so a second consumer is a scheduling decision.

---

## 6. What is not measured, stated plainly

- **No 1024×1024 render can be requested through `moss.yaml`** — the ceiling is 921 600 px
  so that SD lands on 1280×720. The quality figures in
  `docs/research/p10-b3-dreamshaper-and-moss-stage2-report.md` were taken at 1024×1024
  before the ceiling was fixed, and are labelled as history there.
- **The turbo LoRA at CFG 3,0 is unmeasured**, which is why it is not declared.
- **LoRA L3** (three adapters stacked) passed on the raw runtime, not through this
  service.
- **The catalogue declares one alias, `realism`.** The anime adapter works end to end
  through `denoise` and the turbo adapter is verified in the runtime, but neither is
  declared: declaring one is an entry block plus `lora` in `request_fields`.
