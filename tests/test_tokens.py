"""tests/test_tokens.py — Token ABC and built-in token types."""

import pytest

from templex import ChoiceToken, IntToken, RegexToken, StrToken
from templex.exceptions import FormatError, ParseError

# ── StrToken ──────────────────────────────────────────────────────────────────


class TestStrToken:
    def test_parse_returns_string(self):
        t = StrToken("name", pattern=r"[a-z]+")
        assert t.parse("hello") == "hello"
        assert isinstance(t.parse("hello"), str)

    def test_default_pattern_matches_non_slash(self):
        t = StrToken("name")
        r = t.to_regex()
        import re

        assert re.fullmatch(r[len("(?P<name>") : -1], "hello-world")
        assert not re.fullmatch(r[len("(?P<name>") : -1], "hello/world")

    def test_custom_pattern(self):
        t = StrToken("seq", pattern=r"SQ\d{3}")
        import re

        assert re.fullmatch(t._default_pattern(), "SQ010")
        assert not re.fullmatch(t._default_pattern(), "SQ10")

    def test_format_default(self):
        t = StrToken("name")
        assert t.format("hello") == "hello"

    def test_format_callable(self):
        t = StrToken("name", fmt=str.upper)
        assert t.format("hello") == "HELLO"

    def test_format_string_template(self):
        t = StrToken("name", fmt="[{}]")
        assert t.format("hello") == "[hello]"

    def test_to_regex_named_group(self):
        t = StrToken("myfield", pattern=r"[a-z]+")
        assert t.to_regex().startswith("(?P<myfield>")

    def test_to_regex_seen_first_occurrence(self):
        t = StrToken("x", pattern=r"[a-z]+")
        seen = set()
        regex = t.to_regex(seen=seen)
        assert "(?P<x>" in regex
        assert "x" in seen

    def test_to_regex_seen_subsequent_is_backref(self):
        t = StrToken("x", pattern=r"[a-z]+")
        seen = {"x"}
        regex = t.to_regex(seen=seen)
        assert regex == "(?P=x)"

    def test_configure_returns_new_instance(self):
        t = StrToken("name", pattern=r"[a-z]+")
        t2 = t.configure(pattern=r"[A-Z]+")
        assert t2 is not t
        assert t._pattern == r"[a-z]+"
        assert t2._pattern == r"[A-Z]+"

    def test_configure_name_change(self):
        t = StrToken("original", pattern=r"[a-z]+")
        t2 = t.configure(name="renamed")
        assert t2.name == "renamed"
        assert t.name == "original"

    def test_default_value(self):
        t = StrToken("name", default="fallback")
        assert t.default == "fallback"
        assert t.to_format({}) == "fallback"

    def test_missing_value_raises_format_error(self):
        t = StrToken("name")
        with pytest.raises(FormatError):
            t.to_format({})

    def test_repr(self):
        t = StrToken("mytoken")
        assert "StrToken" in repr(t)
        assert "mytoken" in repr(t)


# ── IntToken ──────────────────────────────────────────────────────────────────


class TestIntToken:
    def test_parse_returns_int(self):
        t = IntToken("v")
        assert t.parse("42") == 42
        assert isinstance(t.parse("42"), int)

    def test_parse_zero_padded(self):
        t = IntToken("v")
        assert t.parse("007") == 7

    def test_parse_min_violation(self):
        t = IntToken("v", min_val=1)
        with pytest.raises(ParseError, match="min_val"):
            t.parse("0")

    def test_parse_max_violation(self):
        t = IntToken("v", max_val=100)
        with pytest.raises(ParseError, match="max_val"):
            t.parse("101")

    def test_parse_within_bounds(self):
        t = IntToken("v", min_val=1, max_val=999)
        assert t.parse("500") == 500

    def test_format_default(self):
        t = IntToken("v")
        assert t.format(7) == "7"

    def test_format_zero_padded(self):
        t = IntToken("v", fmt="{:03d}")
        assert t.format(7) == "007"
        assert t.format(42) == "042"
        assert t.format(999) == "999"

    def test_format_callable(self):
        t = IntToken("v", fmt=lambda x: f"v{x:04d}")
        assert t.format(3) == "v0003"

    def test_configure_preserves_min_max(self):
        t = IntToken("v", min_val=1, max_val=999, fmt="{:03d}")
        t2 = t.configure(fmt="{:02d}")
        assert t2.min_val == 1
        assert t2.max_val == 999
        assert t2.format(7) == "07"

    def test_default_pattern_matches_digits(self):
        t = IntToken("v")
        import re

        assert re.fullmatch(t._default_pattern(), "12345")
        assert not re.fullmatch(t._default_pattern(), "abc")


# ── ChoiceToken ───────────────────────────────────────────────────────────────


class TestChoiceToken:
    def test_parse_valid_choice(self):
        t = ChoiceToken("dept", choices=["chr", "prp", "env"])
        assert t.parse("chr") == "chr"
        assert t.parse("env") == "env"

    def test_parse_invalid_choice(self):
        t = ChoiceToken("dept", choices=["chr", "prp"])
        with pytest.raises(ParseError, match="not in choices"):
            t.parse("fx")

    def test_pattern_is_alternation(self):
        t = ChoiceToken("dept", choices=["chr", "prp", "env"])
        import re

        assert re.fullmatch(t._default_pattern(), "chr")
        assert re.fullmatch(t._default_pattern(), "prp")
        assert not re.fullmatch(t._default_pattern(), "fx")

    def test_special_chars_escaped(self):
        t = ChoiceToken("sep", choices=["a.b", "c+d"])
        import re

        assert re.fullmatch(t._default_pattern(), "a.b")
        assert not re.fullmatch(t._default_pattern(), "axb")

    def test_configure_new_choices(self):
        t = ChoiceToken("dept", choices=["chr", "prp"])
        t2 = t.configure(choices=["chr", "prp", "env"])
        assert "env" in t2.choices
        assert "env" not in t.choices

    def test_format(self):
        t = ChoiceToken("dept", choices=["chr", "prp"])
        assert t.format("chr") == "chr"


# ── RegexToken ────────────────────────────────────────────────────────────────


class TestRegexToken:
    def test_parse_returns_string(self):
        t = RegexToken("seq", pattern=r"SQ\d{3}")
        assert t.parse("SQ010") == "SQ010"

    def test_pattern_used_in_regex(self):
        t = RegexToken("seq", pattern=r"SQ\d{3}")
        assert r"SQ\d{3}" in t.to_regex()

    def test_configure(self):
        t = RegexToken("seq", pattern=r"SQ\d{3}")
        t2 = t.configure(pattern=r"EP\d{4}")
        assert t2._pattern == r"EP\d{4}"
        assert t._pattern == r"SQ\d{3}"
