"""Common configuration for tests in templex."""

import re
from typing import override

from templex import TemplateModel
from templex.core import AbstractField
from templex.engine import AbstractRegexEngine
from templex.field import integer
from templex.field import model
from templex.field import string


class IntChoiceField(AbstractField[int]):
    """An integer choice field."""

    def __init__(self, choices: list[int]) -> None:
        """Initialize the integer choice field."""
        self.choices = choices

    @override
    def extract_value(self, raw: str) -> int:
        return int(raw)

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        pattern = "|".join(re.escape(str(c)) for c in self.choices)
        return rf"(?:{pattern})"


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

    __template__ = "/root/{foo_bar}{foo}_{bar}"
    foo: str = string(r"\w+")
    bar: int = integer()
    foo_bar: FooBarModel = model(FooBarModel)
