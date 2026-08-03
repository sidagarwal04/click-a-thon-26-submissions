"""Durable UI history for schema changes and agent insights."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from ..agents.context_store import context_dialect
from ..agents.types import ColumnSpec, InsightReport, TableSpec
from ..config import Settings

SCHEMA_CHANGES_TABLE = "ui_schema_changes"
INSIGHTS_TABLE = "ui_agent_insights"


def _tables() -> list[TableSpec]:
    """Small append-only audit tables; no partitioning is needed at this scale."""
    return [
        TableSpec(
            name=SCHEMA_CHANGES_TABLE,
            columns=[
                ColumnSpec("created_at", "DateTime64(3, 'UTC')", codec="Delta, ZSTD(1)"),
                ColumnSpec("run_id", "String"),
                ColumnSpec("change_kind", "LowCardinality(String)"),
                ColumnSpec("table_name", "String", default="''"),
                ColumnSpec("sql", "String", codec="ZSTD(3)"),
                ColumnSpec("ok", "Bool"),
                ColumnSpec("error", "String", default="''", codec="ZSTD(3)"),
            ],
            order_by=["created_at", "run_id"],
            comment="append-only timeline of schema statements executed by the agent",
        ),
        TableSpec(
            name=INSIGHTS_TABLE,
            columns=[
                ColumnSpec("created_at", "DateTime64(3, 'UTC')", codec="Delta, ZSTD(1)"),
                ColumnSpec("run_id", "String"),
                ColumnSpec("context_version", "UInt32"),
                ColumnSpec("cut", "LowCardinality(String)"),
                ColumnSpec("confidence", "Float32"),
                ColumnSpec("headline", "String", codec="ZSTD(3)"),
                ColumnSpec("detail", "String", default="''", codec="ZSTD(3)"),
                ColumnSpec("why", "String", codec="ZSTD(3)"),
                ColumnSpec("recommendation", "String", default="''", codec="ZSTD(3)"),
                ColumnSpec("context_refs", "Array(String)"),
            ],
            order_by=["created_at", "run_id"],
            comment="append-only history of analytics-agent insights and confidence",
        ),
    ]


class UIHistoryStore:
    def __init__(self, client: Any, settings: Settings) -> None:
        self.client = client
        self.dialect = context_dialect(settings)

    def ensure_schema(self) -> None:
        self.client.command(self.dialect.create_database())
        for table in _tables():
            self.client.command(self.dialect.create_table(table))

    @property
    def _insert_settings(self) -> dict[str, int]:
        # UI runs produce small batches. Server-side buffering avoids creating
        # one tiny part per click while still waiting for durable acknowledgement.
        return {"async_insert": 1, "wait_for_async_insert": 1}

    def record_schema_changes(self, run_id: str, statements: list[Any]) -> None:
        if not statements:
            return
        now = datetime.now(UTC)
        self.client.insert(
            table=SCHEMA_CHANGES_TABLE,
            database=self.dialect.database,
            column_names=[
                "created_at", "run_id", "change_kind", "table_name", "sql", "ok", "error"
            ],
            data=[
                [now, run_id, s.kind, s.table or "", s.sql, bool(s.ok), s.error or ""]
                for s in statements
            ],
            settings=self._insert_settings,
        )

    def record_insights(self, run_id: str, report: InsightReport) -> None:
        if not report.insights:
            return
        now = datetime.now(UTC)
        self.client.insert(
            table=INSIGHTS_TABLE,
            database=self.dialect.database,
            column_names=[
                "created_at", "run_id", "context_version", "cut", "confidence",
                "headline", "detail", "why", "recommendation", "context_refs",
            ],
            data=[
                [
                    now, run_id, report.context_version, i.cut, i.confidence,
                    i.headline, i.detail, i.why, i.recommendation, i.context_refs,
                ]
                for i in report.insights
            ],
            settings=self._insert_settings,
        )

    def schema_changes(self, limit: int = 100) -> list[dict[str, Any]]:
        result = self.client.query(
            f"SELECT created_at, run_id, change_kind, table_name, sql, ok, error "
            f"FROM {self.dialect.qualified(SCHEMA_CHANGES_TABLE)} "
            f"ORDER BY created_at DESC LIMIT {int(limit)}"
        )
        changes = [
            {
                "created_at": str(r[0]), "run_id": r[1], "kind": r[2], "table": r[3],
                "sql": r[4], "ok": bool(r[5]), "error": r[6],
            }
            for r in (getattr(result, "result_rows", None) or [])
        ]
        # Legacy rows recorded statements that succeeded, including idempotent
        # CREATE IF NOT EXISTS no-ops. Recover their target names, then retain
        # only CREATEs whose table metadata changed at the recorded time.
        for change in changes:
            if not change["table"]:
                match = re.search(r"`[^`]+`\.`([^`]+)`", change["sql"])
                if match:
                    change["table"] = match.group(1)

        altered = {
            (change["run_id"], change["table"])
            for change in changes
            if change["kind"] == "alter_table"
        }
        create_names = sorted(
            {change["table"] for change in changes if change["kind"] == "create_table"}
        )
        modified: dict[str, datetime] = {}
        if create_names:
            table_result = self.client.query(
                "SELECT name, metadata_modification_time FROM system.tables "
                "WHERE database = {db:String} AND name IN {names:Array(String)}",
                parameters={"db": self.dialect.database, "names": create_names},
            )
            modified = {
                str(row[0]): row[1]
                for row in (getattr(table_result, "result_rows", None) or [])
            }

        actual = []
        for change in changes:
            if change["kind"] == "create_database":
                continue
            if change["kind"] != "create_table":
                actual.append(change)
                continue
            if (change["run_id"], change["table"]) in altered:
                continue
            table_modified = modified.get(change["table"])
            try:
                recorded_at = datetime.fromisoformat(
                    change["created_at"].replace("Z", "+00:00")
                )
                if table_modified is not None:
                    if table_modified.tzinfo is None:
                        table_modified = table_modified.replace(tzinfo=UTC)
                    if recorded_at.tzinfo is None:
                        recorded_at = recorded_at.replace(tzinfo=UTC)
                    if abs((table_modified - recorded_at).total_seconds()) <= 60:
                        actual.append(change)
            except (TypeError, ValueError):
                # Ambiguous legacy rows stay visible rather than being lost.
                actual.append(change)
        return actual[:limit]

    def insights(self, limit: int = 100) -> list[dict[str, Any]]:
        result = self.client.query(
            f"SELECT created_at, run_id, context_version, cut, confidence, headline, "
            f"detail, why, recommendation, context_refs "
            f"FROM {self.dialect.qualified(INSIGHTS_TABLE)} "
            f"ORDER BY created_at DESC, confidence DESC LIMIT {int(limit)}"
        )
        return [
            {
                "created_at": str(r[0]), "run_id": r[1], "context_version": r[2],
                "cut": r[3], "confidence": float(r[4]), "headline": r[5],
                "detail": r[6], "why": r[7], "recommendation": r[8],
                "context_refs": list(r[9] or []),
            }
            for r in (getattr(result, "result_rows", None) or [])
        ]
