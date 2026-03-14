"""Definition of tokens to be used in template models."""

from __future__ import annotations

import abc
import re
from typing import Any
from typing import TypeVar
from typing import override

from templex.core import AbstractToken
from templex.core import RegexBuilder
from templex.error import ParseError

T_token = TypeVar("T_token")


class PatternToken(AbstractToken[T_token], abc.ABC):
    """Generic token matching a regex."""

    def __init__(self, pattern: str) -> None:
        """Initialize the token."""
        self._pattern = pattern

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return self._pattern


class StrToken(PatternToken[str]):
    """A string token."""

    @override
    def parse(self, raw: str) -> str:
        return raw


def string(pattern: str) -> Any:  # noqa: ANN401
    """Return a string token."""
    return StrToken(pattern)


class IntToken(PatternToken[int]):
    """An integer token."""

    def __init__(
        self,
        min_val: int | None = None,
        max_val: int | None = None,
        padding: int | None = None,
    ) -> None:
        """Initialize the token."""
        super().__init__(r"\d+")
        self._min_val = min_val
        self._max_val = max_val
        self._padding = padding

    @override
    def parse(self, raw: str) -> int:
        value = int(raw)
        if self._min_val is not None and value < self._min_val:
            msg = f"{value} < min {self._min_val}"
            raise ParseError(msg)
        if self._max_val is not None and value > self._max_val:
            msg = f"{value} > max {self._max_val}"
            raise ParseError(msg)
        return value


def integer(
    min_val: int | None = None,
    max_val: int | None = None,
    padding: int | None = None,
) -> Any:  # noqa: ANN401
    """Return an integer token."""
    return IntToken(min_val, max_val, padding=padding)


class ChoiceToken(PatternToken[str]):
    """A choice token."""

    def __init__(self, choices: set[str]) -> None:
        """Initialize the token."""
        self.choices = list(choices)
        super().__init__("|".join(re.escape(c) for c in self.choices))

    @override
    def parse(self, raw: str) -> str:
        if raw not in self.choices:
            msg = f"{raw!r} not in choices {self.choices}"
            raise ParseError(msg)
        return raw


def choice(choices: set[str]) -> Any:  # noqa: ANN401
    """Return a choice token."""
    return ChoiceToken(choices)


class CustomToken(AbstractToken[T_token]):
    """A custom token wrapping the given definition."""

    def __init__(self, token: AbstractToken[T_token]) -> None:
        """Initialize the token."""
        self._custom_token = token

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return self._custom_token.to_regex(builder)

    @override
    def parse(self, raw: str) -> T_token:
        return self._custom_token.parse(raw)


def custom_token(token: AbstractToken[T_token]) -> Any:  # noqa: ANN401
    """Return a custom token wrapping the given definition."""
    return CustomToken(token)
