# Spec: Singleton Scope

Adds the **singleton** lifetime alongside the transient lifetime from `constructor-injection`: a service registered
as a singleton is constructed at most once per `ServiceProvider`, and every resolution of it after the first returns
that same cached instance. This spec extends `ServiceCollection` with `add_singleton`; it does not change
`add_transient`, `get_service`, or `get_required_service` in any way, and mixed graphs (a transient depending on a
singleton, or vice versa) work exactly as you'd expect from the two lifetimes composing.

**Scoped lifetime (`ServiceProvider.create_scope()`) is a separate capability and is not part of this spec.** Reading
"scope" in this spec's name as "the container scoping an instance to itself" is correct; reading it as "the
`IServiceScope` / per-request scope from ASP.NET Core" is not — that gets its own spec later.

## Public API

Everything below is exported from the top-level `fastdi` package, in addition to everything `constructor-injection`
already exports.

```python
from collections.abc import Callable
from typing import Self, overload

type Factory[T] = Callable[[ServiceProvider], T]


class ServiceCollection:
  """A mutable registry of service registrations."""

  @overload
  def add_singleton[T](self, service_type: type[T], /) -> Self: ...

  @overload
  def add_singleton[T](self, service_type: type[T], implementation_type: type[T], /) -> Self: ...

  @overload
  def add_singleton[T](self, service_type: type[T], instance: T, /) -> Self: ...

  @overload
  def add_singleton[T](self, service_type: type[T], /, *, factory: Factory[T]) -> Self: ...

  def add_singleton[T](
    self,
    service_type: type[T],
    implementation_type_or_instance: type[T] | T | None = None,
    /,
    *,
    factory: Factory[T] | None = None,
  ) -> Self: ...
```

No new exception types are introduced. `add_singleton` raises the same `RegistrationError` this spec extends the
conditions of, and `build_service_provider()` / resolution still raise `MissingDependencyError`,
`CircularDependencyError`, and `ServiceNotRegisteredError` under the same circumstances described in
`constructor-injection`.

## Behavior

### Registration

`add_singleton` accepts four shapes, and returns `self` so calls can be chained fluently, consistent with
`add_transient`:

1. **`add_singleton(Impl)`** — registers the concrete class `Impl` under itself. The first resolution constructs
   `Impl` via constructor injection; every later resolution returns that same instance.
2. **`add_singleton(ServiceType, Impl)`** — registers `Impl` under a different key, same rules as
   `add_transient(ServiceType, Impl)`. `ServiceType` may be abstract; it is only ever used as a dictionary key.
3. **`add_singleton(ServiceType, instance)`** — registers an already-built object directly. No construction ever
   happens for this registration: every resolution of `ServiceType`, from the very first, returns `instance` itself.
4. **`add_singleton(ServiceType, factory=...)`** — registers a callable that will be handed the `ServiceProvider`.
   The first resolution calls `factory(provider)` and caches whatever it returns; later resolutions skip the call
   and return the cached value.

**Distinguishing shape 2 from shape 3 is a runtime check, not a type-checker trick:** a Python class is itself an
instance of `type`, so `add_singleton` decides which shape it was given with `isinstance(second_argument, type)`. A
class → shape 2 (`implementation_type`); anything else → shape 3 (`instance`). This has one sharp edge, documented
under [Design notes](#design-notes): a value that is itself a class object can never be registered as an _instance_
this way, because it is indistinguishable from shape 2's `implementation_type`. There is also no way to register a
literal `None` as an instance: the sentinel default for "no second argument" is itself `None`, so
`add_singleton(ServiceType, None)` is identical to `add_singleton(ServiceType)` — it selects shape 1, not "an
instance whose value is `None`". A factory that returns `None` (`add_singleton(ServiceType, factory=lambda _: None)`)
is the way to register that value.

`add_singleton` raises `RegistrationError` when:

- Both a second positional argument (`implementation_type` or `instance`) and `factory` are supplied.
- `service_type` is not a class.
- The class that would be **instantiated** is abstract — i.e. it has a non-empty `__abstractmethods__`, or is a
  `Protocol` class. This applies to `implementation_type` in shape 2, and to `service_type` in shape 1 where it
  stands as its own implementation. It does not apply to shape 3: an `instance` is already built, so there is
  nothing to instantiate and nothing to reject.
- `factory` is supplied but is not callable, or is a coroutine function.
- `service_type` is `ServiceProvider`. Exactly as in `constructor-injection`, `ServiceProvider` is implicitly
  registered as itself in every provider — effectively a singleton already — and that implicit registration cannot
  be overridden by any registration method, `add_singleton` included.

FastDI does **not** verify that `implementation_type` or `instance` satisfies `service_type`, for the same reasons
given in `constructor-injection`: the container only ever uses `service_type` as a dictionary key.

**Re-registering the same `service_type` is allowed and the last registration wins, regardless of which method
registered it.** `services.add_transient(Logger, ConsoleLogger); services.add_singleton(Logger, FileLogger)` leaves
`Logger` registered as a singleton `FileLogger`; the earlier transient registration is discarded outright, not
merged with the new one.

**Caching is keyed by the registered `service_type`, not by the implementation class.** Registering the same `Impl`
under two different `service_type` keys — `add_singleton(A, Impl)` and `add_singleton(B, Impl)` — produces two
independent singleton instances, one cached under `A` and one under `B`.

### Building and validation

`build_service_provider()`'s eager, build-time validation walk from `constructor-injection` is unchanged and applies
uniformly across lifetimes: a singleton registration backed by an implementation type has its constructor inspected
and its parameters resolved exactly like a transient one, and `MissingDependencyError` / `CircularDependencyError`
are raised at build time under the same conditions. A cycle running through a mix of singleton and transient
registrations is still a cycle and is still caught — lifetime plays no part in graph-shape validation.

An instance registration (shape 3) is a trivially satisfied leaf: there is no constructor to walk, so it can never
be the source of a `MissingDependencyError` and can never participate in a cycle.

**Building the provider never constructs anything.** Exactly as with transients, `build_service_provider()` only
validates that the graph is shape-correct; it does not call any constructor or factory. This holds for singletons
too — including type- and factory-backed ones — which are always constructed lazily, on their first resolution, not
at build time. The one exception is shape 3: an `instance` registration has nothing to construct because it was
already built by the caller before it was ever registered.

### Resolution and caching

- The first `get_required_service(T)` (or `get_service(T)`) call for a singleton-registered `T` builds the instance
  — via constructor injection for shape 1/2, by calling `factory(provider)` for shape 4, or by returning the
  pre-built object immediately for shape 3 — and caches it on the `ServiceProvider` that resolved it.
- Every subsequent resolution of `T`, through either method, on that same provider, returns the identical cached
  object. `provider.get_required_service(T) is provider.get_required_service(T)` holds for a singleton `T`.
- The cache lives on the `ServiceProvider`, not the `ServiceCollection`. Two providers built from the same collection
  (`collection.build_service_provider()` called twice) each get their own cache and therefore their own singleton
  instances — except for shape 3, where both providers return the same pre-built `instance`, since it's the same
  object handed to both collections' registrations to begin with.
- A singleton's dependencies are resolved once, at the moment it is first built, following their own lifetimes as
  normal: a transient dependency nested inside a singleton is built once (because the singleton that owns it is
  built once), while a singleton dependency nested inside a transient is the same cached object every time the
  transient is rebuilt.
- `get_service(T)` still returns `None` for an unregistered `T`, and still lets any exception raised while
  constructing a singleton (from its constructor or its factory) propagate out unchanged, on the resolution that
  triggers construction. A later resolution after a failed first attempt is not specified by this spec — see
  [Out of scope](#out-of-scope).

## Worked examples

### An app-wide config object handed in whole

A caller builds an `AppConfig` itself — plain construction, no container involved — and registers it directly:
`services.add_singleton(AppConfig, config)`. Every service that declares an `AppConfig` constructor parameter,
however deep in the graph and however many times it's resolved, receives that exact object back. There is no
"first resolution builds it" step to reason about, because it was never the container's job to build it.

### A shared counter behind a transient front door

`RequestCounter` is registered bare (`services.add_singleton(RequestCounter)`) and a `RequestHandler` — registered
_transient_ — takes one as a constructor parameter. Resolving `RequestHandler` twice produces two different handler
objects, but `first_handler.counter is second_handler.counter` is `True`: both handlers were built against the same
underlying counter. Calling `increment()` through either handler is visible through the other, because there was
only ever one `RequestCounter` to begin with.

### A factory-built singleton, constructed once no matter how many consumers pull it in

`services.add_singleton(Database, factory=lambda p: Database(os.environ["DSN"]))` reads the environment exactly
once — on whichever resolution happens to be first, whether that's a direct `get_required_service(Database)` or a
transient service that has `Database` as one of several constructor parameters. Every other consumer, direct or
nested, receives the same `Database` object; the factory lambda is never invoked a second time on that provider.

## Out of scope

Explicitly **not** part of this spec, so `plan-implementation` does not need to design for them:

- **Scoped lifetime**, `ServiceProvider.create_scope()`, and everything ASP.NET Core calls a "scope" — a future spec.
- Disposal / `close()` / context-manager integration, for singletons or otherwise.
- Async factories, `async def` resolution, and awaiting anything.
- Eager singleton construction at build time (an opt-in "validate and build everything now" mode). Singletons are
  always built lazily in this spec, with no way to ask for eager construction.
- Thread safety guarantees for the lazy first-resolution race. If two threads call `get_required_service(T)` for the
  same not-yet-built singleton `T` concurrently, this spec does not guarantee the constructor or factory runs
  exactly once, nor which of the two resulting objects (if two get built) ends up cached. Nothing in
  `constructor-injection` was documented as concurrency-safe either; this spec doesn't change that.
- Recovering from a failed singleton construction. Whether a second resolution attempt retries the constructor/factory
  or re-raises a cached failure is unspecified.
- Enumerating multiple registrations for one service type (`get_services`), and `try_add_*` conditional registration.
- Open generics.
- Decorator-based registration sugar.
- Named / keyed services.

## Design notes

Points where the English description had to bend to what Python can actually do, and how this spec resolved them:

- **A fourth shape, still no call-site type dispatch.** Adding "or a pre-built instance" to `add_transient`'s three
  shapes looks like C#'s `AddSingleton<T>(T instance)` overload, which .NET resolves at compile time from the static
  type of the argument. Python has no such thing, so shape 2 (`implementation_type`) and shape 3 (`instance`) are
  told apart with a single runtime check: `isinstance(second_argument, type)`. Every ordinary object fails that
  check and lands in shape 3; every class passes it and lands in shape 2.
- **A value that is itself a class can't be an "instance."** The `isinstance(x, type)` check above has exactly one
  case it can't resolve correctly: registering a class object as _data_ (e.g. a plugin registry whose "instance" of
  interest happens to be a `type`). `add_singleton(Registry, SomeClass)` always reads `SomeClass` as
  `implementation_type` and tries to instantiate it, never as "the instance to hand back verbatim." This is a
  narrow, acknowledged gap rather than a solved edge case; a factory (`add_singleton(Registry, factory=lambda _:
  SomeClass)`) is the escape hatch, since a factory's return value is never type-sniffed.
- **`None` can't be an instance either**, for the same reason C#'s nullable-vs-omitted distinction doesn't translate:
  Python has no separate "not provided" sentinel distinct from `None` on a plain positional parameter. This spec
  reuses `None` as the "nothing after `service_type`" default, which means it can't simultaneously mean "the
  instance is `None`." A factory returning `None` is the way to express that.
- **Lazy construction, not eager.** `constructor-injection` already established that `build_service_provider()`
  validates shape but constructs nothing; singletons keep that invariant rather than special-casing "build me now
  because I'm cached anyway." The alternative — construct every singleton during `build_service_provider()` — would
  make build order (and thus, for factories with side effects, program behavior) depend on registration order in a
  way this spec deliberately avoids.
- **No enforced privacy, same as before.** The cache described here lives on the `ServiceProvider` conceptually;
  nothing in this spec depends on a caller being unable to reach into it directly.
