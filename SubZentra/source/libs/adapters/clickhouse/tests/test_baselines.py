"""Baselines are read from the ledger, and stay baselines.

Two things are being defended. That the report costs nothing beyond the
ClickHouse the product already runs — it queries `audit_entries`, opens no
second store, and needs no vendor. And that it never becomes a gate: #23 asks
for observed baselines *without* inventing a production threshold, and the
distance between "here is the observed p95" and "the build fails above 4s" is
one well-meaning commit.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import DatabaseError

from zentra_adapter_clickhouse.baselines import (
    AgentBaseline,
    agent_baselines,
    investigation_baseline,
    main,
    render,
)

_AGENTS = [
    AgentBaseline(
        agent_id="insight_v1",
        model="anthropic/claude-sonnet-5",
        outcome="succeeded",
        executions=42,
        latency_p50_ms=1450.0,
        latency_p95_ms=4210.0,
        cost_p50_usd=0.0181,
        cost_p95_usd=0.0402,
        total_cost_usd=0.83,
        total_tokens=64_800,
    )
]
_INVESTIGATIONS = {
    "investigations": 42,
    "cost_p50_usd": 0.0611,
    "cost_p95_usd": 0.1204,
    "cost_total_usd": 2.71,
    "latency_p50_ms": 8100.0,
    "latency_p95_ms": 19400.0,
}


def test_the_report_says_it_is_an_observation_not_a_threshold() -> None:
    output = render(_AGENTS, _INVESTIGATIONS, days=7)

    assert "Observations, not thresholds" in output
    assert "n=42" in output


def test_a_small_sample_says_so_rather_than_implying_precision() -> None:
    """Twelve Investigations do not have a p95, whatever the arithmetic says."""
    output = render(_AGENTS, {**_INVESTIGATIONS, "investigations": 12}, days=7)

    assert "too small for p95" in output


def test_a_large_sample_does_not_carry_the_caveat() -> None:
    output = render(_AGENTS, _INVESTIGATIONS, days=7)

    assert "too small for p95" not in output


def test_an_empty_window_reports_nothing_rather_than_zeroes() -> None:
    """A cost of $0.0000 and no data are different claims."""
    output = render([], {}, days=7)

    assert "Nothing to report" in output
    assert "$0.0000" not in output


def test_reporting_a_baseline_cannot_fail_a_build(monkeypatch) -> None:
    """The exit code is the difference between a baseline and a threshold."""

    class _Client:
        def query(self, *_args, **_kwargs):
            raise AssertionError("should not be reached in this test")

        def close(self) -> None:
            return None

    monkeypatch.setattr("zentra_adapter_clickhouse.baselines._client", _Client)
    monkeypatch.setattr(
        "zentra_adapter_clickhouse.baselines.agent_baselines",
        lambda *_a, **_k: _AGENTS,
    )
    monkeypatch.setattr(
        "zentra_adapter_clickhouse.baselines.investigation_baseline",
        lambda *_a, **_k: _INVESTIGATIONS,
    )
    monkeypatch.setattr(sys, "argv", ["baselines.py", "--days", "7"])

    assert main() == 0


_CLICKHOUSE_HOST = os.getenv("TEST_CLICKHOUSE_HOST")

_needs_clickhouse = pytest.mark.skipif(
    not _CLICKHOUSE_HOST,
    reason="local ClickHouse integration service is not configured",
)


def _runtime_client():
    # The database is overridable so these can be pointed at an empty ledger.
    # They previously asserted on whatever rows happened to exist, which passed
    # on a developer machine and failed on a fresh CI service; being able to run
    # them against an empty table is how that stays fixed.
    return clickhouse_connect.get_client(
        host=_CLICKHOUSE_HOST,
        port=int(os.getenv("TEST_CLICKHOUSE_PORT", "8123")),
        username="zentra_audit_app",
        password="zentra_audit_app",
        database=os.getenv("TEST_CLICKHOUSE_DATABASE", "zentra_audit"),
    )


def _seed(client, *, agent_id: str) -> None:
    """Two executions for one agent: one that worked, one that did not.

    Seeded rather than read, because a test that asserts on whatever happens to
    be in the ledger passes on a developer's machine and fails on a fresh CI
    service — which is exactly what this test did before. Owning the rows also
    means the expected figures can be exact instead of "more than zero".
    """
    now = datetime.now(UTC)
    rows = [
        ("agent.execution_completed", 1000, 200, 100, "0.01000000"),
        ("agent.execution_completed", 3000, 400, 200, "0.03000000"),
        ("agent.execution_failed", 500, 50, 0, "0.00500000"),
        # Excluded by the query: a `_started` row carries no usage, and
        # averaging it in would halve every figure.
        ("agent.execution_started", 0, 0, 0, "0.00000000"),
    ]
    for index, (event_type, latency, inp, out, cost) in enumerate(rows):
        client.insert(
            "audit_entries",
            [[
                uuid4(), uuid4(), uuid4(), uuid4(), uuid4(),
                event_type, agent_id, uuid4(), index,
                now, now, latency, inp, out, Decimal(cost),
                "sha256:seed", None, None, [], [], "test/model-1",
                "running", [], "{}", now,
            ]],
            column_names=[
                "entry_id", "trace_id", "span_id", "tenant_id",
                "investigation_id", "event_type", "agent_id", "execution_id",
                "step", "started_at", "completed_at", "latency_ms",
                "input_tokens", "output_tokens", "total_cost_usd", "input_hash",
                "outcome_kind", "confidence", "tools_called", "errors", "model",
                "status", "artifact_refs", "redacted_metadata", "created_at",
            ],
        )


@_needs_clickhouse
def test_the_agent_baseline_reports_the_rows_it_seeded() -> None:
    """Assert on the contents, not on the type.

    An earlier version filtered `status = 'succeeded'`, which is not a value
    that column ever holds — on an agent row `status` is the *Investigation's*
    status, and the execution enum says `success` anyway. The query returned
    zero rows for every window while a test asserting `isinstance(agents, list)`
    passed the whole time.
    """
    agent_id = f"baseline_probe_{uuid4().hex[:12]}"
    client = _runtime_client()
    try:
        _seed(client, agent_id=agent_id)
        agents = [
            agent
            for agent in agent_baselines(client, days=1)
            if agent.agent_id == agent_id
        ]
    finally:
        client.close()

    by_outcome = {agent.outcome: agent for agent in agents}
    assert set(by_outcome) == {"succeeded", "failed"}

    # Two completed rows, and specifically not the `_started` one.
    assert by_outcome["succeeded"].executions == 2
    assert by_outcome["succeeded"].total_tokens == 900
    assert by_outcome["succeeded"].total_cost_usd == pytest.approx(0.04)
    assert by_outcome["succeeded"].latency_p95_ms >= 1000

    assert by_outcome["failed"].executions == 1
    # A failed call still spent money; a budget that ignored it would understate.
    assert by_outcome["failed"].total_cost_usd == pytest.approx(0.005)


@_needs_clickhouse
def test_a_started_row_is_not_counted_as_an_execution() -> None:
    """Its latency, tokens and cost are all zero and would drag every figure."""
    agent_id = f"baseline_probe_{uuid4().hex[:12]}"
    client = _runtime_client()
    try:
        _seed(client, agent_id=agent_id)
        counted = sum(
            agent.executions
            for agent in agent_baselines(client, days=1)
            if agent.agent_id == agent_id
        )
    finally:
        client.close()

    assert counted == 3


@_needs_clickhouse
def test_the_investigation_baseline_counts_the_investigations_it_seeded() -> None:
    client = _runtime_client()
    try:
        before = investigation_baseline(client, days=1)["investigations"]
        _seed(client, agent_id=f"baseline_probe_{uuid4().hex[:12]}")
        after = investigation_baseline(client, days=1)["investigations"]
    finally:
        client.close()

    # Four rows, each with its own investigation_id.
    assert after - before == 4


@_needs_clickhouse
@pytest.mark.parametrize(
    "statement",
    [
        "ALTER TABLE audit_entries DELETE WHERE 1 = 1",
        "TRUNCATE TABLE audit_entries",
        "DROP TABLE audit_entries",
        "ALTER TABLE audit_entries ADD COLUMN leaked String",
    ],
)
def test_the_runtime_user_can_only_insert_and_select(statement: str) -> None:
    """Insert and select, and nothing else — criterion 7.

    Checked by attempting each destructive operation rather than by reading the
    grant table, because what a grant means is decided by the server and not by
    our reading of a DDL file. `UPDATE` is covered in `test_integration.py`;
    these are the four ways to destroy the ledger that it does not cover.
    """
    client = _runtime_client()
    try:
        with pytest.raises(DatabaseError, match="Not enough privileges"):
            client.command(statement)
    finally:
        client.close()
