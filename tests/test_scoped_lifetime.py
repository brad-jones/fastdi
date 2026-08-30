"""Unit tests for the scoped lifetime's resolution, caching and scope semantics."""

import pytest

from fastdi import CircularDependencyError, ServiceCollection, ServiceProvider, ServiceScope


class Thing:
  pass


def test_bare_class_scoped_service_resolves_the_same_instance_within_one_scope() -> None:
  scope = ServiceCollection().add_scoped(Thing).build_service_provider().create_scope().service_provider

  assert scope.get_required_service(Thing) is scope.get_required_service(Thing)


class Base:
  pass


class Impl(Base):
  pass


def test_type_keyed_scoped_service_resolves_the_same_instance_within_one_scope() -> None:
  scope = ServiceCollection().add_scoped(Base, Impl).build_service_provider().create_scope().service_provider

  assert isinstance(scope.get_required_service(Base), Impl)
  assert scope.get_required_service(Base) is scope.get_required_service(Base)


def test_get_service_and_get_required_service_return_the_same_scoped_instance() -> None:
  scope = ServiceCollection().add_scoped(Thing).build_service_provider().create_scope().service_provider

  assert scope.get_service(Thing) is scope.get_required_service(Thing)


def test_two_scopes_never_share_a_scoped_instance() -> None:
  provider = ServiceCollection().add_scoped(Thing).build_service_provider()

  first_scope = provider.create_scope().service_provider
  second_scope = provider.create_scope().service_provider

  assert first_scope.get_required_service(Thing) is not second_scope.get_required_service(Thing)


def test_the_unscoped_root_provider_acts_as_its_own_scope() -> None:
  provider = ServiceCollection().add_scoped(Thing).build_service_provider()

  assert provider.get_required_service(Thing) is provider.get_required_service(Thing)


def test_factory_backed_scoped_service_runs_the_factory_once_per_scope() -> None:
  call_count = 0

  def factory(_: ServiceProvider) -> Thing:
    nonlocal call_count
    call_count += 1
    return Thing()

  provider = ServiceCollection().add_scoped(Thing, factory=factory).build_service_provider()
  scope = provider.create_scope().service_provider

  scope.get_required_service(Thing)
  scope.get_required_service(Thing)
  scope.get_service(Thing)

  assert call_count == 1

  provider.create_scope().service_provider.get_required_service(Thing)

  assert call_count == 2


def test_create_scope_constructs_nothing() -> None:
  instantiation_count = 0

  class CountedScoped:
    def __init__(self) -> None:
      nonlocal instantiation_count
      instantiation_count += 1

  provider = ServiceCollection().add_scoped(CountedScoped).build_service_provider()

  provider.create_scope()
  provider.create_scope()

  assert instantiation_count == 0


def test_a_scope_created_from_a_scope_is_independent_of_its_parent() -> None:
  provider = ServiceCollection().add_scoped(Thing).build_service_provider()
  parent_scope = provider.create_scope().service_provider

  nested_scope = parent_scope.create_scope().service_provider

  assert nested_scope.get_required_service(Thing) is not parent_scope.get_required_service(Thing)


def test_a_singleton_is_shared_by_the_root_and_every_scope_nested_or_not() -> None:
  services = ServiceCollection().add_singleton(Thing)
  provider = services.build_service_provider()
  first_scope = provider.create_scope().service_provider
  second_scope = provider.create_scope().service_provider
  nested_scope = first_scope.create_scope().service_provider

  singleton = provider.get_required_service(Thing)

  assert first_scope.get_required_service(Thing) is singleton
  assert second_scope.get_required_service(Thing) is singleton
  assert nested_scope.get_required_service(Thing) is singleton


def test_transient_resolution_is_unaffected_by_scopes() -> None:
  services = ServiceCollection().add_transient(Thing)
  scope = services.build_service_provider().create_scope().service_provider

  assert scope.get_required_service(Thing) is not scope.get_required_service(Thing)


transient_dependency_build_log: list[str] = []


class CountedTransient:
  def __init__(self) -> None:
    transient_dependency_build_log.append("built")


class ScopedOwner:
  def __init__(self, counted: CountedTransient) -> None:
    self.counted = counted


def test_a_scoped_service_rebuilds_its_transient_dependency_once_per_scope() -> None:
  transient_dependency_build_log.clear()
  services = ServiceCollection().add_transient(CountedTransient).add_scoped(ScopedOwner)
  provider = services.build_service_provider()
  first_scope = provider.create_scope().service_provider

  first_scope.get_required_service(ScopedOwner)
  first_scope.get_required_service(ScopedOwner)

  assert transient_dependency_build_log == ["built"]

  second_scope = provider.create_scope().service_provider
  second_scope.get_required_service(ScopedOwner)

  assert transient_dependency_build_log == ["built", "built"]


class Consumer:
  def __init__(self, thing: Thing) -> None:
    self.thing = thing


def test_a_transient_consumer_shares_its_scoped_dependency_within_one_scope() -> None:
  services = ServiceCollection().add_scoped(Thing).add_transient(Consumer)
  scope = services.build_service_provider().create_scope().service_provider

  first = scope.get_required_service(Consumer)
  second = scope.get_required_service(Consumer)

  assert first is not second
  assert first.thing is second.thing


def test_validation_is_eager_and_nothing_is_constructed_for_scoped_services() -> None:
  type_instantiation_count = 0
  factory_call_count = 0

  class CountedScoped:
    def __init__(self) -> None:
      nonlocal type_instantiation_count
      type_instantiation_count += 1

  def factory(_: ServiceProvider) -> Thing:
    nonlocal factory_call_count
    factory_call_count += 1
    return Thing()

  services = ServiceCollection().add_scoped(CountedScoped).add_scoped(Thing, factory=factory)

  services.build_service_provider()

  assert type_instantiation_count == 0
  assert factory_call_count == 0


def test_a_cycle_spanning_the_scoped_lifetime_is_still_caught() -> None:
  class Alpha:
    def __init__(self, beta: Beta) -> None:
      self.beta = beta

  class Beta:
    def __init__(self, alpha: Alpha) -> None:
      self.alpha = alpha

  services = ServiceCollection().add_transient(Alpha).add_scoped(Beta)

  with pytest.raises(CircularDependencyError) as excinfo:
    services.build_service_provider()

  assert excinfo.value.chain == (Alpha, Beta, Alpha)


class ProviderCapturingSingleton:
  def __init__(self, provider: ServiceProvider) -> None:
    self.provider = provider


def test_a_singleton_captures_whichever_scopes_provider_built_it_first() -> None:
  provider = ServiceCollection().add_singleton(ProviderCapturingSingleton).build_service_provider()
  scope = provider.create_scope().service_provider

  built_via_scope = scope.get_required_service(ProviderCapturingSingleton)

  assert built_via_scope.provider is scope

  resolved_later_via_root = provider.get_required_service(ProviderCapturingSingleton)
  other_scope = provider.create_scope().service_provider
  resolved_later_via_other_scope = other_scope.get_required_service(ProviderCapturingSingleton)

  assert resolved_later_via_root is built_via_scope
  assert resolved_later_via_other_scope is built_via_scope
  assert resolved_later_via_root.provider is scope


def test_get_service_does_not_swallow_a_scoped_factorys_exception() -> None:
  def raising_factory(_: ServiceProvider) -> Thing:
    raise ValueError("boom")

  scope = ServiceCollection().add_scoped(Thing, factory=raising_factory).build_service_provider().create_scope().service_provider

  with pytest.raises(ValueError, match="boom"):
    scope.get_service(Thing)


def test_get_required_service_does_not_swallow_a_scoped_factorys_exception() -> None:
  def raising_factory(_: ServiceProvider) -> Thing:
    raise ValueError("boom")

  scope = ServiceCollection().add_scoped(Thing, factory=raising_factory).build_service_provider().create_scope().service_provider

  with pytest.raises(ValueError, match="boom"):
    scope.get_required_service(Thing)


def test_a_scoped_constructor_exception_propagates_on_first_resolution_within_a_scope() -> None:
  class Broken:
    def __init__(self) -> None:
      raise ValueError("boom")

  scope = ServiceCollection().add_scoped(Broken).build_service_provider().create_scope().service_provider

  with pytest.raises(ValueError, match="boom"):
    scope.get_required_service(Broken)


def test_service_scope_service_provider_is_stable_and_a_service_provider() -> None:
  scope = ServiceCollection().build_service_provider().create_scope()

  assert isinstance(scope, ServiceScope)
  assert isinstance(scope.service_provider, ServiceProvider)
  assert scope.service_provider is scope.service_provider
