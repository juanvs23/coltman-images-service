# AGENTS

Instructions for coding agents working in this project.

## Read first

1. `docs/protocol.md` — the law.
2. `docs/context.md` — purpose, structure, environment.
3. `docs/roadmap.md` — phases and debt.
4. `docs/changelog.md` — changes.

## Project rules

- Docs must not lie. When a change alters what a document describes, update that document in the same work unit.
- One changelog entry per work unit.
- Every `[DEBT]` needs a roadmap contract: marker, reason, target spec, steps.
- The ignore file is law. Do not weaken `.gitignore`.
- Conventional commits only. No AI attribution, no co-author trailers.
- Evidence for integration and E2E runs lives in `tests/<type>/<name>/`, with a committed `README.md` and a gitignored `evidence/` subfolder.
- Canonical artifacts are written in English.
- One rule, one owner. The law is `docs/protocol.md` and is never copied elsewhere.
- The system is self-contained. Never add a reference to another project.

## Commands

All commands below are built and exercised by the test matrix.

| Command | Purpose | State |
| --- | --- | --- |
| `coltman-images start` | power on and warm up | built |
| `coltman-images generate --prompt "..."` | render one still and print its path | built |
| `coltman-images stop` | graceful shutdown | built |
| `.venv/bin/python -m unittest discover -s tests -v` | run the test matrix | built |

## Guardrails

- Never read or write outside the project tree. The foreign stores this project copied from (a model store and a component store, both outside this tree) were deleted on 2026-11-15; `model/assets/` holds the only copies of the weights.
- Dependencies live in the project's own `.venv`, pinned in `requirements.txt`. The foreign venv that store carried is not a dependency and must not be modified.
- Never write outside the declared output paths and `run/`.
- Never create a git repository without the operator's explicit order.
- Never write secrets or `.env` into the project.
