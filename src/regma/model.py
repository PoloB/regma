"""Template model implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Union
from typing import cast

from typing_extensions import Self  # noqa: UP035
from typing_extensions import dataclass_transform
from typing_extensions import get_type_hints
from typing_extensions import override

from regma.core import ChainAlias
from regma.core import Compound
from regma.error import DefinitionError
from regma.field import AbstractField
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import string
from regma.template import Template
from regma.template import _nest_dict

if TYPE_CHECKING:
    from collections.abc import Mapping

    from regma.core import Token


def _validate_field_name(model_cls: ModelMeta) -> None:
    for attr in (*model_cls.__model_refs__, *model_cls.__typed_fields__):
        if attr.startswith("_"):
            msg = (
                f"{model_cls.__name__}: field attribute {attr!r} cannot starts with "
                f"underscore (reserved for regex construction)"
            )
            raise DefinitionError(msg)

        if attr.endswith("_"):
            msg = (
                f"{model_cls.__name__}: field attribute {attr!r} cannot ends with "
                f"underscore (reserved for regex construction)"
            )
            raise DefinitionError(msg)

        if "__" in attr:
            msg = (
                f"{model_cls.__name__}: field attribute {attr!r} cannot contains "
                f"double underscores (reserved for regex construction)"
            )
            raise DefinitionError(msg)


def _validate_shadowing(model_cls: ModelMeta) -> None:
    """Raise DefinitionError if an attribute of the model shadows a model method.

    Any attribute of a model hides the public methods of its metaclass, so none can take
    their names. The fields, sub-models and templates cannot take the names of the
    methods of Model either, which methods can still override.
    """
    meta_methods = {attr for attr in dir(type(model_cls)) if not attr.startswith("_")}
    model_methods = {attr for attr in dir(Model) if not attr.startswith("_")}
    # The annotations declare the fields and sub-models, even the ones without value
    elements = {*get_type_hints(model_cls), *_get_declared_templates(model_cls)}
    shadowing = sorted(
        (meta_methods & {*dir(model_cls), *elements}) | (model_methods & elements)
    )
    if shadowing:
        msg = (
            f"{model_cls.__name__}: attributes {shadowing} shadow methods of the models"
        )
        raise DefinitionError(msg)


def _get_declared_templates(model_cls: ModelMeta) -> dict[str, ModelTemplateDescriptor]:
    """Return the templates declared on the given model or its bases, in order."""
    return {
        attr: value
        for base in reversed(model_cls.__mro__)
        for attr, value in vars(base).items()
        if isinstance(value, ModelTemplateDescriptor)
    }


class ModelToken(Compound["Model"]):
    """The token of a model, whose value is an instance of the model.

    Dotted tokens reach the fields and the sub-models of the model, and its declared
    templates, which are aliases standing for its fields. A model has no pattern of its
    own, so it cannot be used as a whole.
    """

    def __init__(self, model_cls: type[Model]) -> None:
        """Initialize the token of the given model, from its fields and sub-models."""
        self._model = model_cls
        self._tokens = {
            name: element.__token__ for name, element in model_cls.__fields__.items()
        }
        self._aliases: dict[str, Token[Model]] = {}

    @property
    @override
    def tokens(self) -> Mapping[str, Token[Any]]:
        """Return the tokens of the fields and the sub-models, by name."""
        return self._tokens

    @property
    @override
    def aliases(self) -> Mapping[str, Token[Any]]:
        """Return the aliases of the declared templates, by name."""
        return self._aliases

    @override
    def build_value(self, values: dict[str, Any]) -> Model:
        return self._model(**values)

    def declare(self, name: str, pattern: str) -> Template:
        """Return the template declared on the model under the given name.

        The pattern uses the fields and the sub-models of the model, and the templates
        declared before, the next templates using it as an alias.

        Raises:
            DefinitionError: the template is not valid, or does not reference all the
                fields building the instances of the model.
        """
        template = Template(pattern, **self._tokens, **self._aliases)
        missing = sorted(set(self._tokens) - set(template.tokens))
        if missing:
            msg = f"Template {pattern!r} does not reference fields {missing}"
            raise DefinitionError(msg)

        self._aliases[name] = ChainAlias(template.chain, self)
        return template


class ModelMeta(type):
    """Validates and wires up a Model subclass at definition time.

    1. Binds the fields and sub-models declared through annotations, including the
       ones inherited from base models.
    2. Validates the field names, and that no attribute shadows a model method.
    3. Binds the templates declared with :func:`model_template` to the model.

    A model is not a token itself: it provides its token through ``__token__``, so that
    templates use the model as a token.
    """

    __field_names__: list[str]
    __typed_fields__: dict[str, AbstractField[Any]]
    __fields__: dict[str, AbstractField[Any] | type[Model]]
    __model_refs__: dict[str, type[Model]]
    __templates__: dict[str, Template]
    __token__: ModelToken

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **_kwargs: Any,  # noqa: ANN401
    ) -> ModelMeta:
        """Build the template model internals (fields, sub-models and templates)."""
        cls: ModelMeta = super().__new__(mcs, name, bases, namespace)

        # Skip the bare Model base itself
        if name == "Model":
            return cls

        __typed_fields: dict[str, AbstractField[Any]] = {}
        __model_refs: dict[str, type[Model]] = {}
        __fields: dict[str, AbstractField[Any] | type[Model]] = {}

        # First evaluate the model field references by checking annotations
        for attr, hint in get_type_hints(cls).items():
            if not isinstance(hint, type):
                continue

            # Fields inherited from a base model are found on the class
            attr_value = namespace.get(attr, getattr(cls, attr, None))
            if issubclass(hint, Model) and attr_value in (None, hint):
                setattr(cls, attr, hint)
                __model_refs[attr] = hint
                __fields[attr] = hint

            elif isinstance(attr_value, AbstractField):
                __typed_fields[attr] = attr_value
                __fields[attr] = attr_value

        cls.__fields__ = __fields
        cls.__typed_fields__ = __typed_fields
        cls.__model_refs__ = __model_refs

        _validate_field_name(cls)
        _validate_shadowing(cls)

        cls.__token__ = token = ModelToken(cast("type[Model]", cls))

        # Bind the templates in declaration order
        cls.__templates__ = {}
        for attr, declaration in _get_declared_templates(cls).items():
            try:
                cls.__templates__[attr] = token.declare(attr, declaration.pattern)
            except DefinitionError as e:
                msg = f"{name}.{attr}: {e}"
                raise DefinitionError(msg) from e

        return cls


def reference(model_cls: type[Model]) -> Any:  # noqa: ANN401
    """Return a model reference from the given model class."""
    return model_cls


@dataclass_transform(field_specifiers=(string, integer, choice, custom_field, reference))
class Model(metaclass=ModelMeta, fsm_validation=True):
    r"""Base class for all declarative template models.

    Subclass to declare typed fields and the templates of the model, then use the model
    as a token of other templates to convert its instances from and to a string:

    class Asset(Model):
        type: str = string("[a-zA-Z]+")
        code: str = string("\w+")
        name = model_template("{type}_{code}")

    template = Template("{asset.name}", asset=Asset)

    Parse:

        template.parse("chr_toto")  # {"asset": Asset("chr", "toto")}

    Format:

        template.format({"asset": Asset("chr", "toto")})  # "chr_toto"
    """

    __dataclass_transform__: ClassVar[dict[str, Any]]
    __typed_fields__: ClassVar[dict[str, AbstractField[Any]]]
    __fields__: ClassVar[dict[str, Union[AbstractField[Any], type[Model]]]]  # noqa: UP007 due to python 3.9 not supporting the | annotation
    __model_refs__: ClassVar[dict[str, type[Model]]]
    __templates__: ClassVar[dict[str, Template]]
    __token__: ClassVar[ModelToken]

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the template model with given kwargs arguments."""
        fields = list(self.__fields__)

        if len(args) > len(fields):
            msg = f"Expected {len(args)} arguments, got {len(fields)}"
            raise TypeError(msg)

        all_kwargs: dict[str, Any] = {}

        for i, value in enumerate(args):
            name = fields[i]
            all_kwargs[name] = value

        for name, value in kwargs.items():
            if name in all_kwargs:
                msg = f"Argument '{name}' provided more than once"
                raise TypeError(msg)
            all_kwargs[name] = value

        for name in fields:
            if name in all_kwargs:
                setattr(self, name, all_kwargs[name])
            else:
                msg = f"Missing required field: '{name}'"
                raise TypeError(msg)

    def __eq__(self, other: object) -> bool:
        """Return true if two models are equal (have the same values)."""
        if not isinstance(other, type(self)):
            return NotImplemented
        # All fields should be equals
        # Start with value fields to quicly eliminate two different objects
        for field_name in self.__fields__:
            if getattr(self, field_name) != getattr(other, field_name):
                return False

        return True

    def __hash__(self) -> int:
        """Return hash of model."""
        return hash((type(self), *(getattr(self, attr) for attr in self.__fields__)))

    def __repr__(self) -> str:
        """Return formatted representation of model."""
        kwargs_str = ", ".join(
            [f"{name}={getattr(self, name)!r}" for name in self.__fields__]
        )
        return f"{self.__class__.__name__}({kwargs_str})"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Return a model from a dictionary nesting the data of its sub-models.

        Each value is parsed and validated by its field, as when parsing a template, and
        the keys which are not fields of the model are ignored:

        Asset.from_dict({"project": {"name": "foo"}, "code": "bar"})

        Raises:
            ParseError: a value is not valid for its field.
            TypeError: a field has no value.
        """
        # The values are parsed as when parsing a template
        return cast("Self", cls.__token__.parse_value(data))

    @classmethod
    def from_flat_dict(cls, data: dict[str, Any]) -> Self:
        """Return a model from a dictionary keyed by the dotted paths of the fields.

        The paths are the ones of the template tokens, and the values are handled as in
        :meth:`from_dict`:

        Asset.from_flat_dict({"project.name": "foo", "code": "bar"})

        Raises:
            ParseError: a value is not valid for its field.
            TypeError: a field has no value.
        """
        return cls.from_dict(_nest_dict(data))

    def to_dict(self) -> dict[str, Any]:
        """Return the values of the fields, nesting the ones of the sub-models.

        The dictionary is structured as expected by :meth:`from_dict`.
        """
        data: dict[str, Any] = {}
        for name in self.__fields__:
            value = getattr(self, name)
            data[name] = value.to_dict() if name in self.__model_refs__ else value

        return data

    def to_flat_dict(self) -> dict[str, Any]:
        """Return the values of the fields keyed by their dotted paths.

        The dictionary is structured as expected by :meth:`from_flat_dict`.
        """
        data: dict[str, Any] = {}
        for name in self.__fields__:
            value = getattr(self, name)
            if name in self.__model_refs__:
                data.update(
                    (f"{name}.{path}", sub_value)
                    for path, sub_value in value.to_flat_dict().items()
                )
            else:
                data[name] = value

        return data


class ModelTemplateDescriptor:
    """Declaration of a template in the body of the model it works on."""

    def __init__(self, pattern: str) -> None:
        """Initialize the declaration with the pattern of the template."""
        self._pattern = pattern
        self._name = ""

    @property
    def pattern(self) -> str:
        """Return the pattern of the declared template."""
        return self._pattern

    def __set_name__(self, owner: type[Model], name: str) -> None:
        """Keep the attribute name, the model metaclass binds the template."""
        self._name = name

    def __get__(self, instance: object, owner: type[Model]) -> Template:
        """Return the template bound to the model it is accessed from."""
        return owner.__templates__[self._name]


def model_template(pattern: str) -> ModelTemplateDescriptor:
    """Declare a template in the body of the model it works on.

    The tokens of the template are the fields of the model, and the pattern shall use
    all of them. The template is reached from the model or its instances. Other
    templates can use it through its name, prefixed by the path of the model declaring
    it:

    class Project(Model):
        name: str = string("[a-z]+")
        folder = model_template("/root/{name}")

    class Asset(Model):
        project: Project
        code: str = string("[a-z]+")
        folder = model_template("{project.folder}/{code}")

    Asset.folder.parse("/root/foo/bar")  # {"project": Project("foo"), "code": "bar"}
    """
    return ModelTemplateDescriptor(pattern)
