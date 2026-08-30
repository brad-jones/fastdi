"""Toy example for the constructor-injection spec.

Wires a tiny reporting app with `fastdi` and prints what it built. `build_provider` is also what
`tests/test_constructor_injection.py` drives, so this module doubles as the spec's fixture.

Run it with `uv run specs/constructor-injection/src/constructor_injection/main.py` from the repo root.
"""

import os
from abc import ABC, abstractmethod
from typing import Protocol

from fastdi import ServiceCollection, ServiceProvider

DEFAULT_DSN = "sqlite://memory"


class Clock(Protocol):
  def now(self) -> str: ...


class FixedClock:
  """A `Clock` implementation with no dependencies of its own."""

  def now(self) -> str:
    return "2026-08-30T00:00:00Z"


class Greeter:
  """Depends on the `Clock` protocol, not on any concrete implementation."""

  def __init__(self, clock: Clock) -> None:
    self.clock = clock

  def greet(self, name: str) -> str:
    return f"Hello {name}, it is {self.clock.now()}"


class AuditLog(ABC):
  """An ABC service key rather than a Protocol, holding the dependency its subclasses share."""

  def __init__(self, clock: Clock) -> None:
    self.clock = clock
    self.entries: list[str] = []

  @abstractmethod
  def format(self, message: str) -> str: ...

  def record(self, message: str) -> None:
    self.entries.append(self.format(message))


class TimestampedAuditLog(AuditLog):
  """Defines no `__init__`, so it inherits `AuditLog`'s and gets a `Clock` injected into it."""

  def format(self, message: str) -> str:
    return f"[{self.clock.now()}] {message}"


class DatabaseConfig:
  """A leaf whose only input is a plain `str`, so it has to come from a factory."""

  def __init__(self, dsn: str) -> None:
    self.dsn = dsn


class Repository:
  def __init__(self, config: DatabaseConfig) -> None:
    self.config = config

  def describe(self) -> str:
    return f"repository on {self.config.dsn}"


class ReportBuilder:
  """Sits at the top of the graph, and reaches `Clock` both directly and via `Greeter`."""

  def __init__(
    self,
    greeter: Greeter,
    repository: Repository,
    clock: Clock,
    audit: AuditLog,
    provider: ServiceProvider,
  ) -> None:
    self.greeter = greeter
    self.repository = repository
    self.clock = clock
    self.audit = audit
    self.provider = provider

  def build(self, name: str) -> str:
    report = f"{self.greeter.greet(name)} - {self.repository.describe()}, generated at {self.clock.now()}"
    self.audit.record(f"report for {name}")
    return report


def build_provider() -> ServiceProvider:
  """Registers the whole app: every registration shape, all transient."""
  services = ServiceCollection()
  services.add_transient(Clock, FixedClock)
  services.add_transient(AuditLog, TimestampedAuditLog)
  services.add_transient(Greeter)
  services.add_transient(DatabaseConfig, factory=lambda _: DatabaseConfig(os.environ.get("DSN", DEFAULT_DSN)))
  services.add_transient(Repository).add_transient(ReportBuilder)
  return services.build_service_provider()


def main() -> None:
  provider = build_provider()
  report = provider.get_required_service(ReportBuilder)

  print(report.build("Ada"))
  print(f"Clock resolved to {type(report.clock).__name__}")
  print(f"AuditLog resolved to {type(report.audit).__name__}, which logged {report.audit.entries}")
  print(f"The builder's clock and the greeter's clock are the same object: {report.clock is report.greeter.clock}")
  print(f"The builder was handed the provider that built it: {report.provider is provider}")


if __name__ == "__main__":
  main()
