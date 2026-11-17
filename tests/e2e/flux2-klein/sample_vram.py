#!/usr/bin/env python3
"""Sample the card's used memory while something else runs, and report the peak.

Protocol section 10's checks ask for the peak to be sampled with
`nvidia-smi --query-gpu=memory.used` every 250 ms during every measurement. This
script is that sampler, so the number in `docs/reference/flux2-klein.md` has a
command behind it and not a memory of one.

    sample_vram.py --csv evidence/fp8-1024-vram.csv &
    ... run the render ...
    kill %1        # SIGTERM: the sampler writes the peak to stdout and exits

The CSV is one `unix_seconds,used_mib` line per sample; the peak is printed as
`peak_used_mib=<n> samples=<n>` on SIGTERM or SIGINT.
"""

from __future__ import annotations

import argparse
import pathlib
import signal
import subprocess
import sys
import time

QUERY = "memory.used"
FORMAT = "csv,noheader,nounits"


def _used() -> int:
    completed = subprocess.run(
        ["nvidia-smi", f"--query-gpu={QUERY}", f"--format={FORMAT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(completed.stdout.strip().splitlines()[0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sample the card's used memory and report its peak.")
    parser.add_argument("--csv", required=True, help="where to write the samples")
    parser.add_argument("--interval", type=float, default=0.25, help="seconds between samples")
    args = parser.parse_args(argv)

    path = pathlib.Path(args.csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    samples: list[tuple[float, int]] = []
    stopping = {"stop": False}

    def _stop(_signum, _frame) -> None:
        stopping["stop"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    with path.open("w", encoding="utf-8") as handle:
        handle.write("unix_seconds,used_mib\n")
        handle.flush()
        while not stopping["stop"]:
            try:
                used = _used()
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                print(f"sample_vram: {exc}", file=sys.stderr)
                break
            stamp = time.time()
            samples.append((stamp, used))
            handle.write(f"{stamp:.3f},{used}\n")
            handle.flush()
            time.sleep(args.interval)

    if not samples:
        print("sample_vram: no sample was taken", file=sys.stderr)
        return 1
    peak = max(used for _stamp, used in samples)
    print(f"peak_used_mib={peak} samples={len(samples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
