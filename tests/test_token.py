"""Tests the token module."""

import pytest

from templex import Chain
from templex import ChoiceToken
from templex import DefinitionError
from templex import IntToken
from templex import ParseError
from templex.core import RegexBuilder
from templex.token import CustomToken
from templex.token import ModelToken
from templex.token import StrToken
from templex.token import choice
from templex.token import custom_token
from templex.token import integer
from templex.token import model
from templex.token import string
from tests.conftest import IntChoiceToken
from tests.conftest import SimpleTestModel


def test_str_token_pattern_value() -> None:
    """Pattern shall be the same as initialized."""
    assert StrToken(".+").pattern == ".+"


def test_str_token_regex() -> None:
    """Regex returned by StrToken shall be the same as initialized."""
    builder = RegexBuilder()
    assert StrToken(".+").to_regex(builder) == ".+"


def test_str_token_to_chain() -> None:
    """StrToken to chain shall contain only itself."""
    token = StrToken(".+")
    chain = token.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [token]


def test_str_token_extract_value() -> None:
    """Parsing of value shall return the given value."""
    assert StrToken("").extract_value("anything") == "anything"


def test_string_field_descriptor() -> None:
    """String field descriptor shall return an StrToken."""
    descriptor = string(r"\w+")
    assert isinstance(descriptor, StrToken)
    assert descriptor.pattern == r"\w+"


def test_int_token_default_init() -> None:
    """Int token shall be initialized."""
    int_token = IntToken()
    assert int_token.pattern == r"\d+"
    assert int_token.min_value is None
    assert int_token.max_value is None
    assert int_token.padding is None


def test_int_token_regex() -> None:
    """Regex returned by IntToken shall be the same as initialized."""
    builder = RegexBuilder()
    assert IntToken().to_regex(builder) == r"\d+"


def test_int_token_to_chain() -> None:
    """IntToken to chain shall contain only itself."""
    token = IntToken()
    chain = token.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [token]


def test_int_token_minimum_greater_than_maximum() -> None:
    """Using a minimum value greater than maximum shall raise a DefinitionError."""
    with pytest.raises(DefinitionError):
        IntToken(minimum=10, maximum=5)


def test_int_token_padding_init() -> None:
    """Set padding of int token changes the pattern."""
    int_token = IntToken(padding=1)
    assert int_token.pattern == r"\d{1}"
    int_token = IntToken(padding=3)
    assert int_token.pattern == r"\d{3}"


def test_int_token_parse_success() -> None:
    """Parsing of value that do not match shall return corresponding integer."""
    assert IntToken().extract_value("12345") == 12345  # noqa: PLR2004
    assert IntToken(padding=4).extract_value("1234") == 1234  # noqa: PLR2004
    assert IntToken(padding=1).extract_value("1234") == 1234  # noqa: PLR2004
    assert IntToken(minimum=1).extract_value("12") == 12  # noqa: PLR2004
    assert IntToken(maximum=10).extract_value("9") == 9  # noqa: PLR2004


def test_int_token_min_max_extract_error() -> None:
    """Parsing a string with incorrect padding shall fail."""
    with pytest.raises(ParseError):
        IntToken(minimum=4).extract_value("2")

    with pytest.raises(ParseError):
        IntToken(maximum=2).extract_value("3")


def test_integer_field_descriptor() -> None:
    """Integer field descriptor shall return an IntToken."""
    descriptor = integer(minimum=1, maximum=10, padding=3)
    assert isinstance(descriptor, IntToken)
    assert descriptor.pattern == r"\d{3}"
    assert descriptor.min_value == 1
    assert descriptor.max_value == 10  # noqa: PLR2004
    assert descriptor.padding == 3  # noqa: PLR2004


def test_choice_token_init() -> None:
    """Choice token shall be initialized."""
    token = ChoiceToken(["test", "test1"])
    assert token.choices == ["test", "test1"]
    assert token.pattern == r"(?:test|test1)"


def test_choice_token_regex() -> None:
    """Regex returned by ChoiceToken shall be the same as initialized."""
    builder = RegexBuilder()
    assert ChoiceToken(["test", "test1"]).to_regex(builder) == r"(?:test|test1)"


def test_choice_token_to_chain() -> None:
    """ChoiceToken to chain shall contain only itself."""
    token = ChoiceToken(["test", "test1"])
    chain = token.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [token]


def test_choice_token_extract_value() -> None:
    """Choice token always return the same value on extraction."""
    assert ChoiceToken(["test", "test1"]).extract_value("other") == "other"


def test_choice_field_descriptor() -> None:
    """Choice field descriptor shall return an ChoiceToken."""
    descriptor = choice(["test", "test1"])
    assert isinstance(descriptor, ChoiceToken)
    assert descriptor.choices == ["test", "test1"]
    assert descriptor.pattern == r"(?:test|test1)"


def test_custom_token_init() -> None:
    """Custom token shall be initialized."""
    int_token = IntChoiceToken([0, 1])
    token = CustomToken(int_token)
    assert token.token is int_token


def test_custom_token_regex() -> None:
    """Regex returned by CustomToken is the same regex as the token itself."""
    builder = RegexBuilder()
    token = IntChoiceToken([0, 1])
    assert CustomToken(token).to_regex(builder) == token.to_regex(builder)


def test_custom_token_to_chain() -> None:
    """CustomToken to chain shall contain only itself."""
    token = CustomToken(IntChoiceToken([0, 1]))
    chain = token.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [token]


def test_custom_token_extract_value() -> None:
    """Custom token always return the same value on extraction."""
    token = IntChoiceToken([0, 1])
    assert CustomToken(token).extract_value("1") == token.extract_value("1")


def test_custom_field_descriptor() -> None:
    """Custom field descriptor shall return an CustomToken."""
    token = IntChoiceToken([0, 1])
    descriptor = custom_token(token)
    assert isinstance(descriptor, CustomToken)
    assert descriptor.token is token


def test_model_token_init() -> None:
    """Model token shall be initialized."""
    model_cls = SimpleTestModel
    model_token = ModelToken(model_cls)
    assert model_token.model is model_cls


def test_model_token_regex() -> None:
    """Regex returned by ModelToken is the same regex as the model itself."""
    builder = RegexBuilder()
    model_cls = SimpleTestModel
    assert ModelToken(model_cls).to_regex(builder) == model_cls.__regex__


def test_model_token_to_chain() -> None:
    """CustomToken to chain shall contain only itself."""
    model_cls = SimpleTestModel
    token = ModelToken(model_cls)
    chain = token.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [token]


def test_model_token_extract_value() -> None:
    """Model token always return the model parsed value."""
    model_cls = SimpleTestModel
    token = ModelToken(model_cls)
    assert token.extract_value("foo") == model_cls.parse("foo")


def test_model_field_descriptor() -> None:
    """Model field descriptor shall return an CustomToken."""
    model_cls = SimpleTestModel
    descriptor = model(model_cls)
    assert isinstance(descriptor, ModelToken)
    assert descriptor.model is model_cls
