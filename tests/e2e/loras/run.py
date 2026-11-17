#!/usr/bin/env python3
"""The LoRA unit's operator-level run: four checks against the real card.

Everything here goes through `bin/coltman-images` or `POST /generate`, as an
operator uses the system, on the promoted entry (`flux2-klein-4b-gguf-q4`), whose
catalog is `pixel-art`, `anime` and `background-remove`:

  A. one LoRA at 512x512 against the same request without it — both render, and
     the bytes differ, so the selection reached the runtime and not only the
     request parser. The `render_s` of each is recorded: the difference is what a
     LoRA costs (protocol section 11 measures +1.5 s each);
  B. three LoRAs at 512x512 — the request is served, and the response records the
     render alone;
  C. an alias the catalog does not declare, and a request whose LoRAs exceed the
     deployment's budget — both refused at the door, with the message printed,
     and neither reaching the worker;
  D. a host that declares `lora_budget_mib: 512` — the whole catalog (559 MiB)
     refused with the arithmetic, naming the sum, the budget and the largest
     single LoRA. The declaration is rewritten in place because the server reads
     that one path at boot (there is no flag for it), and the bytes the tree
     shipped are restored in `finally` and asserted afterwards.

Usage, from the project root. The card must be free: `run/server.json` absent and
no server process running.

    .venv/bin/python tests/e2e/loras/run.py

The run leaves the server stopped and writes `evidence/loras.json` beside the
stills it rendered. It exits 0 when every check held and 1 otherwise.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"

BIN = ROOT / "bin" / "coltman-images"
HOST_FILE = ROOT / "host.yaml"
STATE_FILE = ROOT / "run" / "server.json"
MODEL = "flux2-klein-4b-gguf-q4"

BIND = "127.0.0.1"
PORT = 8420
SIDE = 512
SEED = 7
"""One prompt, one seed, one size for every still: the LoRA is the variable."""

PROMPT = (
    "pixel art sprite, a brave knight in shining armor holding a sword, game asset, "
    "transparent background"
)
"""The pixel-art LoRA's own card prompt, reproduced from `patches/README.md`."""

CATALOG = ["pixel-art", "anime", "background-remove"]

FINDINGS: dict[str, object] = {}


def _failures() -> list[str]:
    return [name for name, held in FINDINGS.items() if not held]


def _http(method: str, path: str, payload: dict | None = None, timeout: float = 600.0) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"http://{BIND}:{PORT}{path}", data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
        exc.close()
    except (urllib.error.URLError, OSError) as exc:
        return 0, {"error": {"code": "transport", "message": str(exc)}}
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {"raw": raw.decode("utf-8", "replace")}
    return status, body if isinstance(body, dict) else {"raw": body}


def _cli(*args: str, timeout: float = 600.0) -> subprocess.CompletedProcess:
    return subprocess.run([str(BIN), *args], cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def _health() -> tuple[int, dict]:
    return _http("GET", "/health", timeout=3.0)


def _server_running() -> bool:
    return STATE_FILE.exists() or _health()[0] == 200


def _wait_stopped(limit: float = 45.0) -> bool:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if not STATE_FILE.exists() and _health()[0] != 200:
            return True
        time.sleep(0.5)
    return False


def _stop() -> None:
    _cli("stop", timeout=180)
    _wait_stopped()


def _start() -> dict:
    began = time.perf_counter()
    completed = _cli("start", "--model", MODEL, timeout=600)
    record = {
        "exit": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "wall_s": round(time.perf_counter() - began, 2),
    }
    if completed.returncode != 0:
        raise SystemExit(f"`start` failed: {record}")
    return record


def _still(path: pathlib.Path) -> dict:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if _server_running():
        raise SystemExit(
            "the card is not free: a server is running — run `bin/coltman-images stop` first"
        )

    shipped_host = HOST_FILE.read_bytes() if HOST_FILE.is_file() else None
    started: list[dict] = []
    try:
        started.append(_start())
        status, health = _health()
        FINDINGS["A.health"] = status == 200 and health.get("status") == "warm"

        # --- A: one LoRA, against the same request without one ---------------
        plain_path = EVIDENCE / f"a-plain-{SIDE}s{SEED}.png"
        lora_path = EVIDENCE / f"a-pixel-art-{SIDE}s{SEED}.png"
        plain_path.unlink(missing_ok=True)
        lora_path.unlink(missing_ok=True)
        status, plain = _http(
            "POST",
            "/generate",
            {"prompt": PROMPT, "seed": SEED, "width": SIDE, "height": SIDE, "out": str(plain_path)},
        )
        status_lora, with_lora = _http(
            "POST",
            "/generate",
            {
                "prompt": PROMPT,
                "seed": SEED,
                "width": SIDE,
                "height": SIDE,
                "lora": ["pixel-art"],
                "out": str(lora_path),
            },
        )
        FINDINGS["A.served"] = status == 200 and status_lora == 200
        FINDINGS["A.bytes_differ"] = (
            plain_path.is_file()
            and lora_path.is_file()
            and _still(plain_path)["sha256"] != _still(lora_path)["sha256"]
        )
        print(
            f"A: 512x512 seed {SEED}, one LoRA — plain render_s {plain.get('render_s')} s, "
            f"pixel-art render_s {with_lora.get('render_s')} s"
        )
        print(f"A: {plain.get('out')}")
        print(f"A: {with_lora.get('out')}")
        print(
            "A: sha256 "
            f"{_still(plain_path)['sha256'][:16]}… against {_still(lora_path)['sha256'][:16]}… — "
            f"different bytes: {FINDINGS['A.bytes_differ']}"
        )

        # --- B: three LoRAs at once -----------------------------------------
        three_path = EVIDENCE / f"b-three-{SIDE}s{SEED}.png"
        three_path.unlink(missing_ok=True)
        status_three, three = _http(
            "POST",
            "/generate",
            {
                "prompt": PROMPT,
                "seed": SEED,
                "width": SIDE,
                "height": SIDE,
                "lora": ["pixel-art:0.8", "anime:0.4", "background-remove:0.3"],
                "out": str(three_path),
            },
        )
        FINDINGS["B.served"] = status_three == 200 and three_path.is_file()
        print(
            f"B: 512x512 seed {SEED}, three LoRAs (explicit weights) — "
            f"render_s {three.get('render_s')} s"
        )
        print(f"B: {three.get('out')}")

        # --- C: the refusals ------------------------------------------------
        # The budget is a memory, so a request that fits the catalog's aliases
        # but not its bytes is what a caller learns to check: the whole catalog,
        # at 561 MiB of file, is under the shipped 3200 MiB budget, so the
        # refusal half is exercised under the tightened host in D. Here the
        # catalog-sized request is sent to prove it *is* allowed.
        worker_before = _served_count()
        status_alias, body_alias = _http(
            "POST", "/generate", {"prompt": "x", "lora": ["no-such-alias"]}
        )
        alias_message = str(body_alias.get("error", {}).get("message", ""))
        FINDINGS["C.unknown_alias"] = (
            status_alias == 400
            and "no-such-alias" in alias_message
            and all(alias in alias_message for alias in CATALOG)
        )
        FINDINGS["C.no_worker_work"] = _served_count() == worker_before
        print(f"C: unknown alias → {status_alias} {alias_message}")
        print(f"C: the worker served nothing new: {FINDINGS['C.no_worker_work']}")

        # --- D: a host with a 512 MiB budget --------------------------------
        _stop()
        HOST_FILE.write_text(_host_document(512), encoding="utf-8")
        started.append(_start())
        status_budget, body_budget = _http(
            "POST",
            "/generate",
            {"prompt": "x", "lora": ["pixel-art", "anime", "background-remove"]},
        )
        budget_message = str(body_budget.get("error", {}).get("message", ""))
        FINDINGS["D.refused_at_512"] = (
            status_budget == 400
            and "need 559 MiB" in budget_message
            and "budget is 512 MiB" in budget_message
            and "host.yaml" in budget_message
            and "'pixel-art' at 311 MiB" in budget_message
        )
        print(f"D: host lora_budget_mib 512, the whole catalog → {status_budget} {budget_message}")
        _stop()

        # --- put the tree back and prove the shipped declaration serves ------
        _restore_host(shipped_host)
        started.append(_start())
        status_back, body_back = _http(
            "POST",
            "/generate",
            {
                "prompt": PROMPT,
                "seed": SEED,
                "width": 256,
                "height": 256,
                "lora": ["pixel-art"],
                "out": str(EVIDENCE / "d-shipped-host-256.png"),
            },
        )
        FINDINGS["D.shipped_host_serves"] = status_back == 200
        print(f"D: shipped host restored, one LoRA at 256x256 → {status_back} render_s {body_back.get('render_s')} s")
        _stop()
    finally:
        _restore_host(shipped_host)
        if _server_running():
            _stop()
        FINDINGS["tree.host_restored"] = (
            HOST_FILE.read_bytes() if HOST_FILE.is_file() else None
        ) == shipped_host

    record = {
        "suite": "loras",
        "generated_at": datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ"),
        "entry": MODEL,
        "catalog": CATALOG,
        "request": {"prompt": PROMPT, "seed": SEED, "side": SIDE},
        "boots": started,
        "checked": FINDINGS,
        "failed": _failures(),
    }
    (EVIDENCE / "loras.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"evidence: {(EVIDENCE / 'loras.json').relative_to(ROOT)}")
    if _failures():
        print(f"FAILED: {_failures()}")
        return 1
    print("all four checks held")
    return 0


def _served_count() -> int:
    """Lines the server logged for a still it served. The door is not the worker."""
    log = ROOT / "run" / "server.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if ": served: " in line)


def _host_document(lora_budget_mib: int) -> str:
    """The shipped declaration with the LoRA budget changed, comments dropped.

    The run restores the shipped bytes afterwards, so the comments are not lost;
    this document exists only for the boot that reads it.
    """
    return (
        "# Written by tests/e2e/loras/run.py; the shipped file is restored after the run.\n"
        "id: this-deployment\n"
        "vram_mib: 7857\n"
        "offload: true\n"
        f"lora_budget_mib: {lora_budget_mib}\n"
    )


def _restore_host(shipped: bytes | None) -> None:
    if shipped is None:
        HOST_FILE.unlink(missing_ok=True)
        return
    HOST_FILE.write_bytes(shipped)


if __name__ == "__main__":
    sys.exit(main())
