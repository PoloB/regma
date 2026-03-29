"""Test the validation of models."""

from __future__ import annotations

from regma import TemplateModel
from regma import choice
from regma import string
from regma.validation import validate_template
from tests.conftest import SimpleTestModel


def test_simple_model_is_valid() -> None:
    """Make sure the simple test model is valid."""
    result = validate_template(SimpleTestModel)
    assert result.is_valid()
    assert not result.language.is_finite
    assert result.language.cardinality is None
    assert result.language.examples == set()
    assert result.ambiguity.is_bijective
    assert result.ambiguity.witness is None
    assert result.ambiguity.split_point is None


def test_finite_model() -> None:
    """Make sure the finite test model is valid."""

    class FiniteModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = choice(["chr", "prp"])
        bar: str = choice(["up", "down"])

    result = validate_template(FiniteModel)
    assert result.is_valid()
    assert result.language.is_finite
    assert result.language.cardinality == 4  # noqa: PLR2004
    assert result.language.examples == {"chr_up", "prp_up", "chr_down", "prp_down"}
    assert result.ambiguity.is_bijective
    assert result.ambiguity.witness is None
    assert result.ambiguity.split_point is None


def test_non_bijective_model_succeed() -> None:
    """Make sure a bijective model succeed validation."""

    class NonBijectiveModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r"[a-zA-Z]+")
        bar: str = string(r"\d+")

    result = validate_template(NonBijectiveModel)
    assert result.is_valid()
    assert not result.language.is_finite
    assert result.language.cardinality is None
    assert result.ambiguity.is_bijective


def test_non_bijective_model_fails() -> None:
    """Make sure a nonbijective model fails validation."""

    class NonBijectiveModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r".+")
        bar: str = string(r".+")

    result = validate_template(NonBijectiveModel)
    assert not result.is_valid()
    assert not result.language.is_finite
    assert result.language.cardinality is None
    assert not result.ambiguity.is_bijective
