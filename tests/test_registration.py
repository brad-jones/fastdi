"""Unit tests for `ServiceCollection.add_transient`'s registration rules."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import pytest

from fastdi import RegistrationError, ServiceCollection, ServiceProvider


def a_function() -> None: ...


class Concrete:
  """No dependencies of its own."""


class AbstractStore(ABC):
  @abstractmethod
  def save(self) -> None: ...


class ConcreteStore(AbstractStore):
  def save(self) -> None: ...


class Unrelated:
  """Neither subclasses `AbstractStore` nor satisfies its protocol equivalent."""


@runtime_checkable
class StoreProtocol(Protocol):
  def save(self) -> None: ...


class NonAbstractABC(ABC):
  """An ABC with no abstract methods, so it is instantiable."""


class PartiallyImplementedStore(AbstractStore):
  """Still leaves `save` unimplemented via a further abstract method."""

  @abstractmethod
  def flush(self) -> None: ...


def test_self_registration_resolves_to_itself() -> None:
  services = ServiceCollection().add_transient(Concrete)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_two_argument_registration_resolves_to_the_implementation() -> None:
  services = ServiceCollection().add_transient(AbstractStore, ConcreteStore)

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert isinstance(resolved, ConcreteStore)


def test_factory_registration_resolves_to_the_factorys_return_value() -> None:
  services = ServiceCollection().add_transient(Concrete, factory=lambda _: Concrete())

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_add_transient_returns_the_same_collection() -> None:
  services = ServiceCollection()

  result = services.add_transient(Concrete)

  assert result is services


def test_a_chain_of_three_registrations_registers_all_three() -> None:
  class A:
    pass

  class B:
    pass

  class C:
    pass

  services = ServiceCollection().add_transient(A).add_transient(B).add_transient(C)
  provider = services.build_service_provider()

  assert isinstance(provider.get_required_service(A), A)
  assert isinstance(provider.get_required_service(B), B)
  assert isinstance(provider.get_required_service(C), C)


def test_both_implementation_type_and_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(Concrete, Concrete, factory=lambda _: Concrete())  # type: ignore[call-overload]


@pytest.mark.parametrize(
  "bad_service_type",
  ["logger", list[int], 42, a_function, Concrete()],
)
def test_non_class_service_type_raises(bad_service_type: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(bad_service_type)  # type: ignore[arg-type]


@pytest.mark.parametrize(
  "bad_implementation_type",
  ["logger", list[int], 42, a_function, Concrete()],
)
def test_non_class_implementation_type_raises(bad_implementation_type: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(Concrete, bad_implementation_type)  # type: ignore[arg-type]


def test_abstract_service_type_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(AbstractStore)


def test_protocol_service_type_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(StoreProtocol)


def test_abstract_implementation_type_in_two_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(AbstractStore, AbstractStore)


def test_protocol_implementation_type_in_two_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(StoreProtocol, StoreProtocol)


def test_runtime_checkable_protocol_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(StoreProtocol)


def test_abc_subclass_still_missing_an_abstract_method_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(PartiallyImplementedStore)


def test_abstract_service_type_with_concrete_implementation_is_fine() -> None:
  services = ServiceCollection().add_transient(AbstractStore, ConcreteStore)

  services.build_service_provider()


def test_abstract_service_type_with_factory_is_fine() -> None:
  services = ServiceCollection().add_transient(AbstractStore, factory=lambda _: ConcreteStore())

  services.build_service_provider()


def test_non_abstract_abc_is_instantiable_in_one_argument_form() -> None:
  services = ServiceCollection().add_transient(NonAbstractABC)

  resolved = services.build_service_provider().get_required_service(NonAbstractABC)

  assert isinstance(resolved, NonAbstractABC)


def test_non_callable_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_transient(Concrete, factory=42)  # type: ignore[arg-type]


def test_async_def_factory_raises() -> None:
  services = ServiceCollection()

  async def factory(_: ServiceProvider) -> Concrete:
    return Concrete()

  with pytest.raises(RegistrationError):
    services.add_transient(Concrete, factory=factory)


def test_a_plain_def_factory_returning_a_coroutine_is_accepted() -> None:
  async def coroutine() -> Concrete:
    return Concrete()

  def factory(_: ServiceProvider) -> object:
    return coroutine()

  services = ServiceCollection().add_transient(Concrete, factory=factory)  # type: ignore[arg-type]

  services.build_service_provider()


@pytest.mark.parametrize(
  "register",
  [
    lambda services: services.add_transient(ServiceProvider),
    lambda services: services.add_transient(ServiceProvider, Concrete),  # type: ignore[arg-type]
    lambda services: services.add_transient(ServiceProvider, factory=lambda _: Concrete()),  # type: ignore[arg-type]
  ],
)
def test_registering_service_provider_raises(register: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    register(services)  # type: ignore[operator]


def test_last_registration_wins_type_to_factory() -> None:
  services = ServiceCollection().add_transient(Concrete)
  services.add_transient(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert resolved == "not a concrete instance"


def test_last_registration_wins_factory_to_type() -> None:
  services = ServiceCollection().add_transient(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]
  services.add_transient(Concrete)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_last_registration_wins_type_to_type() -> None:
  services = ServiceCollection().add_transient(AbstractStore, ConcreteStore)
  services.add_transient(AbstractStore, NonAbstractABC)  # type: ignore[arg-type]

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert isinstance(resolved, NonAbstractABC)


def test_no_conformance_checking() -> None:
  services = ServiceCollection().add_transient(AbstractStore, Unrelated)  # type: ignore[arg-type]

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert isinstance(resolved, Unrelated)
