"""FastDI's exception hierarchy."""


class FastDIError(Exception):
  """Base class for every error FastDI raises."""


class RegistrationError(FastDIError):
  """A registration call was malformed. Raised by `add_transient`."""


class ServiceNotRegisteredError(FastDIError):
  """`get_required_service` was called with an unregistered service type."""

  service_type: type

  def __init__(self, service_type: type, /) -> None:
    super().__init__(f"No registration exists for {service_type.__name__!r}.")
    self.service_type = service_type


class MissingDependencyError(FastDIError):
  """A constructor parameter cannot be satisfied. Raised by `build_service_provider`."""

  service_type: type
  implementation_type: type
  parameter_name: str
  parameter_type: type | None

  def __init__(
    self,
    service_type: type,
    implementation_type: type,
    parameter_name: str,
    parameter_type: type | None,
    /,
  ) -> None:
    type_description = "no annotation" if parameter_type is None else parameter_type.__name__
    super().__init__(f"{implementation_type.__name__}.__init__ parameter {parameter_name!r} ({type_description}) has no registration and no default, while resolving {service_type.__name__!r}.")
    self.service_type = service_type
    self.implementation_type = implementation_type
    self.parameter_name = parameter_name
    self.parameter_type = parameter_type


class CircularDependencyError(FastDIError):
  """The registration graph contains a cycle. Raised by `build_service_provider`."""

  chain: tuple[type, ...]

  def __init__(self, chain: tuple[type, ...], /) -> None:
    rendered = " -> ".join(service_type.__name__ for service_type in chain)
    super().__init__(f"Circular dependency detected: {rendered}")
    self.chain = chain
