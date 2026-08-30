"""Unit tests for `ServiceCollection.add_singleton`'s registration rules."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import pytest

from fastdi import RegistrationError, ServiceCollection, ServiceProvider


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


def test_bare_class_registration_resolves_to_itself() -> None:
  services = ServiceCollection().add_singleton(Concrete)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_bare_instance_registration_resolves_under_its_own_runtime_type() -> None:
  instance = Concrete()
  services = ServiceCollection().add_singleton(instance)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert resolved is instance


def test_two_argument_type_registration_resolves_to_the_implementation() -> None:
  services = ServiceCollection().add_singleton(AbstractStore, ConcreteStore)

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert isinstance(resolved, ConcreteStore)


def test_two_argument_instance_registration_resolves_to_the_exact_instance() -> None:
  instance = ConcreteStore()
  services = ServiceCollection().add_singleton(AbstractStore, instance)

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert resolved is instance


def test_factory_registration_resolves_to_the_factorys_return_value() -> None:
  services = ServiceCollection().add_singleton(Concrete, factory=lambda _: Concrete())

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_add_singleton_returns_the_same_collection() -> None:
  services = ServiceCollection()

  result = services.add_singleton(Concrete)

  assert result is services


def test_add_singleton_chains_with_add_transient() -> None:
  class Other:
    pass

  services = ServiceCollection().add_singleton(Concrete).add_transient(Other)
  provider = services.build_service_provider()

  assert isinstance(provider.get_required_service(Concrete), Concrete)
  assert isinstance(provider.get_required_service(Other), Other)


def test_both_second_argument_and_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(Concrete, Concrete, factory=lambda _: Concrete())  # type: ignore[call-overload]


def test_non_class_first_argument_with_second_argument_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(Concrete(), Concrete())  # type: ignore[call-overload]


def test_non_class_first_argument_with_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(Concrete(), factory=lambda _: Concrete())  # type: ignore[call-overload]


def test_abstract_service_type_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(AbstractStore)


def test_protocol_service_type_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(StoreProtocol)


def test_abstract_implementation_type_in_two_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(AbstractStore, AbstractStore)


def test_protocol_implementation_type_in_two_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(StoreProtocol, StoreProtocol)


def test_registering_an_instance_under_an_abstract_key_is_fine() -> None:
  instance = ConcreteStore()
  services = ServiceCollection().add_singleton(AbstractStore, instance)

  services.build_service_provider()


def test_non_callable_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_singleton(Concrete, factory=42)  # type: ignore[arg-type]


def test_async_def_factory_raises() -> None:
  services = ServiceCollection()

  async def factory(_: ServiceProvider) -> Concrete:
    return Concrete()

  with pytest.raises(RegistrationError):
    services.add_singleton(Concrete, factory=factory)


def test_a_plain_def_factory_returning_a_coroutine_is_accepted() -> None:
  async def coroutine() -> Concrete:
    return Concrete()

  def factory(_: ServiceProvider) -> object:
    return coroutine()

  services = ServiceCollection().add_singleton(Concrete, factory=factory)  # type: ignore[arg-type]

  services.build_service_provider()


@pytest.mark.parametrize(
  "register",
  [
    lambda services: services.add_singleton(ServiceProvider),
    lambda services: services.add_singleton(ServiceProvider, Concrete),  # type: ignore[arg-type]
    lambda services: services.add_singleton(ServiceProvider, factory=lambda _: Concrete()),  # type: ignore[arg-type]
  ],
)
def test_registering_service_provider_raises(register: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    register(services)  # type: ignore[operator]


def test_registering_a_service_provider_instance_raises() -> None:
  services = ServiceCollection()
  provider = ServiceCollection().build_service_provider()

  with pytest.raises(RegistrationError):
    services.add_singleton(provider)


def test_bare_none_registers_under_nonetype_and_resolves_to_none() -> None:
  services = ServiceCollection().add_singleton(None)

  resolved = services.build_service_provider().get_required_service(type(None))

  assert resolved is None


def test_last_registration_wins_transient_to_singleton() -> None:
  services = ServiceCollection().add_transient(Concrete)
  services.add_singleton(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]

  provider = services.build_service_provider()
  first = provider.get_required_service(Concrete)
  second = provider.get_required_service(Concrete)

  assert first == "not a concrete instance"
  assert first is second


def test_last_registration_wins_singleton_to_transient() -> None:
  services = ServiceCollection().add_singleton(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]
  services.add_transient(Concrete)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_last_registration_wins_singleton_type_to_singleton_instance() -> None:
  instance = ConcreteStore()
  services = ServiceCollection().add_singleton(AbstractStore, ConcreteStore)
  services.add_singleton(AbstractStore, instance)

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert resolved is instance


def test_last_registration_wins_singleton_instance_to_singleton_factory() -> None:
  services = ServiceCollection().add_singleton(Concrete, Concrete())
  services.add_singleton(Concrete, factory=lambda _: "swapped to a factory")  # type: ignore[arg-type]

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert resolved == "swapped to a factory"


@pytest.mark.parametrize("falsy_instance", [0, "", False])
def test_bare_falsy_instances_round_trip_correctly(falsy_instance: object) -> None:
  services = ServiceCollection().add_singleton(falsy_instance)

  resolved = services.build_service_provider().get_required_service(type(falsy_instance))

  assert resolved is falsy_instance


@pytest.mark.parametrize("falsy_instance", [0, "", False])
def test_two_argument_falsy_instances_round_trip_correctly(falsy_instance: object) -> None:
  class Key:
    pass

  services = ServiceCollection().add_singleton(Key, falsy_instance)

  resolved = services.build_service_provider().get_required_service(Key)

  assert resolved is falsy_instance


def test_no_conformance_checking() -> None:
  instance = Unrelated()
  services = ServiceCollection().add_singleton(AbstractStore, instance)

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert resolved is instance


def test_caching_is_keyed_by_service_type_not_implementation_class() -> None:
  class KeyA:
    pass

  class KeyB:
    pass

  services = ServiceCollection().add_singleton(KeyA, Concrete).add_singleton(KeyB, Concrete)
  provider = services.build_service_provider()

  assert provider.get_required_service(KeyA) is not provider.get_required_service(KeyB)
