"""Integration suite for the service-disposal spec.

Drives the toy application in `src/service_disposal/main.py` through the public `fastdi` API and asserts
the happy-path behavior described in README.md. Error conditions and edge cases - `ProviderClosedError`,
`DisposalError`, resolving through a closed provider - are specified in that README but are deliberately
not tested here: they're unit-level, and belong in `./tests/`.
"""

import pytest
from service_disposal.main import (
  AuditLog,
  ConnectionPool,
  DatabaseSession,
  MetricsSink,
  OrderRepository,
  build_provider,
  main,
)

from fastdi import ServiceProvider, ServiceScope


def test_the_example_container_builds() -> None:
  assert isinstance(build_provider(), ServiceProvider)


def test_entering_a_scope_binds_the_scope_itself() -> None:
  provider = build_provider()

  with provider.create_scope() as scope:
    assert isinstance(scope, ServiceScope)
    assert isinstance(scope.service_provider, ServiceProvider)


def test_leaving_a_scope_closes_the_session_that_scope_built() -> None:
  provider = build_provider()

  with provider.create_scope() as scope:
    session = scope.service_provider.get_required_service(DatabaseSession)
    assert not session.closed

  assert session.closed


def test_leaving_a_scope_does_not_close_the_singletons_it_borrowed() -> None:
  provider = build_provider()

  with provider.create_scope() as scope:
    session = scope.service_provider.get_required_service(DatabaseSession)

  assert not session.pool.closed


def test_leaving_a_scope_does_not_close_transients() -> None:
  provider = build_provider()

  with provider.create_scope() as scope:
    repository = scope.service_provider.get_required_service(OrderRepository)
    repository.save_order("A1")

  assert not repository.closed


def test_closing_one_scope_leaves_a_sibling_scopes_session_open() -> None:
  provider = build_provider()
  first = provider.create_scope()
  second = provider.create_scope()
  first_session = first.service_provider.get_required_service(DatabaseSession)
  second_session = second.service_provider.get_required_service(DatabaseSession)

  first.close()

  assert first_session.closed
  assert not second_session.closed


def test_an_explicit_close_matches_the_with_form() -> None:
  provider = build_provider()
  scope = provider.create_scope()
  session = scope.service_provider.get_required_service(DatabaseSession)

  scope.close()

  assert session.closed


def test_closing_a_scope_twice_is_a_no_op() -> None:
  provider = build_provider()

  with provider.create_scope() as scope:
    session = scope.service_provider.get_required_service(DatabaseSession)

  scope.close()
  scope.close()

  assert session.closed


def test_closing_the_provider_closes_the_singletons_it_built() -> None:
  provider = build_provider()
  with provider.create_scope() as scope:
    scope.service_provider.get_required_service(OrderRepository).save_order("A1")
  pool = provider.get_required_service(ConnectionPool)
  sink = provider.get_required_service(MetricsSink)

  provider.close()

  assert pool.closed
  assert sink.closed


def test_closing_the_provider_does_not_close_a_registered_instance() -> None:
  provider = build_provider()
  audit = provider.get_required_service(AuditLog)

  provider.close()

  assert not audit.closed


def test_singletons_are_closed_in_reverse_construction_order() -> None:
  provider = build_provider()
  with provider.create_scope() as scope:
    scope.service_provider.get_required_service(OrderRepository).save_order("A1")
  audit = provider.get_required_service(AuditLog)

  provider.close()

  # The sink is built after the pool it depends on, so it must be closed before it - while the pool
  # is still usable. Its own teardown record reports whether that held.
  assert "closed metrics sink (pool still open: True)" in audit.events
  sink_closed = audit.events.index("closed metrics sink (pool still open: True)")
  assert sink_closed < audit.events.index("closed connection pool")


def test_closing_the_provider_cascades_into_an_open_scope() -> None:
  provider = build_provider()
  scope = provider.create_scope()
  session = scope.service_provider.get_required_service(DatabaseSession)

  provider.close()

  assert session.closed


def test_the_provider_is_a_context_manager_too() -> None:
  with build_provider() as provider:
    assert isinstance(provider, ServiceProvider)
    with provider.create_scope() as scope:
      scope.service_provider.get_required_service(OrderRepository).save_order("A1")
    pool = provider.get_required_service(ConnectionPool)

  assert pool.closed


def test_the_example_runs_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
  main()

  out = capsys.readouterr().out
  assert "Leaving the scope closed the session it built: True" in out
  assert "...but left the singleton pool it borrowed open: True" in out
  assert "...and never closed the transient repositories: True" in out
  assert "Closing the provider closed the singletons it built: True" in out
  assert "...but not the audit log instance handed to it: True" in out
