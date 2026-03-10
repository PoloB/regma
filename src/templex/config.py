"""
templex.config
~~~~~~~~~~~~~~~~
Delimiter enum and global library configuration.

    from templex import Delimiter
    import templex

    # Global default (affects all models without a Meta.delimiter)
    templex.configure(delimiter=Delimiter.ANGLE)

    # Per-model override via inner Meta class
    class MyModel(TemplateModel):
        class Meta:
            delimiter = Delimiter.SQUARE
        ...
"""

from __future__ import annotations

import enum
import re


class Delimiter(enum.Enum):
    """
    Supported token delimiter styles for string templates.

    Each variant carries its open/close characters and can compile
    its own token regex — template_parser.py stays delimiter-agnostic.

    Examples
    --------
    CURLY  →  {asset_source.type}/{asset_source}
    ANGLE  →  <asset_source.type>/<asset_source>
    SQUARE →  [asset_source.type]/[asset_source]
    """

    CURLY = ("{", "}")
    ANGLE = ("<", ">")
    SQUARE = ("[", "]")

    @property
    def token_open(self) -> str:
        return self.value[0]

    @property
    def token_close(self) -> str:
        return self.value[1]

    def token_re(self) -> re.Pattern[str]:
        """
        Compile and return the regex that matches one token placeholder,
        capturing (name, optional_subfield).
        """
        o = re.escape(self.token_open)
        c = re.escape(self.token_close)
        ident = r"[A-Za-z_][A-Za-z0-9_]*"
        return re.compile(rf"{o}({ident}(?:\.{ident})*){c}")

    def __repr__(self) -> str:
        return f"{self.__class__}.{self.name}"


# ── Global configuration ──────────────────────────────────────────────────────


class _Config:
    """Holds library-wide defaults. Mutated by templex.configure()."""

    def __init__(self) -> None:
        self.delimiter: Delimiter = Delimiter.CURLY

    def __repr__(self) -> str:
        return f"_Config(delimiter={self.delimiter!r})"


#: Singleton — import and mutate via templex.configure()
_config = _Config()


def configure(*, delimiter: Delimiter | None = None) -> None:
    """
    Set library-wide defaults.

        import templex
        templex.configure(delimiter=templex.Delimiter.ANGLE)

    Per-model overrides (via ``class Meta``) always take precedence.
    """
    if delimiter is not None:
        if not isinstance(delimiter, Delimiter):
            raise TypeError(
                f"delimiter must be a Delimiter instance, got {type(delimiter).__name__!r}"
            )
        _config.delimiter = delimiter


def get_delimiter() -> Delimiter:
    """Return the current global default delimiter."""
    return _config.delimiter
