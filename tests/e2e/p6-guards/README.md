# The guard matrix

The executable form of `docs/protocol.md` section 10: one assertion per guard, each
aimed at the failure that guard exists to catch rather than at a proxy for it. The
table below names every guard the matrix declares; section 10 is where the count
is declared.

- **Date:** 2026-11-15
- **Command:** `.venv/bin/python -m unittest discover -s tests -v` (from the project root)
- **Result:** that run collected 12 test methods, `OK`, 406.6 s of test time / 407.5 s wall
- **Verdict:** the guards P6 closed on, all green, with one disclosed exemption (guard 8, below). The suite has grown since that run; `docs/protocol.md` section 10 is where the current count of guards lives.

The suite is `tests/test_p6_guards.py`. It is the whole matrix; nothing in it is a
script, and nothing outside it is required.

## What each guard asserts

| # | Test | Assertion | Costs |
| --- | --- | --- | --- |
| 1 | `ServiceCase.test_0700_guard01_request_validation` | An unknown field, a missing prompt, a width that is not a multiple of 16 and a relative `out` each answer `400 invalid_request`, and the served counter and the render-failure counter in the server's own log do not move. | 0 renders |
| 2 | `ServiceCase.test_0900_guard02_lifecycle` | `start` exits 0 and `/health` answers `warm` only after the warm-up; `generate` with no server exits 4 and starts nothing; a second `start` exits 0 with the same pid and one process; a differing `--port` is reported and ignored; `stop` exits 0, silences the port, removes `run/server.json` and leaves no process; a second `stop` exits 0 and changes nothing. | 0 renders |
| 3 | `ServiceCase.test_0100_guard03_the_warmup_is_real` | The first `render_s` after `start` is within 1.25× the median of the next three identical requests. | 4 renders |
| 4 | `ServiceCase.test_0800_guard04_census_measured` + `ContractCase.test_guard04b_…` | `/health` and the seven responses report `239 / 282 / 0 / 521`, equal to the entry's `expected_census`; `coltman_images.loader.assert_census` refuses a census with `float8 == 0`. | 0 renders |
| 5 | `ServiceCase.test_0200_guard05_determinism` | Four renders of one request and seed are byte-identical. | borrows guard 3's four stills |
| 6 | `ServiceCase.test_0300_guard06_default_folder` | `generate` with no `--out` prints an absolute path inside `out/`, matches `<UTC stamp>-<seed>.png`, and the file exists and is a non-empty PNG. | 1 render |
| 7 | `ServiceCase.test_0400_guard07_cli_api_parity` | The CLI still and a direct `POST /generate` for the same seed are equal by `cmp` (`sha256` and `filecmp.cmp(shallow=False)`). | borrows guard 6's still and guard 3's first |
| 8 | `ContractCase.test_guard08_no_import_or_path_outside_the_tree` | Every import resolves inside the project tree or to the interpreter's own stdlib; every absolute path literal resolves inside the tree, except the kernel interfaces named below. | 0.05 s |
| 9 | `ServiceCase.test_0500_guard09_single_flight` | Two concurrent requests both answer 200 and write their stills; their `duration_s` differ by at least 1.5×, and `/health` reports a queue depth of 1 while one waits. Both are the same server process. | 2 renders |
| 10 | `ServiceCase.test_0600_guard10_the_upscale_stage` | A size above the ceiling without `upscale: true` is refused naming the ceiling; a size beyond `max_pixels × scale²` is refused naming the stage's reach; with permission the response declares the stage, its base, its own cost and `to`, and the census stays the render's. A permitted request at the native size delivers `upscale: null`. | 1 render (+ 4.7 s stage) |
| 11 | `ContractCase.test_guard11_core_imports_nothing_from_the_model_stack` | In a fresh subprocess per module, `coltman_images.server`, `coltman_images.render` and `coltman_images.entry` are imported and `diffusers`, `transformers`, `safetensors`, `coltman_images.loader` and `coltman_images.fp8` are absent from `sys.modules`. | 2.6 s |
| 12 | `ServiceCase.test_0850_guard12_one_instance` | With `run/server.json` deleted, `start` exits 0, names the running server's pid and spawns nothing; a hand-launched `python -m coltman_images.server --port 8599` exits 4 naming the instance as the reason and leaves no process behind; the state file is put back from `/health` afterwards, because the server writes it only at boot. | 0 renders (the second server is refused before it loads a weight) |
| 13 | — | Reserved by the web UI (P9) and not written: the UI must never render outside the queue (`docs/protocol.md` section 10). | not written |
| 14 | `ContractCase.test_guard14_entry_neutrality` | A synthetic entry with components `thing_a` and `thing_b`, no transformer config and a census of `{parameters, tensors}` loads through `entry.py` and renders one still through a stub adapter, whose pixel and call sequence the guard reads rather than trusts; an AST scan of `coltman_images/entry.py` finds none of the five model names in code, while the same scan over the Z-Image adapter finds all five — so the scan is not vacuous — and the same scan over `render.py`, `server.py` and `adapter.py` finds none. | 1 stub render (256×256, no weights on the card) |
| 15 | `ServiceCase.test_0650_guard15_steps` | The entry's own default must lie inside `limits.steps` or the entry refuses to load, naming the range and its bounds; a step outside the range is refused before the adapter is built, so zero stub instances exist and no still is written; over HTTP the same out-of-range values answer `400 invalid_request` naming the field and the range and the worker counters do not move, while a request without `steps` reports the entry's default; and 8 and 12 steps at one seed produce different files, each identical across two runs. | 4 renders at 512×512 (two at 8 steps, two at 12) |

## The render budget

Eight stills, each with one owner, each borrowed only where the borrowing guard's
assertion is genuinely about that still. This is the budget of the run recorded
below; the matrix has grown since, and each row of the table above carries its own
guard's cost:

| Still | Owner | Borrowed by |
| --- | --- | --- |
| 4 × 1280×720, `a brass compass on a wooden table`, seed 4242 | guard 3 | guard 5 (bytes), guard 7 (one of them as the API half) |
| 1 × 1280×720 through the CLI, no `--out`, same prompt and seed | guard 6 | guard 7 (the CLI half) |
| 2 × 1280×720 concurrent, seeds 91 and 92 | guard 9 | guard 10 (`upscale: null` from the request that carried `upscale: true` at the native size) |
| 1 × 2560×1440, `upscale: true`, seed 4242 | guard 10 | — |

Guard 3 costs four because the protocol's threshold is stated over four renders;
guard 9 costs two because concurrency cannot be borrowed; guard 10 costs one base
render. The other seven guards of that run cost no GPU time at all.

## Measured, this run

| Measurement | Value |
| --- | --- |
| `start` → warm | 20.11 s |
| Guard 3: first / next three `render_s` | 43.483 / 43.819, 43.895, 43.946 s |
| Guard 3: median of the next three, ratio | 43.895 s, **0.991** (limit 1.25) |
| Guard 5: four stills | 1 096 139 bytes each, one `sha256` `d155082ca1887f6c…` |
| Guard 6: default-folder still | `out/20261115T223325Z-4242.png` |
| Guard 7: CLI against POST | identical, `d155082ca1887f6c…` |
| Guard 9: `duration_s` of the pair | 46.981 s and 93.868 s, ratio **1.998** |
| Guard 9: peak queue depth | 1 over 187 samples |
| Guard 10: stage | `realesrgan-x2plus` ×2, `[1280, 720]` → `[2560, 1440]`, `upscale_s` 4.623 |
| Guard 10: HD still | 4 608 989 bytes, 2560×1440 |
| Guard 4: census, seven responses and `/health` | `239 / 282 / 0 / 521` every time |
| Guard 8: sources / declarations / imports | 11 / 7 / 32, 0 outside, 1 kernel interface |
| Guard 11: forbidden modules | none, in all three subprocesses |
| Guard 2: `stop` | 0.79 s, exit 0, state removed, no process, port refused |
| Total | 12 tests, 406.6 s |

The same `sha256` was produced by two earlier runs of the same suite (411.3 s and
408.7 s), so the bytes are stable across separate server processes, not merely
across four renders in one.

## Two things the guards found, both disclosed rather than softened

**Guard 8 exempts the kernel's process table.** The literal reading of protocol
section 2 is "no runtime lookup may point outside its own tree", and
`bin/coltman-images:115` reads `/proc/<pid>/cmdline` to decide whether the pid in the state
file is its own server before it signals anything. `/proc` is the operating
system's process table, not another project's data store: it exists on every Linux
host, so it neither breaks independent runnability nor creates a dependency on
anything this project does not own. The guard classifies absolute literals as
inside / kernel / outside, fails on `outside`, and **prints every exempted
literal** so the exemption is visible in the transcript rather than implied. The
exempted roots are `/proc`, `/sys` and `/dev`; today only `/proc` is used. If the
operator wants section 2 read literally, the CLI would have to drop the pid
check — which is a change to the system, not to this guard.

**The server logs under `__main__`, not `coltman_images.server`.** The process is
launched with `python -m coltman_images.server`, so the module runs as a script and
`logging.getLogger(__name__)` gets `__main__`. Guard 1's counter reads the message
text (": served: ") rather than the logger name, so it does not depend on how the
process was started — but anyone reading `run/server.log` should know that the
server's own lines are attributed to `__main__`.

## What the run leaves behind

- `evidence/` (gitignored): `guards-<stamp>.json` and `latest.json` — every
  observation the run made, per guard — plus `files/` with the eight stills the
  byte comparisons used.
- One still in `out/`, written by guard 6 through the default folder. That file is
  the guard's own product; `out/` is gitignored.
- `run/server.log` grows by the run's lines. The run removes `run/server.json` and
  leaves no process and no listener: `tearDownModule` refuses to pass otherwise.

## How to regenerate

```sh
cd coltman-images-service
.venv/bin/python -m unittest discover -s tests -v
```

The suite owns the lifecycle, so it refuses to start if `run/server.json` exists, a
`coltman_images.server` process is alive, or `127.0.0.1:8420` answers. Stop it with
`bin/coltman-images stop` first. A single server is started once per run and stopped by
guard 2's own test; a failure anywhere else still stops it in `tearDownClass`.

How many guards a run collects is declared in `docs/protocol.md` section 10. This file
names them.

To run one guard, filter by name — `-k` still runs the class fixture:

```sh
.venv/bin/python -m unittest discover -s tests -v -k guard08
```

## Inputs, by location

| Input | Where |
| --- | --- |
| The specification | `docs/protocol.md` sections 4, 5, 6 and 10 |
| The entry (census, ceiling, defaults, request fields) | `model/entry.yaml`, read live by guards 4 and 8 |
| The stage declaration (id, scale) | `model/upscaler.yaml`, read live by guard 10 |
| The CLI | `bin/coltman-images`, executed as an operator would |
| The server's own log | `run/server.log`, the counter guards 1 and 3 use |
| The stills | `tests/e2e/p6-guards/evidence/files/`, plus the default folder |
