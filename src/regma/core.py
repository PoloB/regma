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


AnyNode = Node[Any, Any]


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
