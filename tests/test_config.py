"""tests/test_config.py — Delimiter enum and global configure()."""

import pytest

from templex import Delimiter, Field, Slot, TemplateModel, configure, get_delimiter
from templex.exceptions import DefinitionError

from .conftest import GROOM, VALID_PATH, AssetResult, GroomPathResult

# ── Delimiter enum ────────────────────────────────────────────────────────────


class TestDelimiterEnum:
    def test_curly_chars(self):
        assert Delimiter.CURLY.token_open == "{"
        assert Delimiter.CURLY.token_close == "}"

    def test_angle_chars(self):
        assert Delimiter.ANGLE.token_open == "<"
        assert Delimiter.ANGLE.token_close == ">"

    def test_square_chars(self):
        assert Delimiter.SQUARE.token_open == "["
        assert Delimiter.SQUARE.token_close == "]"

    def test_token_re_curly_matches(self):
        pattern = Delimiter.CURLY.token_re()
        m = pattern.search("{asset_source.type}")
        assert m is not None
        assert m.group(1) == "asset_source"
        assert m.group(2) == "type"

    def test_token_re_angle_matches(self):
        pattern = Delimiter.ANGLE.token_re()
        m = pattern.search("<groom>")
        assert m is not None
        assert m.group(1) == "groom"
        assert m.group(2) is None

    def test_token_re_square_matches(self):
        pattern = Delimiter.SQUARE.token_re()
        m = pattern.search("[asset.code]")
        assert m is not None
        assert m.group(1) == "asset"
        assert m.group(2) == "code"

    def test_token_re_no_cross_match(self):
        # CURLY pattern must not match angle brackets
        curly_re = Delimiter.CURLY.token_re()
        assert curly_re.search("<groom>") is None

    def test_repr(self):
        assert repr(Delimiter.CURLY) == "Delimiter.CURLY"
        assert repr(Delimiter.ANGLE) == "Delimiter.ANGLE"
        assert repr(Delimiter.SQUARE) == "Delimiter.SQUARE"

    def test_all_three_produce_same_regex_for_same_template(self):
        from templex import Field
        from templex.template_parser import parse_template

        fields = {"groom": Field(GROOM)}
        fields["groom"].name = "groom"

        chains = {
            d: parse_template(f"{d.token_open}groom{d.token_close}", fields, {}, d) for d in Delimiter
        }
        regexes = [c.to_regex(seen=set()) for c in chains.values()]
        assert len(set(regexes)) == 1, f"Regexes differ: {regexes}"


# ── configure() and get_delimiter() ──────────────────────────────────────────


class TestConfigure:
    def test_default_is_curly(self):
        assert get_delimiter() == Delimiter.CURLY

    def test_configure_changes_global(self):
        configure(delimiter=Delimiter.ANGLE)
        assert get_delimiter() == Delimiter.ANGLE

    def test_configure_bad_type_raises(self):
        with pytest.raises(TypeError, match="must be a Delimiter instance"):
            configure(delimiter="{}")  # type: ignore

    def test_configure_none_is_noop(self):
        original = get_delimiter()
        configure(delimiter=None)
        assert get_delimiter() == original

    def test_global_affects_new_models(self):
        configure(delimiter=Delimiter.ANGLE)

        class M(TemplateModel):
            asset_source = Slot(AssetResult)
            asset_target = Slot(AssetResult)
            groom: str = Field(GROOM)
            template = (
                "/root/assets/<asset_source.type>/<asset_source>"
                "/modeling/GB_<asset_source>_<groom>_<asset_target>"
            )

        assert M._delimiter == Delimiter.ANGLE
        r = M.parse(VALID_PATH)
        assert r.groom == "hair"

    def test_global_does_not_affect_existing_models(self):
        configure(delimiter=Delimiter.ANGLE)
        # GroomPathResult was defined with >> chain (no delimiter)
        assert GroomPathResult._delimiter is None
        # Must still parse correctly
        r = GroomPathResult.parse(VALID_PATH)
        assert r.groom == "hair"


# ── Per-model Meta.delimiter ──────────────────────────────────────────────────


class TestMetaDelimiter:
    def test_meta_overrides_global(self):
        configure(delimiter=Delimiter.ANGLE)

        class M(TemplateModel):
            groom: str = Field(GROOM)

            class Meta:
                delimiter = Delimiter.SQUARE

            template = "[groom]"

        assert M._delimiter == Delimiter.SQUARE
        r = M.parse("hair")
        assert r.groom == "hair"

    def test_meta_delimiter_stored_on_class(self):
        class M(TemplateModel):
            groom: str = Field(GROOM)

            class Meta:
                delimiter = Delimiter.ANGLE

            template = "<groom>"

        assert M._delimiter == Delimiter.ANGLE

    def test_chain_model_delimiter_is_none(self):
        assert GroomPathResult._delimiter is None

    def test_meta_invalid_delimiter_raises(self):
        with pytest.raises(DefinitionError, match="Meta.delimiter must be a Delimiter"):

            class Bad(TemplateModel):
                groom: str = Field(GROOM)

                class Meta:
                    delimiter = "{}"  # string, not Delimiter instance

                template = "{groom}"

    def test_all_three_delimiters_parse_same_path(self):
        models = {}
        for delim, tmpl in [
            (Delimiter.CURLY, "{groom}"),
            (Delimiter.ANGLE, "<groom>"),
            (Delimiter.SQUARE, "[groom]"),
        ]:

            class M(TemplateModel):
                groom: str = Field(GROOM)

                class Meta:
                    delimiter = delim

                template = tmpl

            models[delim] = M

        for delim, M in models.items():
            r = M.parse("hair")
            assert r.groom == "hair", f"Failed for {delim}"
            assert str(r) == "hair"
