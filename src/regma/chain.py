"""Define the chain structure responsible for storing a structured pattern."""

from __future__ import annotations

import abc
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar

from typing_extensions import override

from regma.core import AnyNode
from regma.core import Delimiter
from regma.core import Node
from regma.core import Token
from regma.error import DefinitionError

if TYPE_CHECKING:
    from collections.abc import Iterator


class Reference:
    """A referenced element in a template construction."""

    def __init__(self, attribute_name: str, target: AnyNode) -> None:
        """Initialize a FieldReference node."""
        self.__name = attribute_name
        self._target = target

    @property
    def name(self) -> str:
        """Return the name of the field attribute."""
        return self.__name

    @property
    def target(self) -> AnyNode:
        """Return the referenced element."""
        return self._target

    def to_regex(self) -> str:
        """Return the reference as a regex."""
        return self.target.to_regex()

    def format(self, value: object) -> str:
        """Return the formatted value for the field.

        The value holds the value of each token by key, or by attribute for models.
        """
        ref_value: Any = value
        for attr in self.__name.split("."):
            ref_value = (
                ref_value[attr]
                if isinstance(ref_value, Mapping)
                else getattr(ref_value, attr)
            )

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
            sub_chain = reference.target.to_chain()

            sub_regex = (
                self.walk(sub_chain.through_name(reference.name))
                if sub_chain
                else reference.to_regex()
            )
            regexes.append(rf"(?P<{reference_name}>{sub_regex})")
            regexes.append(re.escape(ref_sep.suffix))

        return "".join(regexes)


def _get_reference(tokens: dict[str, AnyNode], token_name: str) -> Reference:
    """Return the field reference of the given token name."""
    if token_name.startswith("_") or token_name.endswith("_") or "__" in token_name:
        msg = (
            f"Token {token_name} start or end with underscore or contains a "
            f"double underscore"
        )
        raise DefinitionError(msg)

    # Find the targeted field
    attributes = token_name.split(".")
    if "" in attributes:
        message = f"Invalid token {token_name!r}"
        raise DefinitionError(message)

    current_attr = attributes[0]

    try:
        lookup_node: AnyNode = tokens[current_attr]
    except KeyError as e:
        msg = f"No element {current_attr!r} provided to template"
        raise DefinitionError(msg) from e

    for attr in attributes[1:]:
        sub_node = lookup_node.get_nodes().get(attr)
        if sub_node is None:
            msg = f"Invalid token {token_name!r}: {current_attr!r} has no {attr!r}"
            raise DefinitionError(msg)

        current_attr = f"{current_attr}.{attr}"
        lookup_node = sub_node

    return Reference(token_name, lookup_node)


class Chain:
    """Ordered sequence of template nodes."""

    @classmethod
    def empty(cls) -> Chain:
        """Return an empty chain."""
        return cls("", [])

    @classmethod
    def from_pattern(cls, pattern: str, /, **kwargs: AnyNode) -> Chain:
        """Return a chain constructed from the given pattern.

        Raises:
            DefinitionError: the chain is not constructed properly.
        """
        token_re = Delimiter.CURLY.token_re()
        chain = Chain.empty()
        cursor = 0

        for m in token_re.finditer(pattern):
            start, end = m.span()
            attr_name: str = m.group(1)
            chain.append_separator(pattern[cursor:start])

            reference = _get_reference(kwargs, attr_name)
            if isinstance(reference.target, ChainAlias):
                # The alias stands for its references, through the node holding it
                holder = attr_name.rpartition(".")[0]
                alias_chain = reference.target.to_chain()
                chain.append_chain(
                    alias_chain.through_name(holder) if holder else alias_chain
                )
            else:
                chain.append_reference(reference)

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
        """Return the ordered sequence of template nodes."""
        yield from self._ref_seps

    def to_regex(self) -> str:
        """Return the regex associated to the chain."""
        return RegexBuilder().walk(self)

    def format(self, value: object) -> str:
        """Return the formatted string of this chain."""
        return self._prefix + "".join(
            f"{n.reference.format(value)}{n.suffix}" for n in self._ref_seps
        )


class ChainAlias(Token, Node[object, dict[str, Any]]):
    """A chain standing for references through the node holding it.

    A template does not reference an alias as a node: it splices the chain of the alias
    where the alias is used, its references going through the node holding the alias.
    For example, the templates declared on a model are aliases of the model node, as
    they stand for references to the fields of the model. As a token, an alias stands
    for references to the other tokens of the template.
    """

    def __init__(self, chain: Chain) -> None:
        """Initialize the alias of the given chain."""
        self._chain = chain

    @override
    def to_node(self, name: str) -> ChainAlias:
        return self

    @override
    def to_regex(self) -> str:
        return self._chain.to_regex()

    @override
    def to_chain(self) -> Chain:
        return self._chain

    @override
    def get_nodes(self) -> Mapping[str, AnyNode]:
        # The nodes of the chain are reached through the node holding the alias
        return {}

    @override
    def format_value(self, value: object) -> str:
        # The value of an alias is the value of the node holding it
        return self._chain.format(value)

    @override
    def parse_value(self, raw: dict[str, Any]) -> object:
        return raw
