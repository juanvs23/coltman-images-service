#!/usr/bin/env python3
"""What the sampler and the flow shift actually change on FLUX.2 [klein] Q4_K_M.

Neither knob is reachable through an entry: the `ggml` adapter builds `sd-cli`'s
command line from the entry, and the entry declares no `--sampling-method` and no
`--flow-shift`. This script calls the vendored binary directly, which is a
measurement and not a service behaviour — the card must be free, and the script
refuses to run while a server holds it.

Same prompt, same seed, same step count; only the knob moves.

Usage, from the project root:

    .venv/bin/python tests/e2e/flux2-klein/sampler_sweep.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence" / "sweep"
SD = ROOT / "vendor/stable-diffusion.cpp/build/bin/sd-cli"
LOCK = ROOT / "run" / "server.lock"

MODEL = ROOT / "model/assets/flux2-klein/gguf/flux-2-klein-4b-Q4_K_M.gguf"
VAE = ROOT / "model/assets/flux2-klein/official/vae/diffusion_pytorch_model.safetensors"
LLM = ROOT / "model/assets/flux2-klein/gguf/Qwen3-4B-Q4_K_M.gguf"

SIZE, SEED, STEPS = 1024, 7, 4

PROMPTS = {
    "poker": ("Photorealistic scene inside a dimly lit bar: six people around a round poker "
              "table, one of them dealing playing cards, chips and half-empty glasses on the "
              "green felt, a bartender in a white shirt and apron wiping a glass behind a "
              "wooden counter, warm tungsten lamps, cigarette smoke in the air, shallow depth "
              "of field, 50mm lens"),
    "glass": ("A cut crystal whiskey glass on a wet slate table, one large clear ice cube, a "
              "lemon slice inside, caustic light patterns on the wood, hard studio light from "
              "the left, macro detail"),
}

METHODS = ["euler", "dpm++2m", "res_multistep", "ipndm", "heun"]
# `--flow-shift` takes a number, not "auto": auto is what the binary does
# when the flag is absent, which is the baseline already rendered by euler.
SHIFTS = ["1.0", "3.0", "6.0"]


def render(tag: str, prompt: str, extra: list[str]) -> dict[str, object]:
    out = EVIDENCE / f"{tag}.png"
    if out.is_file():
        return {"tag": tag, "ok": True, "wall_s": 0.0, "extra": " ".join(extra), "cached": True}
    cmd = [str(SD), "--diffusion-model", str(MODEL), "--vae", str(VAE), "--llm", str(LLM),
           "-p", prompt, "--cfg-scale", "1.0", "--steps", str(STEPS),
           "-W", str(SIZE), "-H", str(SIZE), "-s", str(SEED), "-o", str(out),
           "--offload-to-cpu", *extra]
    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0 or not out.is_file():
        return {"tag": tag, "ok": False, "wall_s": round(elapsed, 1),
                "error": (proc.stderr or proc.stdout)[-200:]}
    return {"tag": tag, "ok": True, "wall_s": round(elapsed, 1),
            "extra": " ".join(extra)}


def sheet(name: str, tags: list[str]) -> None:
    """One row per variant, so a difference is seen and not argued."""
    from PIL import Image

    images = [Image.open(EVIDENCE / f"{tag}.png").convert("RGB")
              for tag in tags if (EVIDENCE / f"{tag}.png").is_file()]
    scale = 0.34
    tiles = [im.resize((int(im.width * scale), int(im.height * scale))) for im in images]
    width = sum(t.width for t in tiles) + 6 * (len(tiles) - 1)
    height = max(t.height for t in tiles)
    out = Image.new("RGB", (width, height), "white")
    x = 0
    for tile in tiles:
        out.paste(tile, (x, 0))
        x += tile.width + 6
    out.save(EVIDENCE / f"sheet-{name}.png")


def main() -> int:
    if LOCK.exists():
        holder = subprocess.run(["fuser", str(LOCK)], capture_output=True, text=True).stdout.strip()
        if holder:
            print(f"refused: the card is held ({LOCK} by pid {holder}); stop the server first")
            return 1
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for name, prompt in PROMPTS.items():
        for method in METHODS:
            tag = f"{name}-{method.replace('+', 'p')}"
            row = render(tag, prompt, ["--sampling-method", method])
            row["prompt"], row["method"] = name, method
            results.append(row)
            print(f"  {tag:<22} {row['wall_s']:>5.1f} s"
                  + ("  (ya estaba)" if row.get("cached") else "")
                  + ("" if row["ok"] else f"  FALLÓ: {row.get('error', '')}"), flush=True)
        for shift in SHIFTS:
            tag = f"{name}-shift{shift}"
            row = render(tag, prompt, ["--flow-shift", shift])
            row["prompt"], row["shift"] = name, shift
            results.append(row)
            print(f"  {tag:<22} {row['wall_s']:>5.1f} s"
                  + ("  (ya estaba)" if row.get("cached") else "")
                  + ("" if row["ok"] else f"  FALLÓ: {row.get('error', '')}"), flush=True)

    for name in PROMPTS:
        sheet(name, [f"{name}-{m.replace('+', 'p')}" for m in METHODS])
        sheet(f"{name}-shift", [f"{name}-shift{s}" for s in SHIFTS])

    (EVIDENCE / "sweep.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nevidence: {EVIDENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
