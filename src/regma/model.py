"""Template model implementation."""

from __future__ import annotations

import collections
import contextlib
import typing
from typing import Any
from typing import ClassVar
from typing import TypeVar

from typing_extensions import Self  # noqa: UP035
from typing_extensions import dataclass_transform

from regma import DefinitionError
from regma.core import AbstractField
from regma.core import BoundField
from regma.core import Strictness
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import string
from regma.template import BoundTemplate
from regma.template import Template
from regma.template import create_bound_template

T_mod = TypeVar("T_mod", bound="Model")


def _validate_field_name(model_cls: ModelMeta) -> None:
    for attr in (*model_cls.__model_refs__, *model_cls.__typed_fields__):
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


class ModelMeta(type):
    """Validates and wires up a TemplateModel subclass at definition time.

    1. Injects ``name`` into all :class:`Field` and :class:`~regma.slot.Slot`
       descriptors.
    2. Normalizes ``template`` (string or :class:`~regma.core.Chain`) and
       compiles a full regex.
    3. Validates that every Field/Slot appears in the chain (and vice versa).
    4. Validates sub-field accesses (``slot.field``) against the sub-model.
    """

    __field_names__: list[str]
    __typed_fields__: dict[str, BoundField[AbstractField[Any]]]
    __fields__: dict[str, BoundField[AbstractField[Any]] | type[Model]]
    __model_refs__: dict[str, type[Model]]
    __templates__: dict[Template[Model], BoundTemplate[Model]]

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
        for attr, hint in typing.get_type_hints(cls).items():
            if not isinstance(hint, type):
                continue

            attr_value = namespace.get(attr)

            if issubclass(hint, Model) and attr_value is None:
                setattr(cls, attr, hint)
                __model_refs[attr] = hint
                __fields[attr] = hint

            elif isinstance(attr_value, AbstractField):
                new_field = BoundField(attr, attr_value)
                __bound_fields[attr] = BoundField(attr, attr_value)
                __fields[attr] = new_field

        cls.__fields__ = __fields
        cls.__typed_fields__ = __bound_fields
        cls.__model_refs__ = __model_refs

        _validate_field_name(cls)
        __contents = [namespace, *[b.__dict__ for b in bases]]

        # Process all the templates defined in the model
        __bound_templates: dict[Template[Model], BoundTemplate[Model]] = {}
        for attr_value in namespace.values():
            if not isinstance(attr_value, Template):
                continue

            __bound_template = create_bound_template(attr_value, cls)
            __bound_templates[attr_value] = __bound_template

        cls.__templates__ = __bound_templates

        return cls


def reference(model_cls: type[Model]) -> Any:  # noqa: ANN401
    """Return a model reference from the given model class."""
    return model_cls


@dataclass_transform(field_specifiers=(string, integer, choice, custom_field, reference))
class Model(metaclass=ModelMeta, fsm_validation=True):
    r"""Base class for all declarative template models.

    Subclass to declare a typed, bidirectional string template:

    class AssetResult(TemplateModel):
        type: str = string("[a-zA-Z]+")
        code: str = string("\w+")
        __template__ = "{asset_type}_{code}"

    Parse:

        result = AssetResult.parse("chr_toto")
        result.type   # "chr"
        result.code   # "toto"

    Format:

        str(result)   # "chr_toto"
    """

    __dataclass_transform__: ClassVar[dict[str, Any]]
    __typed_fields__: ClassVar[dict[str, BoundField[AbstractField[Any]]]]
    __fields__: ClassVar[dict[str, BoundField[AbstractField[Any]] | type[Model]]]
    __model_refs__: ClassVar[dict[str, type[Model]]]
    __templates__: ClassVar[dict[Template[Self], BoundTemplate[Self]]]

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
    def from_flat_dict(
        cls, data: dict[str, Any], strictness_override: Strictness | None = None
    ) -> Self:
        """Return a model from the given flattened dictionary data.

        The input dict is assumed to be as the regex of the model would return it.
        """
        inst_kwargs: dict[str, Any] = {}
        data_by_model_field: dict[str, dict[str, Any]] = collections.defaultdict(dict)

        for key, value in data.items():
            if key in cls.__model_refs__:  # skipped, we have the sub attribute
                continue

            field_split = key.split("__", maxsplit=1)
            attr = field_split[0]

            # this is a direct field
            if len(field_split) == 1:
                with contextlib.suppress(KeyError):
                    inst_kwargs[attr] = cls.__typed_fields__[attr].field.parse_value(
                        value, strictness_override
                    )
            else:
                data_by_model_field[attr][field_split[1]] = value

        for field_name, field_data in data_by_model_field.items():
            sub_model_cls = cls.__model_refs__[field_name]
            sub_model = sub_model_cls.from_flat_dict(field_data, strictness_override)
            inst_kwargs[field_name] = sub_model

        return cls(**inst_kwargs)
