"""Accuracy & evaluation benchmark across all complexity levels and acceptance criteria."""
import json
import re
from pathlib import Path

import pytest

from atlys_agentic import tools
from atlys_agentic.flows.analysis_flow import AnalysisFlow, AnalysisState


class AccuracyBenchmark:
    """Benchmark harness evaluating system accuracy across complexity tiers."""

    @classmethod
    def evaluate_invariants_and_safety(cls) -> float:
        """Level 1: 6-pillar invariants and SELECT-only enforcement accuracy."""
        tests_passed = 0
        total_tests = 4

        # Test 1: Invariant validation detects missing clauses
        violations = tools.Tool_Validate_Invariants("CREATE TABLE t (id String) ENGINE=MergeTree")
        if any("ORDER BY" in v for v in violations) and any("PARTITION BY" in v for v in violations):
            tests_passed += 1

        # Test 2: Valid DDL passes invariant checks
        valid_ddl = """CREATE TABLE t (
            device_type LowCardinality(String),
            timestamp DateTime
        ) ENGINE=MergeTree
        PARTITION BY toYYYYMM(timestamp)
        PRIMARY KEY (device_type, timestamp)
        ORDER BY (device_type, timestamp)
        SETTINGS index_granularity=8192"""
        if len(tools.Tool_Validate_Invariants(valid_ddl)) == 0:
            tests_passed += 1

        # Test 3: Rejection of destructive statements
        try:
            tools._assert_select_only("DROP TABLE insights")
        except ValueError:
            tests_passed += 1

        # Test 4: Acceptance of safe analytic CTE queries
        try:
            tools._assert_select_only("WITH cte AS (SELECT 1 as x) SELECT * FROM cte")
            tests_passed += 1
        except ValueError:
            pass

        return tests_passed / total_tests

    @classmethod
    def evaluate_answerability_trap_precision(cls) -> float:
        """Level 2: Precision in detecting metric boundary traps and impossible questions."""
        trap_questions = [
            "What is our on-time delivery rate for express checkout orders in the UAE?",
            "What is the average courier transit time for shipped visas?",
            "What is the SLA fulfillment score for passport courier delivery?",
        ]
        legitimate_questions = [
            "Why is conversion dropping on express checkout in UAE on iOS?",
            "What is the drop-off rate between application started and payment completed?",
        ]

        correct = 0
        total = len(trap_questions) + len(legitimate_questions)

        for q in trap_questions:
            res = tools.Tool_Resolve_And_Answerability(
                question=q,
                candidates_info=[{"table_name": "express_checkout", "spec_id": "01_express_checkout"}],
                business_context_info={},
            )
            if res.get("answerable") == "no":
                correct += 1

        for q in legitimate_questions:
            res = tools.Tool_Resolve_And_Answerability(
                question=q,
                candidates_info=[{"table_name": "express_checkout", "spec_id": "01_express_checkout"}],
                business_context_info={},
            )
            if res.get("answerable") == "yes":
                correct += 1

        return correct / total

    @classmethod
    def evaluate_multi_cut_completeness(cls) -> float:
        """Level 2: Completeness of query architect plan (5 cuts, intersection, baseline, timeseries, alt headline)."""
        queries, _ = tools.Tool_Plan_Queries(
            interpretation={"chosen_table": "express_checkout", "metric": "conversion_rate"},
            table_name="express_checkout",
            available_columns=["timestamp", "user_id", "device_type", "os", "geoip_country_code", "destination", "event", "is_guest"],
            probe_result={"rows": 5507},
            context_package={},
        )
        required_purposes = {
            "cut:device_type",
            "cut:geoip_country_code",
            "cut:destination",
            "cut:funnel_stage",
            "cut:user_segment",
            "intersection",
            "headline_alt",
            "baseline",
            "timeseries",
        }
        present = {q.purpose for q in queries}
        intersection = required_purposes.intersection(present)
        return len(intersection) / len(required_purposes)

    @classmethod
    def evaluate_signal_and_correlation_accuracy(cls) -> float:
        """Level 3: Accuracy of derived signals, concentration ratio, and K-issue correlation."""
        matched_k = tools.Tool_Match_Known_Issue(
            question="Why is iOS checkout dropping in the UAE?",
            spec_id="01_express_checkout",
            table_name="express_checkout",
            context_package={"known_issues": ["[K1] iOS WebKit OTP autofill regression"]},
        )
        signals = tools.Tool_Derive_Signals(
            execution_results={},
            probe_result={"rows": 5507},
            matched_k_issue=matched_k,
            interpretation={"chosen_table": "express_checkout", "metric": "conversion_rate"},
            warnings=[],
            query_origin="architect_fallback",
        )

        checks_passed = 0
        total_checks = 5

        # 1. Matched K1 issue
        if matched_k and matched_k.get("k_id") == "K1":
            checks_passed += 1

        # 2. Calculated concentration ratio in iOS x AE
        if signals.get("concentration_ratio") == pytest.approx(0.78, abs=0.05):
            checks_passed += 1

        # 3. Baseline vs observed delta calculated (-15.2pp)
        if signals.get("headline_delta") == pytest.approx(-15.2, abs=0.1):
            checks_passed += 1

        # 4. Alt-denominator delta computed (-8.3pp)
        if signals.get("alt_delta") == pytest.approx(-8.3, abs=0.1):
            checks_passed += 1

        # 5. Finding key and trend state populated
        if signals.get("finding_key") and signals.get("trend_state") in ("persisting", "new", "reversed"):
            checks_passed += 1

        return checks_passed / total_checks

    @classmethod
    def evaluate_end_to_end_synthesis_accuracy(cls) -> float:
        """Level 3: Verification of PM report structure, hidden tokens, and submission artifacts."""
        flow = AnalysisFlow()
        initial_state = AnalysisState(
            question="Why is conversion dropping on express checkout in UAE on iOS?",
            spec_id="01_express_checkout",
            dry_run=True,
        )
        final_state = flow.run(initial_state)

        passed = 0
        total = 4

        # 1. Pipeline completed
        if final_state.phase == "completed":
            passed += 1

        # 2. Contains Section 9 required headers
        md = final_state.insight_report_md
        if "#### Headline" in md and "#### Where it is concentrated" in md and "#### The why" in md:
            passed += 1

        # 3. Machine-readable hidden token present
        if "<!-- atlys:insight" in md and "finding_key=" in md:
            passed += 1

        # 4. Submission artifact emitted to disk
        out_path = Path("outputs/submission/01_express_checkout/insight_report.md")
        if out_path.exists() and out_path.read_text().strip():
            passed += 1

        return passed / total


# ==============================================================================
# PYTEST TEST CASES
# ==============================================================================

def test_eval_level1_invariants_and_safety():
    score = AccuracyBenchmark.evaluate_invariants_and_safety()
    assert score == 1.0, f"Expected 100% accuracy on invariants & safety; got {score * 100:.1f}%"


def test_eval_level2_answerability_trap_precision():
    score = AccuracyBenchmark.evaluate_answerability_trap_precision()
    assert score == 1.0, f"Expected 100% trap precision; got {score * 100:.1f}%"


def test_eval_level2_multi_cut_completeness():
    score = AccuracyBenchmark.evaluate_multi_cut_completeness()
    assert score == 1.0, f"Expected 100% multi-cut completeness; got {score * 100:.1f}%"


def test_eval_level3_signal_and_correlation_accuracy():
    score = AccuracyBenchmark.evaluate_signal_and_correlation_accuracy()
    assert score == 1.0, f"Expected 100% signal accuracy; got {score * 100:.1f}%"


def test_eval_level3_end_to_end_synthesis_accuracy():
    score = AccuracyBenchmark.evaluate_end_to_end_synthesis_accuracy()
    assert score == 1.0, f"Expected 100% E2E synthesis accuracy; got {score * 100:.1f}%"
