"""CRUD for ``meta_events``."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, Engine, text

from instrumentation_agent.db.connection import get_engine
from instrumentation_agent.models.domain import EventProfile
from instrumentation_agent.utils.serialize import row_to_dict

# Freshly registered / feature appended; done = already linked for this feature.
STATUS_UPDATED = "updated"
STATUS_DONE = "done"


def _split_feature_ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def append_feature_id(existing: str, feature_id: str) -> str:
    """Return CSV with ``feature_id`` appended if not already present."""
    ids = _split_feature_ids(existing)
    if feature_id not in ids:
        ids.append(feature_id)
    return ",".join(ids)


class MetaEventsCRUD:
    """Create / read / delete rows in ``meta_events``."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def replace_for_feature(
        self,
        *,
        feature_id: str,
        events: list[EventProfile],
        conn: Connection | None = None,
    ) -> None:
        """Upsert events for a feature (append feature_id; status=done)."""

        def _write(c: Connection) -> None:
            for ev in events:
                self.insert_if_missing(
                    event_name=ev.event_name,
                    feature_id=feature_id,
                    ch_table=ev.ch_table,
                    columns=ev.columns,
                    status=STATUS_DONE,
                    conn=c,
                )

        if conn is not None:
            _write(conn)
            return
        with self._engine.begin() as opened:
            _write(opened)

    def list_by_feature_id(self, feature_id: str) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT event_name, feature_id, ch_table, columns, status,
                           registered_at
                    FROM meta_events
                    WHERE :feature_id = ANY (string_to_array(feature_id, ','))
                    ORDER BY event_name
                    """
                ),
                {"feature_id": feature_id},
            ).all()
        return [row_to_dict(r) for r in rows]

    def get_by_event_name(
        self,
        event_name: str,
        *,
        conn: Connection | None = None,
    ) -> dict[str, Any] | None:
        sql = text(
            """
            SELECT event_name, feature_id, ch_table, columns, status,
                   registered_at
            FROM meta_events
            WHERE event_name = :event_name
            """
        )
        params = {"event_name": event_name}

        def _read(c: Connection) -> dict[str, Any] | None:
            row = c.execute(sql, params).first()
            return row_to_dict(row) if row else None

        if conn is not None:
            return _read(conn)
        with self._engine.connect() as opened:
            return _read(opened)

    def insert_if_missing(
        self,
        *,
        event_name: str,
        feature_id: str,
        ch_table: str,
        columns: dict[str, str] | None = None,
        status: str = STATUS_UPDATED,
        conn: Connection | None = None,
    ) -> str:
        """Insert event, or append ``feature_id`` when the event already exists.

        Returns one of: ``created`` | ``linked`` | ``exists``.
        """

        def _write(c: Connection) -> str:
            existing = self.get_by_event_name(event_name, conn=c)
            if existing is not None:
                current_ids = str(existing.get("feature_id") or "")
                ids = _split_feature_ids(current_ids)
                if feature_id in ids:
                    c.execute(
                        text(
                            """
                            UPDATE meta_events
                            SET status = :status
                            WHERE event_name = :event_name
                            """
                        ),
                        {"event_name": event_name, "status": STATUS_DONE},
                    )
                    return "exists"

                merged = append_feature_id(current_ids, feature_id)
                c.execute(
                    text(
                        """
                        UPDATE meta_events
                        SET feature_id = :feature_id,
                            status = :status
                        WHERE event_name = :event_name
                        """
                    ),
                    {
                        "event_name": event_name,
                        "feature_id": merged,
                        "status": STATUS_UPDATED,
                    },
                )
                return "linked"

            c.execute(
                text(
                    """
                    INSERT INTO meta_events
                      (event_name, feature_id, ch_table, columns, status)
                    VALUES
                      (:event_name, :feature_id, :ch_table, CAST(:columns AS jsonb),
                       :status)
                    """
                ),
                {
                    "event_name": event_name,
                    "feature_id": feature_id,
                    "ch_table": ch_table,
                    "columns": json.dumps(columns or {}),
                    "status": status,
                },
            )
            return "created"

        if conn is not None:
            return _write(conn)
        with self._engine.begin() as opened:
            return _write(opened)

    def mark_status(
        self,
        event_names: list[str],
        *,
        status: str = STATUS_DONE,
        conn: Connection | None = None,
    ) -> None:
        if not event_names:
            return

        def _write(c: Connection) -> None:
            update = text(
                """
                UPDATE meta_events
                SET status = :status
                WHERE event_name = :event_name
                """
            )
            for event_name in event_names:
                c.execute(update, {"status": status, "event_name": event_name})

        if conn is not None:
            _write(conn)
            return
        with self._engine.begin() as opened:
            _write(opened)
