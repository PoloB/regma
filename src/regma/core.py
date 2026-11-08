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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from regma.chain import Chain


T_format = TypeVar("T_format", bound=Any)
T_parse = TypeVar("T_parse", bound=Any)


class Node(abc.ABC, Generic[T_format, T_parse]):
    """Anything that can participate in a template chain."""

    @abc.abstractmethod
    def to_regex(self) -> str:
        """Return the element as a regex."""

    @abc.abstractmethod
    def to_chain(self) -> Chain | None:
        """Return the element as chain."""

    @abc.abstractmethod
    def format_value(self, value: T_format) -> str:
        """Format the given value to a string."""

    @abc.abstractmethod
    def parse_value(self, raw: T_parse) -> T_format:
        """Parse the given string and return the parsed value."""

    def get_nodes(self) -> Mapping[str, AnyNode]:
        """Return the nodes that dotted tokens reach through this node, by name.

        By default, they are the nodes referenced by the chain of the node.
        """
        chain = self.to_chain()
        if chain is None:
            return {}

        return {
            ref_sep.reference.name: ref_sep.reference.target
            for ref_sep in chain.iter_field_seps()
        }


AnyNode = Node[Any, Any]


class Token(abc.ABC):
    """Anything a template can use as a token, such as a field, a template or a model.

    A template builds its chain from the nodes of its tokens: a dotted token reaches
    the nodes of a node, and the regex builder expands the chain of a node having one.
    A new kind of token only provides its node, either a leaf with a regex or a node
    building its value from the nodes of its chain.
    """

    @abc.abstractmethod
    def to_node(self, name: str) -> AnyNode:
        """Return the node of this token in the chain of a template using it by name."""


class Strictness(enum.Flag):
    """State the strictness of field parsing and format."""

    NONE = 0
    PARSE = auto()
    FORMAT = auto()
    ALL = PARSE | FORMAT


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
