---
status: done
date: 2026-08-30
completed: 2026-08-30
specs: [constructor-injection]
---

# Constructor injection, transient lifetime

## Context

Satisfies [specs/constructor-injection/README.md](specs/constructor-injection/README.md), the foundational spec. It is
the only spec that exists, and `./src/fastdi` is an empty package, so this plan builds FastDI's entire runtime from
nothing: `ServiceCollection`, `ServiceProvider`, the five exceptions, and the build-time graph walk.

There are no other plans; this supersedes nothing.

### Spec cross-check

README, `main.py` and `tests/test_constructor_injection.py` agree — no contradictory drift, nothing to send back to
`create-spec`. Two _gaps_ worth recording (design for the README, which is authoritative):

- The spec suite tests only happy paths; it deliberately asserts nothing about `RegistrationError`,
  `MissingDependencyError`, `CircularDependencyError` or `ServiceNotRegisteredError`, nor about snapshot semantics.
  Every one of those is specified prose-only. They are the bulk of the `./tests/` additions below.
- `main.py` exercises no positional-only parameter, no keyword-only parameter, no `Annotated[...]`, no `X | None`
  default and no `*args`/`**kwargs` — all of which the README pins down precisely. Covered in `./tests/` too.

## Current state

- `src/fastdi/__init__.py` — a module docstring, nothing else.
- `tests/` — empty (`.gitkeep` only).
- `conftest.py` at the repo root already puts each `specs/*/src` on `sys.path`, and `pyproject.toml` already sets
  `testpaths = ["tests", "specs"]`, so a single `pytest` run collects both. No test plumbing to add.
- `[tool.pyright] exclude` lists `specs`, so the spec tree is not type-checked. Leave that alone; this plan does not
  touch `pyproject.toml`.

## `./src/fastdi` changes

Ordered so implementation proceeds top-to-bottom with no forward dependencies. Every module except `__init__.py` is
underscore-private; the public surface is exactly what `__init__.py` re-exports.

### 1. `src/fastdi/_errors.py` (new)

The five exceptions from the spec's [Exceptions](specs/constructor-injection/README.md) section. No behavior beyond
storing attributes and producing a readable message.

```python
class FastDIError(Exception): ...


class RegistrationError(FastDIError): ...


class ServiceNotRegisteredError(FastDIError):
  service_type: type

  def __init__(self, service_type: type, /) -> None: ...


class MissingDependencyError(FastDIError):
  service_type: type
  implementation_type: type
  parameter_name: str
  parameter_type: type | None

  def __init__(self, service_type, implementation_type, parameter_name, parameter_type, /) -> None: ...


class CircularDependencyError(FastDIError):
  chain: tuple[type, ...]

  def __init__(self, chain: tuple[type, ...], /) -> None: ...
```

Each `__init__` must call `super().__init__(<message>)` so `str(exc)` is useful, and must assign the documented
attributes. `CircularDependencyError`'s message should render the chain as `A -> B -> A` using `__name__`.

### 2. `src/fastdi/_inspection.py` (new)

Pure functions over classes; no knowledge of the container. Two responsibilities.

**Abstractness**, used by registration validation:

```python
def is_abstract(cls: type, /) -> bool: ...
```

True when `cls.__abstractmethods__` is non-empty _or_ `typing.is_protocol(cls)` is true (Python ≥ 3.13 gives us
`typing.is_protocol`; the project requires ≥ 3.14, so use it rather than poking `_is_protocol`). This is the
"the class that would be **instantiated** is abstract" check from
[Registration](specs/constructor-injection/README.md). Note the asymmetry the spec calls for: it is applied only to the
type that gets instantiated, never to a `service_type` that has a separate implementation or factory.

**Constructor parameters**:

```python
@dataclass(frozen=True, slots=True)
class ConstructorParameter:
  name: str
  annotation: type | None  # None when unannotated
  positional_only: bool
  has_default: bool


def constructor_parameters(implementation_type: type, /) -> tuple[ConstructorParameter, ...]: ...
```

Implements [Constructor inference](specs/constructor-injection/README.md):

- `inspect.signature(implementation_type.__init__)`, so `__init__` is found through the MRO and an implementation with
  no `__init__` of its own picks up the base class's. A class that lands on `object.__init__` yields `()` — its
  signature is `(self, /, *args, **kwargs)`, all of which are dropped by the next two rules.
- Drop the first parameter (`self`), and drop every `VAR_POSITIONAL` / `VAR_KEYWORD` parameter.
- `typing.get_type_hints(implementation_type.__init__, include_extras=True)` for annotations. PEP 649 lazy evaluation
  means a constructor may name a class defined later in the module; quoted annotations and
  `from __future__ import annotations` work through the same call. A parameter absent from the hints mapping is
  unannotated → `annotation=None`.
- Unwrap `Annotated[X, ...]` to `X`. `typing.get_origin(hint) is Annotated` → take `typing.get_args(hint)[0]`. Do this
  after `get_type_hints(..., include_extras=True)`, not by omitting `include_extras`, so the unwrapping is explicit and
  a later spec can start reading the metadata.
- `positional_only` is `kind is Parameter.POSITIONAL_ONLY`; `has_default` is `default is not Parameter.empty`.
- Do **no** normalization of `X | None`. A union annotation stays a union and simply won't match any registration key —
  which is what the spec's "no special handling of `X | None`" rule requires, and falls out for free.

`constructor_parameters` is called at build time only.

### 3. `src/fastdi/_registrations.py` (new)

The internal record types the collection stores and the provider consumes.

```python
type Factory[T] = Callable[[ServiceProvider], T]  # see note below


@dataclass(frozen=True, slots=True)
class TypeRegistration:
  implementation_type: type


@dataclass(frozen=True, slots=True)
class FactoryRegistration:
  factory: Factory[Any]


type Registration = TypeRegistration | FactoryRegistration
```

`Factory` needs `ServiceProvider` in its definition but `ServiceProvider` lives in `_provider.py`, which imports these
records. Break the cycle by declaring `Factory` in `_provider.py` (next to the class it names) and importing it here
under `if TYPE_CHECKING:`. The public `Factory` alias is re-exported from `__init__.py` either way.

### 4. `src/fastdi/_provider.py` (new)

```python
type Factory[T] = Callable[[ServiceProvider], T]


class ServiceProvider:
  def __init__(self, plan: Mapping[type, ResolutionPlan], /) -> None: ...
  def get_service[T](self, service_type: type[T], /) -> T | None: ...
  def get_required_service[T](self, service_type: type[T], /) -> T: ...
```

`__init__` is internal by convention — the spec's "immutable" is a no-public-mutation promise, not an enforced one, so
no `__slots__` gymnastics or frozen dataclass is required. It stores the validated plan produced by
`build_service_provider` (see §5) and nothing else.

Resolution:

- `service_type is ServiceProvider` → return `self`, before any dictionary lookup. This is the implicit registration
  from [Constructor inference](specs/constructor-injection/README.md), and it is why `get_required_service` cannot be
  reached with `ServiceProvider` unregistered.
- Otherwise look the type up in the plan. Missing → `get_service` returns `None`, `get_required_service` raises
  `ServiceNotRegisteredError(service_type)`. `get_service` must be implemented as
  "`return None` if absent, else delegate to the same construction path" — **not** as `try: get_required_service()
  except FastDIError: return None`, because the spec is explicit that `get_service` swallows nothing else, including a
  `ServiceNotRegisteredError` raised from inside a factory.
- `FactoryRegistration` → `factory(self)`, returned as-is with no isinstance check.
- `TypeRegistration` → build each planned dependency recursively, then
  `implementation_type(*positional, **keyword)`. Positional-only dependencies go in `positional` in signature order;
  everything else goes in `keyword`. Parameters that the plan resolved to "use the default" are simply absent from both.

No caching anywhere: every `get_*` call walks the graph afresh, so a diamond builds its shared leaf twice.

### 5. `src/fastdi/_collection.py` (new)

```python
class ServiceCollection:
  def __init__(self) -> None: ...
  @overload
  def add_transient[T](self, service_type: type[T], /) -> Self: ...
  @overload
  def add_transient[T](self, service_type: type[T], implementation_type: type[T], /) -> Self: ...
  @overload
  def add_transient[T](self, service_type: type[T], /, *, factory: Factory[T]) -> Self: ...
  def add_transient[T](self, service_type, implementation_type=None, /, *, factory=None) -> Self: ...
  def build_service_provider(self) -> ServiceProvider: ...
```

State is a single insertion-ordered `dict[type, Registration]`; re-registering a key overwrites it in place, giving
"last registration wins" while keeping the original insertion position. Insertion order is what makes validation order
deterministic (the spec says callers must not depend on it, but the implementation should still be reproducible).

`add_transient` validates in this order, raising `RegistrationError` with a message naming the offending argument:

1. `implementation_type is not None and factory is not None` → both supplied.
2. `not isinstance(service_type, type)` → not a class. This rejects `"logger"`, instances, functions, and `list[int]`
   (a `types.GenericAlias`, which is not a `type`) for free.
3. `service_type is ServiceProvider` → the implicit registration cannot be overridden, in any of the three shapes.
4. Factory shape: `not callable(factory)` → reject; `inspect.iscoroutinefunction(factory)` → reject. Store a
   `FactoryRegistration`.
5. Two-argument shape: `not isinstance(implementation_type, type)` → reject; `is_abstract(implementation_type)` →
   reject. Store a `TypeRegistration`.
6. One-argument shape: `is_abstract(service_type)` → reject (it stands as its own implementation). Store a
   `TypeRegistration(service_type)`.

Then `return self`, unconditionally, for the fluent chaining `main.py` relies on
(`services.add_transient(Repository).add_transient(ReportBuilder)`).

Nothing here inspects constructors, and nothing checks that `implementation_type` conforms to `service_type` —
structurally or nominally. `add_transient(AbstractStore, Unrelated)` must register cleanly.

`build_service_provider` takes a **snapshot** (`dict(self._registrations)`), validates it, and constructs a
`ServiceProvider` over the validated plan. The collection is never frozen and can be built repeatedly; each provider
owns its own snapshot, so later mutation of the collection cannot reach it.

### 6. `src/fastdi/_validation.py` (new)

The build-time graph walk, kept out of `_collection.py` so it can be unit-tested and later reused by the
lifetime specs.

```python
@dataclass(frozen=True, slots=True)
class Dependency:
  parameter_name: str
  service_type: type
  positional_only: bool


@dataclass(frozen=True, slots=True)
class TypePlan:
  implementation_type: type
  dependencies: tuple[Dependency, ...]


@dataclass(frozen=True, slots=True)
class FactoryPlan:
  factory: Factory[Any]


type ResolutionPlan = TypePlan | FactoryPlan


def build_plan(registrations: Mapping[type, Registration], /) -> dict[type, ResolutionPlan]: ...
```

Doing the inference once at build time and storing the result means resolution is a plan walk with no `inspect` calls
on the hot path, and it is what makes the spec's guarantee — "a provider that was successfully built can never fail
resolution for a graph-shaped reason" — structurally true rather than merely tested.

`build_plan` iterates registrations in insertion order and, for each, runs a depth-first walk:

- A `FactoryRegistration` becomes a `FactoryPlan` and is a **leaf**. Do not inspect the callable, do not recurse, do not
  extend the cycle stack through it. This is the spec's "factory registrations are opaque to validation", and it is
  what makes a cycle routed through a factory legal (and a factory's own missing dependency a resolve-time
  `ServiceNotRegisteredError`).
- A `TypeRegistration` calls `constructor_parameters(implementation_type)` and classifies each parameter:
  - annotation is `ServiceProvider` → a `Dependency` on `ServiceProvider`; do not recurse (it's the implicit
    self-registration, always satisfiable, never part of a cycle).
  - annotation is a key in `registrations` → a `Dependency`; recurse into that key.
  - annotation is unregistered (or `None`) but `has_default` → **omit** it from `dependencies` entirely, so resolution
    never passes it and the constructor's own default applies. Covers both "not registered, has a default" and "no
    annotation at all, has a default".
  - annotation is unregistered (or `None`) with no default →
    `MissingDependencyError(service_type, implementation_type, parameter_name, annotation)`. `annotation` is already
    `None` for the unannotated case, which is exactly the documented `parameter_type=None`.
- Cycle detection uses a `list[type]` stack of _service types_ currently being walked. On entering a service type
  already on the stack, raise `CircularDependencyError` with the chain sliced from its first occurrence to the end plus
  the repeated type appended — giving `(Alpha, Beta, Alpha)` for the spec's example and `(A, A)` for direct
  self-dependency.
- Memoize completed service types so a diamond is validated once, not exponentially. Memoization is keyed on
  service type and must be recorded only _after_ a successful walk.

`MissingDependencyError.service_type` is the registration key whose constructor could not be satisfied — i.e. the key
currently being walked, not the top-level entry point that led there.

### 7. `src/fastdi/__init__.py` (edit)

Keep the existing docstring; add re-exports and an explicit `__all__` naming exactly the public surface:
`ServiceCollection`, `ServiceProvider`, `Factory`, `FastDIError`, `RegistrationError`, `ServiceNotRegisteredError`,
`MissingDependencyError`, `CircularDependencyError`. The spec says "all five are exported from `fastdi`" for the
exceptions and "everything below is exported from the top-level `fastdi` package" for the rest.

## `./tests/` additions

The spec suite covers the public API end-to-end on happy paths only. These cover what it doesn't reach. Each file gets
its own local fixture classes — do not import from `specs/`, which would couple the framework suite to a spec's toy app.

### `tests/test_registration.py`

- Each of the three shapes registers and resolves: self-registration, `(ServiceType, Impl)`, `(ServiceType, factory=)`.
- `add_transient` returns the _same_ collection object (`is`), and a chain of three calls registers all three.
- `RegistrationError` when `implementation_type` **and** `factory` are both supplied.
- `RegistrationError` for a non-class `service_type`, parametrized over `"logger"`, `list[int]`, `42`, a module-level
  function, and an instance of a class.
- `RegistrationError` for a non-class `implementation_type`, parametrized similarly.
- `RegistrationError` for an abstract instantiation target: an ABC with an abstract method in the one-argument form; a
  `Protocol` in the one-argument form; the same two as `implementation_type` in the two-argument form; a
  `runtime_checkable` Protocol; an ABC subclass that still leaves an abstract method unimplemented.
- **No** error for an abstract `service_type` paired with a concrete `implementation_type`, and none for an abstract
  `service_type` paired with a `factory` — the normal Protocol/ABC case.
- An ABC with _no_ abstract methods is instantiable, so the one-argument form must be accepted.
- `RegistrationError` for a non-callable `factory` (e.g. `factory=42`), and for an `async def` factory. A plain `def`
  factory that _returns_ a coroutine object is accepted — the spec calls this limit out explicitly, so pin it.
- `RegistrationError` for `add_transient(ServiceProvider)`, `add_transient(ServiceProvider, SomeImpl)` and
  `add_transient(ServiceProvider, factory=...)`.
- Last registration wins, across all transitions: type→type, type→factory, factory→type. Assert the _resolved_ result
  changes, not just internal state.
- No conformance checking: `add_transient(AbstractStore, Unrelated)` where `Unrelated` neither subclasses the ABC nor
  satisfies the Protocol registers, builds and resolves to an `Unrelated`.

### `tests/test_build.py`

- Snapshot semantics: register `A`, build, then register `B` on the same collection — the first provider still returns
  `None` for `B`; a second build sees `B`. Mutating a registration for `A` after building does not change the first
  provider's `A`.
- Building the same collection twice yields two distinct providers, each self-resolving to itself.
- Validation is eager: a class with an unsatisfiable constructor raises `MissingDependencyError` from
  `build_service_provider`, and a module-level instantiation counter proves _nothing_ was constructed.
- `MissingDependencyError` attributes are all correct, including the case where the failing class is registered under a
  different `service_type` (assert `service_type is TheKey` and `implementation_type is TheImpl`), and the case where
  the failure is nested two levels deep (the error names the _inner_ registration, not the entry point).
- `parameter_type is None` for a wholly unannotated, defaultless parameter.
- `CircularDependencyError.chain` for: a two-cycle → `(Alpha, Beta, Alpha)`; a direct self-cycle → `(A, A)`; a
  three-cycle → `(A, B, C, A)`; a cycle reached only from a non-cyclic root, which must still be detected.
- A diamond (`Top` → `Left`, `Right`, both → `Leaf`) builds without error and without exploding — sanity check on
  memoization.
- Factory opacity, three ways: a cycle running through a factory builds successfully; a factory whose lambda resolves an
  unregistered type builds successfully and raises `ServiceNotRegisteredError` only when resolved; a factory
  registration is never inspected, so registering a factory for a type whose class has an unsatisfiable constructor
  still builds.
- A collection with multiple independent problems raises exactly one error, and it is a `FastDIError` — do not assert
  _which_, per the spec's explicit non-guarantee.
- Every FastDI exception subclasses `FastDIError`, and `FastDIError` subclasses `Exception`.

### `tests/test_constructor_inference.py`

- A class inheriting `object.__init__` resolves with no arguments.
- `*args` and `**kwargs` are skipped and never passed (assert the receiving class saw empty `args`/`kwargs`).
- A positional-only dependency is passed positionally; a keyword-only dependency is passed by keyword; a constructor
  mixing positional-only, normal and keyword-only dependencies gets all three right.
- `__init__` inherited through the MRO is injected — including two levels up, and including a subclass that overrides
  `__init__` (its own signature wins, not the base's).
- A constructor annotating a class defined _later_ in the module resolves (PEP 649), as does an explicitly quoted
  annotation.
- `Annotated[Dep, "meta"]` injects a `Dep`; `Annotated[Dep, "meta"]` with the metadata differing between two
  parameters still resolves both to the same registration (metadata is ignored in this spec).
- Unregistered parameter with a default → default used, not injected. Unannotated parameter with a default → default
  used.
- A registered type that _also_ has a default is still injected (registration wins over the default).
- `Dep | None = None` is **not** injected even though `Dep` is registered; the parameter is `None`. Same for
  `Optional[Dep]`.
- A `ServiceProvider`-annotated parameter is injected with the resolving provider, including when it is the only
  parameter and when it is nested two levels down.

### `tests/test_resolution.py`

- `get_service` returns `None` for an unregistered type; `get_required_service` raises `ServiceNotRegisteredError` with
  `.service_type` set to the requested type.
- `get_service` does **not** swallow a factory's exception — a factory raising `ValueError` propagates out of
  `get_service`, and a factory raising `ServiceNotRegisteredError` propagates rather than becoming `None`. This is the
  single most likely implementation shortcut to get wrong, so test both.
- Transient: two `get_required_service(T)` calls return distinct objects; `get_service` and `get_required_service`
  return distinct objects; the spec's `Report(header: Banner, footer: Banner)` diamond yields
  `report.header is not report.footer`.
- A three-level chain constructs bottom-up: assert an instantiation-order log reads leaf-first.
- The factory receives the provider itself (`factory_arg is provider`), and a factory that pulls another service out of
  that provider works.
- A factory's return value is returned as-is, even when it is not an instance of `service_type` (e.g. a factory
  registered for a Protocol returning an `int`).
- `get_service(ServiceProvider)` and `get_required_service(ServiceProvider)` both return the provider; two providers
  built from the same collection each return _themselves_.

### `tests/test_public_api.py`

- `fastdi.__all__` contains exactly the eight documented names, and each is importable from `fastdi` directly.

## Verification

Standard verification only, plus: run the spec's example by hand once —
`pixi run -- uv run specs/constructor-injection/src/constructor_injection/main.py` — and confirm the last two printed
lines report `False` for "the builder's clock and the greeter's clock are the same object" (transient means two clocks)
and `True` for "the builder was handed the provider that built it".

## Deviations

- Ruff's `UP037` (Python 3.14 / PEP 649 lazy annotations) insisted on unquoting the `Factory[Any]` field
  annotations in `_registrations.py` and `_validation.py` that the plan specified as quoted strings. Verified the
  package still imports cleanly with unquoted annotations (dataclass never triggers eager evaluation of the lazy
  `__annotations__`), so left them unquoted per ruff rather than fighting the linter.
