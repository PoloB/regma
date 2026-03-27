"""Common configuration for tests in templex."""

import re
from typing import override

from templex import TemplateModel
from templex.core import AbstractField
from templex.engine import AbstractRegexEngine
from templex.error import ValidationError
from templex.field import integer
from templex.field import string


class AbstractTestField(AbstractField[str]):
    """A basic field, as close as possible to abstract field."""

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        return ".+"

    @override
    def get_supported_types(self) -> tuple[type[str]]:
        return (str,)

    @override
    def validate(self, value: str) -> None:
        if value == "invalid":
            raise ValidationError("Invalid value")

    @override
    def _parse_value(self, raw: str) -> str:
        if raw == "unparseable":
            raise ValueError("Unparseable value")
        return raw

    @override
    def _format_value(self, value: str) -> str:
        if value == "unformattable":
            raise ValueError("unformattable value")
        return value


class IntChoiceField(AbstractField[int]):
    """An integer choice field."""

    @override
    def get_supported_types(self) -> tuple[type[int]]:
        return (int,)

    @override
    def validate(self, value: int) -> None:
        return

    def __init__(self, choices: list[int]) -> None:
        """Initialize the integer choice field."""
        super().__init__()
        self.choices = choices

    @override
    def _parse_value(self, raw: str) -> int:
        return int(raw)

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        pattern = "|".join(re.escape(str(c)) for c in self.choices)
        return rf"(?:{pattern})"

    @override
    def _format_value(self, value: int) -> str:
        return str(value)


class SimpleTestModel(TemplateModel):
    """Simple test model."""

    __template__ = "{test}"
    test: str = string(".+")


class FooBarModel(TemplateModel):
    """Model with two fields foo and bar."""

    __template__ = "{foo}_{bar}"
    foo: str = string(r"\w+")
    bar: int = integer()


class ComplexModel(TemplateModel):
    """Model with fields and model fields."""

    __template__ = "/root/{foo_bar.foo}_{foo_bar.bar}_{foo}_{bar}"
    foo_bar: FooBarModel
    foo: str = string(r"\w+")
    bar: int = integer()
