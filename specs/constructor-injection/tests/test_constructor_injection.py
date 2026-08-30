"""Integration suite for the constructor-injection spec.

Drives the toy application in `src/constructor_injection/main.py` through the public `fastdi` API and
asserts the happy-path behavior described in README.md. Error conditions and edge cases are specified
in that README but are deliberately not tested here — they're unit-level, and belong in `./tests/`.
"""

import pytest
from constructor_injection.main import (
  DEFAULT_DSN,
  AuditLog,
  Clock,
  DatabaseConfig,
  FixedClock,
  Greeter,
  ReportBuilder,
  Repository,
  TimestampedAuditLog,
  build_provider,
  main,
)

from fastdi import ServiceProvider


def test_the_example_container_builds() -> None:
  assert isinstance(build_provider(), ServiceProvider)


def test_the_whole_graph_is_wired_from_type_hints_alone() -> None:
  report = build_provider().get_required_service(ReportBuilder)

  assert isinstance(report.greeter, Greeter)
  assert isinstance(report.repository, Repository)
  assert isinstance(report.repository.config, DatabaseConfig)
  assert isinstance(report.greeter.clock, FixedClock)
  assert isinstance(report.audit, TimestampedAuditLog)


def test_the_resolved_graph_actually_works() -> None:
  message = build_provider().get_required_service(ReportBuilder).build("Ada")

  assert "Hello Ada" in message
  assert DEFAULT_DSN in message


def test_a_protocol_registration_resolves_to_its_implementation() -> None:
  assert isinstance(build_provider().get_required_service(Clock), FixedClock)


def test_an_abstract_base_class_registration_resolves_to_its_implementation() -> None:
  assert isinstance(build_provider().get_required_service(AuditLog), TimestampedAuditLog)


def test_a_constructor_inherited_from_a_base_class_still_gets_injected() -> None:
  audit = build_provider().get_required_service(AuditLog)

  assert isinstance(audit.clock, FixedClock)


def test_the_abstract_service_is_usable_through_its_base_class_api() -> None:
  report = build_provider().get_required_service(ReportBuilder)

  report.build("Ada")

  assert report.audit.entries == [f"[{report.clock.now()}] report for Ada"]


def test_a_factory_supplies_what_the_container_cannot_infer(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("DSN", "postgres://example")

  assert build_provider().get_required_service(DatabaseConfig).dsn == "postgres://example"


def test_every_resolution_returns_a_new_instance() -> None:
  provider = build_provider()

  assert provider.get_required_service(Greeter) is not provider.get_required_service(Greeter)


def test_a_dependency_reached_twice_in_one_graph_is_built_twice() -> None:
  report = build_provider().get_required_service(ReportBuilder)

  assert report.clock is not report.greeter.clock


def test_the_provider_resolves_and_injects_itself() -> None:
  provider = build_provider()

  assert provider.get_required_service(ServiceProvider) is provider
  assert provider.get_required_service(ReportBuilder).provider is provider


def test_the_example_runs_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
  main()

  assert "Hello Ada" in capsys.readouterr().out
