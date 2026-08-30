# Spec: Constructor Injection (Transient Lifetime)

This is FastDI's foundational spec. It defines the two-phase container — a mutable `ServiceCollection` you register
into, and an immutable `ServiceProvider` you resolve from — and the constructor injection rules that let FastDI build a
service graph from nothing but runtime type hints.

Only the **transient** lifetime exists in this spec: every resolution of a service produces a brand new instance.
Singleton and scoped lifetimes are deliberately out of scope and get their own specs later.

## Public API

Everything below is exported from the top-level `fastdi` package.

```python
from collections.abc import Callable
from typing import Self, overload

type Factory[T] = Callable[[ServiceProvider], T]


class ServiceCollection:
  """A mutable registry of service registrations."""

  def __init__(self) -> None: ...

  @overload
  def add_transient[T](self, service_type: type[T], /) -> Self: ...

  @overload
  def add_transient[T](self, service_type: type[T], implementation_type: type[T], /) -> Self: ...

  @overload
  def add_transient[T](self, service_type: type[T], /, *, factory: Factory[T]) -> Self: ...

  def add_transient[T](
    self,
    service_type: type[T],
    implementation_type: type[T] | None = None,
    /,
    *,
    factory: Factory[T] | None = None,
  ) -> Self: ...

  def build_service_provider(self) -> ServiceProvider: ...


class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def get_service[T](self, service_type: type[T], /) -> T | None: ...

  def get_required_service[T](self, service_type: type[T], /) -> T: ...
```

### Exceptions

```python
class FastDIError(Exception):
  """Base class for every error FastDI raises."""


class RegistrationError(FastDIError):
  """A registration call was malformed. Raised by `add_transient`."""


class ServiceNotRegisteredError(FastDIError):
  """`get_required_service` was called with an unregistered service type."""

  service_type: type


class MissingDependencyError(FastDIError):
  """A constructor parameter cannot be satisfied. Raised by `build_service_provider`."""

  service_type: type  # the service whose constructor could not be satisfied
  implementation_type: type  # the class whose `__init__` was being inspected
  parameter_name: str
  parameter_type: type | None  # `None` when the parameter carries no annotation


class CircularDependencyError(FastDIError):
  """The registration graph contains a cycle. Raised by `build_service_provider`."""

  chain: tuple[type, ...]  # the cycle, with the repeated service type at both ends
```

All five are exported from `fastdi`.

## Behavior

### Registration

`add_transient` accepts exactly three shapes, and returns `self` so calls can be chained fluently:

1. **`add_transient(Impl)`** — registers the concrete class `Impl` under itself. Resolving `Impl` constructs `Impl`.
2. **`add_transient(ServiceType, Impl)`** — registers `Impl` under a different key. `ServiceType` may be a `Protocol`,
   an ABC, or any other class: it is only ever used as a dictionary key, never instantiated and never introspected,
   so it is free to be abstract. Resolving `ServiceType` constructs `Impl`.
3. **`add_transient(ServiceType, factory=...)`** — registers a callable that will be handed the `ServiceProvider` and
   must return the instance. Resolving `ServiceType` calls `factory(provider)` and returns whatever it returns.

`factory` is keyword-only precisely so the three shapes are distinguished by arity and keyword presence, never by
inspecting argument types (see [Design notes](#design-notes)).

`add_transient` raises `RegistrationError` when:

- Both an `implementation_type` and a `factory` are supplied.
- `service_type` is not a class (e.g. `add_transient("logger", ...)`, `add_transient(list[int])`).
- `implementation_type` is supplied but is not a class.
- The class that would be **instantiated** is abstract — i.e. it has a non-empty `__abstractmethods__`, or is a
  `Protocol` class. That means `implementation_type` in the two-argument form, or `service_type` in the one-argument
  form where it stands as its own implementation. Such classes cannot be instantiated, so failing at registration is
  strictly better than failing at build. An abstract `service_type` paired with a concrete `implementation_type` or a
  `factory` is explicitly fine — that is the normal `Protocol`/ABC case, and the whole point of shape 2.
- `factory` is supplied but is not callable, or is a coroutine function. Async resolution is out of scope for this
  spec; a `async def` factory is rejected eagerly rather than silently returning an un-awaited coroutine.

FastDI does **not** verify that `implementation_type` satisfies `service_type` in any way: neither structural
conformance to a `Protocol` nor nominal `issubclass` inheritance from an ABC is checked. Both are the type checker's
job; the container only ever uses `service_type` as a dictionary key, so `add_transient(AbstractStore, Unrelated)`
registers successfully and resolves to an `Unrelated`.

**Re-registering the same `service_type` is allowed and the last registration wins.** Enumerating every registration
for a type (MEDI's `GetServices`) is out of scope here.

### Building

`build_service_provider()` takes a **snapshot** of the collection and returns a `ServiceProvider` over it. Mutating the
`ServiceCollection` afterwards has no effect on any provider already built, and the collection may be built again to
produce a second, independent provider. The collection itself is never frozen.

Before returning, the provider **eagerly validates the whole graph**. Every registration backed by an implementation
type is walked: its constructor is inspected, each parameter is resolved to another registration, and the walk recurses.
Any `MissingDependencyError` or `CircularDependencyError` is raised here, at build time, not at resolve time. A provider
that was successfully built can never fail resolution for a graph-shaped reason.

Factory registrations are **opaque** to validation. FastDI cannot see what a factory does, so it is treated as a leaf:
neither its dependencies nor any cycle running through it can be detected. A factory that calls
`provider.get_required_service(...)` on an unregistered type will raise `ServiceNotRegisteredError` at resolve time.

When multiple problems exist, exactly one error is raised; which one is unspecified. Registrations are validated in
insertion order, which makes the choice deterministic in practice but is not something callers should depend on.

### Constructor inference

For an implementation type `Impl`, FastDI inspects `Impl.__init__` and resolves its parameters:

- `self` is skipped. So are `*args` and `**kwargs` (`VAR_POSITIONAL` / `VAR_KEYWORD`), which are simply never passed.
- `Impl.__init__` is looked up through the MRO, so an implementation that doesn't define its own `__init__` but
  inherits one from a base class — commonly an ABC holding dependencies shared by every subclass — gets that
  inherited signature injected. A class that inherits `object.__init__` therefore has zero dependencies and is
  constructed with no arguments.
- Annotations are read with `typing.get_type_hints(Impl.__init__, include_extras=True)` at build time. Because Python
  3.14 evaluates annotations lazily (PEP 649), a constructor may annotate a class defined later in the module and it
  still resolves; explicitly quoted annotations and `from __future__ import annotations` work for the same reason.
- `Annotated[X, ...]` resolves as `X`; the metadata is ignored by this spec.
- Each remaining parameter's annotation is looked up in the registrations:
  - **Registered** → recursively resolved and injected.
  - **Not registered, has a default** → the default is used and no injection happens.
  - **Not registered, no default** → `MissingDependencyError` at build time.
  - **No annotation at all, has a default** → the default is used.
  - **No annotation at all, no default** → `MissingDependencyError` with `parameter_type=None`.
- There is **no special handling of `X | None`**. A `Logger | None = None` parameter is only injected if the union
  itself was registered as a key (it won't be, since unions aren't classes) — otherwise the default `None` is used.
  Resolution is strict; nothing is inferred from optionality.

Resolved dependencies are passed by keyword, except positional-only parameters, which are passed positionally.

`ServiceProvider` is implicitly registered as itself in every provider: a constructor parameter annotated
`ServiceProvider` receives the provider doing the resolving, and `provider.get_required_service(ServiceProvider)`
returns that same provider. This implicit registration cannot be overridden; `add_transient(ServiceProvider, ...)`
raises `RegistrationError`.

### Resolution

- `get_required_service(T)` returns a new instance of `T`, or raises `ServiceNotRegisteredError` if `T` has no
  registration.
- `get_service(T)` is identical except it returns `None` instead of raising for an unregistered `T`. It does **not**
  swallow any other error: if a registered factory raises, that exception propagates out of `get_service` unchanged.

Because the only lifetime is transient, **every** resolution allocates:

- Two calls to `get_required_service(T)` return two distinct objects.
- A dependency appearing twice in one graph is built twice. Given `Report(header: Banner, footer: Banner)`, a single
  `get_required_service(Report)` constructs two distinct `Banner` instances.

FastDI never caches, never reuses, and never disposes instances in this spec.

## Worked examples

### A three-level graph behind a Protocol

An application registers a `Clock` protocol backed by `FixedClock`, a `Greeter` that depends on `Clock`, and a
`ReportBuilder` that depends on both. All three are registered transient. Building the provider validates that
`FixedClock` needs nothing, that `Greeter`'s single `Clock` parameter maps to the `Clock` registration, and that
`ReportBuilder`'s parameters map to `Greeter` and `Clock` respectively — all before a single object is constructed.
Resolving `ReportBuilder` then constructs, bottom-up, one `FixedClock` for the builder's own `Clock` parameter, a
second `FixedClock` for the `Greeter` nested inside it, and one `Greeter`. Two clocks, because transient means
transient.

### Configuration through a factory

A `DatabaseConfig` carrying a plain `str` DSN cannot be constructor-injected — `str` is not registered, and per the
strict rules that is an error rather than an implicit `""`. The idiomatic fix is a factory:
`services.add_transient(DatabaseConfig, factory=lambda _: DatabaseConfig(dsn=os.environ["DSN"]))`. A `Repository`
declaring `def __init__(self, config: DatabaseConfig)` then resolves normally; validation treats `DatabaseConfig` as a
satisfied leaf without ever peering inside the lambda. The factory's `provider` parameter is there for the case where
the factory itself needs to pull other services out of the container.

### A cycle caught before anything is built

Registering `Alpha` (which takes a `Beta`) and `Beta` (which takes an `Alpha`) is perfectly legal at registration time —
neither call knows about the other. The failure surfaces on `build_service_provider()`, which raises
`CircularDependencyError` with `chain == (Alpha, Beta, Alpha)`. Nothing was instantiated, and no partially constructed
object escaped. Breaking the cycle requires a design change on the caller's side (extract a shared collaborator, or
have one side take the `ServiceProvider` and pull the other lazily); FastDI offers no lazy proxy.

## Out of scope

Explicitly **not** part of this spec, so `plan-implementation` does not need to design for them:

- Singleton and scoped lifetimes, and `ServiceProvider.create_scope()`.
- Async factories, `async def` resolution, and awaiting anything.
- Disposal / `close()` / context-manager integration.
- Enumerating multiple registrations for one service type (`get_services`), and `try_add_*` conditional registration.
- Registering pre-built instances (`add_instance`).
- Open generics — resolving `Repository[User]` from a `Repository[T]` registration.
- Decorator-based registration sugar.
- Named / keyed services, and `Annotated[...]` markers as resolution keys.
- Thread safety guarantees. Transient resolution holds no mutable state, but nothing here is documented as safe to
  build or mutate concurrently.

## Design notes

Points where the English description had to bend to what Python can actually do, and how this spec resolved them:

- **Three registration shapes, one method.** "`add_transient` behaves differently depending on what you pass" is C#
  overload thinking; Python has no call-site type dispatch. The shapes are therefore distinguished by _arity_ and by a
  _keyword-only_ `factory` parameter — never by inspecting the runtime type of a positional argument. `typing.overload`
  documents the valid combinations for type checkers, but it generates no runtime dispatch, so `add_transient`'s single
  implementation still validates its arguments itself and raises `RegistrationError`.
- **Constructor inference is a runtime operation.** Python has no compile step, so nothing here can depend on static
  analysis. Everything is `inspect.signature` plus `typing.get_type_hints` at `build_service_provider()` time, which is
  also why validation is eager: build time is the earliest moment FastDI can possibly know the graph is sound.
- **One constructor, no signature matching.** A Python class has exactly one `__init__`, so there is no
  "pick the best overload" problem. Anything needing selection between construction strategies goes through an explicit
  `factory` instead.
- **Sync all the way down.** The resolution path is entirely synchronous, so an `async def` factory is a category error
  and is rejected at registration rather than producing an un-awaited coroutine. Note the limit of this check: FastDI
  can detect a coroutine _function_, but a plain `def` factory that returns a coroutine object is indistinguishable
  from any other factory and will be returned as-is.
- **`type[T]` with Protocol and ABC keys.** `service_type` is annotated `type[T]` because it is only ever used as a
  dictionary key. Type checkers are sometimes unhappy about passing a `Protocol` class where `type[T]` is expected;
  that is a type-checker limitation, not a runtime one, and this spec does not contort the signature to work around it.
- **No enforced privacy.** `ServiceProvider` is described as immutable, meaning FastDI provides no public API to mutate
  it after construction. Python cannot stop a caller from reaching into an underscore-prefixed attribute, and no
  behavior in this spec depends on it being impossible.
- **Cycles fail loudly.** Rather than leaving circular constructor dependencies implicit, they are detected during the
  build-time graph walk and reported with the full chain. There is no lazy proxy and no partial construction.
