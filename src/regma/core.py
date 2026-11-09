"""Tokens of the templates and strictness of the fields."""

from __future__ import annotations

import abc
import enum
from enum import auto
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from typing_extensions import override

from regma.chain import Chain
from regma.chain import Reference
from regma.chain import RefSep
from regma.error import DefinitionError

if TYPE_CHECKING:
    from collections.abc import Mapping


T_value = TypeVar("T_value")


class SupportsToken(Protocol):
    """Anything a template can use as a token, such as a token or a model."""

    @property
    @abc.abstractmethod
    def __token__(self) -> Token[Any]:
        """Return the token standing for this object in the templates using it."""


class Token(abc.ABC, Generic[T_value]):
    """Anything a template can use as a token.

    A token converts its value from and to the string it matches: the regex of the
    token, such as a field, or the chain of its tokens, such as a template. Dotted names
    reach the tokens building the value of a token, and its aliases. A new kind of
    token subclasses this class, or :class:`Compound` to build its value from the
    values of its tokens. Any other object a template uses provides its token through
    ``__token__``, such as a model.
    """

    @property
    def __token__(self) -> Token[T_value]:
        """Return this token, which stands for itself in the templates using it."""
        return self

    @property
    def tokens(self) -> Mapping[str, Token[Any]]:
        """Return the tokens building the value of this token, by name.

        By default, the token holds no other token.
        """
        return {}

    @property
    def aliases(self) -> Mapping[str, Token[Any]]:
        """Return the aliases standing for tokens of this token, by name.

        The aliases are the other tokens which dotted tokens reach through this token,
        such as the templates declared on a model. By default, there is none.
        """
        return {}

    @property
    def chain(self) -> Chain | None:
        """Return the chain matching this token, None if it has a regex of its own."""
        return None

    def to_chain(self, name: str) -> Chain:
        """Return the chain standing for this token in a pattern using its dotted name.

        By default, the chain references the token.
        """
        return Chain("", [RefSep(Reference(name, self), "")])

    @abc.abstractmethod
    def to_regex(self) -> str:
        """Return the regex matching this token.

        Raises:
            DefinitionError: the token cannot be matched as a whole.
        """

    @abc.abstractmethod
    def parse_value(self, raw: Any) -> T_value:  # noqa: ANN401
        """Return the value of this token from the strings it matched.

        The string is the one matching its regex, or the strings matching its tokens,
        nested by name.

        Raises:
            ParseError: the string is not valid for the token.
        """

    @abc.abstractmethod
    def format_value(self, value: T_value) -> str:
        """Return the string of the given value of this token.

        Raises:
            FormatError: the value is not valid for the token.
        """

    def get_value(self, value: T_value, name: str) -> object:
        """Return the value of the named token from the value of this token.

        By default, the value holds the values of the tokens as attributes.
        """
        return getattr(value, name)


class Compound(Token[T_value]):
    """A token building its value from the values of its tokens, such as a model.

    Parsing builds the value of a compound from the values of its tokens, and dotted
    tokens reach them by name. A compound having a chain can also be used as a whole,
    matching its chain, such as a template. For example, a date written as
    year-month-day:

    class Date(Compound[datetime.date]):
        def __init__(self) -> None:
            self._tokens = {"year": integer(padding=4), "month": integer(padding=2),
                            "day": integer(padding=2)}
            self._chain = Chain.from_pattern("{year}-{month}-{day}", **self._tokens)

        @property
        def tokens(self) -> Mapping[str, Token[Any]]:
            return self._tokens

        @property
        def chain(self) -> Chain:
            return self._chain

        def build_value(self, values: dict[str, Any]) -> datetime.date:
            return datetime.date(**values)

    template = Template("{shot}_{date}/{date.year}", shot=string("[a-z]+"), date=Date())

    template.parse("foo_2024-05-01/2024")
    # {"shot": "foo", "date": datetime.date(2024, 5, 1)}
    """

    @property
    @abc.abstractmethod
    @override
    def tokens(self) -> Mapping[str, Token[Any]]:
        """Return the tokens building the value of the compound, by name."""

    @abc.abstractmethod
    def build_value(self, values: dict[str, Any]) -> T_value:
        """Return the value of the compound from the values of its tokens, by name."""

    @override
    def to_regex(self) -> str:
        return self._get_chain().to_regex()

    @override
    def parse_value(self, raw: Mapping[str, Any]) -> T_value:
        # The tokens without string have no value, the model reports the missing ones
        values = {
            name: token.parse_value(raw[name])
            for name, token in self.tokens.items()
            if name in raw
        }
        return self.build_value(values)

    @override
    def format_value(self, value: T_value) -> str:
        return self._get_chain().format(value, self)

    def _get_chain(self) -> Chain:
        """Return the chain of the compound, which matches the compound as a whole."""
        chain = self.chain
        if chain is None:
            msg = "the compound has no pattern of its own, reference its tokens instead"
            raise DefinitionError(msg)

        return chain


class ChainAlias(Token[T_value]):
    """A chain standing for references to tokens of its holder, the token holding it.

    A pattern using an alias uses the references of its chain instead, through the
    holder, such as the templates declared on a model. The value of an alias is the
    value of its holder.
    """

    def __init__(self, chain: Chain, holder: Token[T_value]) -> None:
        """Initialize the alias of the chain referencing tokens of the holder."""
        self._chain = chain
        self._holder = holder

    @property
    @override
    def chain(self) -> Chain:
        return self._chain

    @override
    def to_chain(self, name: str) -> Chain:
        # The references go through the holder, which the dotted name ends with
        holder_name = name.rpartition(".")[0]
        return self._chain.through_name(holder_name) if holder_name else self._chain

    @override
    def to_regex(self) -> str:
        return self._chain.to_regex()

    @override
    def parse_value(self, raw: Mapping[str, Any]) -> T_value:
        return self._holder.parse_value(raw)

    @override
    def format_value(self, value: T_value) -> str:
        return self._chain.format(value, self._holder)


class Strictness(enum.Flag):
    """State the strictness of field parsing and format."""

    NONE = 0
    PARSE = auto()
    FORMAT = auto()
    ALL = PARSE | FORMAT
