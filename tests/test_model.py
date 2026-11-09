"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

from typing import Any

import pytest

from regma import Compound
from regma import DefinitionError
from regma import FormatError
from regma import Model
from regma import ParseError
from regma import Template
from regma import Token
from regma import model_template
from regma import reference
from regma.field import integer
from regma.field import string


class FooBarModel(Model):
    """Model with two fields foo and bar."""

    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer()
    name = model_template("{foo}_{bar}")


class ComplexModel(Model):
    """Model with fields and model fields."""

    foo_bar: FooBarModel
    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer()


complex_template = Template(
    "/root/{complex.foo_bar.foo}_{complex.foo_bar.bar}_{complex.foo}_{complex.bar}",
    complex=ComplexModel,
)


class ProjectModel(Model):
    """Model declaring templates."""

    name: str = string(r"[a-z]+")
    folder = model_template("/root/{name}")
    label = model_template("project_{name}")


class AssetModel(Model):
    """Model declaring a template that uses the template of its sub-model."""

    project: ProjectModel = reference(ProjectModel)
    type: str = string(r"[a-z]+")
    code: str = string(r"[a-z0-9]+")
    folder = model_template("{project.folder}/{type}/{code}")


def test_validate_simple_model_with_field() -> None:
    """Models are valid if they provide a template with a field."""

    class TestModel(Model):
        field: str = string(".+")


def test_fields_are_extracted_correctly() -> None:
    """References to fields are extracted correctly."""

    class TestModel(Model):
        test: str = string(r"\w+")
        template = model_template("{test}")

    template = TestModel.template

    assert len(TestModel.__typed_fields__) == 1
    assert "test" in TestModel.__typed_fields__
    assert template.chain.start_prefix == ""
    assert len(list(template.chain.iter_field_seps())) == 1
    assert template.regex.pattern == r"(?P<test>\w+)"


def test_sep_fields_are_extracted_correctly() -> None:
    """References to fields are extracted correctly including separators."""

    class TestModel(Model):
        test: str = string(r"\w+")
        template = model_template("sep{test}other")

    template = TestModel.template

    assert len(TestModel.__typed_fields__) == 1
    assert "test" in TestModel.__typed_fields__
    assert template.chain.start_prefix == "sep"
    field_seps = list(template.chain.iter_field_seps())
    assert len(field_seps) == 1
    assert field_seps[0].reference.name == "test"
    assert field_seps[0].suffix == "other"
    assert template.regex.pattern == r"sep(?P<test>\w+)other"


def test_model_can_reference_field_multiple_times() -> None:
    """A model can reference multiple times in its template."""

    class TestModel(Model):
        test: str = string(r"\w+")
        template = model_template("{test}/{test}")

    template = TestModel.template

    assert len(TestModel.__typed_fields__) == 1
    assert "test" in TestModel.__typed_fields__
    assert len(list(template.chain.iter_field_seps())) == 2  # noqa: PLR2004
    assert template.regex.pattern == r"(?P<test>\w+)/(?P=test)"


def test_model_can_reference_other_models_through_model_field() -> None:
    """A model can reference other models through the model field."""

    class FirstModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")

    class SecondModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")
        first: FirstModel
        template = model_template(
            "{foo}/{bar}/{first.foo}_{first.bar}/{first.foo}_{foo}_{bar}"
        )

    second_template = SecondModel.template

    assert len(SecondModel.__typed_fields__) == 2  # noqa: PLR2004
    assert len(SecondModel.__model_refs__) == 1
    assert (
        second_template.regex.pattern == r"(?P<foo>[a-zA-Z0-9]+)/(?P<bar>\w+)/"
        r"(?P<first__foo>[a-zA-Z0-9]+)_(?P<first__bar>\w+)/"
        r"(?P=first__foo)_(?P=foo)_(?P=bar)"
    )
    assert second_template.regex.match("foo/bar/ffoo_fbar/ffoo_foo_bar") is not None


def test_model_can_reference_fields_of_nested_sub_models() -> None:
    """Tokens shall reach the fields of the sub-models of a sub-model."""

    class Leaf(Model):
        value: int = integer()

    class Middle(Model):
        leaf: Leaf
        name: str = string(r"[a-z]+")

    class Root(Model):
        middle: Middle
        template = model_template("{middle.name}/{middle.leaf.value}")

    template = Root.template
    root = Root(Middle(Leaf(1), "foo"))

    assert (
        template.regex.pattern
        == r"(?P<middle__name>[a-z]+)/(?P<middle__leaf__value>\d+)"
    )
    assert template.format(root) == "foo/1"
    assert template.parse("foo/1") == {"middle": root.middle}


def test_model_can_reference_model_declared_with_reference() -> None:
    """Sub-models declared with reference shall provide tokens like annotated ones."""

    class TestModel(Model):
        foo_bar: FooBarModel = reference(FooBarModel)
        template = model_template("{foo_bar.foo}_{foo_bar.bar}")

    assert list(TestModel.__model_refs__) == ["foo_bar"]
    assert TestModel.template.parse("foo_1") == {"foo_bar": FooBarModel("foo", 1)}


def test_declared_template_accepts_field_named_like_template_arguments() -> None:
    """A field name shall not collide with the arguments building the template."""

    class SubModel(Model):
        pattern: str = string(r"[a-z]+")

    class TestModel(Model):
        sub: SubModel
        pattern: str = string(r"[a-z]+")
        template = model_template("{pattern}_{sub.pattern}")

    assert TestModel.template.parse("foo_bar") == {
        "sub": SubModel("bar"),
        "pattern": "foo",
    }


def test_model_provides_its_token() -> None:
    """A model shall provide a token, its value being an instance of the model."""
    template = Template("sep/{foo_bar.name}", foo_bar=FooBarModel)

    assert template.parse("sep/foo_1") == {"foo_bar": FooBarModel("foo", 1)}
    assert template.format({"foo_bar": FooBarModel("foo", 1)}) == "sep/foo_1"
    assert template.tokens["foo_bar"] is FooBarModel.__token__
    assert not isinstance(FooBarModel, Token)


def test_model_token_is_a_compound_without_pattern() -> None:
    """A model token shall hold its fields and sub-models, its templates as aliases."""
    token = ComplexModel.__token__
    alias = FooBarModel.__token__.aliases["name"]

    assert isinstance(token, Compound)
    assert list(token.tokens) == ["foo_bar", "foo", "bar"]
    assert token.tokens["foo_bar"] is FooBarModel.__token__
    assert token.tokens["foo"] is ComplexModel.__fields__["foo"]
    assert token.chain is None
    assert list(FooBarModel.__token__.aliases) == ["name"]
    assert alias.chain is FooBarModel.name.chain
    assert token.parse_value(
        {"foo_bar": {"foo": "a", "bar": "1"}, "foo": "b", "bar": "2"}
    ) == (ComplexModel(FooBarModel("a", 1), "b", 2))


def test_declared_template_can_be_used_as_template_token() -> None:
    """A declared template shall be usable wherever a template is."""
    template = Template("sep/{foo_bar}", foo_bar=FooBarModel.name)

    assert template.regex.pattern == (
        r"sep/(?P<foo_bar>(?P<foo_bar__foo>[a-zA-Z0-9]+)_(?P<foo_bar__bar>\d+))"
    )
    assert template.parse("sep/foo_1") == {"foo_bar": {"foo": "foo", "bar": 1}}
    assert template.format({"foo_bar": FooBarModel("foo", 1)}) == "sep/foo_1"


def test_definition_fails_referencing_unknown_field() -> None:
    """Definition of model shall fail when referencing an unknown field."""
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            other: str = string(r"\w+")
            template = model_template("{test}")


def test_definition_fails_if_field_starts_with_underscore() -> None:
    """Definition of model shall fail if the field starts with underscore."""
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            _test: str = string(r"\w+")


def test_definition_fails_if_field_ends_with_underscore() -> None:
    """Definition of model shall fail if the field ends with underscore."""
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            test_: str = string(r"\w+")


def test_definition_fails_if_field_contain_double_underscore() -> None:
    """Definition of model shall fail if the field contains underscore.

    We need this to make sure there is no collision between the name of the field and
    the __ used as separator in capturing groups.
    """
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            foo__bar: str = string(r"\w+")


def test_definition_fails_if_attribute_shadows_metaclass_method() -> None:
    """No attribute shall hide the public methods of the metaclass of the models."""
    with pytest.raises(DefinitionError, match=r"\['mro'\]"):

        class _ElementModel(Model):
            name: str = string(r"[a-z]+")
            mro: FooBarModel
            template = model_template("{name}/{mro.name}")


def test_model_elements_can_take_names_of_token_methods() -> None:
    """The model being no token, its elements shall take the names of token methods."""

    class TestModel(Model):
        tokens: str = string(r"[a-z]+")
        aliases: FooBarModel
        chain = model_template("{tokens}/{aliases.name}")

        def build_value(self) -> str:
            return self.tokens

    model = TestModel("foo", FooBarModel("bar", 1))

    assert TestModel.chain.parse("foo/bar_1") == {
        "tokens": "foo",
        "aliases": model.aliases,
    }
    assert model.build_value() == "foo"


def test_definition_fails_if_element_shadows_model_method() -> None:
    """No field, sub-model or template shall shadow the methods of Model."""
    with pytest.raises(
        DefinitionError, match=r"\['from_dict', 'to_dict', 'to_flat_dict'\]"
    ):

        class _TestModel(Model):
            to_dict: str = string(r"[a-z]+")  # type: ignore[assignment]  # ty: ignore[invalid-attribute-override]
            to_flat_dict: FooBarModel  # type: ignore[assignment]  # ty: ignore[invalid-attribute-override]
            from_dict = model_template("{to_dict}/{to_flat_dict.name}")  # type: ignore[assignment]  # ty: ignore[invalid-attribute-override]


def test_model_methods_can_be_overridden() -> None:
    """The methods of a model shall override the methods of Model."""

    class TestModel(Model):
        name: str = string(r"[a-z]+")

        def to_dict(self) -> dict[str, Any]:
            return {**super().to_dict(), "upper": self.name.upper()}

    assert TestModel("foo").to_dict() == {"name": "foo", "upper": "FOO"}


def test_definition_fails_referencing_incorrectly_typed_field() -> None:
    """Definition of model shall fail when referencing a field with the wrong type."""
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            test: str = "test"
            template = model_template("{test}")


def test_definition_fails_with_missing_attribute() -> None:
    """Definition of model shall fail when referencing a missing attribute."""
    with pytest.raises(DefinitionError):

        class _TestModel(Model):
            template = model_template("{.}")


def test_definition_fails_with_missing_model_field() -> None:
    """Definition oif model fails if all the fields are not used in the template."""
    with pytest.raises(DefinitionError, match=r"\['bar'\]"):

        class _TestModel(Model):
            foo: str = string(r"[a-zA-Z0-9]+")
            bar: str = string(r"\w+")
            template = model_template("{foo}")


def test_definition_fails_with_missing_sub_model_field() -> None:
    """Definition of model fails if all the fields are not used in the template."""

    class FirstModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: str = string(r"\w+")

    with pytest.raises(DefinitionError, match=r"\['first\.bar'\]"):

        class _SecondModel(Model):
            foo: str = string(r"[a-zA-Z0-9]+")
            bar: str = string(r"\w+")
            first: FirstModel
            template = model_template("{foo}/{bar}/{first.foo}")  # first.bar missing


def test_definition_fails_referencing_unknown_sub_model_field() -> None:
    """Definition of model fails if a token targets an unknown sub-model field."""
    with pytest.raises(DefinitionError):
        Template(
            "/root/{complex.foo_bar.foo}_{complex.foo_bar.nope}_{complex.foo}",
            complex=ComplexModel,
        )  # foo_bar.nope is invalid


def test_definition_fails_referencing_whole_sub_model() -> None:
    """Definition of model fails if a token targets a sub-model and not its fields.

    A model has no pattern of its own so there is no way to build the regex of such
    token.
    """
    with pytest.raises(DefinitionError, match=r"\{foo_bar\}: .* no pattern of its own"):

        class _TestModel(Model):
            foo_bar: FooBarModel
            foo: str = string(r"[a-zA-Z0-9]+")
            template = model_template("/root/{foo_bar}_{foo}")


def test_model_is_instantiated_correctly() -> None:
    """Models are instantiated correctly if all arguments are provided."""
    model_inst = FooBarModel("test", 1)
    assert model_inst.foo == "test"
    assert model_inst.bar == 1


def test_model_eq() -> None:
    """Models are equal if their fields are equal."""
    mode1 = ComplexModel(FooBarModel("test", 1), "foo", 1)
    mode2 = ComplexModel(FooBarModel("test", 1), "foo", 1)
    assert mode1 == mode2


def test_model_eq_different() -> None:
    """Models are different if their fields are not equal."""
    mode1 = ComplexModel(FooBarModel("test", 1), "foo", 1)
    mode2 = ComplexModel(FooBarModel("test", 2), "foo", 1)
    assert mode1 != mode2


def test_model_eq_different_type() -> None:
    """Models are different if the type is different, event if fields are identical."""

    class OtherFooBarModel(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: int = integer()

    mode1 = FooBarModel("test", 1)
    mode2 = OtherFooBarModel("test", 1)
    assert mode1 != mode2


def test_model_is_hashable() -> None:
    """Models are hashable."""
    assert hash(FooBarModel("test", 1))


def test_model_is_instantiable_with_kwargs() -> None:
    """Models are instantiated using keyword arguments."""
    FooBarModel(foo="test", bar=1)


def test_model_instantiation_fails_if_missing_arguments() -> None:
    """Models instantiation shall raise TypeError if missing arguments."""
    with pytest.raises(TypeError):
        FooBarModel("test")  # type: ignore[call-arg]  # ty: ignore[missing-argument]


def test_model_instantiation_fails_if_too_many_arguments() -> None:
    """Models instantiation shall raise TypeError if there are too many arguments."""
    with pytest.raises(TypeError):
        FooBarModel("test", 1, "excess")  # type: ignore[call-arg]  # ty: ignore[too-many-positional-arguments]

    with pytest.raises(TypeError):
        FooBarModel("test", 1, foo="foo")  # type: ignore[misc]  # ty: ignore[parameter-already-assigned]


def test_model_from_dict() -> None:
    """Models shall be initializable from a dict nesting the data of sub-models."""
    data = {"foo": "foo", "bar": 1, "foo_bar": {"foo": "foo", "bar": 2}}
    inst = ComplexModel.from_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_dict_excess() -> None:
    """Models shall still initialize if there are too many keys."""
    data = {
        "foo": "foo",
        "bar": 1,
        "foo_bar": {"foo": "foo", "bar": 2, "unknown": 42},
        "unknown": 42,
    }
    inst = ComplexModel.from_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_dict_parses_values() -> None:
    """Models shall parse and validate the values of the dict with their fields."""
    assert FooBarModel.from_dict({"foo": "foo", "bar": "1"}) == FooBarModel("foo", 1)
    with pytest.raises(ParseError):
        FooBarModel.from_dict({"foo": "foo", "bar": "one"})


def test_model_from_dict_fail_with_missing_key() -> None:
    """Models shall raise TypeError if missing key."""
    data = {"foo": "foo", "bar": 1, "foo_bar": {"foo": "foo"}}
    with pytest.raises(TypeError):
        ComplexModel.from_dict(data)


def test_model_from_flat_dict() -> None:
    """Models shall be initializable from a flat dict keyed by dotted paths."""
    data = {"foo": "foo", "bar": 1, "foo_bar.foo": "foo", "foo_bar.bar": 2}
    inst = ComplexModel.from_flat_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_flat_dict_excess() -> None:
    """Models shall still initialize if there are too many keys."""
    data = {
        "foo": "foo",
        "bar": 1,
        "foo_bar.foo": "foo",
        "foo_bar.bar": 2,
        "unknown": 42,
        "unknown.foo": 42,
    }
    inst = ComplexModel.from_flat_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_flat_dict_with_unflattened_sub_model() -> None:
    """Models shall still initialize if the data contains sub model key."""
    data = {
        "foo": "foo",
        "bar": 1,
        "foo_bar": "foo_2",
        "foo_bar.foo": "foo",
        "foo_bar.bar": 2,
    }
    inst = ComplexModel.from_flat_dict(data)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_from_flat_dict_fail_with_missing_key() -> None:
    """Models shall raise TypeError if missing key."""
    data = {"foo": "foo", "bar": 1, "foo_bar.foo": "foo"}
    with pytest.raises(TypeError):
        ComplexModel.from_flat_dict(data)


def test_model_to_dict() -> None:
    """Models shall convert to a dict nesting the data of sub-models."""
    inst = ComplexModel(FooBarModel("foo", 2), "foo", 1)
    data = inst.to_dict()

    assert data == {"foo_bar": {"foo": "foo", "bar": 2}, "foo": "foo", "bar": 1}
    assert ComplexModel.from_dict(data) == inst


def test_model_to_flat_dict() -> None:
    """Models shall convert to a flat dict keyed by dotted paths, at any depth."""

    class ShotModel(Model):
        asset: AssetModel
        number: int = integer()

    shot = ShotModel(AssetModel(ProjectModel("foo"), "chr", "bar"), 10)
    data = shot.to_flat_dict()

    assert data == {
        "asset.project.name": "foo",
        "asset.type": "chr",
        "asset.code": "bar",
        "number": 10,
    }
    assert ShotModel.from_flat_dict(data) == shot


def test_model_parse() -> None:
    """Models shall parse successfully."""
    inst = complex_template.parse("/root/foo_2_foo_1")["complex"]
    assert isinstance(inst, ComplexModel)
    assert inst == ComplexModel(FooBarModel("foo", 2), "foo", 1)


def test_model_parse_fail_raises_parse_error() -> None:
    """Models shall raise ParseError if parse fails."""
    with pytest.raises(ParseError):
        complex_template.parse("/nope/foo_2foo_1")


def test_model_parse_validates_what_regex_cannot_express() -> None:
    """Models shall raise ParseError if a value matches the regex but is not valid."""

    class TestModel(Model):
        value: int = integer(maximum=5)
        template = model_template("{value}")

    assert TestModel.template.parse("5") == {"value": 5}
    with pytest.raises(ParseError):
        TestModel.template.parse("6")


def test_model_parse_with_repeated_token() -> None:
    """Repeated tokens shall hold the same value when parsing."""

    class TestModel(Model):
        test: str = string(r"\w+")
        template = model_template("{test}/{test}")

    assert TestModel.template.parse("foo/foo") == {"test": "foo"}
    with pytest.raises(ParseError):
        TestModel.template.parse("foo/bar")


def test_model_format() -> None:
    """Model templates shall format model instances, as the inverse of parse."""
    inst = ComplexModel(FooBarModel("foo", 2), "foo", 1)
    formatted = complex_template.format({"complex": inst})

    assert formatted == "/root/foo_2_foo_1"
    assert complex_template.parse(formatted) == {"complex": inst}


def test_model_format_fail_raises_format_error() -> None:
    """Model templates shall raise FormatError if a value is not valid."""

    class TestModel(Model):
        value: int = integer(maximum=5)
        template = model_template("{value}")

    with pytest.raises(FormatError):
        TestModel.template.format(TestModel(6))


def test_model_repr() -> None:
    """Models shall return a string when using repr."""
    assert isinstance(repr(ComplexModel(FooBarModel("foo", 2), "foo", 1)), str)


def test_declared_template_works_on_its_model() -> None:
    """A template declared in a model shall parse and format the fields of the model."""
    assert ProjectModel.folder.parse("/root/foo") == {"name": "foo"}
    assert ProjectModel.folder.format(ProjectModel("foo")) == "/root/foo"
    assert ProjectModel.folder.format({"name": "foo"}) == "/root/foo"
    assert ProjectModel.folder.pattern == "/root/{name}"


def test_declared_template_is_reachable_from_instances() -> None:
    """A template declared in a model shall be reachable from the model instances."""
    assert ProjectModel("foo").folder is ProjectModel.folder


def test_declared_template_can_use_template_of_sub_model() -> None:
    """A declared template shall be usable in the templates of other models."""
    asset = AssetModel(ProjectModel("foo"), "chr", "bar")

    assert AssetModel.folder.pattern == "{project.folder}/{type}/{code}"
    assert AssetModel.folder.regex.pattern == (
        r"/root/(?P<project__name>[a-z]+)/(?P<type>[a-z]+)/(?P<code>[a-z0-9]+)"
    )
    assert AssetModel.folder.format(asset) == "/root/foo/chr/bar"
    assert AssetModel(**AssetModel.folder.parse("/root/foo/chr/bar")) == asset


def test_declared_template_can_use_template_of_nested_sub_model() -> None:
    """Declared templates shall be usable through several levels of sub-models."""

    class ShotModel(Model):
        asset: AssetModel
        number: int = integer(padding=3)
        file = model_template("{asset.folder}/{number}.ma")
        cache = model_template(
            "{asset.project.folder}/cache/{asset.type}_{asset.code}_{number}"
        )

    shot = ShotModel(AssetModel(ProjectModel("foo"), "chr", "bar"), 12)

    assert ShotModel.file.format(shot) == "/root/foo/chr/bar/012.ma"
    assert ShotModel(**ShotModel.file.parse("/root/foo/chr/bar/012.ma")) == shot
    assert ShotModel.cache.format(shot) == "/root/foo/cache/chr_bar_012"
    assert ShotModel(**ShotModel.cache.parse("/root/foo/cache/chr_bar_012")) == shot


def test_declared_templates_of_sub_model_share_its_fields() -> None:
    """Fields reached through several templates of a sub-model shall hold one value."""
    template = Template(
        "{asset.project.folder}/{asset.type}/{asset.code}/{asset.project.label}",
        asset=AssetModel,
    )

    assert template.parse("/root/foo/chr/bar/project_foo") == {
        "asset": AssetModel(ProjectModel("foo"), "chr", "bar")
    }
    with pytest.raises(ParseError):
        template.parse("/root/foo/chr/bar/project_baz")


def test_template_can_use_template_declared_on_model_token() -> None:
    """A template shall be able to use the templates declared on a model token."""
    template = Template("{asset.folder}/data.json", asset=AssetModel)
    asset = AssetModel(ProjectModel("foo"), "chr", "bar")

    assert template.format({"asset": asset}) == "/root/foo/chr/bar/data.json"
    assert template.parse("/root/foo/chr/bar/data.json") == {"asset": asset}


def test_declared_template_can_only_use_templates_declared_before_it() -> None:
    """Declared templates shall be bound in declaration order."""

    class TestModel(Model):
        name: str = string(r"[a-z]+")
        folder = model_template("/root/{name}")
        file = model_template("{folder}/data.json")

    assert TestModel.file.parse("/root/foo/data.json") == {"name": "foo"}

    with pytest.raises(DefinitionError, match=r"_TestModel\.first"):

        class _TestModel(Model):
            name: str = string(r"[a-z]+")
            first = model_template("{second}/data.json")
            second = model_template("/root/{name}")


def test_declared_template_fails_at_model_definition() -> None:
    """An invalid declared template shall fail when its model is defined."""
    with pytest.raises(DefinitionError, match=r"_TestModel\.folder"):

        class _TestModel(Model):
            name: str = string(r"[a-z]+")
            folder = model_template("/root/{nope}")


def test_template_fails_referencing_unknown_element_of_sub_model() -> None:
    """A token targeting neither a field nor a template of a sub-model shall fail."""
    with pytest.raises(DefinitionError):
        Template("{asset.project.nope}/{asset.type}/{asset.code}", asset=AssetModel)


def test_model_inherits_fields_and_declared_templates() -> None:
    """Sub-classes shall inherit the fields and declared templates of their model."""

    class SpecialAsset(AssetModel):
        pass

    template = Template("{asset.folder}", asset=SpecialAsset)
    asset = template.parse("/root/foo/chr/bar")["asset"]

    assert list(SpecialAsset.__fields__) == ["project", "type", "code"]
    assert SpecialAsset.folder is not AssetModel.folder
    assert type(asset) is SpecialAsset
    assert asset == SpecialAsset(ProjectModel("foo"), "chr", "bar")


def test_inherited_template_shall_reference_new_fields() -> None:
    """A sub-class adding fields shall redeclare the templates it inherits."""
    with pytest.raises(DefinitionError, match=r"_VersionedProject\.folder"):

        class _VersionedProject(ProjectModel):
            version: int = integer()

    class VersionedProject(ProjectModel):
        version: int = integer()
        folder = model_template("/root/{name}/v{version}")
        label = model_template("project_{name}_v{version}")

    assert VersionedProject.folder.parse("/root/foo/v1") == {"name": "foo", "version": 1}
