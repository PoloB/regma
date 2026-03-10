"""
templex.core
~~~~~~~~~~~~
Chainable ABC, Separator, and Chain composite.

``to_regex()`` accepts an optional ``seen`` set that tracks which named
capture groups have already been emitted.  On first occurrence a full named
group is produced; on subsequent occurrences a backreference ``(?P=name)``
is produced instead, enforcing consistency at the regex level.

Design note — ``>>`` operators
-------------------------------
``__rshift__`` and ``__rrshift__`` need :func:`templex._coerce._as_chainable`,
which in turn needs :class:`Chainable` and :class:`~templex.slot.Slot`.
To avoid a circular import the operators are defined here but delegate to
:func:`~templex._coerce._as_chainable`, which is injected by
:mod:`templex._coerce` after both modules are fully loaded.  The injection
happens at the bottom of :mod:`templex._coerce` via plain attribute assignment
and is transparent to all callers.
"""

from __future__ import annotations

import abc
import re
from typing import Any, Generic, Protocol, Self, TypeVar


class RegexBuilder:
    def __init__(self) -> None:
        self._attribute_stack: list[str] = []
        self._seen_tokens: set[str] = set()

    def build(self, attribute_name: str, templatable: Templatable) -> str:
        """Build the regex for the given token name and pattern."""
        attribute_name = attribute_name.replace(".", "__")
        token_name = "__".join([*self._attribute_stack, attribute_name])
        if token_name in self._seen_tokens:
            return rf"(?P={token_name})"

        self._seen_tokens.add(token_name)

        # Build the regex
        self._attribute_stack.append(attribute_name)
        regex = templatable.to_regex(self)
        self._attribute_stack.pop()
        return rf"(?P<{token_name}>{regex})"


class Templatable(abc.ABC):
    """Anything that can participate in a template chain."""

    @abc.abstractmethod
    def to_regex(self, builder: RegexBuilder) -> str:
        """Return a regex fragment for this element."""

    @abc.abstractmethod
    def to_chain(self) -> Chain:
        """Return the templatable as a chain of Templatables."""

    # @abc.abstractmethod
    # def format(self, values: dict[str, Any]) -> str:
    #     """Return the formatted string for the given values dict."""


class Chain(Templatable):
    """Ordered sequence of :class:`Chainable` nodes.  Itself :class:`Chainable`."""

    def __init__(self, nodes: list[Templatable]) -> None:
        self.__nodes = nodes

    @property
    def nodes(self) -> list[Templatable]:
        return self.__nodes

    def to_regex(self, builder: RegexBuilder) -> str:
        return "".join(n.to_regex(builder) for n in self.__nodes)

    def format(self, values: dict[str, Any]) -> str:
        return "".join(n.format(values) for n in self.__nodes)

    def to_chain(self) -> Chain:
        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__nodes!r})"


class Separator(Templatable):
    """A literal string fragment in a chain."""

    def __init__(self, value: str) -> None:
        self.value = value

    def to_regex(self, builder: RegexBuilder) -> str:
        return re.escape(self.value)

    def to_chain(self) -> Chain:
        return Chain([self])

    def format(self, values: dict[str, Any]) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value!r})"


T_token = TypeVar("T_token", bound=Any)


class AbstractToken(Generic[T_token], Templatable, abc.ABC):
    """Abstract base for all atomic tokens."""

    # @abc.abstractmethod
    # def parse(self, raw: str) -> T_token: ...

    @abc.abstractmethod
    def format(self, value: T_token) -> str: ...

    def to_chain(self) -> Chain:
        return Chain([self])


class TokenReference(Templatable):
    def __init__(self, attribute_name: str, target_token: AbstractToken[Any]) -> None:
        self.__name = attribute_name
        self._token = target_token

    @property
    def target(self) -> AbstractToken[Any]:
        return self._token

    def to_regex(self, builder: RegexBuilder) -> str:
        regex = builder.build(self.__name, self._token)
        return regex

    def format(self, values: dict[str, Any]) -> str:
        return self._token.format(values)

    def to_chain(self) -> Chain:
        return Chain([self])

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.__name!r}, target={self.target!r})"


class BoundToken(Generic[T_token], Templatable):
    def __init__(self, name: str, token: AbstractToken[T_token]) -> None:
        self._name = name
        self._token = token

    def to_chain(self) -> Chain:
        return Chain([self])

    def to_regex(self, builder: RegexBuilder) -> str:
        return builder.build(self._name, self._token.to_regex(builder))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._name!r}, {self._token!r})"


class TemplateModelProtocol(Protocol):

    __chain__: Chain

    @classmethod
    def parse(cls, raw: str) -> Self: ...

    def format(self) -> str: ...


T_token_model = TypeVar("T_token_model", bound=TemplateModelProtocol)


class ModelToken(AbstractToken[T_token_model]):
    def __init__(self, model_cls: type[T_token_model]) -> None:
        self._model = model_cls

    def format(self, value: T_token_model) -> str:
        return value.format()

    def to_regex(self, builder: RegexBuilder) -> str:
        return self._model.__chain__.to_regex(builder)

    def __getattr__(self, item) -> Any:
        return getattr(self._model, item)
