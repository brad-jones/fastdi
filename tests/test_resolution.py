"""Unit tests for `ServiceProvider` resolution semantics."""

import pytest

from fastdi import ServiceCollection, ServiceNotRegisteredError, ServiceProvider


class Unregistered:
  pass


def test_get_service_returns_none_for_unregistered_type() -> None:
  provider = ServiceCollection().build_service_provider()

  assert provider.get_service(Unregistered) is None


def test_get_required_service_raises_with_service_type_set() -> None:
  provider = ServiceCollection().build_service_provider()

  with pytest.raises(ServiceNotRegisteredError) as excinfo:
    provider.get_required_service(Unregistered)

  assert excinfo.value.service_type is Unregistered


class Thing:
  pass


def test_get_service_does_not_swallow_a_factorys_value_error() -> None:
  def raising_factory(_: ServiceProvider) -> Thing:
    raise ValueError("boom")

  provider = ServiceCollection().add_transient(Thing, factory=raising_factory).build_service_provider()

  with pytest.raises(ValueError, match="boom"):
    provider.get_service(Thing)


def test_get_service_does_not_swallow_a_factorys_service_not_registered_error() -> None:
  def raising_factory(p: ServiceProvider) -> Thing:
    return p.get_required_service(Unregistered)  # type: ignore[return-value]

  provider = ServiceCollection().add_transient(Thing, factory=raising_factory).build_service_provider()

  with pytest.raises(ServiceNotRegisteredError):
    provider.get_service(Thing)


def test_two_calls_to_get_required_service_return_distinct_objects() -> None:
  provider = ServiceCollection().add_transient(Thing).build_service_provider()

  assert provider.get_required_service(Thing) is not provider.get_required_service(Thing)


def test_get_service_and_get_required_service_return_distinct_objects() -> None:
  provider = ServiceCollection().add_transient(Thing).build_service_provider()

  assert provider.get_service(Thing) is not provider.get_required_service(Thing)


class Banner:
  pass


class Report:
  def __init__(self, header: Banner, footer: Banner) -> None:
    self.header = header
    self.footer = footer


def test_a_diamond_dependency_yields_distinct_instances() -> None:
  provider = ServiceCollection().add_transient(Banner).add_transient(Report).build_service_provider()

  report = provider.get_required_service(Report)

  assert report.header is not report.footer


instantiation_order: list[str] = []


class Leaf:
  def __init__(self) -> None:
    instantiation_order.append("Leaf")


class Middle:
  def __init__(self, leaf: Leaf) -> None:
    instantiation_order.append("Middle")
    self.leaf = leaf


class Top:
  def __init__(self, middle: Middle) -> None:
    instantiation_order.append("Top")
    self.middle = middle


def test_a_three_level_chain_constructs_bottom_up() -> None:
  instantiation_order.clear()
  provider = ServiceCollection().add_transient(Leaf).add_transient(Middle).add_transient(Top).build_service_provider()

  provider.get_required_service(Top)

  assert instantiation_order == ["Leaf", "Middle", "Top"]


def test_the_factory_receives_the_provider_itself() -> None:
  received: list[ServiceProvider] = []

  def factory(p: ServiceProvider) -> Thing:
    received.append(p)
    return Thing()

  provider = ServiceCollection().add_transient(Thing, factory=factory).build_service_provider()

  provider.get_required_service(Thing)

  assert received == [provider]


class Other:
  pass


def test_a_factory_that_pulls_another_service_out_of_the_provider_works() -> None:
  def factory(p: ServiceProvider) -> Thing:
    p.get_required_service(Other)
    return Thing()

  provider = ServiceCollection().add_transient(Other).add_transient(Thing, factory=factory).build_service_provider()

  assert isinstance(provider.get_required_service(Thing), Thing)


def test_a_factorys_return_value_is_returned_as_is_even_if_not_an_instance_of_service_type() -> None:
  provider = ServiceCollection().add_transient(Thing, factory=lambda _: 42).build_service_provider()  # type: ignore[arg-type]

  assert provider.get_required_service(Thing) == 42


def test_get_service_returns_the_provider_for_service_provider() -> None:
  provider = ServiceCollection().build_service_provider()

  assert provider.get_service(ServiceProvider) is provider


def test_get_required_service_returns_the_provider_for_service_provider() -> None:
  provider = ServiceCollection().build_service_provider()

  assert provider.get_required_service(ServiceProvider) is provider


def test_two_providers_from_the_same_collection_each_return_themselves() -> None:
  services = ServiceCollection()

  first = services.build_service_provider()
  second = services.build_service_provider()

  assert first.get_required_service(ServiceProvider) is first
  assert second.get_required_service(ServiceProvider) is second
