> **Superseded for execution by `odd/tasks/PLAN-next-cycle.md`.** This file is kept
> for its history: the T1–T10 table, the handoff state, and the design note on the
> superior file. The plan file is the one to follow.

# RESUME HERE — state at 2026-11-19

**Matrix: RED, 8 of 20 (was 15).** The fixture is already de-coupled; what blocks is
that `load_entry` validates asset existence, so `model/entries/zimage.yaml` is dead
and four `load_entry(ZIMAGE_ENTRY)` sites must move. Exact plan in "Handoff state"
below. Backup: `run/test_p6_guards.py.bak`.

Next three commands to run:
1. make the shared fixture work: `_start()` on klein, one 512x512 render, check
   `guard03.renders` is published (guard 15 cascades off it)
2. build `G04_ENTRY` (float8 census) and `G19_ENTRY` (no image capability) as
   synthetic fixtures, the way G15/G18/U1 already do
3. `.venv/bin/python -m unittest discover -s tests`

---

# Model decoupling and MOSS adoption

**Opened:** 2026-11-19
**Status:** in progress
**Owner:** orchestrator

## Objective

Restore the property the operator named — *add and discard models without much
procedure* — by removing the guard matrix's hard coupling to one model's numbers,
then adopt MOSS-Image as the production model alongside klein, and document the
whole thing so other projects can use this service as an image generator.

## Problem

`tests/test_p6_guards.py` pins one model in two places:

```python
PROTOCOL_CENSUS = {"float8": 239, "plain": 282, "other": 0, "total": 521}
ZIMAGE_ID = "z-image-turbo-fp8"
```

and `_start()` boots a shared server on `ZIMAGE_ID` for the twelve `ServiceCase`
guards. Deleting Z-Image's weights took the matrix from green to **12 failures
and 3 errors of 20** — verified 2026-11-19. Discarding any other model is free;
discarding the fixture costs test surgery. That is the friction to remove.

## Scope

In scope:
- `tests/test_p6_guards.py` — derive model-specific values from the served entry's
  own declaration instead of constants.
- A named `FIXTURE_ID` constant, documented, naming the one model the matrix
  measures.
- `coltman_images/entry.py` — only if a declaration the guards need is not exposed.
- `model/entries/moss.yaml`, `coltman_images/adapters/moss.py`, adapter registry.
- Model assets moved out of `run/` into `model/assets/moss/`.
- Licensed-only LoRA catalogue for MOSS.
- Documentation: model lifecycle, installed models and LoRAs, third-party use.

Out of scope:
- Re-downloading Z-Image. Its weights were locally quantised QUANTO INT8 and are
  **not restorable byte-for-byte** (`docs/reference/retired-models.md`).
- Any change to `docs/protocol.md`, which stays the single owner of the law.

## Constraints

- The test matrix is the contract. It may be **re-based**, never weakened: an
  assertion that stops checking something must be replaced by one that checks it
  for the model actually served.
- Every model-specific number that leaves the tests becomes a **documented
  measurement**, not a deleted claim.
- Conventional commits, no AI attribution, one changelog entry per work unit.
- Docs must not lie: any doc whose claims this work invalidates is updated in the
  same work unit.

## Tasks

| ID | Task | Route | Evidence |
|---|---|---|---|
| T1 | Inventory every model-specific constant and assertion in the guard suite | inline (already started) | grep output |
| T2 | Introduce `FIXTURE_ID` and derive census / ceiling / steps from the served entry | inline | matrix green |
| T3 | Re-record the guard baseline on the new fixture | inline | `tests/e2e/p6-guards/evidence/` |
| T4 | Restore the matrix to green (20/20) | inline | `unittest discover` |
| T5 | Write `model/entries/moss.yaml` | delegated writer | entry loads |
| T6 | Write `coltman_images/adapters/moss.py` + registry row | delegated writer | census + still |
| T7 | Move MOSS assets from `run/` to `model/assets/moss/` | inline | sizes verified |
| T8 | Licensed-only LoRA catalogue for MOSS | inline | budget check |
| T9 | `docs/reference/model-lifecycle.md` — add and discard a model | inline | doc |
| T10 | `docs/reference/generator-handbook.md` — models, LoRAs, third-party use | inline | doc |

## Acceptance criteria

- `python -m unittest discover -s tests` is green, and **discarding any model
  other than the fixture requires no test change** — proven by inspection of the
  remaining constants.
- MOSS serves a still through the service, not through a run/ script.
- A reader who has never seen this repo can add or discard a model from
  `docs/reference/model-lifecycle.md` alone.

## Checks

`\.venv/bin/python -m unittest discover -s tests` after each task that touches
code. No TDD mode is configured for this project; the guard matrix is the check.

## Progress log

- 2026-11-19 — opened; T1 in progress. Earlier the same day: Z-Image weights
  deleted, matrix red, `docs/reference/retired-models.md` corrected to say so.

## Handoff state — 2026-11-19 (T2 partial)

### What changed and works

`tests/test_p6_guards.py` no longer hard-codes a model. The fixture is derived:

```python
FIXTURE_ENTRY = ROOT / "model" / "entry.yaml"
_FIXTURE      = _load_fixture()
FIXTURE_ID            = _FIXTURE.id
FIXTURE_CENSUS        = dict(_FIXTURE.expected_census)
FIXTURE_STEPS         = {"min": _FIXTURE.steps_min, "max": _FIXTURE.steps_max}
FIXTURE_DEFAULT_STEPS = _FIXTURE.steps
```

`PROTOCOL_CENSUS`, `PROTOCOL_STEPS`, `PROTOCOL_DEFAULT_STEPS` and `ZIMAGE_ID` are
gone; guard 15's `G15_STEPS` is now the fixture entry's own range. **Matrix went
from 15 failures/errors to 8.**

### The blocker discovered

**`load_entry` validates asset existence** (`coltman_images/entry.py:787`,
`declared asset is missing`). So `model/entries/zimage.yaml` is **no longer
loadable**, and five sites still load it:

| Line (current) | Test | Needs |
|---|---|---|
| 861 | guard 4b — `float8 == 0` refusal | **synthetic entry** declaring `float8`/`plain`/`other`/`total` |
| 2375 | guard 15 — steps | `load_entry(FIXTURE_ENTRY)` |
| 2641 | guard 04 — census measured | `load_entry(FIXTURE_ENTRY)` |
| 3114 | guard 13 — UI reads the declaration | inspect; likely a synthetic entry or the fixture |
| 4491 | guard 19 — an entry declaring no references | **synthetic entry** with no `image` capability |

`G18_ENTRY` (`ROOT/"model"/"entry.yaml"`, id `flux2-klein-4b-gguf-q4`) proves klein
already works as a guard fixture, and the suite already builds synthetic entries
for guards 15/18/19/U1 — so the pattern exists, it just has to be applied.

### Remaining failures to re-diagnose after the five sites are fixed

`guard07_cli_api_parity`, `guard10_the_upscale_stage`, `guard16_idle_timeout`,
`guard13_ui_never_renders_outside_the_queue`. They may all be downstream of the
fixture move (sizes, steps, census shape); none has been diagnosed yet.

### Next actions, in order

1. Replace sites 2375 and 2641 with `load_entry(FIXTURE_ENTRY)`.
2. Build two synthetic entries — `G04_ENTRY` (float8-keyed census) and
   `G19_ENTRY` (no image capability) — in `run/p6/entries/`, written from the test
   like the existing G15/G18/U1 fixtures.
3. Inspect 3114 and route it to whichever of the two fits.
4. Re-run the matrix; diagnose the four remaining failures with the fixture on klein.
5. Only then delete `model/entries/zimage.yaml` and its RETIRED banner, and remove
   `ZIMAGE_ENTRY` from the test file entirely.
6. Re-record the baseline (`tests/e2e/p6-guards/evidence/`) on klein.

### Backup

`run/test_p6_guards.py.bak` — the file as it was before the constant refactor.

## Design note from the operator: one superior file

The operator asked for *"un archivo, todo el setting, un archivo superior que toma
los otros y pasa la información"* — one top-level file that composes the others.

Proposed shape, respecting "one rule, one owner":
- **`model/models.yaml`** — the roster: one row per model with `id`, `entry` path,
  and `role` (`production`, `draft`, `retired`). It owns **which models exist and
  what each is for**, and nothing else.
- Each `model/entries/<id>.yaml` stays the **single owner** of that model's own
  declaration (adapter, components, steps, limits, census, digests). The roster
  never copies a value out of an entry.
- `host.yaml` keeps owning the deployment's numbers (card, budget, offload).

Then pruning is **one row deleted**, adding is **one row added**, and the guard
matrix reads the roster instead of `model/entry.yaml` directly. That is the version
of "un archivo superior" that does not create a second source of truth.

## Update — after moving guard 15 and guard 04 to the fixture

Matrix still **8 of 20** (5 failures + 3 errors). guard04 moved from ERROR to FAIL.
Two facts discovered that change the order of work:

1. **guard 15 failed with a cascade, not with its own assertion:**
   `AssertionError: guard03.renders was never measured — the run did not reach it`.
   So guard 15 reads an observation that guard 3 is supposed to publish. **Fix
   guard 3's fixture before touching guard 15 again** — the steps test is downstream.
2. The failure set is dominated by **fixture-level** problems, not by the census
   constants: guard07, guard10, guard13, guard16 and guard04 all consume
   observations produced by the shared server. Work the shared fixture first
   (`_start()` on klein), confirm one happy-path render, then re-run.

**Revised order:** make `_start()` + one render green → then guard 3 → then the rest
→ then the synthetic entries for guard 4b and guard 19 → then delete
`model/entries/zimage.yaml`.
