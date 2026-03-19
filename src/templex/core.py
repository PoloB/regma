"""Chainable ABC, Separator, and Chain composite."""

from __future__ import annotations

import abc
import re
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar
from typing import override

if TYPE_CHECKING:
    from templex.engine import AbstractRegexEngine
    from templex.model import TemplateModel


class TemplateNode(abc.ABC):
    """Anything that can participate in a template chain."""

    @abc.abstractmethod
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        """Return the element as a regex."""


class FormatableNode(TemplateNode, abc.ABC):
    """A node that can contribute to formatting a template model."""

    @abc.abstractmethod
    def to_chain(self) -> Chain:
        """Return as a chain of inner template nodes."""

    @abc.abstractmethod
    def format(self, model: TemplateModel) -> str:
        """Return the formatted string of this template node."""


class Chain(FormatableNode):
    """Ordered sequence of template nodes."""

    def __init__(self, nodes: list[FormatableNode]) -> None:
        """Initialize the chain."""
        self.__nodes = nodes

    @property
    def nodes(self) -> list[FormatableNode]:
        """Return the ordered sequence of template nodes."""
        return self.__nodes

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        return "".join(n.to_regex(engine) for n in self.__nodes)

    @override
    def to_chain(self) -> Chain:
        return self

    @override
    def format(self, model: TemplateModel) -> str:
        """Return the formatted string of this chain."""
        return "".join(n.format(model) for n in self.__nodes)


class Separator(FormatableNode):
    """A literal string fragment in a chain."""

    def __init__(self, value: str) -> None:
        """Initialize the separator."""
        self.value = value

    @override
    def to_regex(self, engine: AbstractRegexEngine) -> str:
        return re.escape(self.value)

    @override
    def to_chain(self) -> Chain:
        return Chain([self])

    @override
    def format(self, model: TemplateModel) -> str:
        return self.value


T_value = TypeVar("T_value")


class AbstractField(TemplateNode, abc.ABC, Generic[T_value]):
    """Abstract base for all atomic fields."""

    @abc.abstractmethod
    def extract_value(self, raw: str) -> T_value:
        """Return the parsed value from the given string."""

    @abc.abstractmethod
    def format_value(self, value: T_value) -> str:
        """Return the formatted value for the given string."""
