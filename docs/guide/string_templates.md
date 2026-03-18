# String templates

templex supports two equivalent template syntaxes. Both compile to the
**identical internal `Chain`** — the regex and formatting behaviour are
identical.

---

## Chain syntax (`>>`)

```python
template = (
    "/root/assets/"
    >> asset_source.type
    >> "/"
    >> asset_source
    >> "/modeling/GB_"
    >> asset_source
    >> "_"
    >> GROOM
    >> "_"
    >> asset_target
)
```

Plain `str` literals are automatically wrapped as `Separator` nodes.
Slots used directly become `BoundSlot` nodes; `slot.field` becomes
`BoundField` nodes.

---

## String syntax

```python
template = (
    "/root/assets/{asset_source.type}/{asset_source}"
    "/modeling/GB_{asset_source}_{groom}_{asset_target}"
)
```

Fields inside delimiters are resolved against the model's declared `Field`
and `Slot` attributes:

| Syntax | Resolves to |
|---|---|
| `{name}` | `BoundSlot` if `name` is a `Slot`, otherwise field via `Field` |
| `{name.field}` | `BoundField` — `name` must be a `Slot`, `field` must exist on its model |
| Literal text | `Separator` |

All resolution and validation happens at **class definition time**. Unknown
names, bad sub-fields, or using `.field` on a `Field` (not a `Slot`) all
raise `DefinitionError` at import time.

---

## Verifying equivalence

```python
assert GroomPathChain._regex.pattern == GroomPathString._regex.pattern
```

Both syntaxes always produce the same compiled regex — this is enforced by
the test suite.

---

## When to use which

| Chain `>>` | String |
|---|---|
| Complex composition from sub-chains | Clear, readable declaration |
| Programmatic template construction | Human-written templates |
| IDE auto-complete on field names | Closer to lucidity-style patterns |

For most use cases, the string syntax is more readable. The chain syntax is
more powerful when templates are built dynamically.
