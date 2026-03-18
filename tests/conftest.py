"""Common configuration for tests in templex."""

import re
from typing import override

from templex import TemplateModel
from templex.core import AbstractField
from templex.core import RegexBuilder
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
    def to_regex(self, builder: RegexBuilder) -> str:
        pattern = "|".join(re.escape(str(c)) for c in self.choices)
        return rf"(?:{pattern})"


class SimpleTestModel(TemplateModel):
    """Simple test model."""

    __template__ = "{test}"
    test: str = string(".+")
