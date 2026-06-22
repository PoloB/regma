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

from typing_extensions import Self  # noqa: UP035
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


T_mod = TypeVar("T_mod", bound="Model")


class FormatNode(TemplateNode):
    """A node that can contribute to formatting a template model."""

    @abc.abstractmethod
    def format(self, model: Model) -> str:
        """Return the formatted string of this node for the given model instance."""


class ChainTokenNode(TemplateNode):
    """A format token node that can be used in a chain."""

    @abc.abstractmethod
    def get_content_chain(self) -> Chain:
        """Return the element as chain."""

    @abc.abstractmethod
    def format(self, model: T_mod) -> str:
        """Return the formatted string of this node for the given model instance."""


class RefSep:
    """A reference followed by a separator."""

    def __init__(self, reference: Reference, separator: Separator) -> None:
        """Initialize the field separator."""
        self._reference = reference
        self._sep = separator

    @property
    def reference(self) -> Reference:
        """Return the reference."""
        return self._reference

    @property
    def separator(self) -> Separator:
        """Return the separator."""
        return self._sep


class Chain:
    """Ordered sequence of template nodes."""

    @classmethod
    def empty(cls) -> Self:
        """Return an empty chain."""
        return cls(Separator(""), [])

    def __init__(self, start_separator: Separator, field_seps: list[RefSep]) -> None:
        """Initialize the chain."""
        self._start_sep = start_separator
        self._ref_seps = field_seps
        self._ref_reuse: dict[Reference, bool] = {}
        self._update_field_reuse()

    def _update_field_reuse(self) -> None:
        seen_fields: set[str] = set()
        for ref in self.iter_flatten_references():
            reuse = ref.name in seen_fields
            self._ref_reuse[ref] = reuse
            seen_fields.add(ref.name)

    def using(self, attribute_name: str) -> Self:
        """Return a new chain where all the references go through the given attribute."""
        new_ref_seps: list[RefSep] = []
        for field_sep in self._ref_seps:
            new_ref = Reference(
                f"{attribute_name}.{field_sep.reference.name}",
                field_sep.reference.target,
            )
            new_ref_seps.append(RefSep(new_ref, field_sep.separator))

        return self.__class__(Separator(self._start_sep.value), new_ref_seps)

    def append_reference(self, reference: Reference) -> None:
        """Append the given reference to the chain."""
        self._ref_seps.append(RefSep(reference, Separator("")))
        self._update_field_reuse()

    def append_separator(self, separator: str) -> None:
        """Add the string to the end of the chain."""
        if not self._ref_seps:
            self._start_sep = Separator(self._start_sep.value + separator)
        else:
            last_field_sep = self._ref_seps[-1]
            self._ref_seps[-1] = RefSep(
                last_field_sep.reference,
                Separator(last_field_sep.separator.value + separator),
            )

    @property
    def start_separator(self) -> Separator:
        """Return the first separator of the chain."""
        return self._start_sep

    def iter_field_seps(self) -> Iterator[RefSep]:
        """Return the ordered sequence of template nodes."""
        yield from self._ref_seps

    def to_regex(self) -> str:
        """Return the regex associated to the chain."""
        regexes = []
        for field_sep in self._ref_seps:
            ref = field_sep.reference
            field_name = ref.name.replace(".", "__")
            if self._ref_reuse.get(ref, False):
                regex = rf"(?P={field_name})"
            else:
                regex = rf"(?P<{field_name}>{ref.to_regex()})"
            regexes.append(regex)
            regexes.append(field_sep.separator.to_regex())
        return self._start_sep.to_regex() + "".join(regexes)

    def format(self, model: Model) -> str:
        """Return the formatted string of this chain."""
        return self._start_sep.format(model) + "".join(
            f"{n.reference.format(model)}{n.separator.format(model)}"
            for n in self._ref_seps
        )

    def is_reference_reused(self, reference: Reference) -> bool:
        """Return if given field is already used earlier in the chain."""
        return self._ref_reuse.get(reference, False)

    def iter_flatten_references(self) -> Iterator[Reference]:
        """Iterate over all the flattened references in the chain."""
        for ref_sep in self._ref_seps:
            ref = ref_sep.reference
            yield ref
            ref_chain = ref.target.get_content_chain()
            yield from ref_chain.iter_flatten_references()


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


class BoundField(ChainTokenNode, Generic[T_field]):
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

    @override
    def get_content_chain(self) -> Chain:
        return Chain(Separator(""), [])


class Reference:
    """A referenced element in a template construction."""

    def __init__(self, attribute_name: str, target: ChainTokenNode) -> None:
        """Initialize a FieldReference node."""
        self.__name = attribute_name
        self._target = target

    @property
    def name(self) -> str:
        """Return the name of the field attribute."""
        return self.__name

    @property
    def target(self) -> ChainTokenNode:
        """Return the referenced element."""
        return self._target

    def to_regex(self) -> str:
        """Return the reference as a regex."""
        return self.target.to_regex()

    def format(self, model: Model) -> str:
        """Return the formatted value for the field."""
        value = model
        for attr in self.__name.split(".")[:-1]:
            value = getattr(value, attr)

        return self._target.format(value)
