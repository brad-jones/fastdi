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
`src/<name_with_underscores>/main.py`, and tests first, and edit them in place rather than starting over.

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

Create `./specs/<name>/` (kebab-case, named for the capability, e.g. `constructor-injection`, `scoped-lifetimes`).
Every spec has the same four files, and each has a distinct job. Keeping them in their lanes is what stops a spec
from silently turning into a second copy of the framework's unit tests:

```text
specs/<name>/
  README.md                      # the spec, in English - the authoritative source of truth
  pyproject.toml                 # uv workspace member
  src/
    <name_with_underscores>/     # e.g. constructor_injection/
      __init__.py
      main.py                    # a toy app, and the container builder the tests drive
  tests/
    test_<name>.py               # happy-path integration tests over main.py
```

**The spec covers the happy path only.** That is the single most important rule here, and the one most likely to be
violated by accident. A spec exists to show what the capability _looks like when it works_ — the API a user writes,
the objects they get back, the behavior they can observe. Error conditions, edge cases and sad paths are described
exhaustively in `README.md` and tested exhaustively in the root `./tests/`, by `plan-implementation` and
`execute-plan`. They do not appear in `main.py` or in the spec's test suite at all.

### `README.md` — the spec

What this capability is, the public API it introduces (classes, functions, decorators — signatures included),
expected behavior including edge cases and error conditions, and a couple of worked examples in prose. Also state
what's explicitly **out of scope**, so `plan-implementation` doesn't design for it.

This is what a human or LLM reads to understand _what_ to build, and it is the source of truth `plan-implementation`
reads from. It is the right place — the only place — for exhaustive detail. Be thorough here precisely _because_ the
example and tests aren't: every error condition, boundary and invariant you want implemented has to be written down
here, or nothing downstream will know to build it. Describing behavior you don't test in this project isn't a gap;
it's the intended division of labour.

### `src/<name_with_underscores>/main.py` — the toy example

Written as if `fastdi` already exists and works. It will fail until `./src/fastdi` implements it; that's expected at
this stage. It has two jobs, and they constrain how it's written:

1. **It's a demo.** Running `uv run specs/<name>/src/<name_with_underscores>/main.py` must print something a human
   can read and learn the capability from. `main()` prints and does nothing else — in particular, **no `assert`
   statements in `main()`**. Assertions belong in the test suite, where a failure names itself and doesn't vanish
   under `python -O`.
2. **It's the test suite's fixture.** Container setup lives in a module-level builder function the tests import and
   call — never inline inside `main()`:

   ```python
   def build_provider() -> ServiceProvider:
     """Registers the whole app: every registration shape, all transient."""
   ```

Keep the domain small, concrete and boring — a handful of classes that read like a real, tiny app, all wired up
successfully. Don't add classes that exist only to fail (a deliberately circular pair, a service with an
unsatisfiable constructor); they make the example harder to read and their behavior is the root `./tests/`'s
concern. Any value a test will want to assert on (a default DSN, a fixed timestamp) should be a module-level
constant the test imports, rather than a literal duplicated in both files.

**The package name must be unique across all specs**, which is why it's the spec's own name with underscores rather
than something generic. `sys.path` and `sys.modules` are process-global, so if two specs both exposed a top-level
`main`, a repo-wide `pytest` run would import whichever it reached first and silently hand that same module to every
other spec's tests — wrong objects, passing-looking imports, no error. The per-spec package makes that structurally
impossible. Import it from the tests by its full path:

```python
from constructor_injection.main import build_provider, main
```

`__init__.py` needs nothing in it but a one-line docstring.

### `pyproject.toml`

A `uv` workspace member, and nothing else:

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
- **Do not add a `[tool.pytest.ini_options]` table here.** pytest treats the nearest ancestor `pyproject.toml`
  that has that table as its rootdir, so adding one would make the spec its own rootdir — and pytest only loads
  `conftest.py` files from rootdir down, so the repo-root `conftest.py` that puts spec packages on `sys.path` would
  be skipped and the imports would break. Test configuration is repo-wide and lives in the root `pyproject.toml`.
- The root `pyproject.toml`'s `[tool.uv.workspace] members = ["specs/*"]` picks the directory up as a member
  automatically, but that does not install or lock it — see step 5.

### `tests/test_<name>.py` — integration tests

**These are happy-path integration tests, not unit tests.** They import from the spec's `main.py`, drive the
container it builds through the public `fastdi` API, and assert the behavior a user of the library would care about.
Under a dozen tests is normal.

No wiring is needed to make them runnable: the repo-root `conftest.py` globs every `specs/*/src` onto `sys.path`, and
the root `pyproject.toml` has `testpaths = ["tests", "specs"]`. A bare `pytest` at the repo root collects the
framework suite and every spec suite in one go, and `pytest specs/<name>` runs just this one.

What belongs here:

- The container builds, and the resulting graph comes out fully wired.
- The resolved objects actually do their job — call a method, assert on what it returns.
- Semantics observable from outside the container (same instance or not, what gets injected where).
- A smoke test that `main()` runs and prints what it should (via `capsys`).

What does **not** belong here — this is the part that's easy to get wrong:

- Error conditions. No `pytest.raises`, no assertions about exception types, messages or attributes.
- Exhaustive enumeration of every constructor shape, parameter form or inference edge case.
- Anything needing throwaway classes defined in the test file rather than in `main.py`. If the toy app can't express
  it, it isn't an integration concern.
- Anything asserting on internals rather than public behavior.

That coverage is real and necessary — it's just unit-level, and it isn't this project's file. `plan-implementation`
is responsible for specifying it and `execute-plan` for writing it, both under the root `./tests/`. Duplicating it
here doubles the maintenance and buries the spec's story under fixtures. If you catch yourself reaching for
`pytest.raises` or parametrizing over a dozen malformed registrations, you're writing the wrong file: describe those
conditions in `README.md` prose and let the plan pick them up.

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

Before handing back, check all four of these:

- Does `README.md` unambiguously describe the capability, including all the error conditions and edge cases the
  example and tests deliberately don't cover?
- Does `src/<name_with_underscores>/main.py` read as a small, comprehensible app that only ever succeeds, with its
  container setup in an importable builder function and no assertions in `main()`?
- Do the tests drive `main.py` and stay on the happy path, or have they drifted into unit tests with their own
  fixture classes and `pytest.raises` blocks?
- Would a `plan-implementation` run be able to derive a concrete, buildable design from this — and know which
  unit-level cases to plan for `./tests/` — without more back-and-forth?

Iterate with the user until yes to all four.

## 7. Stop here

Do not write or modify anything under `./src/fastdi` or `./tests/` (the root framework test suite). Do not run
`plan-implementation` or `execute-plan` yourself — scaffolding/updating the spec is the complete task. Tell the user
what spec was created/updated and, if step 2 surfaced a design concern, summarize what you flagged and how the spec
resolved it.
