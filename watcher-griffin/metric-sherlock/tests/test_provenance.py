"""Per-number provenance: the query behind each figure, and that it still returns it.

Every test here exists because of a way this feature can be CONFIDENTLY WRONG. A
"supporting query" that does not actually produce the number it is attached to is worse
than no query at all -- it converts an unverified figure into a falsely verified one. Two
such queries were caught during development and both looked entirely plausible:

  * a Decimal64(6) truncation, so eCPM verified as 5.600000 against a displayed
    5.6003203670300366;
  * a band read that returned one row per seasonal cell, so `rows[0]` was an arbitrary
    cell and sample_count verified as 662 (the pooled `all` cell) against a displayed 8
    (the strict dow|hod cell).

Neither raised. Both were found by running the query and comparing, which is why
test_measured_facts_reproduce_their_numbers is the centre of this file.
"""

import importlib.util
import os
import re

import pytest

from engine import datasets
from engine.grains import grain as get_grain
from engine.provenance import (CONFIG, DERIVED, MEASURED, build_provenance,
                               provenance_payload, verify_fact)
from engine.scopes import scope as get_scope

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# A minimal persisted-incident shape, so the pure tests need no database. Mirrors what
# monitor_store.get_incident() returns: analysis keys lifted to top level, members from
# metric_events.
FAKE_INCIDENT = {
    "incident_id": "11111111-2222-3333-4444-555555555555",
    "root_scope_type": "ad_format",
    "root_scope_value": "video",
    "root_metric": "ecpm",
    "grain": "15h",
    "direction": "below",
    "signature": "S8",
    "signature_confidence": 0.6,
    "opened_at": "2026-07-10 08:00:00",
    "last_seen_at": "2026-07-10 23:00:00",
    "impact_usd": 32.37,
    "impact_usd_per_day": 51.8,
    "windows_spanned": 1,
    "member_event_count": 22,
    "members": [
        {
            "metric": "ecpm", "scope_type": "ad_format", "scope_value": "video",
            "grain": "15h", "direction": "below", "value": 2.1566, "center": 4.5694,
            "spread": 0.2276, "deviation_score": -10.6, "impact_usd": 32.37,
            "window_start": "2026-07-10 08:00:00", "window_end": "2026-07-10 23:00:00",
            "seasonal_cell": "dow=5|hod=8", "baseline_method": "median_mad",
            "sample_count": 105,
        }
    ],
    "ruled_out": [
        {"check": "dimension:app", "reason": "flat",
         "numbers": {"breached": 0, "evaluated": 35, "breadth": 0.0,
                     "top_value": "", "concentration": 0.0},
         "source_steps": []},
    ],
    "seasonality": {"siblings_breached": 1, "siblings_evaluated": 5, "breadth": 0.2},
    "impact_breakdown": {"total_impact_usd": 32.37,
                         "parts": [{"scope_type": "ad_format", "scope_value": "video",
                                    "impact_usd": 32.37, "share_of_impact": 1.0,
                                    "basis": "price-based"}]},
    "evidence_score_detail": {
        "score": 84, "formula": "sum of six components", "caveat": "an index",
        "components_sum": 84.0,
        "components": [{"name": "persistence", "points": 20, "max_points": 20,
                        "raw": "2 of 2", "reason": "held", "source": "metric_events"}],
    },
    "history": {"recurrence_count": 0, "source_step": "history:lookup"},
}


# ---------------------------------------------------------------------------
# Shape and coverage (no database)
# ---------------------------------------------------------------------------


def test_every_figure_on_the_page_has_a_fact():
    """The figures the incident page renders, each of which must be explainable.

    Fails when a number is added to the UI without provenance -- which is the state this
    whole module exists to leave behind, where ~60 figures had between them two step
    references and no queries.
    """
    facts = build_provenance(FAKE_INCIDENT)
    required = [
        "root.value", "root.center", "root.spread", "root.sample_count",
        "root.deviation_score", "impact.usd", "impact.per_day",
        "incident.windows_spanned", "incident.member_event_count",
        "spread.app.evaluated", "spread.app.breached", "spread.app.breadth",
        "seasonality.siblings_breached", "seasonality.siblings_evaluated",
        "seasonality.breadth", "evidence.score", "history.recurrence_count",
        "signature.confidence",
    ]
    missing = [k for k in required if k not in facts]
    assert not missing, f"no provenance for displayed figure(s): {missing}"


def test_each_kind_carries_what_that_kind_promises():
    """A `measured` fact without SQL, or a `config` fact without a path, is a claim the
    UI would render as evidence while carrying none."""
    for key, f in build_provenance(FAKE_INCIDENT).items():
        assert f.kind in (MEASURED, DERIVED, CONFIG), f"{key}: bad kind {f.kind}"
        if f.kind == MEASURED:
            # `note` explains the exception (no rollup covers the scope at this grain),
            # so the absence is stated rather than silent.
            assert f.sql or f.note, f"{key}: measured with neither SQL nor a reason"
            # A column is required only where there is a single displayed figure to
            # compare against. An INPUT BUNDLE (`value is None`, e.g. the five raw
            # measures, or the span's windows) is a fact whose whole result set is the
            # evidence, and verify_fact reports its rows instead of a match verdict --
            # which is the honest answer, not a missing one.
            if f.sql and f.value is not None:
                assert f.column, f"{key}: measured SQL with no column to compare against"
        elif f.kind == DERIVED:
            assert f.formula, f"{key}: derived with no published formula"
        else:
            assert f.config_path, f"{key}: config with no settings path"


def test_derived_inputs_all_resolve():
    """A derived figure's inputs must be Facts a reader can actually open. A dangling key
    renders as a formula over inputs that are not there."""
    facts = build_provenance(FAKE_INCIDENT)
    for key, f in facts.items():
        for dep in f.inputs:
            assert dep in facts, f"{key} cites input '{dep}' which is not a fact"


def test_config_numbers_are_not_dressed_as_measurements():
    """`signature_confidence` is a hand-set literal per rule and contributes up to 15 of
    the 100 evidence points. Presenting it with a query it does not have would borrow
    authority it has not earned."""
    f = build_provenance(FAKE_INCIDENT)["signature.confidence"]
    assert f.kind == CONFIG
    assert f.sql is None
    assert "signature.py" in (f.config_path or "")


def test_payload_reports_its_own_gaps():
    payload = provenance_payload(FAKE_INCIDENT)
    assert payload["counts"]["total"] == len(payload["facts"])
    # Every measured fact on a reconstructable incident should have SQL; the field exists
    # so that when one does not, the payload says so instead of looking complete.
    assert payload["unverifiable"] == []


def test_provenance_is_pure():
    """It must run no query: `GET /api/incidents/{id}` calls it inline on every request,
    and it is also called on an incident dict in tests with no database at all."""
    before = dict(FAKE_INCIDENT)
    build_provenance(FAKE_INCIDENT)
    assert FAKE_INCIDENT == before, "build_provenance mutated the incident it was given"


def test_sql_quotes_are_escaped():
    """Scope values are data. One containing an apostrophe must not truncate the
    predicate of a statement handed to a reader as runnable."""
    inc = dict(FAKE_INCIDENT)
    inc["root_scope_value"] = "it's a value"
    inc["members"] = [dict(FAKE_INCIDENT["members"][0], scope_value="it's a value")]
    sql = build_provenance(inc)["root.value"].sql
    assert "'it''s a value'" in sql


# ---------------------------------------------------------------------------
# Reconstruction fidelity
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_reconstructed_sql_is_byte_identical_to_what_the_sweep_sent():
    """THE LOAD-BEARING TEST FOR RECONSTRUCTION.

    Provenance regenerates the sweep's SQL instead of persisting it, which is what makes
    it available for all 825 existing incidents. That is only honest while the
    regenerated string IS the string that ran, so this diffs them rather than trusting
    that the shared function keeps them equal.
    """
    from engine.ch_client import Trace
    from engine.ops_view import resolve_as_of
    from engine.sweep import band_lookup_sql, sweep_pair, window_sql

    with datasets.use_dataset("unseen"):
        as_of = resolve_as_of()
        s, g = get_scope("ad_format"), get_grain("15h")
        cur, prev = g.window_for(as_of), g.previous_window(as_of)
        trace = Trace()
        sweep_pair(s, g, as_of, ["ecpm"], trace)

    sent = {e.step: e.sql for e in trace.entries}
    assert sent[f"sweep:{s.name}:{g.name}:windows"] == window_sql(s, g, cur, prev)
    assert sent[f"sweep:{s.name}:{g.name}:bands"] == band_lookup_sql(s, g, cur, prev)


@pytest.mark.integration
def test_cited_steps_exist_in_a_real_trace():
    """`source_step` is a reconstructed STRING, not a reference -- five independent
    reconstruction sites and, until now, no test that any of them names a step that
    actually ran. Rename a step in sweep.py and every citation silently points at
    nothing, while still looking like a citation."""
    from engine.ch_client import Trace
    from engine.ops_view import resolve_as_of
    from engine.sweep import sweep_pair

    with datasets.use_dataset("unseen"):
        as_of = resolve_as_of()
        s, g = get_scope("ad_format"), get_grain("15h")
        trace = Trace()
        sweep_pair(s, g, as_of, ["ecpm"], trace)
        real_steps = {e.step for e in trace.entries}

        facts = build_provenance(FAKE_INCIDENT)
        cited = {f.step for f in facts.values()
                 if f.step and f.step.startswith(f"sweep:{s.name}:{g.name}")}
        assert cited, "no sweep steps were cited at all -- the test is not exercising this"
        assert cited <= real_steps, f"cited step(s) that never ran: {cited - real_steps}"


# ---------------------------------------------------------------------------
# The proof itself
# ---------------------------------------------------------------------------


def _sample_incidents(limit_each: int = 4) -> list:
    from engine import monitor_store

    rows = (monitor_store.list_incidents(limit=limit_each, gated=False)
            + monitor_store.list_incidents(limit=limit_each, gated=True))
    out, seen = [], set()
    for r in rows:
        if r["incident_id"] in seen:
            continue
        seen.add(r["incident_id"])
        full = monitor_store.get_incident(r["incident_id"])
        if full:
            out.append(full)
    return out


@pytest.mark.integration
@pytest.mark.parametrize("dataset_key", ["main", "unseen"])
def test_measured_facts_reproduce_their_numbers(dataset_key):
    """Run every measured fact's query and require it to return the displayed figure.

    This is the test the whole feature rests on, and it is the one that caught both real
    defects (the Decimal truncation and the arbitrary seasonal cell). Run across both
    databases because the reconstruction is scope- and grain-driven, and the two datasets
    exercise different scopes, metrics and grains.
    """
    with datasets.use_dataset(dataset_key):
        incidents = _sample_incidents()
        if not incidents:
            pytest.skip(f"no incidents in {dataset_key} to verify")
        mismatches, checked = [], 0
        for inc in incidents:
            for key, f in build_provenance(inc).items():
                if f.kind != MEASURED or not f.sql or f.value is None:
                    continue
                result = verify_fact(inc, key)
                checked += 1
                if result["matches"] is False:
                    mismatches.append(
                        f"{inc['root_metric']}/{inc['grain']} {key}: "
                        f"displayed={result['displayed']} returned={result['returned']}"
                    )
        assert checked > 0, "verified nothing -- the sample produced no measured facts"
        assert not mismatches, "query did not reproduce the displayed number:\n" + "\n".join(mismatches)


@pytest.mark.integration
@pytest.mark.parametrize("dataset_key", ["main", "unseen"])
def test_the_single_confidence_query_returns_the_displayed_score(dataset_key):
    """THE TEST THAT LICENSES `evidence_score_sql` TO EXIST.

    That function is a second implementation of `engine/confidence.py`'s arithmetic, in
    SQL, which is the duplication this repo otherwise refuses -- two implementations of
    one number can disagree, and the disagreement is silent. It is allowed only because
    this test makes a drift loud: the query must return exactly the `evidence_score` that
    was persisted by the Python at cluster time, for real incidents in both databases.

    If this test is ever deleted, delete `evidence_score_sql` with it. An unchecked second
    copy of a scoring formula is how two different confidences end up in front of a
    reader, each looking authoritative.
    """
    from engine.ch_client import Trace, get_client

    with datasets.use_dataset(dataset_key):
        incidents = [i for i in _sample_incidents(6) if i.get("evidence_score_detail")]
        if not incidents:
            pytest.skip(f"no scored incidents in {dataset_key}")
        mismatches = []
        for inc in incidents:
            from engine.provenance import evidence_score_sql

            row = get_client().query_readonly(
                evidence_score_sql(inc), step="test:evidence_score", trace=Trace()
            )[0]
            expected = int(inc["evidence_score_detail"]["score"])
            if int(row["evidence_score"]) != expected:
                mismatches.append(
                    f"{inc['root_metric']}/{inc['grain']}: python={expected} "
                    f"sql={row['evidence_score']} (components_sum={row['components_sum']})"
                )
        assert not mismatches, (
            "the published confidence query disagrees with engine/confidence.py:\n"
            + "\n".join(mismatches)
        )


def test_the_confidence_query_is_one_statement():
    """"A single query I can run" is the requirement, so a semicolon-joined script or a
    trailing statement would not satisfy it even if it returned the right number."""
    from engine.provenance import evidence_score_sql

    sql = evidence_score_sql(FAKE_INCIDENT)
    assert sql.count(";") == 0, "must be one statement, not a script"
    assert sql.lstrip().upper().startswith("WITH")
    # Returns the score under a stable name the verify path compares on.
    assert "AS evidence_score" in sql


def test_the_confidence_query_interpolates_config_rather_than_hardcoding():
    """A threshold change must not leave the published query describing the previous
    configuration -- the same rule that makes `band_k_amber` re-backtested rather than
    reasoned about."""
    from engine import confidence as C
    from engine.config import settings
    from engine.provenance import evidence_score_sql

    sql = evidence_score_sql(FAKE_INCIDENT)
    assert str(settings.band_k_amber) in sql and str(settings.band_k_red) in sql
    assert f"* {C.W_PERSISTENCE}" in sql
    # Every method the score recognises must appear, or a band built by an unlisted
    # method would silently score 0 in SQL and non-zero in Python.
    for method in C._METHOD_POINTS:
        assert f"'{method}'" in sql


@pytest.mark.integration
def test_every_incident_has_provenance_not_just_investigated_ones():
    """The distinguishing property. `evidence.queries` exists for 4 of 825 incidents
    because it is written only when an LLM investigation runs; provenance is derived from
    the incident's own fields, so it must be present even where `evidence` is empty."""
    with datasets.use_dataset("unseen"):
        incidents = _sample_incidents()
        if not incidents:
            pytest.skip("no incidents to check")
        uninvestigated = [i for i in incidents if not i.get("evidence")]
        assert uninvestigated, (
            "sample contained no uninvestigated incident, so this test proved nothing"
        )
        for inc in uninvestigated:
            payload = provenance_payload(inc)
            measured = [f for f in payload["facts"].values() if f["kind"] == MEASURED]
            assert measured, f"{inc['incident_id']}: no measured facts"
            assert all(f.get("sql") or f.get("note") for f in measured)
            assert payload["unverifiable"] == []


# ---------------------------------------------------------------------------
# The verify path must not become a SQL endpoint
# ---------------------------------------------------------------------------


def test_verify_rejects_an_unknown_fact_key():
    with pytest.raises(KeyError):
        verify_fact(FAKE_INCIDENT, "no.such.fact")


def test_sql_supplied_as_a_fact_key_is_never_executed():
    """The API takes a fact KEY. A caller sending SQL gets a lookup miss, not a query --
    which is the property that keeps this from being a SQL-execution endpoint."""
    with pytest.raises(KeyError):
        verify_fact(FAKE_INCIDENT, "TRUNCATE TABLE baselines")


def test_derived_and_config_facts_answer_without_running_anything():
    """Not an error: the honest answer for a figure no single query produces is its
    formula plus the inputs that ARE individually checkable."""
    r = verify_fact(FAKE_INCIDENT, "impact.per_day")
    assert r["verifiable"] is False and r["formula"] and r["inputs"]
    c = verify_fact(FAKE_INCIDENT, "signature.confidence")
    assert c["verifiable"] is False and c["config_path"]


def test_first_keyword_sees_through_comments():
    """The allowlist is only as good as the keyword parse: `-- x\\nINSERT` and
    `/* x */ ALTER` both start with harmless characters."""
    from engine.ch_client import _first_keyword

    assert _first_keyword("SELECT 1") == "SELECT"
    assert _first_keyword("  select 1") == "SELECT"
    assert _first_keyword("(SELECT 1)") == "SELECT"
    assert _first_keyword("WITH a AS (SELECT 1) SELECT 1") == "WITH"
    assert _first_keyword("-- c\nINSERT INTO x VALUES(1)") == "INSERT"
    assert _first_keyword("/* c */ ALTER TABLE x") == "ALTER"
    assert _first_keyword("") == ""


@pytest.mark.integration
@pytest.mark.parametrize("statement", [
    "INSERT INTO incidents SELECT * FROM incidents",
    "ALTER TABLE incidents UPDATE label = 'x' WHERE 1",
    "TRUNCATE TABLE baselines",
    "DROP TABLE baselines",
    "-- sneaky\nINSERT INTO incidents VALUES(1)",
])
def test_query_readonly_refuses_writes(statement):
    """Refused locally, before the round trip. The server also enforces readonly=2, but
    two layers means safety does not depend on this process building strings correctly."""
    from engine.ch_client import Trace, get_client

    with pytest.raises(ValueError, match="refuses"):
        get_client().query_readonly(statement, step="test:refuse", trace=Trace())


@pytest.mark.integration
def test_query_readonly_runs_a_select():
    from engine.ch_client import Trace, get_client

    rows = get_client().query_readonly("SELECT 1 AS n", step="test:ok", trace=Trace())
    assert rows and rows[0]["n"] == 1


# ---------------------------------------------------------------------------
# The DDL/insert-column parity check keeps working alongside this
# ---------------------------------------------------------------------------


def test_no_provenance_sql_is_database_qualified():
    """A qualified name would pin a reconstructed query to one dataset, so switching
    datasets would show one database's numbers with the other's queries."""
    facts = build_provenance(FAKE_INCIDENT)
    pattern = re.compile(r"\b(?:FROM|JOIN)\s+(ad_events_main|unseen_data)\.", re.I)
    offenders = [k for k, f in facts.items() if f.sql and pattern.search(f.sql)]
    assert not offenders, f"database-qualified reconstructed SQL: {offenders}"
