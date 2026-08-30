# Spec: Scoped Services

Adds the **scoped** lifetime alongside the transient and singleton lifetimes from `constructor-injection` and
`singleton-scope`. A service registered as scoped is constructed at most once per `ServiceScope`, and every
resolution of it within that scope after the first returns that same cached instance — but a different scope gets
its own, independent instance. This is the `ServiceProvider.create_scope()` capability that `singleton-scope`
flagged as "a future spec." It extends `ServiceCollection` with `add_scoped` and `ServiceProvider` with
`create_scope`; it does not change `add_transient`, `add_singleton`, `get_service`, or `get_required_service` in any
way, and mixed graphs across all three lifetimes work exactly as you'd expect from them composing.

## Public API

Everything below is exported from the top-level `fastdi` package, in addition to everything `constructor-injection`
and `singleton-scope` already export.

```python
from collections.abc import Callable
from typing import Self, overload

type Factory[T] = Callable[[ServiceProvider], T]


class ServiceCollection:
  """A mutable registry of service registrations."""

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
  ) -> Self: ...


class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def create_scope(self) -> "ServiceScope": ...


class ServiceScope:
  """A boundary within which every scoped service resolves to one shared instance."""

  @property
  def service_provider(self) -> ServiceProvider: ...
```

No new exception types are introduced. `add_scoped` raises the same `RegistrationError` this spec extends the
conditions of, and `build_service_provider()` / resolution still raise `MissingDependencyError`,
`CircularDependencyError`, and `ServiceNotRegisteredError` under the same circumstances described in
`constructor-injection`.

## Behavior

### Registration

`add_scoped` accepts exactly three shapes — the same three as `add_transient`, and for the same reason: there is no
"already-built instance" shape, because an object that already exists doesn't belong to any particular scope. That
shape is exactly what `add_singleton`'s instance forms already mean; `add_scoped` doesn't duplicate them.

1. **`add_scoped(Impl)`** — registers the concrete class `Impl` under itself. The first resolution within a given
   scope constructs `Impl` via constructor injection; every later resolution _within that same scope_ returns that
   same instance.
2. **`add_scoped(ServiceType, Impl)`** — registers `Impl` under a different key, same rules as
   `add_transient(ServiceType, Impl)`. `ServiceType` may be abstract; it is only ever used as a dictionary key.
3. **`add_scoped(ServiceType, factory=...)`** — registers a callable that will be handed the scope's
   `ServiceProvider`. The first resolution within a scope calls `factory(provider)` and caches whatever it returns
   for that scope; later resolutions within the same scope skip the call and return the cached value.

`add_scoped` raises `RegistrationError` under exactly the conditions `add_transient` does:

- Both `implementation_type` and `factory` are supplied.
- `service_type` is not a class.
- `implementation_type` is supplied but is not a class.
- The class that would be **instantiated** is abstract — i.e. it has a non-empty `__abstractmethods__`, or is a
  `Protocol` class. This applies to `implementation_type` in shape 2, and to the first argument in shape 1 where it
  stands as its own implementation.
- `factory` is supplied but is not callable, or is a coroutine function.
- The resolved `service_type` is `ServiceProvider`. Exactly as with `add_transient` and `add_singleton`,
  `ServiceProvider` is implicitly registered in every provider and that registration cannot be overridden.

FastDI does **not** verify that `implementation_type` satisfies `service_type`, for the same reasons given in
`constructor-injection`.

**Re-registering the same `service_type` is allowed and the last registration wins, regardless of which method or
lifetime registered it before** — exactly as `singleton-scope` describes for `add_singleton`.
`services.add_transient(Session); services.add_scoped(Session)` leaves `Session` scoped; the earlier transient
registration is discarded outright.

### Building and validation

`build_service_provider()`'s eager, build-time validation walk is unchanged and applies uniformly across all three
lifetimes: a scoped registration backed by an implementation type has its constructor inspected and its parameters
resolved exactly like a transient or singleton one, and `MissingDependencyError` / `CircularDependencyError` are
raised at build time under the same conditions. A cycle running through any mix of the three lifetimes is still a
cycle and is still caught — lifetime plays no part in graph-shape validation.

**Building the provider, and creating a scope, never construct anything.** `build_service_provider()` only validates
that the graph is shape-correct, and `create_scope()` only allocates a new, empty cache for that scope's scoped
services — neither calls any constructor or factory. Every scoped instance, like every singleton, is always
constructed lazily, on its first resolution within the scope that resolves it.

### Scopes and resolution

- `provider.create_scope()` returns a `ServiceScope`. Its `.service_provider` is a fully-functional `ServiceProvider`
  — `get_service`, `get_required_service`, and `create_scope` all work on it exactly as on any other provider — that
  additionally has its own private cache for scoped services.
- The first `get_required_service(T)` (or `get_service(T)`) call for a scoped-registered `T`, made through a given
  scope's `service_provider`, builds the instance — via constructor injection for shape 1 or shape 2, or by calling
  `factory(provider)` for shape 3 — and caches it on that scope. Every later resolution of `T` through that same
  scope's `service_provider`, via either method, returns the identical cached object:
  `scope.service_provider.get_required_service(T) is scope.service_provider.get_required_service(T)` holds.
- **Two different scopes never share a scoped instance.** `provider.create_scope()` called twice produces two
  `ServiceScope`s whose `service_provider`s each build and cache their own `T`, even though both scopes came from the
  same `ServiceProvider` and the same `ServiceCollection`.
- **Singletons are shared by the root provider and every scope descended from it.** Unlike scoped instances, a
  singleton's cache is not private to a scope: `provider.get_required_service(S)`,
  `provider.create_scope().service_provider.get_required_service(S)`, and the same call through a second scope all
  return the identical `S`, for a singleton-registered `S`. Transient resolution is likewise unaffected by scopes —
  every resolution still allocates, whether made through the root or through a scope.
- **Nesting**: calling `.create_scope()` on a `ServiceProvider` obtained from `ServiceScope.service_provider`
  produces a new, independent child scope. A scoped service resolved through the child is a different instance from
  the same service resolved through its parent scope; both continue to resolve the same object for any
  singleton-registered service, since singleton caching is shared root-wide regardless of nesting depth.
- **The un-scoped root provider — the one returned directly by `build_service_provider()`, before any
  `create_scope()` call — resolves scoped services too, acting as its own scope.** There is no error for skipping
  `create_scope()` and resolving a scoped type directly: the root has its own private scoped-instance cache, exactly
  like any `ServiceScope` would, and the same "first resolution builds and caches, every later resolution on that
  same provider returns the same instance" rule applies to it. Because the root provider typically lives for the
  whole lifetime of the application, this makes a scoped service resolved this way behave indistinguishably from a
  singleton — a known, intentional consequence of this design (see [Design notes](#design-notes)), not a defect.
- A scoped service's dependencies are resolved following their own lifetimes as normal: a transient dependency
  nested inside a scoped service is rebuilt every time the scoped service itself is rebuilt (i.e. once per scope, and
  once more for the root if resolved there too), while a singleton dependency nested inside a scoped service is the
  same object everywhere.
- `ServiceProvider` remains implicitly registered as itself. When a constructor parameter annotated `ServiceProvider`
  is resolved while building an instance through a scope, it receives that scope's `service_provider` — the one
  actually performing the resolution — not the root that created the scope. This has a corollary worth knowing: if a
  **singleton**'s constructor takes a `ServiceProvider` and that singleton happens to be built for the first time
  while resolving through some scope, the `ServiceProvider` it captures and holds forever is that scope's, not the
  root's — because a singleton is only ever constructed once, on whichever resolution happens to be first.
- `get_service(T)` still returns `None`, on any provider (root or scoped), for an unregistered `T`, and still lets
  any exception raised while constructing a scoped instance propagate out unchanged, on the resolution that triggers
  construction.

## Worked examples

### A shared unit of work behind two transient consumers

A `RequestId` and a factory-built `UnitOfWork` (a stand-in for a database session) are both registered scoped; an
`OrderRepository` and a `RequestHandler` are registered transient, each ultimately depending on one or both of them.
Two calls to `scope.service_provider.get_required_service(RequestHandler)` within the _same_ `ServiceScope` produce
two different handler objects — transient is still transient — but
`first_handler.repository.unit_of_work is second_handler.repository.unit_of_work` is `True`: both handlers, however
many transient objects sit between them and the scoped registration, were wired to the one `UnitOfWork` that scope
built. A second, independently created `ServiceScope` gets its own `RequestId` and its own `UnitOfWork` — resolving
through it never sees the first scope's instances.

### A singleton logger threaded through every scope

`Logger` is registered singleton and takes no dependencies. Across the root provider and any number of scopes
created from it, `get_required_service(Logger)` always returns the exact same object: singleton caching doesn't
care whether the call came from `provider` directly or from `provider.create_scope().service_provider` — it's
root-wide, not scope-local. Every scoped `UnitOfWork`, by contrast, only ever sees the operations recorded through
consumers resolved from its own scope.

### Skipping `create_scope()` entirely

An application that registers a scoped `RequestId` but never calls `create_scope()` — because it doesn't need
per-request isolation, say a small script — can still call
`services.build_service_provider().get_required_service(RequestId)` without error. It gets back a `RequestId`, and
every subsequent `get_required_service(RequestId)` call on that same root provider returns the identical object,
because the root is behaving as its own (permanently-lived) scope. That's a legitimate, spec-sanctioned way to use a
scoped registration as a de facto singleton when no narrower scope is ever created — it is exactly what happens to
any scoped registration in an application that has no concept of "requests" to scope by.

## Out of scope

Explicitly **not** part of this spec, so `plan-implementation` does not need to design for them:

- **Disposal, `close()`, and context-manager (`with provider.create_scope() as scope:`) integration** for
  `ServiceScope`. `ServiceScope` in this spec exposes only `.service_provider`; it is not a context manager, and
  ending a scope has no explicit step — it simply means no longer holding a reference to it or its
  `service_provider`. A later spec may add disposal, exactly as `singleton-scope` deferred it for singletons.
- Any "current scope" ambient/implicit tracking (a thread-local or `contextvars`-based "the scope that's currently
  active"). Every scoped resolution goes through the `ServiceProvider` reference the caller was explicitly handed —
  there is no way to ask "what scope am I in right now" from inside a factory or constructor.
- Opt-in scope validation (an equivalent of ASP.NET Core's `ValidateScopes` / `ValidateOnBuild`) that would either
  reject resolving a scoped service off the root provider, or reject a singleton capturing a scope-bound
  `ServiceProvider`. Both remain possible in this spec, by design, exactly as they are upstream by default.
- An injectable scope-factory service (an equivalent of `IServiceScopeFactory`). `ServiceScope` and `create_scope`
  are not themselves resolvable service types.
- Async factories, `async def` resolution, and awaiting anything.
- Eager scoped construction — there is no way to ask a scope to build every scoped registration up front;
  everything is lazy, as with singletons.
- Thread safety guarantees for concurrent resolution, whether within one scope or across scopes sharing a root's
  singleton cache. Nothing in `constructor-injection` or `singleton-scope` was documented as concurrency-safe either.
- Recovering from a failed scoped construction. Whether a second resolution attempt within the same scope retries
  the constructor/factory or re-raises a cached failure is unspecified, exactly as for singletons.
- Enumerating multiple registrations for one service type (`get_services`), and `try_add_*` conditional registration.
- Open generics.
- Decorator-based registration sugar.
- Named / keyed services.

## Design notes

Points where the English description had to bend to what Python can actually do, and how this spec resolved them:

- **`ServiceScope` is a real, separate type, not just an alias for `ServiceProvider`.** A scope's `.service_provider`
  could in principle _be_ a `ServiceProvider` with no wrapper — nothing in this spec's behavior needs a second type
  to exist. It's introduced anyway so that a later spec can attach scope-lifecycle behavior (disposal, a `with`
  block) to `ServiceScope` without changing what `create_scope()` returns or breaking code written against this
  spec. `ServiceScope` is deliberately minimal today — exactly one property — rather than gaining `__enter__` /
  `__exit__` methods that would have nothing to actually do yet.
- **Root-as-its-own-scope, not an error.** Making a bare `provider.get_required_service(T)` raise for a
  scoped `T` would need a new error type, a new place to raise it, and a specification for exactly when it applies —
  none of which any other part of FastDI needed before. Treating the root as an always-available, permanently-lived
  scope keeps exactly one resolution algorithm for every provider, root or scoped alike, at the cost of the same
  captive-dependency footgun .NET accepts as its own default behavior (`ValidateScopes` there is opt-in, not
  automatic).
- **No call-site type dispatch, still.** `add_scoped`'s three shapes are told apart the same way `add_transient`'s
  are: arity plus the keyword-only `factory`, never by inspecting a positional argument's runtime type.
- **No ambient scope.** C# doesn't have one either without deliberately reaching for `AsyncLocal`-backed machinery
  in ASP.NET Core's request pipeline; inventing a Python `contextvars` equivalent here would be adding scope
  _propagation_ magic nobody asked for. A scope in this spec is nothing more than an object a caller holds and passes
  around explicitly — most simply, as the `provider` parameter every `Factory` already receives.
- **A singleton can capture whichever `ServiceProvider` happened to build it, scope included, and that's accepted.**
  This falls straight out of "a singleton is built exactly once, on its first resolution" (already established in
  `singleton-scope`) composed with "resolving through a scope injects that scope's provider" (new in this spec).
  Nothing here special-cases the combination to warn about it or prevent it — same posture as the rest of this
  section's captive-dependency notes.
- **No enforced privacy, same as before.** Both the per-scope cache and the shared singleton cache are described
  here as belonging conceptually to a `ServiceScope` / `ServiceProvider`; nothing in this spec depends on a caller
  being unable to reach into them directly.
