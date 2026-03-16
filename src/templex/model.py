"""Template model implementation."""

from __future__ import annotations

import enum
import re
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Self
from typing import override

from typing_extensions import dataclass_transform

from templex import Separator
from templex import TemplateNode
from templex.core import AbstractToken
from templex.core import Chain
from templex.core import RegexBuilder
from templex.core import T_token
from templex.error import DefinitionError
from templex.token import ModelToken
from templex.token import choice
from templex.token import custom_token
from templex.token import integer
from templex.token import model
from templex.token import string


class Delimiter(enum.Enum):
    """Token delimiter styles for string templates.

    Examples:
    CURLY  →  {asset_source.type}/{asset_source}
    ANGLE  →  <asset_source.type>/<asset_source>
    SQUARE →  [asset_source.type]/[asset_source]
    """

    CURLY = ("{", "}")
    ANGLE = ("<", ">")
    SQUARE = ("[", "]")

    @property
    def token_open(self) -> str:
        """Return the open token of the delimiter."""
        return self.value[0]

    @property
    def token_close(self) -> str:
        """Return the close token of the delimiter."""
        return self.value[1]

    def token_re(self) -> re.Pattern[str]:
        """Compile and return the regex that matches one token placeholder."""
        o = re.escape(self.token_open)
        c = re.escape(self.token_close)
        ident = rf"[^{o}{c}]*"
        return re.compile(rf"{o}({ident}(?:\.{ident})*){c}")


class BoundToken(TemplateNode, Generic[T_token]):
    """A token bound to a template model through an attribute."""

    def __init__(self, name: str, token: AbstractToken[T_token]) -> None:
        """Initialize the bound token.

        The name is the name of the attribute the token is bound to.

        For example, in the following template model:

        class ExampleModel(TemplateModel):
            __template__ = "{test}"
            test: str = StrToken(".+")

        The name is 'test' and the token is StrToken(".+")
        """
        self._name = name
        self._token = token

    @property
    def name(self) -> str:
        """Return the name of the bound token."""
        return self._name

    @property
    def token(self) -> AbstractToken[T_token]:
        """Return the bound token."""
        return self._token

    @override
    def to_chain(self) -> Chain:
        return Chain([self])

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return builder.build(self._name, self._token)


class TokenReference(TemplateNode):
    """A referenced token in a model template.

    This is used in the template parsing.
    """

    def __init__(self, attribute_name: str, target_token: AbstractToken[Any]) -> None:
        """Initialize a TokenReference node."""
        self.__name = attribute_name
        self._token = target_token

    @property
    def attribute_name(self) -> str:
        """Return the name of the token attribute."""
        return self.__name

    @property
    def target(self) -> AbstractToken[Any]:
        """Return the token referenced as a target token."""
        return self._token

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return builder.build(self.__name, self._token)

    @override
    def to_chain(self) -> Chain:
        return Chain([self])


def _parse_template(template_model: TemplateModelMeta) -> Chain:
    """Convert a template string into a :class:`~templex.core.Chain`."""
    template = template_model.__template__
    delimiter = template_model.__delimiter__
    token_re = delimiter.token_re()
    nodes: list[TemplateNode] = []
    cursor = 0
    existing_token_references: dict[str, TokenReference] = {}

    for m in token_re.finditer(template):
        start, end = m.span()
        attr_name: str = m.group(1)

        attributes = attr_name.split(".")

        if start > cursor:
            nodes.append(Separator(template[cursor:start]))

        # Find the targeted token
        token_reference: TokenReference | None = None
        lookup_obj = template_model
        attribute_full_name = ""
        for attr in attributes:
            if not attr:
                continue

            attribute_full_name += attr
            token_reference = existing_token_references.get(attr)

            if token_reference:
                lookup_obj = getattr(lookup_obj, attr)
                token_reference = TokenReference(attribute_full_name, lookup_obj)
                attribute_full_name += "."
                continue

            try:
                lookup_obj = getattr(lookup_obj, attr)
            except AttributeError as e:
                msg = (
                    f"{template_model.__name__}: in reference {m.group()}, "
                    f"could not find attribute {attr!r} in {lookup_obj}"
                )
                raise DefinitionError(msg) from e

            if not isinstance(lookup_obj, AbstractToken):
                msg = (
                    f"{template_model.__name__}: in reference {m.group()}, "
                    f"attribute {attribute_full_name!r} is not an AbstractToken"
                )
                raise DefinitionError(msg)
            token_reference = TokenReference(attribute_full_name, lookup_obj)
            existing_token_references[attribute_full_name] = token_reference
            attribute_full_name += "."

        if token_reference is None:
            msg = f"Invalid attribute {attr_name}"
            raise DefinitionError(msg)

        nodes.append(token_reference)
        cursor = end

    if cursor < len(template):
        nodes.append(Separator(template[cursor:]))

    return Chain(nodes)


def _validate_template(
    model_cls: TemplateModelMeta,
) -> None:
    """Validates that the template is valid."""
    # Template shall contain all the element required to build its model references

    def _check_has_all_elements(
        model_cls_: TemplateModelMeta, references: set[str], parent_bound: str
    ) -> None:
        model_tokens: dict[str, ModelToken[TemplateModel]] = {}
        other_token_names: set[str] = set()

        for bound_token in model_cls_.__bound_tokens__.values():
            wrapped_token = bound_token.token
            if not isinstance(wrapped_token, ModelToken):
                other_token_names.add(bound_token.name)
                continue
            model_tokens[bound_token.name] = wrapped_token

        # Check leaf tokens are used in the template
        missing_tokens = other_token_names.difference(references)
        if missing_tokens:
            # Rebuild the full missing token
            missing_full_tokens = sorted(
                f"{parent_bound}.{missing_token}" for missing_token in missing_tokens
            )
            msg = (
                f"All tokens of {parent_bound!r} are not used in "
                f"{model_cls.__name__} template (missing {missing_full_tokens})"
            )
            raise DefinitionError(msg)

        for bound_name, model_token in model_tokens.items():
            # Get all the references starting with the bound name
            model_refs = {r for r in references if r.startswith(bound_name)}
            if bound_name in model_refs:
                # There is a complete reference, this is ok
                continue

            sub_references = {r.split(".", maxsplit=1)[1] for r in model_refs}
            # Check recursively
            _check_has_all_elements(
                model_token.model,
                sub_references,
                f"{parent_bound}.{bound_name}" if parent_bound else bound_name,
            )

    ref_tokens = {
        node.attribute_name
        for node in model_cls.__chain__.nodes
        if isinstance(node, TokenReference)
    }

    _check_has_all_elements(model_cls, ref_tokens, "")


class TemplateModelMeta(type):
    """Validates and wires up a TemplateModel subclass at definition time.

    1. Injects ``name`` into all :class:`Field` and :class:`~templex.slot.Slot`
       descriptors.
    2. Normalizes ``template`` (string or :class:`~templex.core.Chain`) and
       compiles a full regex.
    3. Validates that every Field/Slot appears in the chain (and vice versa).
    4. Validates sub-field accesses (``slot.field``) against the sub-model.
    """

    __bound_tokens__: dict[str, BoundToken[Any]] = {}  # noqa: RUF012
    __template__: str
    __delimiter__: Delimiter
    __chain__: Chain
    __regex__: str

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,  # noqa: ANN401
    ) -> TemplateModelMeta:
        """Build the template model internals (tokens -> bound tokens, chain, regex)."""
        cls: TemplateModelMeta = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Skip the bare TemplateModel base itself
        if name == "TemplateModel":
            return cls

        # Create bounded token objects
        bound_tokens: dict[str, BoundToken[Any]] = {}

        for attr, value in namespace.items():
            if isinstance(value, AbstractToken):
                bound_tokens[attr] = BoundToken(attr, value)

        cls.__bound_tokens__ = bound_tokens

        # Validate template
        raw_template: Any = namespace.get("__template__")
        if raw_template is None:
            msg = f"{name}: must define a '__template__'"
            raise DefinitionError(msg)

        contents = [namespace, *[b.__dict__ for b in bases]]
        # Go through all bases to get the delimiter
        delimiters = (c.get("__delimiter__") for c in contents)
        delimiter = next(d for d in delimiters if d is not None)

        if not isinstance(delimiter, Delimiter):
            msg = (
                f"{name}: __delimiter__ must be a {Delimiter.__name__} instance, "
                f"got {type(delimiter).__name__!r}"
            )
            raise DefinitionError(msg)

        chain: Chain = _parse_template(cls)
        cls.__chain__ = chain
        _validate_template(cls)

        # Go through all bases to get the regex builder
        regex_builders = (c.get("__regex_builder__") for c in contents)
        regex_builder_cls = next(d for d in regex_builders if d is not None)

        if not isinstance(regex_builder_cls, type) or not issubclass(
            regex_builder_cls, RegexBuilder
        ):
            msg = (
                f"{name}: __regex_builder__ must be of type {RegexBuilder.__name__}, "
                f"got {type(regex_builder_cls).__name__!r}"
            )
            raise DefinitionError(msg)

        cls.__regex__ = cls.__chain__.to_regex(regex_builder_cls())

        return cls


@dataclass_transform(field_specifiers=(string, integer, choice, custom_token, model))
class TemplateModel(metaclass=TemplateModelMeta):
    r"""Base class for all declarative template models.

    Subclass to declare a typed, bidirectional string template:

    class AssetResult(TemplateModel):
        type: str = StrToken("[a-zA-Z]+")
        code: str = StrToken("\w+")
        __template__ = "{asset_type}_{code}"

    Parse:

        result = AssetResult.parse("chr_toto")
        result.type   # "chr"
        result.code   # "toto"

    Format:

        str(result)   # "chr_toto"
    """

    # Populated by metaclass
    __dataclass_transform__: ClassVar[dict[str, Any]]
    __delimiter__ = Delimiter.CURLY
    __regex_builder__: type[RegexBuilder] = RegexBuilder
    __bound_tokens__: dict[str, BoundToken[Any]]
    __template__: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the template model with given kwargs arguments."""
        fields = list(self.__bound_tokens__)

        if len(args) > len(fields):
            msg = f"Expected {len(args)} arguments, got {len(fields)}"
            raise TypeError(msg)

        all_kwargs: dict[str, Any] = {}

        for i, value in enumerate(args):
            name = fields[i]
            all_kwargs[name] = value

        for name, value in kwargs.items():
            if name in all_kwargs:
                msg = f"Argument '{name}' provided more than once"
                raise TypeError(msg)
            all_kwargs[name] = value

        for name in fields:
            if name in all_kwargs:
                setattr(self, name, all_kwargs[name])
            else:
                msg = f"Missing required token: '{name}'"
                raise TypeError(msg)

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return the parsed object of this model from the given raw string."""
        raise NotImplementedError
