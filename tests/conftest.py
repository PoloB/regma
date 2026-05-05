"""Common configuration for tests in regma."""

import re

from typing_extensions import override

from regma import TemplateModel
from regma.core import AbstractField
from regma.engine import AbstractRegexEngine
from regma.error import ValidationError
from regma.field import integer
from regma.field import string


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
            msg = "Invalid value"
            raise ValidationError(msg)

    @override
    def _parse_value(self, raw: str) -> str:
        if raw == "unparseable":
            msg = "Unparseable value"
            raise ValueError(msg)
        return raw

    @override
    def _format_value(self, value: str) -> str:
        if value == "unformattable":
            msg = "Unformattable value"
            raise ValueError(msg)
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
    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer()


class ComplexModel(TemplateModel):
    """Model with fields and model fields."""

    __template__ = "/root/{foo_bar.foo}_{foo_bar.bar}_{foo}_{bar}"
    foo_bar: FooBarModel
    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer()
