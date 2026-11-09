"""Define the chain structure responsible for storing a structured pattern."""

from __future__ import annotations

import abc
import enum
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar

from typing_extensions import override

from regma.error import DefinitionError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from regma.core import Token


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


class Reference:
    """A referenced token in a template construction."""

    def __init__(self, attribute_name: str, target: Token[Any]) -> None:
        """Initialize the reference to the given token, reached by the dotted name."""
        self.__name = attribute_name
        self._target = target
        # The dotted name reaches the token through the names of the tokens holding it
        *self._holder_names, self._target_name = attribute_name.split(".")

    @property
    def name(self) -> str:
        """Return the dotted name of the referenced token."""
        return self.__name

    @property
    def target(self) -> Token[Any]:
        """Return the referenced token."""
        return self._target

    def to_regex(self) -> str:
        """Return the regex of the referenced token.

        Raises:
            DefinitionError: the token cannot be matched as a whole.
        """
        try:
            return self._target.to_regex()
        except DefinitionError as e:
            msg = f"Token {{{self.__name}}}: {e}"
            raise DefinitionError(msg) from e

    def format(self, value: object, holder: Token[Any]) -> str:
        """Return the formatted value of the referenced token.

        The value is the one of the holder, the token holding the token which the
        dotted name starts with, such as the template whose chain holds the reference.
        """
        ref_value: Any = value
        for attr in self._holder_names:
            ref_value = holder.get_value(ref_value, attr)
            holder = holder.tokens[attr]

        ref_value = holder.get_value(ref_value, self._target_name)
        return self._target.format_value(ref_value)


class RefSep:
    """A reference followed by a separator."""

    def __init__(self, reference: Reference, suffix: str) -> None:
        """Initialize the field separator."""
        self._reference = reference
        self._suffix = suffix

    @property
    def reference(self) -> Reference:
        """Return the reference."""
        return self._reference

    @property
    def suffix(self) -> str:
        """Return the suffix."""
        return self._suffix


T_walk_value = TypeVar("T_walk_value", bound=Any)


class ChainVisitor(abc.ABC, Generic[T_walk_value]):
    """A generic chain visitor.

    You can subclass this class if you need a way to walk through the
    chain components.
    You are responsible for nesting the calls if necessary.
    """

    @abc.abstractmethod
    def walk(self, chain: Chain) -> T_walk_value:
        """Walks through the chain elements."""


class RegexBuilder(ChainVisitor[str]):
    """Builds the regex for the given chain."""

    def __init__(self) -> None:
        """Initialize the default regex builder."""
        self._seen_reference_names: set[str] = set()
        self._regexes: list[str] = []

    @override
    def walk(self, chain: Chain) -> str:

        regexes = [re.escape(chain.start_prefix)]
        for ref_sep in chain.iter_field_seps():
            reference = ref_sep.reference
            reference_name = reference.name.replace(".", "__")
            if reference_name in self._seen_reference_names:
                regexes.append(f"(?P={reference_name})")
                regexes.append(re.escape(ref_sep.suffix))
                continue

            self._seen_reference_names.add(reference_name)
            sub_chain = reference.target.chain

            sub_regex = (
                self.walk(sub_chain.through_name(reference.name))
                if sub_chain is not None
                else reference.to_regex()
            )
            regexes.append(rf"(?P<{reference_name}>{sub_regex})")
            regexes.append(re.escape(ref_sep.suffix))

        return "".join(regexes)


def _reach_chain(tokens: Mapping[str, Token[Any]], token_name: str) -> Chain:
    """Return the chain standing for the dotted token reached from the given tokens."""
    if token_name.startswith("_") or token_name.endswith("_") or "__" in token_name:
        msg = (
            f"Token {token_name} start or end with underscore or contains a "
            f"double underscore"
        )
        raise DefinitionError(msg)

    attributes = token_name.split(".")
    if "" in attributes:
        message = f"Invalid token {token_name!r}"
        raise DefinitionError(message)

    # The dotted name reaches a token or an alias through the tokens holding it
    *holder_names, name = attributes
    aliases: Mapping[str, Token[Any]] = {}
    for depth, attr in enumerate(holder_names, start=1):
        holder = tokens.get(attr)
        if holder is None:
            path = ".".join(attributes[:depth])
            msg = f"Invalid token {token_name!r}: {path!r} is not a token"
            raise DefinitionError(msg)

        tokens, aliases = holder.tokens, holder.aliases

    token = aliases.get(name)
    if token is None:
        token = tokens.get(name)
    if token is None:
        msg = f"Invalid token {token_name!r}: neither a token nor an alias"
        raise DefinitionError(msg)

    return token.to_chain(token_name)


class Chain:
    """Ordered sequence of references, each followed by its separator."""

    @classmethod
    def empty(cls) -> Chain:
        """Return an empty chain."""
        return cls("", [])

    @classmethod
    def from_pattern(cls, pattern: str, /, **tokens: Token[Any]) -> Chain:
        """Return the chain of the pattern using the given tokens.

        A dotted token reaches a token or an alias through the tokens holding it, and
        each token stands for the chain of its own in the pattern.

        Raises:
            DefinitionError: a token of the pattern is invalid or reaches nothing.
        """
        token_re = Delimiter.CURLY.token_re()
        chain = Chain.empty()
        cursor = 0

        for m in token_re.finditer(pattern):
            start, end = m.span()
            chain.append_separator(pattern[cursor:start])
            chain.append_chain(_reach_chain(tokens, m.group(1)))
            cursor = end

        chain.append_separator(pattern[cursor:])
        return chain

    def __init__(self, start_separator: str, field_seps: list[RefSep]) -> None:
        """Initialize the chain."""
        self._prefix = start_separator
        self._ref_seps = field_seps

    def through_name(self, attribute_name: str) -> Chain:
        """Return a new chain where all the references go through the given attribute."""
        new_ref_seps: list[RefSep] = []
        for field_sep in self._ref_seps:
            new_ref = Reference(
                f"{attribute_name}.{field_sep.reference.name}",
                field_sep.reference.target,
            )
            new_ref_seps.append(RefSep(new_ref, field_sep.suffix))

        return self.__class__(self._prefix, new_ref_seps)

    def append_reference(self, reference: Reference) -> None:
        """Append the given reference to the chain."""
        self._ref_seps.append(RefSep(reference, ""))

    def append_chain(self, chain: Chain) -> None:
        """Append the separators and references of the given chain to the chain."""
        self.append_separator(chain.start_prefix)
        for ref_sep in chain.iter_field_seps():
            self.append_reference(ref_sep.reference)
            self.append_separator(ref_sep.suffix)

    def append_separator(self, separator: str) -> None:
        """Add the string to the end of the chain."""
        # Adjacent tokens and spliced chains add empty separators, changing nothing
        if not separator:
            return

        if not self._ref_seps:
            self._prefix = self._prefix + separator
        else:
            last_field_sep = self._ref_seps[-1]
            self._ref_seps[-1] = RefSep(
                last_field_sep.reference, last_field_sep.suffix + separator
            )

    @property
    def start_prefix(self) -> str:
        """Return the first prefix of the chain."""
        return self._prefix

    def iter_field_seps(self) -> Iterator[RefSep]:
        """Return the references in order, each followed by its separator."""
        yield from self._ref_seps

    def to_regex(self) -> str:
        """Return the regex associated to the chain."""
        return RegexBuilder().walk(self)

    def format(self, value: object, holder: Token[Any]) -> str:
        """Return the formatted string of this chain.

        The value is the one of the holder, the token holding the tokens which the
        references start with, such as the template of the chain.
        """
        return self._prefix + "".join(
            f"{n.reference.format(value, holder)}{n.suffix}" for n in self._ref_seps
        )
