# The web UI

The acceptance run for P9, `start --ui`: a page served by the server process,
rendering a still through the same queue the API uses — now with the operator's
five shapes. It is an operator-level run against the real service on the real
card, and the numbers below are what the installed system did.

- **Date:** 2026-11-16
- **Verdict:** pass on every criterion that can be observed without a browser.
  Two things were not observed and are named below: no browser ever rendered this
  page, and the 50/50 layout is proved as a component tree rather than as pixels.
  The suite is green — `Ran 17 tests in 677.008 s`, `OK` — and guard 13
  repeats the structural, unit and single-flight halves inside the matrix.

## What it proves

1. **The page is served by the server process itself.** `start --ui` exited 0
   and echoed `ui http://127.0.0.1:7860` on its success line; `127.0.0.1:7860`
   answered `200 text/html; charset=utf-8`, 22,179 bytes, while
   `127.0.0.1:8420/health` answered `warm` on the same pid. Two ports, one
   process; the API keeps its stdlib server. `boot: warm in 21.80 s`, and the
   page was serving 0.30 s later (`boot.log`).
2. **The layout is two equal halves.** `tests/e2e/p9-ui/layout.py` records the
   page's tree (`layout-tree.json`): one `row` whose two children are `column`
   with **`scale=1`** each, the controls in the first (`markdown, textbox,
   row(seed, size), form(slider), form(radio) …`) and `markdown (status), image,
   markdown (details)` in the second; `equal_height` is off. The same artifact
   records the controls' configuration: the steps slider at the entry's
   `8..16` defaulting to `12`, and the aspect radio offering exactly
   `16:9, 1:1, 4:3, 3:4, 9:16` with `16:9` selected.
3. **The page explains itself.** Each control carries one line under it — the
   prompt, the seed, the size switch, the aspect and the slider — and a collapsed
   guide titled **"what each control does"** sits at the foot of the form. The
   *served* page carries it, not just the source: `GET /config` from the running
   page returns the accordion `('what each control does', False)`, five `info`
   lines, and guide text containing the interpolated ladder (`8 to 16, defaulting
   to 12`) and the ten boxes (`served-config.json`, `served-config.txt`). Every
   number in that copy is computed at build time; the module's literal set is
   unchanged at `[0, 0.5, 1, 2, 16, 256, 320, 540]`.
4. **Every size is computed, and none is carried.** Guard 13 asserts all ten
   from the entry's ceiling and the stage's factor, as properties and as exact
   numbers. Against the operator's table, **six match and four differ**, and the
   four are larger:

   | Shape | SD computed | SD in the table | HD computed | HD in the table |
   | --- | --- | --- | --- | --- |
   | `16:9` | 1280×720 (921,600 px) | same | 2560×1440 (3,686,400) | same |
   | `1:1` | 960×960 (921,600) | same | 1920×1920 (3,686,400) | same |
   | `4:3` | **1088×816 (887,808)** | 1024×768 (786,432) | **2176×1632 (3,551,232)** | 2048×1536 (3,145,728) |
   | `3:4` | **816×1088 (887,808)** | 768×1024 (786,432) | **1632×2176 (3,551,232)** | 1536×2048 (3,145,728) |
   | `9:16` | 720×1280 (921,600) | same | 1440×2560 (3,686,400) | same |

   At `4:3` the box is `1088×816`, not `1024×768`: 1088 and 816 are both
   multiples of 16, their ratio is exactly 4:3, and 887,808 px is 96.3 % of the
   ceiling where 1024×768 uses 85.3 %. The next step up, `1152×864`, is 995,328
   and overshoots by 73,728 — so the algorithm stops at 1088×816 and does not
   force the area. The table's two 4:3/3:4 rows are legal boxes but not the
   largest, which is the rule the request states; if the operator wants the
   smaller boxes, that is a different rule and a second ruling.
5. **The baseline did not move.** `16:9` at SD is `1280×720` on this entry — the
   box its own defaults declare — and `POST /generate` at 512×512 for
   `a lighthouse at dusk`, seed 7 still answers
   `sha256 0065c34af014499e6c959ca60d59f681647595538c7edf6f832136a29f6d7a72`,
   258,609 bytes (`baseline-no-steps.png`). The page's 16:9 SD still is
   `sha256 ff3b84a08e48e1b0…`, 848,663 bytes, the project's own 1280×720 baseline
   — so adding a control changed neither number.
6. **The two shapes that are not the entry's own, through the page.** `1:1` at SD
   delivered **960×960**, 857,457 bytes, `sha256 40e21a01c7e66e01…` in 51.42 s of
   status updates (`render_s 45.246`, `load_s 5.700`, `duration_s 51.351`); `1:1`
   at HD delivered **1920×1920 from a 960×960 render**, 3,184,668 bytes,
   `sha256 df11752ec1741b97…`, stage 3.428 s, in 89.15 s — of which
   `load_s 39.886` is a page-cache eviction of the checkpoint, not the stage.
7. **The screen states SD or HD, the base, the census and the three timings.**
   Verbatim from the page (`sd-16-9-steps12-transcript.json`,
   `1-1-hd-transcript.json`):

   ```
   **SD** — 1280x720, the native render; nothing was synthesized.
   `z-image-turbo-fp8` · seed 7 · steps 12
   census — float8 239 · plain 282 · other 0 · total 521
   render_s 45.347 · load_s 3.639 · duration_s 49.323
   ```

   ```
   **HD** — delivered 1920x1920, rendered 960x960, enlarged x2 by `realesrgan-x2plus` in 3.428 s.
   `z-image-turbo-fp8` · seed 7 · steps 12
   census — float8 239 · plain 282 · other 0 · total 521
   render_s 44.898 · load_s 39.886 · duration_s 89.099
   ```

   The census is rendered key by key from the response, and it is the render's,
   not the stage's. `render_s`, `load_s` and `duration_s` are three separate
   lines: the last is the only one that carries load and queue wait.
8. **The step control is the entry's ladder, and its default is an absence.**
   At the slider's initial position the request carries no `steps` at all and the
   panel states `steps 12` (the entry's default, from the response); moved to 16,
   the same page produced `786d8b5142995431…` with `render_s 60.249` against
   `45.347` and its panel stated `steps 16`. At the API, the same request with no
   `steps` field and with `steps: 12` explicitly is the same 512×512 bytes.
9. **The queue depth is on screen while it waits.** Two submissions fired at once
   through the page rendered in 49.40 s and 98.80 s, the second naming
   `in flight — queue depth 1` while it waited. The page has no queue of its own:
   it reaches `submit()` immediately and waits where the depth is visible.
10. **Two concurrent submissions serialise.** Guard 13 fires both through the
   page's own client (gradio's, the endpoint the button calls) — `16:9` at the
   entry's steps and `1:1` at its ceiling — and measured a wall ratio of
   **2.311** (48.894 s against 113.018 s, separator 1.5), both showing their first status
   within **0.1 s** of the click (the guard allows 10 s), and the queue never held
   more than one waiting request over 225 samples.
11. **The page shares the process's life.** `stop` exited 0; both ports then
    refused connections (`000` from `curl`), `run/server.json` was gone and no
    `coltman_images.server` process remained.
12. **A differing `--ui-port` on a running server is reported and ignored** —
    exit 0, with the reason on stderr. `--ui-port` equal to `--port` is refused:
    exit 2, before the mutex, in 1.6 s — no boot, no weight.
13. **A server without `--ui` imports no gradio**, and the whole matrix — started
    without the flag — is green.
14. **`--ui` with gradio absent is exit 3 before any work** (simulated by
    shadowing the module for one process: the server named what was missing, wrote
    no state file, read no weight).
15. **The page telephones nothing.** A `--ui` boot's own log contains **no
    `https://` line at all** while it does contain gradio's calls to its own port
    (`analytics-after.txt`, `boot.log`). `analytics-before.log` keeps three of the
    telemetry lines the pre-fix mounts wrote; `analytics-override.txt` and
    `boot-shell-override.log` show the same boot with `GRADIO_ANALYTICS_ENABLED=True`
    and a foreign `GRADIO_TEMP_DIR` exported — still 0 external lines, cache still
    under `run/ui/`.

## What was not observed

I did not click in a browser. The page was driven through `gradio_client`, which
calls the same handler the button calls and returns the same three outputs the
page displays; guard 13's behavioural half uses the same route. What that leaves
unproven is everything only a browser does: the layout as painted, the
JavaScript, dragging the slider, the aspect radio's look, the
disabled-and-spinning button while a submission runs, and the image in a viewport.
The HTML is served and is in `page.html`; it is a 22 KB shell, and the 50/50 is
evidenced as a component tree in `layout-tree.json`.

## Commands, and what they answered

Every command ran from the project root, with nothing else holding the card.

**The page, and the log it writes:**

```sh
BEFORE=$(wc -l < run/server.log)
bin/coltman-images start --ui
# coltman-images: started — pid 525769, port 8420, state warm, ui http://127.0.0.1:7860
tail -n +$((BEFORE+1)) run/server.log > evidence/boot.log
grep -c "https://" evidence/boot.log          # 0
grep -c "http://127.0.0.1:7860" evidence/boot.log   # 3, gradio calling itself
curl -s -o evidence/page.html -w '%{http_code} %{content_type} %{size_download}\n' http://127.0.0.1:7860/
# 200 text/html; charset=utf-8 22179
```

**The layout and the controls, as a component tree** (no server, no card):

```sh
.venv/bin/python tests/e2e/p9-ui/layout.py
# one row, two columns of scale=1; the aspect radio offers the operator's five; layout: ok
```

**The shape that is not the entry's own, both halves** — the cheap pair:

```sh
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --aspect "1:1" --label 1-1-sd
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --aspect "1:1" --quality HD --label 1-1-hd
```

**The entry's own shape, for contrast** (16:9 at SD, 16 steps, HD):

```sh
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality SD
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --steps 16
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality HD
```

**The baseline, at the API** (512×512, no `steps` field):

```sh
curl -s -X POST localhost:8420/generate -H 'Content-Type: application/json' \
  -d '{"prompt":"a lighthouse at dusk","seed":7,"width":512,"height":512,"out":"…/baseline-no-steps.png"}'
# 512x512, 258,609 bytes, sha256 0065c34af014499e… — unchanged by the new control
```

**Two submissions at once, to see the wait:**

```sh
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a brass compass on a wooden table" --seed 21 --label queue-front &
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a brass compass on a wooden table" --seed 22 --label queue-back &
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
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --aspect "1:1" --label 1-1-sd
.venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --aspect "1:1" --quality HD --label 1-1-hd
bin/coltman-images stop
```

The halves of the proof are also inside the matrix, and guard 13 repeats the
structural scans, the ten sizes, the three failure sentences and the
serialisation with the page mounted — the last through the page itself:

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
| `boot.log` | the server's own log for that boot: `boot: warm in 21.80 s`, `ui: serving …`, and no `https://` line |
| `analytics-after.txt` | the two counts taken over `boot.log` — 0 external, 3 to its own port |
| `analytics-before.log` | three of the telemetry lines the pre-fix mounts wrote, with their timestamps |
| `analytics-override.txt`, `boot-shell-override.log` | the same boot with `GRADIO_ANALYTICS_ENABLED=True` and a foreign `GRADIO_TEMP_DIR` exported: 0 `https://` lines, cache still under `run/ui/` |
| `layout-tree.json` | the page's component tree: one row, two `scale=1` columns, the steps slider's entry-derived range, the aspect radio's five in order, the guide's title and closed state, and every control's `info` line |
| `served-config.json`, `served-config.txt` | what the running page sends a browser: the accordion closed, five info lines, and guide text with the computed ladder and boxes |
| `page.html`, `page.headers` | the page as served: 200, `text/html`, 22,179 bytes |
| `health.json` | `/health` while the page was up |
| `sd-16-9-steps12-transcript.json` | the entry's own shape at the slider's initial position: every status, then the panel |
| `sd-16-9-steps16-transcript.json` | the same request at 16 steps |
| `hd-16-9-steps12-transcript.json` | the entry's shape at HD |
| `1-1-sd-transcript.json`, `1-1-hd-transcript.json` | the square, both halves: 960×960 and 1920×1920 from 960×960 |
| `queue-front-transcript.json`, `queue-back-transcript.json` | two submissions at once: the wait, the depth, the two durations |
| `baseline-no-steps.png` | the 512×512 baseline: `0065c34a…`, unchanged by the new control |
| `ignore.out`, `ignore.err` | the ignored `--ui-port` 7861 |
| `stop.out`, `stop.err` | `stop`, and the empty stderr |

The page's own stills are not copied here: the server wrote them into `out/`,
where the response says they are, and gradio's serving cache lives under
`run/ui/`.

## Inputs, by location

| Input | Where |
| --- | --- |
| The flag, its two ports, the cache and the telemetry | `docs/protocol.md` sections 5.5, 6 and 7 |
| The shapes, the forms and what the page may touch | `docs/protocol.md` section 5.5, and section 4.2 for the response fields |
| The size rule and the stage's reach | `docs/protocol.md` sections 4.1 and 6.2; the numbers are `model/entry.yaml` and `model/upscaler.yaml` |
| The step ladder's bounds and default | `model/entry.yaml` — `limits.steps`, `steps`; read by the page, never carried by it |
| The exit codes of a refusal | `docs/protocol.md` section 5.4 — 3 for a missing asset, 2 for a usage error |
| The implementation | `coltman_images/ui.py` — `size_for`, `request_from_form`; `WarmServer._start_ui` in `coltman_images/server.py` |
| The flag and its forwarding | `bin/coltman-images` — `start --ui [--ui-port N]` |
| The proof in the matrix | `tests/test_p6_guards.py` — `ServiceCase.test_0960_guard13_ui_never_renders_outside_the_queue` |
| The operator's hands | `tests/e2e/p9-ui/drive.py`, `tests/e2e/p9-ui/layout.py` |
