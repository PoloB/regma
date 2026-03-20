"""Object-based, bidirectional string templating with declarative result types.

from templex import TemplateModel, Field, Slot
from templex.fields import StrField, IntField, ChoiceField
"""

from templex.core import TemplateNode
from templex.error import DefinitionError
from templex.error import FormatError
from templex.error import ParseError
from templex.error import TemplexError
from templex.field import choice
from templex.field import custom_field
from templex.field import integer
from templex.field import reference
from templex.field import string
from templex.model import TemplateModel

__all__ = [
    "DefinitionError",
    "FormatError",
    "ParseError",
    "TemplateModel",
    "TemplateNode",
    "TemplexError",
    "choice",
    "custom_field",
    "integer",
    "reference",
    "string",
]
