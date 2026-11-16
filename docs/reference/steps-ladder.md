# The steps ladder

**Evidence, not law.** Measured 2026-11-15 on the RTX 4060 Laptop this project
is built for, with the project's own loader and `.venv`. Reproduce it with
`tests/e2e/steps-ladder/run.py`; the stills it produces are gitignored and the
committed `README.md` beside it says how to read them.

The law's ruling lives in protocol section 12. This file is what that ruling
stands on.

## Why a hostile prompt

A flattering prompt measures nothing. The ladder runs on a prompt built to break
the model — four friends around a table, a fan of exactly five cards with the
fingers visible, six buttons on a denim shirt, a wristwatch with a readable dial,
round glasses with reflections, a chalkboard reading `OPEN 24H`, liquid being
poured from a pitcher into a glass, and visible skin, fabric and hair texture.
Those are the places a distilled model fails, and therefore the places where two
step counts can disagree.

Five seeds: 101, 202, 303, 404, 505. Nine step values: 4, 6, 8, 10, 12, 14, 16,
20, 24. Forty-five stills at 1280×720, the entry's ceiling.

## The ladder

Every time is the mean of the five seeds. SSIM is between the still at one step
count and the still at the next, also averaged over the seeds.

| Steps | Time | Extra time | SSIM vs previous |
| --- | --- | --- | --- |
| 4 | 16.5 s | — | — |
| 6 | 24.1 s | +47 % | 0.772 |
| 8 | 31.8 s | +32 % | 0.786 |
| 10 | 39.5 s | +24 % | 0.807 |
| 12 | 47.1 s | +19 % | **0.861** |
| 14 | 55.1 s | +17 % | 0.883 |
| 16 | 62.9 s | +14 % | **0.900** |
| 20 | 78.4 s | +25 % | 0.885 |
| 24 | 93.9 s | +20 % | 0.899 |

Time is linear: **3.87 s per step**, with about 0.9 s of fixed overhead. The
cost of a step does not fall as the count rises, and nothing in the measurement
suggests a cheaper step exists.

## What the numbers say

1. **The curve turns at 12–14.** SSIM rises from 0.77 to 0.90, and from 14→16
   onward it stays in 0.885–0.900. The largest jumps are 8→10 and 10→12, where
   the model is still deciding what the scene is.
2. **It never converges to 1.0.** Even comparing 20 against 24 the SSIM sits near
   0.90: consecutive step counts differ structurally by about a tenth. That is a
   noise floor, not an approach to a final image. More steps do not reach a
   sharper limit; they reach a different variation.
3. **16→20 falls in four of five seeds** (0.857, 0.920, 0.893, 0.847; it rises
   only on 505) even though those two stills are further apart than their
   neighbours. That is the signature of the ceiling the operator predicted: past
   it the extra steps buy variation, not definition.
4. **Two seeds are unstable at the low end.** Seed 404 jumps hard at 8→10
   (0.736), and its contact sheet shows the candle, the coasters and the position
   of the sign moving. Seed 101 drops at 12→14 (0.841).

## What the eye saw

A qualitative read of the contact sheets, recorded as a judgment and not as a
count:

- **Composition is stable across 4 to 24 with this prompt.** The people and the
  scene hold; they did not in the earlier, less restrictive prompt, where the
  same seed produced a different photograph at every step count.
- **Hands and the grip on the pitcher read correctly at every step count**, with
  no fused fingers even at 4.
- **The low steps show in the pitcher**: at 4–6 on seeds 303 and 404 the interior
  is dirty, with a white smudge where a reflection should be. From 10 upward it
  is defined.
- **The text is not a discriminator**: `OPEN 24H` reads from 4 steps. On seed 404
  the `H` is covered by the cards from 10 upward, which is composition, not
  degradation.
- **The card indices are pseudo-symbols at every step count.** The fan looks
  plausible at a glance and does not improve with steps.
- **The denim shows a mottled pattern from about 8–10 steps** (seeds 101 and 505)
  that does not disappear higher up. It reads as the model's own texture, not as
  a step-count defect.

## The ruling

Recorded in protocol section 12 by the operator on 2026-11-15:

- **12 is the minimum** where the scene and its principal detail are settled, and
  it stays the production default.
- **14 is the cut** if the criterion is visible gain for each 15 % of extra time.
- **16 is the usable ceiling.** Going to 24 costs +49 % of time over 16 and buys
  no convergence.
- **8–10 is the fast mode**: acceptable, with a reframing risk on some seeds —
  404 is the example.
- **Below 8 is not adopted**: under the distilled design of the model, and
  visibly dirty at 4–6.

## The lever

The step count is the only quality-versus-time lever this system has that costs
nothing to change: the same weights serve every value, so an entry that differs
only in `steps` is a second file and not a second model, and switching between
them puts nothing new on the card.

Pick the row by what you are willing to pay, not by what sounds better:

| Intent | Steps | Time at 1280×720 | What the ladder says |
| --- | --- | --- | --- |
| Draft, thumbnail | 8 | 31.8 s | The model's own distilled design point. Acceptable, with a reframing risk between 8 and 10 on some seeds |
| Fast batch | 10 | 39.5 s | Still under the knee; the pitcher's interior and small objects are settling |
| **Default** | **12** | **47.1 s** | The minimum where the scene and its principal detail are settled |
| Quality | 14 | 55.1 s | The cut if the criterion is visible gain for each 15 % of extra time |
| Maximum useful | 16 | 62.9 s | The last range where SSIM still rises. Above it, +49 % to reach 24 buys no convergence |
| — | below 8 | — | Under the distilled design, and visibly dirty on the pitcher at 4–6. Not adopted |
| — | above 16 | — | Not refused by the scheduler — it renders — but it does not converge, so it is refused by the ruling |

Two cautions, because a lever is easy to misread:

- **More is not better.** The curve turns; it does not climb. Past 16 the extra
  forwards buy a different image, not a more defined one.
- **3.87 s per step is this card's price at 1280×720.** Another resolution moves
  the absolute seconds; it does not change the shape of the trade.

The lever is only as honest as its measurement, and the measurement has one hole:
nobody has scored the eight error categories against the forty-five stills. Until
that happens, the table tells you what changes and what it costs, and it does not
tell you which row looks better.

## What this does not establish

- **SSIM measures how much the image changes, not whether it is better.** A high
  value means two step counts agreed more, not that either is closer to correct.
- **The per-image error count is missing.** The protocol defines eight countable
  failures; nobody has scored the forty-five stills against them yet. Until that
  exists, no document may claim that 12 and 16 differ in real quality.
