#!/usr/bin/env python3
"""T5 — the instance lock and the single-flight queue, in the directions not yet proven.

Three scenarios, each run against the real card through `bin/coltman-images` as an
operator uses it, all aimed at the promoted FLUX.2 entry (`start --model
flux2-klein-4b-gguf-q4`):

  A. two `generate` calls at once — the single worker must serialise them, and
     `pgrep -c sd-cli` must never exceed 1 for the whole window;
  B. `stop` arriving mid-render — the render either completes or is aborted
     cleanly, and afterwards no `sd-cli`, no state file and no held lock remain;
  C. a fresh `start` while a bare `sd-cli` (launched by hand, holding no lock)
     is already loading the card — whatever happens is the finding.

Scenario C is deliberately not a pass/fail: a hand-launched `sd-cli` never asks
for `run/server.lock`, so the question is whether anything else notices it.
The script records what it observes and exits 0 either way; the README and
`docs/reference/flux2-klein.md` carry the reading.

Usage, from the project root. The card must be free:
`run/server.json` absent and no `sd-cli` running.

    .venv/bin/python tests/e2e/flux2-klein/contention.py
"""
from __future__ import annotations

import fcntl
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence" / "contention"

CLI = ROOT / "bin" / "coltman-images"
MODEL_ALIAS = "flux2-klein-4b-gguf-q4"
LOCK = ROOT / "run" / "server.lock"
STATE = ROOT / "run" / "server.json"
HEALTH = "http://127.0.0.1:8420/health"

CHILDREN: list[subprocess.Popen] = []
"""Every child this script spawned, so nothing is left on the card on any exit path."""

SD = ROOT / "vendor/stable-diffusion.cpp/build/bin/sd-cli"
MODEL = ROOT / "model/assets/flux2-klein/gguf/flux-2-klein-4b-Q4_K_M.gguf"
VAE = ROOT / "model/assets/flux2-klein/official/vae/diffusion_pytorch_model.safetensors"
LLM = ROOT / "model/assets/flux2-klein/gguf/Qwen3-4B-Q4_K_M.gguf"

PROMPT = ("Photorealistic scene inside a dimly lit bar: six people around a round poker "
          "table, one of them dealing playing cards, chips and half-empty glasses on the "
          "green felt, a bartender in a white shirt and apron wiping a glass behind a "
          "wooden counter, warm tungsten lamps, cigarette smoke in the air, shallow depth "
          "of field, 50mm lens")
SEED, WIDTH, HEIGHT = 7, 1024, 1024


# --- observations ------------------------------------------------------------


def sdcli_count() -> int:
    """`pgrep -c sd-cli`, read as a number. pgrep exits 1 when it finds none."""
    done = subprocess.run(["pgrep", "-c", "sd-cli"], capture_output=True, text=True)
    text = (done.stdout or "").strip()
    return int(text) if text.isdigit() else 0


def gpu_used() -> int:
    done = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                          capture_output=True, text=True)
    try:
        return int(done.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0


def health() -> dict | None:
    try:
        with urllib.request.urlopen(HEALTH, timeout=1.5) as response:
            return json.loads(response.read())
    except Exception:  # noqa: BLE001 — absence is the answer this helper reports
        return None


def lock_held() -> tuple[bool, str]:
    """Whether `run/server.lock` is held right now, and by whom the file says."""
    if not LOCK.exists():
        return False, ""
    handle = open(LOCK, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.seek(0)
            return True, handle.read().strip()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False, ""
    finally:
        handle.close()


def run(args: list[str], timeout: float = 300.0) -> dict:
    started = time.perf_counter()
    done = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    return {
        "cmd": " ".join(args),
        "exit": done.returncode,
        "stdout": done.stdout.strip(),
        "stderr": done.stderr.strip(),
        "wall_s": round(time.perf_counter() - started, 1),
    }


def start_server() -> dict:
    return run([str(CLI), "start", "--model", MODEL_ALIAS])


def stop_server() -> dict:
    return run([str(CLI), "stop"])


def generate(tag: str, out_dir: pathlib.Path) -> dict:
    return run([
        str(CLI), "generate",
        "--prompt", PROMPT,
        "--seed", str(SEED),
        "--width", str(WIDTH),
        "--height", str(HEIGHT),
        "--out", str(out_dir / f"{tag}.png"),
        "--model", MODEL_ALIAS,
        "--json",
    ])


class Sampler(threading.Thread):
    """Samples `pgrep -c sd-cli` and device memory every 100 ms until stopped."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.max_sdcli = 0
        self.max_gpu = 0
        self.samples = 0

    def run(self) -> None:
        while not self.stop.is_set():
            self.max_sdcli = max(self.max_sdcli, sdcli_count())
            self.max_gpu = max(self.max_gpu, gpu_used())
            self.samples += 1
            time.sleep(0.1)


def clean_start() -> None:
    """Refuse to measure on a dirty card: no state file, no server, no child."""
    if STATE.exists():
        raise SystemExit(f"refused: {STATE} exists — stop the server first")
    held, holder = lock_held()
    if held:
        raise SystemExit(f"refused: {LOCK} is held by pid {holder} — stop the server first")
    if sdcli_count():
        raise SystemExit("refused: an sd-cli process is already running")


def afterwards() -> dict:
    held, holder = lock_held()
    return {
        "sdcli_processes": sdcli_count(),
        "state_file_exists": STATE.exists(),
        "lock_held": held,
        "lock_file_holder": holder,
        "server_answering": health() is not None,
    }


# --- the three scenarios -----------------------------------------------------


def scenario_a(out_dir: pathlib.Path) -> dict:
    """Two `generate` calls at once: one worker, one `sd-cli` at a time."""
    started = start_server()
    if started["exit"] != 0:
        return {"scenario": "A", "start": started, "ok": False, "error": "start failed"}

    sampler = Sampler()
    sampler.start()
    began = time.perf_counter()
    first = subprocess.Popen(
        [str(CLI), "generate", "--prompt", PROMPT, "--seed", str(SEED),
         "--width", str(WIDTH), "--height", str(HEIGHT),
         "--out", str(out_dir / "concurrent-a.png"), "--model", MODEL_ALIAS, "--json"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = subprocess.Popen(
        [str(CLI), "generate", "--prompt", PROMPT, "--seed", str(SEED),
         "--width", str(WIDTH), "--height", str(HEIGHT),
         "--out", str(out_dir / "concurrent-b.png"), "--model", MODEL_ALIAS, "--json"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out_a, err_a = first.communicate(timeout=300)
    out_b, err_b = second.communicate(timeout=300)
    window = round(time.perf_counter() - began, 1)
    sampler.stop.set()
    sampler.join(timeout=2)
    stopped = stop_server()

    def parse(text: str) -> dict | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    body_a, body_b = parse(out_a), parse(out_b)
    ordered = sorted(
        [b for b in (body_a, body_b) if b], key=lambda b: b["duration_s"]
    )
    return {
        "scenario": "A",
        "ok": first.returncode == 0 and second.returncode == 0,
        "start": started,
        "concurrent_window_s": window,
        "max_sdcli_processes": sampler.max_sdcli,
        "max_device_mib": sampler.max_gpu,
        "sampler_samples": sampler.samples,
        "requests": [
            {"exit": first.returncode, "stderr": err_a.strip(), "response": body_a},
            {"exit": second.returncode, "stderr": err_b.strip(), "response": body_b},
        ],
        "serialisation": {
            "shorter_duration_s": ordered[0]["duration_s"] if ordered else None,
            "longer_duration_s": ordered[-1]["duration_s"] if ordered else None,
            "ratio": (round(ordered[-1]["duration_s"] / ordered[0]["duration_s"], 3)
                      if len(ordered) == 2 and ordered[0]["duration_s"] else None),
        },
        "stop": stopped,
        "afterwards": afterwards(),
    }


def scenario_b(out_dir: pathlib.Path) -> dict:
    """`stop` arriving mid-render: drain, then leave nothing behind."""
    started = start_server()
    if started["exit"] != 0:
        return {"scenario": "B", "start": started, "ok": False, "error": "start failed"}

    sampler = Sampler()
    sampler.start()
    render = subprocess.Popen(
        [str(CLI), "generate", "--prompt", PROMPT, "--seed", str(SEED),
         "--width", str(WIDTH), "--height", str(HEIGHT),
         "--out", str(out_dir / "mid-render.png"), "--model", MODEL_ALIAS, "--json"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Wait until the child is on the card, then ask the server to stop under it.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and sdcli_count() == 0:
        time.sleep(0.1)
    saw_child = sdcli_count() > 0
    stop = stop_server()
    render_out, render_err = render.communicate(timeout=300)
    sampler.stop.set()
    sampler.join(timeout=2)

    try:
        body = json.loads(render_out)
    except json.JSONDecodeError:
        body = None
    return {
        "scenario": "B",
        "ok": stop["exit"] == 0,
        "start": started,
        "child_seen_before_stop": saw_child,
        "stop": stop,
        "render": {"exit": render.returncode, "stderr": render_err.strip(), "response": body},
        "still_written": (out_dir / "mid-render.png").exists(),
        "max_sdcli_processes": sampler.max_sdcli,
        "max_device_mib": sampler.max_gpu,
        "afterwards": afterwards(),
    }


def scenario_c(out_dir: pathlib.Path) -> dict:
    """A fresh `start` while a hand-launched `sd-cli` loads the card, holding no lock."""
    bare_out = out_dir / "bare-sdcli.png"
    bare_out.unlink(missing_ok=True)
    bare = subprocess.Popen(
        [str(SD), "--diffusion-model", str(MODEL), "--vae", str(VAE), "--llm", str(LLM),
         "-p", PROMPT, "--cfg-scale", "1.0", "--steps", "4",
         "-W", str(WIDTH), "-H", str(HEIGHT), "-s", str(SEED), "-o", str(bare_out),
         "--offload-to-cpu"],
        cwd=str(ROOT), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    CHILDREN.append(bare)

    sampler = Sampler()
    sampler.start()
    time.sleep(0.4)  # let the bare child claim the card first
    bare_running_before_start = sdcli_count()
    held_before_start, holder_before_start = lock_held()

    started = start_server()
    server_answered = health() is not None
    boot_gpu = gpu_used()

    stopped = stop_server() if server_answered else {"cmd": "stop (skipped)", "exit": None}
    sampler.stop.set()
    bare_out_text, bare_err_text = bare.communicate(timeout=300)
    sampler.join(timeout=2)

    return {
        "scenario": "C",
        "ok": True,  # a finding either way; see the module docstring
        "bare_child_running_before_start": bare_running_before_start,
        "lock_held_before_start": held_before_start,
        "lock_holder_before_start": holder_before_start,
        "start": started,
        "server_answered_after_start": server_answered,
        "boot_device_mib": boot_gpu,
        "max_sdcli_processes": sampler.max_sdcli,
        "max_device_mib": sampler.max_gpu,
        "bare_child": {
            "exit": bare.returncode,
            "wrote_still": bare_out.is_file(),
            "stderr_tail": "\n".join((bare_err_text or bare_out_text or "").splitlines()[-6:]),
        },
        "stop": stopped,
        "afterwards": afterwards(),
    }


def main() -> int:
    clean_start()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for name, fn in (("A", scenario_a), ("B", scenario_b), ("C", scenario_c)):
            print(f"scenario {name} —", flush=True)
            result = fn(EVIDENCE)
            results.append(result)
            print(f"  {json.dumps(result.get('afterwards', result), ensure_ascii=False)}", flush=True)
            time.sleep(1.0)
    finally:
        # Never leave a server or a child behind, whatever happened above.
        run([str(CLI), "stop"])
        for child in CHILDREN:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=15)

    payload = {"ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results}
    (EVIDENCE / "contention.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nevidence: {EVIDENCE / 'contention.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
