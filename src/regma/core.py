"""Chainable ABC, Separator, and Chain composite."""

from __future__ import annotations

import abc
import enum
import re
from enum import auto
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar

from typing_extensions import override

from regma.error import FormatError
from regma.error import ParseError
from regma.error import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from regma.model import Model


class TemplateNode(abc.ABC):
    """Anything that can participate in a template chain."""

    @abc.abstractmethod
    def to_regex(self) -> str:
        """Return the element as a regex."""


class FormatNode(TemplateNode):
    """A node that can contribute to formatting a template model."""

    @abc.abstractmethod
    def format(self, model: Model) -> str:
        """Return the formatted string of this template node."""


class FieldSep:
    """A field followed by a separator."""

    def __init__(self, field: FieldReference, separator: Separator) -> None:
        """Initialize the field separator."""
        self._field = field
        self._sep = separator

    @property
    def field(self) -> FieldReference:
        """Return the field."""
        return self._field

    @property
    def separator(self) -> Separator:
        """Return the separator."""
        return self._sep


class Chain(FormatNode):
    """Ordered sequence of template nodes."""

    def __init__(self, start_separator: Separator, field_seps: list[FieldSep]) -> None:
        """Initialize the chain."""
        self._start_sep = start_separator
        self._field_seps = field_seps
        self._fields = [n.field for n in field_seps]

        self._field_reuse: dict[FieldReference, bool] = {}
        seen_fields: set[str] = set()

        for field in self._fields:
            reuse = field.name in seen_fields
            self._field_reuse[field] = reuse
            seen_fields.add(field.name)

    @property
    def start_separator(self) -> Separator:
        """Return the first separator of the chain."""
        return self._start_sep

    def iter_field_seps(self) -> Iterator[FieldSep]:
        """Return the ordered sequence of template nodes."""
        yield from self._field_seps

    @override
    def to_regex(self) -> str:
        regexes = []
        for field_sep in self._field_seps:
            field = field_sep.field
            field_name = field.name.replace(".", "__")
            if self._field_reuse.get(field, False):
                regex = rf"(?P={field_name})"
            else:
                regex = rf"(?P<{field_name}>{field.to_regex()})"
            regexes.append(regex)
            regexes.append(field_sep.separator.to_regex())
        return self._start_sep.to_regex() + "".join(regexes)

    @override
    def format(self, model: Model) -> str:
        """Return the formatted string of this chain."""
        return self._start_sep.format(model) + "".join(
            f"{n.field.format(model)}{n.separator.format(model)}"
            for n in self._field_seps
        )

    def is_field_reused(self, field: FieldReference) -> bool:
        """Return if given field is already used earlier in the chain."""
        return self._field_reuse.get(field, False)


class Separator(FormatNode):
    """A literal string fragment in a chain."""

    def __init__(self, value: str) -> None:
        """Initialize the separator."""
        self.value = value

    @override
    def to_regex(self) -> str:
        return re.escape(self.value)

    @override
    def format(self, model: Model) -> str:
        return self.value


T_value = TypeVar("T_value")


class Strictness(enum.Flag):
    """State the strictness of field parsing and format."""

    NONE = 0
    PARSE = auto()
    FORMAT = auto()
    ALL = PARSE | FORMAT


class AbstractField(TemplateNode, abc.ABC, Generic[T_value]):
    """Abstract base for all atomic fields."""

    def __init__(self, strictness: Strictness = Strictness.ALL) -> None:
        """Initialize the field."""
        self._strictness = strictness

    @property
    def strictness(self) -> Strictness:
        """Return the strictness of the field."""
        return self._strictness

    @abc.abstractmethod
    def get_supported_types(self) -> tuple[type[T_value]]:
        """Return the supported types of the field."""

    @abc.abstractmethod
    def validate(self, value: T_value) -> None:
        """Raising ValidationError if the value is not valid."""

    @abc.abstractmethod
    def _parse_value(self, raw: str) -> T_value:
        """Return the parsed value from the given string."""

    @abc.abstractmethod
    def _format_value(self, value: T_value) -> str:
        """Return the formatted value for the given string."""

    def parse_value(
        self, raw: str, strictness_override: Strictness | None = None
    ) -> T_value:
        """Parse the value, handling validation."""
        strictness = (
            strictness_override if strictness_override is not None else self.strictness
        )
        try:
            value = self._parse_value(raw)
        except Exception as e:
            raise ParseError from e

        if strictness & Strictness.PARSE:
            try:
                self.validate(value)
            except ValidationError as e:
                raise ParseError from e

        return value

    def format_value(
        self, value: T_value, strictness_override: Strictness | None = None
    ) -> str:
        """Format the value to string, handling validation."""
        strictness = (
            strictness_override if strictness_override is not None else self.strictness
        )
        if strictness & Strictness.FORMAT:
            try:
                self.validate(value)
            except ValidationError as e:
                raise FormatError from e

        try:
            return self._format_value(value)
        except Exception as e:
            raise FormatError from e


class Delimiter(enum.Enum):
    """Field delimiter styles for string templates.

    Examples:
    CURLY  →  {asset_source.type}/{asset_source}
    ANGLE  →  <asset_source.type>/<asset_source>
    SQUARE →  [asset_source.type]/[asset_source]
    """

    CURLY = ("{", "}")
    ANGLE = ("<", ">")
    SQUARE = ("[", "]")

    @property
    def token_open(self) -> str:
        """Return the open field of the delimiter."""
        return self.value[0]

    @property
    def token_close(self) -> str:
        """Return the close field of the delimiter."""
        return self.value[1]

    def token_re(self) -> re.Pattern[str]:
        """Compile and return the regex that matches one field placeholder."""
        o = re.escape(self.token_open)
        c = re.escape(self.token_close)
        ident = rf"[^{o}{c}]*"
        return re.compile(rf"{o}({ident}(?:\.{ident})*){c}")


T_field = TypeVar("T_field", bound=AbstractField[Any])


class BoundField(FormatNode, Generic[T_field]):
    """A field bound to a template model through an attribute."""

    def __init__(self, name: str, field: T_field) -> None:
        """Initialize the bound field.

        The name is the name of the attribute the field is bound to.

        For example, in the following template model:

        class ExampleModel(TemplateModel):
            __template__ = "{test}"
            test: str = StrField(".+")

        The name is 'test' and the field is StrField(".+")
        """
        self._name = name
        self._field = field

    @property
    def name(self) -> str:
        """Return the name of the bound field."""
        return self._name

    @property
    def field(self) -> T_field:
        """Return the bound field."""
        return self._field

    @override
    def to_regex(self) -> str:
        return self._field.to_regex()

    @override
    def format(self, model_inst: Model) -> str:
        return self._field.format_value(getattr(model_inst, self._name))


class FieldReference(FormatNode):
    """A referenced field in a model template.

    This is used in the template parsing.
    """

    def __init__(self, attribute_name: str, target_field: AbstractField[Any]) -> None:
        """Initialize a FieldReference node."""
        self.__name = attribute_name
        self._field = target_field

    @property
    def name(self) -> str:
        """Return the name of the field attribute."""
        return self.__name

    @property
    def target(self) -> AbstractField[Any]:
        """Return the field referenced as a target field."""
        return self._field

    @override
    def to_regex(self) -> str:
        return self.target.to_regex()

    @override
    def format(self, model: Model) -> str:
        value = model
        for attr in self.__name.split("."):
            value = getattr(value, attr)

        return self._field.format_value(value)
