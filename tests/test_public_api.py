"""Unit test for the public `fastdi` package surface."""

import fastdi


def test_all_exports_exactly_the_documented_names() -> None:
  assert set(fastdi.__all__) == {
    "ServiceCollection",
    "ServiceProvider",
    "Factory",
    "FastDIError",
    "RegistrationError",
    "ServiceNotRegisteredError",
    "MissingDependencyError",
    "CircularDependencyError",
  }

  for name in fastdi.__all__:
    assert hasattr(fastdi, name)
