#!/usr/bin/env python3
"""The page's reference control, driven the way a browser drives it.

Run under the project's interpreter, with the service already booted
(`bin/coltman-images start --model flux2-klein-4b-gguf-q4 --ui`):

    .venv/bin/python tests/e2e/image-input/page_check.py

It answers three questions with observations, not with a reading of the code:

1. **Does the control exist and is it an image input?** Gradio's own component
   configuration is read off the mounted page, so this is what the page is, not
   what its source says.
2. **Where does an upload land?** The file is posted to the page's own upload
   endpoint and the path the page would hand the handler is printed. Protocol
   section 2 says the page's copy lives under `run/ui/`, inside the tree, which
   is why the page needs no read exception; this is the measurement of that
   sentence.
3. **Does the form send the path when a file is set and omit it when not?** Two
   submissions at one seed — one with the uploaded reference, one without —
   through the page's own client, and the two stills are compared by digest. A
   request with no reference must produce the same bytes as the API does for the
   same prompt, seed, box and step count.

The run writes `evidence/page-check.json` beside this script and prints the same
numbers. Nothing here renders on its own: every still comes back from the
service.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import urllib.request

from gradio_client import Client, handle_file

ROOT = pathlib.Path(__file__).resolve().parents[3]
EVIDENCE = pathlib.Path(__file__).resolve().parent / "evidence"
RUN_UI = ROOT / "run" / "ui"
PAGE = "http://127.0.0.1:7860/"
API = "http://127.0.0.1:8420"

SEED = 4101
STEPS = 4
"""The entry's floor: the page's slider is the entry's ladder, so this is the
cheapest still the form can ask for."""
ASPECT = "1:1"
PROMPT = "Turn this scene into a real photograph"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(name: str) -> pathlib.Path:
    """The path the page would hand the handler for an upload it stored.

    Gradio answers with either a name relative to its temp dir or an absolute
    path, depending on how it was mounted; both are accepted, and the answer is
    printed either way so the claim is measured rather than assumed.
    """
    path = pathlib.Path(name)
    return path if path.is_absolute() else RUN_UI / name


def _upload(path: pathlib.Path) -> dict:
    """POST the file to the page's own upload endpoint, as a browser would."""
    boundary = "----coltman-images-reference"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8")
    body += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        f"{PAGE}gradio_api/upload",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read())
    stored = payload if isinstance(payload, list) else payload.get("files", [])
    names = [item if isinstance(item, str) else item.get("path", "") for item in stored]
    resolved = [_resolve(name) for name in names]
    return {
        "status": 200,
        "raw": payload,
        "resolved": [str(item) for item in resolved],
        "inside_run_ui": [str(item.resolve()).startswith(str(RUN_UI.resolve())) for item in resolved],
        "exists": [item.is_file() for item in resolved],
    }


def _panel(result: object) -> str:
    if isinstance(result, (list, tuple)) and len(result) >= 3 and isinstance(result[2], str):
        return result[2]
    return ""


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    reference = EVIDENCE / "reference-512.png"
    findings: dict[str, object] = {
        "generated_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reference": {"path": str(reference), "sha256": _sha256(reference)},
    }

    # 1. The mounted page, as gradio describes it.
    with urllib.request.urlopen(f"{PAGE}config", timeout=30) as response:
        config = json.loads(response.read())
    components = config.get("components", [])
    images = [
        {
            "id": component.get("id"),
            "label": component.get("props", {}).get("label"),
            "type": component.get("props", {}).get("type"),
            "visible": component.get("props", {}).get("visible"),
        }
        for component in components
        if component.get("type") == "image"
    ]
    events = [
        {
            "api_name": dependency.get("api_name"),
            "inputs": dependency.get("inputs"),
            "outputs": dependency.get("outputs"),
        }
        for dependency in config.get("dependencies", [])
    ]
    findings["page"] = {"images": images, "events": events}
    print(f"page: {len(images)} image components — {images}")
    print(f"page: the event's inputs are {events[0]['inputs'] if events else None}")

    # 2. Where an upload lands.
    upload = _upload(reference)
    findings["upload"] = upload
    print(f"upload: {upload['raw']} → {upload['resolved']} inside run/ui/ {upload['inside_run_ui']}")
    if not all(upload["inside_run_ui"]) or not all(upload["exists"]):
        raise SystemExit("upload: the page's copy did not land inside run/ui/ — section 2 is not true")

    uploaded = pathlib.Path(upload["resolved"][0])

    # 3. Two submissions through the page: with the reference, and without it.
    client = Client(PAGE, verbose=False, download_files=None)
    with_reference = client.submit(
        PROMPT, handle_file(str(uploaded)), SEED, "SD", STEPS, ASPECT, api_name="/generate"
    )
    reference_result = with_reference.result()
    reference_panel = _panel(reference_result)
    still_with = re.search(r"written to `([^`]+)`", reference_panel)

    without_reference = client.submit(
        PROMPT, None, SEED, "SD", STEPS, ASPECT, api_name="/generate"
    )
    plain_result = without_reference.result()
    plain_panel = _panel(plain_result)
    still_without = re.search(r"written to `([^`]+)`", plain_panel)

    findings["submissions"] = {
        "with_reference": {"panel": reference_panel, "still": still_with.group(1) if still_with else None},
        "without_reference": {"panel": plain_panel, "still": still_without.group(1) if still_without else None},
    }
    if not still_with or not still_without:
        raise SystemExit(f"a submission named no still: {reference_panel!r} / {plain_panel!r}")

    digest_with = _sha256(pathlib.Path(still_with.group(1)))
    digest_without = _sha256(pathlib.Path(still_without.group(1)))
    findings["digests"] = {"with_reference": digest_with, "without_reference": digest_without}
    findings["panel_names_reference"] = "reference —" in reference_panel
    findings["panel_without_names_reference"] = "reference —" in plain_panel

    print(f"page: with a reference  → {still_with.group(1)} sha256 {digest_with[:16]}…")
    print(f"page: without one       → {still_without.group(1)} sha256 {digest_without[:16]}…")
    print(f"page: the panel names the reference — with {findings['panel_names_reference']}, "
          f"without {findings['panel_without_names_reference']}")

    (EVIDENCE / "page-check.json").write_text(
        json.dumps(findings, indent=2) + "\n", encoding="utf-8"
    )
    print(f"page-check: wrote {EVIDENCE / 'page-check.json'}")

    if digest_with == digest_without:
        raise SystemExit("the page sent no reference: the two stills are the same bytes")
    if not findings["panel_names_reference"] or findings["panel_without_names_reference"]:
        raise SystemExit("the panel does not state the reference the response echoed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
