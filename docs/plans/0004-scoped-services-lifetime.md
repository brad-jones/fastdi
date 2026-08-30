---
status: done
date: 2026-08-30
completed: 2026-08-30
specs: [scoped-services]
rules: [public-api-requires-docstrings]
---

# Scoped services lifetime

## Context

Satisfies [specs/scoped-services/README.md](../../specs/scoped-services/README.md). Adds
`ServiceCollection.add_scoped`, `ServiceProvider.create_scope`, and a new `ServiceScope` type, on top of the
transient/singleton container `constructor-injection` and `singleton-scope` already built. This is the "scoped
lifetime" `singleton-scope`'s README explicitly flagged as a future spec. No other plan is in flight; this
supersedes nothing.

### Spec cross-check

README, `main.py` and `tests/test_scoped_services.py` agree — no contradictory drift, nothing to send back to
`create-spec`. Gaps worth recording (design for the README, which is authoritative, and cover in `./tests/`):

- The spec suite only exercises the happy path: one bare-class scoped registration (`RequestId`) and one
  factory-backed one (`UnitOfWork`). It asserts nothing about any `RegistrationError` condition, about
  snapshot/re-registration semantics, or about eager build-time validation not constructing scoped instances.
- `main.py` never registers the same `service_type` twice across lifetimes, never nests a transient inside a scoped
  service (only the reverse — scoped inside transient), never exercises a singleton capturing a scope's
  `ServiceProvider`, and never builds a nested scope from a scope's own `service_provider` inside the printed demo
  (a nested-scope test is present in the spec suite, exercising `main.py`'s existing fixtures, but the printed
  example itself doesn't nest). All of this is unit-level and covered below.

## Current state

`./src/fastdi` currently implements `constructor-injection` and `singleton-scope`, in five modules:

- `_registrations.py` — `Lifetime` enum with `TRANSIENT` and `SINGLETON`; `TypeRegistration(implementation_type,
  lifetime)` and `FactoryRegistration(factory, lifetime)` both carry a mandatory `lifetime`; `InstanceRegistration`
  carries none. `Registration = TypeRegistration | FactoryRegistration | InstanceRegistration`.
- `_validation.py` — `build_plan()` walks a `Mapping[type, Registration]` into a `dict[type, ResolutionPlan]`
  (`TypePlan | FactoryPlan | InstancePlan`), threading `lifetime` through unchanged and detecting cycles /
  missing dependencies eagerly. The walk is already lifetime-agnostic: it never branches on `Lifetime`'s value,
  only on which `Registration`/`ResolutionPlan` variant it's handling. It treats factories as opaque leaves and
  instances as trivially-satisfied leaves.
- `_provider.py` — `ServiceProvider.__init__(self, plan, /)` stores the plan and a single `self._singletons: dict`.
  `_resolve` checks `InstancePlan` first, then `Lifetime.SINGLETON` against `self._singletons`, then builds
  (`factory(self)` or `self._build(resolution)`) and caches into `self._singletons` when singleton. `_build`
  recursively resolves each `Dependency` via `self.get_required_service(...)` and instantiates positionally/by
  keyword.
- `_collection.py` — `add_transient` (three overloads, always `Lifetime.TRANSIENT`) and `add_singleton` (five
  overloads, discriminating type-vs-instance shapes at runtime via `isinstance(_, type)`, always
  `Lifetime.SINGLETON` or an `InstanceRegistration`) both validate and store into `self._registrations: dict[type,
  Registration]`; `build_service_provider` snapshots the dict and calls `build_plan`.
- `_inspection.py` / `_errors.py` — unaffected by this plan; reused as-is.

`./tests/` covers `constructor-injection` and `singleton-scope` exhaustively (registration shapes, build-time
validation, constructor inference, resolution, singleton caching). Nothing there references a scope or a third
lifetime yet.

## Rules applied

- **`public-api-requires-docstrings`**: `add_scoped`'s real implementation, `create_scope`, the new `ServiceScope`
  class, and its `service_provider` property all need docstrings — `ServiceScope` is a brand-new exported type, so
  none of it inherits a docstring from anywhere. `add_scoped`'s docstring must cover all three shapes and every
  `RegistrationError` condition, matching `add_transient`'s existing depth (it has no instance shapes to add, unlike
  `add_singleton`). `ServiceProvider.__init__` already has a docstring (its `plan` parameter isn't a public
  attribute, so it doesn't get the class-docstring carve-out); it gains an internal-only `singletons` keyword
  parameter in this plan (see below) and that docstring must mention it, even though `singletons` is not part of the
  public constructor signature callers are expected to use — the existing docstring already establishes that
  `ServiceProvider.__init__` isn't a supported public entry point at all.

## `./src/fastdi` changes

Ordered so implementation can proceed top-to-bottom: data model (no change needed beyond one enum member), then the
provider that gains scope-awareness, then the collection API that produces scoped registrations, then the public
re-export.

### 1. `src/fastdi/_registrations.py`

Add exactly one enum member; nothing else in this module changes:

```python
class Lifetime(Enum):
  TRANSIENT = auto()
  SINGLETON = auto()
  SCOPED = auto()
```

`TypeRegistration` and `FactoryRegistration` already carry a mandatory `lifetime: Lifetime` field, so scoped
registrations need no new dataclass. There is deliberately no `InstanceRegistration`-equivalent for scoped — the
spec's `add_scoped` has no instance shape (see [Registration](../../specs/scoped-services/README.md#registration)),
so nothing here needs to represent one.

### 2. `src/fastdi/_validation.py`

**No change.** `build_plan`'s walk already threads `lifetime=registration.lifetime` through to `TypePlan`/
`FactoryPlan` without ever branching on its value, and cycle/missing-dependency detection is already lifetime-blind
— it walks `registrations` by type, never by how long an instance should live. Adding `Lifetime.SCOPED` as a value
that can now flow through this function requires editing nothing here; this is exactly the design `singleton-scope`
already established and is what makes "a cycle running through any mix of the three lifetimes is still caught" true
for free, per the spec's [Building and validation](../../specs/scoped-services/README.md#building-and-validation)
section.

### 3. `src/fastdi/_provider.py`

This is where scope-awareness actually lives. Two changes: give `ServiceProvider` a second, private cache alongside
the existing singleton one, and add `create_scope` plus the new `ServiceScope` type.

**`ServiceProvider.__init__`** gains an internal-only keyword parameter so a scope can share its parent's singleton
cache by reference, while starting with its own empty scoped cache:

```python
def __init__(self, plan: Mapping[type, ResolutionPlan], /, *, singletons: dict[type, Any] | None = None) -> None:
  """Wrap an already-validated resolution plan.

  Not a supported construction path for callers: build a `ServiceProvider` via
  `ServiceCollection.build_service_provider` instead. `singletons`, when given, is an existing singleton cache to
  share — used internally by `create_scope` so a scope's singletons stay identical to its parent's.
  """
  self._plan = plan
  self._singletons: dict[type, Any] = singletons if singletons is not None else {}
  self._scoped: dict[type, Any] = {}
```

Every `ServiceProvider` — the root one `build_service_provider()` returns, and every scope's `.service_provider` —
gets its own private `self._scoped`, which is exactly what makes the root "act as its own scope" per the spec's
[Scopes and resolution](../../specs/scoped-services/README.md#scopes-and-resolution) bullet on the point: there is
no special-casing for "no scope was ever created" anywhere else in this design: the root simply _is_ a
`ServiceProvider` with a scoped cache like any other, and the fact that nothing ever hands it a `singletons=`
argument is irrelevant to how `self._scoped` behaves.

**`_resolve`** picks the right cache generically instead of hard-coding `Lifetime.SINGLETON`:

```python
def _resolve(self, service_type: type, resolution: ResolutionPlan) -> Any:
  if isinstance(resolution, InstancePlan):
    return resolution.instance

  cache = {Lifetime.SINGLETON: self._singletons, Lifetime.SCOPED: self._scoped}.get(resolution.lifetime)
  if cache is not None and service_type in cache:
    return cache[service_type]

  instance = resolution.factory(self) if isinstance(resolution, FactoryPlan) else self._build(resolution)

  if cache is not None:
    cache[service_type] = instance

  return instance
```

(A literal dict-of-two-lifetimes built on every call is one legitimate way to write this; an `if
resolution.lifetime is Lifetime.SINGLETON: cache = self._singletons elif resolution.lifetime is Lifetime.SCOPED:
cache = self._scoped else: cache = None` chain is equally acceptable and avoids the per-call dict allocation —
either is fine, since the spec places no requirement on the internal shape, only on the caching _behavior_
described in [Scopes and resolution](../../specs/scoped-services/README.md#scopes-and-resolution).) The key
behavioral point either way: `Lifetime.TRANSIENT` resolves to `cache is None`, so transient resolution is
byte-for-byte unchanged from before this plan — no caching, always rebuilds.

`_build` needs **no change**. It already resolves each dependency via `self.get_required_service(dependency.service_type)`,
so a scoped dependency nested inside anything else is looked up against `self` — whichever `ServiceProvider`
(root or scope) is doing the resolving — which is exactly what makes a transient nested inside a scoped service
rebuild once per scope, and what makes a singleton that takes a `ServiceProvider` constructor parameter capture
whichever scope's provider happened to build it first (documented as intentional in the spec's
[Design notes](../../specs/scoped-services/README.md#design-notes)). No recursion-level changes needed for either
direction of composition.

**`create_scope`** and **`ServiceScope`**, appended to the module:

```python
def create_scope(self) -> ServiceScope:
  """Create a new `ServiceScope` sharing this provider's singletons but with its own scoped-service cache.

  Returns:
    A `ServiceScope` whose `service_provider` resolves scoped services independently of this provider (and of
    any other scope), while singleton-registered services remain shared with it.
  """
  return ServiceScope(ServiceProvider(self._plan, singletons=self._singletons))


class ServiceScope:
  """A boundary within which every scoped service resolves to one shared instance."""

  def __init__(self, service_provider: ServiceProvider, /) -> None:
    """Wrap a `ServiceProvider` as a scope.

    Not a supported construction path for callers: build a `ServiceScope` via `ServiceProvider.create_scope`
    instead.
    """
    self._service_provider = service_provider

  @property
  def service_provider(self) -> ServiceProvider:
    """The `ServiceProvider` scoped to this `ServiceScope`."""
    return self._service_provider
```

Passing `self._plan` straight through (the same validated plan every scope and the root share) is what lets a
`ServiceScope` support `get_service`/`get_required_service`/`create_scope` identically to any other
`ServiceProvider` — it's a real, fully-functional provider, just with a fresh `_scoped` dict and the parent's
`_singletons` dict passed by reference (not copied), so a mutation either side makes to `_singletons` — i.e. a
newly-cached singleton — is visible through the other immediately. Nesting (`scope.service_provider.create_scope()`)
falls out for free: it's the same method, called on a `ServiceProvider` that happens to have come from a scope
rather than from `build_service_provider()`.

Note `create_scope`'s return type is written unquoted (`ServiceScope`, not `"ServiceScope"`) even though
`ServiceScope` is defined later in the file — PEP 649 lazy annotation evaluation resolves this at access time, not
definition time, and ruff's `UP037` already enforces unquoted forward references elsewhere in this codebase (see
plan [0001](0001-constructor-injection-transient-container.md)'s Deviations).

Import `Any` is already imported in this module; no new imports are needed beyond what's already present.

### 4. `src/fastdi/_collection.py`

Add `add_scoped`, mirroring `add_transient`'s three-shape structure exactly (arity plus keyword-only `factory`, no
instance shape), with `Lifetime.SCOPED` in place of `Lifetime.TRANSIENT`:

```python
@overload
def add_scoped[T](self, service_type: type[T], /) -> Self: ...


@overload
def add_scoped[T](self, service_type: type[T], implementation_type: type[T], /) -> Self: ...


@overload
def add_scoped[T](self, service_type: type[T], /, *, factory: Factory[T]) -> Self: ...


def add_scoped[T](
  self,
  service_type: type[T],
  implementation_type: type[T] | None = None,
  /,
  *,
  factory: Factory[T] | None = None,
) -> Self:
  """Register a scoped service, in one of three shapes.

  Called as `add_scoped(Impl)` to register a concrete class under itself, as `add_scoped(ServiceType, Impl)` to
  register an implementation under a different key, or as `add_scoped(ServiceType, factory=...)` to supply a
  callable that builds the instance from a `ServiceProvider`. Within one `ServiceScope` (or the un-scoped root,
  which acts as its own scope), the first resolution builds the instance and every later resolution through that
  same scope returns it again; a different scope gets its own, independently-built instance.

  Args:
    service_type: The type resolutions are looked up under.
    implementation_type: The concrete class to construct, when different from `service_type`.
    factory: A callable that receives the `ServiceProvider` and returns the instance.

  Returns:
    `self`, so calls can be chained.

  Raises:
    RegistrationError: If both `implementation_type` and `factory` are supplied, if `service_type` or
      `implementation_type` is not a class, if the class that would be instantiated is abstract, if `factory` is
      not callable or is an `async def` function, or if `service_type` is `ServiceProvider`.
  """
  if implementation_type is not None and factory is not None:
    raise RegistrationError("Cannot supply both `implementation_type` and `factory`.")

  if not isinstance(service_type, type):
    raise RegistrationError(f"`service_type` must be a class, got {service_type!r}.")

  if service_type is ServiceProvider:
    raise RegistrationError("`ServiceProvider` is implicitly registered and cannot be overridden.")

  if factory is not None:
    if not callable(factory):
      raise RegistrationError(f"`factory` must be callable, got {factory!r}.")
    if inspect.iscoroutinefunction(factory):
      raise RegistrationError("`factory` must not be an `async def` function.")
    self._registrations[service_type] = FactoryRegistration(factory=factory, lifetime=Lifetime.SCOPED)
    return self

  if implementation_type is not None:
    if not isinstance(implementation_type, type):
      raise RegistrationError(f"`implementation_type` must be a class, got {implementation_type!r}.")
    if is_abstract(implementation_type):
      raise RegistrationError(f"`implementation_type` {implementation_type.__name__!r} is abstract.")
    self._registrations[service_type] = TypeRegistration(implementation_type=implementation_type, lifetime=Lifetime.SCOPED)
    return self

  if is_abstract(service_type):
    raise RegistrationError(f"`service_type` {service_type.__name__!r} is abstract.")
  self._registrations[service_type] = TypeRegistration(implementation_type=service_type, lifetime=Lifetime.SCOPED)
  return self
```

This duplicates `add_transient`'s validation logic almost verbatim, deliberately: it's the same pattern
`add_singleton` already follows relative to `add_transient` in this codebase (no shared private helper was
extracted then either). Introducing a shared validation helper now, across three call sites, is a larger and
unrelated refactor this plan doesn't take on — flag it to the user if it comes up, don't do it silently.

No changes to `add_transient` or `add_singleton` themselves. No new imports beyond what `_collection.py` already
has (`Lifetime`, `TypeRegistration`, `FactoryRegistration`, `RegistrationError`, `is_abstract`, `ServiceProvider`,
`Factory` are all already imported).

### 5. `src/fastdi/__init__.py` (edit)

Add `ServiceScope` to the imports from `._provider` and to `__all__`, alongside the existing `Factory`,
`ServiceProvider`. Final `__all__` (nine names): `CircularDependencyError`, `Factory`, `FastDIError`,
`MissingDependencyError`, `RegistrationError`, `ServiceCollection`, `ServiceNotRegisteredError`, `ServiceProvider`,
`ServiceScope`.

## `./tests/` additions

### `tests/test_scoped_registration.py` (new)

Mirrors `tests/test_registration.py`'s structure (three shapes, no instance shape) for `add_scoped`:

- Each of the three shapes registers and resolves: self-registration, `(ServiceType, Impl)`, `(ServiceType,
  factory=)`.
- `add_scoped` returns the same collection (`is`), and chains with both `add_transient` and `add_singleton`.
- `RegistrationError` when `implementation_type` **and** `factory` are both supplied.
- `RegistrationError` for a non-class `service_type` and for a non-class `implementation_type`, parametrized like
  `test_registration.py`'s equivalents (a string, `list[int]`, an int, a function, an instance).
- `RegistrationError` for an abstract instantiation target: an ABC with an abstract method and a `Protocol`, each in
  the one-argument form; the same two as `implementation_type` in the two-argument form; a `runtime_checkable`
  Protocol.
- **No** error for an abstract `service_type` paired with a concrete `implementation_type`, and none paired with a
  `factory` — the normal Protocol/ABC case.
- `RegistrationError` for a non-callable `factory` and for an `async def` factory; a plain `def` factory that
  _returns_ a coroutine object is accepted (parity with the other two `add_*` methods).
- `RegistrationError` for `add_scoped(ServiceProvider)`, `add_scoped(ServiceProvider, SomeImpl)`, and
  `add_scoped(ServiceProvider, factory=...)`.
- Last registration wins across lifetime transitions: transient→scoped, scoped→transient, singleton→scoped,
  scoped→singleton, and scoped-type→scoped-factory. Assert the _resolved_ result changes on a freshly-built
  provider, not just that the collection's internal state changed.
- No conformance checking: `add_scoped(AbstractStore, Unrelated)` where `Unrelated` neither subclasses the ABC nor
  satisfies the Protocol registers, builds, and resolves to an `Unrelated`.

### `tests/test_scoped_lifetime.py` (new)

Resolution, caching and scope semantics specific to the scoped lifetime, per the spec's
[Scopes and resolution](../../specs/scoped-services/README.md#scopes-and-resolution) section:

- A bare-class scoped service resolves the same instance for two `get_required_service` calls made through the
  _same_ `ServiceScope.service_provider`.
- A type-keyed scoped service (`add_scoped(Base, Impl)`) behaves the same way, and still resolves to the
  implementation.
- `get_service` and `get_required_service` return the same cached scoped instance as each other, within one scope.
- Two independently created scopes (`provider.create_scope()` called twice) never share a scoped instance for the
  same registration.
- The **un-scoped root** provider (returned directly by `build_service_provider()`, `create_scope()` never called)
  resolves a scoped service and caches it exactly like a scope would: two `get_required_service` calls on the same
  root return the identical instance.
- A factory-backed scoped service's factory runs exactly once per scope (call-counter instrumented), including when
  resolved as a nested dependency multiple times within that scope; creating a second scope and resolving there
  runs the factory again (counter reaches 2, not 1).
- `create_scope()` itself constructs nothing: instantiate a scoped service's counter, call `create_scope()` several
  times, assert the counter is still `0` until something actually resolves through one of the scopes.
- A scope created from another scope's `service_provider` (nesting) is independent of its parent: the nested
  scope's scoped instance differs from the parent scope's, for the same registration.
- Singleton-registered services are shared identically by the root and by every scope, nested or not:
  `provider.get_required_service(S) is scope_one.service_provider.get_required_service(S) is
  scope_two.service_provider.get_required_service(S) is nested_scope.service_provider.get_required_service(S)`.
- Transient resolution is unaffected by scopes: two resolutions of a transient through the same scope's provider
  are still distinct objects.
- A transient dependency nested inside a scoped service is rebuilt once per scope: instrument the transient's
  `__init__` with a counter, resolve the owning scoped service twice within one scope (counter stays `1`), then
  resolve it again through a second scope (counter reaches `2`).
- A scoped dependency nested inside a transient consumer is shared across repeated resolutions of that transient,
  within one scope: `first.dep is second.dep` where `first`/`second` come from two separate
  `get_required_service(Consumer)` calls through the same scope.
- Building the provider constructs nothing, for scoped registrations specifically — parity with the existing
  singleton test's shape (`test_validation_is_eager_and_nothing_is_constructed_for_singletons`).
- A cycle spanning the scoped lifetime is still caught at build time: transient `A` depending on scoped `B`
  depending on transient `A` raises `CircularDependencyError` with the full chain — parity with
  `test_a_cycle_spanning_mixed_lifetimes_is_still_caught`, now with `add_scoped` in the mix.
- A `ServiceProvider`-annotated constructor parameter, on a **singleton** built for the first time while resolving
  through a scope, captures that scope's `service_provider` — not the root's — and keeps it: resolve the singleton
  again later through the root or a different scope and confirm it's still the same captured provider. This is the
  captive-dependency corollary the spec's Design notes call out explicitly.
- An exception raised while constructing a scoped instance (constructor or factory), on the resolution that first
  triggers it, propagates unchanged out of both `get_service` and `get_required_service` — parity with the existing
  singleton-exception tests, now for the scoped path.
- `ServiceScope.service_provider` returns the identical object on repeated access (`scope.service_provider is
  scope.service_provider`), and `isinstance(scope.service_provider, ServiceProvider)` holds.

### `tests/test_public_api.py` (edit)

Add `"ServiceScope"` to the expected `__all__` set (nine names total, up from eight).

## Verification

Standard verification only, plus: run the spec's example by hand once — `pixi run -- uv run
specs/scoped-services/src/scoped_services/main.py` — and confirm every "same ... within a scope" / "different ...
across scopes" line prints `True`, the unit-of-work operations list shows both orders from the first scope only, and
the final "un-scoped root acts as its own scope" line prints `True`.

## Deviations

- `_provider.py`'s `_resolve` was written with the explicit `if`/`elif`/`else` cache-selection chain the plan
  offered as the alternative to a per-call `{Lifetime.SINGLETON: ..., Lifetime.SCOPED: ...}.get(...)` dict, since it
  avoids allocating a dict literal on every resolution. Both were pre-approved as equivalent in the plan; this is a
  choice between them, not a divergence.
- While writing `tests/test_scoped_registration.py`'s `test_last_registration_wins_singleton_to_scoped`, the first
  draft used `factory=lambda _: "not a concrete instance"` (copied from the analogous singleton-registration test)
  and asserted `first is not second` across the root and a new scope. That failed — not because of a caching bug,
  but because CPython interns identical string literals, so two independently-produced `"not a concrete instance"`
  values are the same object regardless of scoping. Rewrote the test to have the factory return a fresh `Marker()`
  instance each call, which is what makes an identity assertion meaningful there. No production code was affected;
  this was purely a test-authoring correction caught by actually running the suite.
