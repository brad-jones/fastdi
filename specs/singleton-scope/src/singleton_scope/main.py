"""Toy example for the singleton-scope spec.

Wires a tiny request-handling app with `fastdi` and prints what it built. `build_provider` is also
what `tests/test_singleton_scope.py` drives, so this module doubles as the spec's fixture.

Run it with `uv run specs/singleton-scope/src/singleton_scope/main.py` from the repo root.
"""

import os
from typing import Protocol

from fastdi import ServiceCollection, ServiceProvider

DEFAULT_DSN = "sqlite://memory"


class AppConfig:
  """A plain value object, built once by the caller and handed to the container as-is."""

  def __init__(self, service_name: str, region: str) -> None:
    self.service_name = service_name
    self.region = region


DEFAULT_APP_CONFIG = AppConfig(service_name="orders-api", region="us-east-1")


class Clock(Protocol):
  def now(self) -> str: ...


class FixedClock:
  """A `Clock` implementation with no dependencies of its own."""

  def now(self) -> str:
    return "2026-08-30T00:00:00Z"


class RequestCounter:
  """No dependencies at all - registered with the bare, one-argument singleton form."""

  def __init__(self) -> None:
    self.total = 0

  def increment(self) -> int:
    self.total += 1
    return self.total


class FeatureFlags:
  """Built once by the caller, then registered under its own runtime type - no service_type needed."""

  def __init__(self, dark_mode: bool) -> None:
    self.dark_mode = dark_mode


DEFAULT_FEATURE_FLAGS = FeatureFlags(dark_mode=True)


class Database:
  """A leaf built from an environment-derived DSN, so it has to come from a factory."""

  def __init__(self, dsn: str) -> None:
    self.dsn = dsn

  def describe(self) -> str:
    return f"database at {self.dsn}"


class RequestHandler:
  """Transient: a fresh handler per request, wired to the app's shared singletons."""

  def __init__(
    self,
    config: AppConfig,
    clock: Clock,
    counter: RequestCounter,
    database: Database,
    flags: FeatureFlags,
  ) -> None:
    self.config = config
    self.clock = clock
    self.counter = counter
    self.database = database
    self.flags = flags

  def handle(self, path: str) -> str:
    request_number = self.counter.increment()
    mode = "dark" if self.flags.dark_mode else "light"
    return f"[{self.config.service_name}/{self.config.region}] request #{request_number} for {path} at {self.clock.now()} via {self.database.describe()} ({mode} mode)"


def build_provider() -> ServiceProvider:
  """Registers the whole app: one of each singleton registration shape, plus a transient consumer."""
  services = ServiceCollection()
  services.add_singleton(DEFAULT_FEATURE_FLAGS)
  services.add_singleton(AppConfig, DEFAULT_APP_CONFIG)
  services.add_singleton(Clock, FixedClock)
  services.add_singleton(RequestCounter)
  services.add_singleton(Database, factory=lambda _: Database(os.environ.get("DSN", DEFAULT_DSN)))
  services.add_transient(RequestHandler)
  return services.build_service_provider()


def main() -> None:
  provider = build_provider()

  print(provider.get_required_service(RequestHandler).handle("/orders"))
  print(provider.get_required_service(RequestHandler).handle("/orders/42"))

  first = provider.get_required_service(RequestHandler)
  second = provider.get_required_service(RequestHandler)
  print(f"Two resolved handlers are different objects: {first is not second}")
  print(f"...but they share the same clock: {first.clock is second.clock}")
  print(f"...the same counter, now at {first.counter.total}: {first.counter is second.counter}")
  print(f"...the same database: {first.database is second.database}")
  print(f"...and the exact config instance the app registered: {first.config is DEFAULT_APP_CONFIG}")
  print(f"...and the exact feature flags instance, registered with no explicit key: {first.flags is DEFAULT_FEATURE_FLAGS}")


if __name__ == "__main__":
  main()
