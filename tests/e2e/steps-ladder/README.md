# The steps ladder — quality against time

A measurement protocol, not a guard. Nothing here blocks a build; it exists to
answer one question with numbers: **at which step count does this model stop
improving, and what does each step cost?**

The law records the operator's ruling of 2026-11-15 (protocol section 12):
twelve steps show more detail, eight trade detail for speed with visibly more
errors. This protocol finds where those two ends actually are.

## The prompt is the instrument

A flattering prompt measures nothing. The one in `run.py` is deliberately
hostile — countable fingers, six buttons, a watch dial, legible text, five
cards, liquid being poured, glass reflections, and skin/fabric/hair texture —
because those are the places a distilled model fails, and the places where two
step counts visibly disagree.

It runs in English: the text encoder is a Qwen3-4B trained largely on English,
and the prompt's job here is to be understood precisely.

## The fixed configuration

| | |
| --- | --- |
| resolution | 1280×720 — the entry's ceiling, the shape production renders |
| sampler / scheduler | whatever the entry declares; unchanged across every run |
| guidance | 0.0, the entry's value. A distilled turbo model has no CFG branch, so a negative prompt could not act |
| seeds | 101, 202, 303, 404, 505 — one seed is not evidence, because composition shifts with the step count |
| steps | 4, 6, 8, 10, 12, 14, 16, 20, 24 |

Nine values times five seeds: **45 stills**, about forty minutes of card.

## How to measure

**1. Error count per still, 0–8.** One point per failure:

1. hands with too many, too few or fused fingers
2. cards fused, or carrying symbols that are not a playing deck
3. deformed or uneven buttons
4. illegible text (`OPEN 24H`)
5. incoherent watch or glasses
6. impossible liquid or glass physics
7. objects appearing or vanishing wrongly (a card inside the glass)
8. plastic skin or fabric at 200 %

**2. Convergence between step values.** For each seed, SSIM between the still at
`N` and the still at the next value. While the difference is large the model is
still changing; when it settles near zero it has converged. `run.py` computes
this and writes `evidence/ssim.json`.

**3. Composition stability.** Note whether the people or the scene change between
consecutive values at the same seed. The value where it stops changing marks the
convergence point — and it is a judgment, recorded beside the score.

## The table to fill

| Steps | Time | Errors (mean of 5 seeds) | SSIM vs previous | Composition stable |
| --- | --- | --- | --- | --- |
| 4 | | | — | |
| 6 | | | | |
| 8 | | | | |
| 10 | | | | |
| 12 | | | | |
| 14 | | | | |
| 16 | | | | |
| 20 | | | | |
| 24 | | | | |

## The decision rule

The optimum is the **first** step value where both hold:

- the mean error count no longer drops by more than ~0.5 against the previous value;
- moving to the next value costs more than 30 % more time.

A turbo model is distilled for a low step count — around eight NFEs. The curve
may not improve smoothly: it can flatten, or **worsen** past that point. If the
mean errors rise at high step values, that rise is the real ceiling, and it is a
result rather than a failure of the measurement.

## What is automated and what is not

`run.py` produces the stills, the timings and the SSIM series. It does **not**
count errors: that is a judgment made from the stills, by the operator or by a
blind judge, and this project does not manufacture a verdict. A VLM judge is
available on this host (`deepseek-v4.1-flash:cloud` and `glm-5.3-flash:cloud`
both accept images; `glm-5.3:cloud` does not), and the precedent for using two
judges blind is recorded in `docs/reference/zimage-fp8-vs-int8.md`.

`evidence/` is gitignored. This README is the record that is committed.
