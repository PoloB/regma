"""Tests the core module of templex."""

from templex import Chain
from templex.core import RegexBuilder
from templex.core import Separator


def test_regex_builder_init() -> None:
    """RegexBuilder shall initialize with no arguments."""
    RegexBuilder()


def test_build_on_attribute() -> None:
    """Building a template node with an attribute shall give the expected value."""
    separator = Separator("test")
    regex_builder = RegexBuilder()
    assert regex_builder.build("attr", separator) == r"(?P<attr>test)"
    # Building with the same attribute again gives the exact pattern match
    assert regex_builder.build("attr", separator) == r"(?P=attr)"
    # Building the same node with a different attribute name gives a new pattern
    assert regex_builder.build("attr_other", separator) == r"(?P<attr_other>test)"


def test_chain_init() -> None:
    """Chain shall initialize as expected."""
    node1 = Separator("test")
    node2 = Separator("test2")
    chain = Chain([node1, node2])
    assert chain.nodes == [node1, node2]


def test_chain_regex() -> None:
    """Chain shall return expected regex."""
    chain = Chain([Separator("test1"), Separator("test2")])
    regex_builder = RegexBuilder()
    assert chain.to_regex(regex_builder) == r"test1test2"


def test_chain_to_chain() -> None:
    """Chain shall return itself as chain."""
    chain = Chain([Separator("test"), Separator("test2")])
    assert chain.to_chain() is chain


def test_separator_init() -> None:
    """Separator shall initialize as expected."""
    separator = Separator("test")
    assert separator.value == "test"


def test_separator_regex() -> None:
    """Separator shall return expected regex."""
    separator = Separator("test")
    assert separator.to_regex(RegexBuilder()) == "test"


def test_separator_to_chain() -> None:
    """Separator shall return a chain with only itself."""
    separator = Separator("test")
    chain = separator.to_chain()
    assert isinstance(chain, Chain)
    assert chain.nodes == [separator]
