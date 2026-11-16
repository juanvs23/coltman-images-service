"""Steps ladder: quality against time, measured on a prompt built to break.

The prompt below is deliberately hostile: countable fingers, buttons, a watch
dial, legible text, cards, liquid, glass reflections, and skin/fabric/hair
texture — the places a distilled model fails. One seed is not evidence, because
composition shifts with the step count, so every step value runs on five seeds.

What this produces:
  evidence/stills/      45 PNGs, `<seed>-steps<nn>.png`
  evidence/results.json every render with its measured render_s
  evidence/ssim.json    SSIM between consecutive step values, per seed

What it does not produce: the error count. That is a judgment, and it is scored
from the stills — by the operator or by a blind judge, never asserted here.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from coltman_images.entry import load_entry  # noqa: E402
from coltman_images.render import render  # noqa: E402

PROMPT = (
    "Candid photo of four friends sitting around a round wooden table in a dim "
    "cocktail bar, playing cards. In the foreground, a woman in a knitted wool "
    "sweater holds a fan of exactly five playing cards, fingers clearly visible. "
    "Opposite her, a bearded man in a denim shirt with six visible buttons pours "
    "amber iced tea from a glass pitcher into a tall glass with ice cubes. "
    "On the left, a man wears a metal wristwatch with a readable round dial and "
    "round glasses with reflections. On the right, a woman has long wavy hair and "
    "small hoop earrings. On the table: a chalkboard menu card with the readable "
    'text "OPEN 24H", four coasters, a candle in a glass holder, and a deck of '
    "cards with distinct red hearts and black spades. Behind them, a bar shelf "
    "with rows of bottles with readable labels. Warm tungsten lighting, shallow "
    "depth of field, 50mm lens, natural skin texture with pores, fabric "
    "texture visible, sharp focus on hands and faces."
)

SEEDS = (101, 202, 303, 404, 505)
STEPS = (4, 6, 8, 10, 12, 14, 16, 20, 24)
WIDTH, HEIGHT = 1280, 720

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
STILLS = EVIDENCE / "stills"
TIMINGS = EVIDENCE / "timings.json"


def _load_timings() -> dict[str, float]:
    """Timings already measured, so a interrupted run resumes instead of repeating.

    The stills are the measurement; losing forty minutes of card because the
    last ten renders never happened would be waste, not rigour.
    """
    if TIMINGS.is_file():
        try:
            return json.loads(TIMINGS.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _to_tensor(path: pathlib.Path) -> torch.Tensor:
    array = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)


def _gaussian(window: int = 11, sigma: float = 1.5) -> torch.Tensor:
    x = torch.arange(window, dtype=torch.float32) - (window - 1) / 2
    g = torch.exp(-(x**2) / (2 * sigma**2))
    g = g / g.sum()
    return (g[:, None] @ g[None, :]).unsqueeze(0).unsqueeze(0)


def ssim(a: torch.Tensor, b: torch.Tensor) -> float:
    """Structural similarity on luminance, the standard 11x11 gaussian window."""
    window = _gaussian().expand(3, 1, 11, 11)
    lum = torch.tensor([0.299, 0.587, 0.114]).view(1, 3, 1, 1)
    a = (a * lum).sum(dim=1, keepdim=True)
    b = (b * lum).sum(dim=1, keepdim=True)
    pad = 5
    mu_a = F.conv2d(F.pad(a, (pad,) * 4, mode="reflect"), window[:, :1], groups=1)
    mu_b = F.conv2d(F.pad(b, (pad,) * 4, mode="reflect"), window[:, :1], groups=1)
    sigma_aa = F.conv2d(F.pad(a * a, (pad,) * 4, mode="reflect"), window[:, :1]) - mu_a**2
    sigma_bb = F.conv2d(F.pad(b * b, (pad,) * 4, mode="reflect"), window[:, :1]) - mu_b**2
    sigma_ab = F.conv2d(F.pad(a * b, (pad,) * 4, mode="reflect"), window[:, :1]) - mu_a * mu_b
    c1, c2 = 0.01**2, 0.03**2
    num = (2 * mu_a * mu_b + c1) * (2 * sigma_ab + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (sigma_aa + sigma_bb + c2)
    return float((num / den).mean())


def main() -> int:
    STILLS.mkdir(parents=True, exist_ok=True)
    entry = load_entry()
    rows: list[dict[str, object]] = []

    timings = _load_timings()
    for seed in SEEDS:
        for steps in STEPS:
            target = STILLS / f"{seed}-steps{steps:02d}.png"
            key = f"{seed}-{steps}"
            if target.is_file() and target.stat().st_size > 0 and key in timings:
                render_s = timings[key]
                print(f"seed {seed} steps {steps:2} | {render_s:6.2f} s | already measured", flush=True)
            else:
                run = dataclasses.replace(entry, steps=steps)
                result = render(run, PROMPT, seed=seed, width=WIDTH, height=HEIGHT, out=str(target))
                render_s = round(result["render_s"], 3)
                timings[key] = render_s
                TIMINGS.write_text(json.dumps(timings, indent=2) + "\n")
                print(
                    f"seed {seed} steps {steps:2} | {render_s:6.2f} s | "
                    f"{target.stat().st_size // 1024:4d} KB",
                    flush=True,
                )
            rows.append(
                {
                    "seed": seed,
                    "steps": steps,
                    "render_s": round(render_s, 3),
                    "bytes": target.stat().st_size,
                    "out": str(target.relative_to(ROOT)),
                }
            )

    (EVIDENCE / "results.json").write_text(json.dumps(rows, indent=2) + "\n")

    print("\nSSIM between consecutive step values, per seed:", flush=True)
    convergence: dict[str, dict[str, float]] = {}
    for seed in SEEDS:
        per_seed: dict[str, float] = {}
        for before, after in zip(STEPS, STEPS[1:]):
            a = _to_tensor(STILLS / f"{seed}-steps{before:02d}.png")
            b = _to_tensor(STILLS / f"{seed}-steps{after:02d}.png")
            value = ssim(a, b)
            per_seed[f"{before}->{after}"] = round(value, 5)
            print(f"  seed {seed}  {before:2} -> {after:2}  SSIM {value:.4f}", flush=True)
        convergence[str(seed)] = per_seed
    (EVIDENCE / "ssim.json").write_text(json.dumps(convergence, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
