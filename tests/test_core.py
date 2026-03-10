"""tests/test_core.py — Chainable ABC, Separator, Chain."""

import pytest

from templex import StrToken
from templex.core import Chain, Separator
from templex.slot import BoundSlot, Slot

# ── Separator ─────────────────────────────────────────────────────────────────


class TestSeparator:
    def test_to_regex_escapes_special_chars(self):
        s = Separator("/root/assets.")
        assert s.to_regex() == r"/root/assets\."

    def test_to_format_returns_literal(self):
        s = Separator("/modeling/GB_")
        assert s.to_format({}) == "/modeling/GB_"

    def test_slot_refs_empty(self):
        s = Separator("_")
        assert s._slot_refs() == []

    def test_repr(self):
        s = Separator("_")
        assert "'_'" in repr(s)

    def test_accepts_seen_kwarg(self):
        s = Separator("_")
        # seen param is accepted and ignored
        assert s.to_regex(seen=set()) == r"\_"


# ── Chain ─────────────────────────────────────────────────────────────────────


class TestChain:
    def _tok(self, name="x", pattern=r"[a-z]+"):
        return StrToken(name, pattern=pattern)

    def test_to_regex_concatenates_nodes(self):
        a = self._tok("a")
        b = self._tok("b")
        chain = Chain([a, Separator("_"), b])
        assert chain.to_regex() == "(?P<a>[a-z]+)_(?P<b>[a-z]+)"

    def test_to_format_concatenates(self):
        chain = Chain([Separator("hello"), Separator("-"), Separator("world")])
        assert chain.to_format({}) == "hello-world"

    def test_slot_refs_collected_from_all_nodes(self):
        from templex import ChoiceToken, Field, TemplateModel

        ASSET_TYPE = ChoiceToken("type", choices=["chr"])
        ASSET_CODE = StrToken("code", pattern=r"[a-z]+")

        class A(TemplateModel):
            type: str = Field(ASSET_TYPE)
            code: str = Field(ASSET_CODE)
            template = ASSET_TYPE >> "_" >> ASSET_CODE

        slot = Slot(A)
        slot.name = "a"
        bound = BoundSlot(slot)
        chain = Chain([bound, Separator("_"), self._tok("x")])
        refs = chain._slot_refs()
        assert len(refs) == 1
        assert refs[0] is bound

    def test_rshift_extends_chain(self):
        a = self._tok("a")
        b = self._tok("b")
        chain = Chain([a]) >> "_" >> b
        assert len(chain._nodes) == 3

    def test_to_regex_passes_seen(self):
        t = self._tok("x")
        chain = Chain([t, Separator("_"), t])
        seen = set()
        regex = chain.to_regex(seen=seen)
        # First occurrence: named group; second: backreference
        assert "(?P<x>" in regex
        assert "(?P=x)" in regex

    def test_repr(self):
        chain = Chain([Separator("_")])
        assert "Chain" in repr(chain)


# ── _as_chainable ─────────────────────────────────────────────────────────────


class TestAsChainable:
    def test_str_becomes_separator(self):
        result = _as_chainable("_")
        assert isinstance(result, Separator)
        assert result.value == "_"

    def test_chainable_passthrough(self):
        t = StrToken("x")
        assert _as_chainable(t) is t

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError, match="Cannot use"):
            _as_chainable(42)

    def test_slot_becomes_bound_slot(self):
        from templex import ChoiceToken, Field, TemplateModel

        ASSET_TYPE = ChoiceToken("type", choices=["chr"])
        ASSET_CODE = StrToken("code", pattern=r"[a-z]+")

        class A(TemplateModel):
            type: str = Field(ASSET_TYPE)
            code: str = Field(ASSET_CODE)
            template = ASSET_TYPE >> "_" >> ASSET_CODE

        slot = Slot(A)
        slot.name = "a"
        result = _as_chainable(slot)
        assert isinstance(result, BoundSlot)


# ── Operator >> ───────────────────────────────────────────────────────────────


class TestRshiftOperator:
    def _tok(self, name, pattern=r"[a-z]+"):
        return StrToken(name, pattern=pattern)

    def test_token_rshift_string(self):
        result = self._tok("a") >> "_"
        assert isinstance(result, Chain)

    def test_token_rshift_token(self):
        result = self._tok("a") >> self._tok("b")
        assert isinstance(result, Chain)
        assert len(result._nodes) == 2

    def test_string_rrshift_token(self):
        result = "prefix_" >> self._tok("a")
        assert isinstance(result, Chain)
        assert isinstance(result._nodes[0], Separator)

    def test_chain_rshift_flattens(self):
        a = self._tok("a")
        b = self._tok("b")
        c = self._tok("c")
        chain = (a >> "_" >> b) >> "_" >> c
        # Should be flat: a _ b _ c
        assert len(chain._nodes) == 5

    def test_complex_chain_regex(self):
        a = self._tok("a")
        b = self._tok("b", pattern=r"\d+")
        chain = "start_" >> a >> "_" >> b >> "_end"
        import re

        pattern = re.compile("^" + chain.to_regex() + "$")
        m = pattern.match("start_hello_42_end")
        assert m is not None
        assert m.group("a") == "hello"
        assert m.group("b") == "42"
