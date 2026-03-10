"""tests/test_slot.py — Slot, BoundSlot, BoundField."""

import pytest

from templex import Slot, TemplateModel
from templex.core import Chain
from templex.slot import BoundField, BoundSlot

from .conftest import AssetResult

# ── Slot ──────────────────────────────────────────────────────────────────────


class TestSlot:
    def _named_slot(self, name="asset"):
        s = Slot(AssetResult)
        s.name = name
        return s

    def test_slot_name_set(self):
        s = self._named_slot("asset_source")
        assert s.name == "asset_source"

    def test_slot_model_stored(self):
        s = self._named_slot()
        assert s.model is AssetResult

    def test_getattr_returns_bound_field(self):
        s = self._named_slot()
        bf = s.type
        assert isinstance(bf, BoundField)
        assert bf.field_name == "type"

    def test_getattr_nonexistent_still_returns_bound_field(self):
        # BoundField is lazy — validation happens in metaclass, not here
        s = self._named_slot()
        bf = s.anything
        assert isinstance(bf, BoundField)
        assert bf.field_name == "anything"

    def test_rshift_produces_chain(self):
        s = self._named_slot()
        result = s >> "_"
        assert isinstance(result, Chain)

    def test_rrshift_produces_chain(self):
        s = self._named_slot()
        result = "/prefix/" >> s
        assert isinstance(result, Chain)

    def test_repr_contains_model_and_name(self):
        s = self._named_slot("asset_source")
        rep = repr(s)
        assert "AssetResult" in rep
        assert "asset_source" in rep

    def test_private_attrs_not_intercepted(self):
        s = self._named_slot()
        with pytest.raises(AttributeError):
            _ = s._private


# ── BoundSlot ─────────────────────────────────────────────────────────────────


class TestBoundSlot:
    def _slot(self, name="asset"):
        s = Slot(AssetResult)
        s.name = name
        return s

    def test_to_regex_named_group(self):
        bs = BoundSlot(self._slot("asset"))
        r = bs.to_regex(seen=set())
        assert r.startswith("(?P<asset>")

    def test_to_regex_reuse_is_backref(self):
        bs = BoundSlot(self._slot("asset"))
        seen = {"asset"}
        r = bs.to_regex(seen=seen)
        assert r == "(?P=asset)"

    def test_to_regex_scopes_inner_groups(self):
        bs = BoundSlot(self._slot("asset"))
        r = bs.to_regex(seen=set())
        # Inner field groups should be scoped as asset__type, asset__code
        assert "asset__type" in r
        assert "asset__code" in r
        # Raw 'type' and 'code' should NOT appear as unscoped group names
        assert "(?P<type>" not in r
        assert "(?P<code>" not in r

    def test_to_format_delegates_to_str(self):
        bs = BoundSlot(self._slot("asset"))
        instance = AssetResult(type="chr", code="toto")
        result = bs.to_format({"asset": instance})
        assert result == "chr_toto"

    def test_to_format_missing_slot_raises(self):
        bs = BoundSlot(self._slot("asset"))
        with pytest.raises(ValueError, match="No value for slot"):
            bs.to_format({})

    def test_slot_refs_returns_self(self):
        bs = BoundSlot(self._slot("asset"))
        assert bs._slot_refs() == [bs]

    def test_repr(self):
        bs = BoundSlot(self._slot("asset"))
        assert "BoundSlot" in repr(bs)
        assert "asset" in repr(bs)


# ── BoundField ────────────────────────────────────────────────────────────────


class TestBoundField:
    def _slot(self, name="asset"):
        s = Slot(AssetResult)
        s.name = name
        return s

    def test_to_regex_scoped_name(self):
        bf = BoundField(self._slot("asset_source"), "type")
        r = bf.to_regex(seen=set())
        assert r.startswith("(?P<asset_source__type>")

    def test_to_regex_reuse_is_backref(self):
        bf = BoundField(self._slot("asset_source"), "type")
        seen = {"asset_source__type"}
        r = bf.to_regex(seen=seen)
        assert r == "(?P=asset_source__type)"

    def test_to_regex_uses_token_pattern(self):
        bf = BoundField(self._slot("asset"), "type")
        r = bf.to_regex(seen=set())
        # Should include the ChoiceToken pattern for ASSET_TYPE
        for choice in ["chr", "prp", "env", "veh"]:
            assert choice in r

    def test_to_format(self):
        bf = BoundField(self._slot("asset"), "type")
        instance = AssetResult(type="chr", code="toto")
        assert bf.to_format({"asset": instance}) == "chr"

    def test_to_format_missing_slot_raises(self):
        bf = BoundField(self._slot("asset"), "type")
        with pytest.raises(ValueError, match="No value for slot"):
            bf.to_format({})

    def test_slot_refs_returns_self(self):
        bf = BoundField(self._slot("asset"), "type")
        assert bf._slot_refs() == [bf]

    def test_repr(self):
        bf = BoundField(self._slot("asset"), "type")
        assert "BoundField" in repr(bf)
        assert "asset" in repr(bf)
        assert "type" in repr(bf)


# ── Scoping prevents cross-slot group name conflicts ──────────────────────────


class TestSlotScoping:
    def test_two_slots_same_model_no_regex_conflict(self):
        """
        Two slots backed by the same AssetResult must produce non-conflicting
        capture group names in the parent regex.
        """

        class TwoAssets(TemplateModel):
            src = Slot(AssetResult)
            dst = Slot(AssetResult)
            template = src >> "_to_" >> dst

        pattern = TwoAssets._regex.pattern
        # Both sets of scoped groups should exist
        assert "src__type" in pattern
        assert "src__code" in pattern
        assert "dst__type" in pattern
        assert "dst__code" in pattern
        # Unscoped names must not exist as capture groups
        assert "(?P<type>" not in pattern
        assert "(?P<code>" not in pattern

    def test_parse_distinguishes_two_slots(self):
        class TwoAssets(TemplateModel):
            src = Slot(AssetResult)
            dst = Slot(AssetResult)
            template = src >> "_to_" >> dst

        r = TwoAssets.parse("chr_toto_to_prp_sword")
        assert r.src == AssetResult(type="chr", code="toto")
        assert r.dst == AssetResult(type="prp", code="sword")

    def test_backreference_enforces_reuse(self):
        """
        The same slot used twice must match the identical string.
        The regex engine enforces this via (?P=name) backreference.
        """

        class Reused(TemplateModel):
            asset = Slot(AssetResult)
            template = asset >> "_" >> asset

        # Same value twice — should parse
        r = Reused.parse("chr_toto_chr_toto")
        assert r.asset == AssetResult(type="chr", code="toto")

        # Different values — must fail at regex level
        with pytest.raises(Exception):
            Reused.parse("chr_toto_prp_sword")

    def test_partial_and_full_consistency(self):
        """
        BoundField (partial embed) and BoundSlot (full embed) of the same slot
        must agree: the partial field is a backreference to the full slot's
        inner scoped group.
        """

        class PartialAndFull(TemplateModel):
            asset = Slot(AssetResult)
            template = asset.type >> "/" >> asset

        # Consistent: "chr" matches the type field of "chr_toto"
        r = PartialAndFull.parse("chr/chr_toto")
        assert r.asset == AssetResult(type="chr", code="toto")

        # Inconsistent: "prp" doesn't match the type of "chr_toto"
        with pytest.raises(Exception):
            PartialAndFull.parse("prp/chr_toto")
