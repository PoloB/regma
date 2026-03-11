"""templex.exceptions — all library-specific errors."""


class TemplexError(Exception):
    """Base for all templex errors."""


class ParseError(TemplexError):
    """Raised when a string cannot be parsed by a template."""


class FormatError(TemplexError):
    """Raised when a value cannot be formatted by a token."""


class DefinitionError(TemplexError):
    """Raised at class definition time when a TemplateModel is invalid."""


class ConsistencyError(ParseError):
    """Raised when the same slot matches different values at different positions."""
