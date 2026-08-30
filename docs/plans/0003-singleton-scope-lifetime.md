---
status: done
date: 2026-08-30
completed: 2026-08-30
specs: [singleton-scope]
rules: [public-api-requires-docstrings]
---

# Singleton lifetime

## Context

Satisfies [specs/singleton-scope/README.md](../../specs/singleton-scope/README.md). Adds `ServiceCollection.add_singleton`
and the caching behavior it requires from `ServiceProvider`, on top of the transient-only container
`constructor-injection` already built. No other plan is in flight; this supersedes nothing.

### Spec cross-check

README, `main.py` and `tests/test_singleton_scope.py` agree — no contradictory drift, nothing to send back to
`create-spec`. Gaps worth recording (design for the README, which is authoritative, and cover in `./tests/`):

- The spec suite only exercises the happy path for all five registration shapes. It asserts nothing about any
  `RegistrationError` condition, about snapshot/re-registration semantics, about eager build-time validation not
  constructing singletons, or about cycle detection spanning mixed lifetimes.
- `main.py` never registers the same `service_type` twice, never mixes `add_transient` and `add_singleton` on the
  same key, and never exercises the `add_singleton(None)` edge case the README's Design notes calls out explicitly.
  All three need unit coverage.

## Current state

`./src/fastdi` currently implements `constructor-injection` only, in five modules:

- `_registrations.py` — `TypeRegistration(implementation_type)` and `FactoryRegistration(factory)`, unioned as
  `Registration`. Neither carries a lifetime; every registration is implicitly transient.
- `_validation.py` — `build_plan()` walks a `Mapping[type, Registration]` into a `dict[type, ResolutionPlan]`
  (`TypePlan | FactoryPlan`), detecting cycles and missing dependencies eagerly. Factory registrations are treated
  as opaque leaves and never pushed onto the cycle-detection stack.
- `_provider.py` — `ServiceProvider` wraps the plan and nothing else (no mutable state). `get_service` /
  `get_required_service` look up the plan and call `_resolve`, which dispatches `FactoryPlan` to
  `factory(self)` and `TypePlan` to `_build`, which recursively resolves each constructor dependency via
  `get_required_service` and instantiates. Every resolution reconstructs from scratch.
- `_collection.py` — `ServiceCollection.add_transient` (three overloads) validates and stores a registration;
  `build_service_provider` snapshots the dict and calls `build_plan`.
- `_inspection.py` / `_errors.py` — unaffected by this plan; reused as-is.

`./tests/` covers `constructor-injection` exhaustively (registration, build-time validation, constructor inference,
resolution). Nothing there references a lifetime concept yet.

## Rules applied

- **`public-api-requires-docstrings`**: `add_singleton`'s real implementation (not the `@overload` stubs, per the
  same carve-out plan
  [0002](0002-public-api-docstrings.md) already established) needs a docstring covering all five shapes and every
  `RegistrationError` condition, matching `add_transient`'s existing docstring in depth. It also means
  `ServiceProvider.get_service` and `get_required_service`'s existing docstrings must be corrected, not just left
  alone: both currently say "a new instance of `service_type`", which stops being true the moment a
  singleton-registered `service_type` exists — the wording needs to say the returned instance may be a cached one
  shared across calls, depending on how `service_type` was registered.

## `./src/fastdi` changes

Ordered so implementation can proceed top-to-bottom: data model, then the build-time walk that consumes it, then the
provider that caches against it, then the collection API that produces it.

### 1. `src/fastdi/_registrations.py`

Add a `Lifetime` enum and an `InstanceRegistration` record; give `TypeRegistration` and `FactoryRegistration` a
mandatory `lifetime` field so every construction site has to state it explicitly (no default to silently fall back
on):

```python
from enum import Enum, auto


class Lifetime(Enum):
  TRANSIENT = auto()
  SINGLETON = auto()


@dataclass(frozen=True, slots=True)
class TypeRegistration:
  implementation_type: type
  lifetime: Lifetime


@dataclass(frozen=True, slots=True)
class FactoryRegistration:
  factory: Factory[Any]
  lifetime: Lifetime


@dataclass(frozen=True, slots=True)
class InstanceRegistration:
  instance: Any


type Registration = TypeRegistration | FactoryRegistration | InstanceRegistration
```

`InstanceRegistration` carries no `lifetime`: per the spec, an instance registration is always immediate and always
shared — there's no transient equivalent, so the field would be meaningless.

### 2. `src/fastdi/_validation.py`

- Add `InstancePlan(instance: Any)`, and give `TypePlan` / `FactoryPlan` the same `lifetime: Lifetime` field as
  their registration counterparts. `type ResolutionPlan = TypePlan | FactoryPlan | InstancePlan`.
- In `build_plan`'s `walk`, handle `InstanceRegistration` as a leaf, before the existing `FactoryRegistration`
  check and before anything touches `stack`: `plan[service_type] = InstancePlan(instance=registration.instance)`,
  then `return`. This is what makes shape 2/4 instance registrations "trivially satisfied" per the spec's
  [Building and validation](../../specs/singleton-scope/README.md#building-and-validation) section — no constructor
  to walk, so they can never raise `MissingDependencyError` and can never sit on a cycle.
- Thread `lifetime=registration.lifetime` through when constructing `FactoryPlan` and `TypePlan` — the only other
  change in this function. The cycle-detection and missing-dependency logic itself is lifetime-agnostic already
  (it walks `registrations` by type, never by how long an instance should live), which is what gives the spec's "a
  cycle running through a mix of singleton and transient registrations is still caught" guarantee for free.

### 3. `src/fastdi/_provider.py`

Add a private, mutable singleton cache to the otherwise-immutable provider, and change `_resolve` to consult it:

```python
def __init__(self, plan: Mapping[type, ResolutionPlan], /) -> None:
  """..."""  # unchanged docstring
  self._plan = plan
  self._singletons: dict[type, Any] = {}
```

`get_service` and `get_required_service` both currently call `self._resolve(resolution)`; change both call sites to
`self._resolve(service_type, resolution)`, since the cache is keyed by `service_type`, not by anything recoverable
from the plan entry alone. Replace `_resolve` with:

```python
def _resolve(self, service_type: type, resolution: ResolutionPlan) -> Any:
  if isinstance(resolution, InstancePlan):
    return resolution.instance

  if resolution.lifetime is Lifetime.SINGLETON and service_type in self._singletons:
    return self._singletons[service_type]

  instance = resolution.factory(self) if isinstance(resolution, FactoryPlan) else self._build(resolution)

  if resolution.lifetime is Lifetime.SINGLETON:
    self._singletons[service_type] = instance

  return instance
```

`_build` is untouched: it already resolves each dependency through `get_required_service`, so a nested singleton
dependency naturally hits this same cache check, and a transient nested inside a singleton is simply built once,
because the singleton `_build` call that contains it only ever runs once. No recursion-level changes needed for
either direction of composition described in the spec's
[Resolution and caching](../../specs/singleton-scope/README.md#resolution-and-caching) section.

Update the docstrings on `get_service` and `get_required_service` per **Rules applied** above — both currently
promise "a new instance"; both need to say the instance may instead be a cached one shared across calls, per how
`service_type` was registered.

Import `InstancePlan` alongside the existing `FactoryPlan`, `ResolutionPlan`, `TypePlan` from `._validation`, and
`Lifetime` from `._registrations`.

### 4. `src/fastdi/_collection.py`

Update `add_transient`'s three existing registration-construction lines to pass `lifetime=Lifetime.TRANSIENT`
explicitly (no other change — its public behavior is unchanged, per the spec's opening paragraph). Import
`InstanceRegistration` and `Lifetime` from `._registrations` alongside the existing imports.

Add `add_singleton`, with the five overloads and the runtime dispatch specified in
[specs/singleton-scope/README.md](../../specs/singleton-scope/README.md#public-api):

```python
@overload
def add_singleton[T](self, service_type: type[T], /) -> Self: ...


@overload
def add_singleton[T](self, instance: T, /) -> Self: ...


@overload
def add_singleton[T](self, service_type: type[T], implementation_type: type[T], /) -> Self: ...


@overload
def add_singleton[T](self, service_type: type[T], instance: T, /) -> Self: ...


@overload
def add_singleton[T](self, service_type: type[T], /, *, factory: Factory[T]) -> Self: ...


def add_singleton[T](
  self,
  service_type_or_instance: type[T] | T,
  implementation_type_or_instance: type[T] | T | None = None,
  /,
  *,
  factory: Factory[T] | None = None,
) -> Self:
  if implementation_type_or_instance is not None and factory is not None:
    raise RegistrationError("Cannot supply both a second argument and `factory`.")

  if not isinstance(service_type_or_instance, type):
    if implementation_type_or_instance is not None or factory is not None:
      raise RegistrationError("A non-class first argument must be the only argument.")
    instance = service_type_or_instance
    service_type = type(instance)
    if service_type is ServiceProvider:
      raise RegistrationError("`ServiceProvider` is implicitly registered and cannot be overridden.")
    self._registrations[service_type] = InstanceRegistration(instance=instance)
    return self

  service_type = service_type_or_instance
  if service_type is ServiceProvider:
    raise RegistrationError("`ServiceProvider` is implicitly registered and cannot be overridden.")

  if factory is not None:
    if not callable(factory):
      raise RegistrationError(f"`factory` must be callable, got {factory!r}.")
    if inspect.iscoroutinefunction(factory):
      raise RegistrationError("`factory` must not be an `async def` function.")
    self._registrations[service_type] = FactoryRegistration(factory=factory, lifetime=Lifetime.SINGLETON)
    return self

  if implementation_type_or_instance is not None:
    if isinstance(implementation_type_or_instance, type):
      implementation_type = implementation_type_or_instance
      if is_abstract(implementation_type):
        raise RegistrationError(f"`implementation_type` {implementation_type.__name__!r} is abstract.")
      self._registrations[service_type] = TypeRegistration(implementation_type=implementation_type, lifetime=Lifetime.SINGLETON)
      return self

    self._registrations[service_type] = InstanceRegistration(instance=implementation_type_or_instance)
    return self

  if is_abstract(service_type):
    raise RegistrationError(f"`service_type` {service_type.__name__!r} is abstract.")
  self._registrations[service_type] = TypeRegistration(implementation_type=service_type, lifetime=Lifetime.SINGLETON)
  return self
```

Two things worth calling out so `execute-plan` doesn't "simplify" them away:

- Every branch tests `is not None`, never truthiness. An instance registration commonly carries a falsy value
  (`0`, `""`, `False`, an empty collection) — unlike `add_transient`, which never handled arbitrary instance data —
  so a truthiness check here would silently misroute a falsy `instance` into the wrong branch.
- `add_singleton(None)` is deliberately _not_ special-cased to raise. It flows through the non-class branch,
  derives `service_type = type(None)` (`NoneType`), and registers successfully — matching the spec's Design notes,
  which call this out as an accepted, if unusual, consequence of the mechanism rather than a case requiring a
  guard.

The docstring (per **Rules applied**) needs to describe all five shapes, the `isinstance(_, type)` discriminator,
and every `RegistrationError` condition: both-second-argument-and-factory; non-class first argument paired with a
second argument or `factory`; an abstract instantiation target (shapes 1 and 3 only — never 2 or 4, since nothing is
ever instantiated there); a non-callable or `async def` factory; and the resolved `service_type` — the first
argument in shapes 1/3/4/5, or `type(instance)` in shape 2 — being `ServiceProvider`.

## `./tests/` additions

### `tests/test_singleton_registration.py` (new)

Mirrors the structure of `test_registration.py`, for `add_singleton`:

- Each of the five shapes registers and resolves: self-registration; bare instance (assert it resolves under
  `type(instance)`); `(ServiceType, Impl)`; `(ServiceType, instance)`; `(ServiceType, factory=...)`.
- `add_singleton` returns the same collection (`is`), chainable with itself and with `add_transient`.
- `RegistrationError` when a second positional argument and `factory` are both supplied.
- `RegistrationError` when the first argument is not a class and a second positional argument is also supplied;
  same when paired with `factory` instead.
- `RegistrationError` for an abstract instantiation target in shape 1 (ABC, `Protocol`) and shape 3
  (`implementation_type` abstract) — parametrized like `test_registration.py`'s equivalents. No error for the
  parallel shape 2/4 cases: registering an already-built instance under an abstract key
  (`add_singleton(AbstractStore, ConcreteStore())`) must succeed, since nothing is instantiated.
- `RegistrationError` for a non-callable `factory` and for an `async def` factory; a plain `def` factory returning
  a coroutine is accepted (parity with `add_transient`'s equivalent tests).
- `RegistrationError` for `add_singleton(ServiceProvider)`, `add_singleton(ServiceProvider, Concrete)`,
  `add_singleton(ServiceProvider, factory=...)`, and for `add_singleton(some_service_provider_instance)` (shape 2
  where the derived key is `ServiceProvider`).
- `add_singleton(None)` registers successfully under `type(None)`, and `get_required_service(type(None))` returns
  `None` — the Design-notes edge case, pinned down rather than left implicit.
- Last registration wins across every method/shape combination that matters: transient→singleton, singleton→
  transient, singleton-type→singleton-instance, singleton-instance→singleton-factory. Assert the _resolved_ result
  changes.
- Falsy instances round-trip correctly: `add_singleton(0)`, `add_singleton("")`, `add_singleton(False)` each
  resolve back to that exact falsy value (guards against an `is not None` regression to truthiness).
- No conformance checking, parity with `add_transient`'s equivalent: `add_singleton(AbstractStore, unrelated_instance)`
  resolves to `unrelated_instance` even though it satisfies neither the ABC nor an equivalent Protocol.
- Caching is keyed by `service_type`, not by implementation class: `add_singleton(A, Impl)` and
  `add_singleton(B, Impl)` produce two independent instances (`is not`) once both are resolved.

### `tests/test_singleton_lifetime.py` (new)

Resolution and validation semantics specific to the singleton lifetime, per the spec's
[Resolution and caching](../../specs/singleton-scope/README.md#resolution-and-caching) and
[Building and validation](../../specs/singleton-scope/README.md#building-and-validation) sections:

- Bare-class, type-keyed, and factory-backed singletons each resolve to the identical object across repeated
  `get_required_service` calls, and across a `get_service` / `get_required_service` pair.
- A factory-backed singleton's factory runs exactly once (instrument with a call counter) no matter how many times
  the service is resolved, directly or as a nested dependency.
- An instance registration never constructs anything and always returns the exact object passed to `add_singleton`
  — including across two providers built from the _same_ collection (since it's the same underlying object), which
  is the one exception to the next point.
- Two providers built from the same collection have independent singleton caches for every other shape: resolving
  a bare-class or factory-backed singleton on each returns two different objects, one per provider.
- A transient service depending on a singleton gets the same singleton instance across repeated resolutions of the
  transient itself (`first.dep is second.dep` where `first`/`second` are two separately-resolved transients).
- A singleton depending on a transient only builds that transient once: instrument the transient's `__init__` with
  a counter, resolve the owning singleton twice, and assert the counter is `1`.
- Building the provider constructs nothing, for singletons specifically: a bare-class singleton and a
  factory-backed singleton each get an instantiation/call counter; `build_service_provider()` runs it to zero,
  matching the existing transient test's shape (`test_validation_is_eager_and_nothing_is_constructed`).
- A cycle spanning mixed lifetimes is still caught at build time: transient `A` depending on singleton `B`
  depending on transient `A` raises `CircularDependencyError` with the full chain, exactly as an all-transient
  cycle does today.
- An exception raised by a singleton's constructor or factory, on the resolution that first triggers construction,
  propagates unchanged out of both `get_service` and `get_required_service` — parity with the existing
  factory-exception tests in `test_resolution.py`, now for the singleton path.

## Verification

Standard verification only, plus: run the spec's example by hand once —
`pixi run -- uv run specs/singleton-scope/src/singleton_scope/main.py` — and confirm every "the same X" line prints
`True` except none of them should ever print `False` for a singleton comparison; the two resolved-handlers-are-
different-objects line should print `True` (transient), and the counter should read `2` after both `handle()` calls.

## Deviations

- `pyright` emits `reportInvalidTypeVarUse` (warning, not error — `task lint` still exits `0`) on the
  `add_singleton[T](self, instance: T, /) -> Self` overload, since `T` appears only once and pyright suggests
  `object` instead. Left as `T`, matching the spec's literal documented signature verbatim
  ([specs/singleton-scope/README.md](../../specs/singleton-scope/README.md#public-api)) rather than deviating from
  it for a cosmetic type-checker nicety with no behavioral effect and no loss of caller-facing type safety (nothing
  else in that overload depends on binding `T`).
