"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

import re

import pytest

from templex import Chain
from templex import DefinitionError
from templex import Delimiter
from templex import StrToken
from templex import TemplateModel
from templex.core import RegexBuilder
from templex.model import BoundToken
from templex.token import integer
from templex.token import model
from templex.token import string


@pytest.mark.parametrize(
    ("delimiter", "open_token", "close_token", "expected_regex"),
    [
        (Delimiter.CURLY, "{", "}", r"\{([^\{\}]*(?:\.[^\{\}]*)*)\}"),
        (Delimiter.ANGLE, "<", ">", r"<([^<>]*(?:\.[^<>]*)*)>"),
        (Delimiter.SQUARE, "[", "]", r"\[([^\[\]]*(?:\.[^\[\]]*)*)\]"),
    ],
)
def test_delimiter(
    delimiter: Delimiter,
    open_token: str,
    close_token: str,
    expected_regex: str,
) -> None:
    """Delimiter enum behaves as expected."""
    assert isinstance(delimiter.value, tuple)
    assert delimiter.token_open == open_token
    assert delimiter.token_close == close_token
    regex = delimiter.token_re()
    assert isinstance(regex, re.Pattern)
    assert regex.pattern == expected_regex


def test_bound_token_init() -> None:
    """Bound token init behaves as expected."""
    BoundToken("attr", StrToken(r"\w+"))


def test_bound_token_regex() -> None:
    """Bound token regex behaves as expected."""
    bound_token = BoundToken("attr", StrToken(r"\w+"))
    regex_builder = RegexBuilder()
    assert bound_token.to_regex(regex_builder) == r"(?P<attr>\w+)"
    # Calling it again with the same regex builder shall reuse
    assert bound_token.to_regex(regex_builder) == r"(?P=attr)"


def test_bound_token_to_chain() -> None:
    """Bound token to_chain behaves as expected."""
    bound_token = BoundToken("attr", StrToken(r"\w+"))
    chain = bound_token.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [bound_token]


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


def test_validate_simple_model_with_token() -> None:
    """Models are valid if they provide a template with a token."""

    class TestModel(TemplateModel):
        __template__ = "{token}"
        token: str = string(".+")


def test_tokens_are_extracted_correctly() -> None:
    """References to tokens are extracted correctly."""

    class TestModel(TemplateModel):
        __template__ = "{test}"
        test: str = string(r"\w+")

    assert len(TestModel.__bound_tokens__) == 1
    assert "test" in TestModel.__bound_tokens__
    assert len(TestModel.__chain__.nodes) == 1
    assert TestModel.__regex__ == r"(?P<test>\w+)"


def test_sep_tokens_are_extracted_correctly() -> None:
    """References to tokens are extracted correctly including separators."""

    class TestModel(TemplateModel):
        __template__ = "sep{test}other"
        test: str = string(r"\w+")

    assert len(TestModel.__bound_tokens__) == 1
    assert "test" in TestModel.__bound_tokens__
    assert len(TestModel.__chain__.nodes) == 3  # noqa: PLR2004
    assert TestModel.__regex__ == r"sep(?P<test>\w+)other"


def test_model_can_reference_token_multiple_times() -> None:
    """A model can reference multiple times in its template."""

    class TestModel(TemplateModel):
        __template__ = "{test}/{test}"
        test: str = string(r"\w+")

    assert len(TestModel.__bound_tokens__) == 1
    assert "test" in TestModel.__bound_tokens__
    assert len(TestModel.__chain__.nodes) == 3  # noqa: PLR2004
    assert TestModel.__regex__ == r"(?P<test>\w+)/(?P=test)"


def test_model_can_reference_other_models_through_model_token() -> None:
    """A model can reference other models through the model token."""

    class FirstModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r"\w+")
        bar: str = string(r"\w+")

    class SecondModel(TemplateModel):
        __template__ = "{foo}/{bar}/{first}/{first.foo}_{foo}_{bar}_{first.bar}"
        foo: str = string(r"\w+")
        bar: str = string(r"\w+")
        first: FirstModel = model(FirstModel)


def test_definition_fails_referencing_unknown_token() -> None:
    """Definition of model shall fail when referencing an unknown token."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{test}"
            other: str = string(r"\w+")


def test_definition_fails_referencing_incorrectly_typed_token() -> None:
    """Definition of model shall fail when referencing an token with the wrong type."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{test}"
            test: str = "test"


def test_definition_fails_with_missing_attribute() -> None:
    """Definition of model shall fail when referencing a missing attribute."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{.}"


def test_definition_fails_with_missing_model_token() -> None:
    """Definition oif model fails if all the tokens are not used in the template."""
    with pytest.raises(DefinitionError):

        class TestModel(TemplateModel):
            __template__ = "{foo}"
            foo: str = string(r"\w+")
            bar: str = string(r"\w+")


def test_definition_fails_with_missing_sub_model_token() -> None:
    """Definition oif model fails if all the tokens are not used in the template."""

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
