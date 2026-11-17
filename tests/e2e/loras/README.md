# LoRAs — the catalog, the budget, and the four checks

The operator-level run for the LoRA unit: the promoted entry
(`flux2-klein-4b-gguf-q4`) serving real stills on the real card, through
`bin/coltman-images` and `POST /generate`, with the LoRA selection as the only
variable. The law it exercises is protocol sections 4.1 (`lora`), 6.1 (the
catalog and `lora_budget_mib`), 6.3 (the adapter's obligation), 7, 10 (guard 18),
11 and 12; the matrix's own half is `tests/test_p6_guards.py`, guard 18.

- **Date:** 2026-11-17
- **Card:** RTX 4060 Laptop, 8188 MiB
- **Interpreter:** `.venv/bin/python` (Python 3.14.8)
- **Request:** one prompt and one seed throughout — the `pixel-art` LoRA's own
  card prompt, "pixel art sprite, a brave knight in shining armor holding a
  sword, game asset, transparent background", seed 7, 512×512, the entry's 8
  steps. The stills are the run's, not taste judgments.
- **Catalog (the promoted entry):** `pixel-art` 311 MiB, `anime` 177 MiB,
  `background-remove` 73 MiB — `model/assets/loras/flux2-klein-4b-gguf-q4/*.safetensors`,
  read with `stat`, which is what the budget is spent on. Each model owns its
  LoRAs: the folder is named for the entry's `id`, and a path outside it refuses
  at boot (protocol sections 3 and 6.1).
- **Budget:** `host.yaml`'s `lora_budget_mib: 3200` — a memory, not a count.

## What it proves

| Check | Observed |
| --- | --- |
| A. One LoRA reaches the runtime | `render_s` **6.911 s** without it and **8.916 s** with `pixel-art`, same prompt and seed; `sha256 1f01cecd70ccd6c7…` against `8a8808d6e0ddf752…` — different bytes, so the selection did not stop at the request parser |
| B. Three LoRAs are served | `render_s` **10.053 s** for `pixel-art:0.8`, `anime:0.4`, `background-remove:0.3` |
| C. An unknown alias is refused | `400 invalid_request` — `lora: this entry declares no LoRA named 'no-such-alias'; it declares ['anime', 'background-remove', 'pixel-art']`, and the served counter did not move |
| D. A budget that cannot pay is refused | with `lora_budget_mib: 512` in `host.yaml`, the whole catalog → `400 invalid_request` — `lora: these 3 LoRAs need 559 MiB of device memory and this deployment's budget is 512 MiB (host.yaml's lora_budget_mib; this card spends +313 MiB of device memory for a 325 MB LoRA, linear to eleven, and from twelve it plateaus and pays in time); the largest single LoRA in this catalog is 'pixel-art' at 311 MiB. A LoRA's size is its file's, read from disk, so the budget is a memory and not a count` |
| D. The shipped declaration serves | after restoring `host.yaml` byte for byte, one LoRA at 256×256 (311 MiB of the 3200 MiB budget) → `200`, `render_s` 5.694 s |
| Tree left as found | `host.yaml`'s bytes restored and asserted; server stopped |

Sizes are the catalog's, and they are what the refusal is made of: `3200` MiB of
budget admits the whole catalog (559 MiB) and would also admit eleven 325 MB
LoRAs (3443 MiB, the default budget of a tree with no `host.yaml`); `512` admits
`pixel-art` alone. The per-LoRA cost agrees with the ceiling measurement in
protocol section 11 (+1.5 s for a 325 MB file): 6.91 s without a LoRA, 8.92 s with
one, 10.05 s with three, at 512×512. That is one prompt and one seed on one card,
and it is an indication, not a distribution.

What this run does **not** establish is quality: nothing here compares the stills
for interference between LoRAs. Protocol section 12 says so.

## Running it

The card must be free: no server, no `run/server.json`.

```bash
.venv/bin/python tests/e2e/loras/run.py
```

The run writes `evidence/loras.json` and the stills beside it, rewrites
`host.yaml` for check D and restores the shipped bytes in `finally`, and leaves
the server stopped. `evidence/` is gitignored by the repository's ignore file —
run products are never committed — and this README is.
