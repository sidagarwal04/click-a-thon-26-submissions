import json
from pathlib import Path

import pytest

from atlys_agentic import tools


@pytest.fixture
def express_checkout_ndjson(tmp_path):
    events = [
        {
            "event": "express_checkout_shown",
            "timestamp": "2026-04-01T10:00:00",
            "user_id": "u1",
            "application_id": "a1",
            "device_type": "ios",
            "os": "iOS 17",
            "geoip_country_code": "AE",
            "shown_amount": 120.5,
            "currency": "AED",
        },
        {
            "event": "express_payment_confirmed",
            "timestamp": "2026-04-01T10:01:00",
            "user_id": "u1",
            "application_id": "a1",
            "device_type": "ios",
            "os": "iOS 17",
            "geoip_country_code": "AE",
            "payment": {"amount": 120.5, "currency": "AED", "latency_ms": 850},
        },
    ]
    p = tmp_path / "events.ndjson"
    p.write_text("\n".join(json.dumps(e) for e in events))
    return p


def test_infer_schema_never_leads_order_by_with_id(express_checkout_ndjson):
    ddl = tools.Tool_Infer_Schema(express_checkout_ndjson, "spec text", "express_checkout")
    assert "ORDER BY (timestamp, user_id)" in ddl
    assert "ORDER BY (id" not in ddl


def test_infer_schema_partitions_by_month(express_checkout_ndjson):
    ddl = tools.Tool_Infer_Schema(express_checkout_ndjson, "spec text", "express_checkout")
    assert "PARTITION BY toYYYYMM(timestamp)" in ddl


def test_infer_schema_flattens_nested_payment_object(express_checkout_ndjson):
    ddl = tools.Tool_Infer_Schema(express_checkout_ndjson, "spec text", "express_checkout")
    assert "payment_amount" in ddl
    assert "payment_currency" in ddl
    assert "payment_latency_ms" in ddl
    assert "payment Nested" not in ddl
    assert "payment String" not in ddl


def test_infer_schema_uses_low_cardinality_for_categorical_columns(express_checkout_ndjson):
    ddl = tools.Tool_Infer_Schema(express_checkout_ndjson, "spec text", "express_checkout")
    assert "device_type LowCardinality(String)" in ddl
    assert "os LowCardinality(String)" in ddl
    assert "currency LowCardinality(String)" in ddl


def test_infer_schema_has_ttl_twelve_months(express_checkout_ndjson):
    ddl = tools.Tool_Infer_Schema(express_checkout_ndjson, "spec text", "express_checkout")
    assert "TTL timestamp + INTERVAL 12 MONTH" in ddl


def test_infer_schema_sparse_column_becomes_nullable(express_checkout_ndjson):
    # shown_amount/payment_latency_ms only appear on one of the two event
    # types in the fixture -> they must be Nullable(...), not plain types.
    ddl = tools.Tool_Infer_Schema(express_checkout_ndjson, "spec text", "express_checkout")
    assert "shown_amount Nullable(Float64)" in ddl
    assert "payment_latency_ms Nullable(Int64)" in ddl


@pytest.fixture
def bugfix_ndjson(tmp_path):
    events = [
        {
            "event": "express_checkout_shown",
            "timestamp": "2026-04-01T10:00:00",
            "user_id": "u1",
            "retry_count": 0,
            "plan_tier": "free",
        },
        {
            "event": "express_payment_confirmed",
            "timestamp": "2026-04-01T10:01:00",
            "user_id": "u1",
            "retry_count": 1,
            "plan_tier": "pro",
        },
        {
            "event": "express_payment_confirmed",
            "timestamp": "2026-04-01T10:02:00",
            "user_id": "u2",
            "retry_count": 1,
            "plan_tier": "pro",
        },
    ]
    p = tmp_path / "bugfix_events.ndjson"
    p.write_text("\n".join(json.dumps(e) for e in events))
    return p


def test_infer_schema_zero_one_int_gets_uint8_without_naming_qualifier(bugfix_ndjson):
    # "retry_count" has no is_/has_ prefix; brief's rule is unqualified.
    ddl = tools.Tool_Infer_Schema(bugfix_ndjson, "spec text", "express_checkout")
    assert "retry_count UInt8" in ddl


def test_infer_schema_short_enum_string_gets_low_cardinality_without_name_hint(bugfix_ndjson):
    # "plan_tier" isn't in _LOW_CARDINALITY_HINTS, but only has 2 distinct
    # sampled values -> should still be classified as LowCardinality(String).
    ddl = tools.Tool_Infer_Schema(bugfix_ndjson, "spec text", "express_checkout")
    assert "plan_tier LowCardinality(String)" in ddl


def test_generate_mv_creates_daily_segment_rollup():
    ddl = (
        "CREATE TABLE IF NOT EXISTS express_checkout\n"
        "(\n    timestamp DateTime,\n    user_id String,\n"
        "    device_type LowCardinality(String),\n    event LowCardinality(String)\n)\n"
        "ENGINE = MergeTree\nPARTITION BY toYYYYMM(timestamp)\nORDER BY (timestamp, user_id)\n"
        "TTL timestamp + INTERVAL 12 MONTH;"
    )
    mv = tools.Tool_Generate_MV("express_checkout", ddl)
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS express_checkout_daily_mv" in mv
    assert "toYYYYMMDD(timestamp)" in mv
    assert "device_type" in mv
    assert "-- justification:" in mv


def test_generate_mv_skips_when_no_segment_column_present():
    ddl = (
        "CREATE TABLE IF NOT EXISTS tiny\n(\n    timestamp DateTime,\n    user_id String\n)\n"
        "ENGINE = MergeTree\nPARTITION BY toYYYYMM(timestamp)\nORDER BY (timestamp, user_id)\n"
        "TTL timestamp + INTERVAL 12 MONTH;"
    )
    mv = tools.Tool_Generate_MV("tiny", ddl)
    assert mv == ""


def test_execute_ddl_success_writes_versioned_schema_registry_row():
    from unittest.mock import patch
    ddl = "CREATE TABLE IF NOT EXISTS t1 (timestamp DateTime, user_id String) ENGINE=MergeTree ORDER BY (timestamp, user_id)"
    with patch("atlys_agentic.tools.ch_client.command") as mock_command, \
         patch("atlys_agentic.tools.chdb_client.init_schema"), \
         patch("atlys_agentic.tools.chdb_client.run") as mock_chdb_run:
        mock_chdb_run.side_effect = [[], None]
        result = tools.Tool_Execute_DDL(ddl, "t1", spec_id="01_express_checkout")
    mock_command.assert_called_once_with(ddl)
    assert result == {"status": "ok", "table": "t1", "version": 1, "error": None}


def test_execute_ddl_failure_rolls_back_and_reports_error():
    from unittest.mock import patch
    ddl = "CREATE TABLE IF NOT EXISTS t2 (bad syntax"
    with patch("atlys_agentic.tools.ch_client.command", side_effect=Exception("syntax error")) as mock_command, \
         patch("atlys_agentic.tools.ch_client.select") as mock_select:
        result = tools.Tool_Execute_DDL(ddl, "t2", spec_id="01_express_checkout")
    assert result["status"] == "rolled_back"
    assert "syntax error" in result["error"]
    mock_select.assert_called_once_with("DROP TABLE IF EXISTS t2")


def test_analytics_compute_rejects_non_select():
    with pytest.raises(ValueError, match="SELECT-only"):
        tools.Tool_Analytics_Compute("DROP TABLE purchase_completed")
    with pytest.raises(ValueError, match="SELECT-only"):
        tools.Tool_Analytics_Compute("INSERT INTO x VALUES (1)")


def test_analytics_compute_returns_json_rows():
    from unittest.mock import patch
    with patch("atlys_agentic.tools.ch_client.select", return_value=[{"c": 42}]) as mock_select:
        result = tools.Tool_Analytics_Compute("SELECT count() AS c FROM purchase_completed")
    mock_select.assert_called_once_with("SELECT count() AS c FROM purchase_completed")
    assert result == {"rows": [{"c": 42}]}


def test_context_diff_flags_conversion_rate_denominator_conflict():
    from unittest.mock import patch
    with patch("atlys_agentic.tools.chdb_client.run", return_value=[
        {"key": "conversion_rate#0", "definition": "completed purchases / sessions"},
        {"key": "funnel_conversion#0", "definition": "purchase_completed users / application_started"},
    ]):
        result = tools.Tool_Context_Diff("express_checkout", ["timestamp", "user_id", "device_type"])
    assert any("denominator" in c.lower() for c in result["conflicts"])


def test_context_diff_flags_undocumented_column_as_gap():
    from unittest.mock import patch
    with patch("atlys_agentic.tools.chdb_client.run", return_value=[]):
        result = tools.Tool_Context_Diff("document_uploaded", ["failed_attempt_threshold"])
    assert any("failed_attempt_threshold" in g for g in result["gaps"])


def test_context_diff_flags_new_columns_as_additions():
    from unittest.mock import patch
    with patch("atlys_agentic.tools.chdb_client.run", return_value=[]):
        result = tools.Tool_Context_Diff("express_checkout", ["shown_amount", "otp_attempts"])
    assert "express_checkout.shown_amount" in result["additions"]
    assert "express_checkout.otp_attempts" in result["additions"]


def test_context_upsert_increments_version_and_writes_changelog():
    from unittest.mock import patch
    calls = []

    def fake_run(sql, fmt="JSON"):
        calls.append(sql)
        if sql.strip().startswith("SELECT max(version)"):
            return [{"v": 2}]
        if sql.strip().startswith("SELECT definition FROM business_context WHERE key"):
            return [{"definition": "old definition"}]
        return None

    with patch("atlys_agentic.tools.chdb_client.run", side_effect=fake_run):
        version = tools.Tool_Context_Upsert(
            section="Metric definitions",
            key="conversion_rate",
            definition="purchases / application_started (canonical, per Context Agent)",
            agent="context_librarian",
            trace_id="trace-123",
        )
    assert version == 3
    insert_calls = [c for c in calls if c.strip().startswith("INSERT INTO business_context")]
    changelog_calls = [c for c in calls if c.strip().startswith("INSERT INTO context_changelog")]
    assert len(insert_calls) == 1
    assert len(changelog_calls) == 1
    assert "old definition" in changelog_calls[0]
    assert "trace-123" in changelog_calls[0]


def test_confidence_high_for_large_n_large_effect_matching_known_issue():
    result = tools.Tool_Score_Confidence(
        sample_size=50_000, effect_size_pct=15.0, known_issue_match=True, cut_consistency=0.9
    )
    assert result["score"] >= 0.8
    assert "K" in result["rationale"] or "known issue" in result["rationale"].lower()


def test_confidence_low_for_small_n_single_cut_blip():
    result = tools.Tool_Score_Confidence(
        sample_size=40, effect_size_pct=3.0, known_issue_match=False, cut_consistency=0.2
    )
    assert result["score"] < 0.4


def test_confidence_score_always_in_unit_interval():
    for n, eff, match, cons in [(0, 0, False, 0), (10**7, 500, True, 1.0)]:
        result = tools.Tool_Score_Confidence(n, eff, match, cons)
        assert 0.0 <= result["score"] <= 1.0


def test_emit_viz_writes_snapshot_with_three_views(tmp_path):
    from unittest.mock import patch
    import json as _json
    fixture = {
        "schema_registry": [{"table": "express_checkout", "version": 1}],
        "insights": [{"question": "does express lift conversion?", "confidence": 0.82}],
        "context_changelog": [{"change_type": "context_upsert", "agent": "context_librarian"}],
    }

    def fake_run(sql, fmt="JSON"):
        if "schema_registry" in sql:
            return fixture["schema_registry"]
        if "FROM insights" in sql:
            return fixture["insights"]
        if "context_changelog" in sql:
            return fixture["context_changelog"]
        return []

    with patch("atlys_agentic.tools.chdb_client.run", side_effect=fake_run), \
         patch("atlys_agentic.tools.paths.OUTPUTS_DIR", tmp_path):
        result = tools.Tool_Emit_Viz()

    assert result["schema_history"] == fixture["schema_registry"]
    assert result["insights"] == fixture["insights"]
    assert result["context_changelog"] == fixture["context_changelog"]
    snapshot = _json.loads((tmp_path / "viz_snapshot.json").read_text())
    assert snapshot == result

