"""Module providing validation routines for regma templates."""

from __future__ import annotations

import collections
import dataclasses
import enum
import sys
from typing import TYPE_CHECKING
from typing import TypeVar

import greenery
from typing_extensions import Self  # noqa: UP035

from regma.error import ValidityError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from regma import Model
    from regma.core import Chain
    from regma.core import FieldReference
    from regma.core import FieldSep
    from regma.template import BoundTemplate


def _left_reminder(fsm: greenery.Fsm) -> greenery.Fsm:
    """Return the left reminder of the given fsm.

    The left reminder are all the words constructed from an initial state of
    the fsm that are lead to an initial state of the fsm.

    For example, the fsm of the regex b*a is b*
    """
    alphabet = fsm.alphabet

    initial = frozenset(fsm.finals)

    # Find every possible way to reach the current state-set
    # using this symbol.
    def follow(
        current: frozenset[int], symbol: greenery.Charclass
    ) -> frozenset[greenery.fsm.StateType]:
        return frozenset(
            [
                prev
                for prev in fsm.map
                for state in current
                if fsm.map[prev][symbol] == state
            ]
        )

    # A state-set is final if the initial state is in it.
    def final(state: frozenset[int]) -> bool:
        return bool(fsm.finals.intersection(state))

    return greenery.fsm.crawl(alphabet, initial, final, follow).reduce()


def _right_reminder(fsm: greenery.Fsm) -> greenery.Fsm:
    """Return the right reminder of the given fsm.

    The right reminder are all the words constructed from a final state of
    the fsm that are still a word of the fsm.

    For example, the fsm of the regex ab* is b*
    """
    return _left_reminder(fsm).reversed()


def _trim_right_reminder(fsm: greenery.Fsm) -> greenery.Fsm:
    """Return the fsm that removes all the possible right reminders of the given fsm.

    For example, trimmed right reminder of abc* is ab.
    """
    alphabet = fsm.alphabet
    finals = fsm.finals

    # Define an ending state
    end_state = len(fsm.states)

    # Find every possible way to reach the current state-set
    # using this symbol.
    def follow(current: int, symbol: greenery.Charclass) -> int:
        if current in finals:
            return end_state
        if current == end_state:
            return end_state
        return fsm.map[current][symbol]

    # A state-set is final if the initial state is in it.
    def final(state: int) -> bool:
        return state in finals

    return greenery.fsm.crawl(alphabet, fsm.initial, final, follow).reduce()


def _trim_left_reminder(fsm: greenery.Fsm) -> greenery.Fsm:
    """Return the fsm that removes all the possible left reminders of the given fsm.

    For example, trimmed right reminder of a*bc is bc.
    """
    alphabet = fsm.alphabet

    initial_state = fsm.initial

    ending_state = frozenset([len(fsm.states)])

    # Find every possible way to reach the current state-set
    # using this symbol.
    def follow(
        current: frozenset[greenery.fsm.StateType], symbol: greenery.fsm.AlphaType
    ) -> frozenset[greenery.fsm.StateType]:

        if initial_state in current:
            return ending_state

        if current == ending_state:
            return ending_state

        return frozenset(
            [
                prev
                for prev in fsm.map
                for state in current
                if fsm.map[prev][symbol] == state
            ]
        )

    # A state-set is final if the initial state is in it.
    def final(state: frozenset[greenery.fsm.StateType]) -> bool:
        return fsm.initial in state

    return greenery.fsm.crawl(alphabet, frozenset(fsm.finals), final, follow).reduce()


def get_flat_charclass(charclass: greenery.Charclass) -> greenery.Charclass:
    """Return a random char from the given class."""
    if not charclass.negated:
        return charclass

    # Construct a flat charclass from negated
    minimum = 0
    maximum = sys.maxunicode

    if not charclass.ord_ranges:
        return greenery.Charclass(((chr(minimum), chr(maximum)),))

    # Assume the ranges are ordered
    ranges: list[tuple[str, str]] = []
    for char_range in charclass.ord_ranges:
        ranges.append((chr(minimum), chr(char_range[0] - 1)))
        minimum = char_range[1] + 1

    ranges.append((chr(charclass.ord_ranges[-1][1] + 1), chr(maximum)))

    return greenery.Charclass(tuple(ranges))


def _get_shortest_path(fsm: greenery.Fsm) -> list[greenery.Charclass]:

    visited = {fsm.initial}

    def _get_current_level_path(
        current_level: list[tuple[int, list[greenery.Charclass]]],
    ) -> list[greenery.Charclass]:
        next_level = []
        for state, path in current_level:
            if state in fsm.finals:
                return path
            syms_by_next_state: dict[int, list[greenery.Charclass]] = (
                collections.defaultdict(list)
            )
            identical_state = -1
            for sym, next_state in fsm.map[state].items():
                if next_state in visited and next_state != identical_state:
                    continue
                syms_by_next_state[next_state].append(sym)
                identical_state = next_state
                visited.add(next_state)
            for next_state, syms in syms_by_next_state.items():
                combined_charclass = greenery.Charclass()
                for sym in syms:
                    combined_charclass = combined_charclass.union(sym)
                next_level.append((next_state, [*path, combined_charclass]))
        return _get_current_level_path(next_level)

    return _get_current_level_path([(fsm.initial, [])])


def _generate_example(fsm: greenery.Fsm) -> str:
    """Generate an example of string accepted by the given fsm."""
    charclass_path = _get_shortest_path(fsm)
    return "".join(
        next(get_flat_charclass(char).get_chars(), "") for char in charclass_path
    )


@dataclasses.dataclass(frozen=True)
class FsmFieldNode:
    """A finite state machine object corresponding to a template field."""

    field_sep: FieldSep
    fsm: greenery.Fsm

    @property
    def field_name(self) -> str:
        """Return the field name."""
        return self.field_sep.field.name

    @property
    def separator(self) -> str:
        """Return the value of the separator."""
        return self.field_sep.separator.value


@dataclasses.dataclass(frozen=True)
class TokenExample:
    """An example of a token."""

    node: FsmFieldNode
    example: str

    def get_display_string(self) -> str:
        """Return the string representation of the example."""
        return f"{self.node.field_name}={self.example}"


@dataclasses.dataclass(frozen=True)
class CollidingExample:
    """An example of colliding tokens."""

    combined_example: str
    option1: tuple[TokenExample, TokenExample]
    option2: tuple[TokenExample, TokenExample]

    def get_display_string(self) -> str:
        """Return the string representation of the example."""
        left1 = self.option1[0]
        right1 = self.option1[1]
        node1 = left1.node
        return (
            f"{{{node1.field_name}}}{node1.separator}{{{right1.node.field_name}}} "
            f"gives '{self.combined_example}' with both "
            f"({self.option1[0].get_display_string()}, "
            f"{self.option1[1].get_display_string()}) "
            f"and "
            f"({self.option2[0].get_display_string()}, "
            f"{self.option2[1].get_display_string()}) "
        )


@dataclasses.dataclass
class FsmFrontierDecomposition:
    """Decomposition of the frontier between two FSMs."""

    frontier: FsmFrontier
    suffix: greenery.Fsm
    prefix: greenery.Fsm
    intersection: greenery.Fsm

    def is_colliding(self) -> bool:
        """Return whether the two FSMs are colliding with each other."""
        return not self.intersection.empty()

    def generate_colliding_example(self) -> CollidingExample:
        """Generate a colliding example."""
        left = self.frontier.left
        right = self.frontier.right
        trim_prefix = _trim_right_reminder(left.fsm)
        trim_suffix = _trim_left_reminder(right.fsm)
        left_example1 = _generate_example(trim_prefix + self.intersection)
        right_example1 = _generate_example(trim_suffix)
        left_example2 = _generate_example(trim_prefix).removesuffix(left.separator)
        right_example2 = _generate_example(self.intersection + trim_suffix)

        return CollidingExample(
            left_example1 + right_example1,
            (
                TokenExample(
                    self.frontier.left, left_example1.removesuffix(left.separator)
                ),
                TokenExample(self.frontier.right, right_example1),
            ),
            (
                TokenExample(self.frontier.left, left_example2),
                TokenExample(self.frontier.right, right_example2),
            ),
        )


@dataclasses.dataclass(frozen=True)
class FsmFrontier:
    """Define a frontier between two FSMs."""

    left: FsmFieldNode
    right: FsmFieldNode

    def decompose(self) -> FsmFrontierDecomposition:
        """Decompose the FSM frontier."""
        fsm1_suffix = _right_reminder(self.left.fsm)
        fsm2_prefix = _left_reminder(self.right.fsm)
        intersection = fsm1_suffix.intersection(fsm2_prefix) - greenery.EPSILON
        return FsmFrontierDecomposition(self, fsm1_suffix, fsm2_prefix, intersection)


class CollisionResult:
    """Result of collision computation."""

    def __init__(self, token_decompositions: list[FsmFrontierDecomposition]) -> None:
        """Initialize a CollisionResult object."""
        self._token_decompositions = token_decompositions

    def has_collision(self) -> bool:
        """Return whether one or more collision exists."""
        # Check each decomposition
        return any(decomp.is_colliding() for decomp in self._token_decompositions)

    def get_colliding_frontiers(self) -> list[FsmFrontier]:
        """Return the list of frontiers colliding with each other."""
        return [
            decomp.frontier
            for decomp in self._token_decompositions
            if decomp.is_colliding()
        ]

    def generate_examples(self) -> Iterator[CollidingExample]:
        """Generate an example of a collision."""
        for decomp in self._token_decompositions:
            if decomp.is_colliding():
                yield decomp.generate_colliding_example()


def compute_collision(chain: Chain, fsm_builder: FsmBuilder) -> CollisionResult:
    """Compute the collision within the fsm chain."""
    field_seps = list(chain.iter_field_seps())

    if not field_seps:
        return CollisionResult([])

    # Create frontiers between FieldReference
    # We skip any frontier that has a static fsm node
    frontier_nodes: list[tuple[FsmFieldNode, FsmFieldNode]] = []

    for k, left_field_sep in enumerate(field_seps[:-1]):
        right_field_sep = field_seps[k + 1]

        if chain.is_field_reused(left_field_sep.field) or chain.is_field_reused(
            right_field_sep.field
        ):
            continue

        # Compute the fsm of the field only to get better cache hits
        left_field_fsm = fsm_builder.build_fsm(left_field_sep.field.to_regex())
        left_sep_fsm = fsm_builder.build_fsm(left_field_sep.separator.to_regex())
        right_field_fsm = fsm_builder.build_fsm(right_field_sep.field.to_regex())
        right_sep_fsm = fsm_builder.build_fsm(right_field_sep.separator.to_regex())
        left_node = FsmFieldNode(left_field_sep, left_field_fsm + left_sep_fsm)
        right_node = FsmFieldNode(right_field_sep, right_field_fsm + right_sep_fsm)
        frontier_nodes.append((left_node, right_node))

    frontier_decompositions: list[FsmFrontierDecomposition] = []

    for fsm1, fsm2 in frontier_nodes:
        frontier_decompositions.append(FsmFrontier(fsm1, fsm2).decompose())

    return CollisionResult(frontier_decompositions)


class FsmRegexCache:
    """A cache of fsm for regex."""

    def __init__(self) -> None:
        """Initialize the cache."""
        self._fsm_by_regex: dict[str, greenery.Fsm] = {}

    def get_fsm(self, regex: str) -> greenery.Fsm | None:
        """Return the fsm for the given regex."""
        return self._fsm_by_regex.get(regex)

    def push_fsm(self, regex: str, fsm: greenery.Fsm) -> None:
        """Push the fsm for the given regex."""
        self._fsm_by_regex[regex] = fsm


class FsmBuilder:
    """Builder of FSM from regex.

    Has internal cache to avoid recomputing FSM from the same regex node multiple times.
    """

    def __init__(self, cache: FsmRegexCache) -> None:
        """Initialize a FSMNodeBuilder object."""
        self._cache = cache

    def build_fsm(self, regex: str) -> greenery.Fsm:
        """Build an FSM node from TemplateNode."""
        fsm = self._cache.get_fsm(regex)
        if fsm is not None:
            return fsm

        # Build the fsm
        fsm = greenery.parse(regex).to_fsm()
        self._cache.push_fsm(regex, fsm)
        return fsm


T_mod = TypeVar("T_mod", bound="Model")


def validate_template_has_no_collision(
    fsm_builder: FsmBuilder, template: BoundTemplate[T_mod]
) -> None:
    """Raise ValidityError if template has collision."""
    collision = compute_collision(template.chain, fsm_builder)
    if not collision.has_collision():
        return

    colliding_frontiers = collision.get_colliding_frontiers()

    token_pairs = ", ".join(
        [f"({f.left.field_name}, {f.right.field_name})" for f in colliding_frontiers]
    )

    examples = ", ".join(
        [example.get_display_string() for example in collision.generate_examples()]
    )

    error_message = (
        f"Template {template} has possible collision on following token pairs: "
        f"{token_pairs}. "
        f"Example strings: {examples}"
    )
    raise ValidityError(error_message)


def validate_template_has_no_empty_token(
    fsm_builder: FsmBuilder, template: BoundTemplate[T_mod]
) -> None:
    """Validate the template model."""
    empty_fields: list[FieldReference] = []
    for field_sep in template.chain.iter_field_seps():
        field_fsm = fsm_builder.build_fsm(field_sep.field.to_regex())
        if field_fsm.initial in field_fsm.finals:
            empty_fields.append(field_sep.field)

    if not empty_fields:
        return

    fields_names = ", ".join([field.name for field in empty_fields])
    error_message = f"Template {template} has fields which can be empty: {fields_names}"
    raise ValidityError(error_message)


class FsmValidationFlag(enum.Flag):
    """Type of Finite state machine available validation."""

    EMPTY_TOKEN = enum.auto()
    COLLISION = enum.auto()

    @classmethod
    def all(cls) -> Self:
        """Return flags to request all validations."""
        result = cls(0)
        for member in cls:
            result |= member
        return result


def validate(
    fsm_builder: FsmBuilder, template: BoundTemplate[T_mod], flag: FsmValidationFlag
) -> None:
    """Validate the given template with respect to the given flags."""
    if flag & FsmValidationFlag.EMPTY_TOKEN:
        validate_template_has_no_empty_token(fsm_builder, template)

    if flag & FsmValidationFlag.COLLISION:
        validate_template_has_no_collision(fsm_builder, template)
