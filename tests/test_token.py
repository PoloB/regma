"""Tests the token module."""

import pytest

from templex import DefinitionError
from templex import IntToken
from templex import ParseError
from templex.core import RegexBuilder
from templex.token import StrToken
from templex.token import integer
from templex.token import string


def test_str_token_pattern_value() -> None:
    """Pattern shall be the same as initialized."""
    assert StrToken(".+").pattern == ".+"


def test_str_token_regex() -> None:
    """Regex returned by StrToken shall be the same as initialized."""
    builder = RegexBuilder()
    assert StrToken(".+").to_regex(builder) == ".+"


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
    assert int_token.pattern == r"^\d+$"
    assert int_token.min_value is None
    assert int_token.max_value is None
    assert int_token.padding is None


def test_int_token_minimum_greater_than_maximum() -> None:
    """Using a minimum value greater than maximum shall raise a DefinitionError."""
    with pytest.raises(DefinitionError):
        IntToken(minimum=10, maximum=5)


def test_int_token_padding_init() -> None:
    """Set padding of int token changes the pattern."""
    int_token = IntToken(padding=1)
    assert int_token.pattern == r"^\d{1}$"
    int_token = IntToken(padding=3)
    assert int_token.pattern == r"^\d{3}$"


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
    assert descriptor.pattern == r"^\d{3}$"
    assert descriptor.min_value == 1
    assert descriptor.max_value == 10  # noqa: PLR2004
    assert descriptor.padding == 3  # noqa: PLR2004
