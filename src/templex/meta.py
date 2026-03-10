from __future__ import annotations

from abc import ABCMeta
from typing import Any

from templex import Chain, DefinitionError, Delimiter
from templex.core import RegexBuilder
from templex.template_parser import parse_template
from templex.core import AbstractToken
from templex.core import BoundToken


class TemplateModelMeta(ABCMeta):
    """Validates and wires up a TemplateModel subclass at definition time.

    1. Injects ``name`` into all :class:`Field` and :class:`~templex.slot.Slot`
       descriptors.
    2. Normalises ``template`` (string or :class:`~templex.core.Chain`) and
       compiles a full regex.
    3. Validates that every Field/Slot appears in the chain (and vice-versa).
    4. Validates sub-field accesses (``slot.field``) against the sub-model.
    """

    __bound_tokens__: dict[str, BoundToken[Any]] = {}
    __template__: str
    __delimiter__: Delimiter
    __chain__: Chain
    __regex__: str

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> TemplateModelMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Skip the bare TemplateModel base itself
        if name == "TemplateModel":
            return cls

        # Create bounded token objects
        bound_tokens: dict[str, BoundToken[Any]] = {}

        for attr, value in namespace.items():
            if isinstance(value, AbstractToken):
                bound_tokens[attr] = BoundToken(attr, value)

        cls.__bound_tokens__ = bound_tokens

        # Validate template
        raw_template: Any = namespace.get("__template__")
        if raw_template is None:
            raise DefinitionError(f"{name}: must define a '__template__'")

        # Go through all bases to get the delimiter
        delimiter = namespace.get("__delimiter__")
        if delimiter is None:
            for base in bases:
                delimiter = base.__dict__.get("__delimiter__")
                if delimiter:
                    break

        if not isinstance(delimiter, Delimiter):
            raise DefinitionError(
                f"{name}: __delimiter__ must be a Delimiter instance, "
                f"got {type(delimiter).__name__!r}"
            )

        chain: Chain = parse_template(cls)
        cls.__chain__ = chain

        # Go through all bases to get the regex builder
        regex_builder = namespace.get("__regex_builder__")
        if regex_builder is None:
            for base in bases:
                regex_builder = base.__dict__.get("__regex_builder__")
                if regex_builder:
                    break

        if not isinstance(regex_builder, RegexBuilder):
            raise DefinitionError(
                f"{name}: __regex_builder__ must be a RegexBuilder instance, got {type(regex_builder).__name__!r}"
            )
        cls.__regex__ = cls.__chain__.to_regex(regex_builder)

        # # ── 3. Validate slot references ───────────────────────────────────────
        # slot_refs: list[SlotRef] = chain._slot_refs()
        # referenced_slots: set[str] = set()
        # for ref in slot_refs:
        #     slot_name = ref.slot.name
        #     if not slot_name:
        #         raise DefinitionError(
        #             f"{name}: a Slot used in 'template' has no name — "
        #             "make sure it is assigned as a class attribute"
        #         )
        #     if slot_name not in slots:
        #         raise DefinitionError(
        #             f"{name}: slot {slot_name!r} used in template "
        #             "but not declared as a class attribute"
        #         )
        #     referenced_slots.add(slot_name)
        #     if isinstance(ref, BoundField):
        #         sub_model = ref.slot.model
        #         if ref.field_name not in sub_model._fields:  # type: ignore[attr-defined]
        #             raise DefinitionError(
        #                 f"{name}: slot {slot_name!r} references field "
        #                 f"{ref.field_name!r} which does not exist on "
        #                 f"{sub_model.__name__}"
        #             )
        #
        # for slot_name in slots:
        #     if slot_name not in referenced_slots:
        #         raise DefinitionError(
        #             f"{name}: slot {slot_name!r} is declared but never used in 'template'"
        #         )
        #
        # # ── 4. Compile regex ──────────────────────────────────────────────────
        # cls._regex = re.compile("^" + chain.to_regex(seen=set()) + "$")  # type: ignore[attr-defined]

        return cls
