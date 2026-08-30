"""Unit tests for the singleton lifetime's resolution and validation semantics."""

import pytest

from fastdi import CircularDependencyError, ServiceCollection, ServiceProvider


class Thing:
  pass


def test_bare_class_singleton_resolves_the_same_instance_every_time() -> None:
  provider = ServiceCollection().add_singleton(Thing).build_service_provider()

  assert provider.get_required_service(Thing) is provider.get_required_service(Thing)


class Base:
  pass


class Impl(Base):
  pass


def test_type_keyed_singleton_resolves_the_same_instance_every_time() -> None:
  provider = ServiceCollection().add_singleton(Base, Impl).build_service_provider()

  assert provider.get_required_service(Base) is provider.get_required_service(Base)


def test_get_service_and_get_required_service_return_the_same_singleton_instance() -> None:
  provider = ServiceCollection().add_singleton(Thing).build_service_provider()

  assert provider.get_service(Thing) is provider.get_required_service(Thing)


def test_factory_backed_singleton_runs_the_factory_exactly_once() -> None:
  call_count = 0

  def factory(_: ServiceProvider) -> Thing:
    nonlocal call_count
    call_count += 1
    return Thing()

  provider = ServiceCollection().add_singleton(Thing, factory=factory).build_service_provider()

  provider.get_required_service(Thing)
  provider.get_required_service(Thing)
  provider.get_service(Thing)

  assert call_count == 1


class Consumer:
  def __init__(self, thing: Thing) -> None:
    self.thing = thing


def test_factory_backed_singleton_runs_once_even_when_resolved_as_a_nested_dependency() -> None:
  call_count = 0

  def factory(_: ServiceProvider) -> Thing:
    nonlocal call_count
    call_count += 1
    return Thing()

  services = ServiceCollection().add_singleton(Thing, factory=factory).add_transient(Consumer)
  provider = services.build_service_provider()

  provider.get_required_service(Consumer)
  provider.get_required_service(Consumer)

  assert call_count == 1


def test_instance_registration_never_constructs_and_returns_the_exact_object() -> None:
  instance = Thing()
  provider = ServiceCollection().add_singleton(instance).build_service_provider()

  assert provider.get_required_service(Thing) is instance
  assert provider.get_required_service(Thing) is instance


def test_instance_registration_is_shared_across_providers_from_the_same_collection() -> None:
  instance = Thing()
  services = ServiceCollection().add_singleton(instance)

  first = services.build_service_provider()
  second = services.build_service_provider()

  assert first.get_required_service(Thing) is instance
  assert second.get_required_service(Thing) is instance


def test_bare_class_singleton_caches_are_independent_across_providers() -> None:
  services = ServiceCollection().add_singleton(Thing)

  first = services.build_service_provider()
  second = services.build_service_provider()

  assert first.get_required_service(Thing) is not second.get_required_service(Thing)


def test_factory_backed_singleton_caches_are_independent_across_providers() -> None:
  services = ServiceCollection().add_singleton(Thing, factory=lambda _: Thing())

  first = services.build_service_provider()
  second = services.build_service_provider()

  assert first.get_required_service(Thing) is not second.get_required_service(Thing)


def test_a_transient_consumer_shares_the_same_singleton_dependency_across_resolutions() -> None:
  services = ServiceCollection().add_singleton(Thing).add_transient(Consumer)
  provider = services.build_service_provider()

  first = provider.get_required_service(Consumer)
  second = provider.get_required_service(Consumer)

  assert first is not second
  assert first.thing is second.thing


singleton_dependency_build_log: list[str] = []


class CountedTransient:
  def __init__(self) -> None:
    singleton_dependency_build_log.append("built")


class SingletonOwner:
  def __init__(self, counted: CountedTransient) -> None:
    self.counted = counted


def test_a_singleton_only_builds_its_transient_dependency_once() -> None:
  singleton_dependency_build_log.clear()
  services = ServiceCollection().add_transient(CountedTransient).add_singleton(SingletonOwner)
  provider = services.build_service_provider()

  provider.get_required_service(SingletonOwner)
  provider.get_required_service(SingletonOwner)

  assert singleton_dependency_build_log == ["built"]


def test_validation_is_eager_and_nothing_is_constructed_for_singletons() -> None:
  type_instantiation_count = 0
  factory_call_count = 0

  class CountedSingleton:
    def __init__(self) -> None:
      nonlocal type_instantiation_count
      type_instantiation_count += 1

  def factory(_: ServiceProvider) -> Thing:
    nonlocal factory_call_count
    factory_call_count += 1
    return Thing()

  services = ServiceCollection().add_singleton(CountedSingleton).add_singleton(Thing, factory=factory)

  services.build_service_provider()

  assert type_instantiation_count == 0
  assert factory_call_count == 0


def test_a_cycle_spanning_mixed_lifetimes_is_still_caught() -> None:
  class Alpha:
    def __init__(self, beta: Beta) -> None:
      self.beta = beta

  class Beta:
    def __init__(self, alpha: Alpha) -> None:
      self.alpha = alpha

  services = ServiceCollection().add_transient(Alpha).add_singleton(Beta)

  with pytest.raises(CircularDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.chain == (Alpha, Beta, Alpha)


def test_get_service_does_not_swallow_a_singleton_factorys_exception() -> None:
  def raising_factory(_: ServiceProvider) -> Thing:
    raise ValueError("boom")

  provider = ServiceCollection().add_singleton(Thing, factory=raising_factory).build_service_provider()

  with pytest.raises(ValueError, match="boom"):
    provider.get_service(Thing)


def test_get_required_service_does_not_swallow_a_singleton_factorys_exception() -> None:
  def raising_factory(_: ServiceProvider) -> Thing:
    raise ValueError("boom")

  provider = ServiceCollection().add_singleton(Thing, factory=raising_factory).build_service_provider()

  with pytest.raises(ValueError, match="boom"):
    provider.get_required_service(Thing)


def test_a_singleton_constructor_exception_propagates_on_first_resolution() -> None:
  class Broken:
    def __init__(self) -> None:
      raise ValueError("boom")

  provider = ServiceCollection().add_singleton(Broken).build_service_provider()

  with pytest.raises(ValueError, match="boom"):
    provider.get_required_service(Broken)
