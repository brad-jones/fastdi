"""Integration suite for the singleton-scope spec.

Drives the toy application in `src/singleton_scope/main.py` through the public `fastdi` API and
asserts the happy-path behavior described in README.md. Error conditions and edge cases are specified
in that README but are deliberately not tested here - they're unit-level, and belong in `./tests/`.
"""

import pytest
from singleton_scope.main import (
  DEFAULT_APP_CONFIG,
  DEFAULT_DSN,
  AppConfig,
  Clock,
  Database,
  FixedClock,
  RequestCounter,
  RequestHandler,
  build_provider,
  main,
)

from fastdi import ServiceProvider


def test_the_example_container_builds() -> None:
  assert isinstance(build_provider(), ServiceProvider)


def test_a_bare_singleton_class_resolves_the_same_instance_every_time() -> None:
  provider = build_provider()

  assert provider.get_required_service(RequestCounter) is provider.get_required_service(RequestCounter)


def test_a_type_based_singleton_resolves_the_same_instance_every_time() -> None:
  provider = build_provider()

  assert provider.get_required_service(Clock) is provider.get_required_service(Clock)


def test_a_type_based_singleton_still_resolves_to_its_implementation() -> None:
  assert isinstance(build_provider().get_required_service(Clock), FixedClock)


def test_a_factory_based_singleton_resolves_the_same_instance_every_time(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("DSN", "postgres://example")
  provider = build_provider()

  first = provider.get_required_service(Database)
  second = provider.get_required_service(Database)

  assert first is second
  assert first.dsn == "postgres://example"


def test_a_factory_based_singleton_defaults_when_the_environment_is_unset() -> None:
  assert build_provider().get_required_service(Database).dsn == DEFAULT_DSN


def test_an_instance_registration_returns_the_exact_object_that_was_registered() -> None:
  provider = build_provider()

  config = provider.get_required_service(AppConfig)

  assert config is DEFAULT_APP_CONFIG


def test_a_transient_consumer_still_gets_a_new_instance_every_resolution() -> None:
  provider = build_provider()

  assert provider.get_required_service(RequestHandler) is not provider.get_required_service(RequestHandler)


def test_a_transient_consumer_shares_its_singleton_dependencies_across_resolutions() -> None:
  provider = build_provider()

  first = provider.get_required_service(RequestHandler)
  second = provider.get_required_service(RequestHandler)

  assert first.config is second.config
  assert first.clock is second.clock
  assert first.counter is second.counter
  assert first.database is second.database


def test_singleton_state_mutated_through_one_consumer_is_visible_through_another() -> None:
  provider = build_provider()

  first = provider.get_required_service(RequestHandler)
  second = provider.get_required_service(RequestHandler)

  first.handle("/orders")
  second.handle("/orders/42")

  assert first.counter.total == 2
  assert second.counter.total == 2


def test_singletons_are_independent_between_separate_providers() -> None:
  provider_one = build_provider()
  provider_two = build_provider()

  assert provider_one.get_required_service(RequestCounter) is not provider_two.get_required_service(RequestCounter)


def test_the_example_runs_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
  main()

  out = capsys.readouterr().out
  assert "orders-api" in out
  assert "Two resolved handlers are different objects: True" in out
  assert "...but they share the same clock: True" in out
