"""tests/test_template_parser.py — string template parsing."""

import pytest

from templex import (
    Delimiter,
    Field,
    Slot,
    TemplateModel,
)
from templex.exceptions import DefinitionError
from templex.template_parser import parse_template

from .conftest import (
    ASSET_CODE,
    GROOM,
    VALID_PATH,
    AssetResult,
    GroomPathResult,
    GroomPathResultStr,
)

# ── parse_template_string() directly ─────────────────────────────────────────


class TestParseTemplateStringDirect:
    def _fields_slots(self):
        class M(TemplateModel):
            asset = Slot(AssetResult)
            code: str = Field(ASSET_CODE)
            template = ASSET_CODE  # minimal valid template

        return M._fields, M._slots

    def test_separators_become_separator_nodes(self):
        from templex.core import Separator

        fields = {"code": Field(ASSET_CODE)}
        fields["code"].name = "code"
        chain = parse_template("/prefix/{code}/suffix", fields, {}, Delimiter.CURLY)
        separators = [n for n in chain._nodes if isinstance(n, Separator)]
        assert any("/prefix/" in s.value for s in separators)
        assert any("/suffix" in s.value for s in separators)

    def test_unknown_token_raises(self):
        with pytest.raises(DefinitionError, match="is not a declared Field or Slot"):
            parse_template("{unknown}", {}, {}, Delimiter.CURLY, model_name="Test")

    def test_dot_on_field_raises(self):
        fields = {"code": Field(ASSET_CODE)}
        fields["code"].name = "code"
        with pytest.raises(DefinitionError, match="is not a declared Slot"):
            parse_template(
                "{code.something}", fields, {}, Delimiter.CURLY, model_name="Test"
            )

    def test_bad_subfield_raises(self):
        slots = {"asset": Slot(AssetResult)}
        slots["asset"].name = "asset"
        with pytest.raises(DefinitionError, match="does not exist"):
            parse_template(
                "{asset.nonexistent}", {}, slots, Delimiter.CURLY, model_name="Test"
            )

    def test_all_delimiters_produce_same_chain_regex(self):
        fields = {"code": Field(ASSET_CODE)}
        fields["code"].name = "code"
        chains = [
            parse_template("{code}", fields, {}, Delimiter.CURLY),
            parse_template("<code>", fields, {}, Delimiter.ANGLE),
            parse_template("[code]", fields, {}, Delimiter.SQUARE),
        ]
        regexes = [c.to_regex(seen=set()) for c in chains]
        assert regexes[0] == regexes[1] == regexes[2]


# ── String syntax on TemplateModel ────────────────────────────────────────────


class TestStringTemplateOnModel:
    def test_parse_full_path(self):
        r = GroomPathResultStr.parse(VALID_PATH)
        assert r.asset_source == AssetResult(type="chr", code="toto")
        assert r.asset_target == AssetResult(type="chr", code="tata")
        assert r.groom == "hair"

    def test_sub_field_access(self):
        r = GroomPathResultStr.parse(VALID_PATH)
        assert r.asset_source.type == "chr"
        assert r.asset_target.code == "tata"

    def test_format_round_trip(self):
        r = GroomPathResultStr.parse(VALID_PATH)
        assert str(r) == VALID_PATH

    def test_chain_and_string_produce_identical_regex(self):
        assert GroomPathResult._regex.pattern == GroomPathResultStr._regex.pattern

    def test_reuse_mismatch_raises(self):
        bad = "/root/assets/chr/chr_toto/modeling/GB_chr_XXXX_hair_chr_tata"
        with pytest.raises(Exception):
            GroomPathResultStr.parse(bad)

    def test_partial_embed_mismatch_raises(self):
        bad = "/root/assets/chr/prp_toto/modeling/GB_prp_toto_hair_chr_tata"
        with pytest.raises(Exception):
            GroomPathResultStr.parse(bad)

    def test_angle_delimiter(self):
        class M(TemplateModel):
            asset_source = Slot(AssetResult)
            asset_target = Slot(AssetResult)
            groom: str = Field(GROOM)

            class Meta:
                delimiter = Delimiter.ANGLE

            template = (
                "/root/assets/<asset_source.type>/<asset_source>"
                "/modeling/GB_<asset_source>_<groom>_<asset_target>"
            )

        r = M.parse(VALID_PATH)
        assert r.groom == "hair"
        assert str(r) == VALID_PATH

    def test_square_delimiter(self):
        class M(TemplateModel):
            asset_source = Slot(AssetResult)
            asset_target = Slot(AssetResult)
            groom: str = Field(GROOM)

            class Meta:
                delimiter = Delimiter.SQUARE

            template = (
                "/root/assets/[asset_source.type]/[asset_source]"
                "/modeling/GB_[asset_source]_[groom]_[asset_target]"
            )

        r = M.parse(VALID_PATH)
        assert r.groom == "hair"
        assert str(r) == VALID_PATH

    def test_definition_error_unknown_name(self):
        with pytest.raises(DefinitionError):

            class Bad(TemplateModel):
                groom: str = Field(GROOM)
                template = "{groom}_{totally_unknown}"

    def test_definition_error_bad_subfield(self):
        with pytest.raises(DefinitionError):

            class Bad(TemplateModel):
                asset = Slot(AssetResult)
                template = "{asset.nonexistent}"

    def test_definition_error_field_used_as_slot(self):
        with pytest.raises(DefinitionError):

            class Bad(TemplateModel):
                groom: str = Field(GROOM)
                template = "{groom.something}"
