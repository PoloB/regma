"""Object-based, bidirectional string templating with declarative result types.

from regma import TemplateModel, Field, Slot
from regma.fields import StrField, IntField, ChoiceField
"""

from regma.core import TemplateNode
from regma.error import DefinitionError
from regma.error import FormatError
from regma.error import ParseError
from regma.error import RegmaError
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import string
from regma.model import Model
from regma.model import reference
from regma.template import ModelTemplate
from regma.template import Template

__all__ = [
    "DefinitionError",
    "FormatError",
    "Model",
    "ModelTemplate",
    "ParseError",
    "RegmaError",
    "Template",
    "TemplateNode",
    "choice",
    "custom_field",
    "integer",
    "reference",
    "string",
]
