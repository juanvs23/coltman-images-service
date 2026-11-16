# coltman-images

An independent, self-owned image generation service. It turns one generation
request into one still and owns the whole lifecycle: power on and warm up,
serve requests, shut down. It exposes a loopback HTTP API, and the CLI is that
API's first client — it contains no rendering of its own.

It is **not** a wrapper around one model. The core is model-agnostic; Z-Image is
the first adapter behind it, and the declared upscale stage serves every entry.
`docs/protocol.md` is the law that says what is true here; this file says how to
use it.

## What you need

- Linux and an NVIDIA GPU. The card this was measured on is an RTX 4060 Laptop
  with 8188 MiB, and the entry declares its own ceiling from what it measured
  there (`limits.max_pixels`), not from what the model could theoretically do.
- Python 3.14, torch 2.13.0+cu130 — pinned in `requirements.txt`.
- ~12 GB of RAM free: the weights live in the page cache between requests, and
  that is what makes the second request cheaper than the first.

The service reads **only its own tree** — the code, `model/entry.yaml`,
`model/assets/` and its own `.venv`. It never reads another project.

## Install

A fresh clone carries the code and the law. It does **not** carry the weights,
because 10 GB belongs in a model store and not in git. `model/assets/` is
declared by the entry and shipped separately.

```bash
cd coltman-images-service

# 1. the project's own interpreter
uv venv --python /usr/bin/python3.14 .venv
uv pip install --python .venv/bin/python \
  --index-url https://download.pytorch.org/whl/cu130 "torch==2.13.0+cu130"
uv pip install --python .venv/bin/python -r requirements.txt

# 2. the assets, at the paths model/entry.yaml declares
#      model/assets/checkpoint.safetensors      the FP8 transformer, 6.29 GB
#      model/assets/vae.safetensors
#      model/assets/vae_config.json
#      model/assets/scheduler_config.json
#      model/assets/qwen3/                      the Qwen3 text encoder directory
#      model/assets/upscaler/realesrgan_x2plus.pth
#    model/z_image.json is tracked (473 bytes) and pinned by digest in the entry.

# 3. prove it
.venv/bin/python -m unittest discover -s tests -v      # ~7 minutes
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

`generate` prints the absolute path of the file it wrote, and nothing else.
It never starts a server by itself: if none is running it exits 4 and says so.

### Flags

| Flag | Effect |
| --- | --- |
| `--prompt "..."` | required; the text to render |
| `--seed N` | absent: the server picks one and returns it in `--json` |
| `--width N` / `--height N` | absent: the entry's defaults, 1280×720 |
| `--steps N` | absent: the entry's default, 12; the server refuses a value outside the entry's range, 8–16 |
| `--out PATH` | absolute path; absent: `out/` with `<UTC>-<seed>.png` |
| `--upscale` | permit the declared stage when the size exceeds the native ceiling |
| `--json` | print the whole response object instead of the path |

### SD by default, HD on request

A request that fits the render ceiling gets exactly what the model rendered:

```bash
coltman-images generate --prompt "a lighthouse at dusk"                    # 1280×720
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

### What it costs

| Request | Measured |
| --- | --- |
| 1280×720, 12 steps | ~46 s (43.5 s of render, ~2.6 s of load) |
| 2560×1440 via the stage | ~52 s (the same render plus ~4.6 s of stage) |
| boot (`start`) | ~20 s, of which ~11 s is the discarded 512×512 warm-up |

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

The API sends no CORS headers and serves no page, so a browser cannot call it
from another origin as it stands. That is a declared limitation, not an
oversight: a client either runs in the same origin or proxies.

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

One test per guard, and guard 4 is written as two: about eight minutes, a dozen
stills. They prove request validation, the lifecycle and its idempotent edges,
that the warm-up is real, the census, determinism, the default folder, CLI/API
parity, self-containment, single-flight, the upscale stage, one instance per
card, that the core imports nothing from the model stack, that the entry knows
no model by name, and that the step count is bounded by the entry.

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
| `model/entry.yaml` | the model entry: assets, regime, defaults, ceiling |
| `model/upscaler.yaml` | the declared stage: its own weights and scale |
| `coltman_images/` | the core, plus `adapters/zimage.py` behind the adapter contract |

## Troubleshooting

**`the server is not running — run coltman-images start first` (exit 4).**
`generate` never starts a server. Start one.

**A stale state file.** If `run/server.json` names a pid that is gone, `start`
says so, clears the file and asks you to start again. Nothing is repaired
implicitly.

**`census ... no Float8 weights`.** The checkpoint at `model/assets/` is not the
one the entry declares, or it failed to load as FP8. Nothing else in the system
fails this quietly.

**Out of memory at 1280×720.** The card keeps ~1.1 GiB of slack. A desktop or a
second process taking a gigabyte will break the render; the service does not
retry into a smaller size, because that would silently change what you asked
for.

**`2560×1440 is ... above the ... px` with `upscale` missing.** That size is
above the native ceiling. Either ask for a size that fits, or pass `--upscale`
and accept that the extra pixels are synthesized.

## License

Apache License 2.0 — the full text is in [LICENSE](LICENSE).
Copyright 2026 Juan Carlos Avila Pérez.

The weights are **not** part of this repository and carry their own terms: the
FP8 checkpoint's card declares Apache 2.0, the upscaler's repository is
BSD-3-Clause, and each vendor card in `docs/reference/upstream/` states its own.
A license on this code says nothing about a model you download.

