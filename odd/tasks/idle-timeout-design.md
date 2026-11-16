# Design contract — `--idle-timeout` (T4.3)

The contract for the writer that closes `[DEBT] no-idle-timeout`. It is written
here so the writer has one place to read, and so the orchestrator can review
against a spec rather than against prose.

This work unit runs AFTER the documentation truth pass (T1–T3) has landed and
been committed. It edits `docs/protocol.md` §10, which the truth pass also
edits — running them in parallel would collide.

## The debt, and what closing it means

From `docs/roadmap.md`:

> ### `[DEBT] no-idle-timeout`
>
> The server never self-terminates, so a forgotten server keeps a process and its
> port indefinitely — and, measured on 2026-11-15, about 165 MiB: 770 MiB with the
> server idle against 605 without it. It **does not** hold the card; the GPU is
> free between requests. Justified because auto-stop changes the meaning of
> "warm" and the cost of the next request.
>
> - Target spec: an `--idle-timeout` option that releases the process and the port
>   after a declared idle period. There is no GPU to release.
> - Steps: the boot cost is already measured — 15.1 s, of which 11.0 s is the
>   discarded warm-up — so declare the option against that number.

Three things the debt says, and what each becomes:

1. **"releases the process and the port"** — the server retires itself. Not the
   card (there is no card to release between requests), the process and the port.
2. **"after a declared idle period"** — the period is declared by the operator at
   `start` time, not inferred. Absent means never, which is today's behavior and
   stays the default.
3. **"declare the option against that number"** — the 15.1 s boot cost is the
   number the option is defined against, because a retired server's next request
   pays that boot again. It becomes both the floor and the stated trade-off.

## The option

| | |
| --- | --- |
| Flag | `--idle-timeout SECONDS` on `coltman-images start` |
| Default | none — the server never self-terminates (today's behavior) |
| Floor | the measured boot cost, 15.1 s — refused below it, exit 2 |
| Scope | `start` (protocol §7) |
| Effect | after that many seconds with no request in flight and none queued, the server drains, releases, removes its state file and exits |

### Why the floor is the boot cost

Below the boot cost, every cycle is dominated by booting: the server retires
before it has served a request since it started, so the next request pays the
15.1 s boot again (11.0 s of it a discarded warm-up). The option is therefore
refused below 15.1 s, at the door, with a message that names the number and the
reason. A refusal is exit 2 — the same code `argparse` uses for a usage error,
and the same code the law already maps an invalid request to (§5.4).

This is not a new exit code. It is §5.4's exit 2, reached from the CLI's usage
side rather than from an HTTP 400.

### What "idle" means, exactly

Idle is **no request in flight AND none queued**. Both conditions, always.

`self._queue.qsize()` alone is not enough: it counts jobs *waiting*, not the job
being rendered. A 46 s render leaves the queue empty while the card is busy, so
a timeout measured on queue depth alone would retire a server mid-render. The
implementation needs an explicit in-flight count.

Concretely, in `coltman_images/server.py`:

- An in-flight counter, incremented when a job is enqueued and decremented when
  the worker finishes it (success or failure — both paths).
- A last-activity timestamp, set when the port binds and refreshed when a
  request is accepted.
- The idle condition is: in-flight == 0, queue empty, and now − last activity >
  the declared timeout.

The check runs in the thread that already exists for shutdown
(`_watch_shutdown`). Today it does
`self._shutdown_requested.wait()` — an unbounded wait. Change it to a bounded
wait (`wait(timeout=…)`) in a loop, and check the idle condition on each tick.
**Do not add a second thread**: the shutdown watcher already owns "the server is
retiring", and the idle timer is one more reason for it to wake.

### The retirement path

The idle timeout must retire the server through the *same* path `POST /shutdown`
uses. Not a parallel implementation. When the condition is met, the timer calls
the existing `request_shutdown()`, which sets `_stopping`, wakes the watcher, and
the watcher drains the queue, releases the card, removes `run/server.json` and
exits 0. The idle timer adds a decision; it does not add a retirement path.

The one thing it must add is a log line that says *why* the server retired, so
the proof is readable in `run/server.log` rather than inferred. Something in the
register of the existing `stop: card released, state file removed, exiting`.

### Exit code of the retired server

0. A declared timeout that fires is the declared behavior working, not a
failure. The operator's next `stop` finds no state file and says "not running"
(exit 0) — the existing path, unchanged.

## Where the flag travels

`bin/coltman-images start` spawns the server as
`python -m coltman_images.server --port N`. It must forward the timeout:
`--idle-timeout N`. `coltman_images/server.py`'s `_parse` gains the argument.

`start` echoes the declared timeout in its success line, so an operator can see
the deadline they just set.

### When a server is already running

`start` is idempotent: the running server wins, and a differing `--port` is
reported on stderr and ignored (protocol §6). `--idle-timeout` behaves the same
way: a differing timeout on an already-running server is reported and ignored.
The running server keeps the timeout it was started with — changing it would
mean restarting the server, which is exactly what the operator did not ask for.

## The guard

The project holds its proofs in the matrix (`docs/protocol.md` §10). This
behavior gets one, and it is **guard 16** — guard 13 stays reserved for the web
UI (P9), and 14 and 15 are taken.

### The test's position in the suite

The matrix's `ServiceCase` starts one server for the whole class in
`setUpClass`, and guard 2 (`test_0900_guard02_lifecycle`) stops it. The mutex in
`run/server.lock` means **one server per card** — guard 12 proves it — so a
second server cannot start while the first holds the lock.

The idle-timeout guard therefore runs *after* guard 2 has stopped the shared
server. Name it `test_0950_guard16_idle_timeout`; `unittest` sorts test methods
alphabetically within the class, and `"0950"` sorts after `"0900"`. That
ordering is load-bearing: before guard 2 runs, the shared server is still up and
the mutex would refuse the second one.

### What the guard proves

1. `start --idle-timeout N` succeeds, and the server is warm and answering.
2. With no request in flight, the server retires by itself within a bounded
   time.
3. After it retires: the port no longer answers, `run/server.json` is gone, and
   no server process remains.
4. The server's own log records that it retired on the idle timeout — the
   reason is in the evidence, not inferred from the silence.
5. `stop` afterwards is a no-op with exit 0 ("not running"), and `generate` with
   no server is exit 4 — the ordinary paths, still true afterwards.

### The floor

The guard also proves the refusal: `start --idle-timeout 5` (below the 15.1 s
floor) exits 2, says why, and starts nothing — no process, no state file.

### Cost

The guard's server boots (~18 s) and then idles for its timeout before it
retires. With the floor at 15.1 s, use a timeout just above it and the guard
costs roughly 35 s. The suite is ~416 s today; it grows to roughly 7.5 minutes.
That is acceptable, and the writer must report the suite's real duration.

## The evidence run

Rule 11: integration/E2E evidence lives inside the repository, under
`tests/e2e/<name>/`, with a committed `README.md` and a gitignored `evidence/`
subfolder. The other vocabulary in this project is `evidence/` (gitignored) plus
a committed `README.md`; `tests/e2e/p6-guards/README.md` is the closest
precedent for a suite-level run, and `tests/e2e/u2-steps/README.md` for a
unit-sized one.

Create `tests/e2e/idle-timeout/` with a committed `README.md` describing what
the run proves, the exact commands, the observed results and how to regenerate
it, and a gitignored `evidence/` folder holding the run products (the server
log excerpt, the health body before the retirement, the exit codes).

Follow the README structure the existing folders use: what it proves / date /
verdict / commands and what they answered / how to regenerate / what the run
leaves behind / inputs by location.

## The law

`docs/protocol.md`, amended in this same work unit:

- **§5.1 CLI surface** — the `start` line gains `--idle-timeout N`.
- **§5.4 exit codes** — note that a refused `--idle-timeout` is exit 2, from the
  usage side.
- **§6 the lifecycle** — declare the option: what idle means (no request in
  flight, none queued), what it releases (the process and the port; there is no
  GPU to release between requests), that it retires through the same path
  `stop` uses, and the trade against the 15.1 s boot cost.
- **§7 defaults and named options** — a row: idle timeout, default none, scope
  `start`.
- **§10 the test matrix** — guard 16's row, and the counts: 16 guards declared,
  13 reserved for the UI, 15 written, 16 test methods (guard 4 is written as
  two). The counts live here and nowhere else.

`README.md` — the flags table gains `--idle-timeout`, and the "what it costs"
table gains the boot cost it trades against (15.1 s, of which 11.0 s is the
discarded warm-up) if it is not already there.

`docs/roadmap.md` — the debt entry is closed in the form the two closed debts
use: what was deferred, why it was justified, the target spec, the steps, and
then how it was closed (the option, the guard, the evidence run, the observed
numbers).

`docs/changelog.md` — one entry for this work unit, in the house style: a
dense paragraph with the measured numbers and the consequence.

## What this work unit must not do

- Do not change the default. Absent `--idle-timeout`, the server still never
  self-terminates. This is an opt-in.
- Do not add a second retirement path. The idle timer calls
  `request_shutdown()`; it does not implement its own teardown.
- Do not add a thread. The shutdown watcher wakes on a bounded wait and checks
  the condition.
- Do not touch the render path, the entry, the surface, or the request
  vocabulary. Nothing about a request changes.
- Do not renumber the existing guards, and do not use 13.
- Do not push, open a PR, or touch the remote. The orchestrator handles
  delivery.
