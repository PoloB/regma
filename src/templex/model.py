"""Template model implementation."""

from __future__ import annotations

import enum
import re
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Self
from typing import TypeVar

from typing_extensions import dataclass_transform
from typing_extensions import override

from templex import TemplateNode
from templex.core import AbstractToken
from templex.core import Chain
from templex.core import RegexBuilder
from templex.core import T_token
from templex.error import DefinitionError
from templex.template_parser import parse_template
from templex.token import choice
from templex.token import custom_token
from templex.token import integer
from templex.token import string


class Delimiter(enum.Enum):
    """Token delimiter styles for string templates.

    Each variant carries its open/close characters and can compile
    its own token regex — template_parser.py stays delimiter-agnostic.

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
        ident = r"[A-Za-z_][A-Za-z0-9_]*"
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

    @override
    def to_chain(self) -> Chain:
        return Chain([self])

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return builder.build(self._name, self._token)


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

        if TemplateModel.__name__ not in {b.__name__ for b in bases}:
            msg = f"{name}: must be subclass of {TemplateModel.__name__}"
            raise DefinitionError(msg)

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

        chain: Chain = parse_template(cls)
        cls.__chain__ = chain

        # Go through all bases to get the regex builder
        regex_builders = (c.get("__regex_builder__") for c in contents)
        regex_builder = next(d for d in regex_builders if d is not None)

        if not isinstance(regex_builder, RegexBuilder):
            msg = (
                f"{name}: __regex_builder__ must be a {RegexBuilder.__name__} instance, "
                f"got {type(regex_builder).__name__!r}"
            )
            raise DefinitionError(msg)

        cls.__regex__ = cls.__chain__.to_regex(regex_builder)

        return cls


T_token_model = TypeVar("T_token_model", bound="TemplateModel")


class ModelToken(AbstractToken[T_token_model]):
    """A template model wrapped as a token."""

    def __init__(self, model_cls: type[T_token_model]) -> None:
        """Initialize the model token."""
        self._model = model_cls

    @override
    def to_regex(self, builder: RegexBuilder) -> str:
        return self._model.__chain__.to_regex(builder)

    # @override
    # def format(self, value: T_token) -> str:
    #     raise NotImplementedError

    @override
    def extract_value(self, raw: str) -> T_token_model:
        return self._model.parse(raw)

    def __getattr__(self, item: str) -> Any:  # noqa: ANN401
        """Return the attribute of the underlying model class."""
        return getattr(self._model, item)


def model(model_cls: type[T_token_model]) -> Any:  # noqa: ANN401
    """Return a token wrapping an existing template model class."""
    return ModelToken(model_cls)


@dataclass_transform(
    field_specifiers=(
        string,
        integer,
        choice,
        custom_token,
        ModelToken,
    ),
)
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
    __regex_builder__ = RegexBuilder()
    __bound_tokens__: dict[str, BoundToken[Any]]
    __template__: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the template model with given kwargs arguments."""
        fields = list(self.__bound_tokens__)

        for i, value in enumerate(args):
            name = fields[i]
            kwargs[name] = value

        for name in fields:
            if name in kwargs:
                setattr(self, name, kwargs[name])
            else:
                msg = f"Missing required token: '{name}'"
                raise TypeError(msg)

    @classmethod
    def construct_regex(cls, builder: RegexBuilder) -> str:
        """Construct the regex of this module using the given builder."""
        return cls.__chain__.to_regex(builder)

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return the parsed object of this model from the given raw string."""
        raise NotImplementedError
