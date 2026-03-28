# regma

**Object-based, bidirectional string templating with declarative result types.**

regma lets you define string templates using Python objects instead of
pattern strings. Each token is reusable and configurable. Parse results are
typed model instances — not plain dicts.

---

## Why regma?

Most templating libraries (like [lucidity](https://github.com/4degrees/lucidity))
work by parsing a pattern string like `{type}_{code}` at runtime. This means:

- Tokens are anonymous — you can't attach behaviour or validation to them
- Results are plain dicts — no type information, no attribute access
- Reuse means copy-pasting strings
- Parsing and formatting are disconnected

regma turns each token into a **first-class object** and each template
result into a **typed model instance**:

```python
from regma import TemplateModel, Field, Slot
from regma.fields import StrField, ChoiceField, IntField

ASSET_TYPE = ChoiceField("type", choices=["chr", "prp", "env", "veh"])
ASSET_CODE = StrField("code", pattern=r"[a-z][a-z0-9]+")

class AssetResult(TemplateModel):
    type: str = Field(ASSET_TYPE)
    code: str = Field(ASSET_CODE)
    template = ASSET_TYPE >> "_" >> ASSET_CODE

result = AssetResult.parse("chr_toto")
result.type   # "chr"   ← attribute access, not dict lookup
result.code   # "toto"
str(result)   # "chr_toto"  ← bidirectional
```

---

## Key features

- **Object-based tokens** — `StrToken`, `IntToken`, `ChoiceToken`, `RegexToken`,
  each with their own parse/format/validate logic
- **Immutable reconfiguration** — `VERSION.configure(format="{:02d}")` returns a
  new token; the original is never mutated
- **Declarative models** — subclass `TemplateModel`, declare `Field` and `Slot`
  descriptors, write `template = ...` once
- **Nested templates as tokens** — a `TemplateModel` can be embedded inside
  another via `Slot`, producing a typed parse tree
- **Reuse enforcement** — the same `Slot` used multiple times in a chain must
  always match the same value; enforced by the regex engine at parse time
- **Two template syntaxes** — chain syntax (`>>`) and string syntax
  (`"{asset_source.type}/{asset_source}"`) compile to the identical internal
  representation
- **Configurable delimiters** — `{}`, `<>`, or `[]`; set globally or per-model

---

## Installation

```bash
pip install regma
```

Requires Python 3.10+, no dependencies.

---

## Quick example

```python
import regma
from regma import TemplateModel, Field, Slot, Delimiter
from regma.fields import StrField, ChoiceField, IntField

# ── Fields ────────────────────────────────────────────────────────────────────
ASSET_TYPE = ChoiceField("type", choices=["chr", "prp", "env", "veh"])
ASSET_CODE = StrField("code", pattern=r"[a-z][a-z0-9]+")
GROOM      = StrField("groom", pattern=r"[a-z]+")

# ── Sub-model ─────────────────────────────────────────────────────────────────
class AssetResult(TemplateModel):
    type: str = Field(ASSET_TYPE)
    code: str = Field(ASSET_CODE)
    template = ASSET_TYPE >> "_" >> ASSET_CODE

# ── Composite model ───────────────────────────────────────────────────────────
class GroomPathResult(TemplateModel):
    asset_source = Slot(AssetResult)   # reusable — same type, distinct instances
    asset_target = Slot(AssetResult)
    groom: str   = Field(GROOM)

    template = (
        "/root/assets/{asset_source.type}/{asset_source}"
        "/modeling/GB_{asset_source}_{groom}_{asset_target}"
    )

# ── Parse ─────────────────────────────────────────────────────────────────────
path = "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"
result = GroomPathResult.parse(path)

result.asset_source          # AssetResult(type='chr', code='toto')
result.asset_source.type     # 'chr'
result.groom                 # 'hair'
result.asset_target.code     # 'tata'

# ── Format ────────────────────────────────────────────────────────────────────
str(result)   # "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"
```

---

## Next steps

- [Quickstart guide](guide/quickstart.md)
- [Token reference](guide/tokens.md)
- [Nested models with Slot](guide/slots.md)
- [String templates and delimiters](guide/string_templates.md)
