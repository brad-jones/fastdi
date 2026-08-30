"""The build-time graph walk: turns registrations into a validated resolution plan."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ._errors import CircularDependencyError, MissingDependencyError
from ._inspection import constructor_parameters
from ._registrations import FactoryRegistration, Registration

if TYPE_CHECKING:
  from ._provider import Factory


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


def build_plan(registrations: Mapping[type, Registration], /) -> dict[type, ResolutionPlan]:
  from ._provider import ServiceProvider

  plan: dict[type, ResolutionPlan] = {}
  stack: list[type] = []

  def walk(service_type: type) -> None:
    if service_type in plan:
      return

    registration = registrations[service_type]
    if isinstance(registration, FactoryRegistration):
      plan[service_type] = FactoryPlan(factory=registration.factory)
      return

    if service_type in stack:
      cycle_start = stack.index(service_type)
      raise CircularDependencyError((*stack[cycle_start:], service_type))

    stack.append(service_type)
    try:
      implementation_type = registration.implementation_type
      dependencies: list[Dependency] = []
      for parameter in constructor_parameters(implementation_type):
        annotation = parameter.annotation

        if annotation is ServiceProvider:
          dependencies.append(
            Dependency(
              parameter_name=parameter.name,
              service_type=annotation,
              positional_only=parameter.positional_only,
            )
          )
          continue

        if annotation is not None and annotation in registrations:
          walk(annotation)
          dependencies.append(
            Dependency(
              parameter_name=parameter.name,
              service_type=annotation,
              positional_only=parameter.positional_only,
            )
          )
          continue

        if parameter.has_default:
          continue

        raise MissingDependencyError(service_type, implementation_type, parameter.name, annotation)

      plan[service_type] = TypePlan(implementation_type=implementation_type, dependencies=tuple(dependencies))
    finally:
      stack.pop()

  for service_type in registrations:
    walk(service_type)

  return plan
