# coltman-images

An independent, self-owned image generation service. It turns one generation
request into one still and owns the whole lifecycle: power on and warm up,
serve requests, shut down. It exposes a loopback HTTP API, and the CLI is that
API's first client — it contains no rendering of its own.

It is **not** a wrapper around one model. The core is model-agnostic; Z-Image is
the first adapter behind it, FLUX.2 [klein] the second (through the vendored
`ggml` runtime), and the declared upscale stage serves every
entry. `docs/protocol.md` is the law that says what is true here; this file says
how to use it.

## What you need

- Linux and an NVIDIA GPU. The card this was measured on is an RTX 4060 Laptop
  with 8188 MiB, and the entry declares its own ceiling from what it measured
  there (`limits.max_pixels`), not from what the model could theoretically do.
- Python 3.14, torch 2.13.0+cu130 — pinned in `requirements.txt`.
- ~12 GB of RAM free: the weights live in the page cache between requests, and
  that is what makes the second request cheaper than the first.

The service reads **only its own tree** — the code, the entries, `model/assets/`,
its own `.venv` and the vendored `ggml` runtime. It never reads another project.

### The deployment's declaration

`host.yaml` at the tree root says what **this machine** can afford, kept apart
from what a model is. `model/entry.yaml` declares one model's assets, regime and
the largest box it has been measured to render here; `host.yaml` declares the
deployment around it, and the server reads it at boot — there is no flag for it.

```yaml
id: this-deployment
vram_mib: 7857          # torch-usable device memory on this card
offload: true           # hand the ggml child --offload-to-cpu
lora_budget_mib: 3200   # device memory a request's LoRAs may fill, summed from the files
```

That is the whole file this tree ships. A deployment may add one optional block,
to render less than the entry allows — valid only when the entry's default box
fits under the cap:

```yaml
limits:                 # optional, and it may only tighten
  max_pixels: 1048576   # at most the entry's measured ceiling, at least its default box
  steps: {min: 6, max: 8}   # inside the entry's range, and containing its default count
```

- **A host may tighten, never widen.** The effective ceiling is the smaller of
  the host's and the entry's, and the effective step range is their intersection;
  that is what a request is validated against. A `max_pixels` above the entry's
  measured ceiling, or a step range reaching outside the entry's, is refused at
  `start` with exit 3 and a message naming the bound: the entry's number is a
  measurement, and a host is not allowed to promise a box nobody rendered. A cap
  below the entry's default box is refused too, rather than shrinking every
  default request behind your back — lower the entry's defaults or raise the cap.
- **It is optional.** With no `host.yaml`, the entry's own limits apply, the LoRA
  budget is the measured linear arm (3443 MiB), and `offload` is on: the service
  runs exactly as it did before the file existed.
- **Why this tree ships no `limits`.** Both entries render their default box
  exactly at their measured ceiling (1152×1152 on the promoted entry, 1280×720 on
  Z-Image's), so a cap that tightens either one sits below that entry's default
  box — refused — and a cap above either ceiling widens a measurement — refused
  too; no single cap covers both entries. A deployment that wants a smaller
  envelope declares a cap **and** serves an entry whose defaults fit under it.
  Protocol section 6.1 has the arithmetic.

## Install

A fresh clone carries the code and the law. It does **not** carry the weights,
because 16 GB belongs in a model store and not in git. `model/assets/` is
declared by the entry and shipped separately.

```bash
cd coltman-images-service

# 1. the project's own interpreter
uv venv --python /usr/bin/python3.14 .venv
uv pip install --python .venv/bin/python \
  --index-url https://download.pytorch.org/whl/cu130 "torch==2.13.0+cu130"
uv pip install --python .venv/bin/python -r requirements.txt

# 2. Z-Image's assets, at the paths model/entries/zimage.yaml declares
#      model/assets/checkpoint.safetensors      the FP8 transformer, 6.29 GB
#      model/assets/vae.safetensors
#      model/assets/vae_config.json
#      model/assets/scheduler_config.json
#      model/assets/qwen3/                      the Qwen3 text encoder directory
#      model/assets/upscaler/realesrgan_x2plus.pth
#    model/z_image.json is tracked (473 bytes) and pinned by digest in that entry.

# 2b. the promoted model's assets, at the paths model/entry.yaml declares
#      model/assets/flux2-klein/gguf/      the Q4_K_M diffusion model and Qwen3 encoder
#      model/assets/flux2-klein/official/vae/diffusion_pytorch_model.safetensors
#      model/assets/loras/flux2-klein-4b-gguf-q4/pixel-art.safetensors          325 MB
#      model/assets/loras/flux2-klein-4b-gguf-q4/anime.safetensors              185 MB
#      model/assets/loras/flux2-klein-4b-gguf-q4/background-remove.safetensors   76 MB
#    The three LoRA files are the promoted entry's catalog, and they live in the
#    folder named for that entry's id: a model owns its LoRAs, and a LoRA that
#    works on a second model is copied into that model's folder rather than
#    shared (protocol sections 3 and 6.1). The entry refuses to boot without
#    them even when a request names none: a declared asset that is missing is
#    exit 3. Drop one and drop its alias from the entry, or the service will not
#    start.
#    The ggml runtime is built, not committed: vendor/stable-diffusion.cpp at
#    commit 532d2c1, with patches/0001-flux2-lora-name-conversion.patch applied
#    before the build, and the entry pins the binary's digest (protocol section 2).
#    FLUX.2 [klein]'s second runtime (the official scaled-FP8 checkpoint read by
#    diffusers) was removed on 2026-11-17 with its assets and its entry; the
#    numbers behind that removal are in docs/reference/flux2-klein.md.

# 3. prove it
.venv/bin/python -m unittest discover -s tests -v      # ten to fifteen minutes
```

**Guard 4 is the proof that step 2 worked.** The loader counts the parameter
dtypes and refuses a model with no Float8 weights; the census must read
`239 / 282 / 0 / 521`. Anything else means the checkpoint is not the one the
entry declares, and the service says so instead of rendering something
plausible.

## Use it

```bash
coltman-images start                          # loads, warms up, binds 127.0.0.1:8420
coltman-images generate --prompt "a lighthouse at dusk"
coltman-images stop
```

`start --model ID` serves an entry by its `id`. Two exist: the promoted default,
FLUX.2 [klein] (`flux2-klein-4b-gguf-q4`, on the vendored `ggml` runtime), and
Z-Image Turbo FP8 (`z-image-turbo-fp8`), preserved unchanged:

```bash
coltman-images start --model flux2-klein-4b-gguf-q4
coltman-images generate --prompt "a lighthouse at dusk" --seed 7 --width 1024 --height 1024 --json
coltman-images stop

coltman-images start --model z-image-turbo-fp8
coltman-images generate --prompt "a lighthouse at dusk" --seed 7
coltman-images stop
```

An unknown id is refused with the ids the tree declares. Two entries coexist and
one model is served at a time, because the card is single: changing the model is
`stop` and `start` again. On `generate`, `--model` is a check, not a selector: it
says which entry you believe the server is serving and is refused if it is
another, because a request names no model. Without either flag, `start` serves
`model/entry.yaml`, the promoted entry. `--entry PATH` is a **development
shortcut** that names the entry file directly; prefer `--model`.

`start` can also hand the server a deadline for itself:

```bash
coltman-images start --idle-timeout 300       # retires after 5 minutes with no work
```

With no `--idle-timeout` the server never self-terminates, which is the default.
With one, it releases the process and the port after that many seconds with no
request in flight and none queued — through the same drain `stop` uses. The floor
is the measured **15.1 s** boot cost (11.0 s of it a discarded warm-up) and a
shorter period is refused at the door, because a server that idles for less than
it takes to start is worse than no server: the next request pays that boot again.

`generate` prints the absolute path of the file it wrote, and nothing else.
It never starts a server by itself: if none is running it exits 4 and says so.

### LoRAs

The promoted entry declares a catalog of three LoRAs under aliases —
`pixel-art`, `anime` and `background-remove` — and a request names an alias,
never a path:

```bash
coltman-images generate --prompt "a brave knight in shining armor holding a sword" \
  --width 512 --height 512 --lora pixel-art

coltman-images generate --prompt "a lighthouse at dusk" \
  --lora pixel-art:0.6 --lora anime:0.3              # repeatable, with weights
```

`--lora alias[:weight]` is repeatable, one occurrence per LoRA; the weight is a
number in `(0, 1]` and, when you leave it out, the catalog's own default (1.0 for
`pixel-art`, 0.5 for the other two). The catalog belongs to the entry, so Z-Image
accepts no LoRA at all, and an alias the served entry does not declare is refused
with the ones it does. **Each model owns its LoRAs**, and they live in
`model/assets/loras/<entry-id>/`: reuse across models is possible but unverified,
so a LoRA that works on a second model is copied into that model's folder rather
than shared, and the entry refuses a path outside its own folder. What a request's
LoRAs may cost is a **budget in device memory**, not a count: the door sums the
requested LoRAs' file sizes against `host.yaml`'s `lora_budget_mib` — 3200 MiB
here — and refuses a request above it with the sum, the budget and the largest
single LoRA named. That is what the card was measured to afford: a 325 MB LoRA
costs **+313 MiB of device memory and +1.5 s**, linear to eleven selections, and
from twelve the memory plateaus at ~7.6 GB while the wall time doubles. A request
with no `lora` field is rendered exactly as it was before the feature existed.

### A reference image

FLUX.2 [klein] is an editor as well as a text-to-image model: give it a picture
and a prompt that says what to do with the picture. The request field is `image`,
a list of absolute paths, and the served entry declares how many its model
accepts — **10 on the promoted entry**, none on Z-Image's, whose entry refuses
the field by name:

```bash
# a still to edit: the service renders the reference itself
coltman-images generate --prompt "a red ceramic vase on a white table" \
  --seed 7101 --width 512 --height 512 --steps 4 --out /abs/path/vase.png

# the edit: the picture goes in, the prompt says what to do with it
coltman-images generate --prompt "Remove the background from the image" \
  --lora background-remove --image /abs/path/vase.png \
  --seed 7102 --width 512 --height 512 --steps 4 --json
```

`--image PATH` is repeatable and, like `--out`, the path is made absolute for you.
The door refuses a path that is not a file (naming it) and more references than the
entry declares (naming both numbers), before any model is loaded. The response
echoes the paths the still was conditioned on, so `"image": []` means it was
conditioned on the prompt alone. The page carries the same field as an image
control; its upload is copied into `run/ui/`, inside the tree.

What is **not** measured here: whether each editing LoRA behaves as its own card
claims — nine of them are reachable and unrendered — and whether a style LoRA
trained on text-to-image pairs helps or fights a reference. `docs/reference/lora-catalog.md`
§10 keeps both open.

### Flags

| Flag | Effect |
| --- | --- |
| `--prompt "..."` | required; the text to render |
| `--seed N` | absent: the server picks one and returns it in `--json` |
| `--width N` / `--height N` | absent: the entry's defaults (1152×1152 on the promoted entry, 1280×720 on Z-Image's) |
| `--steps N` | absent: the entry's default (8 on the promoted entry, 12 on Z-Image's); the server refuses a value outside the entry's range (4–8, or 8–16) |
| `--out PATH` | absolute path; absent: `out/` with `<UTC>-<seed>.png` |
| `--upscale` | permit the declared stage when the size exceeds the native ceiling |
| `--lora alias[:weight]` | apply a LoRA the served entry declares; repeatable; absent: none. The alias, the weight and the count are the server's to accept or refuse |
| `--image PATH` | a reference image to edit or condition on; repeatable, up to the entry's `image.max` (10 on the promoted entry, none on Z-Image's). A missing file and too many references are refused by the server |
| `--json` | print the whole response object instead of the path |

### SD by default, HD on request

A request that fits the render ceiling gets exactly what the model rendered:

```bash
coltman-images generate --prompt "a lighthouse at dusk"                    # 1152×1152
```

Anything larger needs the stage's permission, because the pixels above the
ceiling are **synthesized, not rendered**:

```bash
coltman-images generate --prompt "a lighthouse at dusk" \
  --width 2560 --height 1440 --upscale --json
# "upscale": {"model": "realesrgan-x2plus", "scale": 2,
#             "from": [1280, 720], "to": [2560, 1440], "upscale_s": 4.6}
```

The response records the base it started from, so no reader can mistake one for
the other. Refuse the flag and a size above the ceiling is refused at the door,
before any GPU work.

### Use the browser

The same process can serve a page, from the same queue:

```bash
coltman-images start --ui                    # the page on http://127.0.0.1:7860
coltman-images start --ui --ui-port 8000     # somewhere else
```

`start` echoes the address on its success line. The page is two equal halves: the
form on the left, the still and its details on the right. The form has a prompt, a
**reference image**, a seed (leave it empty and the server picks one and reports
it), a size switch, an **aspect** choice and a **steps** slider. The shape decides
the box and the entry decides how big it may be, so neither the slider nor the
shapes carry a size: the steps range and its starting position are the entry's
`limits.steps` and `steps`, and every box is the largest at that shape inside the
entry's ceiling (or, for HD, inside what the declared stage can serve). The
reference control is an image input and it hands the page a **path**: drop a
picture there and the prompt says what to do with it, leave it empty and the
request carries no reference at all — and an entry that declares no reference
capability (Z-Image's) hides the control rather than offering something the door
would refuse. The status line sits at the top of the right half, where you are
looking while a request runs.

The five shapes, and what each gives on the promoted entry:

| Shape | SD | HD |
| --- | --- | --- |
| `16:9` | 1536×864 | 3072×1728 |
| `1:1` | 1152×1152 | 2304×2304 |
| `4:3` | 1280×960 | 2624×1968 |
| `3:4` | 960×1280 | 1968×2624 |
| `9:16` | 864×1536 | 1728×3072 |

`16:9`, `1:1` and `9:16` reach the ceiling exactly — 1,327,104 px each. `4:3`
cannot: its next step up with both sides on the 16 grid is 1344×1008, 27,648 px
over `max_pixels`, so it stops at 1280×960 — which is the reason the page offers a
list of shapes rather than two free width/height fields, where you could ask for a
size the card refuses. On Z-Image's entry the same computation yields a different
ten boxes, because the ceiling and the defaults are the entry's.

Every control also says what it does: one line under it, and a collapsed **what
each control does** guide at the foot of the form with the detail — including the
ten boxes this entry and its stage produce for the five shapes, all computed.

It is a third door onto the same implementation, not a second renderer: it calls
the same `submit()` the API calls, so two tabs serialise instead of loading two
models.

What the page says, and what each line means:

| On screen | Means |
| --- | --- |
| **SD** | the native render — `upscale: null`; nothing was synthesized |
| **HD** | a delivered size above the native ceiling, and the line names the base it started from (`upscale.from`) |
| aspect | the shape; the box is computed from it, the entry's `limits.max_pixels` and the stage's factor |
| reference (panel) | the reference paths the response echoed as `image`; the line is absent when the request carried none |
| `steps` (form) | the entry's ladder: its range and its default come from `limits.steps`, and a position at the default is sent as no `steps` field at all |
| `steps N` (panel) | the count the still was actually rendered with, from the response — not the slider's position |
| the census | parameter counts exactly as the entry's adapter declares the keys |
| `render_s` / `load_s` / `duration_s` | the render, the load, and the whole request — the last one is the only place queue wait is visible |
| the queue depth while it waits | the number `/health` reports: jobs waiting for the single worker — your own request counts while it waits |

`--ui` is off by default, and a server started without it never imports gradio.
If gradio is missing, `start --ui` exits 3 before loading a weight and says how
to install it. `--ui-port` without `--ui`, or equal to the API's port, is a usage
error (exit 2), and the page's telemetry is off: a page that called
`api.gradio.app` would be a runtime lookup outside this tree. It keeps its file
cache under `run/ui/`, and `stop` takes the page down with the process.

### What it costs

| Request | Measured |
| --- | --- |
| Z-Image, 1280×720, 12 steps | ~46 s (43.5 s of render, ~2.6 s of load) |
| Z-Image, 2560×1440 via the stage | ~52 s (the same render plus ~4.6 s of stage) |
| FLUX.2 [klein], 1024², 4 steps, through the service | 15.5 s of `render_s`; `load_s` is 0 by declaration, because the child loads, samples and exits in one call |
| FLUX.2 [klein], 1152², 4 steps, the child's own wall | 13.4 s, 4701 MiB — one prompt, one seed |
| FLUX.2 [klein], 512², 8 steps, one LoRA | 8.96 s against 7.27 s without it, `pixel-art` at weight 1.0, and 10.52 s with three — one prompt, one seed, measured 2026-11-17 through the service. The per-MiB cost is **+1.5 s and +313 MiB of device memory for a 325 MB LoRA**, linear to eleven selections; the door refuses a request whose LoRAs exceed `lora_budget_mib` |
| boot (`start`) | Z-Image ~20 s, of which ~11 s is the discarded 512×512 warm-up; FLUX.2 [klein] ~11.3 s. The 15.1 s the server spends on Z-Image's side is the floor `--idle-timeout` is refused below |

There is **no per-request timeout**: a render runs until it finishes, and `stop`
is the only abort. The queue never refuses a request; it serialises them,
because one model is 6 GB of an 8 GB card. `GET /health` reports how deep the
queue is.

## The API

Loopback only. Three endpoints.

```bash
curl -s localhost:8420/health
curl -s -X POST localhost:8420/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "a lighthouse at dusk", "seed": 42}'
curl -s -X POST localhost:8420/shutdown
```

`POST /generate` returns the response object: `out`, `steps`, `seed`, `width`,
`height`, `model`, `census`, `duration_s`, `render_s`, `load_s`, `upscale`.
Errors are always `{"error": {"code": ..., "message": ...}}`:
`400 invalid_request` or `500 render_failed`, and nothing else.

The API sends no CORS headers, so a browser cannot call it from another origin as
it stands. That is a declared limitation, not an oversight: a client either runs
in the same origin or proxies. The page of `start --ui` is the exception by
construction — it lives in the server process and calls `submit()` directly, so
it needs no CORS and no proxy.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | the render failed |
| 2 | invalid request |
| 3 | a declared asset is missing |
| 4 | the server is not available |

Full table and the exact mapping: `docs/protocol.md` §5.4.

## The guards

```bash
.venv/bin/python -m unittest discover -s tests -v
```

One test per guard, and guard 4 is written as two: ten to fifteen minutes, nineteen
stills. They prove request validation, the lifecycle and its idempotent edges,
that the warm-up is real, the census, determinism, the default folder, CLI/API
parity, self-containment, single-flight, the upscale stage, one instance per
card, that the core imports nothing from the model stack, that the entry knows
no model by name, that the step count is bounded by the entry, that the web
page is a surface on the same queue and never a renderer of its own, that the
host declaration may only tighten what the entry measured — with a tree that has
none still serving the entry's own limits — and that a LoRA is a catalog on the
entry (owned by its model's folder) with a memory budget on the host, refused by
alias and by size and delivered when it is inside both.

The count lives in `docs/protocol.md` §10 and nowhere else; this section names
what the tests are for, not how many there are today.

Evidence for the acceptance runs lives in `tests/e2e/<phase>/`, each with a
committed `README.md` and a gitignored `evidence/` folder.

## Where things live

| Path | What |
| --- | --- |
| `docs/protocol.md` | **the law** — the surface, the lifecycle, the guards |
| `docs/context.md` | purpose, environment, known issues |
| `docs/roadmap.md` | phases, debt, and what is not yet measured |
| `docs/changelog.md` | one entry per work unit |
| `docs/reference/` | the measurements the cost model is built on — evidence, not law |
| `model/entry.yaml` | the model entry: assets, regime, defaults, ceiling, LoRA catalog |
| `model/assets/loras/<entry-id>/` | the LoRAs one model owns: one folder per entry, copied — never shared — when a LoRA is verified on another model |
| `host.yaml` | the deployment: the card's memory, the offload policy, the LoRA budget, and limits that may only tighten |
| `model/upscaler.yaml` | the declared stage: its own weights and scale |
| `coltman_images/` | the core, plus `adapters/zimage.py` behind the adapter contract |
| `coltman_images/ui.py` | the web page of `start --ui`: presentation for the submission seam |

## Troubleshooting

**`the server is not running — run coltman-images start first` (exit 4).**
`generate` never starts a server. Start one.

**A stale state file.** If `run/server.json` names a pid that is gone, `start`
says so, clears the file and asks you to start again. Nothing is repaired
implicitly.

**`census ... no Float8 weights`.** On Z-Image's entry, the checkpoint at
`model/assets/` is not the one the entry declares, or it failed to load as FP8.
Nothing else in the system fails this quietly.

**Out of memory at the top of the range.** Z-Image at 1280×720 keeps ~1.1 GiB of
slack; FLUX.2 [klein] at 1152² keeps 3156 MiB of the card's 7857 usable. A desktop
or a second process can take either margin away, and the service does not retry
into a smaller size, because that would silently change what you asked for.

**`2560×1440 is ... above the ... px` with `upscale` missing.** That size is
above the native ceiling. Either ask for a size that fits, or pass `--upscale`
and accept that the extra pixels are synthesized.

**`lora: this entry declares no LoRA named ...`.** The served entry's catalog
does not declare that alias. The promoted entry declares `pixel-art`, `anime` and
`background-remove`; Z-Image's entry declares none, so it accepts no LoRA at all,
and a catalog is per model. The refusal lists the aliases the served entry has.

**`lora: these N LoRAs need X MiB … and this deployment's budget is Y MiB`.** The
request's LoRAs are summed by their files' sizes and the total is above
`lora_budget_mib` — 3200 MiB on this deployment. The message names the sum, the
budget and the largest single LoRA in the catalog, so the arithmetic is visible;
send fewer or smaller ones, or raise the budget (never above the card's own
memory). A budget is a memory and not a count: the same number of small LoRAs can
fit where fewer large ones do not.

## License

Apache License 2.0 — the full text is in [LICENSE](LICENSE).
Copyright 2026 Juan Carlos Avila Pérez.

The weights are **not** part of this repository and carry their own terms: the
FP8 checkpoint's card declares Apache 2.0, the upscaler's repository is
BSD-3-Clause, and each vendor card in `docs/reference/upstream/` states its own.
A license on this code says nothing about a model you download.

