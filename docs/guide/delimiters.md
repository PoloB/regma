# Delimiters

When using the string template syntax, regma supports three delimiter
styles. The `Delimiter` enum controls which style is expected.

---

## Available delimiters

| Enum value | Syntax | Example |
|---|---|---|
| `Delimiter.CURLY` | `{name}` | `{asset_source.type}/{asset_source}` |
| `Delimiter.ANGLE` | `<name>` | `<asset_source.type>/<asset_source>` |
| `Delimiter.SQUARE` | `[name]` | `[asset_source.type]/[asset_source]` |

**Default:** `Delimiter.CURLY`

All three produce an identical compiled regex — the delimiter is a
declaration-time concern only.

---

## Choosing a delimiter

| Delimiter | Avoid when |
|---|---|
| `CURLY {}` | Using Python `str.format()` or f-strings in the same codebase |
| `ANGLE <>` | Templating HTML or XML |
| `SQUARE []` | Templating URLs with query strings (`?key[]=value`) |

`ANGLE` is often the best choice for file paths and pipeline strings since
`<` and `>` rarely appear literally in those contexts.

---

## Global configuration

Set the default delimiter for all models that don't declare their own:

```python
import regma
from regma import Delimiter

regma.configure(delimiter=Delimiter.ANGLE)
```

This affects all `TemplateModel` subclasses defined **after** this call.
Models already defined keep their original delimiter.

---

## Per-model override

Override the global default for a specific model via an inner `Meta` class:

```python
class GroomPathResult(TemplateModel):
    asset_source = Slot(AssetResult)
    asset_target = Slot(AssetResult)
    groom: str   = Field(GROOM)

    class Meta:
        delimiter = Delimiter.SQUARE   # overrides global for this model

    template = "[asset_source.type]/[asset_source]/modeling/GB_[asset_source]_[groom]_[asset_target]"
```

**Resolution order:** `Meta.delimiter` → global `configure()` → `Delimiter.CURLY`

---

## Introspection

```python
GroomPathResult._delimiter   # Delimiter.SQUARE  (string template)
GroomPathChain._delimiter    # None              (>> chain template)
```

Models defined with the `>>` chain syntax have `_delimiter = None` since
the delimiter concept doesn't apply to them.
