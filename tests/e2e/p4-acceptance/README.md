# P4 acceptance — the server process and the CLI's `start`/`stop`

**What it tests.** The lifecycle protocol section 6 declares, end to end, on a
real card: `start` (resolve, validate, warm up, write the state file, bind),
a second `start` (idempotent, one process), `POST /generate`, a refusal at the
door, two concurrent generates through the single-flight queue, `stop` (drain,
release, remove the state file), and the absence of the `generate` subcommand.
Two lifecycle edges the protocol declares but the seven checks do not reach are
probed as well: a stale state file, and `stop` against a state file whose pid is
gone.

**Date.** 2026-11-15.

**Command.**

```
tests/e2e/p4-acceptance/run.sh
```

It runs from the project root under the project's own interpreter, and it is
not a substitute for the guards of protocol section 10 — it is the phase's exit
observation, and it asserts exactly what it printed.

**Inputs.**

- `model/entry.yaml` — the entry; the warm-up shape, prompt and seed come from it.
- `model/upscaler.yaml` and `model/assets/upscaler/realesrgan_x2plus.pth` — the
  stage's declaration, validated at `start`.
- `model/assets/checkpoint.safetensors`, `model/assets/vae.safetensors`,
  `model/assets/vae_config.json`, `model/assets/scheduler_config.json`,
  `model/assets/qwen3/`, `model/z_image.json` — the render's assets.
- `.venv/bin/python` — the interpreter the server runs under.
- prompts: `a lighthouse at dusk` (seeds 7, 11, 12) and `x` (the refusals).

**Result.** Seven checks, two lifecycle edges, zero failures — the run ended with
`failures: 0` and exit 0. The transcript is `evidence/transcript.txt`;
`evidence/transcript-1-harness-quoting-bug.txt` is the first pass of the same
run, kept because it is what happened: check 3 went red there for a defect in
*this script* (a JSON string was re-parsed by the shell with its quotes, so the
PNG path never resolved), and the server's own output in that pass was already
correct — `http=200`, `duration_s 46.37`, `render_s 43.273`, and the file on
disk. The harness was fixed and the run repeated in full; no assertion was
weakened.

Measured, 1280×720 on the production entry:

| Request | `duration_s` | `render_s` | `load_s` | peak reserved |
| --- | --- | --- | --- | --- |
| seed 7, first after start | 45.758 | 42.976 | 2.492 | 6698 MiB |
| seed 11, concurrent pair, served first | 46.115 | 43.307 | 2.523 | 6698 MiB |
| seed 12, concurrent pair, queued behind it | 92.561 | 43.546 | 2.608 | 6698 MiB |

The queued request waited 46.446 s for the one ahead of it and its `render_s`
did not move: one worker, one model on the card. `nvidia-smi` sampled every
200 ms during the first request peaked at 7158 MiB of 8188.

**Re-run after the adapter cut, 2026-11-15.** The same seven checks are green
and the run exits 0. The seed-7 still from `POST /generate` is byte-identical to
the pre-cut file, `sha256 ff3b84a08e48e1b0c70bc96aa40c10936e782f183b6443ae1157e1c654dbe5c4`
before and after — the refactor moved the sequencing and changed no pixel. The
request timings are within noise of the table above. Measured boot is 18.0 s
against the original 15.1 s for two reasons, both accounted for: the adapter's
stack is imported lazily inside `boot` now (that import was always paid, just
outside the clock before), and `prepare` loads the transformer once to establish
the census before the port binds (~1 s of new work, and the warm-up that follows
reloads the same file from the page cache that load filled). The warm-up itself
fell to 14.1 s. HD was re-checked through the server: 2560×1440 from a 1280×720
base, `upscale.from: [1280, 720]`, `upscale_s` 4.643.

**Verdict.** P4's exit criterion is observed: `start` returns after warm-up
(17.96 s measured, of which 14.13 s is the discarded 512×512 render),
`/health` answers warm with the census 239 / 282 / 0 / 521, a second `start`
exits 0 and reports the same pid with one process alive, `stop` releases the
card and removes the state file in 0.75 s, and two concurrent requests both
succeed with a serialised wait. The run's exit code is the number of failed
checks.

**How to regenerate.** Re-run the command. It is destructive of server state by
design: it stops whatever is running on port 8420 and starts its own, so it
needs the card free. Each pass costs about four minutes of GPU time — one
warm-up, four 1280×720 renders and one serialised pair.
