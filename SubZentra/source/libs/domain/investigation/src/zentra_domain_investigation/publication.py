"""Who decides whether a Draft Finding becomes a Finding.

Not the Insight Agent, and not the Orchestrator. ADR 0011 puts publication
authority in deterministic Investigation policy precisely so that no Agent —
however confident, however well-evidenced — can publish its own conclusion.

Four conditions, evaluated independently. A Draft Finding publishes
automatically only when all four pass; anything else opens a Human Approval
gate. They are separate rather than folded into one score because a reviewer
opening that gate needs to know *which* of them failed, and because a single
number cannot say "the recheck disagreed" and "nothing backs claim 2" at the
same time.

Every failure is recorded, not just the first. A reviewer told only that
confidence was low, when the evidence was also unreachable, would approve on a
false picture of what is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PublicationCondition(StrEnum):
    """The four things that must hold before a conclusion publishes itself.

    The values are the vocabulary the API and the UI both use. A reviewer, an
    operator reading Replay, and a developer reading a truth table are all
    looking at the same words.
    """

    #: The Evaluator's independent recheck agreed with the Analyst.
    CONVERGED = "converged"
    #: Bounded confidence cleared the Tenant's threshold. Bounded, not
    #: reported: the ceilings for sample size and model independence have
    #: already been applied.
    CONFIDENT = "confident"
    #: Every substantive claim cites evidence, and that evidence resolves.
    #: Citable and resolvable are one condition on purpose — a citation that
    #: cannot be followed backs a claim no better than no citation at all.
    EVIDENCED = "evidenced"
    #: No contradiction is left open.
    UNCONTRADICTED = "uncontradicted"


@dataclass(frozen=True, slots=True)
class PublicationDecision:
    """What the policy decided, and everything that made it decide so."""

    failed: tuple[PublicationCondition, ...]

    @property
    def publishes(self) -> bool:
        return not self.failed

    @property
    def requires_approval(self) -> bool:
        return bool(self.failed)


def evaluate_publication(
    *,
    converged: bool,
    confidence: float | None,
    confidence_threshold: float,
    substantive_claims: int,
    resolvable_claims: int,
    unresolved_contradictions: int,
    # False only for an Investigation that predates claim-level evidence. A
    # narrative Finding was never citable, and gating every legacy one on a
    # contract that did not exist when it ran would be a change of behaviour
    # rather than a policy. Stated as its own argument so the caller cannot
    # fake a satisfied claim to get the same effect.
    evidence_applicable: bool = True,
) -> PublicationDecision:
    """Decide, deterministically, from facts that have already been settled.

    Nothing here computes evidence, bounds confidence, or resolves a citation.
    Those are done, and their results are arguments. This function only says
    what they add up to — which is what makes it a truth table rather than a
    judgement.

    A Draft Finding with no substantive claims is *not* evidenced. An empty
    conclusion has nothing to publish, and treating "nothing to check" as
    "everything checks out" is how a vacuous Finding reaches a reader.
    """
    failed: list[PublicationCondition] = []

    if not converged:
        failed.append(PublicationCondition.CONVERGED)
    # A missing confidence is a failed condition, never an assumed pass. The
    # score being unknown is exactly when a human should look.
    if confidence is None or confidence < confidence_threshold:
        failed.append(PublicationCondition.CONFIDENT)
    if evidence_applicable and (
        substantive_claims == 0 or resolvable_claims < substantive_claims
    ):
        failed.append(PublicationCondition.EVIDENCED)
    if unresolved_contradictions > 0:
        failed.append(PublicationCondition.UNCONTRADICTED)

    return PublicationDecision(failed=tuple(failed))
