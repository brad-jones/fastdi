"""Toy example for the scoped-services spec.

Wires a tiny "handle a request" app with `fastdi` and prints what it built. `build_provider` is also
what `tests/test_scoped_services.py` drives, so this module doubles as the spec's fixture.

Run it with `uv run specs/scoped-services/src/scoped_services/main.py` from the repo root.
"""

import itertools
import os

from fastdi import ServiceCollection, ServiceProvider

DEFAULT_DSN = "sqlite://memory"

_request_ids = itertools.count(1)


class Logger:
  """Singleton: one shared log sink for the whole app, regardless of which scope built it."""

  def __init__(self) -> None:
    self.lines: list[str] = []

  def log(self, message: str) -> None:
    self.lines.append(message)


class RequestId:
  """Scoped, registered bare: minted once per scope, then shared by everything resolved within it."""

  def __init__(self) -> None:
    self.value = f"req-{next(_request_ids)}"


class UnitOfWork:
  """Scoped, built via factory: one simulated database connection, shared for the life of a scope."""

  def __init__(self, dsn: str) -> None:
    self.dsn = dsn
    self.operations: list[str] = []

  def record(self, operation: str) -> None:
    self.operations.append(operation)


class OrderRepository:
  """Transient: a fresh repository per resolution, wired to the scope's shared `UnitOfWork`."""

  def __init__(self, unit_of_work: UnitOfWork, logger: Logger) -> None:
    self.unit_of_work = unit_of_work
    self.logger = logger

  def save_order(self, order_id: str) -> None:
    self.unit_of_work.record(f"insert order {order_id}")
    self.logger.log(f"saved order {order_id} via {self.unit_of_work.dsn}")


class RequestHandler:
  """Transient: a fresh handler per resolution, wired to the scope's `RequestId` and repository."""

  def __init__(self, request_id: RequestId, repository: OrderRepository) -> None:
    self.request_id = request_id
    self.repository = repository

  def handle(self, order_id: str) -> str:
    self.repository.save_order(order_id)
    return f"[{self.request_id.value}] order {order_id} saved"


def build_provider() -> ServiceProvider:
  """Registers the whole app: a singleton, a bare scoped type, a factory-backed scoped type, and two transients."""
  services = ServiceCollection()
  services.add_singleton(Logger)
  services.add_scoped(RequestId)
  services.add_scoped(UnitOfWork, factory=lambda _: UnitOfWork(os.environ.get("DSN", DEFAULT_DSN)))
  services.add_transient(OrderRepository)
  services.add_transient(RequestHandler)
  return services.build_service_provider()


def main() -> None:
  provider = build_provider()

  first_scope = provider.create_scope().service_provider
  print(first_scope.get_required_service(RequestHandler).handle("A1"))
  print(first_scope.get_required_service(RequestHandler).handle("A2"))

  second_scope = provider.create_scope().service_provider
  print(second_scope.get_required_service(RequestHandler).handle("B1"))

  first_request_id = first_scope.get_required_service(RequestId)
  second_request_id = second_scope.get_required_service(RequestId)
  print(f"Same request id shared by every resolution within a scope: {first_scope.get_required_service(RequestId) is first_request_id}")
  print(f"Different scopes mint different request ids: {first_request_id.value != second_request_id.value}")

  first_unit_of_work = first_scope.get_required_service(UnitOfWork)
  print(f"One unit of work recorded both orders from the first scope: {first_unit_of_work.operations}")

  logger = provider.get_required_service(Logger)
  print(f"One singleton logger saw every scope's work: {logger.lines}")

  root_request_id = provider.get_required_service(RequestId)
  print(f"The un-scoped root acts as its own scope: {provider.get_required_service(RequestId) is root_request_id}")


if __name__ == "__main__":
  main()
