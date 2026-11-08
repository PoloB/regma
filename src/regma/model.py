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

from regma.chain import ChainAlias
from regma.core import Node
from regma.core import Token
from regma.error import DefinitionError
from regma.field import AbstractField
from regma.field import BoundField
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import string
from regma.template import Template
from regma.template import _nest_dict

if TYPE_CHECKING:
    from collections.abc import Mapping

    from regma.core import AnyNode


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

    Any attribute of a model hides the methods of its metaclass, which make the model a
    token, so none can take their names. The fields, sub-models and templates cannot
    take the names of the methods of Model either, which methods can still override.
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


class ModelCompound(Node["Model", dict[str, Any]]):
    """A model as a node, giving the tokens of templates access to its fields.

    A model has no pattern of its own: dotted tokens reach its fields, its sub-models
    and its declared templates, which are aliases standing for references to its fields.
    """

    def __init__(self, model_cls: type[Model], name: str) -> None:
        """Initialize the node of the given model, reached by the given token name."""
        self._model = model_cls
        self._name = name
        self._nodes: dict[str, AnyNode] = {
            attr: element
            if isinstance(element, BoundField)
            else ModelCompound(element, f"{name}.{attr}")
            for attr, element in model_cls.__fields__.items()
        }
        self._nodes.update(
            (attr, ChainAlias(template.chain))
            for attr, template in model_cls.__templates__.items()
        )

    @override
    def to_regex(self) -> str:
        raise self._no_pattern_error()

    @override
    def to_chain(self) -> None:
        return None

    @override
    def get_nodes(self) -> Mapping[str, AnyNode]:
        return self._nodes

    @override
    def format_value(self, value: Model) -> str:
        raise self._no_pattern_error()

    @override
    def parse_value(self, raw: dict[str, Any]) -> Model:
        return self._model.from_dict(raw)

    def _no_pattern_error(self) -> DefinitionError:
        """Return the error raised when a template uses the model as a whole."""
        msg = (
            f"Token {{{self._name}}} is the model {self._model.__name__}, which has no "
            f"pattern of its own: reference its fields or templates instead"
        )
        return DefinitionError(msg)


class ModelMeta(type, Token):
    """Validates and wires up a Model subclass at definition time.

    1. Binds the fields and sub-models declared through annotations, including the
       ones inherited from base models.
    2. Validates the field names, and that no attribute shadows a model method.
    3. Binds the templates declared with :func:`model_template` to the model.

    The models are also tokens: a template reaches the fields and declared templates
    of a model through dotted paths, and the value of the token is a model instance.
    """

    __field_names__: list[str]
    __typed_fields__: dict[str, BoundField[AbstractField[Any]]]
    __fields__: dict[str, BoundField[AbstractField[Any]] | type[Model]]
    __model_refs__: dict[str, type[Model]]
    __templates__: dict[str, Template]

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **_kwargs: Any,  # noqa: ANN401
    ) -> ModelMeta:
        """Build the template model internals (fields -> bound fields, chain, regex)."""
        cls: ModelMeta = super().__new__(mcs, name, bases, namespace)

        # Skip the bare Model base itself
        if name == "Model":
            return cls

        # Create bounded field objects
        __bound_fields: dict[str, BoundField[Any]] = {}
        __model_refs: dict[str, type[Model]] = {}
        __fields: dict[str, BoundField[AbstractField[Any]] | type[Model]] = {}

        # First evaluate the model field references by checking annotations
        for attr, hint in get_type_hints(cls).items():
            if not isinstance(hint, type):
                continue

            # Fields inherited from a base model are found already bound on the class
            attr_value = namespace.get(attr, getattr(cls, attr, None))
            if isinstance(attr_value, BoundField):
                attr_value = attr_value.field

            if issubclass(hint, Model) and attr_value in (None, hint):
                setattr(cls, attr, hint)
                __model_refs[attr] = hint
                __fields[attr] = hint

            elif isinstance(attr_value, AbstractField):
                new_field = BoundField(attr, attr_value)
                setattr(cls, attr, new_field)
                __bound_fields[attr] = BoundField(attr, attr_value)
                __fields[attr] = new_field

        cls.__fields__ = __fields
        cls.__typed_fields__ = __bound_fields
        cls.__model_refs__ = __model_refs

        _validate_field_name(cls)
        _validate_shadowing(cls)

        # Bind the templates in declaration order, the tokens of a template being the
        # fields of the model and the templates declared before it
        cls.__templates__ = {}
        tokens: dict[str, Token] = {
            attr: element.field if isinstance(element, BoundField) else element
            for attr, element in cls.__fields__.items()
        }
        for attr, declaration in _get_declared_templates(cls).items():
            try:
                template = Template(declaration.pattern, **tokens)
            except DefinitionError as e:
                msg = f"{name}.{attr}: {e}"
                raise DefinitionError(msg) from e

            # Template shall contain all the elements required to build its model
            referenced = {
                ref_sep.reference.name.partition(".")[0]
                for ref_sep in template.chain.iter_field_seps()
            }
            missing = sorted(set(cls.__fields__) - referenced)
            if missing:
                msg = (
                    f"{name}.{attr}: Template {declaration.pattern!r} does not "
                    f"reference fields {missing}"
                )
                raise DefinitionError(msg)

            cls.__templates__[attr] = template
            # The next templates use it as an alias of the fields it references
            tokens[attr] = ChainAlias(template.chain)

        return cls

    @override
    def to_node(cls, name: str) -> AnyNode:
        return ModelCompound(cast("type[Model]", cls), name)


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
    __typed_fields__: ClassVar[dict[str, BoundField[AbstractField[Any]]]]
    __fields__: ClassVar[dict[str, Union[BoundField[AbstractField[Any]], type[Model]]]]  # noqa: UP007 due to python 3.9 not supporting the | annotation
    __model_refs__: ClassVar[dict[str, type[Model]]]
    __templates__: ClassVar[dict[str, Template]]

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
        kwargs: dict[str, Any] = {}
        for name, element in cls.__fields__.items():
            # The model reports the missing fields when instantiated
            if name not in data:
                continue

            if isinstance(element, BoundField):
                kwargs[name] = element.parse_value(data[name])
            else:
                kwargs[name] = element.from_dict(data[name])

        return cls(**kwargs)

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
