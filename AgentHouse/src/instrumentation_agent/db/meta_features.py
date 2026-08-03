"""CRUD for ``meta_features``."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, Engine, text

from instrumentation_agent.db.connection import get_engine
from instrumentation_agent.models.domain import EventProfile
from instrumentation_agent.utils.serialize import row_to_dict


class MetaFeaturesCRUD:
    """Create / read / update rows in ``meta_features``."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def upsert_ok(
        self,
        *,
        feature_id: str,
        spec_path: str,
        events: list[EventProfile],
        conn: Connection | None = None,
    ) -> None:
        journey = [
            {
                "event_name": e.event_name,
                "journey_order": e.journey_order,
                "ch_table": e.ch_table,
            }
            for e in events
        ]
        self._upsert(
            {
                "feature_id": feature_id,
                "journey": json.dumps(journey),
                "spec_path": spec_path,
            },
            conn=conn,
        )

    def upsert_failed(
        self,
        *,
        feature_id: str,
        spec_path: str,
        conn: Connection | None = None,
    ) -> None:
        self._upsert(
            {
                "feature_id": feature_id,
                "journey": "[]",
                "spec_path": spec_path,
            },
            conn=conn,
        )

    def _upsert(self, params: dict[str, Any], *, conn: Connection | None) -> None:
        sql = text(
            """
            INSERT INTO meta_features
              (feature_id, journey, spec_path, updated_at)
            VALUES
              (:feature_id, CAST(:journey AS jsonb), :spec_path, now())
            ON CONFLICT (feature_id) DO UPDATE SET
              journey = EXCLUDED.journey,
              spec_path = EXCLUDED.spec_path,
              updated_at = now()
            """
        )
        if conn is not None:
            conn.execute(sql, params)
            return
        with self._engine.begin() as opened:
            opened.execute(sql, params)

    def get_by_feature_id(
        self,
        feature_id: str,
        *,
        conn: Connection | None = None,
    ) -> dict[str, Any] | None:
        sql = text(
            """
            SELECT feature_id, journey, spec_path, updated_at
            FROM meta_features
            WHERE feature_id = :feature_id
            """
        )
        params = {"feature_id": feature_id}

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
        feature_id: str,
        spec_path: str,
        journey: list[dict[str, Any]],
        conn: Connection | None = None,
    ) -> bool:
        """Insert ``meta_features`` row when absent. Returns True if inserted."""

        def _write(c: Connection) -> bool:
            if self.get_by_feature_id(feature_id, conn=c) is not None:
                return False
            c.execute(
                text(
                    """
                    INSERT INTO meta_features
                      (feature_id, journey, spec_path, updated_at)
                    VALUES
                      (:feature_id, CAST(:journey AS jsonb), :spec_path, now())
                    """
                ),
                {
                    "feature_id": feature_id,
                    "journey": json.dumps(journey),
                    "spec_path": spec_path,
                },
            )
            return True

        if conn is not None:
            return _write(conn)
        with self._engine.begin() as opened:
            return _write(opened)
