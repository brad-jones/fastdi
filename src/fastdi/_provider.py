"""The immutable, validated container that resolves services."""

from collections.abc import Callable, Mapping
from typing import Any

from ._errors import ServiceNotRegisteredError
from ._validation import FactoryPlan, ResolutionPlan, TypePlan

type Factory[T] = Callable[["ServiceProvider"], T]


class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def __init__(self, plan: Mapping[type, ResolutionPlan], /) -> None:
    self._plan = plan

  def get_service[T](self, service_type: type[T], /) -> T | None:
    if service_type is ServiceProvider:
      return self  # type: ignore[return-value]

    resolution = self._plan.get(service_type)
    if resolution is None:
      return None

    return self._resolve(resolution)

  def get_required_service[T](self, service_type: type[T], /) -> T:
    if service_type is ServiceProvider:
      return self  # type: ignore[return-value]

    resolution = self._plan.get(service_type)
    if resolution is None:
      raise ServiceNotRegisteredError(service_type)

    return self._resolve(resolution)

  def _resolve(self, resolution: ResolutionPlan) -> Any:
    if isinstance(resolution, FactoryPlan):
      return resolution.factory(self)

    return self._build(resolution)

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
