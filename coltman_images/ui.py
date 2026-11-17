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
4. `build` — the page. Two equal columns: the form on the left (prompt, seed, the
   SD/HD switch, the steps slider whose range is the entry's, the button), the
   status line, the still and its details on the right. Presentation only: no
   validation, no request shaping, no knowledge of a model. The adapter's census
   keys are never written here; they are rendered as the response declares them,
   because protocol section 6.1 makes the adapter the owner of what a census key
   means — and a second model may declare keys this page has never heard of.

Gradio is the first rendering of this, behind that seam: replacing it is
replacing `build` and nothing else (protocol section 5.5).
"""

from __future__ import annotations

import math
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

ASPECT_PRESETS = ("16:9", "1:1", "4:3", "3:4", "9:16")
"""The shapes the page offers, in the operator's order, as text.

Text and not numbers: a preset's digits are a label, and a size is never carried
here — `size_for` computes it from the entry's ceiling and the stage's factor, so
a different entry or a different stage changes every one of them without a line
of this module."""


def _ratio(aspect: str) -> tuple[int, int]:
    """`"16:9"` → `(16, 9)`, reduced. A shape the page does not offer is refused."""
    if aspect not in ASPECT_PRESETS:
        raise ValueError(f"aspect: {aspect!r} is not one of the offered shapes {ASPECT_PRESETS}")
    across, down = aspect.split(":")
    left, right = int(across), int(down)
    common = math.gcd(left, right)
    return left // common, right // common


def size_for(entry: Any, aspect: str, factor: int) -> tuple[int, int]:
    """The largest box at `aspect` this entry can serve at `factor`.

    One rule for both halves of the switch: SD is `factor=1`, HD is the stage's
    declared factor, and the ceiling is `max_pixels x factor²` (section 6.2). The
    box is the largest whose area fits that ceiling, whose sides are both
    multiples of the request's block (section 4.1) and at least 256, and whose
    ratio is exactly `aspect`.

    It shrinks to the largest that fits and never forces the area: at 4:3 the
    next step up is over the ceiling by 73,728 px, so 4:3 stops lower than the
    other shapes — which is the whole reason the page offers a list of shapes
    instead of two free fields. A size is never carried in this module: the entry
    and the stage are the only inputs.
    """
    across, down = _ratio(aspect)
    cap = int(entry.max_pixels) * int(factor) * int(factor)
    block = 16
    # The smallest step that keeps *both* sides on the block grid, so the box's
    # ratio survives the grid instead of being rounded away from it.
    step = math.lcm(block // math.gcd(across, block), block // math.gcd(down, block))
    scale = math.isqrt(cap // (across * down))
    scale -= scale % step
    while scale > 0 and (
        across * scale < 256 or down * scale < 256 or across * scale * down * scale > cap
    ):
        scale -= step
    if scale <= 0:
        raise ValueError(
            f"size: no {aspect} box with sides on the {block} grid fits the {cap} px a factor of "
            f"{factor} offers"
        )
    return across * scale, down * scale


def request_from_form(
    prompt: str,
    seed: Any,
    hd: bool,
    steps: Any,
    aspect: str,
    entry: Any,
    factor: int,
    image: str | None = None,
) -> dict[str, Any]:
    """The protocol section 4.1 request this form describes. Pure — no I/O.

    `hd` is the switch: False asks for the shape's largest box under the entry's
    ceiling, True for its largest inside what the declared stage can serve, with
    `upscale: true` — the only way that stage may run (section 6.2). Both come
    from `size_for`, so the page carries no size of its own.

    `steps` is the ladder's position. A value equal to the entry's own default is
    **omitted**, because absent means the entry's steps (section 4.1): the page
    left at its initial position then sends exactly the request the API serves by
    default, and "the entry's default" stays the entry's business instead of
    becoming a number this module learned. Sending it explicitly produces the
    same still — measured, `a lighthouse at dusk`, seed 7, 512×512 — but it would
    write today's number into every request.

    `seed` is carried through exactly as given, never coerced: the server is the
    only thing that decides whether it is a usable seed, and a page that rounded
    it would be changing the request behind the operator's back.

    `image` is the reference the operator dropped on the page, as the **path**
    gradio hands over (`type="filepath"`), and it is sent only when a file is
    there: a page with no reference sends exactly the request it sent before the
    control existed. The path is the request's field and nothing else — the page
    does not open the file, measure it or derive a size from it, because the box
    is the entry's and the aspect's to decide (sections 4.1 and 5.5). The count
    and the existence are the door's to accept or refuse.

    `entry` is the resolved entry and `factor` its stage's declared scale; both
    are arguments rather than module constants because `limits.max_pixels` and
    `limits.steps` belong to the entry (roadmap P9 step 4).
    """
    request: dict[str, Any] = {"prompt": str(prompt)}
    if seed is not None:
        request["seed"] = seed
    if steps is not None and steps != entry.steps:
        request["steps"] = steps
    width, height = size_for(entry, aspect, int(factor) if hd else 1)
    request["width"] = width
    request["height"] = height
    if hd:
        request["upscale"] = True
    if image:
        request["image"] = [str(image)]
    return request


def render(app: Any, request: dict[str, Any]) -> dict[str, Any]:
    """The UI's only route to a still: the server's submission seam.

    Not a client of the API over HTTP — a second client would be a second place
    where a request can be shaped — and not the adapter, not the queue: one
    producer, one queue, one renderer (protocol section 9, rule 8).
    """
    return app.submit(request)


def generate(
    app: Any, prompt: str, seed: Any, hd: bool, steps: Any, aspect: str, image: str | None = None
) -> Iterator[Any]:
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
        request = request_from_form(
            prompt, seed, hd, steps, aspect, entry, int(declaration.scale) if hd else 1, image
        )
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
    """The page: two equal halves — the form on the left, the result on the right.

    Presentation only. Every number and every word on the result panel comes
    from the response object — the delivered size, the base the stage started
    from, the census exactly as its keys are declared, and the three timings kept
    separate because `duration_s` is the only one that shows queue wait and load
    (protocol section 4.2).

    The form's steps control takes its range **from the entry** — `limits.steps`
    and the entry's own default — so a second entry with its own ladder needs no
    change here. The status line sits at the top of the result half, not under the
    form: it is the proof that the page is not hung, and the operator is looking
    at the half where the still will appear.
    """
    entry = app.entry
    if entry is None:
        raise RuntimeError("build: the page needs the resolved entry, and none is loaded")
    declaration = app.declaration
    if declaration is None:
        raise RuntimeError("build: the page needs the stage's declaration, and none is loaded")
    factor = int(declaration.scale)

    def _guide() -> str:
        """What each control does, with every number computed from the entry.

        Presentation only: the ladder comes from `entry.steps_min`/`steps_max`/
        `steps`, the boxes from `size_for`, and the ceiling and the stage from the
        entry and the declaration. A number written here would be a number the
        next entry inherits wrongly, so there is none — the strings are templates
        and guard 13 scans them for the entry's sizes. The reference paragraph is
        emitted only when the entry declares that capability, and its count is
        `entry.images_max`.
        """
        boxes = {shape: (size_for(entry, shape, 1), size_for(entry, shape, factor)) for shape in ASPECT_PRESETS}
        ceiling = int(entry.max_pixels)
        exact = [shape for shape in ASPECT_PRESETS if boxes[shape][0][0] * boxes[shape][0][1] == ceiling]
        short = [shape for shape in ASPECT_PRESETS if shape not in exact]
        if short:
            verb = "stops" if len(short) == 1 else "stop"
            short_sentence = (
                f"On this entry the ceiling is reached exactly by {', '.join(exact) or 'no shape'}; "
                f"{', '.join(short)} {verb} short."
            )
        else:
            short_sentence = "On this entry every shape reaches the ceiling exactly."
        table = "\n".join(
            f"| `{shape}` | {boxes[shape][0][0]}×{boxes[shape][0][1]} "
            f"| {boxes[shape][1][0]}×{boxes[shape][1][1]} |"
            for shape in ASPECT_PRESETS
        )
        default_width = int(entry.defaults["width"])
        default_height = int(entry.defaults["height"])
        paragraphs = [
            "**prompt** — The encoder is the pipeline's own prompt encoder, not a language "
            "model bolted on. Measured on this deployment on 2026-11-16: the same "
            "description that kept `blue skin` in English lost it in Spanish at the same "
            "seed, so keep the attributes that matter in English — or the whole prompt.",
            "**seed** — A render does not start from an empty canvas — it starts from noise. "
            "The seed chooses which noise. **Same seed and the same everything else gives "
            "byte-identical files**; a different seed gives a different composition, not a "
            "better one. The seed alone does not reproduce a still: the prompt, the steps, "
            "the shape and the model must match too. No number is better than another; when "
            "one gives you something you like, keep it.",
            "**steps** — Each step is one pass of the model over the noise. Cost is linear — "
            f"measured on this deployment at 3.9 s per step at {default_width}×{default_height}, "
            "the box this entry renders by default — and the curve turns, measured here: below the entry's range the "
            "scene is not settled, above it the stills differ but do not improve. The range "
            f"and the default are the entry's, not the page's: {entry.steps_min} to "
            f"{entry.steps_max}, defaulting to {entry.steps}.",
            "**size** — **SD** is the native render: exactly the pixels the model produced. "
            "**HD** delivers a larger still by enlarging a base render with the declared "
            "stage — those pixels are synthesized, not rendered, and the panel names the base "
            "it started from so the two cannot be confused. HD only runs when the size is "
            "above the ceiling and only because you asked for it. On this entry the ceiling "
            f"is {entry.max_pixels} px and the stage is ×{factor}.",
            "**aspect** — Each shape's size is the largest box at that proportion whose sides "
            "stay on the 16-pixel grid and whose area fits the entry's ceiling — and for HD, "
            "the stage's reach. So a shape can never ask for something the card would refuse. "
            f"{short_sentence} On the grid, the next size up for a shape that stops short "
            "would overshoot, so the page shrinks to the largest that fits and the panel tells "
            "you what you got.\n\n"
            "| shape | SD | HD |\n| --- | --- | --- |\n" + table,
            "**the panel** — Every number on the result comes from the response, never from "
            "the page: the size delivered, the base the stage started from, the census the "
            "loader measured — key by key, whatever that model declares — and `render_s`, "
            "`load_s` and `duration_s` kept apart, because the last one is the only one that "
            "shows queue wait and load.",
            "**the status line** — While a request runs, the line quotes the server's queue "
            "depth. It is quoted and never interpreted: a depth cannot say whether the "
            "request ahead is waiting or already on the card. A quiet page and a hung page "
            "must not look the same.",
        ]
        if entry.images_max:
            # Computed, like every other number here: the count is the entry's
            # declaration of what the model accepts, and the paragraph exists only
            # for a model that declares it.
            paragraphs.insert(
                1,
                "**reference image** — Drop an image here to condition the render on it: the "
                "model reads a picture as a reference as well as a prompt, and it edits or "
                "re-renders from it rather than treating it as a canvas. The prompt still "
                "applies — say what you want done with the picture, not what the picture is. "
                f"This model accepts up to {entry.images_max} references; the page sends the "
                "one you drop, and leaving the box empty sends the request the API serves with "
                "no reference at all.",
            )
        return "\n\n".join(paragraphs)

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
        ]
        references = response.get("image") or []
        if references:
            # The response echoes the reference paths it was conditioned on
            # (section 4.2), so the panel states them instead of assuming the box
            # that is on screen now is what rendered this still.
            lines.extend(["", "reference — " + ", ".join(f"`{path}`" for path in references)])
        lines.extend(["", f"written to `{response.get('out')}`"])
        return "\n".join(lines)

    def _submit(
        prompt: str, image: Any, seed: Any, quality: str, steps: Any, aspect: str
    ) -> Iterator[tuple[Any, ...]]:
        """Drive `generate` and hand its yields to the three outputs.

        `seed` is passed on as the component gives it — `gr.Number` with
        `precision=0` hands an integer or nothing — `steps` as the slider hands
        it, which is an integer because the slider's `precision` is 0, and
        `aspect` as the operator's label. `image` is the reference, as the path
        `gr.Image(type="filepath")` hands over: a string when a file is there and
        nothing when the box is empty, and `request_from_form` sends it only in
        the first case. The server owns the rules about all of them, and the size
        is computed from the entry and the stage, never taken from the form.
        """
        for update in generate(app, prompt, seed, quality == HD_LABEL, steps, aspect, image):
            if isinstance(update, dict):
                yield f"done — {update.get('out')}", update.get("out"), _describe(update)
            else:
                yield str(update), None, ""

    with gr.Blocks(title="coltman-images", analytics_enabled=False) as page:
        with gr.Row():
            with gr.Column(scale=1, min_width=320):
                gr.Markdown(
                    "**coltman-images** — one request, one still. SD is the native render; "
                    "HD asks the declared stage to supply the pixels above the native ceiling."
                )
                prompt = gr.Textbox(
                    label="prompt",
                    lines=2,
                    placeholder="what to render",
                    info="what to render — English gets the most out of the encoder",
                )
                reference = gr.Image(
                    label="reference image",
                    type="filepath",
                    visible=bool(entry.images_max),
                    placeholder="drop an image to edit — or leave it empty",
                )
                if entry.images_max:
                    # The line beneath the control exists only when the control
                    # does: a page that explained a hidden box would describe a
                    # capability the served entry does not have.
                    gr.Markdown(
                        "_reference — an image the model edits or conditions on; empty renders "
                        "from the prompt alone_"
                    )
                with gr.Row():
                    seed = gr.Number(
                        label="seed",
                        precision=0,
                        value=None,
                        info="the starting noise; empty lets the server pick one and report it",
                    )
                    quality = gr.Radio(
                        choices=[SD_LABEL, HD_LABEL],
                        value=SD_LABEL,
                        label="size",
                        info="SD renders; HD asks the stage to synthesize the pixels above the native ceiling",
                    )
                aspect = gr.Radio(
                    choices=list(ASPECT_PRESETS),
                    value=ASPECT_PRESETS[0],
                    label="aspect",
                    info="the shape; every size is computed to fit",
                )
                steps = gr.Slider(
                    minimum=int(entry.steps_min),
                    maximum=int(entry.steps_max),
                    step=1,
                    value=int(entry.steps),
                    precision=0,
                    label="steps",
                    info=(
                        f"the entry's range, {entry.steps_min}–{entry.steps_max}; "
                        f"its default is {entry.steps}. How many denoising passes — time grows "
                        "linearly with it, and past the entry's ceiling more steps buy variation, "
                        "not definition."
                    ),
                )
                submit = gr.Button("generate", variant="primary")
                with gr.Accordion("what each control does", open=False):
                    gr.Markdown(_guide())
            with gr.Column(scale=1, min_width=320):
                status = gr.Markdown("idle")
                still = gr.Image(label="still", type="filepath", height=540)
                details = gr.Markdown("")
        submit.click(
            _submit,
            inputs=[prompt, reference, seed, quality, steps, aspect],
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
