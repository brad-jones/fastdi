---
status: accepted
date: 2026-06-01
---

# Use monorepo structure for closely related projects and libraries

## Context and Problem Statement

As the codebase grows, it will contain multiple deployable applications and shared libraries that depend on one another.
We need to decide whether to host these in a single repository (monorepo) or in separate repositories (polyrepo). The
relationship between the projects and libraries is close enough that coordinated changes and shared tooling are expected
to be common.

## Considered Options

- Monorepo — all projects and libraries in one repository
- Polyrepo — each project or library in its own repository

## Decision Outcome

Chosen option: "Monorepo", because it simplifies cross-cutting changes, keeps shared tooling (pixi, Taskfile, linting,
hooks) in one place, and makes it easier to keep library consumers in sync with library changes.

### Consequences

- Good, because atomic commits can span multiple projects and shared libraries.
- Good, because a single set of tooling and CI configuration applies to everything.
- Good, because dependency version alignment is enforced naturally.
- Bad, because the repository grows larger over time and clone/CI times may increase.
- Bad, because access control is coarser — all contributors see all projects.

## Repository Layout

This repo follows a spec-driven development process (see `create-spec`, `plan-implementation` and `execute-plan` in
`.apm/skills/`), which shapes the monorepo layout:

- `./specs/` — one self-contained `uv` project per public API surface: a `README.md` describing the spec in English, a
  `main.py` demonstrating it, and a pytest suite. Each spec is a `uv` workspace member that depends on `fastdi` from
  `./src/`.
- `./src/` — the `fastdi` package itself. This is the only thing published from this repository, and is only ever
  written or rewritten by an LLM in response to a spec change.
- `./tests/` — framework-level unit tests for `./src/`, covering internals that aren't exercised by any one spec.

If a solution does not require this specs/src/tests split, it can be ignored until it becomes relevant.
