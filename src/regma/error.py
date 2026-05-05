"""regma.exceptions — all library-specific errors."""
from __future__ import annotations


class RegmaError(Exception):
    """Base for all regma errors."""


class ValidationError(RegmaError):
    """Raised when a value is not valid."""


class ParseError(RegmaError):
    """Raised when a string cannot be parsed by a template."""


class FormatError(RegmaError):
    """Raised when a value cannot be formatted by a field."""


class DefinitionError(RegmaError):
    """Raised at class definition time when a TemplateModel is invalid."""


class ValidityError(Exception):
    """Exception raised when validation fails."""
