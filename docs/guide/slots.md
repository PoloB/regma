# Slots and nested models

A `Slot` embeds one `TemplateModel` inside another. This produces a typed
parse tree rather than a flat result.

---

## Declaring slots

```python
from templex import TemplateModel, Field, Slot
from templex.tokens import StrToken

GROOM = StrToken("groom", pattern=r"[a-z]+")

class GroomPathResult(TemplateModel):
    asset_source = Slot(AssetResult)   # bound to AssetResult template
    asset_target = Slot(AssetResult)   # distinct slot, same template type
    groom: str   = Field(GROOM)

    template = (
        "/root/assets/"
        >> asset_source        # full sub-model match
        >> "/modeling/GB_"
        >> asset_source        # reuse — must match same value
        >> "_"
        >> GROOM
        >> "_"
        >> asset_target        # distinct slot
    )
```

The slot name is inferred from the class attribute name (`asset_source`,
`asset_target`) — exactly like `dataclasses`.

---

## Partial field embeds

Use `slot.field_name` in the template chain to embed only one field of the
sub-model at a specific position:

```python
template = (
    "/root/assets/"
    >> asset_source.type   # only the .type field here
    >> "/"
    >> asset_source        # full sub-model here
    >> ...
)
```

When the same slot appears both as a partial embed (`asset_source.type`) and
a full embed (`asset_source`) in the same chain, the partial embed becomes a
regex **backreference** — the regex engine itself enforces that the partial
value is consistent with the full value. No post-parse checks needed.

---

## Reuse consistency

When the same `Slot` appears more than once in a chain, every occurrence
must match the **identical string**:

```python
# "chr_toto" appears twice — both must be the same
template = ... >> asset_source >> "/modeling/GB_" >> asset_source >> ...
```

The regex engine enforces this via `(?P=slot_name)` backreferences. A mismatch
causes `ParseError` immediately — no value is ever produced.

---

## Parse tree result

```python
r = GroomPathResult.parse(
    "/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata"
)

r.asset_source          # AssetResult(type='chr', code='toto')
r.asset_source.type     # "chr"   — deep attribute access
r.asset_target.code     # "tata"
r.groom                 # "hair"
```

---

## Two slots, same model type

`asset_source` and `asset_target` both use `AssetResult` as their model,
but they are **independent** — they can hold different values, and their
internal regex capture groups are scoped to avoid conflicts:

| Regex group | Belongs to |
|---|---|
| `asset_source__type` | `asset_source` slot |
| `asset_source__code` | `asset_source` slot |
| `asset_target__type` | `asset_target` slot |
| `asset_target__code` | `asset_target` slot |

The parent template only uses named groups with the `slot__field` naming
scheme — there are no ambiguous or colliding group names.
