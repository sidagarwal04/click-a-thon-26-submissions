"""Publish a new context_version: copy-forward parent items + apply deltas."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from context_agent.db import get_writable_engine

_VALID_KINDS = frozenset(
    {"entity", "metric", "join", "funnel_step", "issue", "contradiction"}
)


def _normalize_payload(payload: Any) -> str:
    if payload is None:
        return "{}"
    if isinstance(payload, str):
        # Validate JSON
        json.loads(payload)
        return payload
    return json.dumps(payload)


def _validate_item(item: dict[str, Any]) -> dict[str, Any]:
    kind = (item.get("kind") or "").strip()
    item_key = (item.get("item_key") or "").strip()
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"invalid kind {kind!r}; expected one of {sorted(_VALID_KINDS)}"
        )
    if not item_key:
        raise ValueError("item_key is required for each upsert/delete item")
    return {
        "kind": kind,
        "item_key": item_key,
        "label": item.get("label"),
        "payload": _normalize_payload(item.get("payload", {})),
    }


def _current_version(conn: Connection) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT context_version
            FROM context_versions
            WHERE is_current = true
            LIMIT 1
            """
        )
    ).first()
    return row[0] if row else None


def _copy_forward(conn: Connection, *, parent: str, new_version: str) -> int:
    result = conn.execute(
        text(
            """
            INSERT INTO context_items
              (context_version, kind, item_key, label, payload, created_at, updated_at)
            SELECT
              :new_version, kind, item_key, label, payload, created_at, now()
            FROM context_items
            WHERE context_version = :parent
            """
        ),
        {"new_version": new_version, "parent": parent},
    )
    return result.rowcount or 0


def _upsert_item(conn: Connection, *, version: str, item: dict[str, Any]) -> None:
    conn.execute(
        text(
            """
            INSERT INTO context_items
              (context_version, kind, item_key, label, payload, created_at, updated_at)
            VALUES
              (:version, :kind, :item_key, :label, CAST(:payload AS jsonb), now(), now())
            ON CONFLICT (context_version, kind, item_key) DO UPDATE SET
              label = EXCLUDED.label,
              payload = EXCLUDED.payload,
              updated_at = now()
            """
        ),
        {
            "version": version,
            "kind": item["kind"],
            "item_key": item["item_key"],
            "label": item["label"],
            "payload": item["payload"],
        },
    )


def _delete_item(conn: Connection, *, version: str, kind: str, item_key: str) -> None:
    conn.execute(
        text(
            """
            DELETE FROM context_items
            WHERE context_version = :version
              AND kind = :kind
              AND item_key = :item_key
            """
        ),
        {"version": version, "kind": kind, "item_key": item_key},
    )


def publish_context_version(
    *,
    context_version: str,
    source: str,
    summary: str | None = None,
    feature_id: str | None = None,
    parent_version: str | None = None,
    upserts: list[dict[str, Any]] | None = None,
    deletes: list[dict[str, Any]] | None = None,
    copy_forward: bool = True,
) -> dict[str, Any]:
    """Create a new context version, optionally copy parent items, apply deltas.

    - If ``parent_version`` is omitted, uses the current ``is_current`` version
      (or None for a seed with no parent).
    - When ``copy_forward`` is True and a parent exists, all parent items are
      copied, then ``upserts`` / ``deletes`` are applied.
    - Marks the new version as the sole ``is_current``.
    """
    version = (context_version or "").strip()
    src = (source or "").strip()
    if not version:
        raise ValueError("context_version is required")
    if not src:
        raise ValueError("source is required")

    upsert_items = [_validate_item(i) for i in (upserts or [])]
    delete_items = []
    for d in deletes or []:
        kind = (d.get("kind") or "").strip()
        item_key = (d.get("item_key") or "").strip()
        if kind not in _VALID_KINDS or not item_key:
            raise ValueError(
                f"delete entries need valid kind + item_key; got {d!r}"
            )
        delete_items.append({"kind": kind, "item_key": item_key})

    engine = get_writable_engine()
    with engine.begin() as conn:
        parent = parent_version
        if parent is not None:
            parent = parent.strip() or None
        else:
            parent = _current_version(conn)

        if parent == version:
            raise ValueError("context_version cannot equal parent_version")

        exists = conn.execute(
            text(
                """
                SELECT 1 FROM context_versions
                WHERE context_version = :version
                """
            ),
            {"version": version},
        ).first()
        if exists:
            raise ValueError(f"context_version {version!r} already exists")

        if parent is not None:
            parent_ok = conn.execute(
                text(
                    """
                    SELECT 1 FROM context_versions
                    WHERE context_version = :parent
                    """
                ),
                {"parent": parent},
            ).first()
            if not parent_ok:
                raise ValueError(f"parent_version {parent!r} not found")

        conn.execute(
            text("UPDATE context_versions SET is_current = false WHERE is_current = true")
        )
        conn.execute(
            text(
                """
                INSERT INTO context_versions
                  (context_version, parent_version, source, feature_id,
                   is_current, summary, created_at, updated_at)
                VALUES
                  (:version, :parent, :source, :feature_id,
                   true, :summary, now(), now())
                """
            ),
            {
                "version": version,
                "parent": parent,
                "source": src,
                "feature_id": feature_id,
                "summary": summary,
            },
        )

        copied = 0
        if copy_forward and parent is not None:
            copied = _copy_forward(conn, parent=parent, new_version=version)

        for item in upsert_items:
            _upsert_item(conn, version=version, item=item)

        for d in delete_items:
            _delete_item(
                conn, version=version, kind=d["kind"], item_key=d["item_key"]
            )

        count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM context_items
                WHERE context_version = :version
                """
            ),
            {"version": version},
        ).scalar_one()

    return {
        "context_version": version,
        "parent_version": parent,
        "source": src,
        "feature_id": feature_id,
        "summary": summary,
        "is_current": True,
        "copied_from_parent": copied,
        "upserted": len(upsert_items),
        "deleted": len(delete_items),
        "item_count": int(count),
    }
