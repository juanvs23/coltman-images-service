#!/usr/bin/env python3
"""Drive the P9 page the way a browser would, and record what it showed.

The page is gradio's, so the only honest way to submit through it without a
browser is gradio's own client module — not the page's HTTP details, which are
gradio's to change. What comes back is exactly what the page displays: the status
line, the still and the result panel, one tuple per yielded update.

Usage, against a server already started with `--ui`, from the project root:

    .venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality SD
    .venv/bin/python tests/e2e/p9-ui/drive.py --prompt "a lighthouse at dusk" --seed 7 --quality HD

It writes `<evidence>/<quality>-transcript.json` and nothing else; the still
itself is written by the server into `out/`, and its path is in the transcript.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time

from gradio_client import Client

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
EVIDENCE = ROOT / "tests" / "e2e" / "p9-ui" / "evidence"
BIND = "127.0.0.1"


def _flatten(value: object) -> object:
    """A yielded output, as JSON — a downloaded file becomes its local path."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {key: _flatten(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_flatten(item) for item in value]
    return str(value)


def drive(ui_port: int, prompt: str, seed: int | None, quality: str) -> dict:
    # `download_files=None`: the client returns where the page served the file
    # from instead of copying it into a temp folder of its own. The still the
    # server wrote is named in the result panel either way.
    client = Client(f"http://{BIND}:{ui_port}/", verbose=False, download_files=None)
    began = time.perf_counter()
    job = client.submit(prompt, seed, quality, api_name="/generate")
    updates = []
    for update in job:
        updates.append({"after_s": round(time.perf_counter() - began, 2), "update": _flatten(update)})
    return {
        "ui": f"http://{BIND}:{ui_port}/",
        "prompt": prompt,
        "seed": seed,
        "quality": quality,
        "updates": updates,
        "wall_s": round(time.perf_counter() - began, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-port", type=int, default=7860)
    parser.add_argument("--prompt", default="a lighthouse at dusk")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--quality", choices=["SD", "HD"], default="SD")
    parser.add_argument(
        "--label",
        default=None,
        help="name the transcript after this instead of the quality (two runs at once need two names)",
    )
    args = parser.parse_args(argv)

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    transcript = drive(args.ui_port, args.prompt, args.seed, args.quality)
    label = args.label or args.quality.lower()
    destination = EVIDENCE / f"{label}-transcript.json"
    destination.write_text(json.dumps(transcript, indent=2) + "\n", encoding="utf-8")

    for update in transcript["updates"]:
        status, still, details = (update["update"] + [None, None, None])[:3]
        print(f"[{update['after_s']:>6.2f} s] status: {status}")
    print(f"--- the result panel as the page showed it ---")
    print(details)
    print(f"drive: {len(transcript['updates'])} updates in {transcript['wall_s']} s → {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
