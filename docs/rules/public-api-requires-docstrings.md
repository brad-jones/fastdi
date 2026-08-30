---
description: Every symbol reachable from fastdi's exported public API must carry a docstring.
applies-to: [src/fastdi]
---

# Every Exported Public Symbol Must Carry a Docstring

## Rule

Every module, class, function, method, and property reachable from `fastdi`'s public API surface — everything listed
in `fastdi/__init__.py`'s `__all__`, plus the non-underscore-prefixed methods, properties, and attributes of the
classes it exports — must have a docstring describing what it does. Magic methods other than `__init__` are exempt;
`__init__` needs its own docstring only when it accepts parameters the class docstring doesn't already cover.
Underscore-prefixed symbols, and anything not reachable from `__all__`, are exempt regardless of where they live in
`src/fastdi`.

## Why

FastDI's exported surface is its product: a call to `ServiceCollection.add_transient` or
`ServiceProvider.get_required_service` has no source file most callers will ever open, so the signature alone
routinely leaves behavior, side effects, and failure modes (which exception, under what condition) unstated. For an
exception type, the docstring is what tells a caller what raised it and why. A missing docstring on anything exported
is a gap in the only contract most callers ever see.

## Scope

Applies to `src/fastdi` only. It doesn't reach `./tests` — test functions aren't exported and need no doc comments to
be understood. Within `src/fastdi`, it doesn't reach symbols that aren't reachable from `__all__`: internal helper
types such as those in `_registrations.py` or `_validation.py` stay exempt even though they aren't themselves
underscore-prefixed, because they're never exported.

## Overrides

Sharpens `coding-standards`' `doc-docstring` rule, which says public APIs "should" have docstrings and allows an
"obvious from context" exception. Here, presence is mandatory for anything exported, with no obviousness exception.
The docstring's style and content (Google-style, args/returns/raises) is still governed by that rule.

## Examples

Compliant:

```python
class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def get_required_service[T](self, service_type: type[T], /) -> T:
    """Resolve `service_type`, raising if no registration exists.

    Raises:
      ServiceNotRegisteredError: If `service_type` has no registration.
    """
    ...
```

Non-compliant — exported, undocumented:

```python
class ServiceProvider:
  """An immutable, fully validated snapshot of a `ServiceCollection`."""

  def get_required_service[T](self, service_type: type[T], /) -> T: ...
```

## Exceptions

None. A symbol that feels too trivial to document is a signal to make it private (underscore-prefix it or drop it
from `__all__`), not a reason to skip its docstring.
