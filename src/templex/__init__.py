"""
templex
~~~~~~~
Object-based, bidirectional string templating with declarative result types.

    from templex import TemplateModel, Field, Slot
    from templex.tokens import StrToken, IntToken, ChoiceToken
"""

from templex.core import Chain
from templex.core import Separator
from templex.core import TemplateNode
from templex.error import ConsistencyError
from templex.error import DefinitionError
from templex.error import FormatError
from templex.error import ParseError
from templex.error import TemplexError
from templex.model import Delimiter
from templex.model import TemplateModel
from templex.token import ChoiceToken
from templex.token import IntToken
from templex.token import StrToken

__all__ = [
    "Chain",
    "ChoiceToken",
    "ConsistencyError",
    "DefinitionError",
    "Delimiter",
    "FormatError",
    "IntToken",
    "ParseError",
    "Separator",
    "StrToken",
    "TemplateModel",
    "TemplateNode",
    "TemplexError",
]
