"""Define templates used as usable object for creating bidirectional patterns."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

from regma import ParseError
from regma.chain import Chain
from regma.chain import ChainCompound
from regma.field import AbstractField
from regma.field import BoundField

if TYPE_CHECKING:
    from regma.core import AnyNode
    from regma.model import Model

T_mod = TypeVar("T_mod", bound="Model")


class Template:
    """A template that can only be used for formatting."""

    def __init__(self, pattern: str, **kwargs: AbstractField[Any] | Template) -> None:
        """Initialize the template."""
        all_kwargs: dict[str, AnyNode] = {}
        for name, field in kwargs.items():
            if isinstance(field, AbstractField):
                all_kwargs[name] = BoundField(name, field)
            elif isinstance(field, Template):
                all_kwargs[name] = ChainCompound(field.chain)
        self._pattern = pattern
        self._tokens = all_kwargs
        self._chain = Chain.from_pattern(pattern, **self._tokens)
        self._regex = re.compile(self._chain.to_regex())

    @property
    def pattern(self) -> str:
        """Return the pattern string of this template."""
        return self._pattern

    @property
    def chain(self) -> Chain:
        """Return the chain associated to this template."""
        return self._chain

    @property
    def regex(self) -> re.Pattern[str]:
        """Return the regex string of this template."""
        return self._regex

    def format(self, value: dict[str, Any]) -> str:
        """Format this template with the given value."""
        return self._chain.format(value)

    def parse(self, raw: str) -> dict[str, Any]:
        """Parse this template with the given string."""
        data = self._regex.match(raw)
        if not data:
            msg = f"Template regex {self._regex.pattern} does not match {raw}."
            raise ParseError(msg)

        # Reconstruct the nested dict from data
        nested_data: dict[str, Any] = {}

        for key, value in data.groupdict().items():
            split_key = key.split("__")

            sub_data = nested_data
            for sub_key in split_key[:-1]:
                new_data: dict[str, Any] = nested_data.get(sub_key, {})
                if not isinstance(new_data, dict):
                    new_data = {}
                    nested_data[sub_key] = new_data
                sub_data = new_data

            sub_data[split_key[-1]] = value

        converted_data: dict[str, Any] = {}

        for token_name, token in self._tokens.items():
            converted_data[token_name] = token.parse_value(nested_data[token_name])

        return converted_data
