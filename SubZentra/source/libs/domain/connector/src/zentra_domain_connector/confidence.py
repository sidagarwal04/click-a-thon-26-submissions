"""Bounding a Relation's confidence by the evidence behind it.

This module is the reason the connector can be trusted to feed agents at all.
A join the system guessed wrong does not fail loudly — it produces a confident,
well-cited, wrong Finding. So confidence here is never asserted from the signal
score alone; it is the *minimum* of that score and what the evidence can
actually support.

Directly parallel to ``zentra_domain_investigation.confidence_ceiling``, which
made the same argument for Findings.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    CARDINALITY_CEILINGS,
    NAME_AFFINITY_WEIGHT,
    OVERLAP_WEIGHT,
    SAMPLE_CEILINGS,
    UNKNOWN_CARDINALITY_CEILING,
    UNKNOWN_SAMPLE_CEILING,
)
from .types import BindingCeiling


@dataclass(frozen=True, slots=True)
class OverlapMeasurement:
    """What was found when the two fields' values were compared.

    Produced by aggregate queries pushed down to the source. No source rows are
    transferred to compute it — discovery must not become exfiltration.
    """

    left_distinct: int
    right_distinct: int
    matched_distinct: int
    sampled_rows: int
    left_is_unique: bool = False
    right_is_unique: bool = False

    def __post_init__(self) -> None:
        if min(self.left_distinct, self.right_distinct, self.matched_distinct) < 0:
            raise ValueError("Distinct counts cannot be negative")
        if self.matched_distinct > min(self.left_distinct, self.right_distinct):
            raise ValueError("More values matched than exist on one of the sides")
        if self.sampled_rows < 0:
            raise ValueError("sampled_rows cannot be negative")

    @property
    def overlap_fraction(self) -> float:
        """The share of the *narrower* side's values found on the other side.

        Measured against the narrower side deliberately. A dimension table's
        keys will mostly appear in a fact table, but a fact table's keys will
        mostly *not* appear in some small lookup — scoring against the wider
        side would make every real foreign key look weak.
        """
        narrower = min(self.left_distinct, self.right_distinct)
        if narrower == 0:
            return 0.0
        return self.matched_distinct / narrower

    @property
    def min_cardinality(self) -> int:
        return min(self.left_distinct, self.right_distinct)


def sample_size_ceiling(sampled_rows: int | None) -> float:
    """The most confidence an overlap over this many rows may claim.

    An unknown sample is treated as the weakest case, on the same reasoning the
    Investigation domain already applies: a claim whose basis cannot be checked
    does not get to publish itself.
    """
    if sampled_rows is None or sampled_rows < 0:
        return UNKNOWN_SAMPLE_CEILING
    for threshold, ceiling in SAMPLE_CEILINGS:
        if sampled_rows < threshold:
            return ceiling
    return 1.0


def cardinality_ceiling(distinct_values: int | None) -> float:
    """The most confidence a relation between fields this coarse may claim.

    This is the rule that keeps two boolean columns out of the reviewer's
    queue. With two distinct values, perfect overlap is what you would expect
    from unrelated fields, so it is close to no evidence at all.
    """
    if distinct_values is None or distinct_values < 0:
        return UNKNOWN_CARDINALITY_CEILING
    for threshold, ceiling in CARDINALITY_CEILINGS:
        if distinct_values <= threshold:
            return ceiling
    return 1.0


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """A scored candidate and the reason it scored what it did."""

    confidence: float
    raw_score: float
    binding_ceiling: BindingCeiling
    sample_ceiling: float
    cardinality_ceiling_value: float


def assess(
    *,
    name_affinity: float,
    overlap: OverlapMeasurement,
) -> ConfidenceAssessment:
    """Combine the signals, then bound the result by the evidence.

    The raw score weights measured overlap above naming because names lie and
    data does not. Both ceilings are then applied, and whichever bound actually
    held the score down is recorded — so a reviewer looking at a middling
    proposal can see whether the problem is weak signals, a thin sample, or a
    field too coarse to identify anything.
    """
    raw = (
        NAME_AFFINITY_WEIGHT * name_affinity
        + OVERLAP_WEIGHT * overlap.overlap_fraction
    )
    sample_bound = sample_size_ceiling(overlap.sampled_rows)
    cardinality_bound = cardinality_ceiling(overlap.min_cardinality)

    confidence = min(raw, sample_bound, cardinality_bound)
    if confidence == raw:
        binding = BindingCeiling.NONE
    elif sample_bound <= cardinality_bound:
        binding = BindingCeiling.SAMPLE_SIZE
    else:
        binding = BindingCeiling.CARDINALITY

    return ConfidenceAssessment(
        confidence=round(confidence, 4),
        raw_score=round(raw, 4),
        binding_ceiling=binding,
        sample_ceiling=sample_bound,
        cardinality_ceiling_value=cardinality_bound,
    )
