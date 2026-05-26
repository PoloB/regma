"""Test the validation of models."""

from __future__ import annotations

import greenery
import pytest

from regma import TemplateModel
from regma import string
from regma.core import Chain
from regma.core import FieldReference
from regma.core import Separator
from regma.error import ValidityError
from regma.field import StrField
from regma.validation.fsm import CollisionResult
from regma.validation.fsm import FsmBuilder
from regma.validation.fsm import FsmRegexCache
from regma.validation.fsm import TemplateHasNoCollision
from regma.validation.fsm import TemplateHasNoEmptyToken
from regma.validation.fsm import compute_collision


@pytest.fixture
def simple_model() -> type[TemplateModel]:
    """Return a simple template model."""

    class SimpleTestModel(TemplateModel):
        """Simple test model."""

        __template__ = "{test}"
        test: str = string(".+")

    return SimpleTestModel


@pytest.fixture
def fsm_builder() -> FsmBuilder:
    """Return a FsmNodeBuilder object."""
    return FsmBuilder(FsmRegexCache())


def test_fsm_builder_cache() -> None:
    """Verify the cache of fsm builder is working."""
    fsm_cache = FsmRegexCache()
    fsm_builder = FsmBuilder(fsm_cache)
    field = FieldReference("test", StrField(".+"))
    regex = field.to_regex()
    fsm = fsm_builder.build_fsm(regex)
    assert isinstance(fsm, greenery.Fsm)
    assert fsm_cache.get_fsm(regex) is fsm
    cached_fsm = fsm_builder.build_fsm(regex)
    assert cached_fsm is fsm


def test_separator_only_chain_is_always_valid(fsm_builder: FsmBuilder) -> None:
    """Make sure a separator only chain is always valid."""
    result = compute_collision(Chain(Separator("test"), []), fsm_builder)
    assert isinstance(result, CollisionResult)
    assert not result.has_collision()


def test_simple_model_has_no_empty_tokens(
    fsm_builder: FsmBuilder, simple_model: type[TemplateModel]
) -> None:
    """Test the simple model has no empty tokens."""
    TemplateHasNoEmptyToken(fsm_builder).validate(simple_model)


def test_model_with_empty_tokens_fail_validation() -> None:
    """Test the model has empty tokens fail validation."""
    with pytest.raises(ValidityError):

        class _TestModel(TemplateModel):
            """Simple test model."""

            __template__ = "{test}"
            test: str = string(".*")


def test_simple_model_has_no_collision(
    fsm_builder: FsmBuilder, simple_model: type[TemplateModel]
) -> None:
    """Make sure the simple test model is valid."""
    TemplateHasNoCollision(fsm_builder).validate(simple_model)


def test_separator_are_used_in_construction(fsm_builder: FsmBuilder) -> None:
    """Make sure separator are taken into consideration when checking collision."""

    class _TestModel(TemplateModel):
        __template__ = "start_{foo}_{bar}_end"
        foo: str = string(r"[a-zA-Z]+")
        bar: str = string(r"\d+")

    TemplateHasNoCollision(fsm_builder).validate(_TestModel)


def test_success_on_complex_example() -> None:
    """Make sure a more complex regex template also works."""

    class _TestModel(TemplateModel):
        foo: str = string(r"[a-z][a-z_]+")
        bar: str = string(r"[a-z]+")
        __template__ = "{foo}_{bar}"


def test_failing_on_colliding_model() -> None:
    """Make sure a nonbijective model fails validation."""
    with pytest.raises(ValidityError):

        class _TestModel(TemplateModel):
            __template__ = "start_{foo}_{bar}_end"
            foo: str = string(r".+")
            bar: str = string(r"[^a]+")
