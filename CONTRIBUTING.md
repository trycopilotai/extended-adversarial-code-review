# Contributing

This repository is one skill, one small program with its
tests, and the scripts that build and check the demo images.

## Run the checks first

```sh
make check
```

That runs `tests/test_round_yield.py` and
`tests/test_integrations.py`. The first needs only
`python3`; the second also needs `git` and nothing else. The
second needs a real clone with its history and tags, because
it reads `git ls-files`, `git log` and the release tag.

**The packaging contract asserts on the README.** These will
fail on an innocent-looking prose edit:

- the claim line at the top of the README must appear
  verbatim, and each of the eight clause lines it refers to
  must be in the recorded transcript;
- each install block must carry its own `release=` pin at
  the version both plugin manifests ship;
- `SKILL.md` must stay under 500 lines.

If you change one of those, change the thing it describes
too.

## Changing the program or the transcript

The demo images are built from the recorded transcript, and
the transcript is a real run of the program. After a change
to `round_yield.py` that alters its output:

```sh
python3 skills/extended-adversarial-code-review/scripts/round_yield.py \
  --explain examples/rounds.json
```

Record the new session in `evidence/transcripts/`, update
the hashes in `evidence/demo-manifest.json`, then run
`make demo`. `make assets` rebuilds the social preview and
needs Chrome or Chromium; `make asset-check` does not.

## What is most useful

Open an issue for any of these. The labels
`good first issue` and `help wanted` mark the ones that are
ready to pick up.

- **A record the program judges wrongly.** A loop that
  should have stopped and was told to continue, or the
  reverse. Attach the per-round JSON record.
- **Measurements from another review loop.** The figures in
  `SKILL.md` come from one episode. Per-round counts from a
  different loop, on different code, are the most valuable
  thing this repository can receive.
- **A stopping clause that is missing.** Describe the loop,
  why none of the eight clauses fired, and what you would
  have wanted the program to say.

## Pull requests

Prose changes to `SKILL.md` are welcome. Say what an agent
did before the change and what it does after, on the same
input. "This reads better" is not reviewable.

Keep `SKILL.md` under 500 lines; the suite enforces it.
Frontmatter carries `name` and `description` and nothing
else.

The top-level `skill` is a symlink to
`skills/extended-adversarial-code-review/`. Do not reverse
that orientation.

Commit with your own identity and no `Co-authored-by`
trailer of any kind. The suite fails on one anywhere in
history, so do not apply review suggestions through the
GitHub UI.
