# Tokens

Tokens are the atomic units of a templex template. Each token defines:

- **Pattern** — the regex it matches during parsing
- **Parser** — converts the matched string to a typed Python value
- **Formatter** — converts a Python value back to a string

All tokens are **immutable**. Use `.configure()` to create a modified copy.

---

## Built-in tokens

### StrToken

Matches a string pattern, returns `str`.

```python
from templex.fields import StrField

CODE = StrField("code", pattern=r"[a-z][a-z0-9]+")
NAME = StrField("name")                              # default: matches [^/]+
UPPER = StrField("label", format=str.upper)          # callable formatter
BRACKETED = StrField("tag", format="[{}]")           # str.format formatter
```

### IntToken

Matches digits, returns `int`. Supports range validation and zero-padded
formatting.

```python
from templex.fields import IntField

VERSION = IntField("version", format="{:03d}")             # → "007"
PAGE    = IntField("page", min=1, max=999, format="{:03d}")
```

### ChoiceToken

Matches one of a fixed set of string values.

```python
from templex.fields import ChoiceField

DEPT = ChoiceField("dept", choices=["chr", "prp", "env", "veh"])
```

Parsing a value not in `choices` raises `ParseError`.

### RegexToken

Defined entirely by a raw regex pattern. Useful for complex patterns that
don't fit `StrToken`.

```python
from templex.fields import RegexField

SEQUENCE = RegexField("sequence", pattern=r"SQ\d{3}")
EPISODE  = RegexField("episode",  pattern=r"EP\d{4}")
```

---

## Immutable reconfiguration

`.configure(**overrides)` returns a new token of the same type with the
specified attributes overridden. The original is never mutated:

```python
VERSION = IntField("version", format="{:03d}")

# Returns a new IntField — VERSION is unchanged
SHORT_VERSION = VERSION.configure(format="{:02d}", max=99)

assert VERSION.format(7)       == "007"
assert SHORT_VERSION.format(7) == "07"
```

All keyword arguments accepted by `__init__` can be overridden. For
`IntToken` this includes `min`, `max`, `format`, `name`, `pattern`, and
`default`.

---

## Default values

Any token can carry a `default` used when the field is absent during
formatting:

```python
VERSION = IntField("version", format="{:03d}", default=1)
```

---

## Custom tokens

Subclass `Token` and implement `_default_pattern()` and `_parse_value()`:

```python
from templex.fields import Field

class ShotField(Field):
    def _default_pattern(self) -> str:
        return r"\d{4}"

    def _parse_value(self, raw: str):
        return int(raw)   # or any typed conversion
```
