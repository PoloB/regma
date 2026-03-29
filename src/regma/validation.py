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

import collections
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

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


def _right_quotient(fsm_b: greenery.Fsm, fsm_a: greenery.Fsm) -> greenery.Fsm:
    """Compute the right quotient B / A = { s : ∃ u ∈ L(A), u·s ∈ L(B) }.

    This is the set of strings that can *complete* a string in L(A) to
    reach a string in L(B).

    When A = B this gives the self-overlap suffixes — strings s such that
    some u ∈ L(A) can be extended by s and still land in L(A).  These are
    exactly the "dangling suffixes" of the Sardinas-Patterson algorithm.

    We use ``greenery.fsm.unify_alphabets([fsm_a, fsm_b])`` — a public
    module-level function — to repartition both FSMs onto a common
    alphabet.  After unification every charclass in A's transition map
    corresponds exactly to a charclass in B's transition map, so we can
    walk both state graphs in parallel via a BFS over ``(state_a, state_b)``
    pairs without any character-level guessing.

    Whenever A is in an accepting state during the BFS, B's current state
    is recorded as a valid "quotient start state" — i.e. B can accept
    strings from there.  The quotient FSM is then built as a new Fsm
    with those start states encoded via the union operator ``|``.

    Args:
        fsm_b : The language we want suffixes of.
        fsm_a : The language whose strings are the consumed prefixes.

    Returns:
        An FSM accepting exactly B / A.
    """
    # Unify alphabets so both FSMs share the same charclass partition.
    # After this, every transition charclass in fsm_a also appears in
    # fsm_b and vice versa — the BFS can walk both maps in lockstep.
    fsm_a, fsm_b = greenery.fsm.unify_alphabets([fsm_a, fsm_b])

    # Product BFS over (state_a, state_b) pairs.
    # Whenever state_a is an A-accepting state, record state_b as a
    # valid initial state for the quotient FSM.
    visited: set[tuple[int, int]] = set()
    queue: collections.deque[tuple[int, int]] = collections.deque()

    start = (fsm_a.initial, fsm_b.initial)
    queue.append(start)
    visited.add(start)

    quotient_initials: set[int] = set()

    # ε ∈ L(A) → B's initial state is immediately a quotient start
    if fsm_a.initial in fsm_a.finals:
        quotient_initials.add(fsm_b.initial)

    while queue:
        state_a, state_b = queue.popleft()
        trans_a = fsm_a.map.get(state_a, {})
        trans_b = fsm_b.map.get(state_b, {})

        # After unify_alphabets, both maps share the same charclasses
        for charclass in trans_a:
            next_a = trans_a[charclass]
            next_b = trans_b.get(charclass)  # None if b has no transition here
            if next_b is None:
                continue
            pair = (next_a, next_b)
            if pair not in visited:
                visited.add(pair)
                queue.append(pair)
            if next_a in fsm_a.finals:
                quotient_initials.add(next_b)

    if not quotient_initials:
        # No string in L(A) drives B to any reachable state → quotient empty
        return greenery.Fsm(
            alphabet=fsm_b.alphabet,
            states=frozenset({0}),
            initial=0,
            finals=frozenset(),
            map={},
        )

    # Build quotient FSM as the union of copies of fsm_b, one per
    # quotient initial state.  Each copy is fsm_b with its initial
    # state replaced — greenery's Fsm is a frozen dataclass so we
    # reconstruct it.  The union (|) handles alphabet compatibility
    # automatically since all copies share the same alphabet.
    def _with_initial(fsm: greenery.Fsm, initial: int) -> greenery.Fsm:
        return greenery.Fsm(
            alphabet=fsm.alphabet,
            states=fsm.states,
            initial=initial,
            finals=fsm.finals,
            map=fsm.map,
        )

    parts = [_with_initial(fsm_b, q) for q in quotient_initials]
    result = parts[0]
    for part in parts[1:]:
        result = result | part
    return result


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
        c1 = _right_quotient(prefix_fsm, prefix_fsm)
        c1_nonempty = c1 & sigma_plus

        if c1_nonempty.empty():
            # Prefix is suffix-free at this boundary — unambiguous
            continue

        # Check: can any string in C₁ start a valid suffix match?
        # right_quotient(suffix_fsm, c1_nonempty) = { t : ∃ s ∈ C₁, s·t ∈ L(suffix) }
        # If non-empty: u·s ∈ prefix (long split) AND s·t ∈ suffix (short split's suffix)
        # where u ∈ prefix AND u·s ∈ prefix — genuine ambiguity.
        reachable = _right_quotient(suffix_fsm, c1_nonempty)

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
    u_language = _right_quotient(prefix_fsm, s_literal_fsm)

    u = "" if u_language.accepts("") else next(u_language.strings([]), "")
    return u + s + t
