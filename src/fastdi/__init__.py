"""FastDI: an IoC container for Python, inspired by Microsoft.Extensions.DependencyInjection."""

from ._collection import ServiceCollection
from ._errors import (
  CircularDependencyError,
  FastDIError,
  MissingDependencyError,
  RegistrationError,
  ServiceNotRegisteredError,
)
from ._provider import Factory, ServiceProvider

__all__ = [
  "CircularDependencyError",
  "Factory",
  "FastDIError",
  "MissingDependencyError",
  "RegistrationError",
  "ServiceCollection",
  "ServiceNotRegisteredError",
  "ServiceProvider",
]
