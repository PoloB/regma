"""Module providing validation routines for regma templates.

The module provide the following functions
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
    """Decomposition of the frontier between two FSMs."""

    frontier: FsmFieldFrontier
    suffix: greenery.Fsm
    prefix: greenery.Fsm
    intersection: greenery.Fsm

    def is_colliding(self) -> bool:
        """Return whether the two FSMs are colliding with each other."""
        return not self.intersection.empty()

    def generate_colliding_example(self) -> str:
        """Generate a colliding example."""
        trim_prefix = _trim_right_reminder(self.frontier.left.fsm)
        trim_suffix = _trim_left_reminder(self.frontier.right.fsm)
        ambigious_fsm = trim_prefix + self.intersection + trim_suffix
        return next(ambigious_fsm.strings([]), "")


@dataclasses.dataclass(frozen=True)
class FsmFieldFrontier:
    """Define a frontier between two FSMs."""

    left: FsmNode
    right: FsmNode

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
        return all(not decomp.is_colliding() for decomp in self._token_decompositions)

    def generate_examples(self) -> Iterator[str]:
        """Generate an example of a collision."""
        for decomp in self._token_decompositions:
            if decomp.is_colliding():
                yield decomp.generate_colliding_example()


class FsmNodeBuilder:
    """Builder of FSM node from TemplateNode.

    Has an internal cache to avoid recomputing FSM from the same template node multiple
    times.
    """

    def __init__(self) -> None:
        """Initialize a FSMNodeBuilder object."""
        self._fsm_by_template_node: dict[TemplateNode, FsmNode] = {}
        self._engine = ValidationRegexEngine()

    def build_node_fsm(self, node: TemplateNode) -> FsmNode:
        """Build an FSM node from TemplateNode."""
        if node in self._fsm_by_template_node:
            return self._fsm_by_template_node[node]

        # Build the regex and the fsm
        regex = self._engine.build("", node)
        fsm = greenery.parse(regex).to_fsm()
        fsm_node = FsmNode(node, fsm)
        self._fsm_by_template_node[node] = fsm_node
        return fsm_node


class FsmChain:
    """A chain of finite state machines."""

    @classmethod
    def from_chain(cls, chain: Chain, builder: FsmNodeBuilder | None = None) -> FsmChain:
        """Create a FsmChain from a template chain."""
        if builder is None:
            builder = FsmNodeBuilder()

        nodes = chain.nodes

        fsm_nodes: list[FsmNode] = []

        for node in nodes:
            fsm_node = builder.build_node_fsm(node)
            fsm_nodes.append(fsm_node)

        return cls(fsm_nodes)

    def __init__(self, fsm_nodes: list[FsmNode]) -> None:
        """Initialize the chain of fsms."""
        self._nodes = fsm_nodes

    def compute_collision(self) -> CollisionResult:
        """Compute the collision within the fsm chain."""
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
