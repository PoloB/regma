# Quickstart

This guide walks through templex's core concepts in 5 minutes.


## 1. Declare a model

Subclass `TemplateModel`, declare tokens, and write the `template`:

```python
from templex import TemplateModel
from templex import token

class Asset(TemplateModel):
    type: str = token.choice({'chr', 'prp'})
    code: str = token.string(r"\w+")

    # Declare the tempalte using the declared tokens
    template = "{type}_{code}"
```

## 2. Parse and format

```python
asset = Asset.parse("chr_toto")
asset.type  # "chr"
asset.code  # "toto"

str(asset)  # "chr_toto"
```

Parse and format are always **symmetric**: `str(Model.parse(s)) == s`.

## 3. Nest models

A `TemplateModel` can be embedded inside another via `token.model`:

```python
from templex import TemplateModel
from templex import token


class GroomPath(TemplateModel):
    asset_source: Asset
    asset_target: Asset
    groom: str = token.string(r"\w+")

    template = "/root/assets/{asset_source.type}/{asset_source}/modeling/GB_{asset_source}_{groom}_{asset_target}"
```

```python
path = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"
r = GroomPath.parse(path)

r.asset_source.type  # "chr"
r.asset_source.code  # "toto"
r.groom  # "hair"
r.asset_target.code  # "tata"

str(r) == path  # True
```

Use `<name>` or `[name]` syntax via the `Delimiter` enum — see
[Delimiters](delimiters.md).
