"""tests/test_model.py — TemplateModel, Field, parse/format/flatten."""

import pytest

from templex import (
    Field,
    Slot,
    TemplateModel,
)
from templex.exceptions import DefinitionError, ParseError

from .conftest import (
    ASSET_CODE,
    SHOT,
    VALID_PATH,
    VERSION,
    AssetResult,
    GroomPathResult,
    ShotResult,
)

# ── AssetResult — simple two-field model ──────────────────────────────────────


class TestAssetResult:
    def test_parse_chr_toto(self):
        r = AssetResult.parse("chr_toto")
        assert r.type == "chr"
        assert r.code == "toto"

    def test_parse_all_choice_types(self):
        for t in ["chr", "prp", "env", "veh"]:
            r = AssetResult.parse(f"{t}_myasset")
            assert r.type == t

    def test_parse_invalid_type_raises(self):
        with pytest.raises(ParseError):
            AssetResult.parse("fx_toto")

    def test_parse_invalid_code_raises(self):
        with pytest.raises(ParseError):
            AssetResult.parse("chr_")  # empty code

    def test_format(self):
        r = AssetResult(type="chr", code="toto")
        assert str(r) == "chr_toto"

    def test_round_trip(self):
        original = "prp_sword"
        assert str(AssetResult.parse(original)) == original

    def test_equality_same(self):
        assert AssetResult(type="chr", code="toto") == AssetResult(type="chr", code="toto")

    def test_equality_different_code(self):
        assert AssetResult(type="chr", code="toto") != AssetResult(type="chr", code="tata")

    def test_equality_different_type(self):
        assert AssetResult(type="chr", code="x") != AssetResult(type="prp", code="x")

    def test_equality_different_class(self):
        r = AssetResult(type="chr", code="toto")
        assert r != "chr_toto"

    def test_repr_contains_fields(self):
        r = AssetResult(type="chr", code="toto")
        rep = repr(r)
        assert "chr" in rep
        assert "toto" in rep

    def test_class_has_fields_dict(self):
        assert "type" in AssetResult._fields
        assert "code" in AssetResult._fields

    def test_class_has_compiled_regex(self):
        import re

        assert isinstance(AssetResult._regex, re.Pattern)

    def test_field_descriptor_returns_field_on_class(self):
        assert isinstance(AssetResult._fields["type"], Field)


# ── ShotResult — IntToken with formatting ────────────────────────────────────


class TestShotResult:
    def test_parse_returns_int_version(self):
        r = ShotResult.parse("0030_v002")
        assert r.version == 2
        assert isinstance(r.version, int)

    def test_parse_returns_str_shot(self):
        r = ShotResult.parse("0030_v002")
        assert r.shot == "0030"
        assert isinstance(r.shot, str)

    def test_format_pads_version(self):
        r = ShotResult(shot="0030", version=2)
        assert str(r) == "0030_v002"

    def test_format_version_single_digit(self):
        r = ShotResult(shot="0010", version=7)
        assert str(r) == "0010_v007"

    def test_round_trip(self):
        r = ShotResult.parse("0050_v012")
        assert ShotResult.parse(str(r)) == r


# ── GroomPathResult — full nested model ───────────────────────────────────────


class TestGroomPathResult:
    def test_parse_full_path(self):
        r = GroomPathResult.parse(VALID_PATH)
        assert r.asset_source == AssetResult(type="chr", code="toto")
        assert r.asset_target == AssetResult(type="chr", code="tata")
        assert r.groom == "hair"

    def test_parse_sub_field_access(self):
        r = GroomPathResult.parse(VALID_PATH)
        assert r.asset_source.type == "chr"
        assert r.asset_source.code == "toto"
        assert r.asset_target.type == "chr"
        assert r.asset_target.code == "tata"

    def test_format_round_trip(self):
        r = GroomPathResult.parse(VALID_PATH)
        assert str(r) == VALID_PATH

    def test_construct_and_format(self, groom_path_instance):
        assert str(groom_path_instance) == VALID_PATH

    def test_different_groom(self):
        path = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_fur_chr_tata"
        r = GroomPathResult.parse(path)
        assert r.groom == "fur"
        assert str(r) == path

    def test_different_source_type(self):
        path = "/root/assets/prp/prp_sword/modeling/GB_prp_sword_hair_chr_tata"
        r = GroomPathResult.parse(path)
        assert r.asset_source == AssetResult(type="prp", code="sword")
        assert r.asset_target == AssetResult(type="chr", code="tata")

    def test_both_slots_same_type_and_code(self):
        path = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_toto"
        r = GroomPathResult.parse(path)
        assert r.asset_source == r.asset_target

    def test_reused_slot_mismatch_raises(self):
        # asset_source appears 3x; the 2nd/3rd occurrence (in filename)
        # doesn't match the first (in folder)
        bad = "/root/assets/chr/chr_toto/modeling/GB_chr_XXXX_hair_chr_tata"
        with pytest.raises((ParseError,)):
            GroomPathResult.parse(bad)

    def test_partial_embed_mismatch_raises(self):
        # folder says "chr" but chr_toto sub-model has type "prp"
        bad = "/root/assets/chr/prp_toto/modeling/GB_prp_toto_hair_chr_tata"
        with pytest.raises((ParseError,)):
            GroomPathResult.parse(bad)

    def test_invalid_path_raises_parse_error(self):
        with pytest.raises(ParseError):
            GroomPathResult.parse("/wrong/path/here")


# ── flatten() ─────────────────────────────────────────────────────────────────


class TestFlatten:
    def test_flatten_all_keys_present(self):
        r = GroomPathResult.parse(VALID_PATH)
        flat = r.flatten()
        assert "asset_source__type" in flat
        assert "asset_source__code" in flat
        assert "asset_target__type" in flat
        assert "asset_target__code" in flat
        assert "groom" in flat

    def test_flatten_values_correct(self):
        r = GroomPathResult.parse(VALID_PATH)
        flat = r.flatten()
        assert flat["asset_source__type"] == "chr"
        assert flat["asset_source__code"] == "toto"
        assert flat["asset_target__type"] == "chr"
        assert flat["asset_target__code"] == "tata"
        assert flat["groom"] == "hair"

    def test_flatten_simple_model(self):
        r = AssetResult(type="chr", code="toto")
        flat = r.flatten()
        assert flat == {"type": "chr", "code": "toto"}


# ── DefinitionError — caught at class creation ────────────────────────────────


class TestDefinitionError:
    def test_missing_template(self):
        with pytest.raises(DefinitionError, match="must define"):

            class Bad(TemplateModel):
                code: str = Field(ASSET_CODE)

    def test_slot_declared_but_not_used(self):
        with pytest.raises(DefinitionError, match="declared but never used"):

            class Bad(TemplateModel):
                asset = Slot(AssetResult)
                code: str = Field(ASSET_CODE)
                template = ASSET_CODE

    def test_template_wrong_type(self):
        with pytest.raises(DefinitionError, match="must be a string or a Chain"):

            class Bad(TemplateModel):
                code: str = Field(ASSET_CODE)
                template = 42  # type: ignore

    def test_bound_field_nonexistent_field(self):
        with pytest.raises(DefinitionError, match="does not exist"):
            asset = Slot(AssetResult)

            class Bad(TemplateModel):
                asset = asset
                template = asset.nonexistent_field

    def test_slot_used_in_template_not_declared(self):
        """A Slot used in template chain must be assigned as class attribute."""
        with pytest.raises(DefinitionError):
            orphan = Slot(AssetResult)
            orphan.name = "ghost"

            class Bad(TemplateModel):
                code: str = Field(ASSET_CODE)
                template = ASSET_CODE >> "_" >> orphan


# ── Field descriptor ──────────────────────────────────────────────────────────


class TestField:
    def test_field_name_set_by_metaclass(self):
        assert AssetResult._fields["type"].name == "type"
        assert AssetResult._fields["code"].name == "code"

    def test_field_get_on_class_returns_field(self):
        assert isinstance(AssetResult.__dict__["type"], Field)

    def test_field_get_on_instance_returns_value(self):
        r = AssetResult(type="chr", code="toto")
        assert r.type == "chr"

    def test_field_set_on_instance(self):
        r = AssetResult(type="chr", code="toto")
        r.type = "prp"
        assert r.type == "prp"

    def test_field_repr(self):
        f = AssetResult._fields["type"]
        assert "Field" in repr(f)
        assert "type" in repr(f)


# ── Token default values ──────────────────────────────────────────────────────


class TestDefaults:
    def test_field_default_used_when_missing(self):
        VER_WITH_DEFAULT = VERSION.configure(default=1)

        class WithDefault(TemplateModel):
            shot: str = Field(SHOT)
            version: int = Field(VER_WITH_DEFAULT)
            template = SHOT >> "_v" >> VER_WITH_DEFAULT

        r = WithDefault.parse("0010_v001")
        assert r.version == 1
