"""Tests the core module of regma."""

import re

import pytest

from regma import FormatError
from regma import ParseError
from regma.core import BoundField
from regma.core import Chain
from regma.core import Delimiter
from regma.core import FieldReference
from regma.core import FieldSep
from regma.core import Separator
from regma.core import Strictness
from regma.field import IntField
from regma.field import StrField
from tests.conftest import AbstractTestField
from tests.conftest import ComplexModel
from tests.conftest import FooBarModel
from tests.conftest import SimpleTestModel


def test_chain_init() -> None:
    """Chain shall initialize as expected."""
    sep = Separator("test")
    chain = Chain(sep, [])
    assert chain.start_separator is sep
    assert list(chain.iter_field_seps()) == []


def test_chain_regex() -> None:
    """Chain shall return expected regex."""
    field_sep = FieldSep(FieldReference("test", StrField(".+")), Separator("end"))
    chain = Chain(Separator("start"), [field_sep])
    assert chain.to_regex() == r"start(?P<test>.+)end"


def test_chain_format() -> None:
    """Chain shall return expected format."""
    field_sep = FieldSep(FieldReference("test", StrField(".+")), Separator("end"))
    chain = Chain(Separator("start"), [field_sep])
    assert chain.format(SimpleTestModel("test")) == "starttestend"


def test_separator_init() -> None:
    """Separator shall initialize as expected."""
    separator = Separator("test")
    assert separator.value == "test"


def test_separator_regex() -> None:
    """Separator shall return expected regex."""
    separator = Separator("test")
    assert separator.to_regex() == "test"


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


def test_abstract_field_init() -> None:
    """Test the initialization of abstract field."""
    field = AbstractTestField()
    assert field.strictness == Strictness.ALL
    assert field.get_supported_types() == (str,)
    assert field.to_regex() == ".+"


def test_abstract_field_parse_value() -> None:
    """Test the parsing of abstract field."""
    field = AbstractTestField()
    assert field.parse_value("test") == "test"


def test_abstract_field_parse_value_fails() -> None:
    """Parsing an invalid value shall raise ParseError."""
    with pytest.raises(ParseError):
        AbstractTestField().parse_value("invalid")


def test_abstract_field_parse_value_success_if_not_strict() -> None:
    """Parsing an invalid value shall success if not strict."""
    assert (
        AbstractTestField().parse_value("invalid", strictness_override=Strictness.NONE)
        == "invalid"
    )


def test_abstract_field_parse_value_fails_if_value_is_unparseable() -> None:
    """Parsing an invalid value shall success if not strict."""
    with pytest.raises(ParseError):
        AbstractTestField().parse_value(
            "unparseable", strictness_override=Strictness.NONE
        )


def test_abstract_field_format_value_fails() -> None:
    """Format an invalid value shall raise FormatError."""
    with pytest.raises(FormatError):
        AbstractTestField().format_value("invalid")


def test_abstract_field_format_value_success_if_not_strict() -> None:
    """Formatting an invalid value shall success if not strict."""
    assert (
        AbstractTestField().format_value("invalid", strictness_override=Strictness.NONE)
        == "invalid"
    )


def test_abstract_field_format_value_fails_if_value_is_unformattable() -> None:
    """Formatting an invalid value shall success if not strict."""
    with pytest.raises(FormatError):
        AbstractTestField().format_value(
            "unformattable", strictness_override=Strictness.NONE
        )


def test_bound_field_init() -> None:
    """Bound field init behaves as expected."""
    bound_field = BoundField("attr", StrField(r"\w+"))
    assert bound_field.name == "attr"


def test_bound_field_regex() -> None:
    """Bound field regex behaves as expected."""
    bound_field = BoundField("attr", StrField(r"\w+"))
    assert bound_field.to_regex() == r"\w+"


def test_bound_field_format() -> None:
    """Bound field format behaves as expected."""
    bound_field = BoundField("test", StrField(r"\w+"))
    assert bound_field.format(SimpleTestModel("test")) == "test"


def test_field_reference_init() -> None:
    """A field reference shall init successfully."""
    target_field = StrField(r"\w+")
    field_ref = FieldReference("attr", target_field)
    assert field_ref.name == "attr"
    assert field_ref.target is target_field


def test_field_reference_to_regex() -> None:
    """Test the field reference regex construction."""
    field_ref = FieldReference("foo.bar", StrField(r"\w+"))
    assert field_ref.to_regex() == r"\w+"


def test_field_reference_format() -> None:
    """Test the field reference format."""
    field_ref = FieldReference("foo_bar.bar", IntField())
    assert field_ref.format(ComplexModel(FooBarModel("foo", 2), "test", 1)) == "2"
