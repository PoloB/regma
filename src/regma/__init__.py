"""Object-based, bidirectional string templating with declarative result types.

from regma import TemplateModel, Field, Slot
from regma.fields import StrField, IntField, ChoiceField
"""

from regma.core import TemplateNode
from regma.error import DefinitionError
from regma.error import FormatError
from regma.error import ParseError
from regma.error import regmaError
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import reference
from regma.field import string
from regma.model import TemplateModel

__all__ = [
    "DefinitionError",
    "FormatError",
    "ParseError",
    "TemplateModel",
    "TemplateNode",
    "regmaError",
    "choice",
    "custom_field",
    "integer",
    "reference",
    "string",
]
