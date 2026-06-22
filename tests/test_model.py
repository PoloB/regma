"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

import re

import pytest

from regma import DefinitionError
from regma import Model
from regma import ModelTemplate
from regma import ParseError
from regma.field import integer
from regma.field import string
from tests.conftest import ComplexModel
from tests.conftest import FooBarModel
from tests.conftest import complex_template


def test_validate_simple_model_with_field() -> None:
    """Models are valid if they provide a template with a field."""

    class TestModel(Model):
        field: str = string(".+")


def test_fields_are_extracted_correctly() -> None:
    """References to fields are extracted correctly."""

    class TestModel(Model):
        test: str = string(r"\w+")

    template = ModelTemplate(TestModel, "{test}")

    assert len(TestModel.__typed_fields__) == 1
    assert "test" in TestModel.__typed_fields__
    assert template.chain.start_separator.value == ""
    assert len(list(template.chain.iter_field_seps())) == 1
    assert template.to_regex() == r"(?P<test>\w+)"


def test_sep_fields_are_extracted_correctly() -> None:
    """References to fields are extracted correctly including separators."""

    class TestModel(Model):
        test: str = string(r"\w+")

    template = ModelTemplate(TestModel, "sep{test}other")

    assert len(TestModel.__typed_fields__) == 1
    assert "test" in TestModel.__typed_fields__
    assert template.chain.start_separator.value == "sep"
    field_seps = list(template.chain.iter_field_seps())
    assert len(field_seps) == 1
    assert field_seps[0].reference.name == "test"
    assert field_seps[0].separator.value == "other"
    assert template.to_regex() == r"sep(?P<test>\w+)other"


def test_model_can_reference_field_multiple_times() -> None:
    """A model can reference multiple times in its template."""

    class TestModel(Model):
        test: str = string(r"\w+")

    template = ModelTemplate(TestModel, "{test}/{test}")

    assert len(TestModel.__typed_fields__) == 1
    assert "test" in TestModel.__typed_fields__
    assert len(list(template.chain.iter_field_seps())) == 2  # noqa: PLR2004
    assert template.to_regex() == r"(?P<test>\w+)/(?P=test)"


def test_model_can_reference_other_models_through_model_field() -> None:
    """A model can reference other models through the model field."""

    class FirstModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")

    first_template = ModelTemplate(FirstModel, "{foo}_{bar}")

    class SecondModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")
        first: FirstModel

    second_template = ModelTemplate(
        SecondModel,
        "{foo}/{bar}/{first_template}/{first.foo}_{foo}_{bar}_{first.bar}_{first_template}",
        first_template=first_template.using("first"),
    )

    assert len(SecondModel.__typed_fields__) == 2  # noqa: PLR2004
    assert len(SecondModel.__model_refs__) == 1
    assert (
        second_template.to_regex() == r"(?P<foo>[a-zA-Z0-9]+)/(?P<bar>\w+)/"
        r"(?P<first_template>(?P<first__foo>[a-zA-Z0-9]+)_(?P<first__bar>\w+))/"
        r"(?P=first__foo)_(?P=foo)_(?P=bar)_(?P=first__bar)_(?P=first_template)"
    )
    assert (
        re.match(
            second_template.to_regex(), "foo/bar/ffoo_fbar/ffoo_foo_bar_fbar_ffoo_fbar"
        )
        is not None
    )


def test_definition_fails_referencing_unknown_field() -> None:
    """Definition of model shall fail when referencing an unknown field."""

    class TestModel(Model):
        other: str = string(r"\w+")

    with pytest.raises(DefinitionError):
        ModelTemplate(TestModel, "{test}")


def test_definition_fails_if_field_ends_with_underscore() -> None:
    """Definition of model shall fail if the field ends with underscore."""
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            test_: str = string(r"\w+")


def test_definition_fails_if_field_contain_double_underscore() -> None:
    """Definition of model shall fail if the field contains underscore.

    We need this to make sure there is no collision between the name of the field and
    the __ used as separator in capturing groups.
    """
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            foo__bar: str = string(r"\w+")


def test_definition_fails_referencing_incorrectly_typed_field() -> None:
    """Definition of model shall fail when referencing a field with the wrong type."""

    class TestModel(Model):
        test: str = "test"

    with pytest.raises(DefinitionError):
        ModelTemplate(TestModel, "{test}")


def test_definition_fails_with_missing_attribute() -> None:
    """Definition of model shall fail when referencing a missing attribute."""

    class TestModel(Model):
        pass

    with pytest.raises(DefinitionError):
        ModelTemplate(TestModel, "{.}")


def test_definition_fails_with_missing_model_field() -> None:
    """Definition oif model fails if all the fields are not used in the template."""

    class TestModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")

    with pytest.raises(DefinitionError):
        ModelTemplate(TestModel, "{foo}")


def test_definition_fails_with_missing_sub_model_field() -> None:
    """Definition of model fails if all the fields are not used in the template."""

    class FirstModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")

    class SecondModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")
        first: FirstModel

    with pytest.raises(DefinitionError):
        ModelTemplate(SecondModel, "{foo}/{bar}/{first.foo}")  # first.bar is missing


def test_definition_fails_with_template_misuse() -> None:
    """Definition of model fails if a template is not properly referenced."""

    class FirstModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")

    first_template = ModelTemplate(FirstModel, "{foo}_{bar}")

    class SecondModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")
        first: FirstModel

    with pytest.raises(DefinitionError):
        ModelTemplate(
            SecondModel,
            "{foo}/{bar}/{first_template.nope}",
            first_template=first_template,
        )  # first.template.nope is invalid


def test_model_is_instantiated_correctly() -> None:
    """Models are instantiated correctly if all arguments are provided."""
    model_inst = FooBarModel("test", 1)
    assert model_inst.foo == "test"
    assert model_inst.bar == 1


def test_model_eq() -> None:
    """Models are equal if their fields are equal."""
    mode1 = ComplexModel(FooBarModel("test", 1), "foo", 1)
    mode2 = ComplexModel(FooBarModel("test", 1), "foo", 1)
    assert mode1 == mode2


def test_model_eq_different() -> None:
    """Models are different if their fields are not equal."""
    mode1 = ComplexModel(FooBarModel("test", 1), "foo", 1)
    mode2 = ComplexModel(FooBarModel("test", 2), "foo", 1)
    assert mode1 != mode2


def test_model_eq_different_type() -> None:
    """Models are different if the type is different, event if fields are identical."""

    class OtherFooBarModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: int = integer()

    mode1 = FooBarModel("test", 1)
    mode2 = OtherFooBarModel("test", 1)
    assert mode1 != mode2


def test_model_is_hashable() -> None:
    """Models are hashable."""
    assert hash(FooBarModel("test", 1))


def test_model_is_instantiable_with_kwargs() -> None:
    """Models are instantiated using keyword arguments."""
    FooBarModel(foo="test", bar=1)


def test_model_instantiation_fails_if_missing_arguments() -> None:
    """Models instantiation shall raise TypeError if missing arguments."""
    with pytest.raises(TypeError):
        FooBarModel("test")  # type: ignore[call-arg]


def test_model_instantiation_fails_if_too_many_arguments() -> None:
    """Models instantiation shall raise TypeError if there are too many arguments."""
    with pytest.raises(TypeError):
        FooBarModel("test", 1, "excess")  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        FooBarModel("test", 1, foo="foo")  # type: ignore[misc]


def test_model_from_flat_dict() -> None:
    """Models shall be initializable from a flat dict."""
    data = {"foo": "foo", "bar": 1, "foo_bar__foo": "foo", "foo_bar__bar": 2}
    inst = ComplexModel.from_flat_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_flat_dict_excess() -> None:
    """Models shall still initialize if there are too many keys."""
    data = {
        "foo": "foo",
        "bar": 1,
        "foo_bar__foo": "foo",
        "foo_bar__bar": 2,
        "unknown": 42,
    }
    inst = ComplexModel.from_flat_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_flat_dict_with_unflattened_sub_model() -> None:
    """Models shall still initialize if the data contains sub model key."""
    data = {
        "foo": "foo",
        "bar": 1,
        "foo_bar": "foo_2",
        "foo_bar__foo": "foo",
        "foo_bar__bar": 2,
        "unknown": 42,
    }
    inst = ComplexModel.from_flat_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_flat_dict_fail_with_missing_key() -> None:
    """Models shall raise TypeError if missing key."""
    data = {"foo": "foo", "bar": 1, "foo_bar__foo": "foo"}
    with pytest.raises(TypeError):
        ComplexModel.from_flat_dict(data)


def test_model_parse() -> None:
    """Models shall parse successfully."""
    inst = complex_template.parse("/root/foo_2_foo_1")
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_parse_fail_raises_parse_error() -> None:
    """Models shall raise ParseError if parse fails."""
    with pytest.raises(ParseError):
        complex_template.parse("/nope/foo_2foo_1")


def test_model_repr() -> None:
    """Models shall return a string when using repr."""
    assert isinstance(repr(ComplexModel(FooBarModel("foo", 2), "foo", 1)), str)
