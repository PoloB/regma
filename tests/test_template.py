"""Tests for templates."""

from typing import Any

import pytest

from regma import ParseError
from regma import Template
from regma.field import StrField


def test_template_init() -> None:
    """A template shall initialize correctly."""
    field = StrField(r"\w+")
    template = Template("{field}", field=field)
    assert template.pattern == r"{field}"


@pytest.mark.parametrize(
    ("template", "regex"),
    [
        (Template("{a}", a=StrField(r"\w+")), r"(?P<a>\w+)"),
        (
            Template(
                "{t}_{a}",
                t=Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b")),
                a=StrField(r"a"),
            ),
            r"(?P<t>(?P<t__a>a)_(?P<t__b>b))_(?P<a>a)",
        ),
    ],
)
def test_template_regex(template: Template, regex: str) -> None:
    """Test a template return the correct regex."""
    assert template.regex.pattern == regex


@pytest.mark.parametrize(
    ("template", "value", "result"),
    [
        (Template("{a}", a=StrField(r"\w+")), {"a": "test"}, "test"),
        (
            Template(
                "{t}_{a}",
                t=Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b")),
                a=StrField(r"a"),
            ),
            {"t": {"a": "a", "b": "b"}, "a": "a"},
            "a_b_a",
        ),
    ],
)
def test_template_format(template: Template, value: dict[str, Any], result: str) -> None:
    """Test a template format."""
    assert template.format(value) == result


@pytest.mark.parametrize(
    ("template", "value", "result"),
    [
        (Template("{a}", a=StrField(r"\w+")), "test", {"a": "test"}),
        (
            Template(
                "{t}_{a}",
                t=Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b")),
                a=StrField(r"a"),
            ),
            "a_b_a",
            {"t": {"a": "a", "b": "b"}, "a": "a"},
        ),
    ],
)
def test_template_parse(template: Template, value: str, result: dict[str, Any]) -> None:
    """Test a template parse."""
    assert template.parse(value) == result


def test_template_parse_fail() -> None:
    """Test a template raise ParseError if regex does not match."""
    template = Template("{a}", a=StrField(r"\d+"))

    with pytest.raises(ParseError):
        template.parse("abc")
