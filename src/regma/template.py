"""Define templates used as usable object for creating bidirectional patterns."""

from __future__ import annotations

import collections
import re
from typing import TYPE_CHECKING
from typing import Any

from typing_extensions import override

from regma.chain import Chain
from regma.chain import ChainAlias
from regma.core import Node
from regma.core import Token
from regma.error import DefinitionError
from regma.error import ParseError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from regma.core import AnyNode


def _nest_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return the given dictionary keyed by dotted paths as nested dictionaries."""
    nested_data: dict[str, Any] = {}
    data_by_parent: dict[str, dict[str, Any]] = collections.defaultdict(dict)
    for path, value in data.items():
        parent, _, sub_path = path.partition(".")
        if sub_path:
            data_by_parent[parent][sub_path] = value
        else:
            nested_data[path] = value

    # The paths through a key take over a value given to the key itself
    for parent, sub_data in data_by_parent.items():
        nested_data[parent] = _nest_dict(sub_data)

    return nested_data


def _iter_field_paths(nodes: Mapping[str, AnyNode]) -> Iterator[str]:
    """Yield the dotted path of every field building the values of the given nodes."""
    for name, node in nodes.items():
        # An alias has no value of its own, it stands for nodes of its holder
        if isinstance(node, ChainAlias):
            continue

        sub_nodes = node.get_nodes()
        if not sub_nodes:
            yield name
            continue

        yield from (f"{name}.{path}" for path in _iter_field_paths(sub_nodes))


class _TemplateNode(Node[object, dict[str, Any]]):
    """The node of a template, whose value holds the value of each of its tokens."""

    def __init__(self, chain: Chain, nodes: Mapping[str, AnyNode]) -> None:
        """Initialize the node from a template chain and the nodes of its tokens."""
        self._chain = chain
        self._nodes = nodes

    @override
    def to_regex(self) -> str:
        return self._chain.to_regex()

    @override
    def to_chain(self) -> Chain:
        return self._chain

    @override
    def format_value(self, value: object) -> str:
        return self._chain.format(value)

    @override
    def parse_value(self, raw: dict[str, Any]) -> dict[str, Any]:
        # The tokens missing from the pattern have no string, so no value
        return {
            name: node.parse_value(raw[name])
            for name, node in self._nodes.items()
            if name in raw
        }


class Template(Token):
    """A template converting the values of its tokens from and to a string.

    A token is defined by a field, another template or a model, or any other
    :class:`Token`. The tokens of a model reach its fields and declared templates
    through dotted paths, and its value is an instance of the model:

    class Asset(Model):
        type: str = string("[a-z]+")
        code: str = string("[a-z]+")
        path = model_template("assets/{type}/{code}")

    template = Template("{asset.path}/{task}", asset=Asset, task=string("[a-z]+"))

    template.parse("assets/chr/toto/rig")
    # {"asset": Asset("chr", "toto"), "task": "rig"}

    The values only hold the tokens of the pattern, the other tokens are ignored.
    """

    def __init__(self, pattern: str, /, **tokens: Token) -> None:
        """Initialize the template from its pattern and the definitions of its tokens.

        Raises:
            DefinitionError: a token of the pattern is not defined or cannot be
                matched, or the pattern does not reference all its fields.
        """
        self._pattern = pattern
        nodes = {name: token.to_node(name) for name, token in tokens.items()}
        self._node = _TemplateNode(Chain.from_pattern(pattern, **nodes), nodes)
        self._regex = re.compile(self._node.to_regex())

        # Parsing builds the value of a token from all its fields
        captured = {name.replace("__", ".") for name in self._regex.groupindex}
        used_nodes = {
            name: nodes[name] for name in {path.partition(".")[0] for path in captured}
        }
        missing = sorted(set(_iter_field_paths(used_nodes)) - captured)
        if missing:
            msg = f"Template {pattern!r} does not reference fields {missing}"
            raise DefinitionError(msg)

    @property
    def pattern(self) -> str:
        """Return the pattern string of this template."""
        return self._pattern

    @property
    def chain(self) -> Chain:
        """Return the chain associated to this template."""
        return self._node.to_chain()

    @property
    def regex(self) -> re.Pattern[str]:
        """Return the regex string of this template."""
        return self._regex

    def format(self, value: object) -> str:
        """Format this template with the value of its tokens.

        The value holds the value of each token by key, or by attribute such as a model
        instance for the templates declared on its model.
        """
        return self._node.format_value(value)

    def parse(self, raw: str) -> dict[str, Any]:
        """Parse the given string and return the value of each token of the pattern.

        Raises:
            ParseError: the string does not match the template, or holds a value which
                is not valid for its field.
        """
        data = self._regex.match(raw)
        if not data:
            msg = f"Template regex {self._regex.pattern} does not match {raw}."
            raise ParseError(msg)

        # The regex groups are named after the token paths, with __ in place of dots
        groups = {
            name.replace("__", "."): value for name, value in data.groupdict().items()
        }
        return self._node.parse_value(_nest_dict(groups))

    @override
    def to_node(self, name: str) -> AnyNode:
        # The same node for any name, the template using it naming its references
        return self._node
