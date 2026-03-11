# templex

[![Tests](https://github.com/PoloB/templex/actions/workflows/ci.yml/badge.svg)](https://github.com/PoloB/templex/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/PoloB/templex/graph/badge.svg?token=KNWN8UT6OK)](https://codecov.io/gh/PoloB/templex)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

**Object-based, bidirectional string templating with declarative result types.**

templex lets you define string templates using Python objects. Each token
is typed, reusable, and configurable. Parse results are typed model
instances — not plain dicts.

```python
from templex import TemplateModel, Field, Slot
from templex.tokens import StrToken, ChoiceToken

ASSET_TYPE = ChoiceToken("type", choices=["chr", "prp", "env", "veh"])
ASSET_CODE = StrToken("code", pattern=r"[a-z][a-z0-9]+")

class AssetResult(TemplateModel):
    type: str = Field(ASSET_TYPE)
    code: str = Field(ASSET_CODE)
    template = ASSET_TYPE >> "_" >> ASSET_CODE

result = AssetResult.parse("chr_toto")
result.type   # "chr"
result.code   # "toto"
str(result)   # "chr_toto"
```

## Installation

```bash
pip install templex
```

Requires Python 3.10+. No dependencies.

## Documentation

Full documentation at **[your-org.github.io/templex](https://your-org.github.io/templex)**.

## Features

- **Typed tokens** — `StrToken`, `IntToken`, `ChoiceToken`, `RegexToken`
- **Immutable reconfiguration** — `VERSION.configure(format="{:02d}")`
- **Nested templates** — `Slot` embeds one model inside another, producing a typed parse tree
- **Reuse enforcement** — repeated slots must match the same value; enforced by the regex engine
- **Two template syntaxes** — chain (`>>`) and string (`"{slot.field}/{slot}"`) — identical output
- **Configurable delimiters** — `{}`, `<>`, `[]`; global or per-model

## Quick example

```python
from templex import TemplateModel, Field, Slot
from templex.tokens import StrToken, ChoiceToken

GROOM = StrToken("groom", pattern=r"[a-z]+")

class GroomPathResult(TemplateModel):
    asset_source = Slot(AssetResult)
    asset_target = Slot(AssetResult)
    groom: str   = Field(GROOM)

    template = (
        "/root/assets/{asset_source.type}/{asset_source}"
        "/modeling/GB_{asset_source}_{groom}_{asset_target}"
    )

path = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"
r = GroomPathResult.parse(path)

r.asset_source.type   # "chr"
r.groom               # "hair"
r.asset_target.code   # "tata"
str(r) == path        # True
```

## Development

```bash
git clone https://github.com/your-org/templex
cd templex
pip install -e ".[dev]"
pytest tests/ -v --cov=templex
```

## License

MIT
