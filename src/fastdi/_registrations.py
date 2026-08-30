"""Internal record types describing what a `ServiceCollection` has registered."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from ._provider import Factory


@dataclass(frozen=True, slots=True)
class TypeRegistration:
  implementation_type: type


@dataclass(frozen=True, slots=True)
class FactoryRegistration:
  factory: Factory[Any]


type Registration = TypeRegistration | FactoryRegistration
