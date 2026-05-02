"""Formal validation of template bijectivity using finite automata.

Given a template composed of N pattern nodes, this module answers three
questions — all at class definition time, zero cost at parse/format time:

1. **Empty language** — does the template match *any* string at all?
   Formally: is L(P₁ · P₂ · ... · Pₙ) = ∅ ?

2. **Finite language** — does the template match only a bounded set of
   strings? Useful for documentation and exhaustive testing.

3. **Bijectivity** — is T⁻¹ ∘ T = id ?  i.e. does formatting then parsing
   always recover the original tokens?  Formally: does the concatenation
   L(P₁ · ... · Pₙ) have a unique factorization for every string in it?
   Detected via a generalization of the Sardinas-Patterson algorithm over
   finite automata.

All three checks use `greenery` (optional dependency) which represents
regular languages as DFAs and supports intersection, concatenation, union,
complement, emptiness, and string enumeration.

Requires: ``pip install greenery``
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from regma.core import FieldReference
from regma.core import Separator

try:
    import greenery
except ImportError as exc:
    msg = "Package 'greenery' is required for template validation."
    raise ImportError(msg) from exc


from regma.engine import AbstractRegexEngine

if TYPE_CHECKING:
    from collections.abc import Iterator

    from regma import TemplateNode
    from regma.core import Chain


class ValidationRegexEngine(AbstractRegexEngine):
    """Engine used to create the patterns for validation.

    It will not insert any unsupported features in the pattern that greenery will not
    support as FSM (like back references or back tracking)
    """

    def build(self, _: str, template_node: TemplateNode) -> str:
        """Build the regex for the given field name and pattern."""
        return template_node.to_regex(self)


@dataclasses.dataclass(frozen=True)
class LanguageProperties:
    """Properties of the full concatenated language L(P₁ · ... · Pₙ).

    Attributes:
    is_empty: True if no string can ever match the template.
    is_finite: True if only a bounded number of strings match.
    cardinality: Exact count of matching strings when finite, None when infinite.
    examples: A small sample of accepted strings (empty if language is empty).
    """

    is_finite: bool
    cardinality: int | None
    examples: set[str]


@dataclasses.dataclass(frozen=True)
class AmbiguityResult:
    """Result of the bijectivity check.

    Attributes:
    is_bijective: True if T⁻¹ ∘ T = id is guaranteed — every formatted string parses
        back to exactly the original tokens.
    witness: A concrete string that admits two different parses, when ``is_bijective``
        is False.  None when bijective.
    split_point: Index of the node *after* which the ambiguous split occurs,
        when ``is_bijective`` is False.  None when bijective.
    """

    is_bijective: bool
    witness: str | None = None
    split_point: int | None = None


@dataclasses.dataclass(frozen=True)
class ValidationReport:
    """Complete validation report for a template.

    Attributes:
    language: Properties of the full concatenated language.
    ambiguity: Result of the bijectivity check.
    """

    language: LanguageProperties
    ambiguity: AmbiguityResult

    def is_valid(self) -> bool:
        """Return whether the template is valid."""
        return self.ambiguity.is_bijective


def _check_language(full_fsm: greenery.Fsm, max_examples: int) -> LanguageProperties:
    """Compute emptiness, finiteness, cardinality, and example strings."""
    # Finiteness: len() raises OverflowError when infinite
    try:
        cardinality: int | None = len(full_fsm)
        is_finite = True
    except OverflowError:
        cardinality = None
        is_finite = False

    # Collect a small sample of accepted strings
    examples: set[str] = set()
    for s in full_fsm.strings([]):
        examples.add(s)
        if len(examples) >= max_examples:
            break

    return LanguageProperties(
        is_finite=is_finite, cardinality=cardinality, examples=examples
    )


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


@dataclasses.dataclass(frozen=True)
class FsmNode:
    """A finite state machine object corresponding to a template node."""

    node: TemplateNode
    fsm: greenery.Fsm


@dataclasses.dataclass
class FsmFrontierDecomposition:
    frontier: FsmFieldFrontier
    suffix: greenery.Fsm
    prefix: greenery.Fsm
    intersection: greenery.Fsm

    def is_colliding(self) -> bool:
        return not self.intersection.empty()

    def generate_example(self) -> str:
        trim_prefix = _trim_right_reminder(self.frontier.left.fsm)
        trim_suffix = _trim_left_reminder(self.frontier.right.fsm)
        ambigious_fsm = trim_prefix + self.intersection + trim_suffix
        return next(ambigious_fsm.strings([]), "")


class FsmFieldFrontier:
    def __init__(self, fsm_left: FsmNode, fsm_right: FsmNode):
        self._left = fsm_left
        self._right = fsm_right

    @property
    def left(self) -> FsmNode:
        return self._left

    @property
    def right(self) -> FsmNode:
        return self._right

    def decompose(self) -> FsmFrontierDecomposition:
        fsm1_suffix = _right_reminder(self._left.fsm)
        fsm2_prefix = _left_reminder(self._right.fsm)
        intersection = (fsm1_suffix.intersection(fsm2_prefix) - greenery.EPSILON)
        return FsmFrontierDecomposition(self, fsm1_suffix, fsm2_prefix, intersection)


class CollisionResult:
    def __init__(self, token_decompositions: list[FsmFrontierDecomposition]) -> None:
        self._token_decompositions = token_decompositions

    def is_valid(self) -> bool:
        # Check each decomposition
        return all(not decomp.is_colliding() for decomp in self._token_decompositions)

    def generate_examples(self) -> Iterator[str]:
        for decomp in self._token_decompositions:
            if decomp.is_colliding():
                yield decomp.generate_example()


class FsmChain:
    @classmethod
    def from_chain(
        cls, chain: Chain, engine: AbstractRegexEngine | None = None
    ) -> FsmChain:
        """Create a FsmChain from a template chain."""
        if engine is None:
            engine = ValidationRegexEngine()

        nodes = chain.nodes

        fsm_nodes: list[FsmNode] = []

        for node in nodes:
            regex = engine.build("", node)
            fsm = greenery.parse(regex).to_fsm()
            fsm_nodes.append(FsmNode(node, fsm))

        return cls(fsm_nodes)

    def __init__(self, fsm_nodes: list[FsmNode]) -> None:
        """Initialize the chain of fsms."""
        self._nodes = fsm_nodes

    def iter_fsm_nodes(self) -> Iterator[FsmNode]:
        """Iterate over the fsm tokens in the model."""
        yield from self._nodes

    def get_collision_result(self) -> CollisionResult:

        # Only keep field reference and separators
        nodes = list(self._nodes)
        if not nodes:
            return CollisionResult([])

        # Remove elements until we fall onto a FieldReference
        first_node = nodes[0]

        while not isinstance(first_node.node, FieldReference):
            nodes.pop(0)
            first_node = nodes[0]

        if not nodes:
            return CollisionResult([])

        last_node = nodes[-1]

        while not isinstance(last_node.node, FieldReference):
            nodes.pop(-1)
            last_node = nodes[-1]

        if not nodes:
            return CollisionResult([])

        current_node = nodes[0]
        current_fsm = current_node.fsm

        # Create frontiers between FieldReference
        frontier_nodes: list[tuple[FsmNode, FsmNode]] = []

        for node in nodes[1:]:
            if isinstance(node.node, Separator):
                current_fsm = current_fsm.concatenate(node.fsm)
                continue

            if isinstance(node.node, FieldReference):
                # Store the current fsm
                frontier_nodes.append((FsmNode(current_node.node, current_fsm), node))
                current_node = node
                current_fsm = current_node.fsm

        frontier_decompositions: list[FsmFrontierDecomposition] = []

        for fsm1, fsm2 in frontier_nodes:
            frontier_decompositions.append(FsmFieldFrontier(fsm1, fsm2).decompose())

        return CollisionResult(frontier_decompositions)
