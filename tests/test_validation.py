"""Test the validation of models."""

from __future__ import annotations

import pytest

from regma import TemplateModel
from regma import string
from regma.core import BoundField
from regma.core import Chain
from regma.core import Separator
from regma.error import ValidityError
from regma.field import StrField
from regma.validation.fsm import CollisionResult
from regma.validation.fsm import FsmChain
from regma.validation.fsm import FsmNode
from regma.validation.fsm import FsmNodeBuilder
from regma.validation.fsm import FsmNodeCache
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
def fsm_builder() -> FsmNodeBuilder:
    """Return a FsmNodeBuilder object."""
    return FsmNodeBuilder(FsmNodeCache())


def test_fsm_builder_cache() -> None:
    """Verify the cache of fsm builder is working."""
    fsm_cache = FsmNodeCache()
    fsm_node_builder = FsmNodeBuilder(fsm_cache)
    bound_field = BoundField("test", StrField(".+"))
    fsm_node = fsm_node_builder.build_node_fsm(bound_field)
    assert isinstance(fsm_node, FsmNode)
    assert fsm_node.node is bound_field
    assert fsm_cache.get_fsm(bound_field) is fsm_node
    other_fsm_node = fsm_node_builder.build_node_fsm(bound_field)
    assert fsm_node is other_fsm_node


def test_compute_collision_with_empty_chain(fsm_builder: FsmNodeBuilder) -> None:
    """Make sure the compute collision return a valid collision result when empty."""
    fsm_chain = FsmChain.from_chain(Chain([]), fsm_builder)
    result = compute_collision(fsm_chain)
    assert isinstance(result, CollisionResult)
    assert not result.has_collision()


def test_separator_only_chain_is_always_valid(fsm_builder: FsmNodeBuilder) -> None:
    """Make sure a separator only chain is always valid."""
    fsm_chain = FsmChain.from_chain(Chain([Separator("test")]), fsm_builder)
    result = compute_collision(fsm_chain)
    assert isinstance(result, CollisionResult)
    assert not result.has_collision()


def test_simple_model_has_no_empty_tokens(
    fsm_builder: FsmNodeBuilder, simple_model: type[TemplateModel]
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
    fsm_builder: FsmNodeBuilder, simple_model: type[TemplateModel]
) -> None:
    """Make sure the simple test model is valid."""
    TemplateHasNoCollision(fsm_builder).validate(simple_model)


def test_separator_are_used_in_construction(fsm_builder: FsmNodeBuilder) -> None:
    """Make sure separator are taken into consideration when checking collision."""

    class _TestModel(TemplateModel):
        __template__ = "start_{foo}_{bar}_end"
        foo: str = string(r"[a-zA-Z]+")
        bar: str = string(r"\d+")

    TemplateHasNoCollision(fsm_builder).validate(_TestModel)


def test_failing_on_colliding_model() -> None:
    """Make sure a nonbijective model fails validation."""
    with pytest.raises(ValidityError):

        class _TestModel(TemplateModel):
            __template__ = "start_{foo}_{bar}_end"
            foo: str = string(r".+")
            bar: str = string(r".+")
