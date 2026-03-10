"""
templex.slot
~~~~~~~~~~~~
Slot, BoundSlot, BoundField.

Scoping strategy:
- BoundSlot wraps the sub-model inner regex in a named group (?P<slot_name>...)
  All inner capture groups are prefixed: type → asset_source__type
- BoundField emits a standalone (?P<slot__field>...) for partial embeds
- The parent ``seen`` set is threaded through ALL nodes so that if
  asset_source__type is emitted by BoundField first, then BoundSlot's inner
  regex emits (?P=asset_source__type) as a backreference — enforcing consistency
  at the regex engine level with zero post-parse checks needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from templex.core import Chain, Templatable, Separator

if TYPE_CHECKING:
    from templex.model import TemplateModel


_SLOT_OWN_ATTRS: frozenset[str] = frozenset({"model", "name"})


class SlotRef(Templatable):
    """Base for BoundSlot and BoundField — both reference a Slot."""

    @property
    def slot(self) -> Slot:
        raise NotImplementedError

    def _slot_refs(self) -> list[SlotRef]:
        return [self]


def _build_scoped_regex(chain: Chain, slot_name: str, seen: set[str]) -> str:
    """
    Walk the sub-model chain and emit each node's regex with scoped group
    names (slot__field), threading the parent seen set so duplicates across
    partial embeds and full embeds become backreferences.
    """
    parts: list[str] = []
    for node in chain._nodes:
        if isinstance(node, Separator):
            parts.append(node.to_regex())
        elif isinstance(node, SlotRef):
            parts.append(node.to_regex(seen=seen))
        else:
            token_name: str | None = getattr(node, "name", None)
            if token_name is None:
                parts.append(node.to_regex(seen=seen))
                continue
            scoped = f"{slot_name}__{token_name}"
            raw_pattern: str | None = getattr(node, "_pattern", None)
            pat: str = raw_pattern if raw_pattern is not None else node._default_pattern()  # type: ignore[attr-defined]
            if scoped in seen:
                parts.append(f"(?P={scoped})")
            else:
                seen.add(scoped)
                parts.append(f"(?P<{scoped}>{pat})")
    return "".join(parts)


class BoundSlot(SlotRef):
    """
    Full-pattern embed of a Slot.
    First use → ``(?P<slot_name>scoped_inner)``
    Reuse     → ``(?P=slot_name)``
    """

    def __init__(self, slot: Slot) -> None:
        self._slot = slot

    @property
    def slot(self) -> Slot:
        return self._slot

    def to_regex(self, seen: set[str] | None = None) -> str:
        if seen is None:
            seen = set()
        name = self._slot.name
        if name in seen:
            return f"(?P={name})"
        seen.add(name)
        inner = _build_scoped_regex(self._slot.model._chain, name, seen)
        return f"(?P<{name}>{inner})"

    def to_format(self, values: dict[str, Any]) -> str:
        instance = values.get(self._slot.name)
        if instance is None:
            raise ValueError(f"No value for slot {self._slot.name!r}")
        return str(instance)

    def __repr__(self) -> str:
        return f"BoundSlot({self._slot.name!r})"


class BoundField(SlotRef):
    """
    Partial embed: one field of a Slot's TemplateModel.

    Capture name: ``slot__field``
    First use → ``(?P<slot__field>pattern)``
    Reuse     → ``(?P=slot__field)``
    """

    def __init__(self, slot: Slot, field_name: str) -> None:
        self._slot = slot
        self.field_name = field_name

    @property
    def slot(self) -> Slot:
        return self._slot

    def to_regex(self, seen: set[str] | None = None) -> str:
        if seen is None:
            seen = set()
        capture_name = f"{self._slot.name}__{self.field_name}"
        if capture_name in seen:
            return f"(?P={capture_name})"
        seen.add(capture_name)
        field_token = self._slot.model._get_field_token(self.field_name)
        pat = field_token._pattern or field_token._default_pattern()
        return f"(?P<{capture_name}>{pat})"

    def to_format(self, values: dict[str, Any]) -> str:
        instance = values.get(self._slot.name)
        if instance is None:
            raise ValueError(f"No value for slot {self._slot.name!r}")
        field_value = getattr(instance, self.field_name)
        field_token = self._slot.model._get_field_token(self.field_name)
        return field_token.format(field_value)

    def __repr__(self) -> str:
        return f"BoundField({self._slot.name!r}, {self.field_name!r})"


class Slot:
    """
    Declaration-time placeholder for a nested TemplateModel.

        asset_source = Slot(AssetResult)
        asset_target = Slot(AssetResult)

        template = asset_source.type >> "/" >> asset_source >> "/modeling/" >> asset_source
    """

    def __init__(self, model: type[TemplateModel]) -> None:
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "name", "")

    def __rshift__(self, other: Any) -> Chain:
        return BoundSlot(self).__rshift__(other)

    def __rrshift__(self, other: Any) -> Chain:
        return BoundSlot(self).__rrshift__(other)

    def __getattr__(self, field_name: str) -> BoundField:
        if field_name.startswith("_") or field_name in _SLOT_OWN_ATTRS:
            raise AttributeError(field_name)
        return BoundField(self, field_name)

    def __repr__(self) -> str:
        model_name: str = object.__getattribute__(self, "model").__name__
        name: str = object.__getattribute__(self, "name")
        return f"Slot({model_name!r}, name={name!r})"
