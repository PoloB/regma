# regma

[![Tests](https://github.com/PoloB/regma/actions/workflows/ci.yml/badge.svg)](https://github.com/PoloB/regma/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/PoloB/regma/graph/badge.svg?token=KNWN8UT6OK)](https://codecov.io/gh/PoloB/regma)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

**Object-based, bidirectional string templating with declarative result types.**

regma lets you define string templates using Python objects.
Each token is typed, reusable, and configurable.
Parse results are typed model instances — not plain dicts.

## Installation

```bash
pip install regma
```

Requires Python 3.11+.

## Features

- **Dataclass like structure**: your models are properly typed and subclasses
- **Typed fields**: `string`, `integer`, `choice`
- **Reference to other models**: using annotations or using the `reference` field 
- **Field validation**: fields are validated both during formatting and parsing. Strictness can be configured in both directions independently
- **Configurable delimiters**: `{}`, `<>`, `[]`; global or per-model
- **Great developer experience**: common linter and static type checker are supported. Most common IDEs (VS Code, PyCharm) provide autocompletion 

## Concrete exemple in VFX/Animation pipelines

```python
from regma import TemplateModel
from regma import string, choice, integer

class Asset(TemplateModel):
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
class GroomRetargetInfoPath(TemplateModel):
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
