"""Tests the field module."""

import pytest

from templex import ChoiceField
from templex import DefinitionError
from templex import IntField
from templex import ParseError
from templex.engine import BuiltinRegexEngine
from templex.field import CustomField
from templex.field import ModelField
from templex.field import StrField
from templex.field import choice
from templex.field import custom_field
from templex.field import integer
from templex.field import model
from templex.field import string
from tests.conftest import IntChoiceField
from tests.conftest import SimpleTestModel


def test_str_field_pattern_value() -> None:
    """Pattern shall be the same as initialized."""
    assert StrField(".+").pattern == ".+"


def test_str_field_regex() -> None:
    """Regex returned by StrField shall be the same as initialized."""
    engine = BuiltinRegexEngine()
    assert StrField(".+").to_regex(engine) == ".+"


def test_str_field_extract_value() -> None:
    """Parsing of value shall return the given value."""
    assert StrField("").extract_value("anything") == "anything"


def test_string_field_descriptor() -> None:
    """String field descriptor shall return an StrField."""
    descriptor = string(r"\w+")
    assert isinstance(descriptor, StrField)
    assert descriptor.pattern == r"\w+"


def test_int_field_default_init() -> None:
    """Int field shall be initialized."""
    int_field = IntField()
    assert int_field.pattern == r"\d+"
    assert int_field.min_value is None
    assert int_field.max_value is None
    assert int_field.padding is None


def test_int_field_regex() -> None:
    """Regex returned by IntField shall be the same as initialized."""
    engine = BuiltinRegexEngine()
    assert IntField().to_regex(engine) == r"\d+"


def test_int_field_minimum_greater_than_maximum() -> None:
    """Using a minimum value greater than maximum shall raise a DefinitionError."""
    with pytest.raises(DefinitionError):
        IntField(minimum=10, maximum=5)


def test_int_field_padding_init() -> None:
    """Set padding of int field changes the pattern."""
    int_field = IntField(padding=1)
    assert int_field.pattern == r"\d{1}"
    int_field = IntField(padding=3)
    assert int_field.pattern == r"\d{3}"


def test_int_field_parse_success() -> None:
    """Parsing of value that do not match shall return corresponding integer."""
    assert IntField().extract_value("12345") == 12345  # noqa: PLR2004
    assert IntField(padding=4).extract_value("1234") == 1234  # noqa: PLR2004
    assert IntField(padding=1).extract_value("1234") == 1234  # noqa: PLR2004
    assert IntField(minimum=1).extract_value("12") == 12  # noqa: PLR2004
    assert IntField(maximum=10).extract_value("9") == 9  # noqa: PLR2004


def test_int_field_min_max_extract_error() -> None:
    """Parsing a string with incorrect padding shall fail."""
    with pytest.raises(ParseError):
        IntField(minimum=4).extract_value("2")

    with pytest.raises(ParseError):
        IntField(maximum=2).extract_value("3")


def test_integer_field_descriptor() -> None:
    """Integer field descriptor shall return an IntField."""
    descriptor = integer(minimum=1, maximum=10, padding=3)
    assert isinstance(descriptor, IntField)
    assert descriptor.pattern == r"\d{3}"
    assert descriptor.min_value == 1
    assert descriptor.max_value == 10  # noqa: PLR2004
    assert descriptor.padding == 3  # noqa: PLR2004


def test_choice_field_init() -> None:
    """Choice field shall be initialized."""
    field = ChoiceField(["test", "test1"])
    assert field.choices == ["test", "test1"]
    assert field.pattern == r"(?:test|test1)"


def test_choice_field_regex() -> None:
    """Regex returned by ChoiceField shall be the same as initialized."""
    engine = BuiltinRegexEngine()
    assert ChoiceField(["test", "test1"]).to_regex(engine) == r"(?:test|test1)"


def test_choice_field_extract_value() -> None:
    """Choice field always return the same value on extraction."""
    assert ChoiceField(["test", "test1"]).extract_value("other") == "other"


def test_choice_field_descriptor() -> None:
    """Choice field descriptor shall return an ChoiceField."""
    descriptor = choice(["test", "test1"])
    assert isinstance(descriptor, ChoiceField)
    assert descriptor.choices == ["test", "test1"]
    assert descriptor.pattern == r"(?:test|test1)"


def test_custom_field_init() -> None:
    """Custom field shall be initialized."""
    int_field = IntChoiceField([0, 1])
    field = CustomField(int_field)
    assert field.field is int_field


def test_custom_field_regex() -> None:
    """Regex returned by CustomField is the same regex as the field itself."""
    engine = BuiltinRegexEngine()
    field = IntChoiceField([0, 1])
    assert CustomField(field).to_regex(engine) == field.to_regex(engine)


def test_custom_field_extract_value() -> None:
    """Custom field always return the same value on extraction."""
    field = IntChoiceField([0, 1])
    assert CustomField(field).extract_value("1") == field.extract_value("1")


def test_custom_field_descriptor() -> None:
    """Custom field descriptor shall return an CustomField."""
    field = IntChoiceField([0, 1])
    descriptor = custom_field(field)
    assert isinstance(descriptor, CustomField)
    assert descriptor.field is field


def test_model_field_init() -> None:
    """Model field shall be initialized."""
    model_cls = SimpleTestModel
    model_field = ModelField(model_cls)
    assert model_field.model is model_cls


def test_model_field_regex() -> None:
    """Regex returned by ModelField is the same regex as the model itself."""
    engine = BuiltinRegexEngine()
    model_cls = SimpleTestModel
    assert ModelField(model_cls).to_regex(engine) == model_cls.__regex__


def test_model_field_extract_value() -> None:
    """Model field always return the model parsed value."""
    model_cls = SimpleTestModel
    field = ModelField(model_cls)
    assert field.extract_value("foo") == model_cls.parse("foo")


def test_model_field_descriptor() -> None:
    """Model field descriptor shall return an CustomField."""
    model_cls = SimpleTestModel
    descriptor = model(model_cls)
    assert isinstance(descriptor, ModelField)
    assert descriptor.model is model_cls
