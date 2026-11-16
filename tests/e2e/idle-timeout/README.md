# The idle timeout

The acceptance run for `start --idle-timeout`, the option that closes
`[DEBT] no-idle-timeout` (protocol sections 5.1, 5.4, 6 and 7; guard 16 in
section 10). It is an operator-level run against the real service on the real
card: the numbers below are what the installed system did.

- **Date:** 2026-11-16
- **Verdict:** pass, on every criterion below. The suite is green (16 test
  methods) and guard 16 repeats this run inside the matrix.

## What it proves

1. A period below the measured boot cost (15.1 s) is refused at the door, with
   exit 2, before any model work, and starts nothing.
2. A declared period is echoed by `start`, so the operator sees the deadline
   they just set.
3. A request that outlasts the declared period is served whole — 44.816 s of
   render against a 16 s period answered `200` with its still. Idle means no
   request in flight **and** none queued; the queue is empty during a render, so
   a period measured on the queue alone would cut it.
4. The server retires on its own once the period passes with nothing to do —
   and the period counts from the moment it *becomes* idle, not from the moment
   the request was accepted. Measured: render served at `08:17:27.269`, retired
   at `08:17:43.521`, **16.25 s later**.
5. The retirement goes through the path `stop` uses: the port stops answering,
   `run/server.json` is removed, and no server process remains.
6. The reason is in the server's own log, not inferred from silence.
7. A differing period on an already-running server is reported on stderr and
   ignored — the running server keeps the period it was started with, the same
   rule `--port` follows. `stop` afterwards is a no-op with exit 0.

## Commands, and what they answered

Every command ran from the project root.

**The refusal, below the floor:**

```sh
bin/coltman-images start --idle-timeout 5
```

exit 2, and the server's own log line says why:

```
idle timeout: 5.0 s is below the boot cost of 15.1 s — a server that idles for
less than it takes to start is worse than no server; nothing was loaded
```

No `run/server.json`, no process.

**A declared period, and a render that outlasts it:**

```sh
bin/coltman-images start --idle-timeout 16
bin/coltman-images generate --prompt "a brass compass on a wooden table" \
  --seed 7 --width 1280 --height 720 --out <evidence>/in-flight.png --json
```

`start` echoed `idle timeout 16 s`; the render answered `render_s: 44.82`,
`duration_s: 48.304` — 44.816 s of render and 3.2 s of load against a 16 s
period, served whole.

**The retirement, from the server's log:**

```
idle: declared 16.0 s — the server retires on its own when nothing is in flight
served: …/in-flight.png seed=7 render_s=44.82 load_s=3.20
idle: 16.0 s with no request in flight and none queued — retiring
stop: card released, state file removed, exiting
```

`run/server.json` gone, the port silent, no `coltman_images.server` process.

**A differing period, on the running server:**

```sh
bin/coltman-images start --idle-timeout 600
```

exit 0, with `--idle-timeout 600 ignored: the running server keeps the idle
period it was started with (stop it first to change it)` on stderr.

## The defect this run found

The first end-to-end run retired the server **0.05 s** after a 45 s render
finished, not 16 s after it: the idle clock was starting when a request was
*accepted*, so the render's own duration consumed the whole period. The clock
now starts when the server *becomes* idle. A second defect was found by
reading the code the same day: the in-flight counter was raised after the job
reached the queue, so a worker that finished it first would leave the counter
above zero and the period would never expire; it is now raised before the job
is queued. Both are in the same work unit — the run is what caught the first.

## How to regenerate

```sh
cd coltman-images-service
bin/coltman-images start --idle-timeout 16
bin/coltman-images generate --prompt "a brass compass on a wooden table" \
  --seed 7 --width 1280 --height 720 --out tests/e2e/idle-timeout/evidence/in-flight.png --json
# wait for the retirement, then
grep -E "idle: declared|served:|idle: .*retiring|stop: card released" run/server.log
```

The floor and the whole behaviour are also proved by guard 16:

```sh
.venv/bin/python -m unittest discover -s tests -v -k guard16
```

## What the run leaves behind

`evidence/` (gitignored, written by the commands above):

| File | What it is |
| --- | --- |
| `in-flight.png` | the still rendered while the 16 s period was already running |
| `render-in-flight.json` | that request's response, with its `render_s` and `duration_s` |
| `retired.log` | the log excerpt: declared, served, retiring, released |
| `render-in-flight.err` | the request's stderr — empty, because the run printed no diagnostics |

Nothing is written outside this folder and the project's own `run/` and `out/`.

## Inputs, by location

| Input | Where |
| --- | --- |
| The option, its default and its floor | `docs/protocol.md` sections 5.1, 6 and 7 |
| The exit code of a refusal | `docs/protocol.md` section 5.4 |
| The floor's number | `docs/protocol.md` section 6, measured as the boot cost |
| The implementation | `coltman_images/server.py` — `MIN_IDLE_TIMEOUT_S`, `_idle_expired`, `_await_shutdown`, `_finish` |
| The flag and its forwarding | `bin/coltman-images` — `start --idle-timeout` |
| The proof in the matrix | `tests/test_p6_guards.py` — `ServiceCase.test_0950_guard16_idle_timeout` |
