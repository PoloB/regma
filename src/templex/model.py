"""Template model implementation."""

from __future__ import annotations

import collections
import contextlib
import re
import typing
from typing import Any
from typing import ClassVar
from typing import Self
from typing import TypeVar

from typing_extensions import dataclass_transform

from templex.core import AbstractField
from templex.core import BoundField
from templex.core import Chain
from templex.core import Delimiter
from templex.core import FieldReference
from templex.core import FormatableNode
from templex.core import Separator
from templex.engine import AbstractRegexEngine
from templex.engine import BuiltinRegexEngine
from templex.error import DefinitionError
from templex.error import ParseError
from templex.field import ModelField
from templex.field import choice
from templex.field import custom_field
from templex.field import integer
from templex.field import string


def _parse_template(template_model: TemplateModelMeta) -> Chain:
    """Convert a template string into a :class:`~templex.core.Chain`."""
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


def _validate_bound_field_names(model_cls: TemplateModelMeta) -> None:
    """Validate all fields have a valid name."""
    for attr in (*model_cls.__model_fields__, *model_cls.__fields__):
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


def _validate_field_references(model_cls: TemplateModelMeta) -> None:
    """Validate the model has all its fields in __template__."""
    # Template shall contain all the element required to build its model references

    def _check_has_all_elements(
        model_cls_: TemplateModelMeta, references: set[str], parent_bound: str
    ) -> None:
        # Check leaf fields are used in the template
        missing_fields = set(model_cls_.__fields__).difference(references)
        if missing_fields:
            # Rebuild the full missing field
            missing_full_fields = sorted(
                f"{parent_bound}.{missing_field}" for missing_field in missing_fields
            )
            msg = (
                f"All fields of {parent_bound!r} are not used in "
                f"{model_cls.__name__} template (missing {missing_full_fields})"
            )
            raise DefinitionError(msg)

        for bound_name, model_field in model_cls_.__model_fields__.items():
            # Get all the references starting with the bound name
            model_refs = {r for r in references if r.startswith(bound_name)}
            if bound_name in model_refs:
                # There is a complete reference, this is ok
                continue

            sub_references = {r.split(".", maxsplit=1)[1] for r in model_refs}
            # Check recursively
            _check_has_all_elements(
                model_field.field.model,
                sub_references,
                f"{parent_bound}.{bound_name}" if parent_bound else bound_name,
            )

    ref_fields = {
        node.attribute_name
        for node in model_cls.__chain__.nodes
        if isinstance(node, FieldReference)
    }

    _check_has_all_elements(model_cls, ref_fields, "")


T_model = TypeVar("T_model", bound="TemplateModel")


class TemplateModelMeta(type):
    """Validates and wires up a TemplateModel subclass at definition time.

    1. Injects ``name`` into all :class:`Field` and :class:`~templex.slot.Slot`
       descriptors.
    2. Normalizes ``template`` (string or :class:`~templex.core.Chain`) and
       compiles a full regex.
    3. Validates that every Field/Slot appears in the chain (and vice versa).
    4. Validates sub-field accesses (``slot.field``) against the sub-model.
    """

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
        bound_fields: dict[str, BoundField[Any]] = {}
        model_fields: dict[str, BoundField[ModelField[TemplateModel]]] = {}

        # First evaluate the model field references by checking annotations
        for attr, hint in typing.get_type_hints(cls).items():
            if not isinstance(hint, type) or not issubclass(hint, TemplateModel):
                continue

            model_field = ModelField(hint)
            setattr(cls, attr, model_field)
            model_fields[attr] = BoundField(attr, model_field)

        # Check for other fields
        for attr, value in namespace.items():
            if not isinstance(value, AbstractField) or attr in model_fields:
                continue

            # Separate value fields from model fields
            bound_fields[attr] = BoundField(attr, value)

        cls.__fields__ = bound_fields
        cls.__model_fields__ = model_fields
        _validate_bound_field_names(cls)

        # Validate template
        raw_template: Any = namespace.get("__template__")
        if raw_template is None:
            msg = f"{name}: must define a '__template__'"
            raise DefinitionError(msg)

        contents = [namespace, *[b.__dict__ for b in bases]]
        # Go through all bases to get the delimiter
        delimiters = (c.get("__delimiter__") for c in contents)
        delimiter = next(d for d in delimiters if d is not None)

        if not isinstance(delimiter, Delimiter):
            msg = (
                f"{name}: __delimiter__ must be a {Delimiter.__name__} instance, "
                f"got {type(delimiter).__name__!r}"
            )
            raise DefinitionError(msg)

        chain: Chain = _parse_template(cls)
        cls.__chain__ = chain
        _validate_field_references(cls)

        # Go through all bases to get the regex engine
        regex_engines = (c.get("__regex_engine__") for c in contents)
        regex_engine_cls = next(d for d in regex_engines if d is not None)

        if not isinstance(regex_engine_cls, type) or not issubclass(
            regex_engine_cls, AbstractRegexEngine
        ):
            msg = (
                f"{name}: __regex_engine__ must be of type "
                f"{AbstractRegexEngine.__name__}, "
                f"got {type(regex_engine_cls).__name__!r}"
            )
            raise DefinitionError(msg)

        cls.__regex__ = cls.__chain__.to_regex(regex_engine_cls())

        return cls


@dataclass_transform(field_specifiers=(string, integer, choice, custom_field))
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
        for field_name in self.__fields__:
            if getattr(self, field_name) != getattr(other, field_name):
                return False

        for field_name in self.__model_fields__:
            if getattr(self, field_name) != getattr(other, field_name):
                return False

        return True

    def __hash__(self) -> int:
        """Return hash of model."""
        return hash(
            (
                type(self),
                *(getattr(self, attr) for attr in self.__fields__),
                *(getattr(self, attr) for attr in self.__model_fields__),
            )
        )

    def __str__(self) -> str:
        """Return formatted representation of model."""
        return self.format()

    @classmethod
    def fields(cls) -> dict[str, AbstractField[Any]]:
        """Return the fields available in the template model."""
        return {name: bt.field for name, bt in cls.__fields__.items()} | {
            name: bt.field for name, bt in cls.__model_fields__.items()
        }

    @classmethod
    def from_flat_dict(cls, data: dict[str, Any]) -> Self:
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
                    inst_kwargs[attr] = cls.__fields__[attr].field.extract_value(value)
            else:
                data_by_model_field[attr][field_split[1]] = value

        for field_name, field_data in data_by_model_field.items():
            sub_model_cls = cls.__model_fields__[field_name].field.model
            sub_model = sub_model_cls.from_flat_dict(field_data)
            inst_kwargs[field_name] = sub_model

        return cls(**inst_kwargs)

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return the parsed object of this model from the given raw string."""
        r = re.match(cls.__regex__, raw)
        if not r:
            msg = f"Could not parse {raw!r} from {cls.__regex__!r}"
            raise ParseError(msg)
        return cls.from_flat_dict(r.groupdict())

    def format(self) -> str:
        """Return the formatted string of this model."""
        return self.__chain__.format(self)
