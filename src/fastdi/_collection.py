"""The mutable registry callers build up before constructing a `ServiceProvider`."""

import inspect
from typing import Self, overload

from ._errors import RegistrationError
from ._inspection import is_abstract
from ._provider import Factory, ServiceProvider
from ._registrations import FactoryRegistration, Registration, TypeRegistration
from ._validation import build_plan


class ServiceCollection:
  """A mutable registry of service registrations."""

  def __init__(self) -> None:
    self._registrations: dict[type, Registration] = {}

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
  ) -> Self:
    """Register a transient service, in one of three shapes.

    Called as `add_transient(Impl)` to register a concrete class under itself, as
    `add_transient(ServiceType, Impl)` to register an implementation under a different key (`ServiceType`
    may be a `Protocol`, an ABC, or any other class — it is only ever used as a dictionary key), or as
    `add_transient(ServiceType, factory=...)` to supply a callable that builds the instance from a
    `ServiceProvider`. Every resolution of a transient service produces a brand new instance.

    Args:
      service_type: The type resolutions are looked up under.
      implementation_type: The concrete class to construct, when different from `service_type`.
      factory: A callable that receives the `ServiceProvider` and returns the instance.

    Returns:
      `self`, so calls can be chained.

    Raises:
      RegistrationError: If both `implementation_type` and `factory` are supplied, if `service_type` or
        `implementation_type` is not a class, if the class that would be instantiated is abstract, if
        `factory` is not callable or is an `async def` function, or if `service_type` is
        `ServiceProvider`.
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
      self._registrations[service_type] = FactoryRegistration(factory=factory)
      return self

    if implementation_type is not None:
      if not isinstance(implementation_type, type):
        raise RegistrationError(f"`implementation_type` must be a class, got {implementation_type!r}.")
      if is_abstract(implementation_type):
        raise RegistrationError(f"`implementation_type` {implementation_type.__name__!r} is abstract.")
      self._registrations[service_type] = TypeRegistration(implementation_type=implementation_type)
      return self

    if is_abstract(service_type):
      raise RegistrationError(f"`service_type` {service_type.__name__!r} is abstract.")
    self._registrations[service_type] = TypeRegistration(implementation_type=service_type)
    return self

  def build_service_provider(self) -> ServiceProvider:
    """Take a snapshot of this collection and build a validated `ServiceProvider` over it.

    Later mutation of this collection has no effect on the returned provider, and the collection may be
    built again to produce a second, independent provider. The whole registration graph is validated
    eagerly, before this method returns.

    Returns:
      A `ServiceProvider` whose entire registration graph has already been validated.

    Raises:
      MissingDependencyError: If a constructor parameter cannot be satisfied.
      CircularDependencyError: If the registration graph contains a cycle.
    """
    snapshot = dict(self._registrations)
    plan = build_plan(snapshot)
    return ServiceProvider(plan)
