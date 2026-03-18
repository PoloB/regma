"""Chainable ABC, Separator, and Chain composite."""

from __future__ import annotations

import abc
import re
from typing import Generic
from typing import TypeVar
from typing import override


class RegexBuilder:
    """In charge of recursively building the regex from a given node."""

    def __init__(self) -> None:
        """Initialize the regex builder."""
        self._attribute_stack: list[str] = []
        self._seen_fields: set[str] = set()

    def build(self, attribute_name: str, template_node: TemplateNode) -> str:
        """Build the regex for the given field name and pattern."""
        attribute_name = attribute_name.replace(".", "__")
        field_name = "__".join([*self._attribute_stack, attribute_name])
        if field_name in self._seen_fields:
            return rf"(?P={field_name})"

        self._seen_fields.add(field_name)

        # Build the regex
        self._attribute_stack.append(attribute_name)
        regex = template_node.to_regex(self)
        self._attribute_stack.pop()
        return rf"(?P<{field_name}>{regex})"


class TemplateNode(abc.ABC):
    """Anything that can participate in a template chain."""

    @abc.abstractmethod
    def to_regex(self, builder: RegexBuilder) -> str:
        """Return the element as a regex."""

    @abc.abstractmethod
    def to_chain(self) -> Chain:
        """Return as a chain of inner template nodes."""


class Chain(TemplateNode):
    """Ordered sequence of template nodes."""

    def __init__(self, nodes: list[TemplateNode]) -> None:
        """Initialize the chain."""
        self.__nodes = nodes

    @property
    def nodes(self) -> list[TemplateNode]:
        """Return the ordered sequence of template nodes."""
        return self.__nodes

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return "".join(n.to_regex(builder) for n in self.__nodes)

    @override
    def to_chain(self) -> Chain:
        return self


class Separator(TemplateNode):
    """A literal string fragment in a chain."""

    def __init__(self, value: str) -> None:
        """Initialize the separator."""
        self.value = value

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return re.escape(self.value)

    @override
    def to_chain(self) -> Chain:
        return Chain([self])


T_value = TypeVar("T_value")


class AbstractField(TemplateNode, abc.ABC, Generic[T_value]):
    """Abstract base for all atomic fields."""

    @abc.abstractmethod
    def extract_value(self, raw: str) -> T_value:
        """Return the parsed value from the given string."""

    @override
    def to_chain(self) -> Chain:
        return Chain([self])
