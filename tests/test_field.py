"""Tests the field module."""

import pytest

from templex import DefinitionError
from templex import FormatError
from templex import ParseError
from templex import choice
from templex import custom_field
from templex import integer
from templex import reference
from templex import string
from templex.core import Strictness
from templex.engine import BuiltinRegexEngine
from templex.field import ChoiceField
from templex.field import CustomField
from templex.field import IntField
from templex.field import ModelField
from templex.field import StrField
from tests.conftest import FooBarModel
from tests.conftest import IntChoiceField
from tests.conftest import SimpleTestModel


def test_str_field_pattern_init() -> None:
    """Pattern shall be the same as initialized."""
    field = StrField(".+")
    assert field.pattern == ".+"
    assert field.strictness == Strictness.ALL
    assert field.get_supported_types() == (str,)


def test_str_field_regex() -> None:
    """Regex returned by StrField shall be the same as initialized."""
    engine = BuiltinRegexEngine()
    assert StrField(".+").to_regex(engine) == ".+"


def test_str_field_extract_value() -> None:
    """Parsing of value shall return the given value."""
    assert StrField("").parse_value("anything") == "anything"


def test_str_field_format_value() -> None:
    """Format of value shall match pattern."""
    assert StrField(r"\d+").format_value("12345") == "12345"


def test_str_field_format_value_fail() -> None:
    """Format of value shall fail if pattern does not match."""
    with pytest.raises(FormatError):
        StrField(r"\d+").format_value("nope")


def test_string_field_descriptor() -> None:
    """String field descriptor shall return an StrField."""
    descriptor = string(r"\w+")
    assert isinstance(descriptor, StrField)
    assert descriptor.pattern == r"\w+"


def test_int_field_default_init() -> None:
    """Int field shall be initialized."""
    field = IntField()
    assert field.pattern == r"\d+"
    assert field.min_value is None
    assert field.max_value is None
    assert field.padding is None
    assert field.get_supported_types() == (int,)


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


def test_int_field_extract_value() -> None:
    """Parsing of value that do not match shall return corresponding integer."""
    assert IntField().parse_value("12345") == 12345  # noqa: PLR2004
    assert IntField(padding=4).parse_value("1234") == 1234  # noqa: PLR2004
    assert IntField(minimum=1).parse_value("12") == 12  # noqa: PLR2004
    assert IntField(maximum=10).parse_value("9") == 9  # noqa: PLR2004
    assert IntField(padding=1).parse_value("-1") == -1


def test_int_field_extract_value_fails_when_no_int() -> None:
    """Parsing a noninteger value shall raise a ParseError."""
    with pytest.raises(ParseError):
        IntField().parse_value("test")


def test_int_field_min_max_extract_error() -> None:
    """Parsing a string with incorrect min max shall fail."""
    with pytest.raises(ParseError):
        IntField(minimum=4).parse_value("2")

    with pytest.raises(ParseError):
        IntField(maximum=2).parse_value("3")


def test_int_field_padding_strict_extract_error() -> None:
    """Parsing a string not following padding fails by default."""
    with pytest.raises(ParseError):
        IntField(padding=3).parse_value("12345")

    with pytest.raises(ParseError):
        IntField(padding=1).parse_value("-12")


def test_int_field_padding_mode_non_strict_extract_success() -> None:
    """Parsing a string with a padding but not strict shall succeed."""
    mode = Strictness.NONE
    assert (
        IntField(padding=2, strictness=mode).parse_value("0002") == 2  # noqa: PLR2004
    )
    assert (
        IntField(padding=2, strictness=mode).parse_value("-0002") == -2  # noqa: PLR2004
    )


def test_int_field_format_value() -> None:
    """Format of value shall follow padding."""
    assert IntField().format_value(12345) == "12345"
    assert IntField(padding=4).format_value(1234) == "1234"
    assert IntField(minimum=1).format_value(12) == "12"
    assert IntField(maximum=10).format_value(9) == "9"
    assert IntField(padding=1).format_value(-2) == "-2"


def test_int_field_min_max_format_error() -> None:
    """Formatting a value greater or lower than maximum or minimum shall fail."""
    with pytest.raises(FormatError):
        IntField(minimum=4).format_value(2)

    with pytest.raises(FormatError):
        IntField(maximum=2).format_value(3)


def test_int_field_padding_strict_format_error() -> None:
    """Formatting a value not following padding fails by default."""
    with pytest.raises(FormatError):
        IntField(padding=2).format_value(123)

    with pytest.raises(FormatError):
        IntField(padding=2).format_value(-123)


def test_int_field_padding_mode_non_strict_format_success() -> None:
    """Formatting a value with a padding but not strict shall succeed."""
    mode = Strictness.NONE
    assert IntField(padding=2, strictness=mode).format_value(123) == "123"
    assert IntField(padding=2, strictness=mode).format_value(-123) == "-123"


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
    assert field.get_supported_types() == (str,)


def test_choice_field_regex() -> None:
    """Regex returned by ChoiceField shall be the same as initialized."""
    engine = BuiltinRegexEngine()
    assert ChoiceField(["test", "test1"]).to_regex(engine) == r"(?:test|test1)"


def test_choice_field_extract_value() -> None:
    """Choice field always return the same value on extraction."""
    assert ChoiceField(["test", "test1"]).parse_value("test") == "test"


def test_choice_field_extract_fails_if_not_in_choice() -> None:
    """Choice field always return the same value on extraction."""
    with pytest.raises(ParseError):
        ChoiceField(["test", "test1"]).parse_value("other")


def test_choice_field_format_value() -> None:
    """Choice field is formatting value as expected."""
    assert ChoiceField(["test", "test1"]).format_value("test") == "test"


def test_choice_field_format_fails_if_not_in_choice() -> None:
    """Formatting field fails if the value is not in choices."""
    with pytest.raises(FormatError):
        ChoiceField(["test", "test1"]).format_value("other")


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
    assert field.get_supported_types() == int_field.get_supported_types()


def test_custom_field_regex() -> None:
    """Regex returned by CustomField is the same regex as the field itself."""
    engine = BuiltinRegexEngine()
    field = IntChoiceField([0, 1])
    assert CustomField(field).to_regex(engine) == field.to_regex(engine)


def test_custom_field_extract_value() -> None:
    """Custom field always return the same value on extraction."""
    field = IntChoiceField([0, 1])
    assert CustomField(field).parse_value("1") == field.parse_value("1")


def test_custom_field_format_value() -> None:
    """Custom field always return the formatted value of the wrapped field."""
    field = IntChoiceField([0, 1])
    assert CustomField(field).format_value(1) == field.format_value(1)


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
    assert model_field.get_supported_types() == (SimpleTestModel,)


def test_model_field_regex() -> None:
    """Regex returned by ModelField is the same regex as the model itself."""
    engine = BuiltinRegexEngine()
    model_cls = SimpleTestModel
    assert ModelField(model_cls).to_regex(engine) == model_cls.__regex__


def test_model_field_extract_value() -> None:
    """Model field always return the model parsed value."""
    model_cls = FooBarModel
    field = ModelField(model_cls)
    assert field.parse_value("foo_1") == model_cls.parse("foo_1")


def test_model_field_extract_fails_if_model_fails() -> None:
    """PArsing shall fail if the value is not compatible with model template."""
    model_cls = FooBarModel
    field = ModelField(model_cls)
    with pytest.raises(ParseError):
        assert field.parse_value("foo")


def test_model_field_format_value() -> None:
    """Model field always return the model formatted value."""
    model_cls = FooBarModel
    field = ModelField(model_cls)
    model_inst = FooBarModel("foo", 1)
    assert field.format_value(model_inst) == model_inst.format()


def test_model_field_format_fails_if_model_fails() -> None:
    """PArsing shall fail if the value is not compatible with model template."""
    model_cls = FooBarModel
    field = ModelField(model_cls)
    with pytest.raises(ParseError):
        assert field.parse_value("foo")


def test_model_field_descriptor() -> None:
    """Model field descriptor shall return an CustomField."""
    model_cls = SimpleTestModel
    descriptor = reference(model_cls)
    assert isinstance(descriptor, ModelField)
    assert descriptor.model is model_cls
