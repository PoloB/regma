# Models

A `TemplateModel` is a declarative combination of a parse result type and
a bidirectional string template.

---

## Declaring a model

```python
from regma import TemplateModel
from regma.field import choice, string


class Asset(TemplateModel):
    type: str = choice({"chr", "prp", "env"})
    code: str = string(r"[a-z][a-z0-9]+")

    template = "{type}_{code}"
```

The metaclass validates the model at **class creation time**:

Raise `DefinitionError` at import time, not at parse time.

---

## Parsing

```python
result = Asset._parse_value("chr_toto")
result.type  # "chr"
result.code  # "toto"
```

Parsing raises `ParseError` if the string doesn't match the template.

---

## Formatting

```python
r = Asset(type="chr", code="toto")
str(r)   # "chr_toto"
```

The `__str__` method always uses the same template chain as parsing —
round-trips are guaranteed: `str(Model.parse(s)) == s`.

---

## Equality

Two model instances are equal when all their fields and slots are equal:

```python
Asset(type="chr", code="toto") == Asset(type="chr", code="toto")   # True
Asset(type="chr", code="toto") == Asset(type="prp", code="toto")   # False
```
