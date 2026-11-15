# coltman-images

## What it is

`coltman-images` is an independent, self-owned image generation service. It turns a generation request into a still and owns its whole lifecycle: `coltman-images start` powers on and warms up, `coltman-images generate` serves a generation, `coltman-images stop` shuts down gracefully. It carries its own connection layer for applications — a loopback HTTP API, with the CLI as its first client — plus its own model entry, vocabulary, protocol and tests, and runs with no other project present. The model is an asset its entry declares and uses, not something it owns. Every artifact of the system itself is declared, not built.

## How to run it

Setup:

| Item | Value | State |
| --- | --- | --- |
| Interpreter | `.venv/bin/python` — the project's own: Python 3.14.8, torch 2.13.0+cu130, CUDA 13.0, torchao 0.18.0 | owned, pinned |
| Model assets | `model/assets/` — checkpoint `Z-Image-Turbo-FP8.safetensors` (6,289,509,744 bytes), the VAE and its config, the scheduler config, and the `Qwen3/` encoder. These are the project's own copies; the folder is gitignored | present |
| Transformer config | `model/z_image.json` — 473 bytes, pinned by digest | present |
| Model entry | this project's own `model/entry.yaml` | declared, not built |

Commands:

| Command | Effect | State |
| --- | --- | --- |
| `coltman-images start [--port N] [--foreground]` | power on and warm up; binds `127.0.0.1` after warm-up | declared, not built |
| `coltman-images generate --prompt "..." [--seed N] [--width N] [--height N] [--out PATH] [--json]` | render one still; returns the absolute path | declared, not built |
| `coltman-images stop` | graceful shutdown | declared, not built |

A minimal call against the API:

```bash
curl -s -X POST http://127.0.0.1:8420/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "a lighthouse at dusk", "seed": 42}'
```

The response body is the generation response; `out` is the absolute path of the written file.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | render failed |
| 2 | invalid request |
| 3 | a declared asset is missing |
| 4 | the server is not available (not running, unreachable, or the port could not be claimed) |

## Where to go

- `docs/protocol.md` — the law.
- `docs/context.md` — purpose, structure, environment.
- `docs/roadmap.md` — phases and debt.
- `docs/changelog.md` — changes.
- `docs/reference/` — the measurements the cost model is built on.
