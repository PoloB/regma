"""Template definition defined for models."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar

from typing_extensions import override

from regma import ParseError
from regma.core import AbstractField
from regma.core import BoundField
from regma.core import Chain
from regma.core import ChainTokenNode
from regma.core import Delimiter
from regma.core import Reference
from regma.core import Strictness
from regma.error import DefinitionError

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

    ref_fields = {
        field_sep.reference.name for field_sep in template.chain.iter_field_seps()
    }

    _check_has_all_elements(template.model, ref_fields, "")


def _get_reference(
    tokens: dict[str, ChainTokenNode | type[Model]], token_name: str
) -> Reference:
    """Return the field reference of the given token name."""
    # Find the targeted field
    attributes = token_name.split(".")
    if not attributes:
        message = f"Invalid token {token_name!r}"
        raise DefinitionError(message)

    reference: ChainTokenNode | type[Model] | None = tokens[attributes[0]]
    lookup_obj: Any = reference
    attribute_full_name = ""

    for attr in attributes[1:]:
        if not attr:
            msg = f"Invalid token {token_name!r}"
            raise DefinitionError(msg)

        if isinstance(lookup_obj, Template):
            reference = None  # Invalidate the bound template found earlier

        attribute_full_name += attr

        try:
            lookup_obj = getattr(lookup_obj, attr)
        except AttributeError as e:
            msg = f"could not find attribute {attr!r} in {lookup_obj}"
            raise DefinitionError(msg) from e

        if isinstance(lookup_obj, ChainTokenNode):
            reference = lookup_obj
            continue

        attribute_full_name += "."

    if not isinstance(reference, ChainTokenNode):
        msg = f"Invalid token {token_name}"
        raise DefinitionError(msg)

    return Reference(token_name, reference)


def create_chain(pattern: str, tokens: dict[str, ChainTokenNode | type[Model]]) -> Chain:
    """Convert a template string into a chain."""
    token_re = Delimiter.CURLY.token_re()
    chain = Chain.empty()
    cursor = 0

    for m in token_re.finditer(pattern):
        start, end = m.span()
        attr_name: str = m.group(1)
        chain.append_separator(pattern[cursor:start])

        reference = _get_reference(tokens, attr_name)
        chain.append_reference(reference)
        cursor = end

    chain.append_separator(pattern[cursor:])
    return chain


class Template(ChainTokenNode):
    """A template that can only be used for formatting."""

    def __init__(
        self, pattern: str, **kwargs: ChainTokenNode | AbstractField[Any] | type[Model]
    ) -> None:
        """Initialize the template."""
        all_kwargs: dict[str, ChainTokenNode | type[Model]] = {}
        for name, field in kwargs.items():
            if isinstance(field, AbstractField):
                all_kwargs[name] = BoundField(name, field)
            else:
                all_kwargs[name] = field
        self._pattern = pattern
        self._tokens = all_kwargs
        self._chain = create_chain(pattern, self._tokens)

    @property
    def pattern(self) -> str:
        """Return the pattern string of this template."""
        return self._pattern

    @property
    def chain(self) -> Chain:
        """Return the chain associated to this template."""
        return self._chain

    @override
    def to_regex(self) -> str:
        return self._chain.to_regex()

    @override
    def format(self, model: T_mod) -> str:
        return self._chain.format(model)

    @override
    def get_content_chain(self) -> Chain:
        return self._chain


class BoundTemplate(ChainTokenNode):
    """A template that can only be used for formatting."""

    def __init__(self, name: str, template: ModelTemplate[Model]) -> None:
        """Initialize the bound template."""
        self._name = name
        self._chain = template.chain.using(name)

    @override
    def get_content_chain(self) -> Chain:
        return self._chain

    @override
    def format(self, model: Model) -> str:
        return self._chain.format(model)

    @override
    def to_regex(self) -> str:
        return self._chain.to_regex()


class ModelTemplate(Template, Generic[T_mod]):
    """Definition of a template for a model."""

    def __init__(
        self, model_cls: type[T_mod], pattern: str, **kwargs: ChainTokenNode
    ) -> None:
        """Initialize the template with pattern and delimiter."""
        all_kwargs: dict[str, ChainTokenNode | type[Model]] = model_cls.__fields__.copy()
        all_kwargs.update(kwargs)
        super().__init__(pattern, **all_kwargs)
        self._model = model_cls

    def using(self, name: str) -> BoundTemplate:
        """Provide a new template through the given model instance."""
        return BoundTemplate(name, self)

    def parse(self, string: str) -> T_mod:
        """Parse the given string through the template and return the model object."""
        regex = self._chain.to_regex()
        r = re.match(regex, string)
        if not r:
            msg = f"Could not parse {string!r} from {regex!r}"
            raise ParseError(msg)

        # We assume that the regex already rejects invalid fields
        # We can avoid doing a pass of validation here to speed things up
        return self._model.from_flat_dict(
            r.groupdict(), strictness_override=Strictness.NONE
        )
