"""The web UI — presentation for the one seam, and nothing else.

A browser cannot read a filesystem path, a request costs ~46 s, and the queue is
single-flight: those three facts decide this module. It renders one page, it
calls `WarmServer.submit()` for a still, and it does neither of the two things
that would make it a second implementation — it never reaches a model, and it
never enqueues work of its own (protocol section 9 rule 8, one producer).

Four things live here, in this order, and nothing else — with one private helper,
`_hd_size`, because the HD size is arithmetic derived from the entry's ceiling and
the builder must not restate it:

1. `request_from_form` — pure. Builds the protocol section 4.1 request the form
   describes, from the entry's own defaults and ceiling. It reads no constant of
   its own: `limits.max_pixels`, `defaults.width` and `defaults.height` are
   per-entry, and the next entry will not be 1280x720.
2. `render` — one line, `app.submit(request)`. This is the UI's only route to a
   still, and its existence is what guard 13 asserts structurally.
3. `generate` — a generator. `submit()` blocks for the whole render, so the
   submission runs in a worker thread and a status line is yielded every half
   second until the result is ready: a request behind another one must not look
   like a hang, and the queue depth is the only thing that tells the operator
   why a page is quiet.
4. `build` — the page. Presentation only: no validation, no request shaping, no
   knowledge of a model. The adapter's census keys are never written here; they
   are rendered as the response declares them, because protocol section 6.1
   makes the adapter the owner of what a census key means and the next model has
   no FP8 at all.

Gradio is the first rendering of this, behind that seam: replacing it is
replacing `build` and nothing else (protocol section 5.5).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Iterator

import gradio as gr

__all__ = ["build", "generate", "render", "request_from_form"]

STATUS_TICK_S = 0.5
"""How long the status line waits between refreshes while a submission is in flight.

Half a second is the roadmap's number, and it is a UI decision, not a service
one: the render costs ~46 s, so a line that moved twice a second would be noise
and one that moved every ten seconds would look like a hang.
"""

SD_LABEL = "SD"
"""The two labels of the quality switch. They are the operator's words, not the
protocol's: the request carries a size and a permission, and the response says
which one was delivered."""

HD_LABEL = "HD"


def _hd_size(entry: Any, factor: int) -> tuple[int, int]:
    """The largest box of the entry's aspect that the declared stage can serve.

    The stage's reach is `max_pixels x factor²` (section 6.2), so HD is the
    biggest multiple-of-16 box inside that reach with the entry's own aspect —
    the base it will be enlarged from stays the entry's shape. Derived from the
    ceiling, never from the defaults times the factor: those only clear the
    ceiling while the defaults sit at it, and a future entry with smaller
    defaults would get a native render labelled HD.
    """
    width = int(entry.defaults["width"])
    height = int(entry.defaults["height"])
    cap = int(entry.max_pixels) * int(factor) * int(factor)
    grid = 1 << 16

    def snapped(numerator: int) -> tuple[int, int]:
        return (width * numerator // grid // 16 * 16, height * numerator // grid // 16 * 16)

    low, high, best = 1, grid * 128, None
    while low <= high:
        middle = (low + high) // 2
        box_width, box_height = snapped(middle)
        if box_width >= 256 and box_height >= 256 and box_width * box_height <= cap:
            best = (box_width, box_height)
            low = middle + 1
        else:
            high = middle - 1
    if best is None:
        raise ValueError(
            f"HD: the {width}x{height} defaults leave no multiple-of-16 box inside the "
            f"{cap} px the stage can serve"
        )
    if best[0] * best[1] <= int(entry.max_pixels):
        raise ValueError(
            f"HD: the largest box inside the stage's {cap} px reach is {best[0]}x{best[1]}, "
            f"which does not clear the entry's {entry.max_pixels} px ceiling"
        )
    return best


def request_from_form(
    prompt: str, seed: Any, hd: bool, entry: Any, factor: int
) -> dict[str, Any]:
    """The protocol section 4.1 request this form describes. Pure — no I/O.

    `hd` is the switch: False asks for the entry's own defaults and no
    permission, True asks for a size above the entry's ceiling and sets
    `upscale: true`, which is the only way the declared stage may run (section
    6.2). The HD size is derived from the entry's ceiling and aspect by
    `_hd_size`, so it is above that ceiling by construction and inside what the
    stage can serve; the switch carries no size of its own.

    `seed` is carried through exactly as given, never coerced: the server is the
    only thing that decides whether it is a usable seed, and a page that rounded
    it would be changing the request behind the operator's back.

    `entry` is the resolved entry and `factor` its stage's declared scale; both
    are arguments rather than module constants because `limits.max_pixels` and
    the defaults belong to the entry (roadmap P9 step 4).
    """
    request: dict[str, Any] = {"prompt": str(prompt)}
    if seed is not None:
        request["seed"] = seed
    if hd:
        width, height = _hd_size(entry, int(factor))
        request["width"] = width
        request["height"] = height
        request["upscale"] = True
    else:
        request["width"] = int(entry.defaults["width"])
        request["height"] = int(entry.defaults["height"])
    return request


def render(app: Any, request: dict[str, Any]) -> dict[str, Any]:
    """The UI's only route to a still: the server's submission seam.

    Not a client of the API over HTTP — a second client would be a second place
    where a request can be shaped — and not the adapter, not the queue: one
    producer, one queue, one renderer (protocol section 9, rule 8).
    """
    return app.submit(request)


def generate(app: Any, prompt: str, seed: Any, hd: bool) -> Iterator[Any]:
    """Submit one request and report while it waits: status strings, then the response.

    `submit()` blocks until the still exists — ~46 s at 1280x720, and longer
    behind another request — so the call runs in a worker thread and this
    generator yields a status string every `STATUS_TICK_S` until it returns, then
    yields the response object itself. The status is the queue depth from
    `app.depth()`: without it a request waiting behind another looks frozen.

    A failure is yielded as a sentence rather than raised, and the sentence says
    which of three things happened — it does not call every failure a refusal.
    The classes are named rather than imported: `coltman_images.server` imports
    this module, so importing it back would be a cycle, and the three names are
    the seam's declared vocabulary (protocol section 9, rule 8).
    """
    entry = app.entry
    if entry is None:
        raise RuntimeError("generate: the UI was built before the entry was resolved")
    declaration = app.declaration
    if hd and declaration is None:
        raise RuntimeError("generate: HD needs the stage's declaration, and none is loaded")
    try:
        request = request_from_form(prompt, seed, hd, entry, int(declaration.scale) if hd else 1)
    except ValueError as exc:
        yield f"the page could not build that request — {exc}"
        return

    outcome: dict[str, Any] = {}

    def _work() -> None:
        try:
            outcome["response"] = render(app, request)
        except BaseException as exc:  # noqa: BLE001 — reported on the page, never hidden
            outcome["error"] = exc

    began = time.perf_counter()
    worker = threading.Thread(target=_work, name="coltman-images-ui", daemon=True)
    worker.start()
    while worker.is_alive():
        # `app.depth()` is the server's own count of requests waiting for the
        # worker — the number `/health` reports — and it includes this one until
        # the worker picks it up. It is quoted as the server declares it and never
        # interpreted: a depth cannot tell this request whether the one ahead of it
        # is still waiting or already on the card, so the line does not claim
        # which. "In flight" is the law's own word for a request the server has
        # accepted and not finished (section 6).
        yield f"in flight — queue depth {app.depth()} — {time.perf_counter() - began:.1f} s"
        worker.join(STATUS_TICK_S)

    if "response" in outcome:
        yield outcome["response"]
        return
    error = outcome.get("error")
    name = type(error).__name__
    if name == "InvalidRequest":
        lead = "the server refused it"
    elif name == "RenderFailed":
        lead = "the server ran it and the render failed"
    elif name == "ServerError":
        lead = "the server is not accepting work"
    else:
        lead = "the page lost the request"
    yield f"{lead} — {name}: {error}"


def build(app: Any) -> gr.Blocks:
    """The page: prompt, seed, an SD/HD switch, the status line and the still.

    Presentation only. Every number and every word on the result panel comes
    from the response object — the delivered size, the base the stage started
    from, the census exactly as its keys are declared, and the three timings kept
    separate because `duration_s` is the only one that shows queue wait and load
    (protocol section 4.2).
    """

    def _describe(response: dict[str, Any]) -> str:
        """The honest copy, from the response and never from a constant."""
        stage = response.get("upscale")
        size = f"{response.get('width')}x{response.get('height')}"
        if isinstance(stage, dict):
            base = stage.get("from") or []
            base_text = "x".join(str(side) for side in base) if base else "?"
            quality = (
                f"**HD** — delivered {size}, rendered {base_text}, enlarged "
                f"x{stage.get('scale')} by `{stage.get('model')}` in {stage.get('upscale_s')} s."
            )
        else:
            quality = f"**SD** — {size}, the native render; nothing was synthesized."
        census = response.get("census") or {}
        census_text = " · ".join(f"{key} {value}" for key, value in census.items())
        lines = [
            quality,
            "",
            f"`{response.get('model')}` · seed {response.get('seed')} · "
            f"steps {response.get('steps')}",
            "",
            f"census — {census_text}" if census_text else "census — (none reported)",
            "",
            f"render_s {response.get('render_s')} · load_s {response.get('load_s')} · "
            f"duration_s {response.get('duration_s')}",
            "",
            f"written to `{response.get('out')}`",
        ]
        return "\n".join(lines)

    def _submit(prompt: str, seed: Any, quality: str) -> Iterator[tuple[Any, ...]]:
        """Drive `generate` and hand its yields to the three outputs.

        `seed` is passed on as the component gives it — `gr.Number` with
        `precision=0` hands an integer or nothing — because the server owns the
        rule about what a seed may be.
        """
        for update in generate(app, prompt, seed, quality == HD_LABEL):
            if isinstance(update, dict):
                yield f"done — {update.get('out')}", update.get("out"), _describe(update)
            else:
                yield str(update), None, ""

    with gr.Blocks(title="coltman-images", analytics_enabled=False) as page:
        gr.Markdown(
            "**coltman-images** — one request, one still. SD is the native render; "
            "HD asks the declared stage to supply the pixels above the native ceiling."
        )
        prompt = gr.Textbox(
            label="prompt",
            lines=2,
            placeholder="what to render",
        )
        with gr.Row():
            seed = gr.Number(label="seed", precision=0, value=None)
            quality = gr.Radio(
                choices=[SD_LABEL, HD_LABEL],
                value=SD_LABEL,
                label="size",
            )
        submit = gr.Button("generate", variant="primary")
        status = gr.Markdown("idle")
        still = gr.Image(label="still", type="filepath", height=540)
        details = gr.Markdown("")
        submit.click(
            _submit,
            inputs=[prompt, seed, quality],
            outputs=[status, still, details],
            api_name="generate",
        )
    # Gradio's own queue is turned off. It serialises event handlers by default,
    # which would hold the second submission *in front of* the seam: observed
    # before this line existed, a second tab sat inside gradio and the depth line
    # never saw it (tens of seconds — the pre-fix transcript was not kept, so no
    # figure is claimed). The page must not have a queue of its own: the server's
    # single-flight queue is the only one (section 9, rule 8), and `app.depth()`
    # is the only honest thing to report. Gradio still dispatches through a thread
    # pool bounded by `max_threads` (40 by default), so beyond forty simultaneous
    # submissions it holds one — a bound of the rendering layer, declared in
    # section 5.5.
    page.queue(default_concurrency_limit=None)
    return page
