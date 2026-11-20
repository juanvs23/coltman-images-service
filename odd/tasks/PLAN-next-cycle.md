# Plan — unblock the guard matrix, adopt MOSS, and make models cheap to add or drop

**Written:** 2026-11-19
**Supersedes:** the scattered handoff in `odd/tasks/model-decoupling-and-moss-adoption.md`
(kept for its history; this file is the executable plan)
**Owner:** next session

---

## 1. Where we are, in six facts

1. **The model decision is closed.** MOSS-Image DMD int8 is production; FLUX.2 [klein]
   4B is the draft/fast pass; Z-Image is retired.
2. **Z-Image's weights are gone and are not restorable byte-for-byte.** They were
   locally produced QUANTO INT8 artefacts; the repo has no quantisation script and no
   fp16 sources. Recorded in `docs/reference/retired-models.md`.
3. **The guard matrix is red: 8 of 20** (5 failures, 3 errors). It was green before the
   deletion; the deletion took it to 15.
4. **The fixture is already de-coupled.** `tests/test_p6_guards.py` no longer contains
   `PROTOCOL_CENSUS`, `PROTOCOL_STEPS`, `PROTOCOL_DEFAULT_STEPS` or `ZIMAGE_ID`. It
   derives `FIXTURE_ID`, `FIXTURE_CENSUS`, `FIXTURE_STEPS` and `FIXTURE_DEFAULT_STEPS`
   from `model/entry.yaml`.
5. **The blocker:** `load_entry` **validates that declared assets exist**
   (`coltman_images/entry.py:787`, `declared asset is missing`). So
   `model/entries/zimage.yaml` can no longer be loaded by anything, and three test
   sites still read it.
6. **The trap:** leaf guards cascade. `guard 15` fails with
   `guard03.renders was never measured — the run did not reach it`, which is not its
   own failure. Diagnosing leaves while the shared fixture is unproven points at the
   wrong file.

### Current failure set (verified 2026-11-19)

| Test | Kind | Believed cause |
|---|---|---|
| `guard04b_assert_census` | ERROR | loads `zimage.yaml` (line ~861) |
| `guard19_image_input` | ERROR | loads `zimage.yaml` (line ~4491) |
| `guard15_steps` | ERROR | cascade off `guard03.renders` |
| `guard04_census_measured` | FAIL | shared-fixture observation shape |
| `guard07_cli_api_parity` | FAIL | shared-fixture |
| `guard10_the_upscale_stage` | FAIL | shared-fixture |
| `guard13_ui_never_renders` | FAIL | reads `zimage.yaml` declaration (line ~3114) |
| `guard16_idle_timeout` | FAIL | shared-fixture |

**None of the four "shared-fixture" failures has been diagnosed.** They are grouped by
the observation they consume, not by a proven cause.

---

## 2. Rule for the whole plan

> The matrix may be **re-based**, never weakened. An assertion that stops checking
> something is replaced by one that checks it for the model actually served, or by a
> **synthetic entry** that isolates the property without depending on any real model.

Backup before any editing pass: `run/test_p6_guards.py.bak` (the pre-refactor file).

---

## 3. Phases

### Phase 0 — prove the shared fixture (do this first)

**Goal:** one boot and one render through the guard fixture, on klein.

1. Confirm the server boots on the promoted entry:
   ```sh
   ./bin/coltman-images start && ./bin/coltman-images stop
   ```
   Expect `boot: entry flux2-klein-4b-gguf-q4`, `warm`, and a discarded 512×512 warmup.
2. Run the two guards that own the fixture and the first render:
   ```sh
   .venv/bin/python -m unittest tests.test_p6_guards.ServiceCase.test_0900_guard02_lifecycle
   .venv/bin/python -m unittest tests.test_p6_guards.ServiceCase.test_0100_guard03_the_warmup_is_real
   ```
3. Inspect `tests/e2e/p6-guards/evidence/guards-*.json` and confirm
   `guard03.renders` is present. **If it is absent, stop and fix guard 3** — every leaf
   guard below depends on it.

**Acceptance:** guard 2 and guard 3 green, `guard03.renders` present in the evidence.

### Phase 1 — diagnose the four shared-fixture failures

**Goal:** know the cause of each, not guess it.

```sh
for t in test_0400_guard07_cli_api_parity test_0600_guard10_the_upscale_stage \
         test_0800_guard04_census_measured test_0950_guard16_idle_timeout; do
  .venv/bin/python -m unittest "tests.test_p6_guards.ServiceCase.$t" 2>&1 | tail -20
done
```

For each, record in this file: the assertion, the observed value, the expected value,
and whether the difference is (a) a klein-vs-Z-Image measurement difference, which is
legitimate and gets re-based, or (b) a real defect, which gets a fix.

**Watch for the census shape:** klein censuses `artifacts`/`bytes`; Z-Image censused
`float8`/`plain`/`other`/`total`. Any assertion that reasons about `float8` is
Z-Image-shaped and belongs in a synthetic entry (Phase 2), not in the fixture guards.

**Acceptance:** four rows in this file with cause and disposition.

### Phase 2 — synthetic entries, and remove `zimage.yaml`

**Goal:** no test depends on a model that is not installed.

The suite already builds its own entries for guards 15, 18, 19 and U1; copy that
pattern.

1. **`G04_ENTRY`** — a minimal entry whose `expected_census` has
   `float8`/`plain`/`other`/`total`, written under `run/p6/entries/`. Guard 4b uses it
   instead of `zimage.yaml`. The property being tested is `assert_census` refusing
   `float8 == 0`; it does not need a real model.
2. **`G19_ENTRY`** — a minimal entry that declares **no** `image` capability. Guard 19
   uses it for "an entry with no references refuses one". klein declares `image: max 10`,
   so it cannot serve this test.
3. **guard 13, site ~3114** — it reads `zimage.yaml` as a declaration template. Point it
   at `FIXTURE_ENTRY` if it only needs a valid declaration; otherwise at `G04_ENTRY`.
4. Delete `model/entries/zimage.yaml` and drop `ZIMAGE_ENTRY` from the test file.
5. Update `docs/reference/retired-models.md`: the entry is gone, so "restore" now means
   *re-author the entry from the recipe* rather than *remove the banner*.

**Acceptance:** `grep -n ZIMAGE tests/test_p6_guards.py` returns nothing; no file under
`model/entries/` is unloadable.

### Phase 3 — green, then re-record the baseline

```sh
.venv/bin/python -m unittest discover -s tests
```

Re-record `tests/e2e/p6-guards/evidence/` on klein and note in the evidence README that
the measured entry changed and why. **Do not** edit an assertion merely to make it pass:
each re-based assertion gets a one-line comment naming the entry it now measures.

**Acceptance:** 20/20 green, and `git log` shows the re-base as its own commit.

### Phase 4 — adopt MOSS as a first-class model

**Goal:** MOSS serves a still **through the service**, not through a `run/` script.

| Piece | File | Notes |
|---|---|---|
| Entry | `model/entries/moss.yaml` | adapter `moss`; checkpoint = DMD int8 DiT; components vae/llm/tokenizer; `steps: 8`, `limits.steps {min:4, max:16}`; `guidance: 3.0`; `expected_census` measured from the files |
| Adapter | `coltman_images/adapters/moss.py` | subprocess like `flux2klein_sd.py`; `--diffusion-model`, `--llm`, `--vae`, `--tokenizer`, `--lora-model-dir`; dimensions multiple of 16 |
| Registry | `coltman_images/adapter.py` | one row: `"moss": "coltman_images.adapters.moss:MossAdapter"` |
| Assets | `model/assets/moss/` | move from `run/p10-stage2/moss-image/`: DiT 5.413.723.302 B, encoder 5.680.522.464 B, VAE 336.211.292 B, tokenizer 19.989.325 B |
| LoRA catalogue | `model/assets/loras/moss-dmd-int8/` | **Apache 2.0 only**: Impressionism, NextScene, the three `deadman44` styles (verify subject first), the seven `thedeoxen` controls, plus the turbo and anime already verified |
| Budget | `host.yaml` | MOSS peak measured 6.394 MiB at 1024² with CFG 3,0 and 6.686 with the turbo LoRA; check `lora_budget_mib` against the card |

Measured facts to carry into the entry's comments: 12 steps at CFG 3,0 = 52,2 s and
6.394 MiB; 8 steps with the turbo LoRA at CFG 1,0 = 40,4 s and 6.686 MiB; 65 images per
15-minute video.

**Acceptance:** `coltman-images start --model moss-... ` then `generate` produces a
still; the guard census matches the entry's `expected_census`.

### Phase 5 — the superior file (the operator's request)

**Goal:** one place that composes the others, without duplicating a single value.

`model/models.yaml`:

```yaml
# The roster. This file owns WHICH models exist and WHAT EACH IS FOR.
# It copies no value out of an entry: the entry stays the single owner of its own
# declaration, and host.yaml stays the owner of the deployment's numbers.
models:
  - id: flux2-klein-4b-gguf-q4
    entry: model/entry.yaml
    role: draft
  - id: moss-dmd-int8
    entry: model/entries/moss.yaml
    role: production
```

Rules:
- `role` is one of `production`, `draft`, `retired`.
- A `retired` row keeps the entry path even when the entry no longer exists, and says
  where the restore recipe lives — that is how the door stays open.
- The guard matrix reads the roster's `production` entry as its fixture, falling back to
  `model/entry.yaml`. **Promoting a model then becomes one line, not a test change.**
- `models.yaml` is scanned by the same guard that reads declaration documents, so it must
  contain no path outside the tree.

**Acceptance:** adding a model is one row plus its entry; discarding is one row change;
`grep -c "z-image-turbo-fp8" model/models.yaml` returns 1 (the retired row).

### Phase 6 — documentation for third parties

| Document | Contents |
|---|---|
| `docs/reference/model-lifecycle.md` | add a model, promote it, retire it, restore it; the roster; what a retirement may and may not delete; **the incident of 2026-11-19 as the cautionary case** |
| `docs/reference/generator-handbook.md` | the two models and their roles; every installed LoRA with licence and status; the two configurations (quality: CFG 3,0 without LoRA; speed: turbo at CFG 1,0); the measured cost per image and per 15-minute video; API/CLI surface; how another project points at this service |
| `README.md` | a three-line pointer to the handbook |

**Acceptance:** a reader who has never seen this repo can add or discard a model, and
serve a still from another project, using those two documents alone.

---

## 4. Risks, with the mitigation that applies

| Risk | Mitigation |
|---|---|
| Editing leaf guards while the fixture is broken produces wrong diagnoses | Phase 0 is a hard gate |
| Re-basing turns into weakening | Every re-based assertion gets a comment naming the entry it measures; synthetic entries isolate properties instead of deleting them |
| Deleting an asset a test needs — **the 2026-11-19 incident** | Before deleting any weight, tokenizer or config: `grep -rn "<filename>" tests/` **and** read the suite's fixture (`_start()`), not only its declaration lists |
| MOSS adoption breaks the matrix again | Adopt MOSS **after** the matrix is green, in its own commit, and re-run before touching `models.yaml` |
| Hires LoRA is wanted but unlicensed | Ask `comfyanonymous` for a licence; keep it out of the catalogue until granted |

---

## 5. What was learned today, in the order it cost us

1. **Do not decide on a proxy.** Judged quality from the full image → wrong; from
   Laplacian variance → rewards grain; from an assumed 8 fps → wrong by 30×; from a
   README → wrong about the 4-step adapter.
2. **Do not delete without reading the consumers.** "No other model uses it" is not
   "nothing uses it". The test suite is a consumer, and its fixture is the first thing
   to read.
3. **A red matrix is a defect, not a state.** Report it, never paper over it.

---

## 6. Commands cheat-sheet

```sh
# matrix
.venv/bin/python -m unittest discover -s tests
# one guard
.venv/bin/python -m unittest tests.test_p6_guards.ServiceCase.test_0100_guard03_the_warmup_is_real
# service
./bin/coltman-images start --model <id> | stop
./bin/coltman-images generate --prompt "…" --seed 7 --width 1024 --height 1024 --json
# revert the test refactor
cp run/test_p6_guards.py.bak tests/test_p6_guards.py
```

---

## 7. Phase 0 result — 2026-11-19, executed

**The shared fixture is proven on klein.** Boot logs and one render:

```
boot: entry flux2-klein-4b-gguf-q4 — 8 steps, guidance 1.0, ceiling 1327104 px
warmup: 512x512 rendered in 7.82 s … census {"artifacts": 3, "bytes": 5269713294}
boot: warm in 9.44 s
```

**guard 3 passes on klein** — `first 15.803 s; next three 16.000, 18.121, 16.357;
median 16.357 s; ratio 0.966 (limit 1.25)`. The warm-up is a real warm-up.

**Guard 2's failure in a two-test subset is an artifact, not a defect:** it reads
`guard06.path`, published by guard 6, which the subset did not run. Subsets are only
valid for guards that do not consume another guard's observation.

### The remaining blocker, narrowed

Full matrix after Phase 0: **still 8 of 20** (5 failures + 3 errors). guard 15 keeps
failing with `guard03.renders was never measured` **even though guard 3 passes and
publishes it**:

- published at `tests/test_p6_guards.py:1998` — `_put("guard03.renders", renders)`
- read at `tests/test_p6_guards.py:2470` — `self.obs("guard03.renders")[0]["body"]`
- `_put`/`obs` share a module-level `OBS` dict (line 242), so this is not per-test state.

So the cascade is **not** a missing `_put`: guard 3 either skips the publish on a branch
in the full run, or guard 15 executes before guard 3. **First thing next session:**

```sh
grep -n "def test_0100_guard03" -A 5 tests/test_p6_guards.py   # any early return before 1998?
grep -n "class ServiceCase" -A 3 tests/test_p6_guards.py        # confirm both live there
.venv/bin/python -m unittest discover -s tests -v 2>&1 | grep -n "test_0" | head -25
```

The last command prints the real execution order, which settles it in one look.

### What is NOT the problem, so nobody re-chases it

- The fixture constants: already de-coupled and working.
- klein's ability to boot and render: proven above.
- `load_entry` and the missing Z-Image assets: affects only guard 4b and guard 19, which
  are the two synthetic-entry tasks in Phase 2.

---

## 8. Phase 1 result — 2026-11-19, executed (matrix 15 → 6)

### Fixed and green

| Guard | Cause | Fix applied |
|---|---|---|
| `guard03_warmup` | — | passes on klein: ratio 0.966 (limit 1.25) |
| `guard15_steps` | `by_steps[8]` / `by_steps[12]` hard-coded; klein's range is 4..8 → `KeyError: 12` | derives `low_steps, high_steps = G15_STEPS[0], G15_STEPS[-1]` |
| `guard04_census` | cascade off `guard10` | gone once guard 10 is fixed |
| `guard10` (first failure) | refusal asserted to name `921600`, Z-Image's ceiling | `MAX_PIXELS = _FIXTURE.max_pixels` instead of the literal |

**Ordering is not the cascade cause.** The execution order was printed with
`TestLoader`, and guard 3 runs first. guard 15's earlier cascade came from running it
*alone*, without guard 3. Subsets are only valid for guards that do not consume another
guard's observation.

### Remaining: 6 (4 failures + 2 errors), each with a named cause

| Test | Message | Cause | Disposition |
|---|---|---|---|
| `guard04b_assert_census` | ERROR, `declared asset is missing` | loads `zimage.yaml` | **synthetic `G04_ENTRY`** with float8-keyed census (Phase 2) |
| `guard19_image_input` | ERROR | loads `zimage.yaml` | **synthetic `G19_ENTRY`** with no `image` capability (Phase 2) |
| `guard07_cli_api_parity` | two sha256 differ | CLI and API renders of the "same" request differ | **diagnose first** — may be a real defect: compare the two payloads field by field before assuming a re-base |
| `guard10_the_upscale_stage` | `[1536, 864] != [1280, 720]` | the expected upscale target is tied to the old 1280x720 ceiling | derive the expected target from `MAX_PIXELS` and the source aspect |
| `guard16_idle_timeout` | `11.032 not greater than 16.0` | klein renders a 720p still in ~11 s, so the render no longer outlasts the 16 s idle period and the guard proves nothing | make the guard's render longer than the period (max size, max steps) **or** lower the declared period — keep the property "no idle stop mid-render"; do not simply drop the assertion |
| `guard13_ui_never_renders` | `'**SD** — 960x960' not found in ''` | the page panel returned nothing; geometry and entry declaration changed | inspect `ui_module`'s panel for the served entry before re-basing |

### The pattern worth naming

Every remaining failure is a **Z-Image measurement embedded as an expectation**: a
ceiling, a 720p geometry, a 16-second idle premise, a panel string. None is a defect in
the system. That is exactly the coupling this task exists to remove — and it is why
`MAX_PIXELS` moving made one guard fail *differently* rather than pass.

---

## 9. Phase 2 result — 2026-11-19 (matrix 6 → 4, zero errors)

**20 tests, 16 pass, 4 fail, 0 errors.** Both synthetic entries landed and both guards
they were built for are green:

| Guard | Now | How |
|---|---|---|
| `guard04b_assert_census` | **green** | `_g04_entry()` — a synthetic entry declaring `float8/plain/other/total`; the float8 property no longer depends on any installed model |
| `guard19_image_input` | **green** | `_g19_entry("g19-no-image.yaml", image_block=False, image_field=False)` — the entry with no reference block is synthesised, not borrowed |

Also renamed a leftover `zimage_refusal` → `no_image_refusal` in the evidence dict.

**`model/entries/zimage.yaml` is NOT deleted yet:** guard 13 still reads it as a
declaration (`tests/test_p6_guards.py:3152`). Keep `ZIMAGE_ENTRY` until that site moves.

### The four that remain — each with its fix

| Guard | Message | Fix |
|---|---|---|
| `guard07_cli_api_parity` | two sha256 differ between the CLI and the API for the same request | **diagnose first.** Compare the two payloads field by field; if they are identical, this is a real determinism defect in the runtime, not a re-base |
| `guard10_the_upscale_stage` | `[1536, 864] != [1280, 720]` | the expected target is derived from the old 720p ceiling; compute it from `MAX_PIXELS` and the source aspect |
| `guard16_idle_timeout` | `11.032 not greater than 16.0` | klein renders 720p in 11 s, so the render no longer outlasts the 16 s period and the guard proves nothing: lengthen the render (max size, max steps) or lower the declared period, **keeping** the property |
| `guard13_ui_never_renders` | `'**SD** — 960x960' not found in ''` | move line 3152 to `FIXTURE_ENTRY`, then re-derive the panel's expected size from the fixture's defaults (klein is 1152×1152, so 960×960 is a Z-Image shape) |

### Honest read of the state

The system is **not** broken: every remaining failure is a measurement of the retired
model written as an expectation. The matrix is doing its job — it is telling us exactly
where the coupling still lives.

---

## 10. guard 7 solved — it was never a determinism defect (2026-11-19)

**Cause:** the two renders were not the same request. Guard 6 ran
`generate --prompt … --seed …` with **no geometry**, so it inherited the entry's
defaults (klein: 1152×1152); guard 3 POSTs an explicit `1280×720`. Under Z-Image the
defaults *were* 1280×720, so the byte compare passed by coincidence.

**Fix, in the request and not in the assertion:** guard 6 now passes
`--width 1280 --height 720`, so the CLI renders the same box the API asks for.

**Evidence:** `guard 7: cli 65c72ce29ed1bc23… against post 65c72ce29ed1bc23… → identical=True`

This is worth remembering: the guard did its job. It caught that two code paths were
not being asked the same question — under the old model the coincidence hid it.

### Remaining: 3 (guard 10, guard 16, guard 13)

| Guard | Message | Next action |
|---|---|---|
| `guard10_the_upscale_stage` | `[1536, 864] != [1280, 720]` | find where the expected target is computed; the actual comes from a 768×432 source doubled, so the source box in this guard is not `WIDTH×HEIGHT` |
| `guard16_idle_timeout` | `11.032 not greater than 16.0` | lengthen the guard's render (max size and steps for the fixture) **or** lower the declared period; keep the property |
| `guard13_ui_never_renders` | `'**SD** — 960x960' not found in ''` | move line 3152 to `FIXTURE_ENTRY`, then re-derive the panel's expected size from the fixture defaults; 960×960 is a Z-Image shape |

**Matrix: 17 of 20 green, 3 failures, zero errors** (measured after the guard 7 fix;
the last full run before it was 16/20).

---

## 11. Phase 2 closed — 18 of 20 (2026-11-19)

**guard 10 solved.** The server clamps the upscale source to the entry's ceiling, so with
klein a 16:9 request starts from **1536×864 = 1 327 104 px exactly**; Z-Image's ceiling
*was* 1280×720, which is why the literal passed before. The assertion now computes the
expected box from `MAX_PIXELS` and the target's aspect (`math.gcd`, then the largest `k`
that fits) instead of naming it.

```
guard 10: stage {'model': 'realesrgan-x2plus', 'scale': 2,
                 'from': [1536, 864], 'to': [2560, 1440], 'upscale_s': 6.536}
```

### Two left

| Guard | Why it still fails | Fix |
|---|---|---|
| `guard16_idle_timeout` | declares a 16 s period and needs a render that **outlasts** it; klein renders 720p in 11,03 s, so the guard proves nothing | ask for the **ceiling box (1152×1152) with `upscale: true`**: ~13,4 s + ~6,5 s ≈ 20 s > 16. **Do not lower the period** — below the boot cost the guard's own `start` is refused, which is a different assertion |
| `guard13_ui_never_renders` | the page panel returns `''` and the guard still reads `zimage.yaml` at line 3152 | move that read to `FIXTURE_ENTRY`, then derive the panel's expected size from the fixture's defaults; 960×960 is a Z-Image shape |

### Matrix: 18/20 green, 0 errors

From **15 broken** at the start of the day. Nothing in the system changed behaviour:
each step removed an expectation that named the retired model's measurements.

---

## 12. guard 13 — three quarters closed, one assertion left (2026-11-19)

Done: the panel works again (it returned `''`), the declaration is read from
`FIXTURE_ENTRY`, and the five shape boxes are **derived** by `_ui_boxes(ceiling, factor)`.

**The rule, validated by prediction rather than by trial:** native side `k` is the largest
integer whose product fits the ceiling with both sides a multiple of 16
(`k = isqrt(ceiling // (aw*ah))`, then step down). The **upscaled** box comes from
`ceiling * factor²`, not from doubling the native one.

- It reproduces Z-Image's recorded table exactly: 1280×720, 960×960, 1088×816,
  816×1088, 720×1280 at 921 600 px.
- It predicts klein's failing values before they were run: 16:9 native `(1536, 864)` and
  upscaled `(3072, 1728)` — which is exactly what the guard had already reported.

### The one assertion left

```
AssertionError: Tuples differ: (1536, 864) != (1152, 1152)
```

The default box. Under Z-Image the entry's defaults were **1280×720**, which happened to
equal the 16:9 shape box, so the coincidence hid the coupling. klein's defaults are
**1152×1152** (1:1) and match no shape box.

**Fix:** derive the expected default from `declaration["defaults"]` — the entry's own
declared box — instead of comparing it to a shape box. Same rule as everywhere else in
this task: read the declaration, never remember the measurement.

### guard 16 — unchanged, still the one described in §11

Ask for the ceiling box with `upscale: true` (~13,4 s + ~6,5 s ≈ 20 s) so the render
outlasts the 16 s period. Do not lower the period: below the boot cost the guard's own
`start` is refused, which is a different assertion.

---

## 13. GREEN — 20 of 20, and the dead entry is gone (2026-11-19)

```
Ran 20 tests in 444.558s
OK
```

Verified **after** `model/entries/zimage.yaml` was deleted and the `ZIMAGE_ENTRY`
constant removed from the suite. From **15 broken** at the start of the day.

### Every coupling removed, in the order it was found

| Coupling | Replacement |
|---|---|
| `PROTOCOL_CENSUS` (239/282/521) | `FIXTURE_CENSUS` from the entry's `expected_census` |
| `PROTOCOL_STEPS` (8..16) / `PROTOCOL_DEFAULT_STEPS` (12) | `FIXTURE_STEPS` / `FIXTURE_DEFAULT_STEPS` from `limits.steps` |
| `ZIMAGE_ID` | `FIXTURE_ID` from the promoted entry |
| `G15_STEPS = (8,8,12,12)` | derived from the fixture's range |
| `by_steps[8]` / `by_steps[12]` | the two ends of `G15_STEPS` |
| `MAX_PIXELS = 921600` | `_FIXTURE.max_pixels` |
| upscale source `[WIDTH, HEIGHT]` | largest aspect box that fits the ceiling |
| five shape boxes (1280×720, 960×960, 1088×816, …) | `_ui_boxes(ceiling, factor)` |
| "16:9 is the entry's default" | whichever shape matches `defaults` |
| guard 6 rendering at the entry default | guard 6 states the same geometry guard 3 asks for |
| guard 4b / guard 19 loading `zimage.yaml` | `_g04_entry()` / `_g19_entry(no image)` |

**Not one assertion was weakened.** Each was replaced by a derivation from the served
entry's declaration, or by a synthetic entry that isolates the property. The two guards
that test model-shaped ideas (a `float8` census, an entry with no reference block) now
build their own fixtures and therefore survive any model changing.

### What this bought

Discarding a model is now **free** unless it is the fixture, and promoting a different
entry moves the whole matrix with it — which is the property the operator asked for.

### Still open

Phase 4 (adopt MOSS: entry, adapter, 11 GB of assets, Apache-2.0 catalogue), Phase 5
(`model/models.yaml` roster), Phase 6 (lifecycle and handbook). Nothing is committed yet.

---

## 14. Phases 4, 5 and 6 — exact specification (assets already moved)

**Done:** the four MOSS components now live in `model/assets/moss/` and the ten adapters
in `model/assets/loras/moss-dmd-int8/`. `model/assets` is 21 GB. Nothing else changed;
the matrix is still 20/20.

### Phase 4 — adopt MOSS

**`model/entries/moss.yaml`** (paths relative to the project root, as the loader wants):

```yaml
id: moss-dmd-int8
adapter: moss
checkpoint: model/assets/moss/moss_image_sft_8stepdmd_int8_convrot.safetensors

components:
  vae: model/assets/moss/flux2-vae.safetensors
  llm: model/assets/moss/Qwen3.5-9B-Q4_K_M.gguf
  tokenizer: model/assets/moss/tokenizer.json
  cli: vendor/stable-diffusion.cpp/build/bin/sd-cli

# Measured 2026-11-19 at 1024x1024, seed 7, offload: 12 steps CFG 3.0 = 52.2 s and
# 6.394 MiB; 4 steps = 34.3 s; 8 steps with the 12-step turbo LoRA at CFG 1.0 = 40.4 s
# and 6.686 MiB. The DMD distill is native at 8 steps; 4 steps is the cheap end.
steps: 8
guidance: 3.0

limits:
  max_pixels: 1048576      # 1024x1024, the box every measurement was taken at
  steps: {min: 4, max: 16}

request_fields: [prompt, seed, width, height, out, steps]

expected_census: {artifacts: 4, bytes: 11445310383}   # DiT + encoder + VAE + tokenizer

defaults: {width: 1024, height: 1024, format: png}
warmup: {width: 512, height: 512, prompt: "warm up", seed: 0}
```

**`coltman_images/adapters/moss.py`** — subprocess, modelled on `flux2klein_sd.py`:
`prepare` takes `run/server.lock` exactly as the klein adapter does; `census` counts the
four artefacts and their bytes; `encode` carries the prompt and the `<lora:NAME:WEIGHT>`
tags; `denoise` builds

```
sd-cli --diffusion-model <checkpoint> --vae … --llm … --tokenizer …
       --lora-model-dir model/assets/loras/moss-dmd-int8
       -p "<prompt> <lora:…>" -n "<negative>" --cfg-scale 3.0 --steps N
       -W W -H H -s SEED -o OUT --offload-to-cpu --lora-apply-mode at_runtime
```

**Width and height must be multiples of 16** — refuse at the door with both numbers rather
than letting the runtime round. `guidance: 3.0` is the quality configuration; CFG 1.0 is
only valid with the turbo LoRA, so the adapter must refuse a request that asks for both a
LoRA-free render and CFG 1.0, or document that `guidance` is per-entry.

**`coltman_images/adapter.py`** — add the registry row
`"moss": "coltman_images.adapters.moss:MossAdapter"`.

**Catalogue** — declare only Apache 2.0 adapters in the entry's `loras` block:
`lineart`, `scribble`, `canny`, `normal`, `depth`, `segmentation`, `pose` (thedeoxen),
`impressionism`, `nextscene`, plus the verified `anime` and `12-step-turbo`. **Excluded
until licensing is resolved:** `blue-archive-style` (no license), `char_*` (copyrighted
characters), `moss_alpha_v1` (needs the 4-channel VAE the runtime refuses), `epyan_4step`
(needs its own sampler).

**`host.yaml`** — the measured peaks are 6.394 MiB without a LoRA and 6.686 with one, and
one LoRA costs +588 MiB. `lora_budget_mib: 3200` does **not** fit on paper; either declare
a smaller budget for MOSS or record that under offload the LoRA lives in RAM.

### Phase 5 — `model/models.yaml`

```yaml
# The roster. Owns WHICH models exist and WHAT EACH IS FOR. Copies no value out of an
# entry: each entry stays the single owner of its own declaration, and host.yaml stays
# the owner of the deployment's numbers. A retired row keeps its entry path even when
# the entry is gone, and says where the restore recipe lives.
models:
  - id: flux2-klein-4b-gguf-q4
    entry: model/entry.yaml
    role: draft
  - id: moss-dmd-int8
    entry: model/entries/moss.yaml
    role: production
  - id: z-image-turbo-fp8
    entry: model/entries/zimage.yaml
    role: retired
    restore: docs/reference/retired-models.md
```

Rules: `role` ∈ {production, draft, retired}; the guard matrix takes the **production**
entry as its fixture, falling back to `model/entry.yaml`; the file is scanned by the
declaration guard, so it may name no path outside the tree. **Then promoting a model is
one line and pruning is one line.**

### Phase 6 — documentation

**`docs/reference/model-lifecycle.md`** — add / promote / retire / restore, the roster,
what a retirement may and may not delete (weights yes; entry, adapter, configs and the
restore recipe no), and the 2026-11-19 incident as the cautionary case with the rule it
produced: *before deleting any weight, tokenizer or config, grep the test suite AND read
its fixture.*

**`docs/reference/generator-handbook.md`** — the two models and their roles; every
installed LoRA with licence and status; the two configurations (quality: CFG 3.0 without
a LoRA; speed: the turbo at CFG 1.0); the measured cost per image and per 15-minute
video (65 images: klein 24 min, MOSS 57 min); the API and CLI surface; and how another
project points at this service.

**`README.md`** — three lines pointing at the handbook.

### Order of work, and why

1. Adapter and entry **together** — an entry whose adapter is missing can make guards that
   walk the entries directory fail, which would cost the 20/20 again.
2. Then the catalogue and `host.yaml`.
3. Then the roster, then the docs.
4. Re-run the matrix after step 1 and after step 3, not only at the end.
