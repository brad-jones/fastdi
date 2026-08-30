---
status: done
date: 2026-08-30
completed: 2026-08-30
specs: []
rules: [public-api-requires-docstrings]
---

# Public API docstring compliance

## Context

`./docs/rules/public-api-requires-docstrings.md` is a newly authored rule (untracked in git, added after plan
[0001](0001-constructor-injection-transient-container.md) was already marked `done`), so the code that plan produced
predates it and was never checked against it. This plan closes that gap. No spec requires new behavior here — the
`constructor-injection` spec already passes and nothing about its observable behavior changes; this is purely bringing
`./src/fastdi` into compliance with a rule that postdates it. Hence `specs: []`: there is no spec this plan is
responsible for making pass, only a rule to satisfy.

## Current state

Per the rule, compliance is required for everything reachable from `fastdi.__all__`: `CircularDependencyError`,
`Factory`, `FastDIError`, `MissingDependencyError`, `RegistrationError`, `ServiceCollection`,
`ServiceNotRegisteredError`, `ServiceProvider`. Auditing the current code against that surface:

- Every module (`__init__.py`, `_collection.py`, `_provider.py`, `_errors.py`) already has a module docstring. No
  change needed.
- Every exported class already has a class docstring. No change needed.
- `Factory` is a `type` statement (PEP 695 alias), not a class/function/method/property — the rule's vocabulary doesn't
  reach it, and Python gives a `type` statement nowhere to hang a docstring anyway. No change.
- `ServiceCollection.__init__` takes no parameters, so per the rule's `__init__` carve-out it needs no docstring of its
  own. No change.
- **Missing, and this plan's whole scope:**
  - `ServiceCollection.add_transient` (the real implementation, not the `@overload` stubs) — no docstring.
  - `ServiceCollection.build_service_provider` — no docstring.
  - `ServiceProvider.__init__` — takes a `plan` parameter the class docstring doesn't cover — no docstring.
  - `ServiceProvider.get_service` — no docstring.
  - `ServiceProvider.get_required_service` — no docstring.
  - `ServiceNotRegisteredError.service_type`, `MissingDependencyError`'s four attributes, and
    `CircularDependencyError.chain` are all public (non-underscore) attributes of exported classes, per the rule's
    "attributes of the classes it exports" clause — none are documented anywhere today.
- Internal modules `_inspection.py`, `_registrations.py`, `_validation.py` export nothing from `fastdi.__all__`, so per
  the rule's own **Scope** section they stay exempt regardless of their docstring state. Left untouched.

## Rules applied

- **`public-api-requires-docstrings`** drives every change below. Two things it settles that would otherwise be
  judgment calls:
  - `ServiceNotRegisteredError`, `MissingDependencyError`, and `CircularDependencyError` all raise in their `__init__`
    with parameters that become public attributes of the same name. Rather than duplicating that documentation onto
    a separate `__init__` docstring, this plan documents each via a Google-style `Attributes:` section on the class
    docstring, which is exactly what the rule's `__init__` carve-out ("needs its own docstring only when it accepts
    parameters the class docstring doesn't already cover") is designed to make sufficient. No exception in this plan
    gets a separate `__init__` docstring.
  - `ServiceProvider.__init__` has no such carve-out available — `plan` isn't a public attribute (it's stored as
    `self._plan`) — so it gets a docstring of its own. Since the spec's public API deliberately omits `__init__` from
    `ServiceProvider` (construction only happens through `ServiceCollection.build_service_provider`), that docstring
    says so explicitly rather than pretending direct construction is a supported entry point.
  - The rule's vocabulary is "module, class, function, method, and property" — it does not reach `@overload` stub
    signatures (which exist purely for type checkers and are overwritten at runtime by the final implementation
    anyway, so a docstring placed on one would never be reachable via introspection). Only the real `add_transient`
    implementation gets a docstring.

## `./src/fastdi` changes

### 1. `src/fastdi/_errors.py`

Add an `Attributes:` section to each exception class docstring, documenting the public attributes `__init__` already
assigns. No behavior change; no `__init__` docstrings added (see Rules applied).

- `ServiceNotRegisteredError`: document `service_type` — "The type that was requested but has no registration."
- `MissingDependencyError`: document all four existing attributes, reusing the spec's own wording from
  [specs/constructor-injection/README.md](../../specs/constructor-injection/README.md)'s Exceptions section:
  `service_type` ("the service whose constructor could not be satisfied"), `implementation_type` ("the class whose
  `__init__` was being inspected"), `parameter_name`, `parameter_type` ("`None` when the parameter carries no
  annotation").
- `CircularDependencyError`: document `chain` — "the cycle, with the repeated service type at both ends."

### 2. `src/fastdi/_provider.py`

- `ServiceProvider.__init__`: add a one-line docstring stating it wraps an already-validated resolution plan and that
  callers should go through `ServiceCollection.build_service_provider` instead of constructing a `ServiceProvider`
  directly.
- `ServiceProvider.get_service`: add a docstring with `Args`/`Returns`, covering that it returns `None` for an
  unregistered `service_type` and does not swallow any other exception raised while resolving a registered
  factory/constructor (per [specs/constructor-injection/README.md](../../specs/constructor-injection/README.md)'s
  Resolution section).
- `ServiceProvider.get_required_service`: add a docstring with `Args`/`Returns`/`Raises`, naming
  `ServiceNotRegisteredError`.

### 3. `src/fastdi/_collection.py`

- `add_transient` (the implementation, not the overloads): add a docstring describing the three registration shapes,
  that it returns `self` for chaining, and every `RegistrationError` condition already implemented (both
  `implementation_type` and `factory` supplied; non-class `service_type`/`implementation_type`; abstract
  instantiation target; non-callable or `async def` `factory`; `service_type is ServiceProvider`).
- `build_service_provider`: add a docstring covering the snapshot semantics (later mutation of the collection doesn't
  affect a provider already built) and eager validation, with `Raises` naming `MissingDependencyError` and
  `CircularDependencyError`.

No other file changes. No new modules, no signature changes, no behavior changes — this plan only adds docstrings.

## `./tests/` additions

None. This plan changes no observable behavior — every existing test in `./tests/` and in
`specs/constructor-injection/tests/` continues to exercise the same code paths with the same results. Docstrings
aren't executable and have no test surface of their own.

## Verification

Standard verification only (`task fmt`, `task lint`, `task test`). `task lint` does not currently enforce this rule
(no `pydocstyle`/ruff `D`-rule `select` is configured in `pyproject.toml`), so compliance here is a manual review
against the rule's text, not something a linter will catch — re-read `docs/rules/public-api-requires-docstrings.md`
against the diff before calling this done, per that rule's own scope.

## Deviations

none yet
