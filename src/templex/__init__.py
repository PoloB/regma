"""
templex
~~~~~~~
Object-based, bidirectional string templating with declarative result types.

    from templex import TemplateModel, Field, Slot
    from templex.tokens import StrToken, IntToken, ChoiceToken
"""

# _coerce must be imported first: it injects the coercion function into
# templex.core so that Chainable.__rshift__ works without a local import.
from templex.config import Delimiter, configure, get_delimiter
from templex.core import Chain, Separator, Templatable
from templex.exceptions import (
    ConsistencyError,
    DefinitionError,
    FormatError,
    ParseError,
    TemplexError,
)
from templex.model import TemplateModel
from templex.slot import BoundField, BoundSlot, Slot
from templex.token import ChoiceToken, IntToken, StrToken

__all__ = [
    "Templatable",
    "Chain",
    "Separator",
    "Delimiter",
    "configure",
    "get_delimiter",
    "TemplateModel",
    "Slot",
    "BoundSlot",
    "BoundField",
    "StrToken",
    "IntToken",
    "ChoiceToken",
    "TemplexError",
    "ParseError",
    "FormatError",
    "DefinitionError",
    "ConsistencyError",
]
