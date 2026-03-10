"""
templex.model
~~~~~~~~~~~~~
Field descriptor, TemplateModelMeta, and TemplateModel base class.

Import order (no circular dependencies)
----------------------------------------
exceptions  ← no templex deps
config      ← no templex deps
core        ← no templex deps
tokens      ← core, exceptions
slot        ← core  (TemplateModel referenced only under TYPE_CHECKING)
template_parser ← core, exceptions, slot
model       ← all of the above  ✓
"""

from __future__ import annotations

from typing import Any

from templex.config import Delimiter
from templex.core import RegexBuilder, Templatable
from templex.exceptions import DefinitionError, ParseError
from templex.meta import TemplateModelMeta


class TemplateModel(metaclass=TemplateModelMeta):
    """Base class for all declarative template models.

    Subclass to declare a typed, bidirectional string template::

        class AssetResult(TemplateModel):
            type: str = Field(ASSET_TYPE)
            code: str = Field(ASSET_CODE)
            template = ASSET_TYPE >> "_" >> ASSET_CODE

    Parse::

        result = AssetResult.parse("chr_toto")
        result.type   # "chr"
        result.code   # "toto"

    Format::

        str(result)   # "chr_toto"
    """

    # Populated by metaclass
    __delimiter__ = Delimiter.CURLY
    __regex_builder__ = RegexBuilder()
    __templatables__: dict[str, Templatable]
    __template__: str

    def __init__(self, **kwargs: Any) -> None:
        for field_name, field in self._fields.items():
            value = kwargs.get(field_name, field.token.default)
            setattr(self, field_name, value)
        for slot_name in self._slots:
            value = kwargs.get(slot_name)
            setattr(self, slot_name, value)

    @classmethod
    def construct_regex(cls, builder: RegexBuilder) -> str:
        return cls.__chain__.to_regex(builder)

    def format(self) -> str:
        return self._chain.to_format(self.as_dict())

    def _slot_refs(self) -> list[Any]:
        return []

    # ── Parse ─────────────────────────────────────────────────────────────────

    @classmethod
    def parse(cls, string: str) -> TemplateModel:
        """Parse *string* and return a typed model instance.

        Raises :class:`~templex.exceptions.ParseError` on mismatch.
        """
        m = cls._regex.match(string)
        if not m:
            raise ParseError(
                f"{cls.__name__}: could not parse {string!r}\n"
                f"  expected pattern: {cls._regex.pattern}"
            )
        return cls._build_from_groups(m.groupdict(), string)

    @classmethod
    def _build_from_groups(cls, groups: dict[str, str], original: str) -> TemplateModel:
        kwargs: dict[str, Any] = {}

        for field_name, field in cls._fields.items():
            raw = groups.get(field_name)
            if raw is None:
                if field.token.default is not None:
                    kwargs[field_name] = field.token.default
                else:
                    raise ParseError(f"{cls.__name__}: no match for field {field_name!r}")
            else:
                kwargs[field_name] = field.token.parse(raw)

        for slot_name, slot in cls._slots.items():
            prefix = f"{slot_name}__"
            sub_groups = {
                key[len(prefix) :]: val
                for key, val in groups.items()
                if key.startswith(prefix) and val is not None
            }
            raw_slot = groups.get(slot_name)
            if not sub_groups and raw_slot is None:
                raise ParseError(f"{cls.__name__}: no match for slot {slot_name!r}")
            kwargs[slot_name] = slot.model._build_from_groups(sub_groups, original)

        return cls(**kwargs)

    # ── Format ────────────────────────────────────────────────────────────────

    def _to_values(self) -> dict[str, Any]:
        """Flatten self into the dict expected by :meth:`Chain.to_format`."""
        values: dict[str, Any] = {}
        for field_name in self._fields:
            values[field_name] = getattr(self, field_name)
        for slot_name in self._slots:
            values[slot_name] = getattr(self, slot_name)
        return values

    def __str__(self) -> str:
        return self._chain.to_format(self._to_values())

    def __repr__(self) -> str:
        field_parts = [f"{n}={getattr(self, n)!r}" for n in self._fields]
        slot_parts = [f"{n}={getattr(self, n)!r}" for n in self._slots]
        return f"{self.__class__.__name__}({', '.join(field_parts + slot_parts)})"

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        for attr_name in list(self._fields) + list(self._slots):
            if getattr(self, attr_name) != getattr(other, attr_name):
                return False
        return True

    def __hash__(self) -> int:
        return NotImplemented  # type: ignore[return-value]

    # ── Flatten ───────────────────────────────────────────────────────────────

    def flatten(self) -> dict[str, Any]:
        """Return a flat ``dict`` with ``__`` separator for nested slot fields."""
        result: dict[str, Any] = {}
        for field_name in self._fields:
            result[field_name] = getattr(self, field_name)
        for slot_name, slot in self._slots.items():
            sub = getattr(self, slot_name)
            if sub is not None:
                for sub_field in slot.model._fields:
                    result[f"{slot_name}__{sub_field}"] = getattr(sub, sub_field)
                for sub_slot_name in slot.model._slots:
                    if getattr(sub, sub_slot_name) is not None:
                        for k, v in sub.flatten().items():
                            key = f"{slot_name}__{k}"
                            if key not in result:
                                result[key] = v
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @classmethod
    def _get_field_token(cls, field_name: str) -> Token:
        if field_name not in cls._fields:
            raise DefinitionError(f"{cls.__name__} has no field {field_name!r}")
        return cls._fields[field_name].token
