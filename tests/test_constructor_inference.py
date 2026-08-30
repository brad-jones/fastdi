"""Unit tests for constructor inference: MRO lookup, annotations, positional/keyword-only handling."""

from typing import Annotated, Optional

from fastdi import ServiceCollection, ServiceProvider


def build(*registered_types: type) -> ServiceProvider:
  services = ServiceCollection()
  for registered_type in registered_types:
    services.add_transient(registered_type)
  return services.build_service_provider()


class NoInit:
  """Inherits `object.__init__`."""


def test_a_class_inheriting_object_init_resolves_with_no_arguments() -> None:
  provider = build(NoInit)

  assert isinstance(provider.get_required_service(NoInit), NoInit)


class Dep:
  pass


class VarArgs:
  def __init__(self, dep: Dep, *args: int, **kwargs: str) -> None:
    self.dep = dep
    self.args = args
    self.kwargs = kwargs


def test_var_positional_and_var_keyword_are_skipped_and_never_passed() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(VarArgs).build_service_provider()

  resolved = provider.get_required_service(VarArgs)

  assert resolved.args == ()
  assert resolved.kwargs == {}


class Mixed:
  def __init__(self, dep: Dep, /, regular: Dep, *, kw_only: Dep) -> None:
    self.dep = dep
    self.regular = regular
    self.kw_only = kw_only


def test_positional_only_normal_and_keyword_only_dependencies_all_resolve() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(Mixed).build_service_provider()

  resolved = provider.get_required_service(Mixed)

  assert isinstance(resolved.dep, Dep)
  assert isinstance(resolved.regular, Dep)
  assert isinstance(resolved.kw_only, Dep)


class BaseWithInit:
  def __init__(self, dep: Dep) -> None:
    self.dep = dep


class SubclassNoInit(BaseWithInit):
  """Inherits `BaseWithInit.__init__`."""


class GrandchildNoInit(SubclassNoInit):
  """Inherits two levels up."""


class SubclassOwnInit(BaseWithInit):
  def __init__(self, dep: Dep, extra: Dep) -> None:
    super().__init__(dep)
    self.extra = extra


def test_inherited_init_through_one_level_of_mro_is_injected() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(SubclassNoInit).build_service_provider()

  assert isinstance(provider.get_required_service(SubclassNoInit).dep, Dep)


def test_inherited_init_through_two_levels_of_mro_is_injected() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(GrandchildNoInit).build_service_provider()

  assert isinstance(provider.get_required_service(GrandchildNoInit).dep, Dep)


def test_a_subclass_overriding_init_uses_its_own_signature() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(SubclassOwnInit).build_service_provider()

  resolved = provider.get_required_service(SubclassOwnInit)

  assert isinstance(resolved.dep, Dep)
  assert isinstance(resolved.extra, Dep)


class NamesLater:
  def __init__(self, later: DefinedLater) -> None:
    self.later = later


class DefinedLater:
  pass


def test_a_constructor_annotating_a_class_defined_later_in_the_module_resolves() -> None:
  provider = ServiceCollection().add_transient(DefinedLater).add_transient(NamesLater).build_service_provider()

  assert isinstance(provider.get_required_service(NamesLater).later, DefinedLater)


class QuotedAnnotation:
  def __init__(self, dep: Dep) -> None:
    self.dep = dep


def test_an_explicitly_quoted_annotation_resolves() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(QuotedAnnotation).build_service_provider()

  assert isinstance(provider.get_required_service(QuotedAnnotation).dep, Dep)


class SingleAnnotated:
  def __init__(self, dep: Annotated[Dep, "meta"]) -> None:
    self.dep = dep


def test_annotated_injects_the_underlying_type() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(SingleAnnotated).build_service_provider()

  assert isinstance(provider.get_required_service(SingleAnnotated).dep, Dep)


class DoubleAnnotated:
  def __init__(self, first: Annotated[Dep, "first-meta"], second: Annotated[Dep, "second-meta"]) -> None:
    self.first = first
    self.second = second


def test_differing_annotated_metadata_still_resolves_both_to_the_same_registration() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(DoubleAnnotated).build_service_provider()

  resolved = provider.get_required_service(DoubleAnnotated)

  assert isinstance(resolved.first, Dep)
  assert isinstance(resolved.second, Dep)


class UnregisteredWithDefault:
  def __init__(self, thing: NeverRegistered = None) -> None:  # type: ignore[assignment]
    self.thing = thing


class NeverRegistered:
  pass


def test_unregistered_parameter_with_a_default_uses_the_default() -> None:
  provider = ServiceCollection().add_transient(UnregisteredWithDefault).build_service_provider()

  resolved = provider.get_required_service(UnregisteredWithDefault)

  assert resolved.thing is None


class UnannotatedWithDefault:
  def __init__(self, thing=None) -> None:
    self.thing = thing


def test_unannotated_parameter_with_a_default_uses_the_default() -> None:
  provider = ServiceCollection().add_transient(UnannotatedWithDefault).build_service_provider()

  assert provider.get_required_service(UnannotatedWithDefault).thing is None


class RegisteredWithDefault:
  def __init__(self, dep: Dep = None) -> None:  # type: ignore[assignment]
    self.dep = dep


def test_a_registered_type_with_a_default_is_still_injected() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(RegisteredWithDefault).build_service_provider()

  assert isinstance(provider.get_required_service(RegisteredWithDefault).dep, Dep)


class UnionNotInjected:
  def __init__(self, dep: Dep | None = None) -> None:
    self.dep = dep


class OptionalNotInjected:
  def __init__(self, dep: Optional[Dep] = None) -> None:  # noqa: UP045
    self.dep = dep


def test_union_with_none_default_is_not_injected() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(UnionNotInjected).build_service_provider()

  assert provider.get_required_service(UnionNotInjected).dep is None


def test_optional_is_not_injected() -> None:
  provider = ServiceCollection().add_transient(Dep).add_transient(OptionalNotInjected).build_service_provider()

  assert provider.get_required_service(OptionalNotInjected).dep is None


class OnlyProvider:
  def __init__(self, provider: ServiceProvider) -> None:
    self.provider = provider


class NestedProvider:
  def __init__(self, only: OnlyProvider) -> None:
    self.only = only


def test_service_provider_annotated_parameter_is_injected_when_it_is_the_only_parameter() -> None:
  provider = ServiceCollection().add_transient(OnlyProvider).build_service_provider()

  resolved = provider.get_required_service(OnlyProvider)

  assert resolved.provider is provider


def test_service_provider_annotated_parameter_is_injected_when_nested_two_levels_down() -> None:
  provider = ServiceCollection().add_transient(OnlyProvider).add_transient(NestedProvider).build_service_provider()

  resolved = provider.get_required_service(NestedProvider)

  assert resolved.only.provider is provider
