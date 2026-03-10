# Models

A `TemplateModel` is a declarative combination of a parse result type and
a bidirectional string template.

---

## Declaring a model

```python
from templex import TemplateModel, Field
from templex.tokens import ChoiceToken, StrToken

ASSET_TYPE = ChoiceToken("type", choices=["chr", "prp", "env", "veh"])
ASSET_CODE = StrToken("code", pattern=r"[a-z][a-z0-9]+")

class AssetResult(TemplateModel):
    type: str = Field(ASSET_TYPE)   # attribute + token binding
    code: str = Field(ASSET_CODE)

    template = ASSET_TYPE >> "_" >> ASSET_CODE
```

The metaclass validates the model at **class creation time**:

- Every `Field` must appear in `template`
- Every `Slot` must appear in `template`
- Sub-field accesses (`slot.field`) must reference existing fields

Errors raise `DefinitionError` at import time, not at parse time.

---

## Parsing

```python
result = AssetResult.parse("chr_toto")
result.type   # "chr"
result.code   # "toto"
```

Parsing raises `ParseError` if the string doesn't match the template.

---

## Formatting

```python
r = AssetResult(type="chr", code="toto")
str(r)   # "chr_toto"
```

The `__str__` method always uses the same template chain as parsing —
round-trips are guaranteed: `str(Model.parse(s)) == s`.

---

## Equality

Two model instances are equal when all their fields and slots are equal:

```python
AssetResult(type="chr", code="toto") == AssetResult(type="chr", code="toto")   # True
AssetResult(type="chr", code="toto") == AssetResult(type="prp", code="toto")   # False
```

---

## flatten()

Returns a flat `dict` with `__` as the namespace separator for nested slots:

```python
r = GroomPathResult.parse("/root/assets/chr/chr_toto/modeling/GB_chr_toto_hair_chr_tata")
r.flatten()
# {
#     "asset_source__type": "chr",
#     "asset_source__code": "toto",
#     "asset_target__type": "chr",
#     "asset_target__code": "tata",
#     "groom": "hair",
# }
```

---

## Template chain syntax

The `>>` operator composes any two `Chainable` objects. Plain strings are
automatically converted to `Separator` nodes:

```python
template = ASSET_TYPE >> "_" >> ASSET_CODE
#          ┌─────────────┐   ┌─────────────────┐
#          Token          Separator  Token
```

Chains themselves are `Chainable`, so they compose recursively:

```python
asset_chain = ASSET_TYPE >> "_" >> ASSET_CODE
full_chain  = "/prefix/" >> asset_chain >> "/suffix"
```
