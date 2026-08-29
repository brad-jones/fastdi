---
description: Workspace-level ambient instructions for this repo.
---

### APM Agent Harness Configuration

This repo uses [Microsoft's Agent Package Manager (apm)](https://microsoft.github.io/apm/). Refrain from editing files
like AGENTS.md, CLAUDE.md, GEMINI.md, .github/copilot-instructions.md, or anything under .claude/, .cursor/,
.github/instructions/, .agents/, .grok/, .kiro/, .opencode/, .windsurf/ directly. Instead, edit the source of truth in
`.apm/` and run `apm install` (and `apm compile` when the target needs it) to regenerate the output files. More
information about APM can be found in the `apm` skill.

### Pixi Development Environment

This repo is built on [pixi](https://pixi.prefix.dev/latest/). All tooling is managed via `pixi.toml`. Always prefix
commands with `pixi run` (eg: `pixi run -- uv run foo.py`) to ensure the correct environment is used. More information
about pixi can be found in the `pixi` skill.

#### Downloaded Dependencies

**IMPORTANT: Never search the entire root filesystem for dependencies! eg: Any command starting with `find /` is
expressly forbidden. This is too slow.**

##### Python Virtual Env Location

The Python virtual environment is located at the root of this repo: `./.venv`. When looking for installed Python
packages, inspect this path rather than any other location.

### Task Runner

We use [Task (go-task)](https://taskfile.dev/) (`Taskfile.yaml`) for orchestrating our automation. It's our own
documented interface to our tooling — it wraps extra setup (env vars, flags, pre-steps, package-manager detection) that
a bare `npm test` or `go build` would skip. Read it before guessing. More information about how to use task effectively
can be found in the `task` skill.

#### Additional Scripts & Automation

The `scripts/` directory holds automation that does not easily fit into a Taskfile. **Rule of thumb:** if you are
tempted to embed multi-line bash inside YAML, write a Python script in `scripts/` instead.

Scripts are self-contained Python, runnable via `uv` with dependencies declared inline
(<https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies>):

```bash
uv run scripts/<script-name>.py
```

> Always add the she-bang line (`#!/usr/bin/env -S uv run --script`) to the top of scripts & ensure they are executable
> (`chmod +x scripts/<script-name>.py`), per
> <https://docs.astral.sh/uv/guides/scripts/#using-a-shebang-to-create-an-executable-file>.

##### Windows Support

A note about Windows support: she-bang lines are not supported on Windows. Therefore all scripts must be exposed via a
Taskfile task, either directly or indirectly (ie: as part of a larger task).

_The she-bang line is simply a convenience for Unix-like systems._

##### Script Location

This is a monorepo and may have multiple `projects/` and `libs/` directories. Each with their own Taskfile. Scripts that
are shared across the entire repo should be placed in the top-level `scripts/` directory. Scripts that are specific to a
project or library should be placed in the `scripts/` directory of that project or library.

### Using Git Effectively

#### Conventional Commits

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) standard for all commit messages.
Refer to the `git-commit` skill for guidance on how to write commit messages that comply with this standard.

#### Hooks

We use [Lefthook](https://github.com/evilmartians/lefthook) for git hooks (`lefthook.yaml`). Hooks are installed
automatically via `task init`. More information about how to use lefthook effectively can be found in the `lefthook`
skill.

#### Always Use --no-pager

When running git commands, always pass `--no-pager` to prevent the shell from hanging on interactive pager output (e.g.
`less`).

```bash
git --no-pager log
git --no-pager diff
git --no-pager show
```

The flag goes immediately after `git` and before the subcommand.
