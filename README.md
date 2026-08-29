# FastDI

FastDI is an IoC (Inversion of Control) container for Python, inspired by
[Microsoft.Extensions.DependencyInjection](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection)
from the .NET ecosystem.

It stands on its own as a general purpose DI container for any Python application, but it's also being built with a
specific end goal in mind: bridging [FastAPI](https://fastapi.tiangolo.com/)'s and
[FastMCP](https://gofastmcp.com/)'s independent dependency injection systems behind a single, consistent container.

## Spec Driven Development

This project follows a spec driven development process: the specs under `./specs/` are the source of truth for
FastDI's public API, and the framework code under `./src/` is only ever written or rewritten by an LLM in response to a
spec changing. A human (or an LLM) never hand-edits `./src/` directly.

Three skills drive this workflow (see `.apm/skills/`):

- **`create-spec`** — turns a short English description of desired behavior into a new self-contained spec project
  under `./specs/<name>/`. It never touches `./src/`; its only job is to produce (and help iterate on) a spec that
  accurately reflects the API you want, catching designs that aren't actually implementable in Python along the way.
- **`plan-implementation`** — reads every spec plus the current state of `./src/`, and writes a markdown implementation
  plan under `./docs/plans/` describing the diff needed to satisfy them, including any extra unit tests to add under
  `./tests/`.
- **`execute-plan`** — reads a plan from `./docs/plans/` and implements it, iterating until every spec's test suite and
  the main `./tests/` suite pass.

## Repository Layout

- `./specs/` — one self-contained Python project per public API surface: a `README.md` describing the spec in
  English, a runnable `main.py` example, and a pytest suite. Each spec depends on `fastdi` from `./src/` via a `uv`
  workspace source, and is expected to fail until the corresponding framework code exists.
- `./src/` — the `fastdi` package. This is the only thing published from this repository.
- `./tests/` — framework-level unit tests for `./src/`, covering internals beyond what any single spec exercises.
- `./docs/decisions/` — architectural decision records explaining the tooling and structural choices in this repo.
- `./docs/plans/` — implementation plans produced by the `plan-implementation` skill, kept for posterity.

## Tooling

- [uv](https://docs.astral.sh/uv/): package management, workspace management, and running self-contained scripts.
- [Ruff](https://docs.astral.sh/ruff/) & [Pyright](https://microsoft.github.io/pyright/): Python linting, import
  sorting and type checking.
- [pytest](https://docs.pytest.org/): the test runner for both `./specs/*/tests` and `./tests`.
- [Pixi](https://pixi.prefix.dev/latest/): a fast, modern, and reproducible package management tool for the rest of
  the dev environment (uv, dprint, task, lefthook, cocogitto, apm, sops).
- [Taskfile](https://taskfile.dev/): a fast, cross-platform build tool inspired by Make, designed for modern workflows.
- [APM](https://microsoft.github.io/apm/): a package manager for agent instructions, skills, and rules, compiling them
  to whichever coding agent you use.
- [Lefthook](https://lefthook.dev/): a Git hooks manager, Fast, Powerful, Simple.
- [Dprint](https://dprint.dev/): a pluggable and configurable code formatting platform, used here for JSON, YAML,
  Markdown, TOML and Python (via Ruff).
- [Cocogitto](https://docs.cocogitto.io/): the conventional commit toolbox.

For exact details on why we decided to use the tools we did, see the ADRs in `./docs/decisions/`.

## Getting Started

Clone the repo and either let [direnv](https://direnv.net/) activate the environment for you (`.envrc` runs `pixi
shell-hook` and `task init` automatically on `cd`), or run `pixi shell` / `task init` manually.

### direnv (optional)

[direnv](https://direnv.net/) is a shell extension that loads and unloads environment variables based on the current
directory. This repo's `.envrc` uses it to automatically activate the pixi environment (via `pixi shell-hook`) and run
`task init` whenever you `cd` into the project, so you don't have to remember to do it yourself.

It's an optional convenience, not a requirement: nothing in this repo depends on direnv being installed, and everything
it does for you can also be done manually (`pixi shell`, `task init`). If you want the automation, install direnv
yourself and [hook it into your shell](https://direnv.net/docs/hook.html); it isn't managed by pixi because it needs to
be active before pixi's own shell hook can run.

#### Silencing direnv for AI agents

direnv prints a `direnv: loading ...` / `direnv: export ...` line every time it (re)loads `.envrc`. That's useful for a
human in an interactive terminal, but it's just noise cluttering the output an AI coding agent sees when it runs shell
commands, and can make it harder for the agent to see the actual output. This repo silences it for VS Code's Copilot
Chat terminal specifically (see `chat.tools.terminal.terminalProfile.linux` in `.vscode/settings.json`), but that only
covers that one surface.

Terminal-based agents (Claude Code, Copilot CLI, etc.) run in your normal shell, so there's no per-repo hook that can
catch them - direnv reads its `DIRENV_LOG_FORMAT` setting from the environment _before_ `.envrc` gets a chance to run,
so nothing in this repo can change it in time. If you want those agents silenced too, add a guard to your own shell rc,
before the line that installs the `direnv hook`, that sets `DIRENV_LOG_FORMAT=""` only when an agent-specific
environment variable is present (see the comment in `.envrc` for the exact recipe). This also requires a
`~/.config/direnv/direnv.toml` to exist (any content, even empty) - direnv 2.36+ only honors `DIRENV_LOG_FORMAT` from
the environment when that file is present.
