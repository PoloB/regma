"""regma.exceptions — all library-specific errors."""


class regmaError(Exception):
    """Base for all regma errors."""


class ValidationError(regmaError):
    """Raised when a value is not valid."""


class ParseError(regmaError):
    """Raised when a string cannot be parsed by a template."""


class FormatError(regmaError):
    """Raised when a value cannot be formatted by a field."""


class DefinitionError(regmaError):
    """Raised at class definition time when a TemplateModel is invalid."""
