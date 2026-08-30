"""Unit tests for `build_service_provider`'s eager validation."""

import pytest

from fastdi import (
  CircularDependencyError,
  FastDIError,
  MissingDependencyError,
  RegistrationError,
  ServiceCollection,
  ServiceNotRegisteredError,
)


class Leaf:
  """No dependencies."""


class NeedsUnregistered:
  def __init__(self, missing: Unregistered) -> None:
    self.missing = missing


class Unregistered:
  """Never registered anywhere."""


def test_snapshot_semantics_first_provider_unaffected_by_later_registration() -> None:
  class A:
    pass

  class B:
    pass

  services = ServiceCollection().add_transient(A)
  first_provider = services.build_service_provider()

  services.add_transient(B)

  assert first_provider.get_service(B) is None

  second_provider = services.build_service_provider()
  assert second_provider.get_service(B) is not None


def test_snapshot_semantics_mutating_a_registration_does_not_affect_built_provider() -> None:
  class A:
    pass

  class AlternateA:
    pass

  services = ServiceCollection().add_transient(A)
  first_provider = services.build_service_provider()

  services.add_transient(A, AlternateA)

  assert isinstance(first_provider.get_required_service(A), A)


def test_building_twice_yields_two_distinct_self_resolving_providers() -> None:
  services = ServiceCollection()

  first = services.build_service_provider()
  second = services.build_service_provider()

  assert first is not second
  assert first.get_required_service(type(first)) is first
  assert second.get_required_service(type(second)) is second


def test_validation_is_eager_and_nothing_is_constructed() -> None:
  instantiation_count = 0

  class Counted:
    def __init__(self, missing: Unregistered) -> None:
      nonlocal instantiation_count
      instantiation_count += 1
      self.missing = missing

  services = ServiceCollection().add_transient(Counted)

  with pytest.raises(MissingDependencyError):
    services.build_service_provider()

  assert instantiation_count == 0


def test_missing_dependency_error_attributes_when_registered_under_a_different_key() -> None:
  class TheImpl:
    def __init__(self, missing: Unregistered) -> None:
      self.missing = missing

  class TheKey:
    pass

  services = ServiceCollection().add_transient(TheKey, TheImpl)

  with pytest.raises(MissingDependencyError) as excinfo:
    services.build_service_provider()

  error = excinfo.value
  assert error.service_type is TheKey
  assert error.implementation_type is TheImpl
  assert error.parameter_name == "missing"
  assert error.parameter_type is Unregistered


def test_missing_dependency_error_names_the_inner_registration_not_the_entry_point() -> None:
  class Inner:
    def __init__(self, missing: Unregistered) -> None:
      self.missing = missing

  class Middle:
    def __init__(self, inner: Inner) -> None:
      self.inner = inner

  class Top:
    def __init__(self, middle: Middle) -> None:
      self.middle = middle

  services = ServiceCollection().add_transient(Top).add_transient(Middle).add_transient(Inner)

  with pytest.raises(MissingDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.service_type is Inner


def test_parameter_type_is_none_for_a_wholly_unannotated_defaultless_parameter() -> None:
  class Unannotated:
    def __init__(self, thing) -> None:
      self.thing = thing

  services = ServiceCollection().add_transient(Unannotated)

  with pytest.raises(MissingDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.parameter_type is None


def test_circular_dependency_two_cycle() -> None:
  class Alpha:
    def __init__(self, beta: Beta) -> None:
      self.beta = beta

  class Beta:
    def __init__(self, alpha: Alpha) -> None:
      self.alpha = alpha

  services = ServiceCollection().add_transient(Alpha).add_transient(Beta)

  with pytest.raises(CircularDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.chain == (Alpha, Beta, Alpha)


def test_circular_dependency_direct_self_cycle() -> None:
  class A:
    def __init__(self, a: A) -> None:
      self.a = a

  services = ServiceCollection().add_transient(A)

  with pytest.raises(CircularDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.chain == (A, A)


def test_circular_dependency_three_cycle() -> None:
  class A:
    def __init__(self, b: B) -> None:
      self.b = b

  class B:
    def __init__(self, c: C) -> None:
      self.c = c

  class C:
    def __init__(self, a: A) -> None:
      self.a = a

  services = ServiceCollection().add_transient(A).add_transient(B).add_transient(C)

  with pytest.raises(CircularDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.chain == (A, B, C, A)


def test_circular_dependency_reached_only_from_a_non_cyclic_root() -> None:
  class Alpha:
    def __init__(self, beta: Beta) -> None:
      self.beta = beta

  class Beta:
    def __init__(self, alpha: Alpha) -> None:
      self.alpha = alpha

  class Root:
    """Registered but unrelated to the cycle; the cycle must still be found."""

  services = ServiceCollection().add_transient(Root).add_transient(Alpha).add_transient(Beta)

  with pytest.raises(CircularDependencyError):
    services.build_service_provider()


def test_diamond_builds_without_error() -> None:
  class Leaf2:
    pass

  class Left:
    def __init__(self, leaf: Leaf2) -> None:
      self.leaf = leaf

  class Right:
    def __init__(self, leaf: Leaf2) -> None:
      self.leaf = leaf

  class Top:
    def __init__(self, left: Left, right: Right) -> None:
      self.left = left
      self.right = right

  services = ServiceCollection().add_transient(Leaf2).add_transient(Left).add_transient(Right).add_transient(Top)

  services.build_service_provider()


def test_a_cycle_through_a_factory_builds_successfully() -> None:
  class Alpha:
    def __init__(self, beta: Beta) -> None:
      self.beta = beta

  class Beta:
    def __init__(self, alpha: Alpha) -> None:
      self.alpha = alpha

  services = ServiceCollection().add_transient(Alpha, factory=lambda p: Alpha(p.get_required_service(Beta)))
  services.add_transient(Beta)

  services.build_service_provider()


def test_a_factory_resolving_an_unregistered_type_builds_but_fails_at_resolve_time() -> None:
  services = ServiceCollection().add_transient(Leaf, factory=lambda p: p.get_required_service(Unregistered))

  provider = services.build_service_provider()

  with pytest.raises(ServiceNotRegisteredError):
    provider.get_required_service(Leaf)


def test_a_factory_registration_is_never_inspected() -> None:
  services = ServiceCollection().add_transient(NeedsUnregistered, factory=lambda _: NeedsUnregistered(Unregistered()))

  services.build_service_provider()


def test_multiple_independent_problems_raise_exactly_one_fastdi_error() -> None:
  class BadOne:
    def __init__(self, missing: Unregistered) -> None:
      self.missing = missing

  class BadTwo:
    def __init__(self, missing: Unregistered) -> None:
      self.missing = missing

  services = ServiceCollection().add_transient(BadOne).add_transient(BadTwo)

  with pytest.raises(FastDIError):
    services.build_service_provider()


def test_every_fastdi_exception_subclasses_fastdi_error() -> None:
  assert issubclass(MissingDependencyError, FastDIError)
  assert issubclass(CircularDependencyError, FastDIError)
  assert issubclass(ServiceNotRegisteredError, FastDIError)
  assert issubclass(RegistrationError, FastDIError)
  assert issubclass(FastDIError, Exception)
