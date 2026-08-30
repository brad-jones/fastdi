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
    snapshot = dict(self._registrations)
    plan = build_plan(snapshot)
    return ServiceProvider(plan)
