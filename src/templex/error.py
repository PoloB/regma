"""templex.exceptions — all library-specific errors."""


class TemplexError(Exception):
    """Base for all templex errors."""


class ValidationError(TemplexError):
    """Raised when a value is not valid."""


class ParseError(TemplexError):
    """Raised when a string cannot be parsed by a template."""


class FormatError(TemplexError):
    """Raised when a value cannot be formatted by a field."""


class DefinitionError(TemplexError):
    """Raised at class definition time when a TemplateModel is invalid."""
