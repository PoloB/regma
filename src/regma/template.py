"""Define templates used as usable object for creating bidirectional patterns."""

from __future__ import annotations

import collections
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import Any

from typing_extensions import override

from regma.chain import Chain
from regma.core import Compound
from regma.error import DefinitionError
from regma.error import ParseError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from regma.core import SupportsToken
    from regma.core import Token


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


def _iter_field_paths(tokens: Mapping[str, Token[Any]]) -> Iterator[str]:
    """Yield the dotted path of every field building the values of the given tokens.

    A field is a token holding no other token, its value being parsed from its string.
    """
    for name, token in tokens.items():
        sub_tokens = token.tokens
        if sub_tokens:
            yield from (f"{name}.{path}" for path in _iter_field_paths(sub_tokens))
        else:
            yield name


class Template(Compound[dict[str, Any]]):
    """A template converting the values of its tokens from and to a string.

    A token is a field, another template or a model, or any other :class:`Token`.
    Dotted tokens reach the fields and the declared templates of a model, and the value
    of a model is an instance of the model:

    class Asset(Model):
        type: str = string("[a-z]+")
        code: str = string("[a-z]+")
        path = model_template("assets/{type}/{code}")

    template = Template("{asset.path}/{task}", asset=Asset, task=string("[a-z]+"))

    template.parse("assets/chr/toto/rig")
    # {"asset": Asset("chr", "toto"), "task": "rig"}

    The values only hold the tokens of the pattern, the other tokens are ignored.
    """

    def __init__(self, pattern: str, /, **tokens: SupportsToken) -> None:
        """Initialize the template from its pattern and the definitions of its tokens.

        Raises:
            DefinitionError: a token of the pattern is not defined or cannot be
                matched, or the pattern does not reference all its fields.
        """
        self._pattern = pattern
        # A model is not a token itself, it provides the token building its instances
        all_tokens = {name: token.__token__ for name, token in tokens.items()}
        self._chain = Chain.from_pattern(pattern, **all_tokens)
        self._regex = re.compile(self._chain.to_regex())

        # The tokens of the pattern, which dotted tokens reach through the template
        used = {
            ref_sep.reference.name.partition(".")[0]
            for ref_sep in self._chain.iter_field_seps()
        }
        self._tokens = {
            name: token for name, token in all_tokens.items() if name in used
        }

        # Parsing builds the value of a token from all its fields
        captured = {name.replace("__", ".") for name in self._regex.groupindex}
        missing = sorted(set(_iter_field_paths(self._tokens)) - captured)
        if missing:
            msg = f"Template {pattern!r} does not reference fields {missing}"
            raise DefinitionError(msg)

    @property
    def pattern(self) -> str:
        """Return the pattern string of this template."""
        return self._pattern

    @property
    @override
    def tokens(self) -> Mapping[str, Token[Any]]:
        """Return the tokens of the pattern, by name."""
        return self._tokens

    @property
    @override
    def chain(self) -> Chain:
        """Return the chain associated to this template."""
        return self._chain

    @property
    def regex(self) -> re.Pattern[str]:
        """Return the regex string of this template."""
        return self._regex

    def format(self, value: object) -> str:
        """Format this template with the value of its tokens.

        The value holds the value of each token by key, or by attribute such as a model
        instance for the templates declared on its model.
        """
        return self._chain.format(value, self)

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
        return self.parse_value(_nest_dict(groups))

    @override
    def build_value(self, values: dict[str, Any]) -> dict[str, Any]:
        return values

    @override
    def get_value(self, value: object, name: str) -> object:
        # The templates declared on a model also format the instances of the model
        return value[name] if isinstance(value, Mapping) else getattr(value, name)
