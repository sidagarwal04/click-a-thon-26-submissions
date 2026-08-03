"""
Integration test for main.py's run_pipeline() -- the actual orchestrator
entry point.

Every other test in this repo constructs ContextAgent/AnalyticsAgent/
InstrumentationAgent directly with the correct signatures, which is exactly
why a previous version of run_pipeline() could call
`ContextAgent(str(path), clickhouse_client=client)` -- a signature that never
matched the real class -- and no test ever caught it: nothing imported
main.py. This test imports and calls run_pipeline() itself (with
clickhouse_connect.get_client and OpenRouter mocked out) so a wiring break
like that fails `pytest`, not a live run.
"""

import json
from unittest.mock import MagicMock, patch

import main


def _mock_query_side_effect(sql, *args, **kwargs):
    """Route mocked ClickHouse responses by recognizable query shape -- good
    enough to let run_pipeline() exercise its real control flow without a
    live ClickHouse service, not a claim of correct business-logic output."""
    result = MagicMock()
    s_lower = (sql if isinstance(sql, str) else str(sql)).lower()

    if "as users" in s_lower:
        result.column_names = ["device_type", "users", "events"]
        result.result_rows = [("ios", 10, 12)]
    elif "windowfunnel(" in s_lower:
        result.column_names = []
        result.result_rows = [tuple([0] * 10)]
    elif "count()" in s_lower:
        result.column_names = ["count()"]
        result.result_rows = [(0,)]
    else:
        result.column_names = []
        result.result_rows = []
    return result


def _make_mock_client():
    client = MagicMock()
    client.query.side_effect = _mock_query_side_effect
    client.command.return_value = None
    client.insert.return_value = None
    return client


def _write_spec(spec_dir):
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(
        "# Test Feature\n\n"
        "## User actions (raw events emitted)\n"
        "- `test_event_shown` — shown (`amount`)\n\n"
        "## Questions the PM will ask\n"
        "- Does this convert?\n"
    )
    events = [
        {
            "event": "test_event_shown",
            "id": "f105934b4c083002827058f3ac25e9c6",
            "timestamp": "2026-06-08T06:00:00.000",
            "user_id": "testuser000000000000000001",
            "application_id": "app000000000000000000000000001",
            "device_type": "ios",
            "amount": 100,
        }
    ]
    with open(spec_dir / "events.ndjson", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_run_pipeline_completes_without_a_real_clickhouse_service(tmp_path):
    spec_dir = tmp_path / "test_spec"
    _write_spec(spec_dir)

    mock_client = _make_mock_client()

    with patch("main.clickhouse_connect.get_client", return_value=mock_client), \
         patch("main.get_config") as mock_get_config:
        ch_config = MagicMock(host="fake-host", port=8443, user="default", password="x", database="atlys", secure=True)
        lf_config = MagicMock(enabled=False)
        or_config = MagicMock(enabled=False)
        mock_get_config.return_value = (ch_config, lf_config, or_config)

        # Must not raise -- this is the exact class of break (a constructor
        # signature mismatch) that shipped previously with zero test coverage.
        main.run_pipeline(str(spec_dir))

    # A real DDL/insert/query call happened against the mocked client.
    assert mock_client.command.called
    assert mock_client.insert.called

    # The pipeline produced its three output artifacts.
    assert (spec_dir / "generated_schema.sql").exists()
    assert (spec_dir / "insight_summary.md").exists()
    assert (spec_dir / "dashboard.html").exists()
