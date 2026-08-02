from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

RUNNER_PATH = Path(__file__).parents[1] / "analytics_runner.py"
SPEC = importlib.util.spec_from_file_location("analytics_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class Result:
    def __init__(self, columns, rows):
        self.column_names = columns
        self.result_rows = rows


class Client:
    def __init__(self, result=None, results=None):
        self.result = result or Result([], [])
        self.results = list(results or [])
        self.inserts = []
        self.queries = []

    def query(self, sql, **kwargs):
        self.queries.append((sql, kwargs))
        if self.results:
            return self.results.pop(0)
        return self.result

    def insert(self, table, rows, column_names):
        self.inserts.append((table, rows, column_names))


def request_b64(payload):
    return base64.b64encode(json.dumps(payload).encode()).decode()


def instrumentation_handoff():
    return {
        "status": "completed",
        "spec_md": "# New feature\n\nAnalyse express checkout.",
        "event_tables": {
            "feature_shown": "default.inv_test_events",
            "feature_completed": "default.inv_test_completed",
        },
        "tables": [
            {"name": "default.inv_test_events", "description": "Raw shown events"},
            {"name": "default.inv_test_completed", "description": "Raw completions"},
        ],
        "materialized_views": [],
        "aggregations": [],
        "decision_trace": [],
    }


def handoff_catalog_result():
    return Result(
        ["database", "name", "engine", "total_rows", "create_table_query"],
        [
            (
                "default",
                "inv_test_completed",
                "MergeTree",
                10,
                "CREATE TABLE default.inv_test_completed (event_id UUID) "
                "ENGINE = MergeTree ORDER BY event_id",
            ),
            (
                "default",
                "inv_test_events",
                "MergeTree",
                20,
                "CREATE TABLE default.inv_test_events (event_id UUID) "
                "ENGINE = MergeTree ORDER BY event_id",
            ),
        ],
    )


def base_query_request():
    run_id = str(uuid4())
    return {
        "run_id": run_id,
        "feature_slug": "unseen_feature",
        "question_id": "q1",
        "source_scope": "feature",
        "allowed_tables": ["default.feature_event"],
        "table_scopes": {"default.feature_event": "feature"},
        "protected_columns": ["user_id", "application_id"],
        "expected_columns": ["device_type", "events"],
        "boundary_columns": ["run_id", "event_time"],
        "max_result_rows": 100,
        "sql": (
            "SELECT device_type, uniqExact(event_id) AS events "
            "FROM default.feature_event "
            f"WHERE run_id = '{run_id}' "
            "GROUP BY device_type LIMIT 100"
        ),
    }


def schema_result(*tables):
    return Result(
        ["content"],
        [
            (
                json.dumps(
                    {
                        "tables": [
                            {
                                "database": table.split(".")[0],
                                "name": table.split(".")[1],
                            }
                            for table in tables
                        ]
                    }
                ),
            )
        ],
    )


def test_request_transport_is_one_bounded_json_object():
    payload = {"action": "list_run", "run_id": str(uuid4())}
    assert runner.decode_request(request_b64(payload)) == payload
    with pytest.raises(runner.RunnerError, match="valid base64"):
        runner.decode_request("not base64")
    with pytest.raises(runner.RunnerError, match="one JSON object"):
        runner.decode_request(request_b64([1, 2]))


def test_business_context_loads_latest_published_chunks_with_provenance():
    context_id = str(uuid4())
    chunk_ids = [str(uuid4()), str(uuid4())]
    client = Client(
        results=[
            Result(
                ["context_id", "version_number", "chunk_count", "latest_valid_from"],
                [(context_id, 7, 2, "2026-01-01 00:00:00")],
            ),
            Result(
                [
                    "chunk_id",
                    "chunk_ordinal",
                    "section_type",
                    "entity_type",
                    "entity_id",
                    "confidence",
                    "content_sha256",
                    "chunk_text",
                    "metadata_json",
                ],
                [
                    (chunk_ids[0], 0, "overview", "business", "atlys", 1.0, "a" * 64, "first", "{}"),
                    (chunk_ids[1], 1, "issue", "known_issue", "K1", 0.8, "b" * 64, "second", "{}"),
                ],
            ),
        ]
    )
    content, provenance = runner.load_business_context(client)
    assert content == "first\n\nsecond"
    assert provenance == {
        "source_table": "agent.business_logic_embeddings_v1",
        "context_id": context_id,
        "version_number": 7,
        "chunk_count": 2,
        "chunk_ids": chunk_ids,
        "chunk_content_sha256": ["a" * 64, "b" * 64],
    }
    select_list = client.queries[1][0].casefold().split(" from ", 1)[0]
    assert "embedding" not in select_list
    assert "valid_to IS NULL" in client.queries[0][0]


def test_business_context_missing_blocks():
    with pytest.raises(runner.RunnerError, match="no current published context"):
        runner.load_business_context(Client(Result([], [])))


def test_bootstrap_reads_context_before_any_clickhouse_write(monkeypatch):
    client = Client(result=handoff_catalog_result())
    request = {
        "run_id": str(uuid4()),
        "feature_slug": "new_feature",
        "instrumentation_handoff": instrumentation_handoff(),
        "coverage_ledger": [{"question_id": "q1", "status": "pending"}],
    }

    def missing_context():
        raise runner.RunnerError(
            "missing_context", "missing", status="missing_context"
        )

    monkeypatch.setattr(runner, "load_business_context", lambda client: missing_context())
    with pytest.raises(runner.RunnerError):
        runner.action_bootstrap(client, request)
    assert client.inserts == []

    context_source = {
        "source_table": "agent.business_logic_embeddings_v1",
        "context_id": str(uuid4()),
        "version_number": 1,
        "chunk_count": 1,
        "chunk_ids": [str(uuid4())],
        "chunk_content_sha256": ["a" * 64],
    }
    monkeypatch.setattr(
        runner, "load_business_context", lambda client: ("current", context_source)
    )
    response = runner.action_bootstrap(client, request)
    assert response["context"] == "current"
    assert response["feature_tables"] == [
        "default.inv_test_events",
        "default.inv_test_completed",
    ]
    assert response["context_source"] == context_source
    assert len(client.queries) == 2
    assert len(client.inserts) == 6
    assert [entry[1][0][4] for entry in client.inserts] == [
        "feature_spec",
        "instrumentation_handoff",
        "instrumentation_ddl",
        "instrumentation_ddl",
        "context_snapshot",
        "manifest",
    ]
    assert (
        json.loads(client.inserts[-1][1][0][8])["coverage_ledger"]
        == request["coverage_ledger"]
    )


def test_name_based_instrumentation_contract_validates_catalog():
    validated = runner._validate_instrumentation_handoff(instrumentation_handoff())
    assert validated["declared_tables"] == [
        "default.inv_test_events",
        "default.inv_test_completed",
    ]
    assert validated["raw_event_tables"] == [
        "default.inv_test_events",
        "default.inv_test_completed",
    ]
    invalid = instrumentation_handoff()
    invalid["event_tables"]["outside"] = "default.not_declared"
    with pytest.raises(runner.RunnerError, match="absent from tables"):
        runner._validate_instrumentation_handoff(invalid)


def test_handoff_catalog_requires_nonempty_raw_tables_and_live_views():
    handoff = instrumentation_handoff()
    handoff["tables"].append(
        {"name": "default.daily_target", "description": "Aggregate target"}
    )
    handoff["materialized_views"] = [
        {"name": "default.daily_mv", "target_table": "default.daily_target"}
    ]
    validated = runner._validate_instrumentation_handoff(handoff)
    client = Client(
        Result(
            ["database", "name", "engine", "total_rows", "create_table_query"],
            [
                (
                    "default", "daily_mv", "MaterializedView", 0,
                    "CREATE MATERIALIZED VIEW default.daily_mv "
                    "TO default.daily_target AS SELECT 1",
                ),
                (
                    "default", "daily_target", "AggregatingMergeTree", 0,
                    "CREATE TABLE default.daily_target (x UInt8) "
                    "ENGINE=AggregatingMergeTree ORDER BY x",
                ),
                (
                    "default", "inv_test_completed", "MergeTree", 10,
                    "CREATE TABLE default.inv_test_completed (x UInt8) "
                    "ENGINE=MergeTree ORDER BY x",
                ),
                (
                    "default", "inv_test_events", "MergeTree", 20,
                    "CREATE TABLE default.inv_test_events (x UInt8) "
                    "ENGINE=MergeTree ORDER BY x",
                ),
            ],
        )
    )
    rows = runner._resolve_handoff_catalog(
        client,
        validated["declared_tables"],
        validated["raw_event_tables"],
        validated["declared_views"],
    )
    assert len(rows) == 4

    empty = Client(
        Result(
            ["database", "name", "engine", "total_rows", "create_table_query"],
            [
                (
                    "default", "inv_test_completed", "MergeTree", 0,
                    "CREATE TABLE default.inv_test_completed (x UInt8) "
                    "ENGINE=MergeTree ORDER BY x",
                ),
                (
                    "default", "inv_test_events", "MergeTree", 20,
                    "CREATE TABLE default.inv_test_events (x UInt8) "
                    "ENGINE=MergeTree ORDER BY x",
                ),
            ],
        )
    )
    base = runner._validate_instrumentation_handoff(instrumentation_handoff())
    with pytest.raises(runner.RunnerError, match="contain no data"):
        runner._resolve_handoff_catalog(
            empty,
            base["declared_tables"],
            base["raw_event_tables"],
            base["declared_views"],
        )


def test_discover_returns_live_schema_keys_defaults_and_indices():
    run_id = str(uuid4())
    table_columns = [
        "database",
        "name",
        "engine",
        "sorting_key",
        "primary_key",
        "partition_key",
        "sampling_key",
        "total_rows",
        "total_bytes",
        "comment",
        "create_table_query",
    ]
    column_columns = [
        "database",
        "table",
        "name",
        "type",
        "comment",
        "position",
        "default_kind",
        "default_expression",
        "codec_expression",
        "ttl_expression",
    ]
    index_columns = ["database", "table", "name", "type_full", "expr", "granularity"]
    client = Client(
        results=[
            Result(
                table_columns,
                [
                    (
                        "default",
                        "feature_shown",
                        "MergeTree",
                        "event_time, event_id",
                        "event_time, event_id",
                        "toYYYYMM(event_time)",
                        "",
                        1000,
                        4096,
                        "one row per shown event",
                        "CREATE TABLE default.feature_shown (...) ENGINE=MergeTree",
                    )
                ],
            ),
            Result(
                column_columns,
                [
                    (
                        "default",
                        "feature_shown",
                        "event_time",
                        "DateTime64(3)",
                        "event occurrence time",
                        1,
                        "",
                        "",
                        "DoubleDelta, ZSTD(1)",
                        "",
                    )
                ],
            ),
            Result(
                index_columns,
                [
                    (
                        "default",
                        "feature_shown",
                        "device_idx",
                        "set(100)",
                        "device_type",
                        1,
                    )
                ],
            ),
        ]
    )
    response = runner.action_discover(
        client,
        {
            "run_id": run_id,
            "feature_slug": "feature",
            "tables": ["default.feature_shown"],
        },
    )
    assert response["table_count"] == 1
    assert response["column_count"] == 1
    assert response["skipping_index_count"] == 1
    assert response["schema"]["tables"][0]["sorting_key"] == "event_time, event_id"
    assert response["schema"]["columns"][0]["codec_expression"]
    assert response["schema"]["skipping_indices"][0]["expr"] == "device_type"
    assert len(client.queries) == 3
    assert "system.data_skipping_indices" in client.queries[2][0]
    assert len(client.inserts) == 1


def test_sql_policy_accepts_bounded_aggregate_and_cte_join():
    request = base_query_request()
    assert runner.validate_aggregate_sql(request["sql"], request) == {
        "default.feature_event"
    }

    request["allowed_tables"].append("default.feature_success")
    request["table_scopes"]["default.feature_success"] = "feature"
    request["sql"] = f"""
        WITH exposures AS (
          SELECT device_type, uniqExact(application_id) AS exposed
          FROM default.feature_event
          WHERE run_id = '{request["run_id"]}'
          GROUP BY device_type
        ), successes AS (
          SELECT device_type, uniqExact(application_id) AS converted
          FROM default.feature_success
          WHERE run_id = '{request["run_id"]}'
          GROUP BY device_type
        )
        SELECT e.device_type, sum(e.exposed) AS exposed, sum(s.converted) AS converted
        FROM exposures AS e
        INNER JOIN successes AS s USING device_type
        GROUP BY e.device_type
        LIMIT 100
    """
    assert runner.validate_aggregate_sql(request["sql"], request) == {
        "default.feature_event",
        "default.feature_success",
    }


@pytest.mark.parametrize(
    "sql, message",
    [
        (
            "SELECT * FROM default.feature_event WHERE event_time >= now() - 1 LIMIT 10",
            "SELECT",
        ),
        ("DROP TABLE default.feature_event", "only SELECT"),
        (
            (
                "SELECT device_type FROM default.feature_event "
                "WHERE event_time >= now() - INTERVAL 1 DAY LIMIT 10"
            ),
            "aggregate evidence",
        ),
        (
            (
                "SELECT any(user_id) FROM default.feature_event "
                "WHERE event_time >= now() - INTERVAL 1 DAY LIMIT 10"
            ),
            "row-sampling",
        ),
        (
            "SELECT count() FROM default.feature_event WHERE device_type = 'ios' LIMIT 10",
            "run or time boundary",
        ),
        (
            (
                "SELECT count() FROM default.feature_event "
                "WHERE event_time >= now() - INTERVAL 1 DAY"
            ),
            "final LIMIT",
        ),
        (
            (
                "SELECT count() FROM secret.rows "
                "WHERE event_time >= now() - INTERVAL 1 DAY LIMIT 10"
            ),
            "outside the allowlist",
        ),
        (
            (
                "SELECT count() FROM default.feature_event "
                "WHERE event_time >= now() - INTERVAL 1 DAY LIMIT 10; SELECT 1"
            ),
            "one SQL statement",
        ),
    ],
)
def test_sql_policy_rejects_unsafe_queries(sql, message):
    request = base_query_request()
    with pytest.raises(runner.RunnerError, match=message):
        runner.validate_aggregate_sql(sql, request)


def test_sql_policy_rejects_feature_to_legacy_source_mix():
    request = base_query_request()
    request["allowed_tables"].append("default.legacy_checkout")
    request["table_scopes"]["default.legacy_checkout"] = "legacy"
    request["sql"] = f"""
        SELECT f.device_type, count() AS joined
        FROM default.feature_event AS f
        INNER JOIN default.legacy_checkout AS l USING application_id
        WHERE f.run_id = '{request["run_id"]}'
        GROUP BY f.device_type
        LIMIT 100
    """
    with pytest.raises(runner.RunnerError, match="queried separately"):
        runner.validate_aggregate_sql(request["sql"], request)


def test_sql_policy_accepts_distribution_aggregates_for_unseen_feature():
    request = base_query_request()
    request["expected_columns"] = ["destination", "n", "p50", "p90"]
    request["sql"] = f"""
        SELECT destination, count() AS n,
               quantile(0.5)(latency_ms) AS p50,
               quantile(0.9)(latency_ms) AS p90
        FROM default.feature_event
        WHERE run_id = '{request["run_id"]}'
        GROUP BY destination
        LIMIT 100
    """
    assert runner.validate_aggregate_sql(request["sql"], request) == {
        "default.feature_event"
    }


def test_query_stores_full_aggregate_but_previews_only_20_rows():
    request = base_query_request()
    rows = [(f"segment-{index}", index) for index in range(30)]
    client = Client(
        results=[
            schema_result("default.feature_event"),
            Result(["device_type", "events"], rows),
        ]
    )
    response = runner.action_query(client, request)
    assert response["row_count"] == 30
    assert len(response["preview_rows"]) == 20
    assert response["preview_truncated"] is True
    assert len(client.inserts) == 2
    assert client.inserts[1][1][0][4] == "aggregate"
    assert "segment-29" in client.inserts[1][1][0][8]


def test_query_rejects_protected_output():
    request = base_query_request()
    request["expected_columns"] = ["user_id", "events"]
    client = Client(
        results=[
            schema_result("default.feature_event"),
            Result(["user_id", "events"], [("u1", 1)]),
        ]
    )
    with pytest.raises(runner.RunnerError, match="protected columns"):
        runner.action_query(client, request)
    assert client.inserts == []


def test_query_requires_prior_discovery():
    request = base_query_request()
    client = Client(Result(["content"], []))
    with pytest.raises(runner.RunnerError, match="discover must precede query"):
        runner.action_query(client, request)
    assert len(client.queries) == 1


def test_put_artifact_allows_only_declared_types():
    request = {
        "run_id": str(uuid4()),
        "feature_slug": "feature",
        "artifact_type": "manifest",
        "content_format": "json",
        "content": "{}",
    }
    with pytest.raises(runner.RunnerError, match="not writable"):
        runner.action_put_artifact(Client(), request)

    for removed in ("insight_dump", "insight_set", "chart", "chart_specs"):
        with pytest.raises(runner.RunnerError, match="not writable"):
            runner.action_put_artifact(
                Client(), {**request, "artifact_type": removed}
            )

    report = {**request, "artifact_type": "report"}
    client = Client()
    assert runner.action_put_artifact(client, report)["ok"] is True
    assert client.inserts[0][1][0][4] == "report"


def test_removed_artifact_set_actions_are_not_exposed():
    assert "artifact_limits" not in runner._ACTIONS
    assert "preflight_artifact" not in runner._ACTIONS
    assert "validate_artifact_sets" not in runner._ACTIONS


def test_all_statistical_modes():
    rate = pd.DataFrame(
        {"success": [50, 30], "total": [100, 50], "segment": ["a", "b"]}
    )
    assert (
        runner.run_stats(
            [rate],
            "rate",
            {"numerator_column": "success", "denominator_column": "total"},
        )["results"][0]["status"]
        == "answered"
    )

    feature_rate = pd.DataFrame(
        {"success": [50], "total": [100], "segment": ["feature"]}
    )
    legacy_rate = pd.DataFrame({"success": [40], "total": [100], "segment": ["legacy"]})
    assert runner.run_stats(
        [feature_rate, legacy_rate],
        "rate_compare",
        {
            "numerator_column": "success",
            "denominator_column": "total",
            "group_column": "segment",
            "group_a": "feature",
            "group_b": "legacy",
        },
    )["risk_difference"] == pytest.approx(0.1)
    assert (
        runner.run_stats(
            [rate],
            "rate_compare",
            {
                "numerator_column": "success",
                "denominator_column": "total",
                "group_column": "segment",
                "group_a": "a",
                "group_b": "b",
            },
        )["status"]
        == "answered"
    )

    means = pd.DataFrame(
        {
            "segment": ["a", "b"],
            "n": [100, 90],
            "mean": [10.0, 12.0],
            "variance": [4, 5],
        }
    )
    assert (
        runner.run_stats(
            [means],
            "mean_compare",
            {
                "group_column": "segment",
                "group_a": "a",
                "group_b": "b",
                "count_column": "n",
                "mean_column": "mean",
                "variance_column": "variance",
            },
        )["status"]
        == "answered"
    )

    trend = pd.DataFrame(
        {"day": pd.date_range("2026-01-01", periods=10), "rate": range(10)}
    )
    assert (
        runner.run_stats([trend], "trend", {"x_column": "day", "y_column": "rate"})[
            "slope"
        ]
        > 0
    )

    anomaly = pd.DataFrame(
        {"bucket": list("abcdefghij"), "value": [9, 10, 10, 11, 9, 10, 11, 10, 12, 100]}
    )
    assert runner.run_stats(
        [anomaly], "anomaly", {"value_column": "value", "label_column": "bucket"}
    )["anomalies"]

    correlation = pd.DataFrame(
        {"x": range(10), "y": [value * 2 for value in range(10)]}
    )
    assert runner.run_stats(
        [correlation], "correlation", {"x_column": "x", "y_column": "y"}
    )["spearman_rho"] == pytest.approx(1.0)

    pvalues = pd.DataFrame({"comparison": ["a", "b", "c"], "p": [0.001, 0.02, 0.9]})
    adjusted = runner.run_stats(
        [pvalues],
        "adjust_pvalues",
        {"id_column": "comparison", "pvalue_column": "p"},
    )
    assert len(adjusted["results"]) == 3


def test_get_artifact_bounds_csv_and_nested_json():
    run_id, artifact_id = str(uuid4()), str(uuid4())
    base = [
        artifact_id,
        run_id,
        "feature",
        "q1",
        "aggregate",
        "feature",
        "csv",
        30,
        "x,y\n" + "\n".join(f"{i},{i}" for i in range(30)),
        "{}",
        "a" * 64,
        "2026-01-01 00:00:00",
    ]
    response = runner.action_get_artifact(
        Client(Result([], [base])), {"run_id": run_id, "artifact_id": artifact_id}
    )
    assert len(response["records"]) == 20

    base[4], base[6], base[8] = (
        "stats",
        "json",
        json.dumps({"results": list(range(30))}),
    )
    response = runner.action_get_artifact(
        Client(Result([], [base])), {"run_id": run_id, "artifact_id": artifact_id}
    )
    assert len(response["json_content"]["results"]) == 20
    assert response["records_truncated"] is True


def test_get_artifact_paginates_large_text():
    run_id, artifact_id = str(uuid4()), str(uuid4())
    content = "x" * 60_000
    row = [
        artifact_id,
        run_id,
        "feature",
        "",
        "context_snapshot",
        "none",
        "markdown",
        0,
        content,
        "{}",
        "a" * 64,
        "2026-01-01 00:00:00",
    ]
    first = runner.action_get_artifact(
        Client(Result([], [row])),
        {"run_id": run_id, "artifact_id": artifact_id, "offset": 0},
    )
    second = runner.action_get_artifact(
        Client(Result([], [row])),
        {
            "run_id": run_id,
            "artifact_id": artifact_id,
            "offset": first["next_offset"],
        },
    )
    assert len(first["content_chunk"]) == 50_000
    assert first["eof"] is False
    assert len(second["content_chunk"]) == 10_000
    assert second["eof"] is True


def test_main_emits_exactly_one_json_object(monkeypatch, capsys):
    monkeypatch.setenv("ATLYS_REQUEST_B64", request_b64({"action": "unknown"}))
    monkeypatch.setattr(runner, "create_client", Client)
    assert runner.main() == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["error"]["code"] == "invalid_request"
    assert captured.err == ""


def test_ddl_is_append_only_merge_tree_with_ttl():
    ddl = (RUNNER_PATH.parent / "ddl.sql").read_text(encoding="utf-8")
    assert "ENGINE = MergeTree" in ddl
    assert "TTL created_at + INTERVAL 30 DAY DELETE" in ddl
    assert "UPDATE " not in ddl
    assert "ALTER TABLE" not in ddl


def test_runner_contains_no_local_write_or_repository_context_fallback():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "base_context.md" not in source
    assert "instrumentation_" + "handoff" in source
    assert "create_table_commands" not in source
    assert "agent.business_logic_embeddings_v1" in source
    assert "/app/runtime-context" not in source
    assert ".write_text(" not in source
    assert "open(" not in source
    assert "ATLYS_REQUEST_B64" in source
    assert '"insight_set"' not in source
    assert '"chart"' not in source
    assert "validate_artifact_sets" not in source


def test_agent_contract_restores_pm_facing_output_without_artifact_sets():
    root = RUNNER_PATH.parent
    aggregate = (root / "agents/aggregate_analyst/AGENTS.md").read_text(
        encoding="utf-8"
    )
    reviewer = (root / "agents/evidence_reviewer/AGENTS.md").read_text(
        encoding="utf-8"
    )
    supervisor = (root / "agents/supervisor/AGENTS.md").read_text(encoding="utf-8")
    clickhouse_skill = (root / "skills/clickhouse-analytics/SKILL.md").read_text(
        encoding="utf-8"
    )
    bootstrap = (root.parent / "agents/bootstrap-investigation-agents.cjs").read_text(
        encoding="utf-8"
    )

    for required in (
        "complete persisted\ninstrumentation handoff",
        "normalized CTEs",
        "historical-baseline\nledger",
        "one bounded JSON `report` artifact",
    ):
        assert required in aggregate
    assert "direct PM answer" in reviewer
    assert "one JSON `review` artifact per PM question" in reviewer
    assert "## PM-facing terminal response" in supervisor
    assert "Answer\nevery PM question directly" in supervisor
    assert "Do not require or create chart" in supervisor
    assert "historical_baseline_ledger" in aggregate
    assert "RCA records must cover favorable as well as adverse" in aggregate
    assert "Historical comparison is mandatory to attempt" in reviewer
    assert "artifactSkill" not in bootstrap
    assert "skills/artifact-insertion/SKILL.md" not in bootstrap
    assert "clickhouseSkill" in bootstrap
    assert "skills/clickhouse-analytics/SKILL.md" in bootstrap
    assert "agent-discovery-schema" in clickhouse_skill
    assert "agent-query-safety" in clickhouse_skill
    assert "query-join-filter-before" in clickhouse_skill


def test_persisted_agent_graph_places_analytics_specialists_under_supervisor():
    root = RUNNER_PATH.parent
    bootstrap = (root.parent / "agents/bootstrap-investigation-agents.cjs").read_text(
        encoding="utf-8"
    )

    assert "directEdge(analytics, aggregate, 'Aggregate Analyst')" in bootstrap
    assert "directEdge(analytics, reviewer, 'Evidence Reviewer')" in bootstrap
    assert "configure(aggregate, 'aggregate-analyst', analyticsTools, [])" in bootstrap
    assert "direct(aggregate, reviewer" not in bootstrap
