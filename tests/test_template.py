"""Tests for templates."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from typing import Any

import pytest
from typing_extensions import override

from regma import Compound
from regma import DefinitionError
from regma import FormatError
from regma import Model
from regma import ParseError
from regma import Template
from regma import Token
from regma import integer
from regma import model_template
from regma import reference
from regma import string
from regma.chain import Chain
from regma.field import IntField
from regma.field import StrField

if TYPE_CHECKING:
    from collections.abc import Mapping


class AssetModel(Model):
    """Model declaring templates."""

    type: str = string(r"[a-z]+")
    code: str = string(r"[a-z]+")
    name = model_template("{type}_{code}")
    folder = model_template("/root/{type}/{code}")


class VariantModel(Model):
    """Model with a sub-model, declaring a template using the ones of the sub-model."""

    asset: AssetModel = reference(AssetModel)
    code: str = string(r"[a-z]+")
    folder = model_template("{asset.folder}/variant_{code}")


class VersionModel(Model):
    """Model of a padded number."""

    number: int = integer(maximum=500, padding=3)
    name = model_template("v{number}")


def test_template_init() -> None:
    """A template shall initialize correctly."""
    field = StrField(r"\w+")
    template = Template("{field}", field=field)
    assert template.pattern == r"{field}"


@pytest.mark.parametrize(
    ("template", "regex"),
    [
        (Template("{a}", a=StrField(r"\w+")), r"(?P<a>\w+)"),
        (
            Template(
                "{t}_{a}",
                t=Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b")),
                a=StrField(r"a"),
            ),
            r"(?P<t>(?P<t__a>a)_(?P<t__b>b))_(?P<a>a)",
        ),
    ],
)
def test_template_regex(template: Template, regex: str) -> None:
    """Test a template return the correct regex."""
    assert template.regex.pattern == regex


@pytest.mark.parametrize(
    ("template", "value", "result"),
    [
        (Template("{a}", a=StrField(r"\w+")), {"a": "test"}, "test"),
        (
            Template(
                "{t}_{a}",
                t=Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b")),
                a=StrField(r"a"),
            ),
            {"t": {"a": "a", "b": "b"}, "a": "a"},
            "a_b_a",
        ),
    ],
)
def test_template_format(template: Template, value: dict[str, Any], result: str) -> None:
    """Test a template format."""
    assert template.format(value) == result


@pytest.mark.parametrize(
    ("template", "value", "result"),
    [
        (Template("{a}", a=StrField(r"\w+")), "test", {"a": "test"}),
        (
            Template(
                "{t}_{a}",
                t=Template("{a}_{b}", a=StrField(r"a"), b=StrField(r"b")),
                a=StrField(r"a"),
            ),
            "a_b_a",
            {"t": {"a": "a", "b": "b"}, "a": "a"},
        ),
    ],
)
def test_template_parse(template: Template, value: str, result: dict[str, Any]) -> None:
    """Test a template parse."""
    assert template.parse(value) == result


def test_template_parse_fail() -> None:
    """Test a template raise ParseError if regex does not match."""
    template = Template("{a}", a=StrField(r"\d+"))

    with pytest.raises(ParseError):
        template.parse("abc")


def test_template_parses_values_of_nested_templates() -> None:
    """The value of a template token shall be the value of that template."""
    number = Template("{n}", n=integer())
    template = Template(
        "{a}/{b}/{asset}", a=number, b=Template("{c}", c=number), asset=AssetModel.name
    )
    value = {
        "a": {"n": 1},
        "b": {"c": {"n": 2}},
        "asset": {"type": "chr", "code": "toto"},
    }

    assert template.parse("1/2/chr_toto") == value
    assert template.format(value) == "1/2/chr_toto"


def test_template_reaches_tokens_of_template_token() -> None:
    """Dotted tokens shall reach the tokens of a template token."""
    template = Template("{t}/{t.b}", t=Template("{a}_{b}", a=string("a"), b=string("b")))

    assert template.regex.pattern == r"(?P<t>(?P<t__a>a)_(?P<t__b>b))/(?P=t__b)"
    assert template.parse("a_b/b") == {"t": {"a": "a", "b": "b"}}


def test_template_reaches_fields_of_models_of_template_token() -> None:
    """Dotted tokens shall reach the fields of the models used by a template token."""
    template = Template(
        "{t}/{t.asset.type}", t=Template("{asset.name}", asset=AssetModel)
    )
    value = {"t": {"asset": AssetModel("chr", "toto")}}

    assert template.regex.pattern == (
        r"(?P<t>(?P<t__asset__type>[a-z]+)_(?P<t__asset__code>[a-z]+))"
        r"/(?P=t__asset__type)"
    )
    assert template.parse("chr_toto/chr") == value
    assert template.format(value) == "chr_toto/chr"


def test_template_model_token_reaches_fields() -> None:
    """A model token shall reach the fields of the model through dotted tokens."""
    template = Template("{asset.type}/{asset.code}", asset=AssetModel)
    asset = AssetModel("chr", "toto")

    assert template.regex.pattern == r"(?P<asset__type>[a-z]+)/(?P<asset__code>[a-z]+)"
    assert template.parse("chr/toto") == {"asset": asset}
    assert template.format({"asset": asset}) == "chr/toto"


def test_template_model_token_reaches_declared_templates() -> None:
    """A model token shall reach the templates declared on the model and sub-models."""
    template = Template(
        "{variant.folder}/{variant.asset.name}_{variant.code}", variant=VariantModel
    )
    variant = VariantModel(AssetModel("chr", "toto"), "red")

    assert template.format({"variant": variant}) == (
        "/root/chr/toto/variant_red/chr_toto_red"
    )
    assert template.parse("/root/chr/toto/variant_red/chr_toto_red") == {
        "variant": variant
    }
    with pytest.raises(ParseError):
        template.parse("/root/chr/toto/variant_red/chr_titi_red")


def test_template_mixes_fields_and_model_tokens() -> None:
    """The value of a template shall hold a model instance for each model token."""
    template = Template(
        "{variant.folder}/task_{task}/{version.name}",
        variant=VariantModel,
        task=string(r"[a-z]+"),
        version=VersionModel,
    )
    value = {
        "variant": VariantModel(AssetModel("chr", "toto"), "red"),
        "task": "rig",
        "version": VersionModel(3),
    }
    path = "/root/chr/toto/variant_red/task_rig/v003"
    parsed = template.parse(path)

    assert template.format(value) == path
    assert parsed == value
    assert type(parsed["version"]) is VersionModel
    # The values follow the order of the token definitions
    assert list(parsed) == ["variant", "task", "version"]


def test_template_ignores_tokens_missing_from_pattern() -> None:
    """The tokens which are not in the pattern shall have no value."""
    template = Template(
        "{asset.name}", asset=AssetModel, version=VersionModel, task=string(r"[a-z]+")
    )
    asset = AssetModel("chr", "toto")

    assert template.parse("chr_toto") == {"asset": asset}
    assert template.format({"asset": asset}) == "chr_toto"


def test_template_validates_model_values() -> None:
    """The values of the model fields shall be validated as in model templates."""
    template = Template("{version.name}", version=VersionModel)

    with pytest.raises(FormatError):
        template.format({"version": VersionModel(600)})
    with pytest.raises(ParseError):
        template.parse("v600")


def test_template_fails_referencing_whole_model() -> None:
    """A model has no pattern of its own, so a token cannot be the whole model."""
    with pytest.raises(DefinitionError, match=r"\{asset\}: .* no pattern of its own"):
        Template("{asset}", asset=AssetModel)

    with pytest.raises(
        DefinitionError, match=r"\{variant\.asset\}: .* no pattern of its own"
    ):
        Template("{variant.asset}/{variant.code}", variant=VariantModel)


def test_template_fails_with_missing_model_field() -> None:
    """A template shall capture all the fields of a model to build its instance."""
    with pytest.raises(DefinitionError, match=r"\['variant\.asset\.code'\]"):
        Template("{variant.asset.type}/{variant.code}", variant=VariantModel)


def test_template_fails_referencing_unknown_element_of_model() -> None:
    """A token reaching neither a field nor a template of a model shall fail."""
    with pytest.raises(DefinitionError):
        Template("{asset.nope}", asset=AssetModel)

    with pytest.raises(DefinitionError):
        Template("{variant.nope.name}", variant=VariantModel)

    # A declared template is an alias, standing for references to the fields
    with pytest.raises(DefinitionError, match=r"'asset\.name' is not a token"):
        Template("{asset.name.type}", asset=AssetModel)


class _DateToken(Compound[datetime.date]):
    """A date written as year-month-day, reaching its numbers."""

    def __init__(self) -> None:
        """Initialize the token from the padded numbers of the date."""
        self._tokens = {
            name: IntField(padding=padding)
            for name, padding in (("year", 4), ("month", 2), ("day", 2))
        }
        self._chain = Chain.from_pattern("{year}-{month}-{day}", **self._tokens)

    @property
    @override
    def tokens(self) -> Mapping[str, Token[Any]]:
        return self._tokens

    @property
    @override
    def chain(self) -> Chain:
        return self._chain

    @override
    def build_value(self, values: dict[str, Any]) -> datetime.date:
        return datetime.date(**values)


def test_template_accepts_new_kinds_of_tokens() -> None:
    """A template shall use any compound, expanding its chain."""
    template = Template(
        "{shot}_{date}/{date.year}", shot=string("[a-z]+"), date=_DateToken()
    )
    value = {"shot": "foo", "date": datetime.date(2024, 5, 1)}

    assert template.regex.pattern == (
        r"(?P<shot>[a-z]+)_(?P<date>(?P<date__year>\d{4})\-(?P<date__month>\d{2})"
        r"\-(?P<date__day>\d{2}))/(?P=date__year)"
    )
    assert template.format(value) == "foo_2024-05-01/2024"
    assert template.parse("foo_2024-05-01/2024") == value
    with pytest.raises(ParseError):
        template.parse("foo_2024-05-01/2025")


class _FramesToken(Compound[range]):
    """Frames written first-last, as a range not holding its numbers by attribute."""

    def __init__(self) -> None:
        """Initialize the token from the first and last frames."""
        self._tokens = {"first": IntField(), "last": IntField()}
        self._chain = Chain.from_pattern("{first}-{last}", **self._tokens)

    @property
    @override
    def tokens(self) -> Mapping[str, Token[Any]]:
        return self._tokens

    @property
    @override
    def chain(self) -> Chain:
        return self._chain

    @override
    def build_value(self, values: dict[str, Any]) -> range:
        return range(values["first"], values["last"] + 1)

    @override
    def get_value(self, value: range, name: str) -> object:
        return value[0] if name == "first" else value[-1]


def test_template_gets_values_of_tokens_from_compound() -> None:
    """A compound shall give the values of its tokens from its own value."""
    template = Template(
        "{shot}.{frames}/{frames.last}", shot=string("[a-z0-9]+"), frames=_FramesToken()
    )
    value = {"shot": "sh010", "frames": range(1001, 1101)}

    assert template.format(value) == "sh010.1001-1100/1100"
    assert template.parse("sh010.1001-1100/1100") == value


class _UpperToken(Token[str]):
    """A word written in upper case, which is a token without being a field."""

    @override
    def to_regex(self) -> str:
        return "[A-Z]+"

    @override
    def parse_value(self, raw: str) -> str:
        return raw.lower()

    @override
    def format_value(self, value: str) -> str:
        return value.upper()


def test_template_accepts_any_token() -> None:
    """A template shall use any token, matching its regex if it has no chain."""
    template = Template("{shot}_{date}", shot=_UpperToken(), date=_DateToken())
    value = {"shot": "foo", "date": datetime.date(2024, 5, 1)}

    assert template.regex.pattern.startswith(r"(?P<shot>[A-Z]+)_(?P<date>")
    assert template.format(value) == "FOO_2024-05-01"
    assert template.parse("FOO_2024-05-01") == value
