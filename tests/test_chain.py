"""Tests for the chain related elements."""

from __future__ import annotations

import pytest

from regma.chain import Chain
from regma.chain import ChainAlias
from regma.chain import Reference
from regma.chain import RefSep
from regma.error import DefinitionError
from regma.field import BoundField
from regma.field import StrField
from regma.template import Template


@pytest.fixture
def bound_field() -> BoundField[str]:
    """Return bound field used for reference testing."""
    return BoundField("test", StrField(".+"))


@pytest.fixture
def reference(bound_field: BoundField[str]) -> Reference:
    """Return bound field used for reference testing."""
    return Reference("reference", bound_field)


def test_reference_init(bound_field: BoundField[str]) -> None:
    """Test the reference object initialize properly."""
    reference = Reference("other", bound_field)
    assert reference.target is bound_field
    assert reference.name == "other"


def test_reference_regex(reference: Reference) -> None:
    """Reference shall return expected regex."""
    assert reference.to_regex() == ".+"


def test_reference_format(reference: Reference) -> None:
    """Reference shall return expected format."""
    assert reference.format({"reference": "value"}) == "value"


def test_ref_sep_init(reference: Reference) -> None:
    """Test the RefSep object initialize properly."""
    ref_sep = RefSep(reference, "end")
    assert ref_sep.reference is reference
    assert ref_sep.suffix == "end"


@pytest.fixture
def ref_sep(reference: Reference) -> RefSep:
    """Create ref sep object for testing."""
    return RefSep(reference, "end")


def test_chain_init(ref_sep: RefSep) -> None:
    """Chain shall initialize as expected."""
    chain = Chain("test", [ref_sep])
    assert chain.start_prefix == "test"
    assert list(chain.iter_field_seps()) == [ref_sep]


@pytest.fixture
def chain(ref_sep: RefSep) -> Chain:
    """Return chain object for testing."""
    return Chain("start", [ref_sep])


def test_chain_alias_init(chain: Chain) -> None:
    """Test the chain alias init."""
    alias = ChainAlias(chain)
    assert alias.to_chain() is chain


@pytest.fixture
def alias(chain: Chain) -> ChainAlias:
    """Return a chain alias object for testing."""
    return ChainAlias(chain)


def test_chain_alias_regex(alias: ChainAlias) -> None:
    """Test the regex of chain alias."""
    assert alias.to_regex() == r"start(?P<reference>.+)end"


def test_chain_regex(chain: Chain) -> None:
    """Chain shall return expected regex."""
    assert chain.to_regex() == r"start(?P<reference>.+)end"


def test_chain_use_back_reference(reference: Reference) -> None:
    """Test a chain construct the regex with a back name when reusing reference."""
    chain = Chain("start", [RefSep(reference, "end"), RefSep(reference, "end")])
    assert chain.to_regex() == r"start(?P<reference>.+)end(?P=reference)end"


@pytest.fixture
def nested_chain() -> Chain:
    """Return a chain nesting the chain of a template node for testing."""
    template = Template(
        "{field1}_{field2}", field1=StrField(r".+"), field2=StrField(r"\w+")
    )

    return Chain.from_pattern(
        "{chain1.field1}_{chain1}/{chain1}", chain1=template.to_node("chain1")
    )


def test_chain_use_back_reference_on_nested_nodes(nested_chain: Chain) -> None:
    """Test a chain uses back references on nested nodes."""
    assert (
        nested_chain.to_regex() == r"(?P<chain1__field1>.+)"
        r"_(?P<chain1>(?P=chain1__field1)"
        r"_(?P<chain1__field2>\w+))/(?P=chain1)"
    )


def test_chain_from_pattern_fails_with_no_attribute(
    bound_field: BoundField[str],
) -> None:
    """Test building a chain from pattern fails with no attribute."""
    with pytest.raises(DefinitionError):
        Chain.from_pattern("{}")

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{field.}", field=bound_field)


def test_chain_from_pattern_fails_with_missing_attribute(
    bound_field: BoundField[str],
) -> None:
    """Test building a chain from pattern fails with missing attribute."""
    with pytest.raises(DefinitionError):
        Chain.from_pattern("{missing}", field=bound_field)


def test_chain_from_pattern_fails_with_invalid_attribute(
    bound_field: BoundField[str],
) -> None:
    """Test building a chain from pattern fails with invalid attribute."""
    with pytest.raises(DefinitionError):
        Chain.from_pattern("{field.test}", field=bound_field)


def test_chain_fails_on_missing_nested_node() -> None:
    """Test building a chain from pattern fails on missing nested node."""
    template = Template("{field1}", field1=StrField(r".+"))

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{chain1.field2}", chain1=template.to_node("chain1"))


def test_chain_splices_alias(bound_field: BoundField[str]) -> None:
    """A chain shall replace an alias by the references of the alias chain."""
    alias = ChainAlias(Chain.from_pattern("<{test}>", test=bound_field))
    chain = Chain.from_pattern("{alias}/{test}", alias=alias, test=bound_field)

    assert chain.to_regex() == r"<(?P<test>.+)>/(?P=test)"


def test_cannot_initialize_chain_with_invalid_fields() -> None:
    """A template with heading or trailing underscore is forbidden.

    We need to avoid this because it would otherwise
    """
    bound_field1 = BoundField("field1", StrField(r".+"))

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{_field1}", _field1=bound_field1)

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{field1_}", field1_=bound_field1)

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{fie__ld1}", fie__ld1=bound_field1)


def test_chain_format(chain: Chain) -> None:
    """Chain shall return expected format."""
    assert chain.format({"reference": "test"}) == "starttestend"


def test_chain_alias_format(nested_chain: Chain) -> None:
    """A chain alias shall format the value of the node holding it."""
    alias = ChainAlias(nested_chain)
    assert (
        alias.format_value({"chain1": {"field1": "c1f1", "field2": "c1f2"}})
        == "c1f1_c1f1_c1f2/c1f1_c1f2"
    )


def test_chain_alias_parse(nested_chain: Chain) -> None:
    """A chain alias shall return the raw values of the node holding it."""
    alias = ChainAlias(nested_chain)
    data = {"chain1": {"field1": "c1f1", "field2": "c1f2"}}
    assert alias.parse_value(data) == data
