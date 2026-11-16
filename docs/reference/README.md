# Reference material

These two files are the measurements the project's cost model is built on. They were produced before this project existed and were copied here so the numbers travel with the system instead of living outside it.

They are **evidence, not law**. `docs/protocol.md` is the law. Where a file here and the law disagree, the law wins — and the law cites these numbers, so a disagreement is a defect in the law or in its citation, never permission to change the law silently.

## The design that no longer exists

Two further documents lived here until 2026-11-15: `zimage-fp8-system.md`, which described the predecessor as a batch command-file runner with `per_command` and `warm_process` executors, and `zimage-adapter-removal.md`, the record of that adapter's removal. Both were deleted, together with the predecessor's own tree and the runtime scaffolding it left behind, because that design no longer exists anywhere and a document describing it only invites re-opening decisions the operator already closed. What those documents still had to say was the measurement, and the measurement survives in the two files below.

Nothing here may be used to re-open those decisions. A change to any of them is an operator ruling recorded in `docs/protocol.md`.

## Foreign names

These files name other projects, channels and vendor tooling because they are historical records of where the numbers came from. Those names are provenance, not dependency: the system reads nothing from them (protocol section 2).

## Paths

The absolute paths these records were written with have been replaced by placeholders — `<model store>`, `<predecessor>`, `<bench>`, `<the calling project>` — because the machine layout they described is not this project's business and one of them named a client's workspace. The substitution is editorial and it touched no number: every measurement in these files is exactly as it was recorded.

## The files

| File | What it carries |
| --- | --- |
| `zimage-fp8-speed.md` | the production path's timing, the offload-profile comparison, the GPU, disk, swap and page-cache measurements |
| `zimage-fp8-vs-int8.md` | the A/B between both quantization arms, the blind quality adjudication, and both checkpoints' header censuses |
| `steps-ladder.md` | the nine-step range measured over five seeds on a hostile prompt: the time curve, the SSIM convergence, and where the ceiling actually is |

`upstream/` holds the vendor cards and the official README, with its own README extracting what they add.
