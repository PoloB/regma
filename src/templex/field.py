"""Definition of fields to be used in template models."""

from __future__ import annotations

import abc
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

from typing_extensions import override

from templex.core import AbstractField
from templex.core import Strictness
from templex.error import DefinitionError
from templex.error import ValidationError

if TYPE_CHECKING:
    from templex.engine import AbstractRegexEngine
    from templex.model import TemplateModel

T_field = TypeVar("T_field")


class PatternField(AbstractField[T_field], abc.ABC):
    """Generic field matching a regex."""

    def __init__(self, pattern: str, strictness: Strictness = Strictness.ALL) -> None:
        """Initialize the field."""
        super().__init__(strictness)
        self._pattern = pattern

    @property
    def pattern(self) -> str:
        """Return the pattern for this field."""
        return self._pattern

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        return self.pattern


class StrField(PatternField[str]):
    """A string field."""

    @override
    def get_supported_types(self) -> tuple[type[str]]:
        return (str,)

    @override
    def validate(self, value: str) -> None:
        if not re.match(self.pattern, value):
            msg = f"Value {value} does not match pattern {self.pattern}"
            raise ValidationError(msg)

    @override
    def _parse_value(self, raw: str) -> str:
        return raw

    @override
    def _format_value(self, value: str) -> str:
        return value


def string(pattern: str, strictness: Strictness = Strictness.ALL) -> Any:  # noqa: ANN401
    """Return a string field."""
    return StrField(pattern, strictness=strictness)


class IntField(PatternField[int]):
    """An integer field."""

    def __init__(
        self,
        minimum: int | None = None,
        maximum: int | None = None,
        padding: int | None = None,
        strictness: Strictness = Strictness.ALL,
    ) -> None:
        """Initialize the field."""
        if minimum is not None and maximum is not None and minimum > maximum:
            msg = f"Minimum value is greater than maximum: {minimum} > {maximum}"
            raise DefinitionError(msg)

        pattern = (
            rf"\d{{{padding}}}"
            if padding is not None and strictness & Strictness.PARSE
            else r"\d+"
        )
        super().__init__(pattern, strictness=strictness)
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
    def get_supported_types(self) -> tuple[type[int]]:
        return (int,)

    @override
    def validate(self, value: int) -> None:
        # Check min and max
        if self._min_val is not None and value < self._min_val:
            msg = f"{value} < min {self._min_val}"
            raise ValidationError(msg)
        if self._max_val is not None and value > self._max_val:
            msg = f"{value} > max {self._max_val}"
            raise ValidationError(msg)

        # Check the padding, handling minus number
        if self._padding is not None and len(str(abs(value))) > self._padding:
            msg = f"{value} has not a padding of {self._padding}"
            raise ValidationError(msg)

    @override
    def _parse_value(self, raw: str) -> int:
        return int(raw)

    @override
    def _format_value(self, value: int) -> str:
        return (
            str(value).zfill(self._padding) if self._padding is not None else str(value)
        )


def integer(
    minimum: int | None = None, maximum: int | None = None, padding: int | None = None
) -> Any:  # noqa: ANN401
    """Return an integer field."""
    return IntField(minimum=minimum, maximum=maximum, padding=padding)


class ChoiceField(PatternField[str]):
    """A choice field."""

    def __init__(
        self, choices: list[str], strictness: Strictness = Strictness.ALL
    ) -> None:
        """Initialize the field."""
        self.choices = choices
        pattern = "|".join(re.escape(c) for c in self.choices)
        super().__init__(rf"(?:{pattern})", strictness=strictness)

    @override
    def get_supported_types(self) -> tuple[type[str]]:
        return (str,)

    @override
    def validate(self, value: str) -> None:
        if value not in self.choices:
            msg = f"{value} is not a valid choice."
            raise ValidationError(msg)

    @override
    def _parse_value(self, raw: str) -> str:
        return raw

    @override
    def _format_value(self, value: str) -> str:
        return value


def choice(choices: list[str]) -> Any:  # noqa: ANN401
    """Return a choice field."""
    return ChoiceField(choices)


class CustomField(AbstractField[T_field]):
    """A custom field wrapping the given definition."""

    def __init__(
        self, field: AbstractField[T_field], strictness: Strictness = Strictness.ALL
    ) -> None:
        """Initialize the field."""
        super().__init__(strictness=strictness)
        self._custom_field = field

    @property
    def field(self) -> AbstractField[T_field]:
        """Return the custom field."""
        return self._custom_field

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        return self._custom_field.to_regex(engine)

    @override
    def get_supported_types(self) -> tuple[type[T_field]]:
        return self._custom_field.get_supported_types()

    @override
    def validate(self, value: T_field) -> None:
        return self._custom_field.validate(value)

    @override
    def _parse_value(self, raw: str) -> T_field:
        return self._custom_field.parse_value(raw)

    @override
    def _format_value(self, value: T_field) -> str:
        return self._custom_field.format_value(value)


def custom_field(field: AbstractField[T_field]) -> Any:  # noqa: ANN401
    """Return a custom field wrapping the given definition."""
    return CustomField(field)


T_field_model = TypeVar("T_field_model", bound="TemplateModel")


class ModelField(AbstractField[T_field_model]):
    """A template model wrapped as a field."""

    def __init__(
        self, model_cls: type[T_field_model], strictness: Strictness = Strictness.ALL
    ) -> None:
        """Initialize the model field."""
        super().__init__(strictness=strictness)
        self._model = model_cls

    @property
    def model(self) -> type[T_field_model]:
        """Return the model wrapped by this field."""
        return self._model

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        return self._model.__chain__.to_regex(engine)

    @override
    def get_supported_types(self) -> tuple[type[T_field_model]]:
        return (self._model,)

    @override
    def validate(self, value: T_field_model) -> None:
        # Model is self validating
        pass

    @override
    def _parse_value(self, raw: str) -> T_field_model:
        return self._model.parse(raw)

    @override
    def _format_value(self, value: T_field_model) -> str:
        return value.format()

    def __getattr__(self, item: str) -> Any:  # noqa: ANN401
        """Return the attribute of the underlying model class."""
        return getattr(self._model, item)


def reference(model_cls: type[T_field_model]) -> Any:  # noqa: ANN401
    """Return a field wrapping an existing template model class."""
    return ModelField(model_cls)
