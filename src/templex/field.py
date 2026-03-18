"""Definition of fields to be used in template models."""

from __future__ import annotations

import abc
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar
from typing import override

from templex.core import AbstractField
from templex.core import RegexBuilder
from templex.error import DefinitionError
from templex.error import ParseError

if TYPE_CHECKING:
    from templex.model import TemplateModel

T_field = TypeVar("T_field")


class PatternField(AbstractField[T_field], abc.ABC):
    """Generic field matching a regex."""

    def __init__(self, pattern: str) -> None:
        """Initialize the field."""
        self._pattern = pattern

    @property
    def pattern(self) -> str:
        """Return the pattern for this field."""
        return self._pattern

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return self.pattern


class StrField(PatternField[str]):
    """A string field."""

    @override
    def extract_value(self, raw: str) -> str:
        return raw


def string(pattern: str) -> Any:  # noqa: ANN401
    """Return a string field."""
    return StrField(pattern)


class IntField(PatternField[int]):
    """An integer field."""

    def __init__(
        self,
        minimum: int | None = None,
        maximum: int | None = None,
        padding: int | None = None,
    ) -> None:
        """Initialize the field."""
        if minimum is not None and maximum is not None and minimum > maximum:
            msg = f"Minimum value is greater than maximum: {minimum} > {maximum}"
            raise DefinitionError(msg)

        pattern = r"\d+" if padding is None else rf"\d{{{padding}}}"
        super().__init__(pattern)
        self._min_val = minimum
        self._max_val = maximum
        self._padding = padding

    @property
    def min_value(self) -> int | None:
        """Return the minimum value."""
        return self._min_val

    @property
    def max_value(self) -> int | None:
        """Return the maximum value."""
        return self._max_val

    @property
    def padding(self) -> int | None:
        """Return the padding."""
        return self._padding

    @override
    def extract_value(self, raw: str) -> int:
        value = int(raw)
        if self._min_val is not None and value < self._min_val:
            msg = f"{value} < min {self._min_val}"
            raise ParseError(msg)
        if self._max_val is not None and value > self._max_val:
            msg = f"{value} > max {self._max_val}"
            raise ParseError(msg)
        return value


def integer(
    minimum: int | None = None, maximum: int | None = None, padding: int | None = None
) -> Any:  # noqa: ANN401
    """Return an integer field."""
    return IntField(minimum=minimum, maximum=maximum, padding=padding)


class ChoiceField(PatternField[str]):
    """A choice field."""

    def __init__(self, choices: list[str]) -> None:
        """Initialize the field."""
        self.choices = choices
        pattern = "|".join(re.escape(c) for c in self.choices)
        super().__init__(rf"(?:{pattern})")

    @override
    def extract_value(self, raw: str) -> str:
        return raw


def choice(choices: list[str]) -> Any:  # noqa: ANN401
    """Return a choice field."""
    return ChoiceField(choices)


class CustomField(AbstractField[T_field]):
    """A custom field wrapping the given definition."""

    def __init__(self, field: AbstractField[T_field]) -> None:
        """Initialize the field."""
        self._custom_field = field

    @property
    def field(self) -> AbstractField[T_field]:
        """Return the custom field."""
        return self._custom_field

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return self._custom_field.to_regex(builder)

    @override
    def extract_value(self, raw: str) -> T_field:
        return self._custom_field.extract_value(raw)


def custom_field(field: AbstractField[T_field]) -> Any:  # noqa: ANN401
    """Return a custom field wrapping the given definition."""
    return CustomField(field)


T_field_model = TypeVar("T_field_model", bound="TemplateModel")


class ModelField(AbstractField[T_field_model]):
    """A template model wrapped as a field."""

    def __init__(self, model_cls: type[T_field_model]) -> None:
        """Initialize the model field."""
        self._model = model_cls

    @property
    def model(self) -> type[T_field_model]:
        """Return the model wrapped by this field."""
        return self._model

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return self._model.__chain__.to_regex(builder)

    @override
    def extract_value(self, raw: str) -> T_field_model:
        return self._model.parse(raw)

    def __getattr__(self, item: str) -> Any:  # noqa: ANN401
        """Return the attribute of the underlying model class."""
        return getattr(self._model, item)


def model(model_cls: type[T_field_model]) -> Any:  # noqa: ANN401
    """Return a field wrapping an existing template model class."""
    return ModelField(model_cls)
