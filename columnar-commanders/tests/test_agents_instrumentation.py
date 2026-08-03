"""Instrumentation Agent: the deterministic half is tested exhaustively, and
the LLM half is tested through a fake so the pipeline shape is verified without
a network call."""

from __future__ import annotations

import pytest

from prism_ch.agents.dialect import Dialect, for_settings
from prism_ch.agents.instrumentation import InstrumentationAgent  # noqa: F401
from prism_ch.agents.profiling import (
    default_for,
    profile_events,
    suggest_codec,
    suggest_order_by,
    suggest_type,
    wants_nullable,
)
from prism_ch.agents.types import (
    ColumnSpec,
    EventGroup,
    MaterializedViewSpec,
    SchemaProposal,
    SpecInput,
    TableSpec,
    parse_proposal,
)

EVENTS = [
    {
        "event_id": "3f1a2b4c-5d6e-4f70-8a91-b2c3d4e5f601",
        "ts": "2026-07-01T10:00:00Z",
        "device": "ios",
        "country": "IN",
        "latency_ms": 320,
        "amount": 49.5,
        "note": None,
    },
    {
        "event_id": "3f1a2b4c-5d6e-4f70-8a91-b2c3d4e5f602",
        "ts": "2026-07-01T10:00:05Z",
        "device": "android",
        "country": "IN",
        "latency_ms": 210,
        "amount": 12.0,
        "note": "retry",
    },
    {
        "event_id": "3f1a2b4c-5d6e-4f70-8a91-b2c3d4e5f603",
        "ts": "2026-07-01T10:00:09Z",
        "device": "ios",
        "country": "AE",
        "latency_ms": 980,
        "amount": 99.0,
        "note": None,
    },
]


def test_table_name_is_extracted_from_executed_ddl() -> None:
    sql = (
        "ALTER TABLE `atlys`.`prism_otp_entered` ADD COLUMN IF NOT EXISTS "
        "`otp_lost` UInt32 DEFAULT 0"
    )
    assert InstrumentationAgent._table_of(sql) == "prism_otp_entered"


# --- profiling ----------------------------------------------------------------


def test_profiles_every_field() -> None:
    profiles = {p.name: p for p in profile_events(EVENTS)}
    assert set(profiles) == {"event_id", "ts", "device", "country", "latency_ms", "amount", "note"}
    assert profiles["device"].distinct == 2
    assert profiles["device"].total == 3


def test_semantic_classification() -> None:
    profiles = {p.name: p for p in profile_events(EVENTS)}
    assert profiles["event_id"].looks_like == "uuid"
    assert profiles["ts"].looks_like == "timestamp"
    assert profiles["latency_ms"].looks_like == "integer"
    assert profiles["amount"].looks_like == "float"


def test_null_rate_tracks_missing_values() -> None:
    profiles = {p.name: p for p in profile_events(EVENTS)}
    assert profiles["note"].null_rate == pytest.approx(2 / 3)
    assert profiles["device"].null_rate == 0.0


def test_native_types_are_preferred() -> None:
    profiles = {p.name: p for p in profile_events(EVENTS)}
    assert suggest_type(profiles["event_id"]) == "UUID"
    assert suggest_type(profiles["ts"]) == "DateTime64(3, 'UTC')"
    assert "Nullable" not in suggest_type(profiles["latency_ms"])


def test_often_absent_field_gets_a_default_not_nullable() -> None:
    """`schema-types-avoid-nullable`: absence alone does not justify a null map."""
    profiles = {p.name: p for p in profile_events(EVENTS)}
    note = profiles["note"]
    assert note.null_rate > 0
    assert not wants_nullable(note)
    assert "Nullable" not in suggest_type(note)
    assert default_for(suggest_type(note)) == "''"


def test_semantically_null_field_keeps_nullable() -> None:
    events = [{"deleted_at": None}, {"deleted_at": "2026-07-01T00:00:00Z"}]
    profile = profile_events(events)[0]
    assert wants_nullable(profile)
    assert suggest_type(profile).startswith("Nullable(")


def test_order_key_is_low_to_high_cardinality_then_date() -> None:
    """`schema-pk-cardinality-order`, with toDate for a 16-bit index entry."""
    profiles = profile_events(EVENTS)
    keys = suggest_order_by(profiles)
    assert keys[-1] == "toDate(ts)"
    assert "event_id" not in keys  # a leading UUID kills granule pruning
    cardinalities = [
        next(p.distinct for p in profiles if p.name == k) for k in keys[:-1]
    ]
    assert cardinalities == sorted(cardinalities)


def test_timestamp_gets_a_delta_codec() -> None:
    profiles = {p.name: p for p in profile_events(EVENTS)}
    assert suggest_codec(profiles["ts"]) == "Delta, ZSTD(1)"


def test_empty_events_profile_cleanly() -> None:
    assert profile_events([]) == []


# --- dialect ------------------------------------------------------------------


def _table() -> TableSpec:
    return TableSpec(
        name="demo_events",
        columns=[ColumnSpec("device", "LowCardinality(String)"), ColumnSpec("ts", "DateTime")],
        order_by=["device", "ts"],
        partition_by="toYYYYMM(ts)",
    )


def test_cloud_dialect_has_no_cluster_or_replication() -> None:
    ddl = Dialect(target="cloud", database="atlys").create_table(_table())
    assert "ON CLUSTER" not in ddl
    assert "Replicated" not in ddl
    assert "ENGINE = MergeTree" in ddl


def test_cluster_dialect_is_replicated_and_keeps_macros_literal() -> None:
    ddl = Dialect(target="cluster", database="prism").create_table(_table())
    assert "ON CLUSTER click_agents" in ddl
    assert "ReplicatedMergeTree" in ddl
    # Server-side macros must survive Python untouched.
    assert "{shard}" in ddl and "{replica}" in ddl


def test_ordering_key_and_partition_render() -> None:
    ddl = Dialect(target="cloud", database="atlys").create_table(_table())
    assert "ORDER BY (`device`, `ts`)" in ddl
    assert "PARTITION BY toYYYYMM(ts)" in ddl


def test_unknown_target_is_rejected_early() -> None:
    with pytest.raises(ValueError, match="cloud.*cluster"):
        for_settings("localhost", "db", "click_agents")


# --- agent pipeline -----------------------------------------------------------


class FakeResult:
    def __init__(self, rows: list[tuple]) -> None:
        self.result_rows = rows


class FakeClient:
    """Records every statement instead of talking to ClickHouse.

    `existing_tables`/`existing_columns` seed what `system.tables` /
    `system.columns` would report, for the conflict-detection and append
    tests - real query results, without a real ClickHouse.
    """

    def __init__(
        self,
        existing_tables: set[str] | None = None,
        existing_columns: dict[str, set[str]] | None = None,
        insert_errors: list[str] | None = None,
    ) -> None:
        self.commands: list[str] = []
        self.existing_tables = existing_tables or set()
        self.existing_columns = existing_columns or {}
        # Consumed one at a time, only for INSERT statements - simulates a
        # server rejecting the first load attempt, then accepting the retry
        # once the repair loop has patched the schema.
        self._insert_errors = list(insert_errors or [])

    def command(self, sql: str) -> None:
        if sql.startswith("INSERT INTO") and self._insert_errors:
            raise RuntimeError(self._insert_errors.pop(0))
        self.commands.append(sql)

    def query(self, sql: str, parameters: dict | None = None) -> FakeResult:
        parameters = parameters or {}
        if "system.tables" in sql:
            names = parameters.get("names", [])
            return FakeResult([(n,) for n in names if n in self.existing_tables])
        if "system.columns" in sql:
            table = parameters.get("t")
            return FakeResult([(c,) for c in self.existing_columns.get(table, set())])
        return FakeResult([])


def test_baseline_schema_when_no_llm(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="a demo feature", events=EVENTS))

    assert result.executed
    assert result.proposal.tables
    table = result.proposal.tables[0]
    # The UUID must not lead the ordering key - that is the legacy anti-pattern.
    assert table.order_by[0] != "event_id"
    assert "toDate(ts)" in table.order_by


def test_validation_uses_a_scratch_database_and_drops_it(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)

    agent.run(SpecInput(name="demo", brief="", events=EVENTS))
    joined = "\n".join(client.commands)

    assert "atlys_validate" in joined
    assert "DROP DATABASE IF EXISTS `atlys_validate`" in joined
    # The scratch database must be gone before the real tables are created.
    assert client.commands.index("DROP DATABASE IF EXISTS `atlys_validate`") < len(client.commands) - 1


def test_dry_run_validates_without_creating_real_tables(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)

    agent.run(SpecInput(name="demo", brief="", events=EVENTS), execute=False)

    assert not any("`atlys`.`demo_events`" in c for c in client.commands)


def test_proposal_parsing_tolerates_missing_optionals() -> None:
    proposal = parse_proposal(
        {"tables": [{"name": "t", "columns": [{"name": "a", "type": "String"}]}]}
    )
    assert proposal.tables[0].order_by == []
    assert proposal.tables[0].ttl is None
    assert proposal.materialized_views == []


def test_order_by_expressions_are_not_quoted_as_identifiers() -> None:
    """toDate(ts) must render as an expression, not a backticked column name."""
    ddl = Dialect(target="cloud", database="atlys").create_table(
        TableSpec(
            name="t",
            columns=[ColumnSpec("device", "LowCardinality(String)"), ColumnSpec("ts", "DateTime")],
            order_by=["device", "toDate(ts)"],
        )
    )
    assert "ORDER BY (`device`, toDate(ts))" in ddl


def test_column_clause_order_matches_clickhouse_grammar() -> None:
    """name type [DEFAULT] [COMMENT] [CODEC] - any other order is a syntax error."""
    col = ColumnSpec(
        "ts", "DateTime64(3)", codec="Delta, ZSTD(1)", default="toDateTime(0)",
        comment="event time",
    )
    assert col.sql() == (
        "`ts` DateTime64(3) DEFAULT toDateTime(0) "
        "COMMENT 'event time' CODEC(Delta, ZSTD(1))"
    )
    assert col.sql().index("COMMENT") < col.sql().index("CODEC")


def test_default_renders_before_codec() -> None:
    col = ColumnSpec("note", "String", codec="ZSTD(3)", default="''")
    assert col.sql() == "`note` String DEFAULT '' CODEC(ZSTD(3))"


def test_near_constant_column_is_not_an_ordering_key() -> None:
    """Minimal cardinality with zero selectivity prunes nothing.

    `schema-pk-cardinality-order` is bounded by `schema-pk-prioritize-filters`.
    """
    events = [
        {"device": "ios", "coupon": None, "ts": "2026-07-01T10:00:00Z"},
        {"device": "web", "coupon": None, "ts": "2026-07-01T10:00:01Z"},
        {"device": "ios", "coupon": "SAVE10", "ts": "2026-07-01T10:00:02Z"},
        {"device": "web", "coupon": None, "ts": "2026-07-01T10:00:03Z"},
    ]
    keys = suggest_order_by(profile_events(events))
    assert "coupon" not in keys
    assert keys[0] == "device"


# --- LLM retry ----------------------------------------------------------------


def test_transient_errors_are_retried_then_succeed(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """503 "high demand" is routine; the unseen-spec run gets no second chance."""
    from prism_ch.agents import llm

    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    calls = []

    def flaky(settings, *, model, system, prompt, max_tokens):  # noqa: ANN001, ANN202
        calls.append(model)
        if len(calls) < 3:
            raise RuntimeError("503 UNAVAILABLE. This model is experiencing high demand.")
        return '{"tables": []}', {"input": 10, "output": 5}

    monkeypatch.setattr(llm, "_dispatch", flaky)
    result = llm.complete(
        make_settings(llm_provider="gemini", llm_max_retries=4),
        name="t", system="s", prompt="p", as_json=True,
    )
    assert result == {"tables": []}
    assert len(calls) == 3


def test_permanent_errors_are_not_retried(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """A bad model id or key will never succeed - retrying just burns the clock."""
    from prism_ch.agents import llm

    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    calls = []

    def bad(settings, *, model, system, prompt, max_tokens):  # noqa: ANN001, ANN202
        calls.append(model)
        raise RuntimeError("404 NOT_FOUND: model gemini-nope was not found")

    monkeypatch.setattr(llm, "_dispatch", bad)
    with pytest.raises(RuntimeError, match="404"):
        llm.complete(make_settings(llm_provider="gemini"), name="t", system="s", prompt="p")
    assert len(calls) == 1


def test_fallback_model_is_tried_after_primary_exhausts(make_settings, monkeypatch) -> None:  # noqa: ANN001
    from prism_ch.agents import llm

    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    seen = []

    def only_fallback_works(settings, *, model, system, prompt, max_tokens):  # noqa: ANN001, ANN202
        seen.append(model)
        if model == "primary":
            raise RuntimeError("503 overloaded")
        return "ok", {"input": 1, "output": 1}

    monkeypatch.setattr(llm, "_dispatch", only_fallback_works)
    out = llm.complete(
        make_settings(llm_model="primary", llm_fallback_model="backup", llm_max_retries=2),
        name="t", system="s", prompt="p",
    )
    assert out == "ok"
    assert seen == ["primary", "primary", "backup"]


def test_unparseable_json_is_retried(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """Malformed output is stochastic - re-asking usually works."""
    from prism_ch.agents import llm

    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    attempts = []

    def flaky(settings, *, model, system, prompt, max_tokens):  # noqa: ANN001, ANN202
        attempts.append(model)
        body = '{"tables": [' if len(attempts) == 1 else '{"tables": []}'
        return body, {"input": 10, "output": 5}

    monkeypatch.setattr(llm, "_dispatch", flaky)
    out = llm.complete(make_settings(), name="t", system="s", prompt="p", as_json=True)
    assert out == {"tables": []}
    assert len(attempts) == 2


def test_max_tokens_comes_from_settings(make_settings, monkeypatch) -> None:  # noqa: ANN001
    from prism_ch.agents import llm

    seen = {}

    def capture(settings, *, model, system, prompt, max_tokens):  # noqa: ANN001, ANN202
        seen["max_tokens"] = max_tokens
        return "ok", {"input": 1, "output": 1}

    monkeypatch.setattr(llm, "_dispatch", capture)
    llm.complete(make_settings(llm_max_tokens=24000), name="t", system="s", prompt="p")
    assert seen["max_tokens"] == 24000


# --- DDL repair loop ----------------------------------------------------------


def _lint_clean_table():  # noqa: ANN202
    """A table that passes the quality lint, so repair tests exercise the
    server-rejection path rather than tripping the lint first."""
    from prism_ch.agents import instrumentation as inst

    return inst.TableSpec(
        "t",
        [inst.ColumnSpec("device", "LowCardinality(String)", source_field="device")],
        order_by=["device"],
        ttl="toDateTime(ts) + INTERVAL 90 DAY",
    )


def _lint_clean_proposal():  # noqa: ANN202
    """A full schema that passes every lint check, including the mandatory MV
    coverage rule, so repair tests exercise the server-rejection path rather
    than tripping the lint first."""
    from prism_ch.agents import instrumentation as inst

    rollup = inst.TableSpec(
        "t_rollup",
        [
            inst.ColumnSpec("device", "LowCardinality(String)"),
            inst.ColumnSpec("event_count", "AggregateFunction(count)"),
        ],
        order_by=["device"],
        ttl="toDateTime(ts) + INTERVAL 90 DAY",
        engine="AggregatingMergeTree",
    )
    view = inst.MaterializedViewSpec(
        "mv_t_rollup",
        "t_rollup",
        "SELECT device, countState() AS event_count FROM t GROUP BY device",
        "rollup",
    )
    return inst.SchemaProposal(tables=[_lint_clean_table(), rollup], materialized_views=[view])


class RejectingOnceClient(FakeClient):
    """Rejects the first CREATE TABLE, accepts everything after."""

    def __init__(self) -> None:
        super().__init__()
        self.rejected = False

    def command(self, sql: str) -> None:
        if "CREATE TABLE" in sql and not self.rejected:
            self.rejected = True
            raise RuntimeError(
                "Code: 549. Column with type SimpleAggregateFunction(anyLast, "
                "LowCardinality(String)) is not allowed in key expression."
            )
        self.commands.append(sql)


def test_rejected_ddl_is_repaired_not_aborted(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """A server rejection is an actionable correction, not a reason to give up."""
    from prism_ch.agents import instrumentation as inst

    settings = make_settings(
        clickhouse_target="cloud", database="atlys",
        anthropic_api_key="sk-test", ddl_repair_attempts=2,
    )
    agent = inst.InstrumentationAgent(settings, RejectingOnceClient())

    monkeypatch.setattr(
        agent, "design",
        lambda spec, groups, summaries: _lint_clean_proposal(),
    )
    repairs = []
    monkeypatch.setattr(
        agent, "repair",
        lambda spec, groups, summaries, proposal, error: repairs.append(error)
        or _lint_clean_proposal(),
    )

    result = agent.run(inst.SpecInput(name="demo", brief="", events=EVENTS), execute=False)
    assert result.statements
    assert len(repairs) == 1
    assert "549" in repairs[0]


def test_repair_gives_up_after_the_configured_attempts(make_settings, monkeypatch) -> None:  # noqa: ANN001
    from prism_ch.agents import instrumentation as inst

    class AlwaysRejects(FakeClient):
        def command(self, sql: str) -> None:
            if "CREATE TABLE" in sql:
                raise RuntimeError("Code: 62. Syntax error")
            self.commands.append(sql)

    settings = make_settings(
        clickhouse_target="cloud", database="atlys",
        anthropic_api_key="sk-test", ddl_repair_attempts=2,
    )
    agent = inst.InstrumentationAgent(settings, AlwaysRejects())
    proposal = _lint_clean_proposal()
    monkeypatch.setattr(agent, "design", lambda spec, groups, summaries: proposal)
    monkeypatch.setattr(agent, "repair", lambda spec, groups, summaries, p, e: proposal)

    with pytest.raises(RuntimeError, match="Syntax error"):
        agent.run(inst.SpecInput(name="demo", brief="", events=EVENTS), execute=False)


# --- schema quality lint ------------------------------------------------------


def _profiles():  # noqa: ANN202
    return profile_events(EVENTS)


def test_unpopulated_ordering_key_column_is_caught() -> None:
    """The defect from the live run: a derived key column nothing ever fills."""
    from prism_ch.agents.lint import lint_table

    t = TableSpec(
        "t",
        [ColumnSpec("event_date", "Date"), ColumnSpec("device", "String", source_field="device")],
        order_by=["event_date", "device"],
        ttl="toDateTime(ts) + INTERVAL 1 DAY",
    )
    issues = lint_table(t, {p.name: p for p in _profiles()})
    assert any(i.rule == "orderby-column-unpopulated" for i in issues)


def test_materialized_expression_satisfies_the_check() -> None:
    from prism_ch.agents.lint import lint_table

    t = TableSpec(
        "t",
        [ColumnSpec("event_date", "Date", materialized="toDate(ts)")],
        order_by=["event_date"],
        ttl="toDateTime(ts) + INTERVAL 1 DAY",
    )
    issues = lint_table(t, {p.name: p for p in _profiles()})
    assert not any(i.rule == "orderby-column-unpopulated" for i in issues)


def test_uuid_stored_as_string_is_caught() -> None:
    from prism_ch.agents.lint import lint_table

    t = TableSpec(
        "t",
        [ColumnSpec("event_id", "String", source_field="event_id")],
        order_by=[],
        ttl="toDateTime(ts) + INTERVAL 1 DAY",
    )
    issues = lint_table(t, {p.name: p for p in _profiles()})
    assert any(i.rule == "schema-types-native-types" for i in issues)


def test_missing_ttl_is_caught() -> None:
    from prism_ch.agents.lint import lint_table

    t = TableSpec("t", [ColumnSpec("device", "String", source_field="device")], order_by=[])
    issues = lint_table(t, {p.name: p for p in _profiles()})
    assert any(i.rule == "schema-partition-lifecycle" for i in issues)


def test_leading_uuid_key_is_caught() -> None:
    from prism_ch.agents.lint import lint_table

    t = TableSpec(
        "t",
        [ColumnSpec("event_id", "UUID", source_field="event_id")],
        order_by=["event_id"],
        ttl="toDateTime(ts) + INTERVAL 1 DAY",
    )
    issues = lint_table(t, {p.name: p for p in _profiles()})
    assert any(i.rule == "schema-pk-cardinality-order" for i in issues)


def test_baseline_schema_passes_its_own_lint(make_settings) -> None:  # noqa: ANN001
    """We must clear the bar we hold the model to."""
    from prism_ch.agents.instrumentation import InstrumentationAgent
    from prism_ch.agents.lint import lint_proposal

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())
    groups = agent.groups_for(SpecInput(name="demo", brief="", events=EVENTS))
    proposal = agent._baseline(groups)
    assert lint_proposal(proposal, _profiles()) == []


def test_baseline_generates_a_rollup_wired_into_the_proposal(make_settings) -> None:  # noqa: ANN001
    """The mandatory-MV rule applies to the no-LLM path too - "no LLM
    available" is not a way to skip a hard requirement. (`_rollup_for`'s own
    dimension/aggregate choices are tested directly below, independent of
    profiling thresholds on a tiny sample.)"""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())
    groups = agent.groups_for(SpecInput(name="demo", brief="", events=EVENTS))
    proposal = agent._baseline(groups)

    assert len(proposal.materialized_views) == 1
    view = proposal.materialized_views[0]
    assert view.target_table == "demo_events_rollup"
    assert "FROM demo_events" in view.select
    assert "GROUP BY" in view.select
    assert "countState()" in view.select

    rollup_table = next(t for t in proposal.tables if t.name == "demo_events_rollup")
    assert rollup_table.engine == "AggregatingMergeTree"


def test_rollup_for_groups_by_dimensions_and_aggregates_numerics() -> None:
    """GROUP BY every LowCardinality dimension plus an hourly bucket; every
    numeric column gets a -State aggregate; the near-unique id column never
    enters the GROUP BY - that would produce almost as many rows as the raw
    table and defeat the point of a rollup."""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    table = TableSpec(
        "demo_events",
        [
            ColumnSpec("event_id", "UUID"),
            ColumnSpec("device", "LowCardinality(String)"),
            ColumnSpec("country", "LowCardinality(String)"),
            ColumnSpec("latency_ms", "UInt32"),
            ColumnSpec("amount", "Float64"),
            ColumnSpec("ts", "DateTime64(3, 'UTC')"),
        ],
        order_by=["device", "country"],
        ttl="x",
    )
    agent = InstrumentationAgent.__new__(InstrumentationAgent)
    rollup = agent._rollup_for(table, time_col="ts")
    assert rollup is not None
    target, view = rollup

    assert target.name == "demo_events_rollup"
    assert target.engine == "AggregatingMergeTree"
    assert view.target_table == "demo_events_rollup"
    assert "FROM demo_events" in view.select
    assert "device" in view.select
    assert "country" in view.select
    assert "event_id" not in view.select
    assert "toStartOfHour(ts)" in view.select
    assert "sumState(latency_ms)" in view.select
    assert "sumState(amount)" in view.select
    assert "countState()" in view.select


def test_rollup_for_groups_user_id_only_via_uniqstate() -> None:
    """A `user_id` column must never sit in GROUP BY - it belongs in
    uniqState(), the same rule the LLM prompt states for the design path."""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    table = TableSpec(
        "demo_events",
        [ColumnSpec("user_id", "String"), ColumnSpec("device", "LowCardinality(String)")],
        order_by=["device"],
        ttl="x",
    )
    agent = InstrumentationAgent.__new__(InstrumentationAgent)
    _target, view = agent._rollup_for(table, time_col=None)

    assert "uniqState(user_id)" in view.select
    assert "GROUP BY" in view.select
    assert "user_id" not in view.select.split("GROUP BY")[1]


def test_rollup_for_returns_none_when_nothing_worth_aggregating() -> None:
    """A table with no dimension, numeric, user, or time column has nothing a
    rollup could usefully pre-aggregate."""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    settings_table = TableSpec("t", [ColumnSpec("note", "String")], order_by=["note"], ttl="x")
    agent = InstrumentationAgent.__new__(InstrumentationAgent)
    assert agent._rollup_for(settings_table, time_col=None) is None


def test_generated_tables_carry_the_prefix() -> None:
    """Generated tables share a database with the source tables; the prefix
    keeps them distinguishable in the Cloud console."""
    d = Dialect(target="cloud", database="atlys")
    ddl = d.create_table(
        TableSpec("express_checkout_events",
                  [ColumnSpec("a", "String", source_field="a")],
                  order_by=["a"], ttl="toDateTime(ts) + INTERVAL 1 DAY")
    )
    assert "`atlys`.`prism_express_checkout_events`" in ddl


def test_prefix_is_idempotent_and_disableable() -> None:
    d = Dialect(target="cloud", database="atlys")
    assert d.physical_name("prism_already") == "prism_already"
    assert Dialect(target="cloud", database="atlys", table_prefix="").physical_name("t") == "t"


def test_replicated_path_uses_the_physical_name() -> None:
    d = Dialect(target="cluster", database="prism")
    ddl = d.create_table(
        TableSpec("events", [ColumnSpec("a", "String", source_field="a")],
                  order_by=["a"], ttl="x")
    )
    assert "/prism/prism_events'" in ddl


# --- materialized view targets ------------------------------------------------


def _mv_proposal(with_target: bool):  # noqa: ANN202
    from prism_ch.agents.types import MaterializedViewSpec, SchemaProposal

    base = TableSpec(
        "referral_events",
        [ColumnSpec("country", "LowCardinality(String)", source_field="country")],
        order_by=["country"], ttl="ts + INTERVAL 365 DAY",
    )
    tables = [base]
    if with_target:
        tables.append(
            TableSpec(
                "referral_metrics_hourly",
                [ColumnSpec("country", "LowCardinality(String)"),
                 ColumnSpec("event_count", "AggregateFunction(count)")],
                order_by=["country"], ttl="hour + INTERVAL 365 DAY",
                engine="AggregatingMergeTree",
            )
        )
    return SchemaProposal(
        tables=tables,
        materialized_views=[
            MaterializedViewSpec(
                "referral_mv",
                "referral_metrics_hourly",
                "SELECT country, countState() AS event_count FROM referral_events "
                "GROUP BY country",
                "rollup",
            )
        ],
    )


def test_mv_without_its_target_table_is_caught() -> None:
    """The MV would fail at execute time, after base tables already exist."""
    from prism_ch.agents.lint import lint_proposal

    issues = lint_proposal(_mv_proposal(with_target=False), [])
    assert [i.rule for i in issues] == ["mv-target-missing"]


def test_mv_with_its_target_table_passes() -> None:
    from prism_ch.agents.lint import lint_proposal

    assert lint_proposal(_mv_proposal(with_target=True), []) == []


# --- mandatory MV coverage (every table earns a rollup) -----------------------


def test_table_with_no_materialized_view_is_caught() -> None:
    """'Define any materialized views or aggregations needed' is a hard
    requirement now, not a per-table judgment call - a table with zero
    rollups must be rejected the same way an unpopulated ordering key is."""
    from prism_ch.agents.lint import lint_mv_coverage

    proposal = SchemaProposal(
        tables=[TableSpec("t", [ColumnSpec("a", "String")], order_by=["a"], ttl="x")]
    )
    issues = lint_mv_coverage(proposal)
    assert [i.rule for i in issues] == ["mv-coverage-missing"]
    assert issues[0].table == "t"


def test_a_rollups_own_target_table_is_exempt_from_needing_one() -> None:
    """A rollup is already an aggregate - rolling up a rollup is not the ask,
    and would loop forever if it were required."""
    from prism_ch.agents.lint import lint_mv_coverage

    assert lint_mv_coverage(_mv_proposal(with_target=True)) == []


def test_coverage_survives_the_select_being_rewritten_to_a_physical_name() -> None:
    """`render()` rewrites a materialized view's SELECT from the logical table
    name to the physical (prefixed) one in place before validation - if a
    repair loop re-lints the same proposal afterward, coverage must still
    recognise its own table under the new name."""
    from prism_ch.agents.lint import lint_mv_coverage
    from prism_ch.agents.types import MaterializedViewSpec

    proposal = SchemaProposal(
        tables=[TableSpec("t", [ColumnSpec("a", "String")], order_by=["a"], ttl="x")],
        materialized_views=[
            MaterializedViewSpec(
                "mv_t_rollup", "t_rollup", "SELECT count() FROM prism_t", "rollup"
            )
        ],
    )
    assert lint_mv_coverage(proposal) == []


# --- MV SELECT output must name a real target column, exactly -----------------


def test_mismatched_select_alias_is_caught() -> None:
    """The observed live failure: SELECT outputs `events_count`, but the target
    table's column is named `event_count` - ClickHouse accepts the CREATE
    MATERIALIZED VIEW statement either way and only fails once a row actually
    flows through (THERE_IS_NO_COLUMN), so this has to be caught here instead."""
    from prism_ch.agents.lint import lint_mv_column_match
    from prism_ch.agents.types import MaterializedViewSpec

    proposal = SchemaProposal(
        tables=[
            TableSpec(
                "agg",
                [ColumnSpec("country", "LowCardinality(String)"),
                 ColumnSpec("event_count", "AggregateFunction(count)")],
                order_by=["country"], ttl="x", engine="AggregatingMergeTree",
            )
        ],
        materialized_views=[
            MaterializedViewSpec(
                "mv", "agg",
                "SELECT country, countState() AS events_count FROM t GROUP BY country",
                "rollup",
            )
        ],
    )
    issues = lint_mv_column_match(proposal)
    assert [i.rule for i in issues] == ["mv-column-mismatch"]
    assert "events_count" in issues[0].detail


def test_matching_select_aliases_pass() -> None:
    from prism_ch.agents.lint import lint_mv_column_match

    assert lint_mv_column_match(_mv_proposal(with_target=True)) == []


def test_bare_group_by_column_with_no_alias_must_also_match() -> None:
    """Not just aliased aggregates - a bare `SELECT country` output must also
    name a real target column, since ClickHouse binds by name either way."""
    from prism_ch.agents.lint import lint_mv_column_match
    from prism_ch.agents.types import MaterializedViewSpec

    proposal = SchemaProposal(
        tables=[
            TableSpec(
                "agg", [ColumnSpec("region", "LowCardinality(String)")],
                order_by=["region"], ttl="x", engine="AggregatingMergeTree",
            )
        ],
        materialized_views=[
            MaterializedViewSpec("mv", "agg", "SELECT country FROM t GROUP BY country", "rollup")
        ],
    )
    issues = lint_mv_column_match(proposal)
    assert [i.rule for i in issues] == ["mv-column-mismatch"]


def test_select_star_is_skipped_not_false_flagged() -> None:
    """`SELECT *` can't be resolved to column names without the source table's
    schema in hand - skip rather than guess wrong."""
    from prism_ch.agents.lint import lint_mv_column_match
    from prism_ch.agents.types import MaterializedViewSpec

    proposal = SchemaProposal(
        tables=[
            TableSpec(
                "agg", [ColumnSpec("a", "String")],
                order_by=["a"], ttl="x", engine="AggregatingMergeTree",
            )
        ],
        materialized_views=[MaterializedViewSpec("mv", "agg", "SELECT * FROM t", "rollup")],
    )
    assert lint_mv_column_match(proposal) == []


def test_a_missing_target_table_is_left_to_the_other_check() -> None:
    """No target defined at all is `mv-target-missing`'s job, not this one's -
    avoid a second, confusing error for the same root cause."""
    from prism_ch.agents.lint import lint_mv_column_match
    from prism_ch.agents.types import MaterializedViewSpec

    proposal = SchemaProposal(
        tables=[],
        materialized_views=[MaterializedViewSpec("mv", "agg", "SELECT a FROM t GROUP BY a", "rollup")],
    )
    assert lint_mv_column_match(proposal) == []


def test_mv_target_columns_are_exempt_from_the_source_field_check() -> None:
    """MV targets are filled by the view's SELECT, not by mapped event fields."""
    from prism_ch.agents.lint import lint_table

    target = TableSpec(
        "agg", [ColumnSpec("country", "LowCardinality(String)")],
        order_by=["country"], ttl="x", engine="AggregatingMergeTree",
    )
    assert lint_table(target, {}, mv_target=True) == []
    assert any(i.rule == "orderby-column-unpopulated" for i in lint_table(target, {}))


def test_aggregating_engine_renders_on_both_targets() -> None:
    t = TableSpec("agg", [ColumnSpec("c", "LowCardinality(String)")],
                  order_by=["c"], ttl="x", engine="AggregatingMergeTree")
    assert "ENGINE = AggregatingMergeTree" in Dialect(target="cloud", database="atlys").create_table(t)
    cluster = Dialect(target="cluster", database="prism").create_table(t)
    assert "ReplicatedAggregatingMergeTree(" in cluster


# --- table prefix vs free-text MV SELECTs -------------------------------------


def _agent_for_prefix(make_settings):  # noqa: ANN001, ANN202
    from prism_ch.agents.instrumentation import InstrumentationAgent

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    return InstrumentationAgent(settings, FakeClient())


def test_mv_select_is_rewritten_to_the_physical_table_name(make_settings) -> None:  # noqa: ANN001
    """The model writes the logical name; the table is created with the prefix."""
    agent = _agent_for_prefix(make_settings)
    out = agent.qualify_select(
        "SELECT a FROM atlys.express_checkout_events GROUP BY a", {"express_checkout_events"}
    )
    assert "atlys.prism_express_checkout_events" in out


def test_bare_table_reference_is_rewritten(make_settings) -> None:  # noqa: ANN001
    """Always fully qualified, not just renamed - validate()'s scratch-database
    redirect works by string-replacing the `{database}.` qualifier, so a bare
    reference has to gain one, not just the physical name."""
    agent = _agent_for_prefix(make_settings)
    assert (
        agent.qualify_select("SELECT 1 FROM events", {"events"})
        == "SELECT 1 FROM atlys.prism_events"
    )


def test_wrongly_qualified_reference_is_corrected_to_this_database(make_settings) -> None:  # noqa: ANN001
    """The model sometimes assumes ClickHouse's own `default` database is
    active and qualifies with that instead of the configured one - left
    alone, this reaches the server as UNKNOWN_TABLE against the scratch
    database during validation, and again against the real one at execute
    time; the observed failure this test guards against."""
    agent = _agent_for_prefix(make_settings)
    out = agent.qualify_select("SELECT 1 FROM default.events GROUP BY 1", {"events"})
    assert out == "SELECT 1 FROM atlys.prism_events GROUP BY 1"


def test_rewrite_is_idempotent_and_leaves_other_tables_alone(make_settings) -> None:  # noqa: ANN001
    agent = _agent_for_prefix(make_settings)
    already = "SELECT 1 FROM atlys.prism_events"
    assert agent.qualify_select(already, {"events"}) == already
    other = "SELECT 1 FROM atlys.purchase_completed"
    assert agent.qualify_select(other, {"events"}) == other


def test_materialized_views_are_validated_not_just_tables(make_settings) -> None:  # noqa: ANN001
    """An unvalidated MV fails against the real database, after base tables exist."""
    from prism_ch.agents.instrumentation import InstrumentationAgent
    from prism_ch.agents.types import MaterializedViewSpec, SchemaProposal

    client = FakeClient()
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, client)

    proposal = SchemaProposal(
        tables=[
            TableSpec("events", [ColumnSpec("a", "String", source_field="a")],
                      order_by=["a"], ttl="x"),
            TableSpec("agg", [ColumnSpec("a", "String")], order_by=["a"], ttl="x",
                      engine="AggregatingMergeTree"),
        ],
        materialized_views=[
            MaterializedViewSpec("mv", "agg", "SELECT a FROM atlys.events GROUP BY a", "rollup")
        ],
    )
    agent.validate(proposal)
    joined = "\n".join(client.commands)

    assert "CREATE MATERIALIZED VIEW" in joined
    # The probe repoints the SELECT at the scratch database.
    assert "atlys_validate.prism_events" in joined


# --- table comment / drop / add column -----------------------------------------


def test_table_comment_renders_as_the_last_clause() -> None:
    ddl = Dialect(target="cloud", database="atlys").create_table(
        TableSpec(
            name="t",
            columns=[ColumnSpec("a", "String")],
            order_by=["a"],
            comment="what this table records",
        )
    )
    assert ddl.rstrip().endswith("COMMENT 'what this table records'")


def test_table_without_a_comment_has_no_comment_clause() -> None:
    ddl = Dialect(target="cloud", database="atlys").create_table(
        TableSpec(name="t", columns=[ColumnSpec("a", "String")], order_by=["a"])
    )
    assert "COMMENT" not in ddl


def test_the_dialect_cannot_drop_a_table_at_all() -> None:
    """No drop primitive exists: an existing table is only ever widened, so
    the method that would let a run destroy data is deliberately absent."""
    assert not hasattr(Dialect(target="cloud", database="atlys"), "drop_table")


def test_add_column_uses_if_not_exists_for_idempotency() -> None:
    ddl = Dialect(target="cloud", database="atlys").add_column(
        "t", ColumnSpec("new_field", "String", comment="added later")
    )
    assert "ALTER TABLE" in ddl
    assert "ADD COLUMN IF NOT EXISTS" in ddl
    assert "`new_field` String" in ddl


# --- table already exists: widen, never drop, never ask -------------------------


def test_existing_tables_finds_only_tables_that_actually_exist(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient(existing_tables={"prism_demo_events"})
    agent = InstrumentationAgent(settings, client)

    proposal = SchemaProposal(
        tables=[TableSpec("demo_events", [ColumnSpec("a", "String")], order_by=["a"])]
    )
    assert agent.existing_tables(proposal) == ["prism_demo_events"]


def test_an_existing_table_is_never_dropped(make_settings) -> None:  # noqa: ANN001
    """The whole point of removing overwrite: no path drops a real table."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient(existing_tables={"prism_demo_events"})
    agent = InstrumentationAgent(settings, client)

    agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    drops = [c for c in client.commands if c.startswith("DROP TABLE")]
    assert drops == []
    # The scratch validation database is still torn down - that one is ours.
    assert any(c.startswith("DROP DATABASE") for c in client.commands)


def test_existing_table_is_widened_with_only_the_missing_columns(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    # Everything the baseline would propose except `note`, so exactly one
    # ALTER should follow.
    existing = {"event_id", "ts", "device", "country", "latency_ms", "amount"}
    client = FakeClient(
        existing_tables={"prism_demo_events"},
        existing_columns={"prism_demo_events": existing},
    )
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    assert result.executed
    alters = [c for c in client.commands if c.startswith("ALTER TABLE")]
    assert len(alters) == 1
    assert "`note`" in alters[0]


def test_widening_adds_nothing_when_the_table_already_matches(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    all_columns = {"event_id", "ts", "device", "country", "latency_ms", "amount", "note"}
    client = FakeClient(
        existing_tables={"prism_demo_events"},
        existing_columns={"prism_demo_events": all_columns},
    )
    agent = InstrumentationAgent(settings, client)

    agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    assert not [c for c in client.commands if c.startswith("ALTER TABLE")]


def test_every_executed_statement_is_reported_for_display(make_settings) -> None:  # noqa: ANN001
    """The UI shows the DDL that actually ran, including agent-decided ALTERs."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    existing = {"event_id", "ts", "device", "country", "latency_ms", "amount"}
    client = FakeClient(
        existing_tables={"prism_demo_events"},
        existing_columns={"prism_demo_events": existing},
    )
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    kinds = [s.kind for s in result.executed_statements]
    assert "create_table" in kinds
    assert "alter_table" in kinds
    assert all(s.ok for s in result.executed_statements)
    assert all(s.sql for s in result.executed_statements)


# --- a failed statement is logged, not fatal -----------------------------------


def test_execute_continues_past_a_failed_statement(make_settings) -> None:
    """One CREATE TABLE failing (a transient error `validate()` could not have
    caught, since it already ran clean against the scratch database) must not
    stop the rest from being created."""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    class FlakyClient(FakeClient):
        def command(self, sql: str) -> None:
            if "bad_table" in sql:
                raise RuntimeError("Code: 999. Simulated transient failure")
            super().command(sql)

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FlakyClient()
    agent = InstrumentationAgent(settings, client)

    good = TableSpec("good_table", [ColumnSpec("a", "String")], order_by=["a"], ttl="x")
    bad = TableSpec("bad_table", [ColumnSpec("a", "String")], order_by=["a"], ttl="x")
    statements = agent.render(SchemaProposal(tables=[good, bad]))

    agent.execute(statements)  # must not raise

    assert any("prism_good_table" in c for c in client.commands)
    results = {r.table: r.ok for r in agent.executed_statements}
    assert results["prism_good_table"] is True
    assert results["prism_bad_table"] is False


def test_reconcile_continues_past_a_failed_alter(make_settings) -> None:
    """Same rule for widening an existing table: one column's ALTER failing
    must not block the others."""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    class FlakyClient(FakeClient):
        def command(self, sql: str) -> None:
            if "bad_col" in sql:
                raise RuntimeError("Code: 999. Simulated transient failure")
            super().command(sql)

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FlakyClient(existing_tables={"prism_t"}, existing_columns={"prism_t": {"a"}})
    agent = InstrumentationAgent(settings, client)

    table = TableSpec(
        "t",
        [ColumnSpec("a", "String"), ColumnSpec("good_col", "String"), ColumnSpec("bad_col", "String")],
        order_by=["a"], ttl="x",
    )
    added = agent.reconcile(SchemaProposal(tables=[table]), existing={"prism_t"})

    assert added == ["prism_t.good_col"]
    failed = [r for r in agent.executed_statements if not r.ok]
    assert len(failed) == 1 and "bad_col" in failed[0].sql  # attempted and recorded, not silently dropped


def test_load_repair_reports_an_error_instead_of_raising_when_add_column_fails(
    make_settings,
) -> None:
    """If the column meant to fix an unmapped-field rejection cannot itself be
    added, the load must fail with a reported error - not raise and take
    every other group's load down with it."""
    from prism_ch.agents.instrumentation import InstrumentationAgent

    class Client:
        def command(self, sql: str) -> None:
            if sql.startswith("INSERT INTO"):
                raise RuntimeError("Unknown field found while parsing JSONEachRow format: extra")
            if "ADD COLUMN" in sql:
                raise RuntimeError("Code: 999. Simulated transient failure")

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, Client())
    table = TableSpec("t", [ColumnSpec("a", "String", source_field="a")], order_by=["a"], ttl="x")

    result = agent._load_table(table, [{"a": "x", "extra": "y"}])  # must not raise

    assert result.loaded == 0
    assert result.error and "999" in result.error


def test_each_user_action_becomes_its_own_table(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)
    groups = [
        EventGroup(
            action="otp_entered",
            events=[dict(e, event="otp_entered") for e in EVENTS],
            load_events=[dict(e, event="otp_entered") for e in EVENTS],
            total=3,
        ),
        EventGroup(
            action="express_payment_confirmed",
            events=[dict(e, event="express_payment_confirmed") for e in EVENTS[:2]],
            load_events=[dict(e, event="express_payment_confirmed") for e in EVENTS[:2]],
            total=2,
        ),
    ]
    spec = SpecInput(name="express_checkout", brief="a feature", groups=groups)

    result = agent.run(spec)

    base_tables = [t.name for t in result.proposal.tables if not t.name.endswith("_rollup")]
    assert base_tables == ["otp_entered", "express_payment_confirmed"]
    # Each table is loaded from its own group, not from a pooled event list.
    loaded = {r.table: r.loaded for r in result.load_results}
    assert loaded == {"otp_entered": 3, "express_payment_confirmed": 2}


def test_a_declared_action_with_no_rows_is_reported(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())
    spec = SpecInput(
        name="demo",
        brief="a feature",
        groups=[
            EventGroup(action="present", events=EVENTS, load_events=EVENTS, total=3),
            EventGroup(action="absent"),
        ],
    )

    result = agent.run(spec)

    assert result.empty_actions == ["absent"]
    # No rows to load, so no attempt is reported for it.
    assert [r.table for r in result.load_results] == ["present"]


def test_a_spec_with_no_declared_actions_falls_back_to_one_table(make_settings) -> None:  # noqa: ANN001
    """A bare brief, or a spec format the parser did not recognise, still
    produces a schema rather than nothing."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    base_tables = [t.name for t in result.proposal.tables if not t.name.endswith("_rollup")]
    assert base_tables == ["demo_events"]


def test_preview_run_touches_nothing_real(make_settings) -> None:  # noqa: ANN001
    """execute=False is a preview - nothing created, nothing widened."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient(existing_tables={"prism_demo_events"})
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS), execute=False)

    assert not result.executed
    assert not [c for c in client.commands if c.startswith("ALTER TABLE")]
    assert not any("CREATE TABLE" in c and "atlys_validate" not in c for c in client.commands)


# --- load sample + missing-column repair ----------------------------------------


def test_sample_load_runs_automatically_after_execute(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    assert len(result.load_results) == 1
    load = result.load_results[0]
    assert load.loaded == len(EVENTS)
    assert load.error == ""
    assert any(c.startswith("INSERT INTO") for c in client.commands)


def test_sample_load_uses_the_full_file_not_the_profiling_sample(make_settings) -> None:  # noqa: ANN001
    """Design/profiling reasons from the sample (`events`); the actual INSERT
    must use `load_events` - the full file - when the two differ."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)
    full_file = EVENTS + EVENTS  # same shape, more rows - no schema repair needed

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS, load_events=full_file))

    load = result.load_results[0]
    assert load.attempted == len(full_file) == 6
    assert load.loaded == 6


def test_sample_load_skipped_when_not_executing(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS), execute=False)

    assert result.load_results == []
    assert not any(c.startswith("INSERT INTO") for c in client.commands)


def _short_table(name: str = "demo_events") -> TableSpec:
    """A table missing `extra_field` on purpose - the events carry it, the
    schema does not. Built directly rather than via run(): the deterministic
    baseline design always derives its columns from the same events it will
    load, so it can never itself be short a field - only a hand-built (or
    LLM-designed) schema can be."""
    return TableSpec(
        name=name,
        columns=[
            ColumnSpec("event_id", "UUID", source_field="event_id"),
            ColumnSpec("device", "LowCardinality(String)", source_field="device"),
        ],
        order_by=["device"],
    )


def test_missing_column_is_added_from_the_server_error_then_retried(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient(
        insert_errors=[
            "Code: 117. DB::Exception: Unknown field found while parsing "
            "JSONEachRow format: extra_field: (at row 1)"
        ]
    )
    agent = InstrumentationAgent(settings, client)
    events = [dict(EVENTS[0], extra_field="surprise")]

    proposal = SchemaProposal(tables=[_short_table()])
    groups = [EventGroup(action="demo_events", events=events, load_events=events, total=1)]
    results = agent.load_groups(groups, proposal)

    assert len(results) == 1
    load = results[0]
    assert load.loaded == len(events)
    assert load.columns_added == ["extra_field"]
    alters = [c for c in client.commands if "ADD COLUMN IF NOT EXISTS `extra_field`" in c]
    assert len(alters) == 1
    # The alter must land before the second (successful) insert attempt.
    insert_idx = [i for i, c in enumerate(client.commands) if c.startswith("INSERT INTO")]
    assert len(insert_idx) == 1  # first attempt raised and was never recorded
    assert client.commands.index(alters[0]) < insert_idx[0]


def test_load_gives_up_after_repair_attempts_are_exhausted(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(
        clickhouse_target="cloud", database="atlys", anthropic_api_key="", ddl_repair_attempts=1
    )
    unknown_field_error = (
        "Code: 117. DB::Exception: Unknown field found while parsing "
        "JSONEachRow format: extra_field: (at row 1)"
    )
    # Every attempt fails, including the retry after the repair - the loop
    # must stop rather than repair the same field forever.
    client = FakeClient(insert_errors=[unknown_field_error, unknown_field_error])
    agent = InstrumentationAgent(settings, client)
    events = [dict(EVENTS[0], extra_field="surprise")]

    proposal = SchemaProposal(tables=[_short_table()])
    groups = [EventGroup(action="demo_events", events=events, load_events=events, total=1)]
    results = agent.load_groups(groups, proposal)

    load = results[0]
    assert load.loaded == 0
    assert load.error


def test_non_repairable_load_error_is_reported_not_retried_forever(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient(insert_errors=["Code: 999. DB::Exception: something unrelated"])
    agent = InstrumentationAgent(settings, client)

    result = agent.run(SpecInput(name="demo", brief="", events=EVENTS))

    load = result.load_results[0]
    assert load.loaded == 0
    assert "something unrelated" in load.error
    assert not [c for c in client.commands if c.startswith("ALTER TABLE")]


def test_materialized_view_targets_are_not_directly_inserted_into(make_settings) -> None:  # noqa: ANN001
    """ClickHouse populates an MV target from the base table's insert - a
    second direct insert into it would double the rows."""
    from prism_ch.agents.instrumentation import InstrumentationAgent as Agent

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = FakeClient()
    agent = Agent(settings, client)

    proposal = SchemaProposal(
        tables=[
            TableSpec("events", [ColumnSpec("a", "String", source_field="a")], order_by=["a"]),
            TableSpec("agg", [ColumnSpec("a", "String")], order_by=["a"], engine="AggregatingMergeTree"),
        ],
        materialized_views=[
            MaterializedViewSpec("mv", "agg", "SELECT a FROM atlys.events GROUP BY a", "rollup")
        ],
    )
    groups = [
        EventGroup(action="events", events=[{"a": "x"}], load_events=[{"a": "x"}], total=1),
        EventGroup(action="agg", events=[{"a": "x"}], load_events=[{"a": "x"}], total=1),
    ]
    results = agent.load_groups(groups, proposal)

    assert [r.table for r in results] == ["events"]


# --- notifying the Context Agent about rollups ---------------------------------


def test_notify_context_records_rollups_with_physical_names(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """A materialized view's `why` must reach the context layer, not just the
    UI - that's the one thing that distinguishes a rollup from an ordinary
    table once `record_new_table`'s introspection sees only its columns."""
    calls: dict[str, list] = {"refresh": []}

    class SpyContext:
        def __init__(self, settings, client) -> None:  # noqa: ANN001
            pass

        def bootstrap_if_empty(self, *, run_analytics=False):  # noqa: ANN001
            return None

        def refresh_after_schema_change(self, tables, views=None) -> None:  # noqa: ANN001
            calls["refresh"].append(
                (list(tables), [(v.target_table, v.why) for v in (views or [])])
            )

    import prism_ch.agents.context as context_module

    monkeypatch.setattr(context_module, "ContextAgent", SpyContext)

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())

    proposal = SchemaProposal(
        tables=[
            TableSpec("events", [ColumnSpec("a", "String")], order_by=["a"]),
            TableSpec(
                "agg", [ColumnSpec("a", "String")], order_by=["a"], engine="AggregatingMergeTree"
            ),
        ],
        materialized_views=[
            MaterializedViewSpec(
                "mv", "agg", "SELECT a FROM events GROUP BY a",
                "avoids a full scan per dashboard load",
            )
        ],
    )
    agent._notify_context(proposal)

    # Physical (prefixed) name - the Context Agent's own dialect is unprefixed,
    # so only the caller's dialect can supply the name introspection will see.
    assert calls["refresh"] == [
        (
            ["events", "agg"],
            [("prism_agg", "avoids a full scan per dashboard load")],
        )
    ]


def test_notify_context_surfaces_the_analytics_chain(make_settings, monkeypatch) -> None:  # noqa: ANN001
    """instrument -> context -> analytics (ARCHITECTURE.md): once
    `refresh_after_schema_change` chains into analytics, the result must reach
    the caller the same way self.decisions/self.steps already do - the UI has
    no other way to show "context updated" or the resulting insights."""
    from prism_ch.agents.types import ContextDiff, InsightReport

    fake_report = InsightReport(context_version=7, summary="mobile leads")
    fake_delta = ContextDiff(from_version=6, to_version=7)

    class SpyContext:
        def __init__(self, settings, client) -> None:  # noqa: ANN001
            self.last_insight_report = fake_report
            self.last_analytics_run_id = "run-123"
            self.last_analytics_trace_id = "trace-456"

        def bootstrap_if_empty(self, *, run_analytics=False):  # noqa: ANN001
            return None

        def refresh_after_schema_change(self, tables, views=None):  # noqa: ANN001
            return 7, fake_delta

    import prism_ch.agents.context as context_module

    monkeypatch.setattr(context_module, "ContextAgent", SpyContext)

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())
    proposal = SchemaProposal(
        tables=[TableSpec("events", [ColumnSpec("a", "String")], order_by=["a"])],
    )
    agent._notify_context(proposal)

    assert agent.context_version == 7
    assert agent.context_delta is fake_delta
    assert agent.last_insight_report is fake_report
    assert agent.last_analytics_run_id == "run-123"
    assert agent.last_analytics_trace_id == "trace-456"


def test_notify_context_skips_rollups_when_none_proposed(make_settings, monkeypatch) -> None:  # noqa: ANN001
    calls: dict[str, list] = {"refresh": []}

    class SpyContext:
        def __init__(self, settings, client) -> None:  # noqa: ANN001
            pass

        def bootstrap_if_empty(self, *, run_analytics=False):  # noqa: ANN001
            return None

        def refresh_after_schema_change(self, tables, views=None) -> None:  # noqa: ANN001
            calls["refresh"].append((list(tables), list(views or [])))

    import prism_ch.agents.context as context_module

    monkeypatch.setattr(context_module, "ContextAgent", SpyContext)

    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())

    proposal = SchemaProposal(
        tables=[TableSpec("events", [ColumnSpec("a", "String")], order_by=["a"])],
    )
    agent._notify_context(proposal)

    assert calls["refresh"] == [(["events"], [])]


# --- bootstrapping the default base_context.md on a brand-new database --------


class _FakeContextAgent:
    """`InstrumentationAgent` only ever calls `bootstrap_if_empty()` now - the
    version check and the actual seeding both live in `ContextAgent` itself
    (shared with `AnalyticsAgent.discover()`), so the fake only needs to
    stand in for that one method."""

    def __init__(self, seeded_version: int | None) -> None:
        self.seeded_version = seeded_version
        self.calls: list[bool] = []

    def bootstrap_if_empty(self, *, run_analytics=False):  # noqa: ANN001
        self.calls.append(run_analytics)
        return self.seeded_version


def test_bootstrap_default_context_seeds_a_brand_new_database(make_settings) -> None:  # noqa: ANN001
    """No context version exists yet (C1) - the bundled base_context.md must
    seed it once, so the very first Analytics run this instrumentation run
    triggers still has business context to read first (ARCHITECTURE.md)."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())
    ctx = _FakeContextAgent(seeded_version=1)

    agent._bootstrap_default_context(ctx)

    assert agent.bootstrapped_default_context is True
    # Analytics runs once, inside refresh_after_schema_change right after -
    # running it here too would waste a query pass on a still-partial context.
    assert ctx.calls == [False]


def test_bootstrap_default_context_skipped_when_a_version_already_exists(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = InstrumentationAgent(settings, FakeClient())
    ctx = _FakeContextAgent(seeded_version=None)

    agent._bootstrap_default_context(ctx)

    assert agent.bootstrapped_default_context is False
    assert ctx.calls == [False]
