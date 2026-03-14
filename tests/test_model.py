"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

from templex import TemplateModel
from templex.token import string


def test_validate_simple_model() -> None:
    """Models are valid if they provide at least a template."""

    class TestModel(TemplateModel):
        __template__ = "test"


def test_validate_simple_model_with_token() -> None:
    """Models are valid if they provide a template with a token (even unused)."""

    class TestModel(TemplateModel):
        __template__ = "test"
        token: str = string(".+")
