"""Integration suite for the scoped-services spec.

Drives the toy application in `src/scoped_services/main.py` through the public `fastdi` API and
asserts the happy-path behavior described in README.md. Error conditions and edge cases are specified
in that README but are deliberately not tested here - they're unit-level, and belong in `./tests/`.
"""

import pytest
from scoped_services.main import (
  DEFAULT_DSN,
  Logger,
  RequestHandler,
  RequestId,
  UnitOfWork,
  build_provider,
  main,
)

from fastdi import ServiceProvider


def test_the_example_container_builds() -> None:
  assert isinstance(build_provider(), ServiceProvider)


def test_create_scope_hands_back_a_service_provider() -> None:
  scope = build_provider().create_scope()

  assert isinstance(scope.service_provider, ServiceProvider)


def test_a_scoped_service_resolves_the_same_instance_within_one_scope() -> None:
  scope = build_provider().create_scope().service_provider

  assert scope.get_required_service(RequestId) is scope.get_required_service(RequestId)


def test_two_scopes_get_independent_scoped_instances() -> None:
  provider = build_provider()

  first_scope = provider.create_scope().service_provider
  second_scope = provider.create_scope().service_provider

  assert first_scope.get_required_service(RequestId) is not second_scope.get_required_service(RequestId)


def test_a_factory_backed_scoped_service_is_shared_within_a_scope(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("DSN", "postgres://example")
  scope = build_provider().create_scope().service_provider

  first = scope.get_required_service(UnitOfWork)
  second = scope.get_required_service(UnitOfWork)

  assert first is second
  assert first.dsn == "postgres://example"


def test_a_factory_backed_scoped_service_defaults_when_the_environment_is_unset() -> None:
  scope = build_provider().create_scope().service_provider

  assert scope.get_required_service(UnitOfWork).dsn == DEFAULT_DSN


def test_a_transient_consumer_still_gets_a_new_instance_within_a_scope() -> None:
  scope = build_provider().create_scope().service_provider

  assert scope.get_required_service(RequestHandler) is not scope.get_required_service(RequestHandler)


def test_a_transient_consumer_shares_the_scopes_scoped_dependencies() -> None:
  scope = build_provider().create_scope().service_provider

  first = scope.get_required_service(RequestHandler)
  second = scope.get_required_service(RequestHandler)

  assert first.request_id is second.request_id
  assert first.repository.unit_of_work is second.repository.unit_of_work


def test_scoped_state_mutated_through_one_consumer_is_visible_through_another() -> None:
  scope = build_provider().create_scope().service_provider

  first = scope.get_required_service(RequestHandler)
  second = scope.get_required_service(RequestHandler)

  first.handle("A1")
  second.handle("A2")

  assert first.repository.unit_of_work.operations == ["insert order A1", "insert order A2"]


def test_a_singleton_is_shared_across_the_root_and_every_scope() -> None:
  provider = build_provider()
  first_scope = provider.create_scope().service_provider
  second_scope = provider.create_scope().service_provider

  logger = provider.get_required_service(Logger)

  assert first_scope.get_required_service(Logger) is logger
  assert second_scope.get_required_service(Logger) is logger


def test_the_unscoped_root_acts_as_its_own_scope() -> None:
  provider = build_provider()

  assert provider.get_required_service(RequestId) is provider.get_required_service(RequestId)


def test_a_scope_created_from_a_scope_is_independent_of_its_parent() -> None:
  provider = build_provider()
  parent_scope = provider.create_scope().service_provider

  nested_scope = parent_scope.create_scope().service_provider

  assert nested_scope.get_required_service(RequestId) is not parent_scope.get_required_service(RequestId)


def test_the_example_runs_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
  main()

  out = capsys.readouterr().out
  assert "order A1 saved" in out
  assert "Different scopes mint different request ids: True" in out
  assert "The un-scoped root acts as its own scope: True" in out
