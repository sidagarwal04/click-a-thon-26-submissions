"""Mutually-exclusive outcomes must not be modelled as sequential funnel steps.

The defect this pins, found on the sealed 6th spec: its events include an "applied"
and a "rejected" outcome that are alternatives — measured, ZERO entities have both.
Spec-bullet order listed them consecutively, so the derived funnel put the rejected
arm mid-sequence. `windowFunnel` requires strict sequential passage, so every entity
that took the *other* branch stopped there and EVERY step after it reported zero.

That is the dangerous kind of wrong: it reads as a catastrophic drop-off rather than
a modelling error. Verified against the live table — the derived funnel returned
shown=2100 → entered=777 → applied=408 → 0 → 0, while the same funnel with the branch
removed returns 2100 → 777 → 408 → 238 → 155.

The 0.05 threshold is calibrated, not guessed: across every spec and mock topology in
this repo the minimum per-entity overlap ratio is 1.000 for eight, 0.420 and 0.667 for
the two with a genuinely optional middle step (sequential, correctly not flagged), and
0.000 for the one real branch — a wide margin on both sides.
"""

from __future__ import annotations

from collections import Counter

import pytest

from profile import (
    BRANCH_MAX_OVERLAP,
    BRANCH_MIN_ENTITIES,
    _exclusive_branches,
)


def _entities(spec: dict[str, int], overlap_pairs: int = 0) -> dict:
    """Build a per-entity {entity: {event: (ts, idx)}} map from {event: n_entities}."""
    per: dict[str, dict] = {}
    n = 0
    for event, count in spec.items():
        for _ in range(count):
            per[f"e{n}"] = {event: (n, n)}
            n += 1
    for i in range(overlap_pairs):
        per[f"both{i}"] = {e: (i, i) for e in spec}
    return per


def test_zero_overlap_pair_is_flagged_as_a_branch() -> None:
    per = _entities({"applied": 100, "rejected": 60})
    branches, note = _exclusive_branches(per, ["applied", "rejected"],
                                         Counter({"applied": 100, "rejected": 60}))
    assert branches == {"rejected"}, "the smaller arm is dropped, the majority path kept"
    assert "mutually exclusive" in note


def test_fully_sequential_pair_is_never_flagged() -> None:
    """Anyone at a later step also has the earlier one -> overlap ratio 1.0."""
    per = _entities({}, overlap_pairs=0)
    per = {f"e{i}": {"step1": (i, i), "step2": (i, i)} for i in range(80)}
    per.update({f"only1_{i}": {"step1": (i, i)} for i in range(40)})
    branches, _ = _exclusive_branches(per, ["step1", "step2"],
                                      Counter({"step1": 120, "step2": 80}))
    assert branches == set()


def test_partially_overlapping_optional_step_is_not_a_branch() -> None:
    """An optional middle step (present for ~half) is still sequential, not an
    alternative outcome — this is the shape two real specs in this repo have, and
    flagging it would silently truncate a correct funnel."""
    per = {f"both{i}": {"a": (i, i), "b": (i, i)} for i in range(50)}
    per.update({f"a_only{i}": {"a": (i, i)} for i in range(50)})
    branches, _ = _exclusive_branches(per, ["a", "b"], Counter({"a": 100, "b": 50}))
    assert branches == set(), "50% overlap is a sequential optional step, not a branch"


def test_small_arms_are_left_alone() -> None:
    """Below the entity floor the ratio is noise; refusing to act is the safe default."""
    small = BRANCH_MIN_ENTITIES - 1
    per = _entities({"x": small, "y": small})
    branches, _ = _exclusive_branches(per, ["x", "y"], Counter({"x": small, "y": small}))
    assert branches == set()


def test_the_larger_arm_survives() -> None:
    per = _entities({"small": 40, "large": 400})
    branches, _ = _exclusive_branches(per, ["small", "large"],
                                      Counter({"small": 40, "large": 400}))
    assert branches == {"small"}


def test_threshold_is_a_margin_not_a_knife_edge() -> None:
    """Guard the calibration: the cut must sit well below the lowest sequential
    ratio observed in this repo (0.420) and well above a true branch (0.000)."""
    assert 0.0 < BRANCH_MAX_OVERLAP < 0.42


# ── live: the real specs must be unaffected ──────────────────────────────────


@pytest.mark.parametrize(
    "spec_dir",
    sorted(p for p in __import__("pathlib").Path("../specs").glob("*") if (p / "spec.md").exists())
    if __import__("pathlib").Path("../specs").is_dir() else [],
    ids=lambda p: p.name,
)
def test_known_specs_keep_every_event_in_the_funnel(spec_dir) -> None:
    """Only a genuine branch may shorten a funnel. Any known spec losing a step here
    means the threshold drifted into real sequential data."""
    import profile as profile_mod

    prof = profile_mod.profile_spec(spec_dir / "spec.md", spec_dir / "events.ndjson")
    dropped = set(prof.event_types) - set(prof.derived_funnel)
    if dropped:
        # Permitted only when the derivation says so, with measured evidence.
        assert "BRANCH:" in prof.funnel_derivation, (
            f"{spec_dir.name}: dropped {dropped} with no recorded justification"
        )
    else:
        assert "BRANCH:" not in prof.funnel_derivation
