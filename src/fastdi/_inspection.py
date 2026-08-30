"""Pure introspection helpers over classes; no knowledge of the container."""

import typing
from dataclasses import dataclass
from inspect import Parameter, signature


def is_abstract(cls: type, /) -> bool:
  """True when `cls` cannot be instantiated: a non-empty `__abstractmethods__`, or a `Protocol` class."""
  return bool(getattr(cls, "__abstractmethods__", None)) or typing.is_protocol(cls)


@dataclass(frozen=True, slots=True)
class ConstructorParameter:
  name: str
  annotation: type | None  # None when unannotated
  positional_only: bool
  has_default: bool


def constructor_parameters(implementation_type: type, /) -> tuple[ConstructorParameter, ...]:
  """Resolve `implementation_type.__init__`'s parameters, skipping `self`, `*args` and `**kwargs`."""
  init_signature = signature(implementation_type.__init__)
  hints = typing.get_type_hints(implementation_type.__init__, include_extras=True)

  parameters: list[ConstructorParameter] = []
  for index, (name, parameter) in enumerate(init_signature.parameters.items()):
    if index == 0:
      continue  # self
    if parameter.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
      continue

    annotation = hints.get(name)
    if typing.get_origin(annotation) is typing.Annotated:
      annotation = typing.get_args(annotation)[0]

    parameters.append(
      ConstructorParameter(
        name=name,
        annotation=annotation,
        positional_only=parameter.kind is Parameter.POSITIONAL_ONLY,
        has_default=parameter.default is not Parameter.empty,
      )
    )

  return tuple(parameters)
