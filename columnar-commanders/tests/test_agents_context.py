"""Context Agent: versioning, diffing, and finding the flaws the base context
is known to contain."""

from __future__ import annotations

from prism_ch.agents.context import ContextAgent, parse_markdown
from prism_ch.agents.context_store import ContextStore, diff_snapshots
from prism_ch.agents.dialect import Dialect
from prism_ch.agents.types import ContextEntry, ContextSnapshot, MaterializedViewSpec

# Shaped like the real Atlys base_context.md, including its actual seeded
# contradiction: conversion rate defined with two different denominators.
BASE_CONTEXT = """
# Atlys Analytics Context

## Entity definitions
- **user** — identified by `user_id`, persists across applications
- **application** — starts at application_started; carries visa_issuance_eta_days

## Metric definitions
- conversion rate — completed purchases divided by sessions
- capture pass rate — documents passing verification / documents uploaded

## Funnel analysis guidance
- conversion rate — purchase_completed users / application_started users

## Known issues
- K3 iOS OTP autofill — WebKit fails to autofill OTP on iOS 17.2+
- K5 WhatsApp nudge — re-engagement message sent to dropped users
"""


# --- parsing ------------------------------------------------------------------


def test_sections_map_to_entry_kinds() -> None:
    kinds = {e.kind for e in parse_markdown(BASE_CONTEXT)}
    assert "entity" in kinds
    assert "metric" in kinds
    assert "known_issue" in kinds


def test_labelled_bullets_become_keyed_entries() -> None:
    entries = {e.key: e for e in parse_markdown(BASE_CONTEXT) if e.kind == "known_issue"}
    assert "K3 iOS OTP autofill" in entries
    assert "WebKit" in entries["K3 iOS OTP autofill"].value


def test_unrecognised_lines_are_kept_not_dropped() -> None:
    """Losing a fact silently is worse than carrying an untidy one."""
    entries = parse_markdown("# Overview\n\nSome prose with no bullet structure.\n")
    assert any("Some prose" in e.value for e in entries)


# The shapes the real base_context.md actually uses. The fixture above mirrors
# what the parser already handled, so it passed while the real document parsed
# into nine section-sized blobs - every table looked undocumented and the LLM
# reported our own truncation as a flaw in their file.
REAL_SHAPES = """
# Atlys Analytics — Base Context Layer

## 2. Entity definitions

**User** — a traveller. Identified by `user_id` (a 28-char string), present on every
event. A user may browse many destinations and start multiple applications.

## 3. The eight raw event tables

| Table | Kind | Emitted when |
|-------|------|--------------|
| `destination_card_clicked` | funnel | user taps a destination card |
| `purchase_completed` | funnel | payment succeeds |

## 4. Metric definitions

**Conversion rate** = completed purchases ÷ **sessions**. A session is a single
app-open / web visit.

## 5. Known-issues log

1. **K1 — iOS WebKit OTP autofill regression.** On recent iOS builds the payment OTP
   field fails to autofill, and some users abandon at the pay step.
2. **K2 — Passport scan model update.** The on-device model was updated in April.
"""


def test_markdown_table_rows_become_one_entry_per_table() -> None:
    tables = {e.key for e in parse_markdown(REAL_SHAPES) if e.kind == "table"}
    assert "destination_card_clicked" in tables
    assert "purchase_completed" in tables
    assert not any(t.startswith("section:") for t in tables)


def test_table_header_row_is_not_an_entry() -> None:
    assert "Table" not in {e.key for e in parse_markdown(REAL_SHAPES)}


def test_metric_written_as_a_formula_is_keyed() -> None:
    metrics = {e.key: e.value for e in parse_markdown(REAL_SHAPES) if e.kind == "metric"}
    assert "Conversion rate" in metrics
    assert "sessions" in metrics["Conversion rate"]


def test_numbered_known_issues_become_keyed_entries() -> None:
    issues = {e.key for e in parse_markdown(REAL_SHAPES) if e.kind == "known_issue"}
    assert {"K1", "K2"} <= issues


def test_wrapped_lines_are_joined_not_dropped() -> None:
    """A value cut at the first newline reads to an LLM as a truncated document."""
    entries = {e.key: e.value for e in parse_markdown(REAL_SHAPES)}
    assert "browse many destinations" in entries["User"]
    assert "abandon at the pay step" in entries["K1"]


def test_bold_label_paragraph_parses_like_a_bullet() -> None:
    entities = {e.key for e in parse_markdown(REAL_SHAPES) if e.kind == "entity"}
    assert "User" in entities


def test_parsing_is_deterministic() -> None:
    first = [(e.kind, e.key, e.value) for e in parse_markdown(BASE_CONTEXT)]
    second = [(e.kind, e.key, e.value) for e in parse_markdown(BASE_CONTEXT)]
    assert first == second


# --- contradiction and gap detection -----------------------------------------


class FakeClient:
    def __init__(self, columns: list[tuple[str, str, str]] | None = None) -> None:
        self.commands: list[str] = []
        self.queries: list[str] = []
        self.inserts: list[dict] = []
        self.columns = columns or []
        self._version = 0

    def command(self, sql: str) -> None:
        self.commands.append(sql)

    def insert(self, **kwargs: object) -> None:
        self.inserts.append(kwargs)

    def query(self, sql: str, **_: object):  # noqa: ANN202
        self.queries.append(sql)
        class R:
            result_rows: list = []

        r = R()
        if "system.columns" in sql:
            r.result_rows = list(self.columns)
        elif "max(version)" in sql:
            r.result_rows = [[self._version]]
        return r


def _agent(make_settings, columns=None) -> ContextAgent:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    return ContextAgent(settings, FakeClient(columns or []))


def test_duplicate_metric_with_different_formula_is_a_contradiction(make_settings) -> None:  # noqa: ANN001
    """The real seeded flaw: conversion rate with two denominators."""
    agent = _agent(make_settings)
    entries = [
        ContextEntry("metric", "conversion rate", "purchases / sessions", source="section 4"),
        ContextEntry(
            "metric", "conversion rate", "purchase_completed / application_started", source="funnel"
        ),
    ]
    issues = agent._structural_issues(ContextSnapshot(1, "", "test", entries))

    contradictions = [i for i in issues if i.kind == "contradiction"]
    assert len(contradictions) == 1
    assert contradictions[0].severity == "high"
    assert "sessions" in contradictions[0].detail
    assert "application_started" in contradictions[0].detail


def test_identical_duplicate_is_not_a_contradiction(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings)
    entries = [
        ContextEntry("metric", "m", "a / b", source="one"),
        ContextEntry("metric", "m", "a / b", source="two"),
    ]
    assert agent._structural_issues(ContextSnapshot(1, "", "t", entries)) == []


def test_table_in_context_but_not_in_database_is_a_contradiction(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings)
    entries = [
        ContextEntry("table", "ghost_events", "documented", source="base_context.md"),
        ContextEntry("table", "real_events", "3 columns", source="clickhouse"),
    ]
    issues = agent._structural_issues(ContextSnapshot(1, "", "t", entries))
    assert any(i.subject == "table:ghost_events" and i.kind == "contradiction" for i in issues)


def test_undocumented_live_table_is_a_gap(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings)
    entries = [
        ContextEntry("table", "documented_events", "x", source="base_context.md"),
        ContextEntry("table", "documented_events", "2 columns", source="clickhouse"),
        ContextEntry("table", "orphan_events", "2 columns", source="clickhouse"),
    ]
    issues = agent._structural_issues(ContextSnapshot(1, "", "t", entries))
    assert any(i.subject == "table:orphan_events" and i.kind == "gap" for i in issues)


def test_metric_referencing_a_missing_column_is_a_gap(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings)
    entries = [
        ContextEntry("column", "events.user_id", "String", source="clickhouse"),
        ContextEntry("metric", "bad", "sum(events.nonexistent) / count()", source="doc"),
    ]
    issues = agent._structural_issues(ContextSnapshot(1, "", "t", entries))
    assert any("nonexistent" in i.detail for i in issues)


def test_metric_without_formula_is_a_high_severity_gap(make_settings) -> None:  # noqa: ANN001
    issues = _agent(make_settings)._structural_issues(
        ContextSnapshot(
            1,
            "",
            "t",
            [
                ContextEntry(
                    "metric", "conversion rate", "successful customer conversion", source="doc"
                )
            ],
        )
    )
    assert any(i.subject == "metric:conversion rate" and i.severity == "high" for i in issues)


def test_relationship_without_join_key_is_a_gap(make_settings) -> None:  # noqa: ANN001
    issues = _agent(make_settings)._structural_issues(
        ContextSnapshot(
            1,
            "",
            "t",
            [ContextEntry("relationship", "applications to users", "applications belong to users")],
        )
    )
    assert any(i.subject == "relationship:applications to users" for i in issues)


def test_shared_id_without_documented_relationship_is_a_gap(make_settings) -> None:  # noqa: ANN001
    entries = [
        ContextEntry("column", "starts.user_id", "String", source="clickhouse"),
        ContextEntry("column", "purchases.user_id", "String", source="clickhouse"),
    ]
    issues = _agent(make_settings)._structural_issues(ContextSnapshot(1, "", "t", entries))
    assert any(i.subject == "relationship:user_id" for i in issues)


# --- versioning and diff ------------------------------------------------------


def test_diff_reports_added_removed_and_changed() -> None:
    old = ContextSnapshot(
        1,
        "",
        "s",
        [
            ContextEntry("metric", "kept", "same"),
            ContextEntry("metric", "dropped", "gone"),
            ContextEntry("metric", "edited", "before"),
        ],
    )
    new = ContextSnapshot(
        2,
        "",
        "s",
        [
            ContextEntry("metric", "kept", "same"),
            ContextEntry("metric", "edited", "after"),
            ContextEntry("table", "brand_new", "5 columns"),
        ],
    )

    delta = diff_snapshots(old, new)
    assert [e.key for e in delta.added] == ["brand_new"]
    assert [e.key for e in delta.removed] == ["dropped"]
    assert delta.changed[0][0].value == "before"
    assert delta.changed[0][1].value == "after"
    assert not delta.is_empty


def test_identical_versions_diff_to_nothing() -> None:
    entries = [ContextEntry("metric", "m", "v")]
    delta = diff_snapshots(
        ContextSnapshot(1, "", "s", entries), ContextSnapshot(2, "", "s", entries)
    )
    assert delta.is_empty


def test_version_row_is_written_last(make_settings) -> None:  # noqa: ANN001
    """A reader must never see a version whose contents are still landing."""
    client = FakeClient()
    store = ContextStore(client, Dialect(target="cloud", database="atlys"))
    store.write(
        entries=[ContextEntry("metric", "m", "v")],
        issues=[],
        source="test",
    )
    assert client.inserts[-1]["table"] == "context_versions"


def test_empty_store_loads_as_version_zero(make_settings) -> None:  # noqa: ANN001
    store = ContextStore(FakeClient(), Dialect(target="cloud", database="atlys"))
    snapshot = store.load()
    assert snapshot.version == 0
    assert snapshot.entries == []


def test_context_tables_follow_the_best_practice_rules(make_settings) -> None:  # noqa: ANN001
    """We apply the same rules to our own schema that the agent applies."""
    ddl = "\n".join(ContextStore(FakeClient(), Dialect(target="cloud", database="atlys")).ddl())
    assert "Nullable" not in ddl
    assert "LowCardinality(String)" in ddl
    # Tiny tables: schema-partition-start-without.
    assert "PARTITION BY" not in ddl


def test_introspection_produces_table_and_column_entries(make_settings) -> None:  # noqa: ANN001
    agent = _agent(
        make_settings,
        columns=[
            ("purchase_completed", "user_id", "String"),
            ("purchase_completed", "value", "Float64"),
        ],
    )
    entries = agent.introspect()
    kinds = {e.kind for e in entries}
    assert kinds == {"table", "column"}
    assert any(e.key == "purchase_completed.value" and e.value == "Float64" for e in entries)


def test_introspection_adds_only_trusted_shared_key_relationships(make_settings) -> None:  # noqa: ANN001
    agent = _agent(
        make_settings,
        columns=[
            ("starts", "user_id", "String"),
            ("purchases", "user_id", "String"),
            ("starts", "duplicate_id", "String"),
            ("purchases", "duplicate_id", "String"),
        ],
    )
    relationships = agent.introspect()
    relationships = [entry for entry in relationships if entry.kind == "relationship"]

    assert [entry.key for entry in relationships] == ["shared user_id"]
    assert "starts.user_id" in relationships[0].value
    assert "purchases.user_id" in relationships[0].value


def test_introspection_excludes_ui_history_tables(make_settings) -> None:  # noqa: ANN001
    agent = _agent(make_settings)
    agent.introspect()
    sql = next(query for query in agent.client.queries if "system.columns" in query)
    assert "ui_agent_insights" in sql
    assert "ui_schema_changes" in sql


class InMemoryClient(FakeClient):
    """Round-trips inserts back through query(), so write -> load is exercised."""

    def __init__(self, columns=None) -> None:  # noqa: ANN001
        super().__init__(columns)
        self.rows: dict[str, list[list]] = {}

    def insert(self, **kwargs) -> None:  # noqa: ANN003
        self.rows.setdefault(kwargs["table"], []).extend(kwargs["data"])

    def query(self, sql: str, **_: object):  # noqa: ANN202
        class R:
            result_rows: list = []

        r = R()
        versions = self.rows.get("context_versions", [])
        if "system.columns" in sql:
            r.result_rows = list(self.columns)
        elif "max(version)" in sql:
            r.result_rows = [[max((v[0] for v in versions), default=0)]]
        elif "context_versions" in sql and "WHERE version" in sql:
            target = int(sql.split("WHERE version =", 1)[1].split("LIMIT", 1)[0].strip())
            r.result_rows = [[v[1], v[2]] for v in versions if v[0] == target]
        elif "context_versions" in sql:
            r.result_rows = [[v[1], v[2]] for v in versions]
        elif "context_entries" in sql:
            version = int(sql.rsplit("=", 1)[1].strip())
            r.result_rows = [
                row[1:] for row in self.rows.get("context_entries", []) if row[0] == version
            ]
        elif "context_issues" in sql:
            version = int(sql.rsplit("=", 1)[1].strip())
            r.result_rows = [
                row[1:] for row in self.rows.get("context_issues", []) if row[0] == version
            ]
        return r


def test_written_context_can_be_read_back(make_settings) -> None:  # noqa: ANN001
    """The path the CLI actually takes: publish, then load the new version."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = InMemoryClient(columns=[("purchase_completed", "user_id", "String")])
    agent = ContextAgent(settings, client)

    entries = parse_markdown(BASE_CONTEXT) + agent.introspect()
    version, _ = agent.publish(entries, source="test")
    snapshot = agent.store.load(version)

    assert snapshot.version == version
    assert len(snapshot.entries) == len(entries)
    assert snapshot.metrics
    # The seeded conversion-rate contradiction survives the round-trip.
    assert any(i.kind == "contradiction" for i in snapshot.issues)


def test_second_refresh_produces_a_diff(make_settings) -> None:  # noqa: ANN001
    """C9: the changelog is a comparison of two stored versions."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = InMemoryClient(columns=[("purchase_completed", "user_id", "String")])
    agent = ContextAgent(settings, client)

    agent.publish(parse_markdown(BASE_CONTEXT), source="v1")
    client.columns.append(("express_checkout_events", "device", "LowCardinality(String)"))
    _, delta = agent.publish(parse_markdown(BASE_CONTEXT) + agent.introspect(), source="v2")

    assert not delta.is_empty
    assert any(e.key == "express_checkout_events" for e in delta.added)


def test_schema_refresh_preserves_human_table_context_and_adds_columns(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = InMemoryClient(columns=[("events", "user_id", "String")])
    agent = ContextAgent(settings, client)
    agent.publish(
        [
            ContextEntry("table", "events", "business event stream", source="base_context.md"),
            ContextEntry("column", "events.old", "String", source="clickhouse"),
        ],
        source="seed",
    )

    version, _ = agent.refresh_after_schema_change(["events"])
    snapshot = agent.store.load(version)

    assert any(e.kind == "table" and e.source == "base_context.md" for e in snapshot.entries)
    assert any(e.key == "events.user_id" and e.source == "clickhouse" for e in snapshot.entries)
    assert not any(e.key == "events.old" for e in snapshot.entries)


def test_schema_refresh_records_rollup_in_same_version(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    client = InMemoryClient(columns=[("daily_revenue", "state", "AggregateFunction(sum, UInt64)")])
    agent = ContextAgent(settings, client)
    view = MaterializedViewSpec(
        "mv_daily", "daily_revenue", "SELECT sumState(amount)", "serves revenue dashboard"
    )

    version, _ = agent.refresh_after_schema_change(["daily_revenue"], views=[view])
    snapshot = agent.store.load(version)

    assert version == 1
    assert snapshot.of_kind("rollup")[0].value == "serves revenue dashboard"


def test_context_run_auto_triggers_analytics(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = ContextAgent(settings, InMemoryClient(columns=[]))

    version, _, report = agent.run(None)

    assert report.context_version == version
    assert agent.last_analytics_run_id is not None


# --- seeding a brand-new database from the bundled base_context.md ------------


def test_run_with_nothing_supplied_seeds_the_bundled_context_when_empty(make_settings) -> None:  # noqa: ANN001
    """"When nothing is there" - a refresh with no document, on a database
    with no context version yet, must not silently publish an empty context.
    It falls back to the package's own base_context.md (bootstrap_node)."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = ContextAgent(settings, InMemoryClient(columns=[]))

    version, _, _ = agent.run(None, run_analytics=False)
    snapshot = agent.store.load(version)

    assert snapshot.source == "bootstrap"
    assert any(e.kind == "known_issue" for e in snapshot.entries)
    assert any(e.kind == "metric" for e in snapshot.entries)


def test_run_with_nothing_supplied_does_not_reseed_an_existing_context(make_settings) -> None:  # noqa: ANN001
    """Once a version exists, "nothing supplied" goes back to its original
    meaning - refresh from the database, carrying forward what is there -
    not re-importing the bundled file over whatever a human already wrote."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = ContextAgent(settings, InMemoryClient(columns=[]))
    agent.publish(
        [ContextEntry("definition", "north star", "conversion", source="base_context.md")],
        source="human",
    )

    version, _, _ = agent.run(None, run_analytics=False)
    snapshot = agent.store.load(version)

    # The human-authored entry survived, and no bundled-default content was
    # imported on top of it (the real base_context.md's known-issues log
    # starts at K1 - nothing in this test's own fixture uses that key).
    assert any(e.key == "north star" for e in snapshot.entries)
    assert not any(e.key == "K1" for e in snapshot.entries)


def test_bootstrap_if_empty_seeds_a_fresh_database(make_settings) -> None:  # noqa: ANN001
    """The shared entry point `AnalyticsAgent.discover()` and
    `InstrumentationAgent._bootstrap_default_context()` both call - covers the
    two paths that read the context layer without going through `run()`."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = ContextAgent(settings, InMemoryClient(columns=[]))

    version = agent.bootstrap_if_empty()

    assert version is not None
    snapshot = agent.store.load(version)
    assert snapshot.source == "bootstrap"
    assert any(e.kind == "known_issue" for e in snapshot.entries)


def test_bootstrap_if_empty_is_a_noop_once_seeded(make_settings) -> None:  # noqa: ANN001
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = ContextAgent(settings, InMemoryClient(columns=[]))
    agent.publish(
        [ContextEntry("definition", "x", "y", source="base_context.md")], source="seed"
    )

    assert agent.bootstrap_if_empty() is None


def test_schema_refresh_also_auto_triggers_analytics(make_settings) -> None:  # noqa: ANN001
    """The other half of the chain (ARCHITECTURE.md): instrument -> context ->
    analytics. A schema change is exactly the moment analysis goes stale, so
    `refresh_after_schema_change` (the automatic path `_notify_context` calls
    after every instrumentation run) must trigger it too, not just `run()`."""
    settings = make_settings(clickhouse_target="cloud", database="atlys", anthropic_api_key="")
    agent = ContextAgent(settings, InMemoryClient(columns=[("events", "user_id", "String")]))

    version, _ = agent.refresh_after_schema_change(["events"])

    assert agent.last_analytics_run_id is not None
    assert agent.last_insight_report.context_version == version
