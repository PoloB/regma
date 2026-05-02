"""Test the validation of models."""

from __future__ import annotations

from regma import TemplateModel
from regma import choice
from regma import string
from regma.validation import FsmChain
from tests.conftest import SimpleTestModel


def test_simple_model_is_valid() -> None:
    """Make sure the simple test model is valid."""
    fsm_chain = FsmChain.from_chain(SimpleTestModel.__chain__)
    result = fsm_chain.get_collision_result()
    assert result.is_valid()


def test_finite_model() -> None:
    """Make sure the finite test model is valid."""

    class FiniteModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = choice(["chr", "prp"])
        bar: str = choice(["up", "down"])

    fsm_chain = FsmChain.from_chain(FiniteModel.__chain__)
    result = fsm_chain.get_collision_result()
    assert result.is_valid()


def test_non_bijective_model_succeed() -> None:
    """Make sure a bijective model succeed validation."""

    class NonBijectiveModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r"[a-zA-Z]+")
        bar: str = string(r"\d+")

    fsm_chain = FsmChain.from_chain(NonBijectiveModel.__chain__)
    result = fsm_chain.get_collision_result()
    assert result.is_valid()


def test_non_bijective_model_fails() -> None:
    """Make sure a nonbijective model fails validation."""

    class NonBijectiveModel(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r".+")
        bar: str = string(r".+")

    fsm_chain = FsmChain.from_chain(NonBijectiveModel.__chain__)
    result = fsm_chain.get_collision_result()
    assert not result.is_valid()
