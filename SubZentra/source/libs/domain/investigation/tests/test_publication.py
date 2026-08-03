"""The publication truth table.

Sixteen combinations, because a policy that decides autonomy is exactly the
kind of thing where "the obvious cases work" is not evidence. The interesting
failures are the combinations: a draft that converged *and* is confident but
whose evidence cannot be followed must not publish, and a reviewer must be
told everything that failed rather than the first thing.
"""

from __future__ import annotations

from itertools import product

import pytest

from zentra_domain_investigation import (
    PublicationCondition,
    evaluate_publication,
)

THRESHOLD = 0.7


def decide(
    *,
    converged: bool = True,
    confident: bool = True,
    evidenced: bool = True,
    uncontradicted: bool = True,
):
    """One knob per condition, so a test says what it is varying."""
    return evaluate_publication(
        converged=converged,
        confidence=0.91 if confident else 0.42,
        confidence_threshold=THRESHOLD,
        substantive_claims=2,
        resolvable_claims=2 if evidenced else 1,
        unresolved_contradictions=0 if uncontradicted else 1,
    )


def test_all_four_passing_is_the_only_way_to_publish() -> None:
    assert decide().publishes is True
    assert decide().failed == ()


@pytest.mark.parametrize(
    ("knob", "condition"),
    [
        ("converged", PublicationCondition.CONVERGED),
        ("confident", PublicationCondition.CONFIDENT),
        ("evidenced", PublicationCondition.EVIDENCED),
        ("uncontradicted", PublicationCondition.UNCONTRADICTED),
    ],
)
def test_any_single_failure_gates(knob: str, condition: PublicationCondition) -> None:
    decision = decide(**{knob: False})

    assert decision.publishes is False
    assert decision.requires_approval is True
    assert decision.failed == (condition,)


@pytest.mark.parametrize(
    ("converged", "confident", "evidenced", "uncontradicted"),
    list(product([True, False], repeat=4)),
)
def test_the_whole_truth_table(
    converged: bool,
    confident: bool,
    evidenced: bool,
    uncontradicted: bool,
) -> None:
    """Every combination, and the two properties that must hold across all of
    them: publish exactly when nothing failed, and report every failure."""
    decision = decide(
        converged=converged,
        confident=confident,
        evidenced=evidenced,
        uncontradicted=uncontradicted,
    )

    expected = {
        PublicationCondition.CONVERGED: converged,
        PublicationCondition.CONFIDENT: confident,
        PublicationCondition.EVIDENCED: evidenced,
        PublicationCondition.UNCONTRADICTED: uncontradicted,
    }
    assert set(decision.failed) == {c for c, ok in expected.items() if not ok}
    assert decision.publishes is all(expected.values())


def test_every_failure_is_reported_not_just_the_first() -> None:
    """A reviewer told only that confidence was low, when the evidence was
    also unreachable, would approve on a false picture of what is wrong."""
    decision = decide(confident=False, evidenced=False, uncontradicted=False)

    assert set(decision.failed) == {
        PublicationCondition.CONFIDENT,
        PublicationCondition.EVIDENCED,
        PublicationCondition.UNCONTRADICTED,
    }


def test_failures_are_reported_in_a_stable_order() -> None:
    """The same draft must not produce two different-looking reasons, or
    Replay and the UI will disagree about what happened."""
    twice = [decide(converged=False, evidenced=False).failed for _ in range(2)]

    assert twice[0] == twice[1]
    assert twice[0] == (
        PublicationCondition.CONVERGED,
        PublicationCondition.EVIDENCED,
    )


def test_an_unknown_confidence_gates_rather_than_passing() -> None:
    """The score being unknown is exactly when a human should look. Treating
    absence as a pass would let the least-evidenced case publish itself."""
    decision = evaluate_publication(
        converged=True,
        confidence=None,
        confidence_threshold=THRESHOLD,
        substantive_claims=1,
        resolvable_claims=1,
        unresolved_contradictions=0,
    )

    assert decision.failed == (PublicationCondition.CONFIDENT,)


def test_confidence_exactly_at_the_threshold_passes() -> None:
    """The threshold is what a Tenant considers sufficient, not what it
    considers insufficient."""
    decision = evaluate_publication(
        converged=True,
        confidence=THRESHOLD,
        confidence_threshold=THRESHOLD,
        substantive_claims=1,
        resolvable_claims=1,
        unresolved_contradictions=0,
    )

    assert decision.publishes is True


def test_a_draft_with_nothing_substantive_is_not_evidenced() -> None:
    """"Nothing to check" is not "everything checks out". Treating them the
    same is how a vacuous Finding reaches a reader."""
    decision = evaluate_publication(
        converged=True,
        confidence=0.99,
        confidence_threshold=THRESHOLD,
        substantive_claims=0,
        resolvable_claims=0,
        unresolved_contradictions=0,
    )

    assert decision.failed == (PublicationCondition.EVIDENCED,)


def test_a_partially_resolvable_draft_is_not_evidenced() -> None:
    """A citation that cannot be followed backs a claim no better than no
    citation at all."""
    decision = evaluate_publication(
        converged=True,
        confidence=0.99,
        confidence_threshold=THRESHOLD,
        substantive_claims=3,
        resolvable_claims=2,
        unresolved_contradictions=0,
    )

    assert decision.failed == (PublicationCondition.EVIDENCED,)


def test_a_legacy_investigation_is_not_gated_on_a_contract_it_predates() -> None:
    """A narrative Finding was never citable. Gating every one of them on
    claim-level evidence would be a change of behaviour, not a policy."""
    decision = evaluate_publication(
        converged=True,
        confidence=0.91,
        confidence_threshold=THRESHOLD,
        substantive_claims=0,
        resolvable_claims=0,
        unresolved_contradictions=0,
        evidence_applicable=False,
    )

    assert decision.publishes is True


def test_the_legacy_exemption_only_waives_evidence() -> None:
    """It is not a way past the other three."""
    decision = evaluate_publication(
        converged=False,
        confidence=0.42,
        confidence_threshold=THRESHOLD,
        substantive_claims=0,
        resolvable_claims=0,
        unresolved_contradictions=1,
        evidence_applicable=False,
    )

    assert set(decision.failed) == {
        PublicationCondition.CONVERGED,
        PublicationCondition.CONFIDENT,
        PublicationCondition.UNCONTRADICTED,
    }
    assert PublicationCondition.EVIDENCED not in decision.failed


def test_the_same_facts_always_produce_the_same_decision() -> None:
    """Idempotence at the level that matters: the policy is a function of its
    arguments, so a duplicate evaluation cannot decide differently."""
    facts = dict(
        converged=False,
        confidence=0.42,
        confidence_threshold=THRESHOLD,
        substantive_claims=2,
        resolvable_claims=1,
        unresolved_contradictions=1,
    )

    first = evaluate_publication(**facts)
    second = evaluate_publication(**facts)

    assert first == second
    assert first.failed == second.failed


def test_the_policy_is_the_only_thing_that_decides() -> None:
    """No Agent publishes. `PublicationDecision` carries no way to override
    itself, and `publishes` is derived from the failures rather than set — so
    there is nothing for an Agent to hand in that says "publish me".
    """
    gated = decide(confident=False)

    assert gated.publishes is False
    with pytest.raises((AttributeError, TypeError)):
        gated.publishes = True  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        gated.failed = ()  # type: ignore[misc]
