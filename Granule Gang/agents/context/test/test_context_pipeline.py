# test_context_pipeline.py
"""
Tests for ContextAgent's document-based business-context model
(analytics_context.business_context -- one versioned Markdown document, not
row-decomposed; see agents/context/agent.py). Covers the three behaviors the
agent is responsible for:
1. Auto-updating the document when InstrumentationAgent creates a new table.
2. Downstream consumers (AnalyticsAgent) always reading the latest version.
3. Surfacing contradictions/gaps/obsolete facts (run_audit) and resolving them.

Uses a small in-memory fake ClickHouse client rather than a MagicMock with many
side_effect branches -- real enough to exercise the full seed -> update ->
audit -> resolve read/write cycle (version bumps, content splicing) without a
live ClickHouse service.
"""
import json
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agents.instrumentation.agent import InstrumentationAgent
from agents.analytics.agent import AnalyticsAgent
from agents.context.agent import ContextAgent


class FakeContextClient:
    """Minimal in-memory stand-in for the ClickHouse operations ContextAgent
    and InstrumentationAgent issue against analytics_context.business_context,
    atlys.meta_context_registry, and system.tables."""

    def __init__(self):
        self.business_context_rows = []  # [{doc_id, content, version, changelog_summary, updated_at}]
        self.registered_tables = set()   # meta_context_registry entity_name
        self.existing_tables = set()     # system.tables name
        self.commands = []

    def insert(self, table, rows, column_names=None, settings=None):
        if table == "analytics_context.business_context":
            for row in rows:
                self.business_context_rows.append(dict(zip(column_names, row)))
        elif table.endswith("meta_context_registry"):
            idx = column_names.index("entity_name")
            for row in rows:
                self.registered_tables.add(row[idx])
        return None

    def command(self, sql):
        self.commands.append(sql)
        m = re.search(r"CREATE TABLE\s+\S+\.(\w+)", sql)
        if m:
            self.existing_tables.add(m.group(1))
        return None

    def query(self, sql):
        s = sql if isinstance(sql, str) else str(sql)
        result = MagicMock()

        if "analytics_context.business_context" in s:
            result.column_names = ["doc_id", "content", "version", "changelog_summary", "updated_at"]
            if self.business_context_rows:
                latest = max(self.business_context_rows, key=lambda r: r["version"])
                result.result_rows = [[latest["doc_id"], latest["content"], latest["version"],
                                        latest["changelog_summary"], latest["updated_at"]]]
            else:
                result.result_rows = []
            return result

        if "count()" in s.lower() and "meta_context_registry" in s:
            m = re.search(r"entity_name = '([^']*)'", s)
            name = m.group(1) if m else None
            result.column_names = ["count()"]
            result.result_rows = [[1 if name in self.registered_tables else 0]]
            return result

        if "DISTINCT entity_name" in s and "meta_context_registry" in s:
            result.column_names = ["entity_name"]
            result.result_rows = [[t] for t in sorted(self.registered_tables)]
            return result

        if "system.tables" in s:
            result.column_names = ["name"]
            result.result_rows = [[t] for t in sorted(self.existing_tables)]
            return result

        # Generic fallback (e.g. InstrumentationAgent._load_registry()'s full listing).
        result.column_names = []
        result.result_rows = []
        return result


@pytest.fixture
def fake_client():
    return FakeContextClient()


@pytest.fixture
def mock_llm_call():
    """Mock LLM response function matching ContextAgent's (prompt, span_name) -> str interface."""
    def _llm_call(prompt: str, span_name: str = "test") -> str:
        if "NEW TABLES:" in prompt:
            # Response for update_context()
            return json.dumps({
                "tables": [
                    {
                        "name": "express_checkout_shown",
                        "kind": "supporting",
                        "emitted_when": "express checkout offer renders",
                        "key_columns": ["express_method"],
                    }
                ],
                "changelog_summary": "Documented express_checkout_shown",
            })
        if "resolving an open flag" in prompt:
            # Response for resolve_flag()
            return json.dumps({
                "resolution_notes": "Table was intentionally dropped; the reference is stale and should be removed.",
            })
        if "auditing a business-context" in prompt:
            # Response for run_audit()'s LLM pass -- freshness_check() (deterministic)
            # supplies the flag in the audit test, so no LLM-found issues here.
            return "[]"
        return "{}"
    return _llm_call


@pytest.fixture
def sample_spec_dir(tmp_path: Path):
    """Creates a temporary spec directory with spec.md and events.ndjson."""
    spec_dir = tmp_path / "express_checkout_spec"
    spec_dir.mkdir()

    spec_md = """# Express Checkout Feature Spec

This spec captures user interactions with the express checkout flow.

Events:
`express_checkout_shown`
`express_checkout_clicked`

Properties:
- `express_method`: String (e.g. apple_pay, google_pay)
- `latency_ms`: Int
"""
    (spec_dir / "spec.md").write_text(spec_md)

    events = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "timestamp": "2026-08-01 12:00:00",
            "user_id": "usr_123",
            "application_id": "app_abc",
            "event": "express_checkout_shown",
            "express_method": "apple_pay",
            "latency_ms": 120,
        }
    ]
    with open(spec_dir / "events.ndjson", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    return spec_dir


# ============================================================================
# TESTS
# ============================================================================

def test_auto_update_context_on_new_schema(fake_client, mock_llm_call, sample_spec_dir):
    """
    Test 1: InstrumentationAgent creating a new table auto-documents it in the
    business-context document (a new version, not a mutated row).
    """
    context_agent = ContextAgent(client=fake_client, llm_call_fn=mock_llm_call)
    context_agent.load_v1()
    assert context_agent.get_latest_context()["version"] == 1

    # Spy on update_context
    context_agent.update_context = MagicMock(side_effect=context_agent.update_context)

    instrumentation = InstrumentationAgent(
        clickhouse_client=fake_client,
        context_agent=context_agent,
        openrouter_config=None,  # Triggers fallback basic parsing for reproducible test
    )

    schemas = instrumentation.process_spec(sample_spec_dir, execute_ddl=True)

    assert len(schemas) > 0
    assert context_agent.update_context.called

    latest = context_agent.get_latest_context()
    assert latest["version"] >= 2
    # At least one of the new tables got documented in the Auto-instrumented
    # tables section, not just silently created.
    assert any(s.name in latest["content"] for s in schemas)


def test_analytics_agent_receives_latest_context(fake_client, mock_llm_call):
    """
    Test 2: AnalyticsAgent always reads the LATEST version of the document,
    including content ContextAgent only just wrote.
    """
    context_agent = ContextAgent(client=fake_client, llm_call_fn=mock_llm_call)
    context_agent.load_v1()

    next_version = context_agent.update_context(
        new_tables=[{"name": "express_checkout_shown", "ddl": "CREATE TABLE atlys.express_checkout_shown (id UUID, timestamp DateTime, user_id String)"}],
        source_spec="# Express Checkout\nTracks express checkout impressions.",
    )
    assert next_version is not None and next_version >= 2

    latest_ctx = context_agent.get_latest_context()
    assert latest_ctx["version"] == next_version
    assert "express_checkout_shown" in latest_ctx["content"]

    analytics_agent = AnalyticsAgent(client=fake_client, database="atlys", context_agent=context_agent, openrouter_config=None)
    context_text = analytics_agent._context_text()
    assert "express_checkout_shown" in context_text
    assert f"version {next_version}" in context_text


def test_surface_and_resolve_context_flags(fake_client, mock_llm_call):
    """
    Test 3: Surface an obsolete/stale fact (a registered table that no longer
    exists -- the literal freshness check Section 9 of the document asks for)
    and verify the resolve workflow removes it and bumps the version again.
    """
    context_agent = ContextAgent(client=fake_client, llm_call_fn=mock_llm_call)
    context_agent.load_v1()

    # Simulate a table that was registered but no longer actually exists
    # (e.g. dropped after the fact) without ever running its CREATE TABLE, so
    # it's absent from fake_client.existing_tables.
    fake_client.registered_tables.add("ghost_table")

    flags = context_agent.run_audit()
    assert len(flags) == 1
    assert flags[0]["entity"] == "ghost_table"
    assert flags[0]["flag_type"] == "stale_metric"

    after_audit = context_agent.get_latest_context()
    assert after_audit["version"] == 2
    assert "ghost_table" in after_audit["content"]

    # Re-running audit on an unchanged document must not re-flag the same issue.
    assert context_agent.run_audit() == []
    assert context_agent.get_latest_context()["version"] == 2

    notes = context_agent.resolve_flag(entity="ghost_table", key="table_existence")
    assert notes

    resolved = context_agent.get_latest_context()
    assert resolved["version"] == 3
    assert "ghost_table" not in resolved["content"]
