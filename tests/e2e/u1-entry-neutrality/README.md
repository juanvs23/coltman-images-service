# U1 — entry neutrality (guard 14)

Guard 14 of `docs/protocol.md` section 10, exercised by
`ContractCase.test_guard14_entry_neutrality` in `tests/test_p6_guards.py`. It
exists because the core promises that a second model is an addition, not surgery:
`docs/protocol.md` section 6.3 says the core does not change for a new model. A
law whose schema only one model can satisfy makes that promise false, and this
guard is the executable form of the correction.

- **Date:** 2026-11-15
- **Command:** `.venv/bin/python -m unittest discover -s tests -v` (from the project root)
- **Result:** 14 tests, `OK`, 416.367 s of test time; guard 14 alone runs in 1.43 s
- **Verdict:** green. Both halves pass, and neither is vacuous (below).

Guard 14 lives in `ContractCase` because it needs no service: it writes its own
entry and registers its own adapter, and it renders through `render.render` in a
child process. Being in `ContractCase` it also runs before any server exists, so
the CUDA context it creates cannot share the card with the 6057 MiB transformer
the later guards load.

## What part (a) asserts, behaviourally

The guard writes a synthetic entry into `evidence/` — component names of its own
choosing (`thing_a`, `thing_b`), **no transformer config, no float8 census**, a
census of `{parameters: 2, tensors: 3}`, a `checkpoint` that is a 47-byte text
file (the law checks that the path exists, not what is at it), and
`adapter: u1stub`, registered for the test — and then:

1. loads it through `coltman_images.entry.load_entry`. If `entry.py` still carried
   a model's schema, this entry would be refused before any adapter existed.
   **It loads.**
2. reaches a component by attribute (`entry.components.thing_a`) and asks for one
   the entry does not declare: `AttributeError: components: this entry declares no
   component named 'thing_c'; it declares ['thing_a', 'thing_b']`.
3. renders one 256×256 still through `render.render` with the stub adapter, and the
   still's first pixel equals the stub's own rule for that prompt and seed — so the
   bytes came from the stub, not from a model.
4. reads back the response: `model` is the synthetic id, the seed is the one asked
   for, the census is the entry's two arbitrary keys, and `upscale` is `null`.
5. checks the calls the core actually made, in order — `prepare`, `encode`,
   `denoise`, `census`, `close` — so the still is not a file the guard painted
   itself: the core drove the stub through its whole contract.

Measured, this run:

```
guard 14a: entry u1-stub-model (adapter 'u1stub') loaded from
  tests/e2e/u1-entry-neutrality/evidence/entry.yaml with components
  ['thing_a', 'thing_b'] and census {'parameters': 2, 'tensors': 3} in 1.43 s
guard 14a: rendered 256x256 through the stub →
  tests/e2e/u1-entry-neutrality/evidence/stub-render.png
  (model 'u1-stub-model', seed 11)
guard 14a: the core called the stub ['prepare', "encode 'a thing that is not
  a lighthouse'", 'denoise 256x256 seed=11', 'census', 'close']
guard 14a: a name the entry does not declare →
  "components: this entry declares no component named 'thing_c';
   it declares ['thing_a', 'thing_b']"
```

## What part (b) asserts, on the parsed code

`coltman_images/entry.py` contains none of `transformer_config`, `text_encoder`,
`vae`, `scheduler_config` or `float8` **in code**. Measured, this run:

```
guard 14b: coltman_images/entry.py parsed — 0 of 5 model names in code;
  the same scan finds ['float8', 'scheduler_config', 'text_encoder',
  'transformer_config', 'vae'] in zimage.py (48 occurrences)
```

**Deviation from the brief, reported rather than worked around.** The brief asked
for "a source scan" and cited guard 11 as the technique. Scanning raw prose would
forbid the *word* without forbidding the *coupling*: a comment or a docstring
cannot make a module read a component, and a guard that failed on the word would
push a future author to delete an accurate comment to get green. So the scan reads
the AST — identifiers, attribute names, argument and keyword names, definition
names, imported names and the string constants that are not docstrings (the same
`_literal_strings` guard 8 and guard 11 already use). Comments are absent from an
AST by construction, so they are not scanned; that is the deviation, and it makes
the guard stricter about what matters and silent about what does not.

The scan is proved not vacuous in the same test: run over
`coltman_images/adapters/zimage.py` — the file that *does* own Z-Image — it must
find **all five** names, and it finds them in 48 places. A scan that returned
nothing for both files would prove nothing; this one distinguishes them.

## What the run leaves behind

`evidence/` (gitignored, created by the guard on every run):

| File | What it is |
| --- | --- |
| `entry.yaml` | the synthetic entry, written by the guard |
| `thing_a.bin` | a component with real bytes, under a name no model owns |
| `thing_b.json` | the second component; the one `digests` pins |
| `stub-render.png` | the 256×256 still the stub rendered |

Nothing is written outside `tests/e2e/u1-entry-neutrality/evidence/` and the
project's own `run/` and `out/`. No model is loaded, so the guard costs no
GPU work beyond the CUDA context of its child process, which dies with it.

## How to regenerate

```sh
cd coltman-images-service
.venv/bin/python -m unittest discover -s tests -v -k guard14
```

The guard needs no server, so it can be run on its own. It does need the card to
be free: `render.render` refuses to run without a CUDA device, and the suite must
never run while a server is up (protocol section 10, the one-GPU rule).

## Inputs, by location

| Input | Where |
| --- | --- |
| The law it enforces | `docs/protocol.md` sections 6.1, 6.3 and 10 (guard 14) |
| The file it scans | `coltman_images/entry.py`, read live, parsed, never imported by the scan |
| The control file | `coltman_images/adapters/zimage.py`, which must name all five |
| The synthetic entry | generated by the guard into `evidence/entry.yaml` |
| The stub adapter | `_U1StubAdapter` in `tests/test_p6_guards.py` |
| The still | `evidence/stub-render.png` |
