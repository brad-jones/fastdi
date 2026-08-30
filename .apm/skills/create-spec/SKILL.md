---
name: create-spec
description: Scaffold or iterate a FastDI spec project under ./specs/<name>/ from a short English description of desired IoC container behavior. Use this whenever asked to write, add, draft, or refine a FastDI spec, or to describe a piece of the public API surface FastDI should have. Never touches ./src/fastdi or ./tests/ — that's the execute-plan skill's job, after plan-implementation has written a plan.
---

# create-spec

FastDI is built spec-first: `./specs/*` is the source of truth for what the `fastdi` package's public API looks like
and how it behaves. Framework code under `./src/fastdi` is only ever written or rewritten in response to a spec
changing — never the other way around. This skill's only job is producing (or refining) a spec. It must never write,
edit, or even sketch code under `./src/fastdi`.

## 1. Understand the request

Read the description of the desired behavior the user gave you. If it's vague on a point that meaningfully changes the
public API shape (e.g. "should registration be a decorator or a method call?", "does this need scoped lifetimes or
just singleton/transient?"), ask before scaffolding — a spec built on a guessed API surface just gets rewritten anyway.

If an existing spec under `./specs/` is being refined rather than created fresh, read its current `README.md`,
`main.py`, and tests first, and edit them in place rather than starting over.

## 2. Sanity-check the design against what Python can actually do

Before writing anything, check the proposed API for patterns that sound reasonable in English but don't translate to
working Python, and propose the idiomatic alternative instead of silently going along with an impossible design:

- **Overloading by parameter type** (e.g. "`resolve()` should behave differently depending on whether you pass a type
  or a string") — Python doesn't dispatch on argument type at the call site the way C#/Java do. Use
  `functools.singledispatch`/`singledispatchmethod`, `typing.overload` (type-checker-only, no runtime dispatch), or
  distinct method names instead.
- **Compile-time reflection / static analysis of generic type parameters** — Python has no compile step, so anything
  requiring "the container knows `List[Foo]` was requested vs `List[Bar]` at compile time" needs to be resolved via
  runtime `typing.get_type_hints`/`get_args`, explicit type tokens, or `Annotated[...]` markers instead.
  Constructor-parameter type inference is fine (Python has real runtime type hints to inspect) — the impossible part is
  anything requiring info that only exists before the interpreter runs.
  Prefer explicit registration keys over deep implicit inference where the two diverge.
- **True private/protected members enforced by the language** — Python convention (`_foo`) is not enforcement.
  Don't design an API whose correctness depends on consumers being unable to reach internals.
- **Method overload resolution by arity + type together** (constructor injection needs to pick one `__init__` based on
  registered dependency types) — fine if there's exactly one constructor to inspect (the normal case); flag it if the
  spec implies picking between multiple candidate constructors/factories by signature matching, and suggest an
  explicit factory-selection mechanism instead.
- **Synchronous API wrapping an inherently async resolution graph** (e.g. a dependency's factory is a coroutine) —
  either the whole resolution path is async-aware or it isn't; flag a spec that mixes sync `resolve()` with async
  factories without saying which wins.
- **Circular constructor dependencies** — decide and document what happens when two registered services depend on
  each other (error at registration/resolve time, lazy proxy, etc.) rather than leaving it implicit.

When you find one of these, don't just refuse — propose the closest idiomatic Python equivalent and ask the user
(or note it directly in the spec's README) which they want.

## 3. Scaffold the spec project

Create `./specs/<name>/` (kebab-case, named for the capability, e.g. `constructor-injection`, `scoped-lifetimes`)
containing:

- **`README.md`** — the spec itself, in English: what this capability is, the public API it introduces (classes,
  functions, decorators — signatures included), expected behavior including edge cases and error conditions, and a
  couple of worked examples in prose. This is what a human or LLM reads to understand _what_ to build; it is the
  source of truth `plan-implementation` reads from.
- **`main.py`** — a runnable example exercising the API described in the README, written as if `fastdi` already
  exists and works. It will fail until `./src/fastdi` implements it — that's expected at this stage.
- **`pyproject.toml`** — a `uv` workspace member:

  ```toml
  [project]
  name = "spec-<name>"
  version = "0.0.0"
  requires-python = ">=3.14"
  dependencies = ["fastdi"]

  [tool.uv]
  package = false

  [tool.uv.sources]
  fastdi = { workspace = true }
  ```

  Notes on that template:
  - `requires-python` must match the root `pyproject.toml`'s value — copy it from there rather than from this
    skill, which will drift.
  - `package = false` marks the spec a virtual workspace member: it's never built or published, so it needs no
    `[build-system]`.
  - Don't add a `[dependency-groups] dev = ["pytest"]` here. `uv sync` only installs the _root_ project's dependency
    groups, so a member-level group is inert unless someone remembers `--all-groups`. pytest comes from the root
    `[dependency-groups] dev` and is already available.
  - The root `pyproject.toml`'s `[tool.uv.workspace] members = ["specs/*"]` picks the directory up as a member
    automatically, but that does not install or lock it — see step 5.
- **`tests/test_<name>.py`** — a pytest suite asserting the behavior described in the README, including the edge cases
  and error conditions, not just the happy path from `main.py`.

## 4. Make it re-runnable

This skill is meant to be invoked repeatedly on the same spec as it's refined by humans and LLMs. When `./specs/<name>`
already exists, treat the invocation as "update this spec to reflect the new description," editing the README, example,
and tests in place — don't blow away prior refinements that are still valid.

## 5. Re-lock the workspace and check the spec is committable

Adding (or changing the dependencies of) a spec changes workspace resolution, and `uv.lock` won't pick that up on its
own — `task init` skips `uv sync` unless `uv.lock` itself has changed. So from the repo root, run:

1. `uv sync` — re-resolves the workspace and refreshes `uv.lock` with the new member.
2. `task fmt` — formats the spec's Python, Markdown and TOML.
3. `task lint` — must be clean before you hand back.

`task lint` is expected to pass even though the spec targets an API that doesn't exist yet: pyright is configured in the
root `pyproject.toml` to exclude `./specs`, precisely so a spec can sit unimplemented without breaking the pre-commit
hook or CI. `dprint` and `ruff check` _do_ still cover specs, so genuine formatting or lint errors in what you wrote
are yours to fix.

Do **not** run `task test` here. The spec's suite is supposed to fail until `execute-plan` implements it.

## 6. Review the spec as a whole

Does `README.md` unambiguously describe what `main.py` and the tests encode? Would a `plan-implementation` run be able
to derive a concrete, buildable design from this without more back-and-forth? Iterate with the user until yes.

## 7. Stop here

Do not write or modify anything under `./src/fastdi` or `./tests/` (the root framework test suite). Do not run
`plan-implementation` or `execute-plan` yourself — scaffolding/updating the spec is the complete task. Tell the user
what spec was created/updated and, if step 2 surfaced a design concern, summarize what you flagged and how the spec
resolved it.
