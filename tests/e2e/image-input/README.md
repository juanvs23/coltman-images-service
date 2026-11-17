# The reference image — U4's operator-level run

The request gained an `image` field on 2026-11-17 (protocol sections 2, 4.1 and
6.1; guard 19). This folder holds the run that measured it through the service, and
nothing in it is a guard: the guard is `tests/test_p6_guards.py`, method
`test_0990_guard19_image_input`.

`evidence/` is gitignored, like every other run's products. It holds the stills and
the script's own JSON, and it is the proof the documents cite:

| File | What it is |
| --- | --- |
| `reference-512.png` | the picture the service rendered first, to be edited — `a red ceramic vase on a white table, studio light`, seed 7101, 512×512, four steps, `sha256 4d6a286a…` |
| `edit-with-reference.png` | `Remove the background from the image` with `--lora background-remove` and the reference, seed 7102, 512×512, four steps — `sha256 829671e3…`, `render_s` 7.176 s and 7.510 s on two runs |
| `edit-without-reference.png` | the same prompt, seed, box, steps and LoRA **without** the reference — `sha256 d0a72ee3…`, `render_s` 5.532 s and 5.832 s on two runs |
| `page-check.json` | what `page_check.py` measured: the mounted page, the upload's destination, and two page submissions |
| `g19-*.png` | guard 19's own stills, at 256×256, written by the matrix run |

**What the three stills show.** With the reference, klein reproduced the vase from
the picture and cut the background; without it, the same prompt rendered a
checkerboard and nothing else, because there was nothing to remove. That is the
observation behind §5.2 of `docs/reference/lora-catalog.md`, and it is one file,
one prompt and one seed — not a claim about the other nine editing LoRAs, which
remain the author's word.

**What the digest proves.** The same request with and without `image` produces
different bytes, which is the only evidence that the file reached the model instead
of stopping at the request parser. It does not prove the edit is *good*; that is
the eye's to say, and the eye here is the operator's.

## `page_check.py`

The page's half. Run it with the service already booted:

```bash
bin/coltman-images start --model flux2-klein-4b-gguf-q4 --ui
.venv/bin/python tests/e2e/image-input/page_check.py
bin/coltman-images stop
```

It reads the mounted page's own configuration (the component list and the event's
inputs), posts a file to the page's upload endpoint and prints where it landed,
then submits the same request twice through the page's client — once with the
uploaded path, once with nothing — and compares the two stills.

Measured on 2026-11-17:

- two `image` components: `reference image` (`type: filepath`, an input) and
  `still` (`type: filepath`, an output); the event's inputs are
  `[prompt, reference, seed, quality, steps, aspect]`;
- the upload landed at `run/ui/<hash>/reference-512.png` — inside the tree, which
  is why the page's path needs no read exception in protocol section 2;
- with the reference `sha256 bff4ebbd…`, without it `sha256 0b19b719…`, both at
  1152×1152 and four steps through the page;
- the panel named the reference the response echoed, and named none for the
  submission that carried no reference.

## What this run does not establish

- That the other nine editing LoRAs behave as their cards say. One of ten was
  rendered, once.
- That a style LoRA trained on text-to-image pairs helps or fights a reference
  (a second file applied at once). Unmeasured; `docs/reference/lora-catalog.md`
  §10 keeps it open.
- That a removed background is an alpha channel. The still renders the
  checkerboard; this path writes RGB PNGs.
- That more than one reference renders coherently. The door admits ten and refuses
  eleven; nothing here has sent two.
