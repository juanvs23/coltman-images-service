# The ladder per seed

**Evidence, not law.** Measured 2026-11-15 on the RTX 4060 Laptop this project
is built for, with the project's own loader and `.venv`, from the same ladder
`docs/reference/steps-ladder.md` records: `tests/e2e/steps-ladder/evidence/timings.json`
for the times and `tests/e2e/steps-ladder/evidence/ssim.json` for the SSIM.
Forty-five stills, five seeds, nine step values from 4 to 24.

The law's ruling lives in protocol section 12. This file is a per-seed reading
of the same numbers, and it establishes no quality verdict.

## The question

One seed was put forward as the divergent one: 505. Is it the slowest? Is it the
most cohesive? And is there a seed to choose over the others?

The answer is that the divergence is real in time and does not exist in
quality.

## Time

Every time is the render of one still, in seconds, at 1280×720.

| Steps | 101 | 202 | 303 | 404 | 505 | Mean |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 15.93 | 16.52 | 16.59 | 16.66 | 16.56 | 16.45 |
| 6 | 23.33 | 24.27 | 24.25 | 24.37 | 24.26 | 24.10 |
| 8 | 30.95 | 32.04 | 31.96 | 32.05 | 32.04 | 31.81 |
| 10 | 38.63 | 39.62 | 39.74 | 39.73 | 39.66 | 39.48 |
| 12 | 46.36 | 47.31 | 47.40 | 46.75 | 47.75 | 47.11 |
| 14 | 54.17 | 55.03 | 55.15 | 54.71 | 56.28 | 55.07 |
| 16 | 61.93 | 62.72 | 62.84 | 62.54 | 64.31 | 62.87 |
| 20 | 77.33 | 78.24 | 78.33 | 77.96 | 79.99 | 78.37 |
| 24 | 92.81 | 93.68 | 93.75 | 93.36 | 95.78 | 93.88 |

**505 is not the slowest seed at every step count.** It is the slowest from 12
steps upward. At 4, 6 and 8 steps the slowest is 404; at 10 steps it is 303.

**The spread between the fastest and the slowest seed grows with the step
count**: 0.73 s at 4 steps, 1.04 s at 6, 1.10 s at 8, 1.11 s at 10, 1.39 s at
12, 2.11 s at 14, 2.38 s at 16, 2.66 s at 20 and 2.97 s at 24.

**505's excess over the mean of the other four grows the same way**: +0.14 s at
4 steps, +0.29 s at 8, +0.80 s at 12, +1.80 s at 16 and +2.38 s at 24.

**The divergence is a slope, not an offset.** Each seed's own curve is linear:
3.84 s per step for 101, 3.86 for 202, 3.86 for 303, 3.84 for 404 and 3.96 for
505. The seeds sit close together at the bottom of the range and separate
upward, because 505's steps cost 3 % more than 101's and the difference
accumulates over the twenty steps between them.

**What it costs.** At 24 steps the gap between the fastest and the slowest seed
is 2.97 s on a 92.81 s render: 3.2 %. The slowest seed in the ladder costs
three per cent more than the fastest one, and that is the whole of the
divergence.

## SSIM

SSIM is measured between the still at one step count and the still at the
next, per seed.

| Seed | 20→24 | Mean over the eight pairs | Highest pair in the ladder |
| --- | --- | --- | --- |
| 101 | 0.87029 | 0.82111 | 0.87029 at 20→24 |
| 202 | 0.93861 | 0.86468 | 0.93861 at 20→24 |
| 303 | 0.90401 | 0.86238 | 0.91358 at 14→16 |
| 404 | 0.87694 | 0.83294 | 0.88838 at 14→16 |
| 505 | 0.90267 | 0.86486 | 0.90949 at 16→20 |

**505's SSIM at 20→24 is 0.90267, not 0.95776.** The figure 0.95776 appears
nowhere in the evidence.

**The highest value in the whole matrix is seed 202's 0.93861 at 20→24**, and
505's highest SSIM anywhere in the ladder is 0.90949, at 16→20.

**By mean SSIM over the eight pairs, 505 and 202 are indistinguishable**:
0.86486 against 0.86468, a difference of 0.0002, which is noise.

## What this establishes

- **Per-seed timing variance.** The seeds differ by 3 % in the cost of a step,
  and the difference grows with the count of steps: the spread across seeds
  goes from 0.73 s at 4 steps to 2.97 s at 24.
- **Per-seed SSIM.** The seeds differ by up to 0.121 on a single pair and by
  0.044 on the mean, with 505 and 202 tied at the top.
- **That the growth in the divergence belongs to the timing and not to the
  SSIM.** The spread of the SSIM across seeds does not grow with the step
  count — it stays between 0.033 and 0.121 across the eight pairs — while the
  spread of the timing goes from 0.73 s to 2.97 s.

## What this does not establish

- **SSIM measures how much the image changes, not whether it is better.** A
  high value means two step counts agreed more, not that either is closer to
  correct. The ladder's own report says exactly this, and the mean SSIM from
  14 steps upward is the model's noise floor — 0.885 to 0.900 — not fidelity.
- **No seed is the best one.** Nothing here ranks the seeds by quality, and no
  document may rank them on the strength of a value that measures agreement
  between two renders rather than correctness.
- **The quality question was not answered here, and it is not owed.** The
  operator's own eye read of the contact sheets, recorded in
  `docs/reference/steps-ladder.md` under "What the eye saw", is the
  measurement. The eight-category error count was never produced, and no
  document may claim that it exists.
- **Nothing here reopens the ruling.** The step count's range and its default
  are the operator's, and they are recorded in protocol section 12.

## The earlier reading

The report this file replaces put 505 forward as the most cohesive seed and
recommended it for maximum visual fidelity. Neither claim survives the
evidence: 505's SSIM at 20→24 is 0.90267 and its highest value anywhere is
0.90949, both below seed 202's 0.93861, and a high SSIM at the top of the
ladder is the noise floor rather than a mark of quality. The seed is the
slowest one from 12 steps upward, not at every step count, and being slowest
is a cost, not a defect in the image.
