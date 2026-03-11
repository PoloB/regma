"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

from templex import TemplateModel
from templex.core import __all_token_cls__


def test_all_tokens_are_in_field_specifiers() -> None:
    """Make sure all defined token classes are used as field specifiers."""
    token_specifiers = set(TemplateModel.__dataclass_transform__["field_specifiers"])
    token_classes = set(__all_token_cls__)
    assert token_classes == token_specifiers
