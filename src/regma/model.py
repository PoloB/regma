"""Template model implementation."""

from __future__ import annotations

import collections
import contextlib
import re
import typing
from typing import Any
from typing import ClassVar
from typing import TypeVar

from typing_extensions import Self  # noqa: UP035
from typing_extensions import dataclass_transform

from regma import reference
from regma.core import AbstractField
from regma.core import BoundField
from regma.core import Chain
from regma.core import Delimiter
from regma.core import FieldReference
from regma.core import FormatableNode
from regma.core import Separator
from regma.core import Strictness
from regma.engine import AbstractRegexEngine
from regma.engine import BuiltinRegexEngine
from regma.error import DefinitionError
from regma.error import ParseError
from regma.field import ModelField
from regma.field import choice
from regma.field import custom_field
from regma.field import integer
from regma.field import string
from regma.validation.field import FieldNameValidator
from regma.validation.field import FieldReferenceValidator
from regma.validation.fsm import FsmNodeBuilder
from regma.validation.fsm import FsmNodeCache
from regma.validation.fsm import TemplateHasNoCollision
from regma.validation.fsm import TemplateHasNoEmptyToken


def _parse_template(template_model: TemplateModelMeta) -> Chain:
    """Convert a template string into a :class:`~regma.core.Chain`."""
    template = template_model.__template__
    delimiter = template_model.__delimiter__
    token_re = delimiter.token_re()
    nodes: list[FormatableNode] = []
    cursor = 0
    existing_field_references: dict[str, FieldReference] = {}

    for m in token_re.finditer(template):
        start, end = m.span()
        attr_name: str = m.group(1)

        attributes = attr_name.split(".")

        if start > cursor:
            nodes.append(Separator(template[cursor:start]))

        # Find the targeted field
        field_reference: FieldReference | None = None
        lookup_obj = template_model
        attribute_full_name = ""
        for attr in attributes:
            if not attr:
                continue

            attribute_full_name += attr
            field_reference = existing_field_references.get(attr)

            if field_reference:
                lookup_obj = getattr(lookup_obj, attr)
                field_reference = FieldReference(attribute_full_name, lookup_obj)
                attribute_full_name += "."
                continue

            try:
                lookup_obj = getattr(lookup_obj, attr)
            except AttributeError as e:
                msg = (
                    f"{template_model.__name__}: in reference {m.group()}, "
                    f"could not find attribute {attr!r} in {lookup_obj}"
                )
                raise DefinitionError(msg) from e

            if not isinstance(lookup_obj, AbstractField):
                msg = (
                    f"{template_model.__name__}: in reference {m.group()}, "
                    f"attribute {attribute_full_name!r} is not an AbstractField"
                )
                raise DefinitionError(msg)
            field_reference = FieldReference(attribute_full_name, lookup_obj)
            existing_field_references[attribute_full_name] = field_reference
            attribute_full_name += "."

        if field_reference is None:
            msg = f"Invalid attribute {attr_name}"
            raise DefinitionError(msg)

        nodes.append(field_reference)
        cursor = end

    if cursor < len(template):
        nodes.append(Separator(template[cursor:]))

    return Chain(nodes)


T_model = TypeVar("T_model", bound="TemplateModel")


class TemplateModelMeta(type):
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
    __fields__: dict[str, BoundField[AbstractField[Any]]]
    __model_fields__: dict[str, BoundField[ModelField[TemplateModel]]]
    __template__: str
    __delimiter__: Delimiter
    __chain__: Chain
    __regex__: str

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,  # noqa: ANN401
    ) -> TemplateModelMeta:
        """Build the template model internals (fields -> bound fields, chain, regex)."""
        cls: TemplateModelMeta = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Skip the bare TemplateModel base itself
        if name == "TemplateModel":
            return cls

        # Create bounded field objects
        __bound_fields: dict[str, BoundField[Any]] = {}
        __model_fields: dict[str, BoundField[ModelField[TemplateModel]]] = {}
        __fields: dict[str, BoundField[Any]] = {}

        # First evaluate the model field references by checking annotations
        for attr, hint in typing.get_type_hints(cls).items():
            if not isinstance(hint, type):
                continue

            attr_value = namespace.get(attr)

            if issubclass(hint, TemplateModel) and attr_value is None:
                model_field = ModelField(hint)
                setattr(cls, attr, model_field)
                new_model_bound_field = BoundField(attr, model_field)
                __model_fields[attr] = new_model_bound_field
                __fields[attr] = new_model_bound_field

            elif isinstance(attr_value, AbstractField):
                if isinstance(attr_value, ModelField):
                    bound_model_field = BoundField(attr, attr_value)
                    __model_fields[attr] = bound_model_field
                    __fields[attr] = bound_model_field
                else:
                    new_field = BoundField(attr, attr_value)
                    __bound_fields[attr] = BoundField(attr, attr_value)
                    __fields[attr] = new_field

        cls.__fields__ = __fields
        cls.__typed_fields__ = __bound_fields
        cls.__model_fields__ = __model_fields

        FieldNameValidator().validate(cls)

        # Validate template
        __raw_template: Any = namespace.get("__template__")
        if __raw_template is None:
            msg = f"{name}: must define a '__template__'"
            raise DefinitionError(msg)

        __contents = [namespace, *[b.__dict__ for b in bases]]
        # Go through all bases to get the delimiter
        __delimiters = (c.get("__delimiter__") for c in __contents)
        __delimiter = next(d for d in __delimiters if d is not None)

        if not isinstance(__delimiter, Delimiter):
            msg = (
                f"{name}: __delimiter__ must be a {Delimiter.__name__} instance, "
                f"got {type(__delimiter).__name__!r}"
            )
            raise DefinitionError(msg)

        __chain: Chain = _parse_template(cls)
        cls.__chain__ = __chain
        FieldReferenceValidator().validate(cls)
        # __fsm_builder = FsmNodeBuilder(FsmNodeCache())
        # TemplateHasNoEmptyToken(__fsm_builder).validate(cls)
        # TemplateHasNoCollision(__fsm_builder).validate(cls)

        # Go through all bases to get the regex engine
        __regex_engines = (c.get("__regex_engine__") for c in __contents)
        __regex_engine_cls = next(d for d in __regex_engines if d is not None)

        if not isinstance(__regex_engine_cls, type) or not issubclass(
            __regex_engine_cls, AbstractRegexEngine
        ):
            msg = (
                f"{name}: __regex_engine__ must be of type "
                f"{AbstractRegexEngine.__name__}, "
                f"got {type(__regex_engine_cls).__name__!r}"
            )
            raise DefinitionError(msg)

        cls.__regex__ = cls.__chain__.to_regex(__regex_engine_cls())

        return cls


@dataclass_transform(field_specifiers=(string, integer, choice, custom_field, reference))
class TemplateModel(metaclass=TemplateModelMeta):
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
    __chain__: Chain
    __delimiter__ = Delimiter.CURLY
    __typed_fields__: dict[str, BoundField[AbstractField[Any]]]
    __fields__: dict[str, BoundField[AbstractField[Any]]]
    __model_fields__: dict[str, BoundField[ModelField[TemplateModel]]]
    __regex_engine__: type[AbstractRegexEngine] = BuiltinRegexEngine
    __template__: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the template model with given kwargs arguments."""
        fields = list(self.fields())

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
        for field_name in self.fields():
            if getattr(self, field_name) != getattr(other, field_name):
                return False

        return True

    def __hash__(self) -> int:
        """Return hash of model."""
        return hash((type(self), *(getattr(self, attr) for attr in self.fields())))

    def __str__(self) -> str:
        """Return formatted representation of model."""
        return self.format()

    def __repr__(self) -> str:
        """Return formatted representation of model."""
        kwargs_str = ", ".join(
            [f"{name}={getattr(self, name)!r}" for name in self.fields()]
        )
        return f"{self.__class__.__name__}({kwargs_str})"

    @classmethod
    def fields(cls) -> dict[str, AbstractField[Any]]:
        """Return the fields available in the template model."""
        return {name: bt.field for name, bt in cls.__fields__.items()}

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
            if key in cls.__model_fields__:  # skipped, we have the sub attribute
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
            sub_model_cls = cls.__model_fields__[field_name].field.model
            sub_model = sub_model_cls.from_flat_dict(field_data, strictness_override)
            inst_kwargs[field_name] = sub_model

        return cls(**inst_kwargs)

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return the parsed object of this model from the given raw string."""
        r = re.match(cls.__regex__, raw)
        if not r:
            msg = f"Could not parse {raw!r} from {cls.__regex__!r}"
            raise ParseError(msg)

        # We assume that the regex already rejects invalid fields
        # We can avoid doing a pass of validation here to speed things up
        return cls.from_flat_dict(r.groupdict(), strictness_override=Strictness.NONE)

    def format(self) -> str:
        """Return the formatted string of this model."""
        return self.__chain__.format(self)
