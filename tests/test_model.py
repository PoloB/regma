"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

import re

import pytest

from templex import Chain
from templex import DefinitionError
from templex import Delimiter
from templex import StrField
from templex import TemplateModel
from templex.core import RegexBuilder
from templex.field import integer
from templex.field import model
from templex.field import string
from templex.model import BoundField
from templex.model import FieldReference


@pytest.mark.parametrize(
    ("delimiter", "open_token", "close_token", "expected_regex"),
    [
        (Delimiter.CURLY, "{", "}", r"\{([^\{\}]*(?:\.[^\{\}]*)*)\}"),
        (Delimiter.ANGLE, "<", ">", r"<([^<>]*(?:\.[^<>]*)*)>"),
        (Delimiter.SQUARE, "[", "]", r"\[([^\[\]]*(?:\.[^\[\]]*)*)\]"),
    ],
)
def test_delimiter(
    delimiter: Delimiter, open_token: str, close_token: str, expected_regex: str
) -> None:
    """Delimiter enum behaves as expected."""
    assert isinstance(delimiter.value, tuple)
    assert delimiter.token_open == open_token
    assert delimiter.token_close == close_token
    regex = delimiter.token_re()
    assert isinstance(regex, re.Pattern)
    assert regex.pattern == expected_regex


def test_bound_field_init() -> None:
    """Bound field init behaves as expected."""
    BoundField("attr", StrField(r"\w+"))


def test_bound_field_regex() -> None:
    """Bound field regex behaves as expected."""
    bound_field = BoundField("attr", StrField(r"\w+"))
    regex_builder = RegexBuilder()
    assert bound_field.to_regex(regex_builder) == r"(?P<attr>\w+)"
    # Calling it again with the same regex builder shall reuse
    assert bound_field.to_regex(regex_builder) == r"(?P=attr)"


def test_bound_field_to_chain() -> None:
    """Bound field to_chain behaves as expected."""
    bound_field = BoundField("attr", StrField(r"\w+"))
    chain = bound_field.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [bound_field]


def test_field_reference_init() -> None:
    """A field reference shall init successfully."""
    target_field = StrField(r"\w+")
    field_ref = FieldReference("attr", target_field)
    assert field_ref.attribute_name == "attr"
    assert field_ref.target is target_field


def test_field_reference_to_regex() -> None:
    """Test the field reference regex construction."""
    field_ref = FieldReference("foo.bar", StrField(r"\w+"))
    regex_builder = RegexBuilder()
    assert field_ref.to_regex(regex_builder) == r"(?P<foo__bar>\w+)"


def test_field_reference_to_chain() -> None:
    """Test the field reference chain construction."""
    field_ref = FieldReference("foo.bar", StrField(r"\w+"))
    chain = field_ref.to_chain()
    assert chain.nodes == [field_ref]


def test_model_fails_without_template() -> None:
    """Definition of template model fails if no __template__ is not defined."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            pass


def test_model_fails_with_wrong_delimiter_type() -> None:
    """Definition of template model fails if wrong delimiter type is provided."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "test"
            __delimiter__ = "wrong"  # type: ignore[assignment]


def test_model_fails_with_wrong_regex_builder_type() -> None:
    """Definition of template model fails if wrong regex builder type is provided."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "test"
            __regex_builder__ = "wrong"  # type: ignore[assignment]


def test_validate_simple_model() -> None:
    """Models are valid if they provide at least a template."""

    class TestModel(TemplateModel):
        __template__ = "test"


def test_validate_simple_model_with_field() -> None:
    """Models are valid if they provide a template with a field."""

    class TestModel(TemplateModel):
        __template__ = "{field}"
        field: str = string(".+")


def test_fields_are_extracted_correctly() -> None:
    """References to fields are extracted correctly."""

    class TestModel(TemplateModel):
        __template__ = "{test}"
        test: str = string(r"\w+")

    assert len(TestModel.__fields__) == 1
    assert "test" in TestModel.__fields__
    assert len(TestModel.__chain__.nodes) == 1
    assert TestModel.__regex__ == r"(?P<test>\w+)"


def test_sep_fields_are_extracted_correctly() -> None:
    """References to fields are extracted correctly including separators."""

    class TestModel(TemplateModel):
        __template__ = "sep{test}other"
        test: str = string(r"\w+")

    assert len(TestModel.__fields__) == 1
    assert "test" in TestModel.__fields__
    assert len(TestModel.__chain__.nodes) == 3  # noqa: PLR2004
    assert TestModel.__regex__ == r"sep(?P<test>\w+)other"


def test_model_can_reference_field_multiple_times() -> None:
    """A model can reference multiple times in its template."""

    class TestModel(TemplateModel):
        __template__ = "{test}/{test}"
        test: str = string(r"\w+")

    assert len(TestModel.__fields__) == 1
    assert "test" in TestModel.__fields__
    assert len(TestModel.__chain__.nodes) == 3  # noqa: PLR2004
    assert TestModel.__regex__ == r"(?P<test>\w+)/(?P=test)"


def test_model_can_reference_other_models_through_model_field() -> None:
    """A model can reference other models through the model field."""

    class FirstModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r"\w+")
        bar: str = string(r"\w+")

    class SecondModel(TemplateModel):
        __template__ = "{foo}/{bar}/{first}/{first.foo}_{foo}_{bar}_{first.bar}_{first}"
        foo: str = string(r"\w+")
        bar: str = string(r"\w+")
        first: FirstModel = model(FirstModel)

    assert len(SecondModel.__fields__) == 2  # noqa: PLR2004
    assert len(SecondModel.__model_fields__) == 1
    assert (
        SecondModel.__regex__
        == r"(?P<foo>\w+)/(?P<bar>\w+)/(?P<first>(?P<first__foo>\w+)"
        r"_(?P<first__bar>\w+))/(?P=first__foo)_(?P=foo)_(?P=bar)_(?P=first__bar)_(?P=first)"
    )
    assert (
        re.match(SecondModel.__regex__, "foo/bar/ffoo_fbar/ffoo_foo_bar_fbar_ffoo_fbar")
        is not None
    )


def test_definition_fails_referencing_unknown_field() -> None:
    """Definition of model shall fail when referencing an unknown field."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{test}"
            other: str = string(r"\w+")


def test_definition_fails_if_field_ends_with_underscore() -> None:
    """Definition of model shall fail if the field ends with underscore."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{test_}"
            test_: str = string(r"\w+")


def test_definition_fails_referencing_incorrectly_typed_field() -> None:
    """Definition of model shall fail when referencing an field with the wrong type."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{test}"
            test: str = "test"


def test_definition_fails_with_missing_attribute() -> None:
    """Definition of model shall fail when referencing a missing attribute."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{.}"


def test_definition_fails_with_missing_model_field() -> None:
    """Definition oif model fails if all the fields are not used in the template."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{foo}"
            foo: str = string(r"\w+")
            bar: str = string(r"\w+")


def test_definition_fails_with_missing_sub_model_field() -> None:
    """Definition oif model fails if all the fields are not used in the template."""

    class FirstModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r"\w+")
        bar: str = string(r"\w+")

    with pytest.raises(DefinitionError):

        class SecondModel(TemplateModel):
            __template__ = "{foo}/{bar}/{first.foo}"  # first.bar is missing
            foo: str = string(r"\w+")
            bar: str = string(r"\w+")
            first: FirstModel = model(FirstModel)


class _TestInstanceModel(TemplateModel):
    """Model used to test instantiation."""

    __template__ = "{foo}_{bar}"
    foo: str = string(r"\w+")
    bar: int = integer()


def test_model_is_instantiated_correctly() -> None:
    """Models are instantiated correctly if all arguments are provided."""
    model_inst = _TestInstanceModel("test", 1)
    assert model_inst.foo == "test"
    assert model_inst.bar == 1


def test_model_is_instantiable_with_kwargs() -> None:
    """Models are instantiated using keyword arguments."""
    _TestInstanceModel(foo="test", bar=1)


def test_model_instantiation_fails_if_missing_arguments() -> None:
    """Models instantiation shall raise TypeError if missing arguments."""
    with pytest.raises(TypeError):
        _TestInstanceModel("test")  # type: ignore[call-arg]


def test_model_instantiation_fails_if_too_many_arguments() -> None:
    """Models instantiation shall raise TypeError if there are too many arguments."""
    with pytest.raises(TypeError):
        _TestInstanceModel("test", 1, "excess")  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        _TestInstanceModel("test", 1, foo="foo")  # type: ignore[misc]
