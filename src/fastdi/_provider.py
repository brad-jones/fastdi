"""The immutable, validated container that resolves services."""

from collections.abc import Callable, Mapping
from typing import Any

from ._errors import ServiceNotRegisteredError
from ._registrations import Lifetime
from ._validation import FactoryPlan, InstancePlan, ResolutionPlan, TypePlan

type Factory[T] = Callable[["ServiceProvider"], T]


class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def __init__(self, plan: Mapping[type, ResolutionPlan], /, *, singletons: dict[type, Any] | None = None) -> None:
    """Wrap an already-validated resolution plan.

    Not a supported construction path for callers: build a `ServiceProvider` via
    `ServiceCollection.build_service_provider` instead. `singletons`, when given, is an existing singleton cache
    to share — used internally by `create_scope` so a scope's singletons stay identical to its parent's.
    """
    self._plan = plan
    self._singletons: dict[type, Any] = singletons if singletons is not None else {}
    self._scoped: dict[type, Any] = {}

  def get_service[T](self, service_type: type[T], /) -> T | None:
    """Resolve `service_type`, or return `None` if nothing is registered for it.

    Args:
      service_type: The type to resolve.

    Returns:
      An instance of `service_type`, or `None` if it has no registration. Depending on how
      `service_type` was registered, the instance may be freshly constructed or a cached one shared
      across calls. Any other exception raised while resolving a registered factory or constructor
      propagates unchanged.
    """
    if service_type is ServiceProvider:
      return self  # type: ignore[return-value]

    resolution = self._plan.get(service_type)
    if resolution is None:
      return None

    return self._resolve(service_type, resolution)

  def get_required_service[T](self, service_type: type[T], /) -> T:
    """Resolve `service_type`, raising if nothing is registered for it.

    Args:
      service_type: The type to resolve.

    Returns:
      An instance of `service_type`. Depending on how `service_type` was registered, the instance may
      be freshly constructed or a cached one shared across calls.

    Raises:
      ServiceNotRegisteredError: If `service_type` has no registration.
    """
    if service_type is ServiceProvider:
      return self  # type: ignore[return-value]

    resolution = self._plan.get(service_type)
    if resolution is None:
      raise ServiceNotRegisteredError(service_type)

    return self._resolve(service_type, resolution)

  def create_scope(self) -> ServiceScope:
    """Create a new `ServiceScope` sharing this provider's singletons but with its own scoped-service cache.

    Returns:
      A `ServiceScope` whose `service_provider` resolves scoped services independently of this provider (and of
      any other scope), while singleton-registered services remain shared with it.
    """
    return ServiceScope(ServiceProvider(self._plan, singletons=self._singletons))

  def _resolve(self, service_type: type, resolution: ResolutionPlan) -> Any:
    if isinstance(resolution, InstancePlan):
      return resolution.instance

    if resolution.lifetime is Lifetime.SINGLETON:
      cache = self._singletons
    elif resolution.lifetime is Lifetime.SCOPED:
      cache = self._scoped
    else:
      cache = None

    if cache is not None and service_type in cache:
      return cache[service_type]

    instance = resolution.factory(self) if isinstance(resolution, FactoryPlan) else self._build(resolution)

    if cache is not None:
      cache[service_type] = instance

    return instance

  def _build(self, plan: TypePlan) -> Any:
    positional: list[Any] = []
    keyword: dict[str, Any] = {}

    for dependency in plan.dependencies:
      value = self.get_required_service(dependency.service_type)
      if dependency.positional_only:
        positional.append(value)
      else:
        keyword[dependency.parameter_name] = value

    return plan.implementation_type(*positional, **keyword)


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
