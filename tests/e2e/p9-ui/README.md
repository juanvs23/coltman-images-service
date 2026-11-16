# The web UI

The acceptance run for P9, `start --ui`: a page served by the server process,
rendering a still through the same queue the API uses. It is an operator-level
run against the real service on the real card, and the numbers below are what
the installed system did.

- **Date:** 2026-11-16
- **Verdict:** pass on every criterion that can be observed without a browser.
  Two things were not observed and are named below: no browser ever rendered this
  page, and the 50/50 layout is proved as a component tree rather than as pixels.
  The suite is green — `Ran 17 tests in 725.120 s`, `OK` — and guard 13
  repeats the structural, unit and single-flight halves inside the matrix.

## What it proves

1. **The page is served by the server process itself.** `start --ui` exited 0
   and echoed `ui http://127.0.0.1:7860` on its success line; `127.0.0.1:7860`
   answered `200 text/html; charset=utf-8`, 20,747 bytes, while
   `127.0.0.1:8420/health` answered `warm` on the same pid. Two ports, one
   process; the API keeps its stdlib server. The boot was `boot: warm in
   21.81 s` and the page was serving 0.27 s later (`boot.log`).
2. **The layout is two equal halves.** `tests/e2e/p9-ui/layout.py` builds the
   page in-process and records its tree (`layout-tree.json`): one `row` whose two
   children are `column` with **`scale=1`** each, the first holding
   `markdown, textbox, row(seed, size), slider, button` and the second holding
   `markdown (status), image, markdown (details)`. `equal_height` is off, so the
   halves size to their own content. What that artifact does not prove is how a
   browser paints them — see below.
3. **A still through the page is a still through the queue.** One SD submission
   at the slider's initial position took 49.15 s of status updates and produced
   `out/20261116T200244Z-7.png`: 1280×720, 848,663 bytes,
   `sha256 ff3b84a08e48e1b0c70bc96aa40c10936e782f183b6443ae1157e1c654dbe5c4`.
   That digest is this project's recorded 1280×720 baseline for the same prompt
   and seed — **the page produced the same bytes as the CLI and as a direct
   POST**, which is the strongest statement available that it added no second
   path to the model.
4. **The step control is the entry's ladder, and its default is an absence.**
   Two measurements, in that order:

   - At the API, `a lighthouse at dusk`, seed 7, 512×512 with **no `steps`
     field** and with `steps: 12` explicitly: both are
     `sha256 0065c34af014499e…`, the recorded baseline — so an explicit default
     changes nothing and the page is free to send the absence instead.
   - Through the page, the same request at the slider's initial position is
     `ff3b84a0…` (point 3). Moved to 16, the same page produced
     `786d8b5142995431…` with `render_s 60.488` against `45.201`, and its panel
     stated `steps 16` — the count the still was rendered with, from the
     response, not the slider's position.

   The panel for the default submission states `steps 12`, which is the entry's
   default: the page never sends 12, and the response supplies it.
5. **The screen states SD or HD, the base, the census and the three timings.**
   Verbatim from the page (`sd-steps12-transcript.json`,
   `hd-steps12-transcript.json`):

   ```
   **SD** — 1280x720, the native render; nothing was synthesized.
   `z-image-turbo-fp8` · seed 7 · steps 12
   census — float8 239 · plain 282 · other 0 · total 521
   render_s 45.201 · load_s 3.563 · duration_s 49.101
   ```

   ```
   **HD** — delivered 2560x1440, rendered 1280x720, enlarged x2 by `realesrgan-x2plus` in 5.055 s.
   `z-image-turbo-fp8` · seed 7 · steps 12
   census — float8 239 · plain 282 · other 0 · total 521
   render_s 45.956 · load_s 3.225 · duration_s 55.059
   ```

   The HD still is 2560×1440, 3,148,193 bytes,
   `sha256 28871f935ee8cd70…` — the same digest every run of this page has
   produced, so the whole path including the stage is deterministic. The census
   is rendered key by key from the response, and it is the render's, not the
   stage's. `render_s`, `load_s` and `duration_s` are three separate lines: the
   last is the only one that carries load and queue wait. The HD size is derived
   from the entry's ceiling and aspect, not from `defaults × 2`: 1280×720 is
   exactly this entry's ceiling, so only a derivation survives an entry whose
   defaults sit lower.
6. **The queue depth is on screen while it waits.** Two submissions fired at
   once through the page: the first rendered in 50.00 s and reported
   `queue depth 1` while the second sat behind it; the second waited and finished
   at 100.05 s, its status line naming `in flight — queue depth 1` for its whole
   wait. The page has no queue of its own: it reaches `submit()` immediately and
   waits where the depth is visible.
7. **Two concurrent submissions serialise.** Guard 13 fires both through the
   page's own client (gradio's, the endpoint the button calls), at 12 and 16
   steps, and measured a wall ratio of **2.300** (51.760 s against 119.055 s, separator
   1.5), with both showing their first status within **0.1 s** of the click — the
   guard allows 10 s, and a page that held a submission in front of the seam
   would need about fifty — and the queue never held more than one waiting
   request over 237 samples.
8. **The page shares the process's life.** `stop` exited 0; both ports then
   refused connections (`000` from `curl`), `run/server.json` was gone and no
   `coltman_images.server` process remained.
9. **A differing `--ui-port` on a running server is reported and ignored** —
   exit 0, with the reason on stderr, exactly as `--port` and `--idle-timeout`
   behave. `--ui-port` equal to `--port` is a different thing and is refused:
   exit 2, before the mutex, in 1.6 s — no boot, no weight.
10. **A server without `--ui` imports no gradio.** `import coltman_images.server`
    leaves `gradio` out of `sys.modules`, and the whole matrix — started without
    the flag — is green.
11. **`--ui` with gradio absent is exit 3 before any work.** Gradio is installed,
    so the absence was simulated by shadowing the module for one process; the
    server refused with the missing thing named and exited 3, with no state file
    written and no weight read.
12. **The page telephones nothing.** The server's own log for a `--ui` boot
    contains **no `https://` line at all**, while it does contain gradio's calls
    to its own port (`analytics-after.txt`, `boot.log`). Before the fix the same
    log carried `HEAD https://huggingface.co/api/telemetry/…` twice and
    `GET https://api.gradio.app/pkg-version` per mount;
    `analytics-before.log` is three of those lines, kept with their timestamps.
    Both settings are assigned by the server rather than inherited, and that was
    measured too: started with `GRADIO_ANALYTICS_ENABLED=True` and
    `GRADIO_TEMP_DIR` pointed elsewhere in the shell, the boot still wrote **0**
    `https://` lines and gradio's cache still landed in `run/ui/`
    (`analytics-override.txt`, `boot-shell-override.log`). Gradio's file cache —
    where it copies a still to serve it — lives under `run/ui/`, inside the tree,
    so the system still writes the stills it was asked for and its own `run/` and
    `out/`, and nothing else.

## What was not observed

I did not click in a browser, and neither of the two refinements was seen on a
screen. The page was driven through `gradio_client`, the module gradio ships,
which calls the same handler the button calls and returns the same three outputs
the page displays; guard 13's behavioural half uses the same route. What that
leaves unproven is everything only a browser does: the layout as painted, the
JavaScript, the slider's drag, the disabled-and-spinning button while a
submission runs, and the image in a viewport. The HTML is served and is in
`page.html`; it is a 21 KB shell, because the page is a JavaScript application,
and the 50/50 is evidenced as the component tree in `layout-tree.json`.

## Commands, and what they answered

Every command ran from the project root, with nothing else holding the card.

**The page, and the log it writes:**

```sh
BEFORE=$(wc -l < run/server.log)
bin/coltman-images start --ui
# coltman-images: started — pid 482033, port 8420, state warm, ui http://127.0.0.1:7860
tail -n +$((BEFORE+1)) run/server.log > evidence/boot.log
grep -c "https://" evidence/boot.log          # 0
grep -c "http://127.0.0.1:7860" evidence/boot.log   # 3, gradio calling itself
curl -s -o evidence/page.html -w '%{http_code} %{content_type} %{size_download}\n' http://127.0.0.1:7860/
# 200 text/html; charset=utf-8 20747
curl -s http://127.0.0.1:8420/health
# {"status": "warm", "model": "z-image-turbo-fp8", "census": {...}, "pid": 482033, "port": 8420, "queue": {"depth": 0}}
```

**The layout, as a component tree** (no server, no card):

```sh
.venv/bin/python tests/e2e/p9-ui/layout.py
# one row, two columns of scale=1; controls left, status/still/details right; layout: ok
```

**Still through the page: the default position, 16 steps, then HD** (the stills
are written by the server into `out/`, which is where the response says they
are):

```sh
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality SD
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --steps 16
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality HD
```

**The default is an absence, at the API:**

```sh
curl -s -X POST localhost:8420/generate -H 'Content-Type: application/json' \
  -d '{"prompt":"a lighthouse at dusk","seed":7,"width":512,"height":512,"out":"…/baseline-no-steps.png"}'
curl -s -X POST localhost:8420/generate -H 'Content-Type: application/json' \
  -d '{"prompt":"a lighthouse at dusk","seed":7,"width":512,"height":512,"steps":12,"out":"…/baseline-steps-12.png"}'
# both 512x512, 258,609 bytes, sha256 0065c34af014499e… — the recorded baseline
```

**Two submissions at once, to see the wait:**

```sh
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a brass compass on a wooden table" \
  --seed 21 --label queue-front &
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a brass compass on a wooden table" \
  --seed 22 --label queue-back &
wait
```

**A differing UI port on the running server:**

```sh
bin/coltman-images start --ui --ui-port 7861
# exit 0
# coltman-images: --ui (port 7861) ignored: the running server keeps the surface it
# was started with — its address is not in the state file or /health, so this command
# cannot compare; stop it first to change it
```

**A UI port equal to the API's, with nothing running:**

```sh
bin/coltman-images start --ui --ui-port 8420
# coltman-images: the server exited with code 2 before the port answered
# exit 2, 1.6 s, no boot
```

**The page goes down with the process:**

```sh
bin/coltman-images stop
# coltman-images: stopped
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7860/   # 000
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8420/health  # 000
```

`000` is curl's "no response": the connection is refused, not empty.

**`--ui` with gradio absent** (gradio is installed here, so it is shadowed for
one process — an honest simulation, not the real absence):

```sh
mkdir -p /tmp/opencode/nogradio
printf 'raise ImportError("simulated absent gradio")\n' > /tmp/opencode/nogradio/gradio.py
PYTHONPATH=/tmp/opencode/nogradio:. .venv/bin/python -m coltman_images.server --ui
# ERROR __main__: ui: --ui was asked for and gradio is not importable (ImportError: simulated
# absent gradio) — install it into the project's own interpreter with
# `.venv/bin/pip install gradio`; nothing was loaded
# exit 3, no run/server.json
```

## How to regenerate

```sh
cd coltman-images-service
BEFORE=$(wc -l < run/server.log)
bin/coltman-images start --ui
tail -n +$((BEFORE+1)) run/server.log > tests/e2e/p9-ui/evidence/boot.log
grep -c "https://" tests/e2e/p9-ui/evidence/boot.log       # must be 0
curl -s -o tests/e2e/p9-ui/evidence/page.html http://127.0.0.1:7860/
curl -s http://127.0.0.1:8420/health > tests/e2e/p9-ui/evidence/health.json
.venv/bin/python tests/e2e/p9-ui/layout.py
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality SD
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --steps 16
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality HD
bin/coltman-images stop
```

The halves of the proof are also inside the matrix, and guard 13 repeats the
structural scans, the switch and ladder mapping, the three failure sentences and
the serialisation with the page mounted — the last two through the page itself:

```sh
.venv/bin/python -m unittest discover -s tests -v -k guard13
```

`drive.py` and `layout.py` are the operator's hand, not the system: the first
needs a server started with `--ui`, the second needs neither, and both write only
into `evidence/`.

## What the run leaves behind

`evidence/` (gitignored, written by the commands above):

| File | What it is |
| --- | --- |
| `start.out`, `start.err` | `start --ui`'s success line, and an empty stderr |
| `boot.log` | the server's own log for that boot: `boot: warm in 21.81 s`, `ui: serving …`, and no `https://` line |
| `analytics-after.txt` | the two counts taken over `boot.log` — 0 external, 3 to its own port |
| `analytics-before.log` | three of the telemetry lines the pre-fix mounts wrote, with their timestamps |
| `analytics-override.txt`, `boot-shell-override.log` | the same boot with `GRADIO_ANALYTICS_ENABLED=True` and a foreign `GRADIO_TEMP_DIR` exported: 0 `https://` lines, cache still under `run/ui/` |
| `layout-tree.json` | the page's component tree: one row, two `scale=1` columns, and the slider's entry-derived bounds |
| `page.html`, `page.headers` | the page as served: 200, `text/html`, 20,747 bytes |
| `health.json` | `/health` while the page was up |
| `sd-steps12-transcript.json` | one SD submission at the slider's initial position: every status, then the panel |
| `sd-steps16-transcript.json` | the same request at 16 steps, same shape |
| `hd-steps12-transcript.json` | the HD submission, same shape |
| `queue-front-transcript.json`, `queue-back-transcript.json` | two submissions at once: the wait, the depth, the two durations |
| `baseline-no-steps.png`, `baseline-steps-12.png` | the 512×512 pair: identical bytes with the field absent and present |
| `ignore.out`, `ignore.err` | the ignored `--ui-port` 7861 |
| `stop.out`, `stop.err` | `stop`, and the empty stderr |

The page's own stills are not copied here: the server wrote them into `out/`,
where the response says they are, and gradio's serving cache lives under
`run/ui/`.

## Inputs, by location

| Input | Where |
| --- | --- |
| The flag, its two ports, the cache and the telemetry | `docs/protocol.md` sections 5.5, 6 and 7 |
| What the page may say, and what it may touch | `docs/protocol.md` section 5.5, and section 4.2 for the response fields |
| The step ladder's bounds and default | `model/entry.yaml` — `limits.steps`, `steps`; read by the page, never carried by it |
| The exit codes of a refusal | `docs/protocol.md` section 5.4 — 3 for a missing asset, 2 for a usage error |
| The implementation | `coltman_images/ui.py`; `WarmServer._start_ui` in `coltman_images/server.py` |
| The flag and its forwarding | `bin/coltman-images` — `start --ui [--ui-port N]` |
| The proof in the matrix | `tests/test_p6_guards.py` — `ServiceCase.test_0960_guard13_ui_never_renders_outside_the_queue` |
| The operator's hands | `tests/e2e/p9-ui/drive.py`, `tests/e2e/p9-ui/layout.py` |
