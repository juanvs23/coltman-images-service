#!/usr/bin/env python3
"""Record the page's component tree, so the layout claim has an artifact.

The page is gradio's, so its tree is gradio's config: this builds the Blocks
in-process (no server, no card, no model) and prints the row/column skeleton with
each column's `scale`, then writes it to `evidence/layout-tree.json`.

What it can and cannot prove: it proves the *structure* — one row with two columns
of equal scale, controls in the first, the still and its details in the second —
and the controls' configuration. It does not prove how a browser paints them.

The entry is read as a declaration rather than resolved: `load_entry` would hash
6.29 GB to draw a page, and the layout only needs the fields the page reads.
"""

from __future__ import annotations

import json
import pathlib
import sys
import types

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
EVIDENCE = ROOT / "tests" / "e2e" / "p9-ui" / "evidence"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coltman_images import ui  # noqa: E402 — after sys.path, and it imports gradio

ENTRY = ROOT / "model" / "entry.yaml"
UPSCALER = ROOT / "model" / "upscaler.yaml"


def main() -> int:
    declaration = yaml.safe_load(ENTRY.read_text(encoding="utf-8"))
    stage = yaml.safe_load(UPSCALER.read_text(encoding="utf-8"))
    entry = types.SimpleNamespace(
        defaults=dict(declaration["defaults"]),
        max_pixels=int(declaration["limits"]["max_pixels"]),
        steps=int(declaration["steps"]),
        steps_min=int(declaration["limits"]["steps"]["min"]),
        steps_max=int(declaration["limits"]["steps"]["max"]),
    )
    app = types.SimpleNamespace(
        entry=entry,
        declaration=types.SimpleNamespace(scale=int(stage["scale"])),
        submit=lambda request: request,
        depth=lambda: 0,
    )
    page = ui.build(app)
    components = {component["id"]: component for component in page.config["components"]}
    layout = page.config["layout"]

    root = layout["children"]
    assert len(root) == 1, f"the page is not one root: {root}"
    row = components[root[0]["id"]]
    columns = [components[child["id"]] for child in root[0]["children"]]
    controls, result = columns
    leaves = {
        "controls": [
            components[child["id"]]["type"] if not components[child["id"]].get("children") else "container"
            for child in root[0]["children"][0]["children"]
        ],
        "result": [
            components[child["id"]]["type"] for child in root[0]["children"][1]["children"]
        ],
    }
    tree = {
        "root": row["type"],
        "columns": [
            {"id": column["id"], "scale": column["props"].get("scale"), "min_width": column["props"].get("min_width")}
            for column in columns
        ],
        "equal_height": row["props"].get("equal_height"),
        "controls_children": leaves["controls"],
        "result_children": leaves["result"],
        "steps": {
            key: next(
                component["props"].get(key)
                for component in page.config["components"]
                if component["type"] == "slider"
            )
            for key in ("minimum", "maximum", "step", "value", "precision", "label", "info")
        },
        "aspect": {
            key: next(
                component["props"].get(key)
                for component in page.config["components"]
                if component["type"] == "radio" and component["props"].get("label") == "aspect"
            )
            for key in ("choices", "value", "label")
        },
    }
    print(json.dumps(tree, indent=2))

    problems = []
    if len(columns) != 2:
        problems.append(f"the row holds {len(columns)} columns, not 2")
    if {column["props"].get("scale") for column in columns} != {1}:
        problems.append("the columns are not both scale=1")
    if leaves["result"] != ["markdown", "image", "markdown"]:
        problems.append(f"the result half is {leaves['result']}, not status/still/details")
    shapes = [choice[0] for choice in (tree["aspect"]["choices"] or [])]
    if shapes != ["16:9", "1:1", "4:3", "3:4", "9:16"]:
        problems.append(f"the aspect control offers {shapes}, not the operator's five")
    if tree["aspect"]["value"] != "16:9":
        problems.append(f"the aspect control starts at {tree['aspect']['value']!r}, not 16:9")
    slider = tree["steps"]
    if (slider["minimum"], slider["maximum"], slider["value"]) != (
        entry.steps_min,
        entry.steps_max,
        entry.steps,
    ):
        problems.append(f"the steps control is not the entry's ladder: {slider}")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / "layout-tree.json"
    destination.write_text(json.dumps(tree, indent=2) + "\n", encoding="utf-8")
    print(f"layout: {'FAILED — ' + '; '.join(problems) if problems else 'ok'} → {destination.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
