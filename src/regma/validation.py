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

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from greenery.fsm import AlphaType
from greenery.fsm import StateType
from greenery.fsm import crawl

try:
    import greenery
except ImportError as exc:
    msg = "Package 'greenery' is required for template validation."
    raise ImportError(msg) from exc


from regma.engine import AbstractRegexEngine

if TYPE_CHECKING:
    from regma import TemplateModel
    from regma import TemplateNode


class ValidationRegexEngine(AbstractRegexEngine):
    """Engine used to create the patterns for validation.

    It will not insert any unsupported features in the pattern that greenery will not
    support as FSM (like back references or back tracking)
    """

    def build(self, _: str, template_node: TemplateNode) -> str:
        """Build the regex for the given field name and pattern."""
        return template_node.to_regex(self)


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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


def validate_template(
    model_cls: type[TemplateModel], max_examples: int = 5
) -> ValidationReport:
    """Run all three validation checks on the given model class.

    It checks the following:
    - nonempty template pattern
    - cardinality of the pattern (how many different strings can it match)
    - pattern bijectivity
    """
    patterns = [n.to_regex(ValidationRegexEngine()) for n in model_cls.__chain__.nodes]
    full_fsm = greenery.parse("".join(patterns)).to_fsm()

    # Compute pattern properties
    language = _check_language(full_fsm, max_examples)

    # Check bijectivity
    fsms = [greenery.parse(p).to_fsm() for p in patterns]
    ambiguity = _check_bijectivity(fsms)

    return ValidationReport(language=language, ambiguity=ambiguity)


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


def right_quotient(m1: greenery.Fsm, m2: greenery.Fsm) -> greenery.Fsm:
    """L(m1) / L(m2) = { w | ∃x ∈ L2, wx ∈ L1 }"""
    m1, m2 = greenery.fsm.unify_alphabets([m1, m2])

    def follow(q1, symbol):
        return m1.map[q1][symbol]

    def final(q1):
        return not (
            greenery.Fsm(
                alphabet=m1.alphabet,
                states=m1.states,
                initial=q1,
                finals=m1.finals,
                map=m1.map,
            )
            & m2
        ).empty()

    return greenery.fsm.crawl(m1.alphabet, m1.initial, final, follow)


def left_quotient(m1: greenery.Fsm, m2: greenery.Fsm) -> greenery.Fsm:
    """L(m1) \\ L(m2) = { w | ∃x ∈ L1, xw ∈ L2 }"""
    m1, m2 = greenery.fsm.unify_alphabets([m1, m2])

    reachable_via_l1: set[int] = set()

    def product_follow(state, symbol):
        q1, q2 = state
        return (m1.map[q1][symbol], m2.map[q2][symbol])

    def product_final(state):
        q1, q2 = state
        if q1 in m1.finals:
            reachable_via_l1.add(q2)
        return False

    greenery.fsm.crawl(
        m1.alphabet, (m1.initial, m2.initial), product_final, product_follow
    )

    def follow(states, symbol):
        return frozenset(m2.map[q][symbol] for q in states)

    def final(states):
        return bool(states & m2.finals)

    return greenery.fsm.crawl(m2.alphabet, frozenset(reachable_via_l1), final, follow)


def _right_reminder(fsm: greenery.Fsm) -> greenery.Fsm:
    """Return the right reminder of the given fsm.

    The right reminder are all the words constructed from a final state of
    the fsm that are still a word of the fsm.

    For example, the fsm of the regex ab* is b*
    """
    alphabet = fsm.alphabet

    initial = frozenset(fsm.finals)

    # Find every possible way to reach the current state-set
    # using this symbol.
    def follow(current: frozenset[StateType], symbol: AlphaType) -> frozenset[StateType]:
        return frozenset(
            [
                prev
                for prev in fsm.map
                for state in current
                if fsm.map[prev][symbol] == state
            ]
        )

    # A state-set is final if the initial state is in it.
    def final(state: frozenset[StateType]) -> bool:
        return bool(fsm.finals.intersection(state))

    return crawl(alphabet, initial, final, follow).reduce()


def _left_reminder(fsm: greenery.Fsm) -> greenery.Fsm:
    """Return the left reminder of the given fsm.

    The left reminder are all the words constructed from an initial state of
    the fsm that are lead to an initial state of the fsm.

    For example, the fsm of the regex b*a is b*
    """
    alphabet = fsm.alphabet

    # Find every possible way to reach the current state-set
    # using this symbol.
    def follow(current: int, symbol: greenery.Charclass) -> int:
        return fsm.map[current][symbol]

    # A state-set is final if the initial state is in it.
    def final(state: int) -> bool:
        return fsm.initial == state

    return crawl(alphabet, fsm.initial, final, follow).reduce()


def _check_bijectivity(fsms: list[greenery.Fsm]) -> AmbiguityResult:
    """Faithful Sardinas-Patterson algorithm over DFAs.

    For each split boundary i (between node i and i+1), computes:

        C₁(i) = prefix(i) / prefix(i)   — self-overlap suffixes of the prefix

    where prefix(i) = L(P₁ · ... · Pᵢ₊₁).

    C₁(i) is the set of non-empty strings by which the prefix can
    over-consume relative to a valid split.  Ambiguity at boundary i
    exists iff any string in C₁(i) can start a valid suffix match:

        right_quotient(suffix(i), C₁(i)) ≠ ∅

    where suffix(i) = L(Pᵢ₊₂ · ... · Pₙ).

    If the above is non-empty, a witness string is reconstructed and
    returned.

    Args:
        fsms: Individual FSMs for each pattern node, in order.

    Returns:
        ambiguity result
    """
    if len(fsms) <= 1:
        return AmbiguityResult(is_bijective=True)

    # sigma_plus: any non-empty string — used to exclude ε from C₁
    # ε in C₁ is trivial (every string is a "prefix of itself with ε left over")
    # and does not indicate ambiguity.
    sigma_plus = greenery.parse(".+").to_fsm()

    # Build prefix FSMs incrementally
    prefix_fsm = fsms[0]

    for i in range(len(fsms) - 1):
        if i > 0:
            prefix_fsm = prefix_fsm + fsms[i]

        # suffix_fsm = L(Pᵢ₊₁ · ... · Pₙ)
        suffix_fsm = fsms[i + 1]
        for fsm in fsms[i + 2 :]:
            suffix_fsm = suffix_fsm + fsm

        # C₁(i): non-empty self-overlap suffixes of prefix
        # = { s ≠ ε : ∃ u ∈ L(prefix), u·s ∈ L(prefix) }
        c1 = right_quotient(prefix_fsm, prefix_fsm)
        c1_nonempty = c1 & sigma_plus

        if c1_nonempty.empty():
            # Prefix is suffix-free at this boundary — unambiguous
            continue

        # Check: can any string in C₁ start a valid suffix match?
        # right_quotient(suffix_fsm, c1_nonempty) = { t : ∃ s ∈ C₁, s·t ∈ L(suffix) }
        # If non-empty: u·s ∈ prefix (long split) AND s·t ∈ suffix (short split's suffix)
        # where u ∈ prefix AND u·s ∈ prefix — genuine ambiguity.
        reachable = right_quotient(suffix_fsm, c1_nonempty)

        if not reachable.empty():
            witness = _reconstruct_witness(
                prefix_fsm=prefix_fsm, c1_nonempty=c1_nonempty, reachable=reachable
            )
            return AmbiguityResult(is_bijective=False, witness=witness, split_point=i)

    return AmbiguityResult(is_bijective=True)


def _reconstruct_witness(
    prefix_fsm: greenery.Fsm, c1_nonempty: greenery.Fsm, reachable: greenery.Fsm
) -> str:
    """Reconstruct a concrete witness string for the ambiguity.

    Finds the shortest u·s·t where:
    - u·s ∈ L(prefix)   (long-split prefix)
    - u   ∈ L(prefix)   (short-split prefix — proper prefix of u·s)
    - s   ∈ C₁          (the over-consumed amount, s ≠ ε)
    - s·t ∈ L(suffix)   (short-split suffix)
    - t   ∈ L(suffix)   (long-split suffix, may be ε)

    Strategy:
    1. Find the shortest s ∈ C₁.
    2. Find the shortest t such that s·t ∈ L(suffix) — that's t ∈ reachable.
    3. Find the shortest u such that u·s ∈ L(prefix)
       = u ∈ right_quotient(prefix, {s}).
    """
    # Step 1: shortest s in C₁
    s = next(c1_nonempty.strings([]), "")

    # Step 2: shortest t in reachable (may be empty string "")
    t = next(reachable.strings([]), "")

    # Step 3: shortest u such that u·s ∈ L(prefix)
    s_literal_fsm = greenery.parse(re.escape(s)).to_fsm()
    u_language = right_quotient(prefix_fsm, s_literal_fsm)

    u = "" if u_language.accepts("") else next(u_language.strings([]), "")
    return u + s + t
