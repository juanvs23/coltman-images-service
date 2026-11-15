# P5 — `coltman-images generate` as the API's client

This folder is the phase's exit evidence. `run.sh` starts nothing on its own; it
runs the declared surface end to end and prints `CHECK n: ok` or
`CHECK n: FAILED <why>` per assertion. `evidence/transcript.txt` is the run
product and is gitignored; the committed `README.md` you are reading is the
record.

Phase exit criterion (roadmap): *one prompt through the CLI writes the still and
prints its path; a direct POST for the same seed produces the same bytes.*
That second half is guard 7 and it is measured with `cmp`, not with a
similarity score.

## How to run

```bash
./tests/e2e/p5-cli-parity/run.sh
```

It starts the server itself if it is not running, refuses to touch a running one
if it is, and stops what it started. Four renders, about four minutes; exit 0
means every check passed.

## What the run measured — 2026-11-15, `failures: 0`, `RUN_EXIT=0`

| Check | Assertion | Observed |
| --- | --- | --- |
| 1 | `generate` with no server exits 4 and starts nothing | exit 4, stdout empty, no state file created |
| 2 | a plain generate prints the path and nothing else | stdout exactly the path, stderr 0 bytes, PNG signature present |
| 3 | `--json` prints the declared response object | all ten fields present, `upscale: null`, same bytes as check 2 |
| 4 | **CLI and a direct POST for the same seed are byte-identical** | `aa6f053913ddf300` both |
| 5 | a refused request exits 2, on stderr, writing nothing | exit 2, `width: expected a positive multiple of 16`, no file |
| 6 | `--upscale` reaches the stage | 2560×1440, `from [1280, 720]`, `scale 2`, `upscale_s 4.645`, `duration_s 51.926` |
| stop | the server leaves nothing behind | state file gone, no process |

Two numbers worth keeping beside the transcript: the CLI's request cost 51.9 s
for HD (44.3 s render + 4.6 s stage + ~2.9 s load), and the CLI adds no deadline
of its own — the protocol declares no per-request ceiling, so a client that
invented one would refuse work the server accepts.

## What this folder does not prove

The eleven guards of protocol section 10 are P6's business. This run proves the
CLI's contract and the parity claim only: it says nothing about determinism
across processes (measured in P2), single-flight (P4), or the census (P4).
