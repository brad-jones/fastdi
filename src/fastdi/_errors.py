"""FastDI's exception hierarchy."""


class FastDIError(Exception):
  """Base class for every error FastDI raises."""


class RegistrationError(FastDIError):
  """A registration call was malformed. Raised by `add_transient`."""


class ServiceNotRegisteredError(FastDIError):
  """`get_required_service` was called with an unregistered service type.

  Attributes:
    service_type: The type that was requested but has no registration.
  """

  service_type: type

  def __init__(self, service_type: type, /) -> None:
    super().__init__(f"No registration exists for {service_type.__name__!r}.")
    self.service_type = service_type


class MissingDependencyError(FastDIError):
  """A constructor parameter cannot be satisfied. Raised by `build_service_provider`.

  Attributes:
    service_type: The service whose constructor could not be satisfied.
    implementation_type: The class whose `__init__` was being inspected.
    parameter_name: The name of the unsatisfiable parameter.
    parameter_type: The parameter's annotation, or `None` when it carries no annotation.
  """

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
  """The registration graph contains a cycle. Raised by `build_service_provider`.

  Attributes:
    chain: The cycle, with the repeated service type at both ends.
  """

  chain: tuple[type, ...]

  def __init__(self, chain: tuple[type, ...], /) -> None:
    rendered = " -> ".join(service_type.__name__ for service_type in chain)
    super().__init__(f"Circular dependency detected: {rendered}")
    self.chain = chain
