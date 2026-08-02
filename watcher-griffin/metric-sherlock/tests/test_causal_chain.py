"""The because-ladder may re-present the evidence. It may not add to it.

WHY THIS FILE EXISTS
The causal chain sits at the TOP of the incident page, above the charts, and for most
readers it will be the only thing they read. That makes it the highest-leverage place in
the system to state something the data does not support -- and unlike the narrator it is
deterministic code, so a wrong claim here is wrong every single time rather than
occasionally.

So these tests pin the property that matters more than the wording: **every number in
the chain must already exist in the incident it was built from.** They also pin the two
degradations that must not be silently smoothed over -- an unmatched signature (S0) and
an untestable seasonality check -- because a chain that reads confidently at every rung
is indistinguishable from one that had nothing to say.
"""

import pytest

from engine.causal_chain import (
    DERIVED,
    MEASURED,
    RULED_OUT,
    UNKNOWN,
    build_chain,
)


def _incident(**overrides) -> dict:
    """INC-0623 as the sweep actually records it: the Android demand outage."""
    base = {
        "incident_id": "11111111-1111-1111-1111-111111111111",
        "signature": "S4",
        "mechanism": "A demand partner serving Android stopped bidding: fill rate fell on "
                     "Android while its sibling OS held.",
        "signature_confidence": 0.85,
        "owner": "demand",
        "root_scope_type": "os_family",
        "root_scope_value": "Android",
        "root_metric": "fill_rate",
        "grain": "1d",
        "direction": "below",
        "breached_metrics": ["fill_rate", "rpr"],
        "impact_usd": 48.84,
        "impact_usd_per_day": 24.42,
        "windows_spanned": 2,
        "member_event_count": 295,
        "ruled_out": [
            {"check": "dimension:category", "reason": "spread",
             "numbers": {"breached": 7, "evaluated": 7, "breadth": 1.0},
             "source_steps": ["rank:hourly_by_category:current"]},
            {"check": "dimension:ad_format", "reason": "spread",
             "numbers": {"breached": 5, "evaluated": 5, "breadth": 1.0},
             "source_steps": ["rank:hourly_by_format:current"]},
            {"check": "dimension:app", "reason": "concentrated",
             "numbers": {"breached": 33, "evaluated": 170, "breadth": 0.194},
             "source_steps": ["rank:hourly_by_app:current"]},
        ],
        "seasonality": {
            "tested": True, "isolated": True,
            "siblings_breached": 1, "siblings_evaluated": 2, "breadth": 0.5,
            "reason": "only 1 of 2 os_family values moved",
        },
    }
    base.update(overrides)
    return base


def _all_numbers(chain) -> list:
    out = []
    for link in chain.links:
        out.extend(link.numbers.items())
    return out


# ---------------------------------------------------------------------------
# The guardrail
# ---------------------------------------------------------------------------
def test_every_number_in_the_chain_traces_back_to_the_incident():
    """No figure may appear that was not already persisted.

    Walks every numeric value on every rung and requires it to equal a value the
    incident (or its nested seasonality block) already holds. This is the test that
    would fail if someone later added a convenient subtotal.
    """
    inc = _incident()
    chain = build_chain(inc)

    known = set()
    for source in (inc, inc["seasonality"]):
        for v in source.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                known.add(round(float(v), 6))

    for key, value in _all_numbers(chain):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            assert round(float(value), 6) in known, f"{key}={value} is not in the incident"


def test_absent_fields_produce_absent_numbers_never_defaults():
    """A missing figure must drop out of the chain, not become a zero."""
    inc = _incident()
    del inc["impact_usd"]
    del inc["member_event_count"]
    chain = build_chain(inc)

    keys = {k for k, _ in _all_numbers(chain)}
    assert "impact_usd" not in keys
    assert "member_event_count" not in keys
    # ...and the rungs that did have their numbers are unaffected.
    assert "impact_usd_per_day" in keys


# ---------------------------------------------------------------------------
# The ladder itself
# ---------------------------------------------------------------------------
def test_the_chain_reads_symptom_then_cause_then_cost():
    chain = build_chain(_incident())
    titles = [link.title for link in chain.links]

    assert titles == [
        "What moved",
        "Where it is concentrated",
        "Why not somewhere else",
        "Could it just be seasonality",
        "What this pattern means",
        "What it costs",
    ]
    assert [link.step for link in chain.links] == [1, 2, 3, 4, 5, 6]


def test_steps_stay_contiguous_when_a_rung_does_not_apply():
    """No revenue decomposition and no partner dimensions -- two rungs vanish, and the
    numbering must not develop holes."""
    inc = _incident(ruled_out=[])
    chain = build_chain(inc)

    assert [link.step for link in chain.links] == list(range(1, len(chain.links) + 1))
    assert "Why not somewhere else" not in [link.title for link in chain.links]


def test_the_funnel_rung_appears_only_when_the_identity_was_walked():
    without = build_chain(_incident())
    assert "Which part of the funnel" not in [link.title for link in without.links]

    with_evidence = build_chain(_incident(evidence={
        "primary_factor": "fill_rate",
        "factor_breakdown": [{"factor": "requests"}, {"factor": "fill_rate"},
                             {"factor": "render_rate"}, {"factor": "ecpm"}],
    }))
    funnel = [link for link in with_evidence.links if link.title == "Which part of the funnel"]
    assert len(funnel) == 1
    assert funnel[0].numbers["primary_factor"] == "fill_rate"


def test_uniformly_affected_dimensions_are_the_reason_not_the_cause():
    """category 7/7 and ad_format 5/5 moved entirely, so they are ruled OUT; app 33/170
    did not, so it is not claimed as uniform."""
    chain = build_chain(_incident())
    link = next(x for x in chain.links if x.title == "Why not somewhere else")

    assert link.certainty == RULED_OUT
    assert any("app category (7/7)" in s for s in link.numbers["uniformly_affected"])
    assert any("ad format (5/5)" in s for s in link.numbers["uniformly_affected"])
    assert any("app (33/170)" in s for s in link.numbers["partially_affected"])
    assert "rank:hourly_by_category:current" in link.source_steps


def test_a_dimension_where_nothing_moved_is_the_strongest_ruling_out():
    """0 of 170 is not "concentrated" — it is the cleanest possible clearing.

    This is how INC-0628 was shown not to be a supply problem ("0/170 breached across
    apps"). A two-way breached-vs-evaluated split classified it as concentration, which
    inverts what the number says, so it is pinned here.
    """
    chain = build_chain(_incident(ruled_out=[
        {"check": "dimension:app", "reason": "none breached",
         "numbers": {"breached": 0, "evaluated": 170}, "source_steps": []},
        {"check": "dimension:ad_format", "reason": "partial",
         "numbers": {"breached": 1, "evaluated": 5}, "source_steps": []},
    ]))
    link = next(x for x in chain.links if x.title == "Why not somewhere else")

    assert link.certainty == RULED_OUT
    assert link.numbers["untouched"] == ["app (0/170)"]
    assert link.numbers["partially_affected"] == ["ad format (1/5)"]
    assert "nothing there moved at all" in link.claim
    # ...and the partial one is NOT claimed as a clearing.
    assert "ad format" not in link.claim


def test_a_purely_partial_result_narrows_without_ruling_anything_out():
    """Nothing was cleared, so the rung must not be marked `ruled_out` — that would
    claim a check achieved something it did not."""
    chain = build_chain(_incident(ruled_out=[
        {"check": "dimension:app", "reason": "partial",
         "numbers": {"breached": 33, "evaluated": 170}, "source_steps": []},
    ]))
    link = next(x for x in chain.links if x.title == "Why not somewhere else")

    assert link.certainty == MEASURED
    assert "uneven" in link.claim


def test_the_mechanism_rung_is_marked_derived_not_measured():
    """It is a rule-table classification over measured spread. Sound, but a different
    kind of claim from a band comparison, and the marker has to say so."""
    chain = build_chain(_incident())
    link = next(x for x in chain.links if x.title == "What this pattern means")

    assert link.certainty == DERIVED
    assert "rule table" in link.because
    assert "demand" in link.because          # the owner, in plain language
    assert chain.complete is True


# ---------------------------------------------------------------------------
# Degrading honestly
# ---------------------------------------------------------------------------
def test_s0_says_it_does_not_know_and_keeps_the_measured_rungs():
    """An unmatched pattern must not be dressed up, and must not delete the facts."""
    chain = build_chain(_incident(signature="S0", mechanism="", owner="", signature_confidence=0.0))
    link = next(x for x in chain.links if x.title == "What this pattern means")

    assert link.certainty == UNKNOWN
    assert "does not match any known failure mode" in link.claim
    assert chain.complete is False
    # The measurements survive: what moved, where, and what was ruled out.
    assert next(x for x in chain.links if x.title == "What moved").certainty == MEASURED
    assert next(x for x in chain.links if x.title == "Why not somewhere else").certainty == RULED_OUT


def test_an_untestable_seasonality_check_is_rendered_not_dropped():
    """A missing rung reads as a chain with no gap in it. It has to be shown."""
    chain = build_chain(_incident(seasonality={
        "tested": False,
        "reason": "only 1 value of os_family was evaluated, so there is nothing to compare against.",
    }))
    link = next(x for x in chain.links if x.title == "Could it just be seasonality")

    assert link.certainty == UNKNOWN
    assert "could not be run" in link.claim
    assert "nothing to compare against" in link.because
    assert chain.complete is False


def test_a_broad_move_does_not_claim_seasonality_was_excluded():
    chain = build_chain(_incident(seasonality={
        "tested": True, "isolated": False,
        "siblings_breached": 2, "siblings_evaluated": 2, "breadth": 1.0,
    }))
    link = next(x for x in chain.links if x.title == "Could it just be seasonality")

    assert link.certainty == UNKNOWN
    assert "not excluded" in link.claim


def test_a_click_move_books_no_dollars_and_says_why_in_the_estimator_s_words():
    """The chain and engine/impact.py must give the same reason, from one constant."""
    from engine.impact import ENGAGEMENT_ZERO_EXPOSURE_REASON

    chain = build_chain(_incident(
        root_metric="ctr", impact_usd=0.0, impact_usd_per_day=0.0, signature="S8",
    ))
    link = next(x for x in chain.links if x.title == "What it costs")

    assert link.claim == "Nothing, in revenue terms."
    assert link.because == ENGAGEMENT_ZERO_EXPOSURE_REASON
    assert link.numbers["impact_usd_per_day"] == 0.0


def test_an_unpriceable_incident_says_so_rather_than_showing_zero():
    """$0.00 and 'could not be priced' are different claims, and conflating them would
    put a fabricated zero on the page."""
    inc = _incident()
    del inc["impact_usd_per_day"]
    del inc["impact_usd"]
    link = next(x for x in build_chain(inc).links if x.title == "What it costs")

    assert link.certainty == UNKNOWN
    assert "No dollar exposure could be estimated" in link.claim
    assert link.numbers == {}


def test_a_global_incident_says_nothing_is_concentrated():
    chain = build_chain(_incident(root_scope_type="global", root_scope_value=""))
    link = next(x for x in chain.links if x.title == "Where it is concentrated")

    assert "not concentrated anywhere" in link.claim


def test_the_chain_uses_plain_language_not_column_names():
    """`os_family`, `fill_rate` and `rpr` are schema, not English."""
    chain = build_chain(_incident())
    prose = " ".join(f"{x.title} {x.claim} {x.because}" for x in chain.links)

    for column in ("os_family", "fill_rate", "root_scope_value", "impact_usd_per_day"):
        assert column not in prose
    assert "fill rate" in prose


def test_serialisation_round_trips_for_the_api():
    payload = build_chain(_incident()).to_dict()

    assert payload["incident_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["complete"] is True
    assert len(payload["links"]) == 6
    assert set(payload["links"][0]) == {
        "step", "title", "claim", "because", "numbers", "source_steps", "certainty",
    }


def test_an_empty_incident_does_not_raise():
    """The unseen dataset will produce shapes this build has not seen. A chain that
    crashes takes the whole incident page down with it."""
    chain = build_chain({})

    assert chain.links                       # still says what it can
    assert chain.complete is False
    assert all(isinstance(x.claim, str) and x.claim for x in chain.links)
