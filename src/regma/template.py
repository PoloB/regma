"""Template definition defined for models."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar
from typing import overload

from regma.core import AbstractField
from regma.core import Chain
from regma.core import Delimiter
from regma.core import FieldReference
from regma.core import FieldSep
from regma.core import Separator
from regma.core import Strictness
from regma.error import DefinitionError
from regma.error import ParseError
from regma.fsm import FsmBuilder
from regma.fsm import FsmRegexCache
from regma.fsm import FsmValidationFlag
from regma.fsm import validate

if TYPE_CHECKING:
    from regma.model import Model

T_mod = TypeVar("T_mod", bound="Model")


VALIDATE_FSM = True


def _validate_field_references(template: BoundTemplate[T_mod]) -> None:
    # Template shall contain all the element required to build its model references

    def _check_has_all_elements(
        model_cls_: type[Model], references: set[str], parent_bound: str
    ) -> None:
        # Check leaf fields are used in the template
        missing_fields = set(model_cls_.__typed_fields__).difference(references)
        if missing_fields:
            # Rebuild the full missing field
            missing_full_fields = sorted(
                f"{parent_bound}.{missing_field}" for missing_field in missing_fields
            )
            msg = (
                f"All fields of {parent_bound!r} are not used in "
                f"{template.model.__name__} template (missing {missing_full_fields})"
            )
            raise DefinitionError(msg)

        for bound_name, model_ref_cls in model_cls_.__model_refs__.items():
            # Get all the references starting with the bound name
            model_refs = {r for r in references if r.startswith(bound_name)}
            sub_references = {r.split(".", maxsplit=1)[1] for r in model_refs}
            # Check recursively
            _check_has_all_elements(
                model_ref_cls,
                sub_references,
                f"{parent_bound}.{bound_name}" if parent_bound else bound_name,
            )

    ref_fields = {field_sep.field.name for field_sep in template.chain.iter_field_seps()}

    _check_has_all_elements(template.model, ref_fields, "")


def _get_reference(
    model_cls: type[Model], attribute_name: str
) -> FieldReference | BoundTemplate[Model]:
    """Return the field reference of the given attribute."""
    # Find the targeted field
    attributes = attribute_name.split(".")
    reference: FieldReference | BoundTemplate[Model] | None = None
    lookup_obj = model_cls
    attribute_full_name = ""
    for attr in attributes:
        if not attr:
            continue

        if isinstance(lookup_obj, BoundTemplate):
            reference = None  # Invalidate the bound template found earlier

        attribute_full_name += attr

        try:
            lookup_obj = getattr(lookup_obj, attr)
        except AttributeError as e:
            msg = (
                f"{model_cls.__name__}: "
                f"could not find attribute {attr!r} in {lookup_obj}"
            )
            raise DefinitionError(msg) from e

        if isinstance(lookup_obj, BoundTemplate):
            reference = lookup_obj
            continue

        if isinstance(lookup_obj, AbstractField):
            reference = FieldReference(attribute_full_name, lookup_obj)

        attribute_full_name += "."

    if reference is None:
        msg = f"Invalid attribute {attribute_name}"
        raise DefinitionError(msg)

    return reference


def create_bound_template(
    template: Template[T_mod], model_cls: type[T_mod]
) -> BoundTemplate[T_mod]:
    """Convert a template string into a chain."""
    pattern = template.pattern
    delimiter = template.delimiter
    token_re = delimiter.token_re()
    pending_separator = ""
    separators = []
    fields: list[FieldReference] = []
    cursor = 0

    for m in token_re.finditer(pattern):
        start, end = m.span()
        attr_name: str = m.group(1)

        separators.append(Separator(pending_separator + pattern[cursor:start]))
        pending_separator = ""
        reference = _get_reference(model_cls, attr_name)
        # If we are referencing a model template, we can reconstruct nodes from its chain
        # This is to flatten the chain to atomic elements.
        if isinstance(reference, BoundTemplate):
            attr_name = ".".join(attr_name.split(".")[:-1])
            chain = reference.chain
            separators[-1] = Separator(
                separators[-1].value + chain.start_separator.value
            )
            for field_sep in chain.iter_field_seps():
                field = field_sep.field
                new_field = FieldReference(f"{attr_name}.{field.name}", field.target)
                fields.append(new_field)
                new_sep = Separator(field_sep.separator.value)
                separators.append(new_sep)
            pending_separator = separators.pop(-1).value
        else:
            fields.append(reference)

        cursor = end

    separators.append(Separator(pattern[cursor:]))

    start_sep = separators.pop(0)
    field_seps = [FieldSep(field, sep) for field, sep in zip(fields, separators)]  # noqa: B905
    chain = Chain(start_sep, field_seps)

    __fsm_builder = FsmBuilder(FsmRegexCache())

    bound_template = BoundTemplate(model_cls, chain)
    _validate_field_references(bound_template)
    validate(__fsm_builder, bound_template, template.fsm_validation_flags)
    return bound_template


class BoundTemplate(Generic[T_mod]):
    """A template bounded to a model class."""

    def __init__(self, model_cls: type[T_mod], chain: Chain) -> None:
        """Initialize the bound template."""
        self._model_cls = model_cls
        self._chain = chain
        self._regex = self._chain.to_regex()

    @property
    def model(self) -> type[T_mod]:
        """Return the model class bounded by this template."""
        return self._model_cls

    @property
    def chain(self) -> Chain:
        """Return the chain associated to this template."""
        return self._chain

    @property
    def regex(self) -> str:
        """Return the regex for this template."""
        return self._regex

    def parse(self, string: str) -> T_mod:
        """Parse the given string and return an instance of the bounded model."""
        regex = self._chain.to_regex()
        r = re.match(regex, string)
        if not r:
            msg = f"Could not parse {string!r} from {regex!r}"
            raise ParseError(msg)

        # We assume that the regex already rejects invalid fields
        # We can avoid doing a pass of validation here to speed things up
        return self._model_cls.from_flat_dict(
            r.groupdict(), strictness_override=Strictness.NONE
        )


class FormatTemplate(Generic[T_mod]):
    """A template that can only be used for formatting."""

    def __init__(self, bound_template: BoundTemplate[T_mod]) -> None:
        """Initialize the format template."""
        self._bound_template = bound_template

    def format(self, model: Model) -> str:
        """Return the formatted string of this model."""
        return self._bound_template.chain.format(model)


class Template(Generic[T_mod]):
    """Definition of a template for a model."""

    def __init__(
        self,
        pattern: str,
        delimiter: Delimiter = Delimiter.CURLY,
        fsm_validation_flags: FsmValidationFlag | None = None,
    ) -> None:
        """Initialize the template with pattern and delimiter."""
        if fsm_validation_flags is None:
            fsm_validation_flags = FsmValidationFlag.all()
        self._pattern = pattern
        self._delimiter = delimiter
        self._fsm_validation = fsm_validation_flags

    @property
    def pattern(self) -> str:
        """Return the pattern string of this template."""
        return self._pattern

    @property
    def delimiter(self) -> Delimiter:
        """Return the delimiter string of this template."""
        return self._delimiter

    @property
    def fsm_validation_flags(self) -> FsmValidationFlag:
        """Return the validation flags to execute for this template."""
        return self._fsm_validation

    @overload
    def __get__(self, instance: None, obj_type: type[T_mod]) -> BoundTemplate[T_mod]: ...

    @overload
    def __get__(self, instance: T_mod, obj_type: type[T_mod]) -> str: ...

    def __get__(
        self, instance: T_mod | None, obj_type: type[T_mod]
    ) -> BoundTemplate[T_mod] | str:
        """Return the bound template for this instance."""
        if instance:
            return FormatTemplate(obj_type.__templates__[self]).format(instance)

        return obj_type.__templates__[self]


def model_template(
    pattern: str,
    delimiter: Delimiter = Delimiter.CURLY,
    fsm_validation_flags: FsmValidationFlag | None = None,
) -> Template[Model]:
    """Creates a template for the given pattern."""
    return Template(pattern, delimiter, fsm_validation_flags)
