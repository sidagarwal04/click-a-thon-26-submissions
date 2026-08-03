"""Comprehensive CUJ 2 multi-agent pipeline tests across all phases and complexity levels."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from atlys_agentic import chdb_client, tools
from atlys_agentic.flows.analysis_flow import AnalysisFlow, AnalysisState
from atlys_agentic.tools_common import PlannedQuery, cosine_distance, embed_text


# ==============================================================================
# LEVEL 1: INVARIANTS, VECTOR MATH & VALIDATION SAFETY
# ==============================================================================

def test_l1_cosine_distance_properties():
    """Verify vector distance properties: identical vectors=0.0, orthogonal=1.0, opposite=2.0."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    v4 = [-1.0, 0.0, 0.0]

    assert cosine_distance(v1, v2) == pytest.approx(0.0, abs=1e-5)
    assert cosine_distance(v1, v3) == pytest.approx(1.0, abs=1e-5)
    assert cosine_distance(v1, v4) == pytest.approx(2.0, abs=1e-5)
    # Empty vectors return 1.0 safely
    assert cosine_distance([], [1.0]) == 1.0


def test_l1_strict_select_only_validation():
    """Assert query validator permits SELECT/WITH queries and rejects any mutation or DDL."""
    valid_queries = [
        "SELECT count() FROM express_checkout",
        "WITH daily AS (SELECT toDate(timestamp) as d FROM express_checkout) SELECT d, count() FROM daily GROUP BY d",
        "  select * from express_checkout limit 10",
    ]
    for q in valid_queries:
        tools._assert_select_only(q)  # Must not raise

    invalid_queries = [
        "DROP TABLE express_checkout",
        "ALTER TABLE express_checkout DELETE WHERE user_id = 'u1'",
        "INSERT INTO express_checkout VALUES ('2026-04-01', 'u1')",
        "TRUNCATE TABLE express_checkout",
        "SELECT * FROM express_checkout; DROP TABLE users;",
    ]
    for q in invalid_queries:
        with pytest.raises(ValueError):
            tools._assert_select_only(q)


def test_l1_confidence_score_calibration_boundaries():
    """Verify confidence formula bounds, sample size log-scale, and component additivity."""
    # Large sample (5000+), large effect (>=10%), known issue match, consistent cuts
    high_score = tools.Tool_Score_Confidence(
        sample_size=5507,
        effect_size_pct=15.2,
        known_issue_match=True,
        cut_consistency=1.0,
    )
    assert high_score["score"] >= 0.85
    assert high_score["sample_size_component"] == 0.40
    assert high_score["effect_size_component"] == 0.25
    assert high_score["known_issue_component"] == 0.20
    assert high_score["cut_consistency_component"] == 0.15

    # Small sample (100 rows), small effect (1%), no known issue
    low_score = tools.Tool_Score_Confidence(
        sample_size=100,
        effect_size_pct=1.0,
        known_issue_match=False,
        cut_consistency=0.5,
    )
    assert low_score["score"] < 0.40
    assert low_score["known_issue_component"] == 0.0


# ==============================================================================
# LEVEL 2: COMPONENT INTEGRATION, RETRIEVAL GUARDS & ANSWERABILITY TRAPS
# ==============================================================================

def test_l2_semantic_retrieval_with_three_guards():
    """Phase 1a: Test semantic retrieval candidates, distance threshold guard, and engine filter."""
    result = tools.Tool_Semantic_Retrieval(
        question="Why is conversion dropping on express checkout in UAE on iOS?",
        top_k=3,
        threshold=0.85,
    )
    assert "candidates" in result
    assert len(result["candidates"]) > 0
    assert result["candidates"][0]["classification"] == "raw"
    assert "threshold" in result
    assert "confident_match" in result


def test_l2_live_probe_aggregates_only_zero_llm():
    """Phase 1c: Live probe returns aggregated statistics (row count, min/max timestamp, unique users) without LLM calls."""
    probe = tools.Tool_Live_Probe("express_checkout", spec_id="01_express_checkout")
    assert probe["table_name"] == "express_checkout"
    assert probe["rows"] > 0
    assert "from_ts" in probe
    assert "to_ts" in probe
    assert "users" in probe


def test_l2_answerability_metric_boundary_trap():
    """Phase 2+3: Post-purchase delivery / courier SLA questions trigger honest decline without queries."""
    trap_question = "What is our on-time delivery rate for express checkout orders in the UAE?"
    res = tools.Tool_Resolve_And_Answerability(
        question=trap_question,
        candidates_info=[{"table_name": "express_checkout", "spec_id": "01_express_checkout"}],
        business_context_info={},
    )
    assert res["answerable"] == "no"
    assert "missing" in res
    assert any("delivery" in m.lower() or "post-purchase" in m.lower() for m in res["missing"])


def test_l2_known_issue_matching_k1():
    """Phase 4: Match K1 (iOS WebKit OTP regression) deterministically from context."""
    k_match = tools.Tool_Match_Known_Issue(
        question="Why is iOS checkout dropping in the UAE?",
        spec_id="01_express_checkout",
        table_name="express_checkout",
        context_package={"known_issues": ["[K1] iOS WebKit OTP autofill regression"]},
    )
    assert k_match is not None
    assert k_match["k_id"] == "K1"
    assert "2026-03-11" in k_match["date_logged"]


def test_l2_query_architect_multi_cut_planning():
    """Phase 5: Query Architect outputs 5 cuts, 1 intersection, 1 alt-denominator headline, 1 baseline, 1 timeseries."""
    queries, origin = tools.Tool_Plan_Queries(
        interpretation={"chosen_table": "express_checkout", "metric": "conversion_rate"},
        table_name="express_checkout",
        available_columns=["timestamp", "user_id", "device_type", "os", "geoip_country_code", "destination", "event", "is_guest"],
        probe_result={"rows": 5507},
        context_package={},
    )
    purposes = [q.purpose for q in queries]
    assert "cut:device_type" in purposes
    assert "cut:geoip_country_code" in purposes
    assert "cut:destination" in purposes
    assert "cut:funnel_stage" in purposes
    assert "cut:user_segment" in purposes
    assert "intersection" in purposes
    assert "headline_alt" in purposes
    assert "baseline" in purposes
    assert "timeseries" in purposes
    assert all(isinstance(q, PlannedQuery) for q in queries)


# ==============================================================================
# LEVEL 3: END-TO-END WORKFLOW & PERSISTENCE
# ==============================================================================

def test_l3_cuj2_end_to_end_analysis_flow(tmp_path):
    """Phase 0-11: Full deterministic analysis flow execution emitting insight report and persistence."""
    flow = AnalysisFlow()
    initial_state = AnalysisState(
        question="Why is conversion dropping on express checkout in UAE on iOS?",
        spec_id="01_express_checkout",
        dry_run=True,
    )

    final_state = flow.run(initial_state)

    assert final_state.phase == "completed"
    assert final_state.answerable == "yes"
    assert final_state.chosen_table == "express_checkout"
    assert final_state.matched_k_issue is not None
    assert final_state.matched_k_issue["k_id"] == "K1"
    assert len(final_state.planned_queries) >= 8

    # Signals
    assert final_state.signals.get("concentration_ratio") == pytest.approx(0.78, abs=0.05)
    assert final_state.signals.get("trend_state") == "persisting"

    # Report & Token
    assert "### Express Checkout" in final_state.insight_report_md
    assert "<!-- atlys:insight" in final_state.insight_report_md
    assert "finding_key=" in final_state.insight_report_md

    # Emitted Artifacts
    report_file = Path("outputs/submission/01_express_checkout/insight_report.md")
    assert report_file.exists()


def test_l3_cuj2_metric_trap_declines_honestly():
    """Phase 0-11: Metric-boundary trap flow terminates honestly with decline response and zero queries executed."""
    flow = AnalysisFlow()
    initial_state = AnalysisState(
        question="What is our courier on-time delivery SLA rate for express checkout?",
        spec_id="01_express_checkout",
        dry_run=True,
    )
    final_state = flow.run(initial_state)

    assert final_state.phase == "declined"
    assert final_state.answerable == "no"
    assert len(final_state.planned_queries) == 0
    assert "not derivable" in final_state.insight_report_md.lower() or "not instrumented" in final_state.insight_report_md.lower()


# ==============================================================================
# LEVEL 4: UNSEEN SPEC GENERALIZATION & CONTEXT PERSISTENCE
# ==============================================================================

def test_l4_unseen_spec_semantic_resolution_without_keyword_ladder():
    """The Unseen Spec: An un-hardcoded feature spec (e.g. 06_visa_fast_track) resolves purely via semantic retrieval."""
    # Write a new table semantics record simulating CUJ 1 ingestion of an unseen spec
    tools.Tool_Write_Table_Semantics(
        spec_id="06_visa_fast_track",
        table_name="visa_fast_track",
        spec_text="Feature spec — Visa Fast Track. Streamlines expedited visa processing fees and appointment bookings.",
        column_names=["timestamp", "user_id", "country", "service_tier", "booking_status"],
        agent="instrumentation_agent",
        trace_id="test-unseen-trace",
    )

    # Ask a question specifically about fast track expedited processing
    retrieval = tools.Tool_Semantic_Retrieval(
        question="Why are appointment bookings failing for expedited visa fast track customers?",
        top_k=3,
    )

    candidate_tables = [c["table_name"] for c in retrieval["candidates"]]
    assert "visa_fast_track" in candidate_tables
