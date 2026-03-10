"""
templex.tokens
~~~~~~~~~~~~~~
Token ABC and built-in token types.
Tokens are immutable; .configure() returns a new instance.
"""

from __future__ import annotations

import abc
import re
from typing import Any, TypeVar

from templex.core import AbstractToken, RegexBuilder
from templex.exceptions import ParseError

T_token = TypeVar("T_token", bound=Any)


class PatternToken(AbstractToken[T_token], abc.ABC):
    def __init__(self, pattern: str) -> None:
        self._pattern = pattern

    def to_regex(self, builder: RegexBuilder) -> str:
        return self._pattern


class StrToken(PatternToken[str]):
    def parse(self, raw: str) -> str:
        return raw

    def format(self, value: str) -> str:
        return value


class IntToken(PatternToken[int]):
    def __init__(
        self,
        min_val: int | None = None,
        max_val: int | None = None,
        padding: int | None = None,
    ) -> None:
        super().__init__(r"\d+")
        self._min_val = min_val
        self._max_val = max_val
        self._padding = padding

    def parse(self, raw: str) -> int:
        value = int(raw)
        if self._min_val is not None and value < self._min_val:
            raise ParseError(f"{value} < min {self._min_val}")
        if self._max_val is not None and value > self._max_val:
            raise ParseError(f"{value} > max {self._max_val}")
        return value

    def format(self, value: int) -> str:
        if not self._padding:
            return str(value)
        return str(value).zfill(self._padding)


class ChoiceToken(PatternToken[str]):
    def __init__(self, choices: list[str]) -> None:
        self.choices = list(choices)
        super().__init__("|".join(re.escape(c) for c in self.choices))

    def parse(self, raw: str) -> str:
        if raw not in self.choices:
            raise ParseError(f"{raw!r} not in choices {self.choices}")
        return raw

    def format(self, value: str) -> str:
        return value
