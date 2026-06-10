# regma

![Python](https://img.shields.io/pypi/pyversions/regma)
[![Tests](https://github.com/PoloB/regma/actions/workflows/ci.yml/badge.svg)](https://github.com/PoloB/regma/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/PoloB/regma/graph/badge.svg?token=qxGwGJRzV6)](https://codecov.io/gh/PoloB/regma)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

**String templates with dataclass style**

regma lets you define string templates through models behaving like standard dataclass.

It aims at solving a common scenario in the VFX/animation industry where we need to construct file paths from tokens 
and extract tokens from file paths.

regma lets you define the structure of your strings from typed fields and will handle for you:
- formatting of your model instances to string
- parsing of a string to model instances

## Features

- **Dataclass like structure**: your models are properly typed and subclassable
- **Typed fields**: `string`, `integer`, `choice`
- **Reference to other models**: using annotations or using the `reference` field 
- **Field validation**: fields are validated both during formatting and parsing. Strictness can be configured in both directions independently
- **Configurable delimiters**: `{}`, `<>`, `[]`; global or per-model
- **Great developer experience**: common linter and static type checker are supported. Most common IDEs (VS Code, PyCharm) provide autocompletion 

## Concrete example

```python
from regma import Model
from regma import string, choice, integer


class Asset(Model):
    type: str = choice(["chr", "prp", "set"])
    code: str = string(r"[a-z][a-z0-9]+")
    template = "{type}_{code}"


# Create an asset from its fields
asset = Asset("chr", "foo")

# Get it as a string
asset_str = asset.format()  # or using str(asset)

# Parse an asset from its string
parsed_asset = Asset.parse("chr_foo")


# Build a more complex example to build a path
class GroomRetargetInfoPath(Model):
    source_asset: Asset
    target_asset: Asset
    groom_name: str = string(r"[a-z][a-z0-9]+")

    template = (
        "/root/assets/{target_asset.type}/{target_asset}/{asset_target}_{groom}_{asset_target}.json"
    )


# Create a new model
groom_info = GroomRetargetInfoPath(Asset("chr", "foo"), Asset("chr", "bar"), "hair")

# Get it as string
groom_info_path = groom_info.format()  # /root/assets/chr/chr_foo/chr_foo_hair_chr_bar.json

# Parse the path to its information
parsed_groom_info = GroomRetargetInfoPath.parse("/root/assets/chr/chr_foo/chr_foo_hair_chr_bar.json")

```

## License

MIT
