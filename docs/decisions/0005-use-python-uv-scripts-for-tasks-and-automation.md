---
status: accepted
date: 2026-06-01
---

# Use uv-run Python scripts for tasks and automation instead of shell scripting

## Context and Problem Statement

Project automation often starts as short shell commands in a Taskfile or CI config, but grows into multi-line bash that
is hard to read, test, and maintain reliably across platforms. We need a rule that defines when to reach for a
higher-level scripting language instead of embedding shell logic inline in YAML.

## Considered Options

- Python, run via `uv run` with inline script dependencies
- Deno (TypeScript)
- Bash / shell scripts embedded in YAML

## Decision Outcome

Chosen option: "Python, run via `uv run`", because this repo is a Python project — `uv` is already the package manager
in use, so scripts need no separate runtime, and each script can declare its own dependencies inline
(<https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies>) with no shared `node_modules`/lockfile
overhead, and runs identically everywhere.

**Rule of thumb:** if you are tempted to embed multi-line bash inside YAML, write a Python script in `scripts/`
instead, with a `#!/usr/bin/env -S uv run --script` shebang
(<https://docs.astral.sh/uv/guides/scripts/#using-a-shebang-to-create-an-executable-file>).

> Any higher-level scripting language would work here so long as it can be executed without extra package install
> steps — the script MUST be self-contained. This repo previously used Deno for exactly that reason (TypeScript out of
> the box, no separate install), but since the project itself is Python, `uv run --script` gives the same
> self-contained guarantee without a second language/runtime in the toolchain.

### Consequences

- Good, because scripts need no separate runtime beyond `uv`, which the project already depends on.
- Good, because dependencies are declared inline per-script, so there's no shared `node_modules`/lockfile overhead and
  no separate install step.
- Good, because scripts can be tested and linted with the same Ruff/Pyright tooling as the rest of the codebase.
- Bad, because Python lacks Deno's built-in secure permission model — scripts run with the same ambient permissions as
  any other local Python process.
