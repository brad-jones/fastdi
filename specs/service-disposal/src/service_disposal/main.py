"""Toy example for the service-disposal spec.

Wires a tiny "serve some orders, then shut down" app with `fastdi` and prints what got closed, in what
order, and what deliberately did not. `build_provider` is also what `tests/test_service_disposal.py`
drives, so this module doubles as the spec's fixture.

Every service here writes to one `AuditLog`, which is registered as an already-built instance and is
therefore the one thing the container never closes - so it survives shutdown and can still report on it.

Run it with `uv run specs/service-disposal/src/service_disposal/main.py` from the repo root.
"""

from fastdi import ServiceCollection, ServiceProvider

DEFAULT_ENDPOINT = "metrics://localhost"


class AuditLog:
  """Registered as a pre-built instance: disposable, but the container never built it, so never closes it."""

  def __init__(self) -> None:
    self.events: list[str] = []
    self.closed = False

  def record(self, event: str) -> None:
    self.events.append(event)

  def close(self) -> None:
    self.closed = True
    self.record("closed audit log")


class ConnectionPool:
  """Singleton registered bare: built by the container, so closed by the root provider at shutdown."""

  def __init__(self, audit: AuditLog) -> None:
    self.audit = audit
    self.closed = False
    audit.record("opened connection pool")

  def send(self, payload: str) -> None:
    self.audit.record(f"pool sent {payload}")

  def close(self) -> None:
    self.closed = True
    self.audit.record("closed connection pool")


class MetricsSink:
  """Singleton built by a factory: also root-owned, and closed *before* the pool it flushes through."""

  def __init__(self, pool: ConnectionPool, audit: AuditLog, endpoint: str) -> None:
    self.pool = pool
    self.audit = audit
    self.endpoint = endpoint
    self.pending: list[str] = []
    self.closed = False
    audit.record(f"opened metrics sink at {endpoint}")

  def measure(self, metric: str) -> None:
    self.pending.append(metric)

  def close(self) -> None:
    self.closed = True
    for metric in self.pending:
      self.pool.send(metric)
    self.audit.record(f"closed metrics sink (pool still open: {not self.pool.closed})")


class DatabaseSession:
  """Scoped: one per scope, closed when that scope closes - never when a sibling scope closes."""

  def __init__(self, pool: ConnectionPool, audit: AuditLog) -> None:
    self.pool = pool
    self.audit = audit
    self.rows: list[str] = []
    self.closed = False
    audit.record("opened database session")

  def insert(self, row: str) -> None:
    self.rows.append(row)

  def close(self) -> None:
    self.closed = True
    self.audit.record(f"closed database session holding {len(self.rows)} row(s)")


class OrderRepository:
  """Transient: disposable, but FastDI does not track transients, so its `close` is never called."""

  def __init__(self, session: DatabaseSession, sink: MetricsSink, audit: AuditLog) -> None:
    self.session = session
    self.sink = sink
    self.audit = audit
    self.closed = False

  def save_order(self, order_id: str) -> None:
    self.session.insert(order_id)
    self.sink.measure(f"order.saved:{order_id}")
    self.audit.record(f"saved order {order_id}")

  def close(self) -> None:
    self.closed = True
    self.audit.record("closed order repository")


def build_provider() -> ServiceProvider:
  """Registers the whole app: one pre-built instance, two container-built singletons, a scoped session, a transient."""
  audit = AuditLog()
  services = ServiceCollection()
  services.add_singleton(audit)
  services.add_singleton(ConnectionPool)
  services.add_singleton(
    MetricsSink,
    factory=lambda p: MetricsSink(
      p.get_required_service(ConnectionPool),
      p.get_required_service(AuditLog),
      DEFAULT_ENDPOINT,
    ),
  )
  services.add_scoped(DatabaseSession)
  services.add_transient(OrderRepository)
  return services.build_service_provider()


def main() -> None:
  provider = build_provider()
  audit = provider.get_required_service(AuditLog)

  with provider.create_scope() as scope:
    first = scope.service_provider.get_required_service(OrderRepository)
    second = scope.service_provider.get_required_service(OrderRepository)
    first.save_order("A1")
    second.save_order("A2")
    session = scope.service_provider.get_required_service(DatabaseSession)

  print(f"Leaving the scope closed the session it built: {session.closed}")
  print(f"...but left the singleton pool it borrowed open: {not session.pool.closed}")
  print(f"...and never closed the transient repositories: {not first.closed and not second.closed}")

  with provider.create_scope() as second_scope:
    second_scope.service_provider.get_required_service(OrderRepository).save_order("B1")

  pool = provider.get_required_service(ConnectionPool)
  sink = provider.get_required_service(MetricsSink)
  provider.close()

  print(f"Closing the provider closed the singletons it built: {pool.closed and sink.closed}")
  print(f"...but not the audit log instance handed to it: {not audit.closed}")
  print("Full audit record:")
  for event in audit.events:
    print(f"  - {event}")


if __name__ == "__main__":
  main()
