"""Test the validation of models."""

from __future__ import annotations

import greenery
import pytest

from regma import Template
from regma import string
from regma.chain import Chain
from regma.chain import Reference
from regma.error import ValidityError
from regma.field import BoundField
from regma.field import StrField
from regma.fsm import CollisionResult
from regma.fsm import FsmBuilder
from regma.fsm import FsmRegexCache
from regma.fsm import compute_collision
from regma.fsm import validate
from regma.fsm import validate_template_has_no_collision
from regma.fsm import validate_template_has_no_empty_token


@pytest.fixture
def fsm_builder() -> FsmBuilder:
    """Return a FsmNodeBuilder object."""
    return FsmBuilder(FsmRegexCache())


@pytest.fixture
def simple_test_template() -> Template:
    """Return a simple test template."""
    return Template("{test}", test=string(".+"))


def test_fsm_builder_cache() -> None:
    """Verify the cache of fsm builder is working."""
    fsm_cache = FsmRegexCache()
    fsm_builder = FsmBuilder(fsm_cache)
    field = Reference("test", BoundField("test", StrField(".+")))
    regex = field.to_regex()
    fsm = fsm_builder.build_fsm(regex)
    assert isinstance(fsm, greenery.Fsm)
    assert fsm_cache.get_fsm(regex) is fsm
    cached_fsm = fsm_builder.build_fsm(regex)
    assert cached_fsm is fsm


def test_separator_only_chain_is_always_valid(fsm_builder: FsmBuilder) -> None:
    """Make sure a separator only chain is always valid."""
    result = compute_collision(Chain("test", []), fsm_builder)
    assert isinstance(result, CollisionResult)
    assert not result.has_collision()


def test_simple_model_has_no_empty_tokens(
    fsm_builder: FsmBuilder, simple_test_template: Template
) -> None:
    """Test the simple model has no empty tokens."""
    validate_template_has_no_empty_token(fsm_builder, simple_test_template)


def test_model_with_empty_tokens_fail_validation() -> None:
    """Test the model has empty tokens fail validation."""
    template = Template("{test}", test=string(".*"))
    fsm_builder = FsmBuilder(FsmRegexCache())

    with pytest.raises(ValidityError):
        validate(fsm_builder, template)


def test_simple_model_has_no_collision(
    fsm_builder: FsmBuilder, simple_test_template: Template
) -> None:
    """Make sure the simple test model is valid."""
    validate_template_has_no_collision(fsm_builder, simple_test_template)


def test_separator_are_used_in_construction(fsm_builder: FsmBuilder) -> None:
    """Make sure separator are taken into consideration when checking collision."""
    template = Template(
        "start_{foo}_{bar}_end", foo=string(r"[a-zA-Z]+"), bar=string(r"\d+")
    )
    validate_template_has_no_collision(fsm_builder, template)


def test_success_on_complex_example() -> None:
    """Make sure a more complex regex template also works."""
    template = Template(
        "{foo}_{bar}", foo=string(r"[a-z][a-z_]+"), bar=string(r"[a-z]+")
    )
    fsm_builder = FsmBuilder(FsmRegexCache())
    validate(fsm_builder, template)


def test_failing_on_colliding_template() -> None:
    """Make sure a nonbijective model fails validation."""
    fsm_builder = FsmBuilder(FsmRegexCache())
    template = Template("start_{foo}_{bar}_end", foo=string(r".+"), bar=string(r"[^a]+"))
    with pytest.raises(ValidityError):
        validate(fsm_builder, template)


def test_failing_on_nested_template() -> None:
    """Make sure a collision is detected if regexes at two different depth collides."""
    fsm_builder = FsmBuilder(FsmRegexCache())
    template1 = Template("start_{foo}", foo=string(r".+"))
    template2 = Template("{t}_{bar}", t=template1, bar=string(r".+"))
    with pytest.raises(ValidityError):
        validate(fsm_builder, template2)


def test_empty_field_succeed_with_no_validation() -> None:
    """Make sure validation passes with no validation."""
    Template("{test}", test=string(".*"))


def test_collision_succeed_with_no_validation() -> None:
    """Make sure validation passes with no validation."""
    Template("start_{foo}_{bar}_end", foo=string(r".+"), bar=string(r"[^a]+"))


def test_reuse_leaves_ambiguity() -> None:
    """Reusing a field shall leave ambiguity if possible.

    When the reuse of a field is not taken into account, we may find a collision where
    it is not possible because the value of the field is fixed due to an earlier valid
    use.
    In this example, the first appearing of bar fixes its value and thus, {bar}_{test}
    cannot create a collision.
    """
    template = Template(
        "{bar}_{foo}_{bar}_{test}",
        foo=string(r"[a-zA-Z0-9]+"),
        bar=string(r"\w+"),
        test=string(r"\w+"),
    )
    fsm_builder = FsmBuilder(FsmRegexCache())
    validate(fsm_builder, template)
