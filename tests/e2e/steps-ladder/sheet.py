"""Build the contact sheets the error count is read from.

`run.py` finishes first. This script only arranges what it produced:

  evidence/sheet-seed<seed>.png     nine step values in a 3x3 grid, 640 wide each
  evidence/detail-seed<seed>.png    the same crop at 200 %, one cell per step value

The per-seed detail strip is the one that matters: error counting happens where
hands and faces live, and at 640 wide a fused finger is invisible.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
STILLS = EVIDENCE / "stills"
STEPS = (4, 6, 8, 10, 12, 14, 16, 20, 24)
CROP = (380, 120, 900, 420)  # hands-and-cards region, widened once the ladder shows where it breaks
LABEL = ImageFont.load_default()


def _times() -> dict[str, float]:
    rows = json.loads((EVIDENCE / "results.json").read_text())
    return {f"{r['seed']}-{r['steps']}": r["render_s"] for r in rows}


def _grid(path: pathlib.Path, seed: int, times: dict[str, float]) -> None:
    tile_w, tile_h, cols = 640, 360, 3
    rows = (len(STEPS) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tile_w + (cols - 1) * 4, rows * (tile_h + 20) + (rows - 1) * 4), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    for i, steps in enumerate(STEPS):
        still = Image.open(STILLS / f"{seed}-steps{steps:02d}.png").convert("RGB").resize((tile_w, tile_h), Image.LANCZOS)
        x, y = (i % cols) * (tile_w + 4), (i // cols) * (tile_h + 20 + 4)
        canvas.paste(still, (x, y + 20))
        draw.text((x + 4, y + 5), f"seed {seed} · {steps} steps · {times[f'{seed}-{steps}']:.1f}s", fill=(240, 240, 240), font=LABEL)
    canvas.save(path)


def _detail(path: pathlib.Path, seed: int, times: dict[str, float]) -> None:
    cw, ch, cols = 520, 300, 3
    scale = 2
    rows = (len(STEPS) + cols - 1) // cols
    canvas = Image.new(
        "RGB",
        (cols * cw * scale + (cols - 1) * 4, rows * (ch * scale + 20) + (rows - 1) * 4),
        (16, 16, 16),
    )
    draw = ImageDraw.Draw(canvas)
    for i, steps in enumerate(STEPS):
        still = Image.open(STILLS / f"{seed}-steps{steps:02d}.png").convert("RGB").crop(CROP)
        still = still.resize((cw * scale, ch * scale), Image.LANCZOS)
        x, y = (i % cols) * (cw * scale + 4), (i // cols) * (ch * scale + 20 + 4)
        canvas.paste(still, (x, y + 20))
        draw.text((x + 4, y + 5), f"{steps} steps at 200 %", fill=(240, 240, 240), font=LABEL)
    canvas.save(path)


def _spread(seed: int) -> str:
    """Where the two ends disagree most, so the crop is not a guess."""
    a = np.asarray(Image.open(STILLS / f"{seed}-steps04.png").convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(STILLS / f"{seed}-steps24.png").convert("RGB"), dtype=np.int16)
    diff = np.abs(a - b).mean(axis=2)
    tile, (gh, gw) = 32, (diff.shape[0] // 32, diff.shape[1] // 32)
    tiles = diff[: gh * tile, : gw * tile].reshape(gh, tile, gw, tile).mean(axis=(1, 3))
    ty, tx = np.unravel_index(tiles.argmax(), tiles.shape)
    return f"x={tx * tile + tile // 2} y={ty * tile + tile // 2} (mean diff {tiles.max():.0f}/255)"


def main() -> int:
    times = _times()
    for seed in (101, 202, 303, 404, 505):
        _grid(EVIDENCE / f"sheet-seed{seed}.png", seed, times)
        _detail(EVIDENCE / f"detail-seed{seed}.png", seed, times)
        print(f"seed {seed}: biggest 4-against-24 disagreement at {_spread(seed)}")
    print("\nwrote sheet-seed*.png and detail-seed*.png under evidence/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
