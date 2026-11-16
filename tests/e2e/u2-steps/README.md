# U2 — `steps` as a request field

The acceptance run for the unit that turns the step count into a request field
bounded by the entry (`docs/protocol.md` sections 4.1, 4.2 and 6.1; guard 15 in
section 10; the ruling in section 12). It is an operator-level run against the
real service on the real card, not a unit test: the numbers below are what the
installed system did.

- **Date:** 2026-11-15 (the UTC stamps in `evidence/` read 2026-11-16T02:5xZ)
- **Verdict:** pass, on every criterion below. The suite is green (15 tests) and
  the baseline request is byte-identical to the one recorded before the change.

## What it proves

1. A request that names no `steps` is byte-identical to the pre-change
   baseline — same sha256, same census.
2. `--steps 8` at 1280×720 renders 8 forwards and says so in the response; the
   cost matches the ladder's ~31.8 s.
3. A step count outside the entry's `limits.steps` (8..16) is refused by the
   server with exit 2 and a message that names the range.
4. 8 and 12 steps at one seed produce different files, and each value is stable
   across repeated runs.

## Commands, and what they answered

Every command ran from the project root, with the server started once and
stopped at the end.

```sh
bin/coltman-images start
```

**The baseline** — the same request as before the unit, naming no `steps`:

```sh
bin/coltman-images generate --prompt "a lighthouse at dusk" \
  --seed 7 --width 512 --height 512 --json
```

`steps: 12`, census `239 / 282 / 0 / 521`, sha256
`0065c34af014499e6c959ca60d59f681647595538c7edf6f832136a29f6d7a72` — identical to
the baseline recorded before the change.

**The ladder's fast mode**, at the entry's ceiling:

```sh
bin/coltman-images generate --prompt "a lighthouse at dusk" --seed 7 \
  --steps 8 --width 1280 --height 720 --out <evidence>/steps8-1280x720.png --json
```

`steps: 8`, `render_s: 30.178`, `load_s: 2.649`, sha256 `fba116a9…`.

**The refusals:**

```sh
bin/coltman-images generate --prompt "a lighthouse at dusk" --steps 3  --width 1280 --height 720
bin/coltman-images generate --prompt "a lighthouse at dusk" --steps 20 --width 1280 --height 720
```

both `exit 2`:

```
coltman-images: invalid_request: steps: expected an integer inside 8..16, got 3
coltman-images: invalid_request: steps: expected an integer inside 8..16, got 20
```

**Determinism and difference**, two runs at each value, one seed, 1280×720:

| Run | `steps` | `render_s` | sha256 |
| --- | --- | --- | --- |
| `steps8-run1` | 8 | 30.128 | `fba116a995db6cef…` |
| `steps8-run2` | 8 | 30.228 | `fba116a995db6cef…` |
| `steps12-run1` | 12 | 44.833 | `ff3b84a08e48e1b0…` |
| `steps12-run2` | 12 | 44.876 | `ff3b84a08e48e1b0…` |

Each value is identical across its two runs; the two values differ. The `steps8`
stills are also identical to the one the ceiling command wrote, a third run at
that value.

```sh
bin/coltman-images stop
```

## How to regenerate

```sh
cd coltman-images-service
bin/coltman-images start
# the four commands above, then
bin/coltman-images stop
```

The step range lives in `model/entry.yaml` (`limits.steps`) and its ruling in
`docs/protocol.md` section 12. Guard 15 (`tests/test_p6_guards.py`) is the
executable half: it refuses an out-of-range value before the adapter exists,
reads the response's `steps`, and compares the bytes of 8 against 12 at 512×512.

## What the run leaves behind

`evidence/` (gitignored, written by the commands above):

| File | What it is |
| --- | --- |
| `baseline-after.json` | the response to the request that names no `steps` |
| `steps8-1280x720.json`, `steps8-1280x720.png` | the fast-mode render and its response |
| `refusals.txt` | the two refusals, with their exit codes |
| `steps8-run{1,2}.json`, `steps12-run{1,2}.json` | the four determinism responses |
| `steps{8,12}-run{1,2}-1280x720.png` | the four stills the digests come from |

Nothing is written outside this folder and the project's own `run/` and `out/`.

## Inputs, by location

| Input | Where |
| --- | --- |
| The range and the default | `model/entry.yaml` — `steps: 12`, `limits.steps: {min: 8, max: 16}` |
| The ruling behind the range | `docs/reference/steps-ladder.md`, protocol section 12 |
| The validation | `coltman_images/entry.py` — `Entry.accepts` |
| The resolution and the response field | `coltman_images/render.py`, `coltman_images/server.py` |
| The flag | `bin/coltman-images --steps` |
