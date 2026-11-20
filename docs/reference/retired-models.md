# Retired models

A model leaves this list when the two-model pruning decides it wins neither slot.
**Retiring means deleting the weights, never the code.** The adapter, the configs
and this recipe stay so the model can come back without rewriting anything; the
entry file itself was deleted with the weights, and the recipe below recreates it
from the commit that removed it.

---

## Z-Image Turbo fp8 — retired 2026-11-19

### Why it was retired

It lost both slots of the two-model allocation and was dominated on each:

| Slot | Winner | Z-Image's position |
|---|---|---|
| Production (quality) | MOSS-Image DMD int8 | below it on skin, materials and prompt adherence |
| Draft (speed) | FLUX.2 [klein] 4B | 45,0 s against 22,4 s, and 4.815 MiB against 4.305 MiB |

For the project's real workload — 60–70 images per 15-minute faceless video — the
quality model costs 57 min per video, so volume was never the constraint that
would have justified keeping a third model. See
`docs/research/p10-b3-dreamshaper-and-moss-stage2-report.md` §21.

### What was deleted — 10.872.161.055 bytes (10,87 GB)

| Path | Bytes | What it was |
|---|---:|---|
| `model/assets/checkpoint.safetensors` | 6.289.509.744 | the Z-Image transformer |
| `model/assets/qwen3/qwen3_quanto_bf16_int8.safetensors` | 4.414.004.409 | the INT8-quanto Qwen3 text encoder |
| `model/assets/vae.safetensors` | 167.666.902 | the Z-Image VAE |

**None of the three was referenced by another model.** klein's entry points at
`model/assets/flux2-klein/gguf/*` and `model/assets/flux2-klein/official/vae/*`;
MOSS uses the assets it brought, under its own folder.

### What that check missed, and what it cost

The scan covered the **entries**, the **guards' declaration documents** and the
**docs**. It did not cover the **behaviour of the test matrix**, and the matrix is
a consumer: `tests/test_p6_guards.py` defines `_start()` as *"Start the shared
server on Z-Image, the entry this matrix measures"*, and the twelve service
guards assert **Z-Image's census, ladder and recorded baseline**.

**Deleting the weights took the matrix from green to 12 failures and 3 errors out
of 20 tests.** Verified 2026-11-19 with
`.venv/bin/python -m unittest discover -s tests`.

**And they are not restorable byte-for-byte.** These three files were **not
upstream downloads**: `docs/reference/zimage-fp8-vs-int8.md` describes them as
**QUANTO weight-only INT8** artefacts produced locally. The repository contains
**no quantisation script**, **no fp16/bf16 source weights** for Z-Image-Turbo or
the Qwen3 encoder, and the recipe survives only as prose. A re-download plus a
re-quantisation would produce different bytes and a different census, so the
matrix would need re-basing regardless.

**Consequence:** the retirement is not a free operation. Restoring the model to
its former bytes is impossible from this repository; the honest options are to
**re-base the service matrix onto the model that is actually served** (klein
today, MOSS once adopted) or to accept that the Z-Image baseline is lost.

This section exists because the first version of this document claimed the
deletion was clean. It was not.

### What was kept, on purpose

| Path | Why it stays |
|---|---|
| `coltman_images/adapters/zimage.py` | the adapter; the guard lists it as a required source |
| `model/z_image.json` | transformer config; the guard lists it as a declaration document |
| `model/assets/vae_config.json`, `model/assets/scheduler_config.json` | tiny, needed to rebuild |
| `model/assets/qwen3/` (tokenizer, configs, vocab) | 15 MB total, needed to rebuild |

**The declaration itself was not kept**, and the table above used to claim
otherwise: the entry file `model/entries/zimage.yaml` was deleted on 2026-11-19 by
the unit that re-based the guard matrix off Z-Image, and `tests/test_p6_guards.py`
no longer reads it — the constant that named it is gone. Its last committed
content is recoverable from the commit that deleted it (`22cbb0e`), which is what
the recipe below starts from.

### The honest gap

**These three weights were never pinned by digest.** The previous cycle recorded
`Tongyi-MAI/Z-Image-Turbo` as the upstream model and nothing more: no repository
URL per file, no SHA-256. Restoring them therefore means **obtaining them again
and pinning the digests at that moment** — the byte sizes above are the only
check available today.

That is a documentation failure of the cycle that installed them, and it is
recorded here rather than smoothed over.

### Restore recipe

1. Obtain the three artefacts upstream — the Z-Image-Turbo fp8 transformer, its
   VAE, and the INT8-quanto Qwen3 encoder.
2. Recreate the declaration from the last commit that carried it — the entry is
   not in the tree, so there is nothing to edit:

   ```sh
   git show 22cbb0e^:model/entries/zimage.yaml > model/entries/zimage.yaml
   ```

   It is 59 lines, declares `id: z-image-turbo-fp8`, and carries no retirement
   banner. Read it before going on: it is the declaration the recorded baseline
   and the census belong to.
3. **Pin the SHA-256 of each artefact before use** — these three weights were
   never pinned, so no digest exists to check against — and add them to this
   document and to the recovered entry's `digests:` block.
4. Check each against the recorded size:

   | Destination | Expected bytes |
   |---|---:|
   | `model/assets/checkpoint.safetensors` | 6.289.509.744 |
   | `model/assets/qwen3/qwen3_quanto_bf16_int8.safetensors` | 4.414.004.409 |
   | `model/assets/vae.safetensors` | 167.666.902 |

5. Re-add the roster row in `model/models.yaml`: keep `id: z-image-turbo-fp8` and
   `role:`, drop `restore:` and the retirement note, and declare the entry path
   it now has:

   ```yaml
   - id: z-image-turbo-fp8
     entry: model/entries/zimage.yaml
     role: production
   ```

   The role is the operator's decision: `production` is where the model stood,
   `draft` is the slot the roster gives the fast pass. Without the `entry` key
   `--model z-image-turbo-fp8` still resolves to nothing, because the id scan
   reads `model/entry.yaml` and `model/entries/*.yaml`, not the roster.
6. Run the matrix: `.venv/bin/python -m unittest discover -s tests -v`.
7. Only then does `coltman-images start --model z-image-turbo-fp8` work again.

**Until steps 1–5 are done, `--model z-image-turbo-fp8` resolves to nothing**: the
roster row carries no `entry`, and no file declares that id. The row is left in
the roster so the door stays visible, and `docs/protocol.md` section 6.1 records
where it stands.
