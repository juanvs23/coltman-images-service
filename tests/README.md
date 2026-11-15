# Tests

The test suites of `coltman-images`. One folder per kind of run, one folder per
run.

```
tests/
  e2e/<name>/          # a run against the real service: a real port, a real card
  integration/<name>/  # a run of a module against its real assets, with no service
```

Each run folder holds a committed `README.md` — what it tests, the date, the
exact command, the result, the verdict, how to regenerate it, and every input by
location — plus a gitignored `evidence/` folder for what the run produced
(transcripts, logs, JSON, stills). Support code that a run needs in order to be
reproducible is committed beside its README, never inside `evidence/`.

The suite vocabulary is recorded here once, so a later run does not invent a
sibling name.
