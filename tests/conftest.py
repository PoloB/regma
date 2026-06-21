"""Common configuration for tests in regma."""

from __future__ import annotations

import re

from typing_extensions import override

from regma import Model
from regma import ModelTemplate
from regma.core import AbstractField
from regma.error import ValidationError
from regma.field import integer
from regma.field import string


class AbstractTestField(AbstractField[str]):
    """A basic field, as close as possible to abstract field."""

    @override
    def to_regex(self) -> str:
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
    def to_regex(self) -> str:
        pattern = "|".join(re.escape(str(c)) for c in self.choices)
        return rf"(?:{pattern})"

    @override
    def _format_value(self, value: int) -> str:
        return str(value)


class SimpleTestModel(Model):
    """Simple test model."""

    test: str = string(".+")


simple_test_template = ModelTemplate(SimpleTestModel, "{test}")


class FooBarModel(Model):
    """Model with two fields foo and bar."""

    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer()


foo_bar_template = ModelTemplate(FooBarModel, "{foo}_{bar}")


class ComplexModel(Model):
    """Model with fields and model fields."""

    foo_bar: FooBarModel
    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer()


complex_template = ModelTemplate(
    ComplexModel, "/root/{foo_bar.foo}_{foo_bar.bar}_{foo}_{bar}"
)
