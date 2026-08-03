"""Analytics Agent: query safety, push-down discipline, and the insight contract."""

from __future__ import annotations

from prism_ch.agents.analytics import (
    MAX_INTERPRETABLE_ROWS,
    QUERY_SETTINGS,
    REQUIRED_CUTS,
    AnalyticsAgent,
    _is_destructive,
    _is_raw_select,
)
from prism_ch.agents.context_store import ContextStore
from prism_ch.agents.types import (
    AnalysisQuestion,
    ContextEntry,
    ContextSnapshot,
    QueryResult,
    parse_insights,
)


class RecordingClient:
    """Captures queries and the settings they were run with."""

    def __init__(self, rows=None, columns=None, fail: str | None = None) -> None:  # noqa: ANN001
        self.calls: list[tuple[str, dict]] = []
        self._rows = rows if rows is not None else [["ios", 0.61], ["android", 0.76]]
        self._columns = columns or ["device", "rate"]
        self._fail = fail

    def command(self, sql: str) -> None: ...

    def insert(self, **kwargs: object) -> None: ...

    def query(self, sql: str, **kwargs: object):  # noqa: ANN202
        self.calls.append((sql, dict(kwargs)))
        if self._fail:
            raise RuntimeError(self._fail)

        class R:
            pass

        r = R()
        if "system.columns" in sql:
            r.column_names = ["table", "name", "type"]
            r.result_rows = [("prism_events", "device", "LowCardinality(String)")]
        elif "system.tables" in sql:
            r.column_names = ["name", "total_rows"]
            r.result_rows = [("prism_events", 50000)]
        elif "max(version)" in sql:
            r.column_names = ["v"]
            r.result_rows = [[3]]
        elif "context_versions" in sql:
            r.column_names = ["created_at", "source"]
            r.result_rows = [["2026-08-01 00:00:00", "refresh"]]
        elif "context_entries" in sql:
            r.column_names = ["kind", "key", "value", "source", "detail"]
            r.result_rows = [["metric", "conversion", "a/b", "doc", ""]]
        elif "context_issues" in sql:
            r.column_names = ["kind", "severity", "subject", "detail"]
            r.result_rows = []
        else:
            r.column_names = self._columns
            r.result_rows = self._rows
        return r


def _agent(make_settings, client, **over):  # noqa: ANN001, ANN202
    settings = make_settings(
        clickhouse_target="cloud", database="atlys", anthropic_api_key="", **over
    )
    return AnalyticsAgent(settings, client)


# --- raw-data guard -----------------------------------------------------------


def test_select_star_is_rejected() -> None:
    assert _is_raw_select("SELECT * FROM events") is not None
    assert _is_raw_select("  select *  from  events") is not None


def test_no_group_by_no_aggregate_is_rejected() -> None:
    assert _is_raw_select("SELECT device, ts FROM events WHERE x = 1") is not None


def test_aggregate_without_group_by_passes() -> None:
    assert _is_raw_select("SELECT count() FROM events") is None


def test_group_by_passes() -> None:
    assert _is_raw_select("SELECT device, count() FROM events GROUP BY device") is None


def test_select_star_blocked_at_execute(make_settings) -> None:  # noqa: ANN001
    """SELECT * queries never reach the database."""
    client = RecordingClient()
    agent = _agent(make_settings, client)
    result = agent.execute(
        [AnalysisQuestion("q", "SELECT * FROM events", cut="overall")],
        context_version=1,
    )[0]
    assert not result.ok
    assert "raw rows" in result.error
    # The query should NOT have been sent to ClickHouse.
    analytical = [c for c in client.calls if "system" not in c[0]]
    assert len(analytical) == 0


# --- destructive-statement guard rail -------------------------------------------


def test_select_and_cte_are_allowed() -> None:
    assert _is_destructive("SELECT count() FROM t") is None
    assert _is_destructive("  select count() from t") is None
    assert _is_destructive("WITH x AS (SELECT 1) SELECT * FROM x") is None


def test_drop_table_is_rejected() -> None:
    assert _is_destructive("DROP TABLE prism_events") is not None


def test_delete_from_is_rejected() -> None:
    assert _is_destructive("DELETE FROM prism_events WHERE user_id = 1") is not None


def test_truncate_is_rejected() -> None:
    assert _is_destructive("TRUNCATE TABLE prism_events") is not None


def test_alter_drop_column_is_rejected() -> None:
    assert _is_destructive("ALTER TABLE prism_events DROP COLUMN user_id") is not None


def test_other_mutations_are_rejected() -> None:
    for sql in (
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "CREATE TABLE t (a String)",
        "RENAME TABLE a TO b",
    ):
        assert _is_destructive(sql) is not None, sql


def test_empty_query_is_rejected() -> None:
    assert _is_destructive("") is not None


def test_destructive_query_never_reaches_the_database(make_settings) -> None:  # noqa: ANN001
    client = RecordingClient()
    agent = _agent(make_settings, client)
    result = agent.execute(
        [AnalysisQuestion("q", "DROP TABLE prism_events", cut="overall")],
        context_version=1,
    )[0]
    assert not result.ok
    assert "SELECT/WITH" in result.error
    analytical = [c for c in client.calls if "system" not in c[0]]
    assert len(analytical) == 0


def test_plan_rejects_a_destructive_question() -> None:
    """`plan()`'s validation loop applies the same guard as `execute()`'s
    pre-flight check - a destructive statement never survives planning."""
    from prism_ch.agents.types import parse_questions

    questions = parse_questions(
        {"questions": [{"question": "wipe it", "sql": "DROP TABLE t", "cut": "overall"}]}
    )
    assert _is_destructive(questions[0].sql) is not None


# --- query safety (`agent-query-safety`) --------------------------------------


def test_every_query_carries_safety_settings(make_settings) -> None:  # noqa: ANN001
    client = RecordingClient()
    agent = _agent(make_settings, client)
    agent.execute(
        [AnalysisQuestion("q", "SELECT count() FROM t", cut="overall")], context_version=3
    )

    analytical = [c for c in client.calls if "system" not in c[0]]
    settings = analytical[0][1]["settings"]
    assert settings["max_execution_time"] == 30
    assert settings["max_result_rows"] == 10_000
    assert settings["timeout_before_checking_execution_speed"] == 0
    assert settings["readonly"] == 1


def test_safety_settings_match_the_rule() -> None:
    for key in (
        "max_execution_time",
        "max_rows_to_read",
        "max_bytes_to_read",
        "max_result_rows",
        "result_overflow_mode",
        "timeout_before_checking_execution_speed",
        "readonly",
    ):
        assert key in QUERY_SETTINGS


def test_execute_signals_each_query_before_and_after_running(make_settings) -> None:  # noqa: ANN001
    """The live Activity log needs to see a query while it is in flight, not
    only once the whole `run_queries` step is over - execute() must emit it
    before calling the client, then again once the row count is known."""
    from prism_ch import tracing

    agent = _agent(make_settings, RecordingClient())
    events: list[dict] = []
    token = tracing.set_progress_sink(events.append)
    try:
        agent.execute(
            [AnalysisQuestion("q", "SELECT count() FROM t", cut="overall")], context_version=1
        )
    finally:
        tracing.clear_progress_sink(token)

    sql_events = [e for e in events if e["type"] == "sql"]
    assert [e["rows"] for e in sql_events] == [None, 2]  # RecordingClient returns 2 rows


def test_a_failing_query_does_not_abort_the_run(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings, RecordingClient(fail="Code: 47. Unknown identifier"))
    results = agent.execute(
        [
            AnalysisQuestion("a", "SELECT count() FROM bad"),
            AnalysisQuestion("b", "SELECT count() FROM t"),
        ],
        context_version=1,
    )
    assert len(results) == 2
    assert all(not r.ok for r in results)
    assert "Unknown identifier" in results[0].error


# --- push-down discipline (A10) -----------------------------------------------


def test_an_unaggregated_result_is_rejected(make_settings) -> None:  # noqa: ANN001
    """Raw rows mean the query failed to push computation into ClickHouse."""
    wide = [[i, i * 2] for i in range(MAX_INTERPRETABLE_ROWS + 50)]
    agent = _agent(make_settings, RecordingClient(rows=wide))
    result = agent.execute(
        [AnalysisQuestion("q", "SELECT device, count() FROM t GROUP BY device")],
        context_version=1,
    )[0]

    assert not result.ok
    assert "aggregate further" in result.error
    assert len(result.rows) == MAX_INTERPRETABLE_ROWS


def test_a_small_aggregate_passes(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings, RecordingClient())
    result = agent.execute(
        [AnalysisQuestion("q", "SELECT count() FROM t")], context_version=1
    )[0]
    assert result.ok
    assert result.columns == ["device", "rate"]


# --- required cuts ------------------------------------------------------------


def test_required_cuts_include_the_brief_dimensions() -> None:
    assert {"overall", "trend", "device", "geo", "funnel", "segment"} <= REQUIRED_CUTS


# --- context freshness (C6 / T7) ----------------------------------------------


def test_discovery_reads_the_latest_context_version(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings, RecordingClient())
    snapshot, tables = agent.discover()
    assert snapshot.version == 3
    assert tables and tables[0]["table"] == "prism_events"


def test_discovery_includes_row_counts(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings, RecordingClient())
    _, tables = agent.discover()
    assert tables[0].get("row_count") == 50000


def test_no_llm_yields_no_questions_rather_than_guesses(make_settings) -> None:  # noqa: ANN001
    from prism_ch.agents.types import ContextSnapshot

    agent = _agent(make_settings, RecordingClient())
    questions = agent.plan(ContextSnapshot(1, "", "t"), [], None)
    assert questions == []


def test_no_llm_run_returns_empty_report(make_settings) -> None:  # noqa: ANN001
    """When no LLM is configured, run() returns an empty report, not an error."""
    agent = _agent(make_settings, RecordingClient())
    report = agent.run()
    assert report.insights == []
    assert report.queries_run == 0


# --- the insight contract -----------------------------------------------------


def test_an_insight_without_a_why_is_discarded() -> None:
    """A number with no causal hypothesis is a chart, not an insight."""
    parsed = parse_insights(
        {
            "insights": [
                {"headline": "conversion is 12%", "confidence": 0.9},
                {"headline": "iOS lags Android", "why": "OTP autofill issue", "confidence": 0.7},
            ]
        }
    )
    assert [i.headline for i in parsed] == ["iOS lags Android"]


def test_insight_fields_round_trip() -> None:
    i = parse_insights(
        {
            "insights": [
                {
                    "headline": "h", "detail": "d", "why": "w", "confidence": 0.42,
                    "cut": "device", "evidence": {"ios": 0.61},
                    "context_refs": ["K3"], "recommendation": "r",
                }
            ]
        }
    )[0]
    d = i.as_dict()
    assert d["confidence"] == 0.42
    assert d["context_refs"] == ["K3"]
    assert d["recommendation"] == "r"


def test_interpret_reports_nothing_when_no_query_succeeded(make_settings) -> None:  # noqa: ANN001
    from prism_ch.agents.types import ContextSnapshot, QueryResult

    agent = _agent(make_settings, RecordingClient())
    snapshot = ContextSnapshot(5, "", "t", [ContextEntry("metric", "m", "a/b")])
    failed = [QueryResult(AnalysisQuestion("q", "SELECT count()"), error="boom")]
    report = agent.interpret(snapshot, failed, None)

    assert report.insights == []
    assert report.context_version == 5
    # Even with nothing to interpret, the attempted queries must still be
    # visible - the UI has to be able to show what was tried and why it failed.
    assert report.queries == failed


def test_interpret_attaches_the_executed_queries_to_the_report(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """Each insight card in the UI shows the SQL behind it, matched by `cut` -
    that only works if the report carries every executed QueryResult (with its
    SQL text) alongside the insights, not just an aggregate count."""
    import prism_ch.agents.llm as llm_module
    from prism_ch.agents.types import ContextSnapshot, QueryResult

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="test-key")
    agent = AnalyticsAgent(settings, RecordingClient())
    monkeypatch.setattr(
        llm_module,
        "complete",
        lambda settings, **kw: {
            "summary": "s",
            "insights": [
                {
                    "headline": "h", "detail": "d", "why": "w", "confidence": 0.5,
                    "cut": "device",
                }
            ],
        },
    )
    snapshot = ContextSnapshot(2, "", "t", [ContextEntry("metric", "m", "a/b")])
    results = [
        QueryResult(
            AnalysisQuestion("device split", "SELECT device, count() FROM t GROUP BY device", cut="device"),
            columns=["device", "n"],
            rows=[["ios", 3]],
        )
    ]

    report = agent.interpret(snapshot, results, None)

    assert report.queries == results
    as_dict = report.as_dict()
    assert as_dict["queries"][0]["sql"] == "SELECT device, count() FROM t GROUP BY device"
    assert as_dict["queries"][0]["cut"] == "device"


def test_relevant_context_uses_semantic_hits_for_focus(make_settings, monkeypatch) -> None:  # noqa: ANN001
    import prism_ch.agents.llm as llm_module

    agent = _agent(make_settings, RecordingClient())
    first = ContextEntry("metric", "checkout", "a/b")
    snapshot = ContextSnapshot(3, "", "t", [first, ContextEntry("metric", "other", "c/d")])
    monkeypatch.setattr(ContextStore, "has_embeddings", lambda self, version: True)
    monkeypatch.setattr(
        ContextStore,
        "semantic_search",
        lambda self, query, *, version, limit: [
            {"kind": "metric", "key": "checkout", "score": 0.9}
        ],
    )
    monkeypatch.setattr(llm_module, "embed", lambda settings, texts: [[0.1]])

    assert agent._relevant_context(snapshot, "checkout", kinds=("metric",)) == [first]


def test_prompts_put_business_context_before_schema_and_results(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings, RecordingClient())
    snapshot = ContextSnapshot(1, "", "t", [ContextEntry("metric", "m", "a/b")])
    plan = agent._plan_prompt(snapshot, [{"table": "events", "columns": []}], None)
    result = QueryResult(AnalysisQuestion("q", "SELECT count()"), columns=["c"], rows=[[1]])
    interpretation = agent._interpret_prompt(snapshot, [result], None)

    assert plan.index("# Business context") < plan.index("# Schema")
    assert interpretation.index("# Business context first") < interpretation.index(
        "# Query results"
    )


def test_plan_prompt_exposes_rollup_rationale(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings, RecordingClient())
    snapshot = ContextSnapshot(
        1,
        "",
        "t",
        [ContextEntry("rollup", "daily_revenue", "dashboard", detail="sumState(amount)")],
    )
    prompt = agent._plan_prompt(snapshot, [], None)
    assert "# Pre-aggregated rollups" in prompt
    # The check is mandatory, not a soft preference - a raw-table query must
    # be justified, not just permitted.
    assert "MUST check" in prompt
