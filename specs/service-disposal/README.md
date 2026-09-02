# Spec: Service Disposal

Gives FastDI a teardown story. Until now the container built objects and never let go of them: `singleton-scope` and
`scoped-services` both deferred disposal explicitly, so a singleton holding a connection pool, or a scoped service
holding a database session, was never told when it was finished with. This spec closes that gap.

Two things become closable — `ServiceProvider` and `ServiceScope` — and both gain `close()` plus the context-manager
protocol, so `with provider.create_scope() as scope:` is now the idiomatic way to run a unit of work. Closing a
provider or a scope disposes the services **it built**, in reverse construction order.

Nothing about registration changes: `add_transient`, `add_singleton`, `add_scoped` and `build_service_provider` take
the same arguments and raise under the same conditions as before. What changes is that the container now remembers
which instances it owns, and what `close()` does with them.

## Public API

Everything below is exported from the top-level `fastdi` package, in addition to everything `constructor-injection`,
`singleton-scope` and `scoped-services` already export.

```python
from types import TracebackType
from typing import Protocol, Self, runtime_checkable


@runtime_checkable
class Disposable(Protocol):
  """A service the container can tear down: anything with a no-argument `close()`."""

  def close(self) -> None: ...


class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def close(self) -> None: ...

  def __enter__(self) -> Self: ...

  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: TracebackType | None,
    /,
  ) -> None: ...


class ServiceScope:
  """A boundary within which every scoped service resolves to one shared instance."""

  def close(self) -> None: ...

  def __enter__(self) -> Self: ...

  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    traceback: TracebackType | None,
    /,
  ) -> None: ...
```

### Exceptions

```python
class ProviderClosedError(FastDIError):
  """A closed `ServiceProvider` or `ServiceScope` was used again."""


class DisposalError(FastDIError, ExceptionGroup[Exception]):
  """One or more services raised while being closed. Raised by `close()` / `__exit__`."""
```

Both are exported from `fastdi`. `DisposalError` is a real `ExceptionGroup`, constructed with the standard
`(message, exceptions)` signature, so `except* ValueError:` picks individual service failures out of it.

## Behavior

### What counts as a disposable service

An instance is disposable if it has a **callable `close` attribute** taking no arguments beyond `self`. That is the
whole test — FastDI does not require inheriting or registering anything, and does not look at `__enter__` /
`__exit__`. The exported `Disposable` protocol is the type-checker-facing name for that shape; see
[Design notes](#design-notes) for why the runtime check is duck-typed rather than an `isinstance(x, Disposable)` call,
and why the context-manager protocol is deliberately not accepted as an alternative.

The check happens **when the container takes ownership of the instance** — the moment it finishes constructing it —
not at registration time and not at close time. A registered type whose instances gain a `close` attribute later, after
construction, is not disposed. A factory that returns an object with `close` is owned as a disposable even though the
registered `service_type` has no `close` at all, because the check looks at the instance the container actually got
back.

A non-disposable service is simply never touched at teardown. It is not an error to register one; the overwhelming
majority of services in a graph have nothing to release.

### Ownership: what the container disposes, and what it does not

FastDI disposes **only the instances it constructed itself**, and only for the two caching lifetimes. Nothing else is
ever closed, no matter how disposable it looks.

| Registration                                       | Constructed by | Disposed by FastDI             |
| -------------------------------------------------- | -------------- | ------------------------------ |
| `add_singleton(Impl)`                              | the container  | yes — by the **root provider** |
| `add_singleton(ServiceType, Impl)`                 | the container  | yes — by the **root provider** |
| `add_singleton(ServiceType, factory=...)`          | the container  | yes — by the **root provider** |
| `add_singleton(instance)`                          | the caller     | **no**                         |
| `add_singleton(ServiceType, instance)`             | the caller     | **no**                         |
| `add_scoped(Impl)`                                 | the container  | yes — by the **owning scope**  |
| `add_scoped(ServiceType, Impl)`                    | the container  | yes — by the **owning scope**  |
| `add_scoped(ServiceType, factory=...)`             | the container  | yes — by the **owning scope**  |
| `add_transient(...)`, any shape                    | the container  | **no** — see below             |
| `ServiceProvider` (the implicit self-registration) | n/a            | **no**                         |

Three rows deserve spelling out, because each is a place a caller could reasonably expect the opposite:

- **Instance registrations are never disposed.** `add_singleton(instance)` and `add_singleton(ServiceType, instance)`
  hand the container an object the caller built and still owns. The container returns it from resolutions and nothing
  more; closing the provider does not call its `close()`, even if it has one. Whoever built it closes it. This mirrors
  ASP.NET Core, where `AddSingleton(new Service())` is likewise excluded from container disposal.
- **Transients are never disposed.** FastDI does not track transient instances at all — it never has, and this spec
  does not start. A disposable registered `add_transient` is handed to the caller and forgotten; if it needs closing,
  the caller closes it, typically with `contextlib.closing` or a `with` block of its own. This is a deliberate,
  documented divergence from ASP.NET Core, which _does_ track transient `IDisposable`s on the resolving scope and is
  well known for leaking them into long-lived scopes as a result. See [Out of scope](#out-of-scope).
- **Singletons are owned by the root provider, whichever provider happened to build them.** Per `scoped-services`, the
  singleton cache is shared root-wide; a singleton first resolved through a scope is cached for everyone. It is
  therefore owned by the root — the provider `build_service_provider()` returned — and closing that scope does **not**
  close it. Any other rule would let one scope tear down an object every other scope is still using.

The corollary: **closing a scope never disposes a singleton, and closing the root disposes every singleton in the
tree.**

### `ServiceProvider.close()`

`close()` on a provider disposes the instances that provider owns, and closes the scopes it created. Concretely, in
this order:

1. The provider is marked closed **first**, before anything is disposed. Every resolution or `create_scope()` call from
   this point on raises `ProviderClosedError` — including one made from inside a service's own `close()` method.
2. Every still-open scope created from this provider is closed, most-recently-created first, by the same rules
   recursively. A scope that was already closed is skipped.
3. The instances this provider owns are closed in **reverse construction order** — last built, first closed.

For the **root provider**, step 3 covers both the singletons (built anywhere in the tree) and the scoped instances the
root built acting as its own scope, as one list in the order they were actually constructed. For a **scope's
provider**, step 3 covers only that scope's scoped instances.

Reverse order is what makes teardown safe: a service is always constructed after everything it depends on, so
disposing in reverse guarantees a service's dependencies are still open while its `close()` runs. A `MetricsSink` that
flushes through a `ConnectionPool` during `close()` can rely on that pool not having been closed yet.

`close()` is **idempotent**: the second and every later call is a no-op that raises nothing. It is safe to call
`close()` on a provider whose parent already closed it via the cascade, and safe to combine `with` with an explicit
`close()`.

### `ServiceScope.close()`

`ServiceScope.close()` closes the scope's `service_provider`, with exactly the semantics above — which is to say
`scope.close()` and `scope.service_provider.close()` do the same thing and either one may be used. It disposes the
scoped instances that scope built, cascades into any child scopes created from it, and never touches a singleton.

A closed scope detaches itself from the provider that created it, so a long-lived root does not accumulate references
to scopes that have finished. A scope that is never closed stays attached and is closed when its parent is.

`ServiceScope.service_provider` keeps returning the same `ServiceProvider` object after the scope is closed; reading
the property never raises. Resolving through that provider is what raises `ProviderClosedError`.

### Context-manager protocol

Both types support `with`:

- `__enter__` returns `self`, so `with provider.create_scope() as scope:` binds the **`ServiceScope`** and resolution
  goes through `scope.service_provider`, matching `using var scope = provider.CreateScope();` in C#. Entering an
  already-closed provider or scope raises `ProviderClosedError`.
- `__exit__` calls `close()` and returns `None`, so it **never suppresses** an exception from the `with` body.
- Neither type is reentrant or reusable. Entering the same open scope twice is not an error, but the first `__exit__`
  closes it and the second finds it already closed and does nothing.

If the body of a `with` raises **and** a service's `close()` also raises, the `DisposalError` propagates and the body's
exception is attached as its `__context__`, per normal Python semantics.

### Errors during disposal

Disposal never stops early. `close()` calls `close()` on **every** instance it owns, even if earlier ones raised, so a
single misbehaving service cannot strand the rest of the graph. Failures are collected as they happen; when the sweep
finishes:

- If nothing raised, `close()` returns `None`.
- If one or more `close()` calls raised, `close()` raises a `DisposalError` — an `ExceptionGroup` holding those
  exceptions in the order they were raised (that is, reverse construction order). The provider is fully closed either
  way; a failed disposal does not leave it usable, and calling `close()` again is still a no-op that raises nothing.

A `BaseException` that is not an `Exception` — `KeyboardInterrupt`, `SystemExit` — is not collected: it propagates
immediately and abandons the rest of the sweep. `DisposalError` derives from `ExceptionGroup`, which by definition
only holds `Exception`s.

A `DisposalError` raised while cascading into a child scope propagates out of the parent's `close()`, after the parent
has finished disposing its own instances. Failures from several scopes and from the provider itself arrive as one flat
`DisposalError` covering the whole cascade.

### Using a closed provider

Once closed, a `ServiceProvider` raises `ProviderClosedError` from `get_service`, `get_required_service` and
`create_scope`, and a closed `ServiceScope` raises it from `__enter__`. Note that `get_service` raises here rather
than returning `None`: `None` means "nothing is registered for this type", which is a different and still-answerable
question — a closed provider cannot answer any question at all. This is consistent with `constructor-injection`'s rule
that `get_service` swallows nothing except the unregistered-type case.

Objects already resolved out of a provider before it closed are unaffected; they are ordinary Python objects and
FastDI has no further say over them. Whether one still _works_ after its dependencies were closed is entirely up to
what those services do in their own `close()`.

### What has not changed

- Registration and `build_service_provider()` validation are untouched. Building a provider still constructs nothing,
  and still raises `MissingDependencyError` / `CircularDependencyError` / `RegistrationError` under exactly the
  conditions the earlier specs describe.
- Resolution semantics are untouched on an open provider: transients still allocate every time, singletons are still
  shared root-wide, scoped instances are still one-per-scope, and the root still acts as its own scope.
- `Disposable` is not a registration key with any special meaning. Registering `add_singleton(Disposable, thing)` is
  an ordinary registration under an ordinary key; the container does not scan for it or treat it differently.
- Two providers built from the same `ServiceCollection` remain fully independent, disposal included: closing one never
  closes the other's singletons. The one thing they genuinely share is any registered `instance`, which neither of them
  disposes.

## Worked examples

### A request scope that closes its session

`ConnectionPool` is registered singleton, `DatabaseSession` scoped and depending on that pool, and `OrderRepository`
transient and depending on the session. A unit of work is one `with provider.create_scope() as scope:` block: inside
it, any number of `scope.service_provider.get_required_service(OrderRepository)` calls each produce a fresh repository,
all wired to the one `DatabaseSession` that scope built. On leaving the block, that session's `close()` runs exactly
once. The `ConnectionPool` is untouched — it is a singleton, owned by the root, and the next scope will use it too.
The repositories are untouched as well, because they are transient; if a repository needed closing, the code that
resolved it would have to close it.

### Reverse-order teardown of the whole application

`services.build_service_provider()` produces a root that is closed once, at shutdown. `ConnectionPool` was built first
(a `MetricsSink` singleton depends on it, so it had to be), the `MetricsSink` second. `provider.close()` closes the
sink first and the pool second, which is the only order that lets `MetricsSink.close()` flush its last batch through a
pool that is still open. Had the application also resolved a scoped service directly off the root — legal, per
`scoped-services` — that instance sits in the same ordered list and is closed at its own position in it, not in a
separate pass.

### A config object the container must not close

An `AuditLog` is built by the caller and registered with `services.add_singleton(audit_log)`. Everything in the graph
takes it as a dependency and writes to it, including the `close()` methods of the services being torn down. After
`provider.close()` returns, `audit_log` is still open and still holds the complete record of the shutdown, because
FastDI never disposes an instance it did not construct. Closing it, if it ever needs closing, is the caller's job —
the same caller who built it.

## Out of scope

Explicitly **not** part of this spec, so `plan-implementation` does not need to design for them:

- **Async disposal.** No `aclose()`, no `__aenter__` / `__aexit__`, no `IAsyncDisposable` equivalent, and no awaiting
  anything — consistent with every earlier spec's "sync all the way down" stance. A service whose only teardown is a
  coroutine is not disposable as far as this spec is concerned; its `close()` would have to be a plain `def`.
- **Transient disposal tracking.** FastDI does not remember transient instances and therefore cannot close them, as
  described under [Ownership](#ownership-what-the-container-disposes-and-what-it-does-not). Adding the ASP.NET Core
  behavior — tracking transient `IDisposable`s on the resolving scope — is a possible later spec, and would need to
  answer the captive-transient leak that behavior is known for.
- **Thread safety.** Concurrent `close()` and resolution, or two threads closing the same provider at once, are not
  specified, exactly as concurrent resolution was left unspecified by `singleton-scope` and `scoped-services`.
- **Disposing via the context-manager protocol** (`__exit__`) or any other teardown convention — `dispose()`,
  `shutdown()`, `__del__`. `close()` is the only method FastDI calls. See [Design notes](#design-notes).
- **Opting a container-built service out of disposal**, or opting a transient or a registered instance in. Ownership
  follows from the registration shape and cannot be overridden per registration.
- **Deduplicating by identity.** If one object is taken into ownership twice — most plausibly a factory that returns
  the same shared object for two different `service_type` keys — its `close()` is called twice. FastDI closes each
  ownership it recorded, and `close()` is conventionally idempotent.
- **A disposal timeout, or any ordering control** beyond reverse construction order. No priority, no explicit
  dependency hints, no way to run a service's teardown early.
- **Weakly-held scopes.** A scope that is created and never closed is kept alive by its parent until the parent
  closes. There is no automatic collection of abandoned scopes and no `__del__`-based safety net.
- Everything the earlier specs already list and this one does not change: `get_services`, `try_add_*`, open generics,
  decorator-based registration sugar, named / keyed services, ambient scope tracking, eager construction, opt-in scope
  validation, and recovering from a failed construction.

## Design notes

Points where the English description had to bend to what Python can actually do, and how this spec resolved them:

- **`close()`, not `__exit__`, is the disposal protocol.** Python has two competing "release your resources"
  conventions, and accepting both would need a precedence rule for objects carrying both. `close()` wins because it is
  the one that means "you are finished with this object" independently of a lexical block: `__exit__` is the back half
  of a `with` statement, takes three exception arguments describing a block the container was never part of, and
  pairs with an `__enter__` the container never called. Calling `obj.__exit__(None, None, None)` on something FastDI
  never entered is a protocol violation, not a shortcut. A class that only implements the context-manager protocol is
  adapted in one line — give it a `close()`, or register it through a factory that wraps it — which is a smaller cost
  than the ambiguity of supporting both.
- **Duck-typed detection, not `isinstance(x, Disposable)`.** `Disposable` is exported and is `runtime_checkable`, so
  `isinstance` works, but FastDI's own check is `callable(getattr(instance, "close", None))` because a
  `runtime_checkable` protocol's `isinstance` verifies only that the attribute _exists_ — an object with
  `close = "not callable"` passes it and then blows up at teardown. The stricter runtime check is what the container
  uses; the protocol is what a caller annotates against.
- **`DisposalError` is genuinely both a `FastDIError` and an `ExceptionGroup`.** Multiply inheriting from a
  pure-Python `Exception` subclass and the built-in `ExceptionGroup` works on 3.14 without a custom `__new__`,
  provided the standard `(message, exceptions)` signature is kept — verified before this spec was written, because the
  C-level layout rules make this the kind of thing that can fail outright. Keeping `FastDIError` in the bases preserves
  `constructor-injection`'s promise that it is the base class for every error FastDI raises, while `ExceptionGroup`
  gets `except*` and structured access to the individual service failures for free. This is why disposal reports
  _every_ failure rather than the first: with `ExceptionGroup` in the language, aggregating is strictly better than
  choosing, and a teardown sweep that stopped at the first failure would leak everything after it.
- **`__enter__` returns the scope, not its provider.** `with provider.create_scope() as scope:` reads as though it
  should hand back something you can resolve from, and `ServiceScope` is not that — you still write
  `scope.service_provider.get_required_service(T)`. Returning the provider instead would have made `with` and the
  plain `create_scope()` call bind different types for the same expression, and would leave no object to close.
  This matches C#'s `using var scope = provider.CreateScope()` exactly.
- **The closed flag is set before disposal begins, not after.** This makes "a service's `close()` resolves something
  from the provider" a loud `ProviderClosedError` instead of a silent resurrection that would build a fresh singleton
  into a cache nobody will ever close again.
- **Ownership is decided by registration shape, and there is no opt-out.** "The container disposes what the container
  created" is one sentence a caller can hold in their head, and it is the rule .NET settled on. A per-registration
  `dispose=False` flag would have to be threaded through five `add_singleton` overloads and three `add_scoped` ones to
  buy back something a factory already expresses: wrap the object so the container owns a disposable proxy, or hand it
  in as an instance so the container owns nothing.
- **`ServiceScope` finally has something to do.** `scoped-services` introduced it as a deliberately minimal wrapper —
  one property, no behavior — specifically so this spec could attach lifecycle to it without changing what
  `create_scope()` returns. That bet is now cashed: `ServiceScope` gains `close`, `__enter__` and `__exit__`, and
  nothing written against the previous spec breaks.
- **No enforced privacy, same as before.** The list of owned instances and the closed flag are described here as
  belonging to a `ServiceProvider`; nothing in this spec depends on a caller being unable to reach in and mutate them.
