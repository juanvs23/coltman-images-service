# Model lifecycle — add, promote, retire, restore

This document is the procedure. It is written so a reader who has never seen this
repository can add or discard a model without reading the test suite.

**One rule owns each fact.** An entry owns its own declaration. `host.yaml` owns the
deployment's numbers. The roster owns which models exist and what each is for. No file
copies a value out of another.

---

## 1. What a model is made of

| Piece | Where | Who owns it |
|---|---|---|
| Declaration | `model/entries/<id>.yaml`, or `model/entry.yaml` for the promoted one | the entry |
| Adapter | `coltman_images/adapters/<name>.py` + a row in `coltman_images/adapter.py` | the adapter |
| Weights | `model/assets/<model>/` | the files |
| LoRAs for that model | `model/assets/loras/<id>/` — the folder **is** the rule | the entry's `loras` block |
| Deployment numbers | `host.yaml` | the host |
| Roster row | `model/models.yaml` | the roster |

A model whose files are absent cannot be loaded: `load_entry` refuses a declaration whose
`checkpoint` or `components` do not exist (`coltman_images/entry.py`, "declared asset is
missing"). That is a safety feature, and it is why a weight-less entry is not "disabled" —
it is unloadable.

---

## 2. Add a model

1. **Put the weights under `model/assets/<id>/`.** Never leave them in `run/`, which is
   temporary by design.
2. **Write `model/entries/<id>.yaml`** with at least: `id`, `adapter`, `checkpoint`,
   `components`, `steps`, `guidance`, `limits.max_pixels`, `limits.steps`,
   `request_fields`, `expected_census`, `defaults`, `warmup`. Every comment that explains
   a number should say **where it was measured**.
3. **Write the adapter** and register it in `coltman_images/adapter.py`. Do the two
   together: an entry whose adapter is missing can break the guards that walk
   `model/entries/`.
4. **Declare the LoRAs it may use**, if any, under `model/assets/loras/<id>/`. A catalogue
   path outside that folder is refused at boot — the folder is what makes ownership
   visible, because a LoRA that silently applies nothing is worse than one refused.
5. **Add a roster row** in `model/models.yaml` with `role: draft` or `production`.
6. `./bin/coltman-images start --model <id>` and render one still.
7. `.venv/bin/python -m unittest discover -s tests`

**The guards need no change.** They read the declaration of the entry they serve, so a new
model is measured by the same invariants as the old one.

---

## 3. Promote a model

Change its roster row to `role: production`, and the guard matrix follows it. The
promoted default entry (`model/entry.yaml`) is the fallback the matrix uses when no roster
is present; promoting through the roster does not require editing the tests.

---

## 4. Retire a model

A retirement **deletes weights, never code**.

| May delete | Must keep |
|---|---|
| the weights under `model/assets/<id>/` | the entry file |
| its LoRA catalogue folder, if no other entry owns it | the adapter module and its registry row |
| cached evidence that names it | any config, tokenizer or JSON the model needed — they are small and the restore recipe needs them |
| | the restore recipe, in this document or `retired-models.md` |

Then:
1. Mark the entry with a `RETIRED` banner at the top of the YAML, naming the recipe.
2. Change its roster row to `role: retired` and keep its `entry` path **even if the entry
   no longer exists**, naming where the recipe lives.
3. If the entry becomes unloadable — because its weights are gone — **and something still
   loads it**, that is a defect in the retirement, not in the loader. Either move that
   consumer to a synthetic fixture or keep the weights.

### The rule that cost a day

> **Before deleting any weight, tokenizer or config, grep the test suite for the file and
> read the suite's fixture — not only its declaration lists.**

On 2026-11-19 the Z-Image weights were deleted after a scan that checked the entries, the
declaration documents and the docs. It did not check the suite's *behaviour*, and
`tests/test_p6_guards.py` booted its shared server on that very model. The matrix went
from green to **12 failures and 3 errors of 20**, and the weights were not restorable
byte-for-byte: they were locally produced QUANTO INT8 artefacts, with no quantisation
script and no source weights in the repository.

Two things came out of it, and both are now permanent:

- the matrix no longer names a model — it derives the id, census, step range, default,
  ceiling, upscale source, page shapes and default box from whichever entry it serves;
- guards that test *model-shaped* ideas (a `float8`-keyed census; an entry that declares
  no reference block) build **synthetic entries** instead of borrowing a real model's
  declaration.

---

## 5. Restore a retired model

1. Obtain the artefacts and **pin their SHA-256** — a restored model whose digests were
   never recorded is a model you cannot verify.
2. Check them against the sizes recorded in the recipe.
3. Remove the `RETIRED` banner.
4. Return its roster row to `draft` or `production`.
5. `.venv/bin/python -m unittest discover -s tests`

---

## 6. Why the friction is now low

Discarding a model costs nothing unless it is **the fixture the matrix serves**. Adding one
costs an entry and an adapter. Everything else — the census the guards compare, the step
range they straddle, the ceiling the size refusals name, the page's shape boxes — is read
from the declaration of whatever entry is served.

That is the property this lifecycle exists to protect: **add and discard without
procedure**, with exactly one named exception, and that exception documented rather than
discovered.
