"""Object-based, bidirectional string templating with declarative result types.

from regma import TemplateModel, Field, Slot
from regma.fields import StrField, IntField, ChoiceField
"""

from regma.core import Compound
from regma.core import Token
from regma.error import DefinitionError
from regma.error import FormatError
from regma.error import ParseError
from regma.error import RegmaError
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import string
from regma.model import Model
from regma.model import model_template
from regma.model import reference
from regma.template import Template

__all__ = [
    "Compound",
    "DefinitionError",
    "FormatError",
    "Model",
    "ParseError",
    "RegmaError",
    "Template",
    "Token",
    "choice",
    "custom_field",
    "integer",
    "model_template",
    "reference",
    "string",
]
