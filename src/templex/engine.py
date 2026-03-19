"""Definition of regex engines."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from templex import TemplateNode


class AbstractRegexEngine(abc.ABC):
    """In charge of constructing the regex using for parsing model strings."""

    @abc.abstractmethod
    def build(self, attribute_name: str, template_node: TemplateNode) -> str:
        """Build the regex for the given field name and pattern."""


class BuiltinRegexEngine(AbstractRegexEngine):
    """Regex engine using the python re module."""

    def __init__(self) -> None:
        """Initialize the regex engine."""
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
