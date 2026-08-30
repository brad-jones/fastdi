"""Unit tests for `ServiceCollection.add_scoped`'s registration rules."""

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


def test_self_registration_resolves_to_itself() -> None:
  services = ServiceCollection().add_scoped(Concrete)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_two_argument_registration_resolves_to_the_implementation() -> None:
  services = ServiceCollection().add_scoped(AbstractStore, ConcreteStore)

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert isinstance(resolved, ConcreteStore)


def test_factory_registration_resolves_to_the_factorys_return_value() -> None:
  services = ServiceCollection().add_scoped(Concrete, factory=lambda _: Concrete())

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_add_scoped_returns_the_same_collection() -> None:
  services = ServiceCollection()

  result = services.add_scoped(Concrete)

  assert result is services


def test_add_scoped_chains_with_add_transient_and_add_singleton() -> None:
  class Transient:
    pass

  class Singleton:
    pass

  services = ServiceCollection().add_scoped(Concrete).add_transient(Transient).add_singleton(Singleton)
  provider = services.build_service_provider()

  assert isinstance(provider.get_required_service(Concrete), Concrete)
  assert isinstance(provider.get_required_service(Transient), Transient)
  assert isinstance(provider.get_required_service(Singleton), Singleton)


def test_both_implementation_type_and_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(Concrete, Concrete, factory=lambda _: Concrete())  # type: ignore[call-overload]


@pytest.mark.parametrize(
  "bad_service_type",
  ["logger", list[int], 42, a_function, Concrete()],
)
def test_non_class_service_type_raises(bad_service_type: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(bad_service_type)  # type: ignore[arg-type]


@pytest.mark.parametrize(
  "bad_implementation_type",
  ["logger", list[int], 42, a_function, Concrete()],
)
def test_non_class_implementation_type_raises(bad_implementation_type: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(Concrete, bad_implementation_type)  # type: ignore[arg-type]


def test_abstract_service_type_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(AbstractStore)


def test_protocol_service_type_in_one_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(StoreProtocol)


def test_abstract_implementation_type_in_two_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(AbstractStore, AbstractStore)


def test_protocol_implementation_type_in_two_argument_form_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(StoreProtocol, StoreProtocol)


def test_abstract_service_type_with_concrete_implementation_is_fine() -> None:
  services = ServiceCollection().add_scoped(AbstractStore, ConcreteStore)

  services.build_service_provider()


def test_abstract_service_type_with_factory_is_fine() -> None:
  services = ServiceCollection().add_scoped(AbstractStore, factory=lambda _: ConcreteStore())

  services.build_service_provider()


def test_non_callable_factory_raises() -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    services.add_scoped(Concrete, factory=42)  # type: ignore[arg-type]


def test_async_def_factory_raises() -> None:
  services = ServiceCollection()

  async def factory(_: ServiceProvider) -> Concrete:
    return Concrete()

  with pytest.raises(RegistrationError):
    services.add_scoped(Concrete, factory=factory)


def test_a_plain_def_factory_returning_a_coroutine_is_accepted() -> None:
  async def coroutine() -> Concrete:
    return Concrete()

  def factory(_: ServiceProvider) -> object:
    return coroutine()

  services = ServiceCollection().add_scoped(Concrete, factory=factory)  # type: ignore[arg-type]

  services.build_service_provider()


@pytest.mark.parametrize(
  "register",
  [
    lambda services: services.add_scoped(ServiceProvider),
    lambda services: services.add_scoped(ServiceProvider, Concrete),  # type: ignore[arg-type]
    lambda services: services.add_scoped(ServiceProvider, factory=lambda _: Concrete()),  # type: ignore[arg-type]
  ],
)
def test_registering_service_provider_raises(register: object) -> None:
  services = ServiceCollection()

  with pytest.raises(RegistrationError):
    register(services)  # type: ignore[operator]


def test_last_registration_wins_transient_to_scoped() -> None:
  services = ServiceCollection().add_transient(Concrete)
  services.add_scoped(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]

  provider = services.build_service_provider()
  first = provider.get_required_service(Concrete)
  second = provider.get_required_service(Concrete)

  assert first == "not a concrete instance"
  assert first is second


def test_last_registration_wins_scoped_to_transient() -> None:
  services = ServiceCollection().add_scoped(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]
  services.add_transient(Concrete)

  resolved = services.build_service_provider().get_required_service(Concrete)

  assert isinstance(resolved, Concrete)


def test_last_registration_wins_singleton_to_scoped() -> None:
  class Marker:
    """A distinct object per factory call, so identity comparisons are meaningful."""

  services = ServiceCollection().add_singleton(Concrete)
  services.add_scoped(Concrete, factory=lambda _: Marker())  # type: ignore[arg-type]

  provider = services.build_service_provider()
  first = provider.get_required_service(Concrete)
  second = provider.create_scope().service_provider.get_required_service(Concrete)

  assert isinstance(first, Marker)
  assert isinstance(second, Marker)
  assert first is not second


def test_last_registration_wins_scoped_to_singleton() -> None:
  services = ServiceCollection().add_scoped(Concrete)
  services.add_singleton(Concrete, factory=lambda _: "not a concrete instance")  # type: ignore[arg-type]

  provider = services.build_service_provider()
  first = provider.get_required_service(Concrete)
  second = provider.create_scope().service_provider.get_required_service(Concrete)

  assert first == "not a concrete instance"
  assert first is second


def test_last_registration_wins_scoped_type_to_scoped_factory() -> None:
  services = ServiceCollection().add_scoped(AbstractStore, ConcreteStore)
  services.add_scoped(AbstractStore, factory=lambda _: "swapped to a factory")  # type: ignore[arg-type]

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert resolved == "swapped to a factory"


def test_no_conformance_checking() -> None:
  services = ServiceCollection().add_scoped(AbstractStore, Unrelated)  # type: ignore[arg-type]

  resolved = services.build_service_provider().get_required_service(AbstractStore)

  assert isinstance(resolved, Unrelated)
