# Security

## Reporting a vulnerability

Report privately through GitHub:
<https://github.com/trycopilotai/extended-adversarial-code-review/security/advisories/new>

That opens a private security advisory visible only to the
maintainers. Do not put the details of a vulnerability in a
public issue.

If that link shows "Not Found", private reporting is not
turned on for this repository. Open a public issue titled
"Security report waiting" that says only that you have a
report, with no details, and a maintainer will arrange a
private channel.

## What is in scope

- **Prompt content that redirects an agent.** `SKILL.md` and
  `references/a-round-concretely.md` are instructions an
  agent follows. Text in either that makes an agent run
  commands, send repository contents elsewhere, or treat
  reviewed code as instructions is a valid report.
- **The stopping-rule program.**
  `skills/extended-adversarial-code-review/scripts/round_yield.py`
  reads one JSON file named on its command line and prints
  to standard output. It writes nothing, starts no process
  and opens no network connection. A record that makes it do
  any of those is a finding.
- **The install blocks.** The two README blocks run
  `mkdir -p`, `mktemp -d`, `git clone`, `cp`, `mv` and
  `rm -rf`, all inside one skills directory under `$HOME`. A
  repository state that makes either block write or delete
  outside its install target is in scope.
- **The build scripts.** `assets/build.py` finds a Chrome or
  Chromium binary from a fixed candidate list, runs it
  headless with a temporary profile directory, and writes
  the preview PNG and its stamp. `scripts/generate_demo.py`
  writes two SVG files; `scripts/verify_demo.py` only reads.
  `tests/test_integrations.py` runs `git` against the
  repository root and runs the program with the arguments
  recorded in the transcript. `tests/test_round_yield.py`
  writes small JSON files to the system temporary directory.
- **Disclosure in the shipped bytes.** The guidance reports
  figures from a private review episode. Anything in this
  repository that identifies the reviewed program, a person,
  or a private system is a valid report.

## What is out of scope

The skill advises. It does not dispatch reviewers, edit
code, or stop a loop by itself. A report that an agent kept
running after the program printed `STOP` describes that
agent, not this repository.

Behaviour of Claude Code, Codex, or any other host is out of
scope here. Report those to their own vendors.
