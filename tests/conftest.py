"""
tests/conftest.py
~~~~~~~~~~~~~~~~~
Shared fixtures and token/model definitions used across the test suite.
"""

import pytest

from templex import (
    ChoiceToken,
    Field,
    IntToken,
    Slot,
    StrToken,
    TemplateModel,
    configure,
    get_delimiter,
)

# ── Primitive tokens (module-level, reusable) ─────────────────────────────────

ASSET_TYPE = ChoiceToken("type", choices=["chr", "prp", "env", "veh"])
ASSET_CODE = StrToken("code", pattern=r"[a-z][a-z0-9]+")
GROOM = StrToken("groom", pattern=r"[a-z]+")
VERSION = IntToken("version", fmt="{:03d}")
SHOT = StrToken("shot", pattern=r"\d{4}")
TASK = ChoiceToken("task", choices=["model", "rig", "render", "groom"])


# ── Sub-models ────────────────────────────────────────────────────────────────


class AssetResult(TemplateModel):
    """Matches 'chr_toto', 'prp_sword', etc."""

    type: str = ChoiceToken("type", choices=["chr", "prp", "env", "veh"])
    code: str = StrToken("code", pattern=r"[a-z][a-z0-9]+")
    template = "{type}_{code}"


class ShotResult(TemplateModel):
    """Matches '0030_v002'."""

    shot: str = StrToken("shot", pattern=r"\d{4}")
    version: int = IntToken("version", fmt="{:03d}")
    template = "{shot}_v{version}"


# ── Main path model (>> chain syntax) ────────────────────────────────────────


class GroomPathResult(TemplateModel):
    """
    Matches: /root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata
    Demonstrates: partial embed, full slot reuse, two distinct slots of same type.
    """

    asset_source = AssetResult
    asset_target = AssetResult
    groom: str = StrToken("groom", pattern=r"[a-z]+")

    template = "/root/assets/{asset_source.type}/{asset_source}/modeling/GB_{asset_source}_{groom}_{asset_target}"


# ── Shared path constant ──────────────────────────────────────────────────────

VALID_PATH = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def asset_source_instance():
    return AssetResult(type="chr", code="toto")


@pytest.fixture
def asset_target_instance():
    return AssetResult(type="chr", code="tata")


@pytest.fixture
def groom_path_instance(asset_source_instance, asset_target_instance):
    return GroomPathResult(
        asset_source=asset_source_instance,
        asset_target=asset_target_instance,
        groom="hair",
    )


@pytest.fixture(autouse=True)
def reset_global_delimiter():
    """Restore the global delimiter after each test that mutates it."""
    original = get_delimiter()
    yield
    configure(delimiter=original)
