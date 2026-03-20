"""Tests the core module of templex."""

import re

import pytest

from templex.core import BoundField
from templex.core import Chain
from templex.core import Delimiter
from templex.core import FieldReference
from templex.core import Separator
from templex.engine import BuiltinRegexEngine
from templex.field import IntField
from templex.field import StrField
from tests.conftest import ComplexModel
from tests.conftest import FooBarModel
from tests.conftest import SimpleTestModel


def test_chain_init() -> None:
    """Chain shall initialize as expected."""
    node1 = Separator("test")
    node2 = Separator("test2")
    chain = Chain([node1, node2])
    assert chain.nodes == [node1, node2]


def test_chain_regex() -> None:
    """Chain shall return expected regex."""
    chain = Chain([Separator("test1"), Separator("test2")])
    regex_builder = BuiltinRegexEngine()
    assert chain.to_regex(regex_builder) == r"test1test2"


def test_chain_to_chain() -> None:
    """Chain shall return itself as chain."""
    chain = Chain([Separator("test"), Separator("test2")])
    assert chain.to_chain() is chain


def test_chain_format() -> None:
    """Chain shall return expected format."""
    chain = Chain([Separator("test"), Separator("test2")])
    assert chain.format(SimpleTestModel("test")) == "testtest2"


def test_separator_init() -> None:
    """Separator shall initialize as expected."""
    separator = Separator("test")
    assert separator.value == "test"


def test_separator_regex() -> None:
    """Separator shall return expected regex."""
    separator = Separator("test")
    assert separator.to_regex(BuiltinRegexEngine()) == "test"


def test_separator_to_chain() -> None:
    """Separator shall return a chain with only itself."""
    separator = Separator("test")
    chain = separator.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [separator]


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
    bound_field = BoundField("attr", StrField(r"\w+"))
    assert bound_field.name == "attr"


def test_bound_field_regex() -> None:
    """Bound field regex behaves as expected."""
    bound_field = BoundField("attr", StrField(r"\w+"))
    regex_engine = BuiltinRegexEngine()
    assert bound_field.to_regex(regex_engine) == r"(?P<attr>\w+)"
    # Calling it again with the same regex engine shall reuse
    assert bound_field.to_regex(regex_engine) == r"(?P=attr)"


def test_bound_field_to_chain() -> None:
    """Bound field to_chain behaves as expected."""
    bound_field = BoundField("attr", StrField(r"\w+"))
    chain = bound_field.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [bound_field]


def test_bound_field_format() -> None:
    """Bound field format behaves as expected."""
    bound_field = BoundField("test", StrField(r"\w+"))
    assert bound_field.format(SimpleTestModel("test")) == "test"


def test_field_reference_init() -> None:
    """A field reference shall init successfully."""
    target_field = StrField(r"\w+")
    field_ref = FieldReference("attr", target_field)
    assert field_ref.attribute_name == "attr"
    assert field_ref.target is target_field


def test_field_reference_to_regex() -> None:
    """Test the field reference regex construction."""
    field_ref = FieldReference("foo.bar", StrField(r"\w+"))
    regex_builder = BuiltinRegexEngine()
    assert field_ref.to_regex(regex_builder) == r"(?P<foo__bar>\w+)"


def test_field_reference_to_chain() -> None:
    """Test the field reference chain construction."""
    field_ref = FieldReference("foo.bar", StrField(r"\w+"))
    chain = field_ref.to_chain()
    assert chain.nodes == [field_ref]


def test_field_reference_format() -> None:
    """Test the field reference format."""
    field_ref = FieldReference("foo_bar.bar", IntField())
    assert field_ref.format(ComplexModel("test", 1, FooBarModel("foo", 2))) == "2"
