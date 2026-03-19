"""Tests the engine module of templex."""

from templex import Separator
from templex.engine import BuiltinRegexEngine


def test_regex_builder_init() -> None:
    """RegexBuilder shall initialize with no arguments."""
    BuiltinRegexEngine()


def test_build_on_attribute() -> None:
    """Building a template node with an attribute shall give the expected value."""
    separator = Separator("test")
    regex_builder = BuiltinRegexEngine()
    assert regex_builder.build("attr", separator) == r"(?P<attr>test)"
    # Building with the same attribute again gives the exact pattern match
    assert regex_builder.build("attr", separator) == r"(?P=attr)"
    # Building the same node with a different attribute name gives a new pattern
    assert regex_builder.build("attr_other", separator) == r"(?P<attr_other>test)"
