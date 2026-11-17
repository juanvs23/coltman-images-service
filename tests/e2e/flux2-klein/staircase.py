#!/usr/bin/env python3
"""T3 and T4 — the two questions the law left open about this model.

The measurements below were taken on 2026-11-17 and the operator ruled on them
the same day; the entry now declares `limits.steps: {min: 4, max: 8}` with a
default of 8, and `max_pixels: 1327104`. This script is kept as the record of
how those numbers were produced, and it still runs.

T3: does moving off the four distilled steps help or hurt? The entry declared
    `steps: {min: 4, max: 4}` at the time and refused anything else, so this
    bypasses the service and calls the vendored binary — a measurement, not a
    behaviour.

T4: where does the size ladder stop? The entry's ceiling was 1048576 px, which
    is 1024². 1152² is 1,327,104 px and sat *above* the declared ceiling on
    purpose: if the card holds it, the ceiling is conservative; if it does not,
    the ceiling is a measurement.

Device memory is sampled every 250 ms from before the call until it returns.

Usage, from the project root:

    .venv/bin/python tests/e2e/flux2-klein/staircase.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence" / "staircase"
SD = ROOT / "vendor/stable-diffusion.cpp/build/bin/sd-cli"
LOCK = ROOT / "run" / "server.lock"

MODEL = ROOT / "model/assets/flux2-klein/gguf/flux-2-klein-4b-Q4_K_M.gguf"
VAE = ROOT / "model/assets/flux2-klein/official/vae/diffusion_pytorch_model.safetensors"
LLM = ROOT / "model/assets/flux2-klein/gguf/Qwen3-4B-Q4_K_M.gguf"

PROMPT = ("Photorealistic scene inside a dimly lit bar: six people around a round poker "
          "table, one of them dealing playing cards, chips and half-empty glasses on the "
          "green felt, a bartender in a white shirt and apron wiping a glass behind a "
          "wooden counter, warm tungsten lamps, cigarette smoke in the air, shallow depth "
          "of field, 50mm lens")

STEPS_LADDER = [4, 6, 8]
SIZE_LADDER = [("512", 512, 512), ("768", 768, 768), ("1024", 1024, 1024),
               ("1152", 1152, 1152), ("1280x720", 1280, 720)]
SEED = 7


def gpu_used() -> float:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return float(out[0]) if out else 0.0


def run(tag: str, width: int, height: int, steps: int) -> dict[str, object]:
    out = EVIDENCE / f"{tag}.png"
    peak = {"mib": 0.0}
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            peak["mib"] = max(peak["mib"], gpu_used())
            time.sleep(0.25)

    baseline = gpu_used()
    peak["mib"] = baseline
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    started = time.perf_counter()
    proc = subprocess.run(
        [str(SD), "--diffusion-model", str(MODEL), "--vae", str(VAE), "--llm", str(LLM),
         "-p", PROMPT, "--cfg-scale", "1.0", "--steps", str(steps),
         "-W", str(width), "-H", str(height), "-s", str(SEED), "-o", str(out),
         "--offload-to-cpu"], capture_output=True, text=True)
    wall = time.perf_counter() - started
    stop.set()
    thread.join(timeout=2)
    ok = proc.returncode == 0 and out.is_file()
    return {"tag": tag, "ok": ok, "wall_s": round(wall, 1), "steps": steps,
            "width": width, "height": height, "pixels": width * height,
            "peak_gpu_mib": round(peak["mib"]), "gpu_delta_mib": round(peak["mib"] - baseline),
            "error": None if ok else (proc.stderr or proc.stdout)[-200:]}


def sheet(tags: list[str], name: str) -> None:
    from PIL import Image
    images = [Image.open(EVIDENCE / f"{t}.png").convert("RGB")
              for t in tags if (EVIDENCE / f"{t}.png").is_file()]
    if not images:
        return
    scale = 0.34
    tiles = [im.resize((int(im.width * scale), int(im.height * scale))) for im in images]
    width = sum(t.width for t in tiles) + 6 * (len(tiles) - 1)
    out = Image.new("RGB", (width, max(t.height for t in tiles)), "white")
    x = 0
    for tile in tiles:
        out.paste(tile, (x, 0))
        x += tile.width + 6
    out.save(EVIDENCE / f"sheet-{name}.png")


def main() -> int:
    if LOCK.exists() and subprocess.run(["fuser", str(LOCK)], capture_output=True, text=True).stdout.strip():
        print("refused: the card is held; stop the server first")
        return 1
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = []

    print("T3 — the step count, measured instead of asserted")
    for steps in STEPS_LADDER:
        row = run(f"steps-{steps}", 1024, 1024, steps)
        results.append(row)
        print(f"  {steps} pasos   {row['wall_s']:>6.1f} s   pico {row['peak_gpu_mib']} MiB"
              + ("" if row["ok"] else f"  FALLÓ {row['error']}"), flush=True)

    print("T4 — the size ladder")
    for name, width, height in SIZE_LADDER:
        row = run(f"size-{name}", width, height, 4)
        results.append(row)
        print(f"  {name:<9} {row['pixels']:>9} px   {row['wall_s']:>6.1f} s   "
              f"pico {row['peak_gpu_mib']} MiB"
              + ("" if row["ok"] else f"  FALLÓ {row['error']}"), flush=True)

    sheet([f"steps-{s}" for s in STEPS_LADDER], "steps")
    sheet([f"size-{n}" for n, _, _ in SIZE_LADDER], "sizes")
    (EVIDENCE / "staircase.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nevidence: {EVIDENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
