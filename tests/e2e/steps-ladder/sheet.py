"""Build the contact sheets the error count is read from.

Works on a partial ladder: a still that is not on disk is a cell that is not
drawn, because a measurement can be read before it is finished and a script that
demands all forty-five of them is a script that gets used once.

  evidence/sheet-seed<seed>.png     the step values of one seed, three per row
  evidence/detail-seed<seed>.png    the same crop at 200 %, one cell per value
  evidence/all-stills.png           every still on disk, six per row
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
CROP = (380, 120, 900, 420)  # hands-and-cards region
LABEL = ImageFont.load_default()
BACKGROUND = (16, 16, 16)
INK = (240, 240, 240)


def _times() -> dict[str, float]:
    """Timings from whichever record exists — partial runs write timings first."""
    for name in ("results.json", "timings.json"):
        path = EVIDENCE / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text())
        if name == "timings.json":
            return {key: float(value) for key, value in data.items()}
        return {f"{row['seed']}-{row['steps']}": float(row["render_s"]) for row in data}
    return {}


def _present() -> dict[int, list[int]]:
    """Which step values exist, per seed."""
    found: dict[int, list[int]] = {}
    for path in sorted(STILLS.glob("*.png")):
        seed_text, _, rest = path.stem.partition("-steps")
        if not seed_text.isdigit() or not rest.isdigit():
            continue
        found.setdefault(int(seed_text), []).append(int(rest))
    return {seed: sorted(values) for seed, values in sorted(found.items())}


def _sheet(path: pathlib.Path, seed: int, values: list[int], times: dict[str, float]) -> None:
    tile_w, tile_h, cols = 640, 360, 3
    rows = (len(values) + cols - 1) // cols
    canvas = Image.new(
        "RGB", (cols * tile_w + (cols - 1) * 4, rows * (tile_h + 20) + (rows - 1) * 4), BACKGROUND
    )
    draw = ImageDraw.Draw(canvas)
    for index, steps in enumerate(values):
        still = Image.open(STILLS / f"{seed}-steps{steps:02d}.png").convert("RGB")
        still = still.resize((tile_w, tile_h), Image.LANCZOS)
        x = (index % cols) * (tile_w + 4)
        y = (index // cols) * (tile_h + 20 + 4)
        canvas.paste(still, (x, y + 20))
        seconds = times.get(f"{seed}-{steps}")
        label = f"seed {seed} · {steps} steps" + (f" · {seconds:.1f}s" if seconds else "")
        draw.text((x + 4, y + 5), label, fill=INK, font=LABEL)
    canvas.save(path)


def _detail(path: pathlib.Path, seed: int, values: list[int], times: dict[str, float]) -> None:
    cw, ch, cols, scale = 520, 300, 3, 2
    rows = (len(values) + cols - 1) // cols
    canvas = Image.new(
        "RGB",
        (cols * cw * scale + (cols - 1) * 4, rows * (ch * scale + 20) + (rows - 1) * 4),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(canvas)
    for index, steps in enumerate(values):
        still = Image.open(STILLS / f"{seed}-steps{steps:02d}.png").convert("RGB").crop(CROP)
        still = still.resize((cw * scale, ch * scale), Image.LANCZOS)
        x = (index % cols) * (cw * scale + 4)
        y = (index // cols) * (ch * scale + 20 + 4)
        canvas.paste(still, (x, y + 20))
        seconds = times.get(f"{seed}-{steps}")
        label = f"{steps} steps at 200 %" + (f" · {seconds:.1f}s" if seconds else "")
        draw.text((x + 4, y + 5), label, fill=INK, font=LABEL)
    canvas.save(path)


def _all_stills(path: pathlib.Path, present: dict[int, list[int]], times: dict[str, float]) -> None:
    """Every still on disk in one image, six per row, seed and steps labelled."""
    cells = [(seed, steps) for seed, values in present.items() for steps in values]
    cols, tile_w, tile_h = 6, 426, 240
    rows = (len(cells) + cols - 1) // cols
    canvas = Image.new(
        "RGB", (cols * tile_w + (cols - 1) * 4, rows * (tile_h + 18) + (rows - 1) * 4), BACKGROUND
    )
    draw = ImageDraw.Draw(canvas)
    for index, (seed, steps) in enumerate(cells):
        still = Image.open(STILLS / f"{seed}-steps{steps:02d}.png").convert("RGB")
        still = still.resize((tile_w, tile_h), Image.LANCZOS)
        x = (index % cols) * (tile_w + 4)
        y = (index // cols) * (tile_h + 18 + 4)
        canvas.paste(still, (x, y + 18))
        seconds = times.get(f"{seed}-{steps}")
        label = f"s{seed} · {steps}" + (f" · {seconds:.0f}s" if seconds else "")
        draw.text((x + 3, y + 4), label, fill=INK, font=LABEL)
    canvas.save(path)


def _spread(seed: int, values: list[int]) -> str:
    """Where the two extremes of a seed disagree most, so the crop is not a guess."""
    if len(values) < 2:
        return "not enough stills"
    a = np.asarray(Image.open(STILLS / f"{seed}-steps{values[0]:02d}.png").convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(STILLS / f"{seed}-steps{values[-1]:02d}.png").convert("RGB"), dtype=np.int16)
    diff = np.abs(a - b).mean(axis=2)
    tile = 32
    gh, gw = diff.shape[0] // tile, diff.shape[1] // tile
    tiles = diff[: gh * tile, : gw * tile].reshape(gh, tile, gw, tile).mean(axis=(1, 3))
    ty, tx = np.unravel_index(tiles.argmax(), tiles.shape)
    return f"x={tx * tile + tile // 2} y={ty * tile + tile // 2} (mean diff {tiles.max():.0f}/255)"


def main() -> int:
    times = _times()
    present = _present()
    total = sum(len(values) for values in present.values())
    print(f"stills on disk: {total} across {len(present)} seed(s)\n")
    for seed, values in present.items():
        _sheet(EVIDENCE / f"sheet-seed{seed}.png", seed, values, times)
        _detail(EVIDENCE / f"detail-seed{seed}.png", seed, values, times)
        print(f"  seed {seed}: {len(values)} value(s) · biggest {values[0]}-against-{values[-1]} at {_spread(seed, values)}")
    _all_stills(EVIDENCE / "all-stills.png", present, times)
    print(f"\nwrote sheet-seed*.png, detail-seed*.png and all-stills.png ({total} stills) under evidence/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
