# Roadmap

## Next step

**P7 — the rename and the first commit.** P6 closed on 2026-11-15 with all eleven guards executable and green: twelve tests, 406.6 s, eight stills, and three consecutive runs producing the same `sha256 d155082c…` — determinism across separate server processes, not only within one. The project still carries a name that describes its first model rather than its function, so it is renamed `coltman-images-service`, the suite is re-run under the new name, one still is compared byte for byte with the pre-rename one, and version control begins with a first commit that invents no history before it.

No phase may start before the previous one has an **observed** exit: a command whose output is the proof. A document is not an exit criterion.

## Phases

| Phase | Scope | Exit criterion | Status |
| --- | --- | --- | --- |
| **P1** | The project and its law: these documents, the reference material and the upstream cards. | The documents exist, cite only their own sources, and every code artifact is marked declared. | done, 2026-11-15 |
| **P2** | The render core: `model/entry.yaml` (resolved by name, all model values inside it), the `z_image.json` copy with its digest, the loader module with the activation-scale floor and the root-tensor remap, the live census. | One cold render callable from a Python call writes one still and prints `239 / 282 / 0 / 521`. No server, no port, no CLI. | done, 2026-11-15 |
| **P3** | The declared upscale stage: its own declaration in `model/upscaler.yaml`, its own weights, the tiled pass, and the request field that permits it. It applies to every entry, so it does not live in one. | A request above the render ceiling is refused without the permission and served with it; the response declares the stage and the base size it started from; the census is still the render's. | done, 2026-11-15 |
| **P4** | The server process: warm-up, `run/server.json`, single-flight queue, `GET /health`, `POST /shutdown`, `POST /generate`, and the CLI's `start`/`stop`. `/generate` lands here rather than in P5 because a queue with no producer cannot be tested, and single-flight cannot be proven without two concurrent requests. | `start` returns after warm-up; `/health` answers warm; a second `start` exits 0 and reports the running server; `stop` releases the card and removes the state file; two concurrent requests both succeed and never run two models. | done, 2026-11-15 |
| **P5** | `coltman-images generate` as the CLI client of the API, and the parity proof. | One prompt through the CLI writes the still (default folder or the requested path) and prints its path; a direct POST for the same seed produces the same bytes. | done, 2026-11-15 |
| **P6** | The eleven guards of protocol section 10, at protocol section 10's thresholds. | The suite runs under the production interpreter; every guard passes or reports its failure as a failure. | done, 2026-11-15 |
| **P7** | The rename and the first commit: the project stops being named after its first adapter (`coltman-images-service`), and version control stops being a debt. | The suite is green under the new name, a still is byte-identical to the pre-rename one, and `git log` shows a first commit with no history invented before it. | current |
| **P8** | Clients. This phase lives outside this project: the surface is already declared, and a client adapts to it. | Nothing here. | outside |

## P2 in order

1. `model/z_image.json` — done: the 473-byte transformer config is copied in and its `sha256` (`06d49d1a…c06af8`) is pinned in the entry.
2. `model/entry.yaml` — done: every field of protocol section 6.1 (`request_fields`, `expected_census`), with every asset path relative to the project root and the assets in `model/assets/`.
3. `coltman_images/entry.py` — done: resolves and validates the entry, refuses an unknown field, a missing field, a missing asset, a digest mismatch, a field outside the closed vocabulary and an incoherent census, and answers `accepts()` for a request before any GPU work.
4. The loader — done: `coltman_images/fp8.py` and `coltman_images/loader.py` build the FP8 weights straight from the checkpoint's `qdata` and `_weight_scale` (bit-identical, with no bfloat16 copy), floor the dynamic activation scale at `1e-12` themselves, remap the two `unsloth_root::` tensors, and count 239 / 282 / 0 / 521. The load takes 0.07 s and the transformer fits on the card in 6057 MiB.
5. Guard 4 as a callable first, a test later — done: `assert_census` refuses a wrong census, a model with no Float8 weights, and an unexpected dtype.
6. One cold render — done: 11.0 s at 512×512 and 43.5 s at 1280×720, a 908 KB PNG, the census out, and the same seed gives byte-identical files across separate processes.

## P3 in order

1. The weights — done: `realesrgan_x2plus.pth` (67 MB, sha256 `49fafd45…`) copied in; `realesrgan_x4plus.pth` kept as the comparison arm.
2. `model/upscaler.yaml` — done: its own declaration, ×2, separate from the model entry because the stage serves both models.
3. `coltman_images/upscale.py` — done: RRDBNet in pure torch, `scale` as a constructor argument, both files strict-clean at 702 tensors, tiled at 256 with 32 px of context and a worst seam of 0.0029 over 9 tiles.
4. Wired into `render.py` — done: `width` and `height` are the delivered file, the base is derived under the ceiling, and the response declares the chain.
5. Measured — done: 4.6 s of stage on top of a 43.4 s render, deterministic across runs, and refusals land at the door for both missing permission and the 3,686,400 px cap.

## P6: the guards, and the measurement that is not a guard

The eleven guards are automatable and block. One open question does **not** fit a guard, because it needs a judgment: whether the 8-step regime invents more than the 12-step one, and whether FP8 invents more than INT8. It is scheduled as a **measurement protocol**, not a pass/fail test:

- a fixed prompt set, three seeds, both step regimes, both quantization arms;
- scored blind on unrequested objects and broken text;
- the result recorded in `docs/reference/`, and the ruling recorded in protocol section 12.

Until that measurement exists, no document may claim one regime hallucinates less.

## Debt schedule

### `[DEBT] no-version-control` — closed 2026-11-15

Deferred because the operator's decision was open. Closed when the operator ordered version control: the repository exists, `git init` ran in `<this repository>`, and the first commit carries the state as it stood when the debt closed. No history was invented before it, and the ignore file keeps the weights, the venv, the run state and the test evidence out of the repository.

### `[DEBT] no-idle-timeout`

The server never self-terminates, so a forgotten server keeps a process and its port indefinitely — and, measured on 2026-11-15, about 165 MiB: 770 MiB with the server idle against 605 without it. It does **not** hold the card; the GPU is free between requests. Justified because auto-stop changes the meaning of "warm" and the cost of the next request.

- Target spec: an `--idle-timeout` option that releases the process and the port after a declared idle period. There is no GPU to release.
- Steps: the boot cost is already measured — 15.1 s, of which 11.0 s is the discarded warm-up — so declare the option against that number.

### `[DEBT] server-mirrors-render-sequencing` — closed 2026-11-15

`coltman_images/server.py` repeated about forty lines of
`coltman_images/render.py`'s ordering —
encode, denoise, decode — because `_encode` built its own tokenizer and `render`
accepted no warm VAE. The arithmetic was not duplicated, only the sequencing.

- Target spec: `render` and `_encode` accept the warm pieces, and the server calls them instead of restating them.
- Steps: give `_encode` a `tokenizer=` argument and `render` a `tokenizer=`/`vae=` argument; delete the mirror; re-run the P4 acceptance transcript, which is the proof the refactor changed nothing.
- Closed by the adapter cut: `coltman_images/adapter.py` is the contract and registry,
  `coltman_images/adapters/zimage.py` holds the sequencing once, and `server.py`'s worker calls `render.render` with the adapter it built at boot. The mirror and its `_encode`/`_render` methods are deleted. Proof: the P4 acceptance run is green again (seven checks, exit 0) and the seed-7 1280×720 still from `POST /generate` is byte-identical to the pre-cut file, `sha256 ff3b84a0…dbe5c4`; `render.py` fell from 519 to 317 lines and `server.py` from 786 to 644.

## Decisions that are not phases

Open operator decisions live in `docs/protocol.md` section 12 and block no phase: the FP8-against-INT8 quality tension, and `steps: 8` measured but not adopted. A second entry is scheduled: the base Z-Image variant will be downloaded later and will serve the higher-quality tier, with its own entry file and its own swap cost — the time to unload, load and warm again. Until its weights exist, one entry serves the system and no request selects a model.
