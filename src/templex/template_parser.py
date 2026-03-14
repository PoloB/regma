"""Parses a format-string template into a Chain of Chainable nodes.

Syntax (delimiter-agnostic — works for CURLY, ANGLE, SQUARE):

- ``{name}``        → :class:`~templex.slot.BoundSlot` or inline token node
- ``{name.field}``  → :class:`~templex.slot.BoundField` on a Slot
- literal text      → :class:`~templex.core.Separator`

The delimiter style is passed in as a :class:`~templex.config.Delimiter` enum
value; the parser itself has no knowledge of which style is in use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from typing_extensions import override

from templex.core import AbstractToken
from templex.core import Chain
from templex.core import RegexBuilder
from templex.core import Separator
from templex.core import TemplateNode
from templex.error import DefinitionError

if TYPE_CHECKING:
    from templex.model import TemplateModelMeta


class TokenReference(TemplateNode):
    """A referenced token in a model template.

    This is used in the template parsing.
    """

    def __init__(
        self,
        attribute_name: str,
        target_token: AbstractToken[Any],
    ) -> None:
        """Initialize a TokenReference node."""
        self.__name = attribute_name
        self._token = target_token

    @property
    def target(self) -> AbstractToken[Any]:
        """Return the token referenced as a target token."""
        return self._token

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return builder.build(self.__name, self._token)

    @override
    def to_chain(self) -> Chain:
        return Chain([self])


def parse_template(
    template_model: TemplateModelMeta,
) -> Chain:
    """Convert a template string into a :class:`~templex.core.Chain`."""
    template = template_model.__template__
    delimiter = template_model.__delimiter__
    token_re = delimiter.token_re()
    nodes: list[TemplateNode] = []
    cursor = 0
    existing_token_references: dict[str, TokenReference] = {}

    for m in token_re.finditer(template):
        start, end = m.span()
        attr_name: str = m.group(1)
        attributes = attr_name.split(".")

        if start > cursor:
            nodes.append(Separator(template[cursor:start]))

        # Find the targeted token
        token_reference: TokenReference | None = None
        lookup_obj = template_model
        attribute_full_name = ""
        for attr in attributes:
            attribute_full_name += attr
            token_reference = existing_token_references.get(attr)

            if token_reference:
                lookup_obj = getattr(lookup_obj, attr)
                attribute_full_name += "."
                continue

            try:
                lookup_obj = getattr(lookup_obj, attr)
            except AttributeError as e:
                msg = (
                    f"{template_model.__name__}: in reference {m.group()}, "
                    f"could not find attribute {attr!r} in {lookup_obj}"
                )
                raise DefinitionError(msg) from e

            if not isinstance(lookup_obj, AbstractToken):
                msg = (
                    f"{template_model.__name__}: in reference {m.group()}, "
                    f"attribute {attribute_full_name!r} is not an AbstractToken"
                )
                raise DefinitionError(msg)
            token_reference = TokenReference(attribute_full_name, lookup_obj)
            existing_token_references[attribute_full_name] = token_reference
            attribute_full_name += "."

        if token_reference is None:
            msg = f"Invalid attribute {attr_name}"
            raise DefinitionError(msg)

        nodes.append(token_reference)
        cursor = end

    if cursor < len(template):
        nodes.append(Separator(template[cursor:]))

    return Chain(nodes)
