"""Tests for the chain related elements."""

from __future__ import annotations

import re

import pytest

from regma import Model
from regma import model_template
from regma import string
from regma.chain import Chain
from regma.chain import Delimiter
from regma.chain import Reference
from regma.chain import RefSep
from regma.core import ChainAlias
from regma.error import DefinitionError
from regma.field import StrField
from regma.template import Template


@pytest.fixture
def field() -> StrField:
    """Return field used for reference testing."""
    return StrField(".+")


@pytest.fixture
def reference(field: StrField) -> Reference:
    """Return reference used for testing."""
    return Reference("reference", field)


@pytest.fixture
def holder() -> Template:
    """Return the template holding the token of the reference."""
    return Template("{reference}", reference=StrField(".+"))


def test_reference_init(field: StrField) -> None:
    """Test the reference object initialize properly."""
    reference = Reference("other", field)
    assert reference.target is field
    assert reference.name == "other"


def test_reference_regex(reference: Reference) -> None:
    """Reference shall return expected regex."""
    assert reference.to_regex() == ".+"


def test_reference_to_compound_regex() -> None:
    """A reference to a compound shall return the regex of its chain."""
    template = Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b"))
    assert Reference("t", template).to_regex() == r"(?P<a>a)_(?P<b>b)"


def test_reference_to_compound_without_chain_fails() -> None:
    """A compound without chain shall have no regex, naming its reference."""
    with pytest.raises(DefinitionError, match=r"\{t\}: the compound has no pattern"):
        Reference("t", _AliasModel.__token__).to_regex()


def test_reference_format(reference: Reference, holder: Template) -> None:
    """Reference shall return expected format."""
    assert reference.format({"reference": "value"}, holder) == "value"


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


def test_chain_regex(chain: Chain) -> None:
    """Chain shall return expected regex."""
    assert chain.to_regex() == r"start(?P<reference>.+)end"


def test_chain_use_back_reference(reference: Reference) -> None:
    """Test a chain construct the regex with a back name when reusing reference."""
    chain = Chain("start", [RefSep(reference, "end"), RefSep(reference, "end")])
    assert chain.to_regex() == r"start(?P<reference>.+)end(?P=reference)end"


@pytest.fixture
def inner_template() -> Template:
    """Return a template used as a token of the nested chain."""
    return Template("{field1}_{field2}", field1=StrField(r".+"), field2=StrField(r"\w+"))


@pytest.fixture
def nested_chain(inner_template: Template) -> Chain:
    """Return a chain nesting the chain of a template for testing."""
    return Chain.from_pattern("{chain1.field1}_{chain1}/{chain1}", chain1=inner_template)


def test_chain_use_back_reference_on_nested_nodes(nested_chain: Chain) -> None:
    """Test a chain uses back references on nested nodes."""
    assert (
        nested_chain.to_regex() == r"(?P<chain1__field1>.+)"
        r"_(?P<chain1>(?P=chain1__field1)"
        r"_(?P<chain1__field2>\w+))/(?P=chain1)"
    )


def test_chain_from_pattern_fails_with_no_attribute(field: StrField) -> None:
    """Test building a chain from pattern fails with no attribute."""
    with pytest.raises(DefinitionError):
        Chain.from_pattern("{}")

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{field.}", field=field)


def test_chain_from_pattern_fails_with_missing_attribute(field: StrField) -> None:
    """Test building a chain from pattern fails with missing attribute."""
    with pytest.raises(DefinitionError, match="'missing': neither a token nor an alias"):
        Chain.from_pattern("{missing}", field=field)


def test_chain_from_pattern_fails_with_invalid_attribute(field: StrField) -> None:
    """Test building a chain from pattern fails with invalid attribute."""
    with pytest.raises(DefinitionError):
        Chain.from_pattern("{field.test}", field=field)


def test_chain_fails_on_missing_nested_node(inner_template: Template) -> None:
    """Test building a chain from pattern fails on missing nested node."""
    with pytest.raises(DefinitionError, match=r"'chain1\.nope' is not a token"):
        Chain.from_pattern("{chain1.nope.field1}", chain1=inner_template)


class _AliasModel(Model):
    """Model whose declared template is an alias of the model."""

    test: str = string(".+")
    alias = model_template("<{test}>")


def test_chain_splices_alias(field: StrField, holder: Template) -> None:
    """A chain shall replace an alias by the references of the alias chain."""
    alias = ChainAlias(Chain.from_pattern("<{test}>", test=field), holder)
    chain = Chain.from_pattern("{alias}/{test}", alias=alias, test=field)

    assert chain.to_regex() == r"<(?P<test>.+)>/(?P=test)"


def test_chain_splices_alias_through_its_holder() -> None:
    """The references of an alias shall go through the token holding the alias."""
    chain = Chain.from_pattern("{model.alias}", model=_AliasModel.__token__)

    assert chain.to_regex() == r"<(?P<model__test>.+)>"


def test_alias_matches_value_of_its_holder() -> None:
    """The value of an alias shall be the value of the token holding it."""
    alias = _AliasModel.__token__.aliases["alias"]

    assert alias.chain is _AliasModel.alias.chain
    assert alias.to_regex() == r"<(?P<test>.+)>"
    assert alias.parse_value({"test": "foo"}) == _AliasModel("foo")
    assert alias.format_value(_AliasModel("foo")) == "<foo>"


def test_cannot_initialize_chain_with_invalid_fields() -> None:
    """A template with heading or trailing underscore is forbidden.

    We need to avoid this because it would otherwise
    """
    field1 = StrField(r".+")

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{_field1}", _field1=field1)

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{field1_}", field1_=field1)

    with pytest.raises(DefinitionError):
        Chain.from_pattern("{fie__ld1}", fie__ld1=field1)


def test_chain_format(chain: Chain, holder: Template) -> None:
    """Chain shall return expected format."""
    assert chain.format({"reference": "test"}, holder) == "starttestend"


def test_chain_formats_compound_with_its_chain(
    nested_chain: Chain, inner_template: Template
) -> None:
    """A chain shall format a compound with its chain, from the value of the holder."""
    holder = Template("{chain1}", chain1=inner_template)
    value = {"chain1": {"field1": "c1f1", "field2": "c1f2"}}

    assert nested_chain.format(value, holder) == "c1f1_c1f1_c1f2/c1f1_c1f2"


@pytest.mark.parametrize(
    ("delimiter", "open_token", "close_token", "expected_regex"),
    [
        (Delimiter.CURLY, "{", "}", r"\{([^\{\}]*(?:\.[^\{\}]*)*)\}"),
        (Delimiter.ANGLE, "<", ">", r"<([^<>]*(?:\.[^<>]*)*)>"),
        (Delimiter.SQUARE, "[", "]", r"\[([^\[\]]*(?:\.[^\[\]]*)*)\]"),
    ],
)
def test_delimiter(
    delimiter: Delimiter, open_token: str, close_token: str, expected_regex: str
) -> None:
    """Delimiter enum behaves as expected."""
    assert isinstance(delimiter.value, tuple)
    assert delimiter.token_open == open_token
    assert delimiter.token_close == close_token
    regex = delimiter.token_re()
    assert isinstance(regex, re.Pattern)
    assert regex.pattern == expected_regex
