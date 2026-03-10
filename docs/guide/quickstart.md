# Quickstart

This guide walks through templex's core concepts in 5 minutes.

## 1. Define tokens

Tokens are the atomic building blocks. Each token knows how to parse and
format its own value:

```python
from templex.tokens import StrToken, IntToken, ChoiceToken

# Matches a fixed set of strings
ASSET_TYPE = ChoiceToken("type", choices=["chr", "prp", "env", "veh"])

# Matches a custom regex pattern
ASSET_CODE = StrToken("code", pattern=r"[a-z][a-z0-9]+")

# Matches digits, returns an int, formats with zero-padding
VERSION = IntToken("version", format="{:03d}")
```

Tokens are **immutable**. Reconfigure them with `.configure()` — it returns
a new instance and never mutates the original:

```python
SHORT_VERSION = VERSION.configure(format="{:02d}", max=99)
```

## 2. Declare a model

Subclass `TemplateModel`, declare fields, and write the `template`:

```python
from templex import TemplateModel, Field

class AssetResult(TemplateModel):
    type: str = Field(ASSET_TYPE)
    code: str = Field(ASSET_CODE)

    # Chain syntax — tokens joined with >> and string separators
    template = ASSET_TYPE >> "_" >> ASSET_CODE
```

## 3. Parse and format

```python
result = AssetResult.parse("chr_toto")
result.type   # "chr"
result.code   # "toto"

str(result)   # "chr_toto"
```

Parse and format are always **symmetric**: `str(Model.parse(s)) == s`.

## 4. Nest models with Slot

A `TemplateModel` can be embedded inside another via `Slot`. Each `Slot`
instance is a distinct named binding — two slots can share the same model
type while holding different values:

```python
from templex import Slot
from templex.tokens import StrToken

GROOM = StrToken("groom", pattern=r"[a-z]+")

class GroomPathResult(TemplateModel):
    asset_source = Slot(AssetResult)   # ← distinct slot, reuses AssetResult type
    asset_target = Slot(AssetResult)   # ← another distinct slot
    groom: str   = Field(GROOM)

    template = (
        "/root/assets/"
        >> asset_source.type   # partial sub-field embed
        >> "/"
        >> asset_source        # full sub-model embed
        >> "/modeling/GB_"
        >> asset_source        # reuse — must match same value
        >> "_"
        >> GROOM
        >> "_"
        >> asset_target
    )
```

```python
path = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"
r = GroomPathResult.parse(path)

r.asset_source.type   # "chr"
r.asset_source.code   # "toto"
r.groom               # "hair"
r.asset_target.code   # "tata"

str(r) == path        # True
```

## 5. String template syntax

Instead of `>>`, you can write the template as a format string.
Both compile to the **identical** internal representation:

```python
class GroomPathResult(TemplateModel):
    asset_source = Slot(AssetResult)
    asset_target = Slot(AssetResult)
    groom: str   = Field(GROOM)

    template = (
        "/root/assets/{asset_source.type}/{asset_source}"
        "/modeling/GB_{asset_source}_{groom}_{asset_target}"
    )
```

Use `<name>` or `[name]` syntax via the `Delimiter` enum — see
[Delimiters](delimiters.md).

## 6. Flatten to dict

```python
r.flatten()
# {
#   "asset_source__type": "chr",
#   "asset_source__code": "toto",
#   "asset_target__type": "chr",
#   "asset_target__code": "tata",
#   "groom": "hair",
# }
```
