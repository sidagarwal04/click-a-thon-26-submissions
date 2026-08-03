"""Regression tests for the human-in-the-loop schema approval gate
(`run_pipeline.py::_resolve_approval` / `_write_approval` / `_poll_approval`).

The gate sits between a clean `dry_run()` and `instrumentation.apply()` -- nothing has
been executed or loaded yet at that point, so these tests exercise the real
`pipeline_approvals` table against live ClickHouse rather than mocking it: the whole
point of the design is that the CLI (blocking on stdin) and the Streamlit console
(writing a decision row from a button click) are racing to resolve the SAME table with
no other coordination, so a mock would test the wrong thing.

Two real bugs found while building this, both regression-tested here:
  1. On timeout, the table was left showing `decision='pending'` forever -- nothing
     ever recorded that the run gave up waiting. Fixed by writing a terminal
     'timed_out' row; `test_resolve_approval_writes_a_terminal_row_on_timeout` pins it.
  2. `StageStatus.status` didn't include "pending"/"declined", so the very first call
     to `mark("instrumentation.awaiting_approval", "pending", ...)` crashed with a
     pydantic ValidationError before any approval logic even ran.
"""

from __future__ import annotations

import io
import sys
import threading
import time
import uuid

import pytest

import run_pipeline as rp
from contracts import ColumnSpec, DDLProposal, FeatureSemantics, StageStatus


@pytest.fixture(scope="module")
def ch():
    from ch import CH

    try:
        client = CH()
        client.run_select("SELECT 1")
        client.run_select("SELECT 1 FROM pipeline_approvals LIMIT 1", max_rows=1)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ClickHouse / pipeline_approvals not reachable: {exc}")
    return client


def _run_id() -> str:
    return "test_" + uuid.uuid4().hex


def _fake_proposal(table: str) -> DDLProposal:
    sem = FeatureSemantics(
        feature_slug="approval_gate_test", table_fqn=f"atlys.{table}",
        event_types=["a"], entity_key="user_id", ordered_steps=["a"],
    )
    return DDLProposal(
        table_name=table,
        columns=[ColumnSpec(name="event", type="LowCardinality(String)", json_path="event")],
        engine="MergeTree", order_by=["event"], materialized_views=[],
        rationale={"order_by": "test"}, ddl_sql=[], semantics=sem,
    )


# --------------------------------------------------------------------------
# StageStatus -- the crash the very first version of this feature hit
# --------------------------------------------------------------------------


def test_stage_status_accepts_pending_and_declined() -> None:
    StageStatus(stage="instrumentation.awaiting_approval", status="pending")
    StageStatus(stage="instrumentation.approval", status="declined")


# --------------------------------------------------------------------------
# _write_approval / _poll_approval -- the primitives
# --------------------------------------------------------------------------


def test_write_then_poll_reads_the_decision_back(ch) -> None:
    run_id = _run_id()
    rp._write_approval(ch, run_id, "f_x", "DDL", "{}", "pending", "")
    rp._write_approval(ch, run_id, "f_x", "DDL", "{}", "approved", "test-writer")

    approved, decided_by = rp._poll_approval(ch, run_id, timeout_s=5)
    assert approved is True
    assert decided_by == "test-writer"


def test_poll_approval_times_out_when_nothing_decides(ch) -> None:
    run_id = _run_id()
    rp._write_approval(ch, run_id, "f_x", "DDL", "{}", "pending", "")

    approved, decided_by = rp._poll_approval(ch, run_id, timeout_s=3)
    assert approved is False
    assert decided_by.startswith("timed out")


def test_poll_approval_picks_up_a_decision_written_mid_poll(ch) -> None:
    """Exactly what the Streamlit Approve button relies on: a decision landing from
    a completely separate process/thread while _poll_approval is already sleeping."""
    run_id = _run_id()
    rp._write_approval(ch, run_id, "f_x", "DDL", "{}", "pending", "")

    def _decide_later() -> None:
        # A fresh CH() here, not the shared `ch` fixture: clickhouse-connect clients
        # aren't safe to share across threads/processes -- exactly why production
        # never does either (the CLI process and the UI's browser session each hold
        # their own client and only ever meet through this table, never in-process).
        from ch import CH

        time.sleep(2)
        rp._write_approval(CH(), run_id, "f_x", "DDL", "{}", "rejected", "ui-thread")

    threading.Thread(target=_decide_later, daemon=True).start()
    t0 = time.time()
    approved, decided_by = rp._poll_approval(ch, run_id, timeout_s=20)
    elapsed = time.time() - t0

    assert approved is False
    assert decided_by == "ui-thread"
    assert elapsed < 10, "should pick up the decision within a couple of poll ticks, not the full timeout"


# --------------------------------------------------------------------------
# _resolve_approval -- the full gate, all three paths
# --------------------------------------------------------------------------


def test_resolve_approval_auto_yes_skips_the_wait(ch) -> None:
    run_id = _run_id()
    proposal = _fake_proposal("f_auto_yes_test")

    t0 = time.time()
    approved, decided_by = rp._resolve_approval(ch, run_id, proposal, auto_yes=True, timeout_s=999)
    elapsed = time.time() - t0

    assert approved is True
    assert decided_by == "auto (--yes)"
    assert elapsed < 5, "--yes must never wait"

    rows = ch.run_select(
        f"SELECT decision FROM pipeline_approvals WHERE run_id = '{run_id}' ORDER BY ts"
    )
    assert [r["decision"] for r in rows] == ["pending", "approved"]


def test_resolve_approval_writes_a_terminal_row_on_timeout(ch, monkeypatch) -> None:
    """The bug: a timed-out run used to leave the table saying 'pending' forever."""
    run_id = _run_id()
    proposal = _fake_proposal("f_timeout_test")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))  # not a TTY -> polling branch

    approved, decided_by = rp._resolve_approval(ch, run_id, proposal, auto_yes=False, timeout_s=3)
    assert approved is False
    assert decided_by.startswith("timed out")

    rows = ch.run_select(
        f"SELECT decision FROM pipeline_approvals WHERE run_id = '{run_id}' ORDER BY ts"
    )
    assert rows[-1]["decision"] == "timed_out", (
        "must not be left as 'pending' -- that misreports a dead run as still awaiting a decision"
    )


def test_resolve_approval_non_interactive_sees_an_external_approval(ch, monkeypatch) -> None:
    """The actual UI flow: something else (a Streamlit button, in production) writes
    'approved' while this call is polling, and _resolve_approval must return True."""
    run_id = _run_id()
    proposal = _fake_proposal("f_external_approve_test")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    def _approve_later() -> None:
        from ch import CH  # separate client instance -- see the comment above

        time.sleep(2)
        rp._write_approval(CH(), run_id, proposal.table_name, "DDL", "{}", "approved", "ui")

    threading.Thread(target=_approve_later, daemon=True).start()
    approved, decided_by = rp._resolve_approval(ch, run_id, proposal, auto_yes=False, timeout_s=20)
    assert approved is True
    assert decided_by == "ui"
