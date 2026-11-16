# Documentation truth pass and debt closeout

**Objective**: make every maintained document tell the truth about the system as it
stands, then close the debts the operator has ruled on.

**Problem**: the project holds a rule it does not obey — `AGENTS.md` says "Docs must
not lie. When a change alters what a document describes, update that document in the
same work unit." Six unit-closure commits (P8, P11, U1, U2) landed after the last
documentation sweep and left seven documents describing a state the system left
behind. Separately, three debts sit open against the operator's own rulings.

**Why**: a law that is not kept is not a law. Every stale number in `protocol.md`
is a claim the system cannot back, and a reader who checks one of them learns to
check none.

**Authorized scope**: `docs/`, `README.md`, `AGENTS.md`, `coltman_images/`, `bin/`,
`tests/`. No change to the model's behaviour, the surface, the entry's regime, or
the guard numbering.

**Constraints**:
- Canonical artifacts are written in English. `docs/reference/steps-fidelity.md`
  arrived in Spanish and must be translated, not paraphrased.
- One changelog entry per work unit.
- Conventional commits, no AI attribution, no co-author trailers.
- Every `[DEBT]` needs a roadmap contract: marker, reason, target spec, steps.
- A document that changes a fact changes it in the same work unit that changed the
  fact.

## Tasks

### T1 — Documentation truth pass
Seven documents describe a state the system left behind. Fix each against the
measured facts, and move the counts each document repeats into one place.

- [x] T1.1 `docs/context.md:47` — "No version control yet. The operator's decision
  is open, and nobody may run `git init` unilaterally." **False.** The repository
  exists: 18 commits on `master`, first commit `643fd71`, remote
  `git@github.com:juanvs23/coltman-images-service.git`. The debt closed on
  2026-11-15 and `docs/roadmap.md` says so. Remove the known issue.
- [x] T1.2 `docs/context.md:5` — "the twelve guards that prove them are
  executable". **Stale.** The count lives in `protocol.md` §10 and nowhere else
  (the README already says this). Fix the count at its source, not here.
- [x] T1.3 `docs/protocol.md:50` — `tests/` row says "thirteen tests, green in
  416 s". **Stale.** 15 test methods exist (guard 4 has two: `04` and `04b`).
  The count of *guards* is 15 declared, 13 reserved for the UI, 14 written.
  Record the count once, in §10.
- [x] T1.4 `docs/protocol.md:47` — `coltman_images/` row says "built through P6".
  **Stale.** P8, P11, U1 and U2 landed since.
- [x] T1.5 `docs/roadmap.md:5` — "Thirteen tests, all green in 416 s". **Stale**,
  same as T1.3.
- [x] T1.6 `docs/roadmap.md:89` — "Status: thirty-five of forty-five stills exist;
  the ladder was interrupted once by a GPU collision and resumes from its own
  timing cache". **Stale.** All 45 stills exist
  (`tests/e2e/steps-ladder/evidence/stills/`), `ssim.json` carries all 5 seeds ×
  8 pairs, and `timings.json` all 45 entries. The ladder is finished, not
  interrupted.
- [x] T1.7 `docs/changelog.md` — no entry for U2 (`aa9b2ba`, 10 files, 496
  insertions). AGENTS.md requires one entry per work unit. Add it.
- [x] T1.8 `docs/reference/README.md:3` — "These two files are the measurements".
  **Stale.** Three files are listed in the table below it. Fix the count.
- [x] T1.9 `README.md:156` — "fifteen of them" while the README also says the
  count lives in `protocol.md` §10 and nowhere else. Pick one: the count belongs
  in §10. Remove the number from the README.
- [x] T1.10 The count now lives in three places with three numbers
  (`protocol.md:50` "thirteen tests", `protocol.md:343` "Fifteen guards … the
  table carries the other fourteen", `README.md:156` "fifteen of them"). Make
  §10 the single source: 15 guards declared, 13 reserved for the UI, 14 written,
  15 test methods (guard 4 is written as two). Every other document names the
  guard without counting it.
- [x] T1.11 `docs/changelog.md:12` — the first commit is recorded as `552c9f3`.
  **False.** No such object exists in this repository. The first commit is
  `643fd71` ("chore(repo): start version control at the renamed home", 37 files).
  Fix the hash and the file count.
- [x] T1.12 `docs/changelog.md:12` — the first commit is recorded as "37 files,
  644 KB". The tree at `643fd71` is 37 files and 447,669 bytes (437 KiB). Fix.
- [x] T1.13 `docs/protocol.md:343` — §10 says "Fifteen guards … Guard 13 is
  reserved by the web UI (P9) and is not written yet; the table carries the other
  fourteen." The table carries 14 rows (1–12, 14, 15). Correct as it stands —
  verify and leave.
- [x] T1.14 `.atl/` is untracked and not in `.gitignore`. It is a tool cache
  (skill registry), not project content. Decide: ignore it or leave it untracked;
  do not commit it.
- [x] T1.15 `docs/reference/steps-fidelity.md` — an untracked Spanish report with
  three numerical errors. See T3.
- [x] T1.16 Run the full suite before and after; the count in `protocol.md` §10
  must match what `unittest discover` actually collects.

### T2 — Close the FP8-vs-INT8 question
The operator's ruling of 2026-11-15: the A/B was run, the INT8 model was
discarded, the question is closed. Every document must say that.

- [x] T2.1 `docs/protocol.md:396` (§11) — "FP8 is the production default and INT8
  the declared fallback … No INT8 weights remain on this machine since
  2026-11-15, so the fallback is a declared position and not an available build".
  **Stale in law.** INT8 is not a fallback any more; the operator discarded the
  model. The fallback concept is gone: there is one arm.
- [x] T2.2 `docs/protocol.md:405` (§12) — "FP8 is production and INT8 the declared
  fallback, by the operator's ruling of 2026-11-14 … changes nothing until the
  operator rules otherwise". The operator has now ruled otherwise. Remove the
  open decision.
- [x] T2.3 `docs/protocol.md:254` (§6.1) — "INT8 is the measured fallback (section
  11) and is not in the entry: promoting it is an operator ruling". A discarded
  arm is not a fallback to promote. Fix.
- [x] T2.4 `docs/roadmap.md:93` — "The second half of the original question —
  whether FP8 invents more than INT8 — is now **unmeasurable here**: the INT8
  weights were deleted". It is not unmeasurable; it is **decided**. The operator
  ran it and discarded the model. Fix.
- [x] T2.5 `docs/roadmap.md:122` — "Open operator decisions … the FP8-against-INT8
  quality tension, and `steps: 8` measured but not adopted." Both are closed.
  `steps: 8` was adopted by U2 (a request field, bounds 8..16). Fix.
- [x] T2.6 `docs/context.md:43` — records the 2026-11-14 ruling as live. Bring it
  forward to the operator's closing ruling; the A/B numbers stay, the "declared
  fallback" framing does not.
- [x] T2.7 `docs/context.md:31` — "the only INT8 Z-Image checkpoint on the
  machine … so that fallback is now a position and not an available build".
  Same fix: the fallback framing goes.
- [x] T2.8 The blind adjudication evidence in `docs/reference/zimage-fp8-vs-int8.md`
  stays as it is — it is evidence, and it is what the operator's ruling rests on.
  The *decision* moves; the measurement does not.

### T3 — The steps-fidelity report
The operator supplied `docs/reference/steps-fidelity.md` and asked that the steps
quality be treated as measured. The file has three numerical errors and one
wrong conclusion, all verifiable against
`tests/e2e/steps-ladder/evidence/{timings,ssim}.json`:

1. **SSIM for seed 505 at 20→24 is stated as 0.95776.** The measured value is
   **0.90267**. The number 0.95776 appears nowhere in the evidence. The report's
   central claim — that 505 is the most cohesive seed — does not survive: 505's
   *highest* SSIM anywhere in the ladder is 0.90949 (at 16→20), and the highest
   value in the whole matrix is seed 202's 0.93861 (20→24). By mean SSIM over all
   eight pairs, 505 is 0.86486 and 202 is 0.86468 — a difference of 0.0002, which
   is noise.
2. **"505 is the slowest at every step count" is false.** At 4, 6 and 8 steps the
   slowest is seed 404; at 10 steps it is 303. 505 only becomes slowest at 12
   steps and above. The correct statement is that the *spread* between seeds grows
   with the step count (0.73 s at 4 steps, 2.97 s at 24 steps) and that 505's
   excess over the mean of the other four grows from +0.14 s at 4 steps to +2.38 s
   at 24 steps.
3. **The conclusion inverts the measurement.** The report reads seed 505's higher
   SSIM as "the best option for maximum visual fidelity". SSIM measures how much
   two images differ, not whether either is correct — `docs/reference/steps-ladder.md`
   says exactly this ("SSIM measures how much the image changes, not whether it
   is better") and the ladder README repeats it. A high SSIM at 20→24 means the
   20-step and 24-step stills agree with each other, which for this model is the
   noise floor, not fidelity.

- [x] T3.1 Rewrite the report in English (canonical artifacts are English), with
  the measured numbers, in the register of the other `docs/reference/` files.
- [x] T3.2 State what it does and does not establish: per-seed timing variance
  and per-seed SSIM, and the divergence that grows with step count — and
  explicitly that none of it is a quality verdict.
- [x] T3.3 Register it in `docs/reference/README.md` and fix that file's stale
  count (T1.8).
- [x] T3.4 The open item it is offered against — "the eight-category error count
  has not been scored" (`docs/reference/steps-ladder.md:124-135`,
  `docs/protocol.md:406`) — is closed by the operator's ruling, not by this
  report: the operator's eye read in `steps-ladder.md` is the measurement. Say
  so where the report is cited, and do not claim the count exists.
- [x] T3.5 `docs/roadmap.md:81-93` (the "measurement that is not a guard"
  section) — the status line says 35 of 45 stills exist. Fix per T1.6, and close
  the scoring obligation with the operator's ruling.

### T4 — Debt closeout
Two debts remain open in `docs/roadmap.md`. Both have operator rulings.

- [x] T4.1 `[DEBT] no-idle-timeout` — **closed 2026-11-16.** The server
  never self-terminates. The debt's own target spec: an `--idle-timeout` option
  that releases the process and the port after a declared idle period; the boot
  cost is already measured (15.1 s, of which 11.0 s is the discarded warm-up), so
  declare the option against that number. This one needs implementation, not a
  document edit.
- [x] T4.2 `[DEBT] no-version-control` — closed 2026-11-15. Its contract still
  describes the debt as open in `docs/context.md` (T1.1). The roadmap entry itself
  is correct.
- [x] T4.3 The `[DEBT] no-idle-timeout` implementation: `--idle-timeout` on
  `start`, the server releasing itself after that idle period, the port freed,
  the state file removed, and the card released. Protocol §6 and §7 declare it,
  §5.4 maps its exit codes, and a guard proves it — the guard count in §10 grows
  accordingly, and the README's flag table gains the flag.
- [x] T4.4 The roadmap's debt schedule is rewritten so that every remaining entry
  has a contract with a marker, a reason, a target spec and steps.

## Acceptance criteria

- [x] Every claim in every maintained document is either true of the current
  tree, or is explicitly marked as a decision (§12) or as evidence
  (`docs/reference/`).
- [x] No document counts guards, tests or files except `protocol.md` §10, which
  is the single source and says so.
- [x] The FP8/INT8 question appears nowhere as open.
- [x] The steps-quality obligation appears nowhere as unscored.
- [x] `docs/reference/steps-fidelity.md` carries no number that the evidence
  contradicts.
- [x] `[DEBT] no-idle-timeout` is closed by an implemented, guarded option.
- [x] The suite is green, and the count in §10 is what the suite collects.
- [x] One changelog entry per work unit.

## Applicable checks

- `.venv/bin/python -m unittest discover -s tests -v` — the whole matrix
  (~7 minutes, needs the card).
- `git log --oneline` — the shape of the history.
- Every numeric claim in a document is checked against the file it cites.

## Route

| Task | Route | Trigger evidence |
| --- | --- | --- |
| T1, T2, T3 | delegated direct — one writer | 6+ non-trivial files touched; one writer, one work unit |
| T4.3 | delegated direct — one writer | 2+ non-trivial files (`server.py`, `bin/`, `protocol.md`, `README.md`, tests) |

## Progress

- 2026-11-16 — Feature document created. Baseline suite running against
  `643fd71`+HEAD before any edit: 15 tests collected, green.
- 2026-11-16 — `steps-fidelity.md` verified against the raw evidence: three
  numerical errors (see T3).
- 2026-11-16 — T1, T2 and T3 done. The seven stale documents are corrected
  against the measured facts, the guard count is declared once in
  `docs/protocol.md` §10 (15 guards declared, guard 13 reserved, 14 written,
  15 test methods), the FP8/INT8 question is closed everywhere as one arm, and
  `docs/reference/steps-fidelity.md` is rewritten in English with its three
  numbers fixed against `timings.json` and `ssim.json`. Verified: the suite is
  green — `Ran 15 tests in 486.121 s`, `OK` — and `git log --reverse` starts at
  `643fd71` with 37 files and 447,669 bytes. T4 is untouched.
- 2026-11-16 — Follow-up truth pass over `tests/`, where the same defect survived:
  `tests/e2e/p6-guards/README.md` is the suite's own README and no longer calls
  the matrix eleven guards — it now carries a row for every declared guard (12,
  13 reserved and not written, 14 and 15 written from the test bodies) and points
  at protocol section 10 for the count, and `tests/e2e/p5-cli-parity/README.md`
  points at the folder instead of naming a number. Verified by grep; the suite was
  not re-run.

- 2026-11-16 — T4.3 done, and the debt closed. The delegated writer died on a
  provider quota after finishing `WarmServer` (the idle logic, `_idle_expired`,
  `_await_shutdown`, the in-flight counter) but before wiring it: `_parse` had
  no flag, `_serve` never passed the period, and `bin/coltman-images` had zero
  occurrences of "idle". The orchestrator finished the wiring and wrote guard 16.
  **The end-to-end run found a defect the code review had not**: the idle clock
  started when a request was *accepted*, so a 45 s render consumed the whole
  16 s period and the server retired 0.05 s after the render instead of 16 s
  after it — the clock now starts when the server *becomes* idle. A second
  defect was found reading the diff: the in-flight counter was raised after the
  job reached the queue, so a worker that finished first would leave it stuck
  above zero and the period would never expire. Measured: the floor refuses at
  15.1 s with exit 2 and starts nothing; a 27.711 s render answers 200 against a
  16 s period; retirement lands 16.25 s after that render, leaving no port, no
  state file and no process. Guard 16 green alone in 95.527 s, and the whole
  matrix green — `Ran 16 tests in 546.863 s`, `OK`, after an independent verifier found ten defects, all fixed: `docs/context.md` still declared the debt open; guard 16's log assertion was cumulative against an append-only log and could not fail (it now baselines, and reports 1 declaration and 1 retirement for its own run); the e2e README cited guard 16's render as its own (it is 44.816 s, not 27.711 s); the changelog spliced two runs into one measurement; §5.4 generalised the refusal to every start option while `--port` refuses with 4; and five smaller honesty fixes.
