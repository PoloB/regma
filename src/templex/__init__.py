"""Object-based, bidirectional string templating with declarative result types.

from templex import TemplateModel, Field, Slot
from templex.fields import StrField, IntField, ChoiceField
"""

from templex.core import Chain
from templex.core import Separator
from templex.core import TemplateNode
from templex.error import ConsistencyError
from templex.error import DefinitionError
from templex.error import FormatError
from templex.error import ParseError
from templex.error import TemplexError
from templex.field import ChoiceField
from templex.field import IntField
from templex.field import StrField
from templex.model import Delimiter
from templex.model import TemplateModel

__all__ = [
    "Chain",
    "ChoiceField",
    "ConsistencyError",
    "DefinitionError",
    "Delimiter",
    "FormatError",
    "IntField",
    "ParseError",
    "Separator",
    "StrField",
    "TemplateModel",
    "TemplateNode",
    "TemplexError",
]
