#!/usr/bin/env python3
"""What the surviving FLUX.2 [klein] runtime costs in memory while it renders.

This script used to profile both runtimes. The diffusers path was removed on
2026-11-17 (see `docs/reference/flux2-klein.md`), so it now profiles the one
runtime this tree still serves: the community Q4_K_M GGUF through the vendored
`sd-cli`.

It records two currencies: device memory as the driver reports it, and host
memory as the kernel reports it — split on purpose, because a memory-mapped
checkpoint shows up in the process's resident set only while its pages are being
touched.

One prompt, 1024×1024, seed 7, sampled every 250 ms from before `start` until
after `stop`.

The two-arm record this script produced on 2026-11-16 is
`evidence/resource-profile.json`. It is not regenerable now and is deliberately
not the file this script writes: a run today writes
`evidence/resource-profile-gguf.json` and leaves that record alone.

Usage, from the project root:

    .venv/bin/python tests/e2e/flux2-klein/resource_profile.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
CLI = ROOT / "bin" / "coltman-images"
STATE = ROOT / "run" / "server.json"
HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"

MODEL_ALIAS = "flux2-klein-4b-gguf-q4"
TAG = "gguf"
PROMPT = (
    "Photorealistic scene inside a dimly lit bar: six people around a round poker table, "
    "one of them dealing playing cards, chips and half-empty glasses on the green felt, a "
    "bartender in a white shirt and apron wiping a glass behind a wooden counter, warm "
    "tungsten lamps, cigarette smoke in the air, shallow depth of field, 50mm lens"
)
SAMPLES: list[dict[str, float]] = []


def gpu_used_mib() -> float:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True).stdout.strip().splitlines()
    return float(out[0]) if out else 0.0


def server_pid() -> int | None:
    try:
        return int(json.loads(STATE.read_text(encoding="utf-8"))["pid"])
    except Exception:
        return None


TREE = ("coltman_images.server", "sd-cli", "coltman-images")


def rss_mib(pid: int | None) -> float:
    """The whole tree, not just the server: this path renders in an sd-cli child.

    A server-only reading would charge the adapter for nothing, and the child is
    where the quantised weights are touched.
    """
    total = 0.0
    try:
        listing = subprocess.run(["ps", "-eo", "rss=,args="], capture_output=True, text=True).stdout
    except OSError:
        return 0.0
    for line in listing.splitlines():
        rss, _, args = line.strip().partition(" ")
        if not rss.isdigit():
            continue
        if any(marker in args for marker in TREE) and "resource_profile" not in args:
            total += int(rss) / 1024
    return total


def system_used_mib() -> float:
    """Total minus available: page cache counts as used only when it is not freeable."""
    info = {}
    for line in pathlib.Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, _, rest = line.partition(":")
        info[key] = int(rest.split()[0]) / 1024
    return info["MemTotal"] - info["MemAvailable"]


def sampler(stop: threading.Event, mark: str) -> None:
    while not stop.is_set():
        SAMPLES.append({
            "mark": mark,
            "t": time.perf_counter(),
            "gpu_mib": gpu_used_mib(),
            "server_rss_mib": rss_mib(server_pid()),
            "system_used_mib": system_used_mib(),
        })
        time.sleep(0.25)


def profile() -> dict[str, object]:
    SAMPLES.clear()
    stop = threading.Event()
    thread = threading.Thread(target=sampler, args=(stop, TAG), daemon=True)
    started = time.perf_counter()
    thread.start()
    try:
        subprocess.run([str(CLI), "start", "--model", MODEL_ALIAS], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        out = EVIDENCE / f"profile-{TAG}.png"
        reply = subprocess.run(
            [str(CLI), "generate", "--model", MODEL_ALIAS, "--prompt", PROMPT,
             "--width", "1024", "--height", "1024", "--seed", "7",
             "--out", str(out), "--json"], check=True, capture_output=True, text=True)
        response = json.loads(reply.stdout)
    finally:
        subprocess.run([str(CLI), "stop"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        stop.set()
        thread.join(timeout=2)
    wall = time.perf_counter() - started

    rows = [r for r in SAMPLES if r["mark"] == TAG]
    peak_gpu = max(r["gpu_mib"] for r in rows)
    peak_rss = max(r["server_rss_mib"] for r in rows)
    peak_system = max(r["system_used_mib"] for r in rows)
    baseline_gpu = rows[0]["gpu_mib"]
    baseline_system = rows[0]["system_used_mib"]
    return {
        "model": MODEL_ALIAS,
        "samples": len(rows),
        "wall_s": round(wall, 1),
        "render_s": response["render_s"],
        "load_s": response["load_s"],
        "peak_gpu_mib": round(peak_gpu),
        "baseline_gpu_mib": round(baseline_gpu),
        "gpu_delta_mib": round(peak_gpu - baseline_gpu),
        "peak_server_rss_mib": round(peak_rss),
        "peak_system_used_mib": round(peak_system),
        "baseline_system_used_mib": round(baseline_system),
        "system_delta_mib": round(peak_system - baseline_system),
    }


def main() -> int:
    print(f"{'arm':<6} {'wall':>6} {'render':>7} {'load':>7} {'GPU pico':>9} "
          f"{'Δ GPU':>7} {'RSS pico':>9} {'Δ RAM':>7}")
    row = profile()
    print(f"{TAG:<6} {row['wall_s']:>6.1f} {row['render_s']:>7.1f} {row['load_s']:>7.1f} "
          f"{row['peak_gpu_mib']:>9} {row['gpu_delta_mib']:>7} "
          f"{row['peak_server_rss_mib']:>9} {row['system_delta_mib']:>7}")
    destination = EVIDENCE / "resource-profile-gguf.json"
    destination.write_text(json.dumps({TAG: row}, indent=2) + "\n", encoding="utf-8")
    print(f"\nevidence: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
