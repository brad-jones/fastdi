"""Internal record types describing what a `ServiceCollection` has registered."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from ._provider import Factory


class Lifetime(Enum):
  """How long a resolved instance lives, relative to the `ServiceProvider` that resolved it."""

  TRANSIENT = auto()
  SINGLETON = auto()


@dataclass(frozen=True, slots=True)
class TypeRegistration:
  implementation_type: type
  lifetime: Lifetime


@dataclass(frozen=True, slots=True)
class FactoryRegistration:
  factory: Factory[Any]
  lifetime: Lifetime


@dataclass(frozen=True, slots=True)
class InstanceRegistration:
  instance: Any


type Registration = TypeRegistration | FactoryRegistration | InstanceRegistration
