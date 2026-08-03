"""JAL-73: system of record for investigations and chat sessions.

ClickHouse is the single datastore, so completed Evidence Bundles live here rather than on
disk or in memory. Two tables, split by concern:

  bundles        — the actual evidence. Flattened columns (metric, observed/expected, primary
                    factor, localized segment, ruled-out summary) let the dashboard render a
                    card without parsing JSON; `bundle` itself is the full schema-valid
                    EvidenceBundle, the source of truth for GET /bundle/{id}.
  investigations — a lean session/tracking record (trace id, chat session, timestamps) that
                    references its evidence via `bundle_id` rather than duplicating it.

`trace_id` is persisted because POST /investigate and POST /narrate/{id} are separate HTTP
calls. Narration must attach its generation span to the trace the investigation already
opened; without the stored id it would start an orphaned second trace and the SQL steps
would look unrelated to the LLM call.

Row mapping (`_to_bundle_row` / `_bundle_from_row`) is pure and unit-tested without a database.
Reads and writes here use the raw client rather than `data.client.run_query`, because
bookkeeping should not appear as analysis spans inside an investigation trace.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from data.client import get_client
from models import EvidenceBundle

BUNDLES = "bundles"
INVESTIGATIONS = "investigations"
SESSIONS = "chat_sessions"
TURNS = "chat_turns"
TRACE_VIEWS = "trace_views"

log = logging.getLogger(__name__)

_BUNDLE_COLUMNS = [
    "investigation_id", "created_at", "updated_at", "window_start", "window_end",
    "metric", "direction", "observed", "expected", "pct_delta", "score", "is_anomaly",
    "primary_factor", "localized_segment", "ruled_out_count", "ruled_out_summary",
    "narrative", "narrated", "trace_url", "bundle",
]

_INVESTIGATION_COLUMNS = [
    "investigation_id", "bundle_id", "trace_id", "session_id", "created_at", "updated_at",
]


def _now() -> datetime:
    # ClickHouse DateTime is naive; store UTC without tzinfo so round-trips compare equal.
    return datetime.now(UTC).replace(tzinfo=None)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


# ---- pure row mapping ------------------------------------------------------

def _to_bundle_row(bundle: EvidenceBundle) -> list[Any]:
    """Flatten a bundle into a `bundles` row, ordered to match _BUNDLE_COLUMNS.

    Every detection run gets a row — is_anomaly=0 rows are the (common) "checked,
    normal" traceability records; is_anomaly=1 rows carry the drilled-down evidence."""
    ruled = bundle.ruled_out or []
    return [
        bundle.investigation_id,
        _naive(bundle.created_at),
        _now(),
        _naive(bundle.target_window.start),
        _naive(bundle.target_window.end),
        bundle.metric,
        bundle.anomaly.direction,
        bundle.anomaly.observed,
        bundle.anomaly.expected,
        bundle.anomaly.pct_delta,
        bundle.anomaly.score,
        1 if bundle.anomaly.detected else 0,
        bundle.factor_decomposition.primary_factor if bundle.factor_decomposition else "",
        json.dumps(bundle.localized_segment or {}),
        len(ruled),
        ", ".join(r.hypothesis for r in ruled),
        bundle.narrative or "",
        1 if bundle.narrative else 0,
        bundle.trace_url or "",
        bundle.model_dump_json(),
    ]


def _bundle_from_row(row: dict[str, Any]) -> EvidenceBundle:
    """Rehydrate the bundle. The `bundle` column is the source of truth; the other
    columns exist only so `bundles` is queryable in SQL without parsing JSON."""
    return EvidenceBundle.model_validate_json(row["bundle"])


def _to_investigation_row(
    bundle_id: str, trace_id: str | None, session_id: str | None, created_at: datetime
) -> list[Any]:
    """Flatten into an `investigations` row, ordered to match _INVESTIGATION_COLUMNS.
    investigation_id == bundle_id today (one investigation produces exactly one bundle)."""
    return [bundle_id, bundle_id, trace_id or "", session_id or "", _naive(created_at), _now()]


# ---- bundles + investigations ----------------------------------------------

def save_bundle(
    bundle: EvidenceBundle, trace_id: str | None = None, session_id: str | None = None
) -> None:
    """Insert or replace the evidence row and its investigation record (both ReplacingMergeTree
    keyed on investigation_id, so a later /narrate call rewrites both in place)."""
    get_client().insert(BUNDLES, [_to_bundle_row(bundle)], column_names=_BUNDLE_COLUMNS)
    get_client().insert(
        INVESTIGATIONS,
        [_to_investigation_row(bundle.investigation_id, trace_id, session_id, bundle.created_at)],
        column_names=_INVESTIGATION_COLUMNS,
    )


def load_bundle(investigation_id: str) -> EvidenceBundle | None:
    """Resolve investigation_id -> bundle_id via `investigations`, then read the evidence
    from `bundles`. A single join rather than two round trips."""
    rows = get_client().query(
        f"SELECT b.bundle FROM {INVESTIGATIONS} AS i FINAL "
        f"INNER JOIN {BUNDLES} AS b FINAL ON b.investigation_id = i.bundle_id "
        f"WHERE i.investigation_id = {{id:String}}",
        parameters={"id": investigation_id},
    ).result_rows
    return EvidenceBundle.model_validate_json(rows[0][0]) if rows else None


def load_latest_anomaly(metric: str | None = None) -> EvidenceBundle | None:
    """Most recent bundle where an anomaly was actually detected, optionally for one metric.

    This is what the chat's "replay this incident" flow reads: the dashboard shows an anomaly,
    the user asks to replay it, and this resolves 'it' without needing an id in the message."""
    where = "WHERE is_anomaly = 1" + (" AND metric = {m:String}" if metric else "")
    rows = get_client().query(
        f"SELECT bundle FROM {BUNDLES} FINAL {where} ORDER BY created_at DESC LIMIT 1",
        parameters={"m": metric} if metric else {},
    ).result_rows
    return EvidenceBundle.model_validate_json(rows[0][0]) if rows else None


def load_nearby_bundles(
    metric: str, center_start: datetime, center_end: datetime,
    days: int = 7, exclude_id: str | None = None,
) -> list[dict[str, Any]]:
    """Every stored `bundles` row for `metric` within `days` of [center_start, center_end] —
    seeded context rows (mostly is_anomaly=0) plus any other anomalies nearby. This is how the
    chat answers "what were normal values that day": the anomaly bundle itself only knows its
    own window, so a genuinely different question needs a different query, not a re-read of the
    same JSON. Ordered chronologically so a reply can describe the walk up to and past the event.
    """
    lo = _naive(center_start) - timedelta(days=days)
    hi = _naive(center_end) + timedelta(days=days)
    exclude = "AND investigation_id != {ex:String}" if exclude_id else ""
    result = get_client().query(
        f"SELECT investigation_id, window_start, window_end, direction, observed, expected, "
        f"pct_delta, is_anomaly FROM {BUNDLES} FINAL "
        f"WHERE metric = {{m:String}} AND window_start >= {{lo:DateTime}} "
        f"AND window_start <= {{hi:DateTime}} {exclude} "
        f"ORDER BY window_start",
        parameters={"m": metric, "lo": lo, "hi": hi, **({"ex": exclude_id} if exclude_id else {})},
    )
    return [dict(zip(result.column_names, r)) for r in result.result_rows]


def load_trace_id(investigation_id: str) -> str | None:
    """The Langfuse trace opened by /investigate, so /narrate can attach to it."""
    return load_meta(investigation_id)[0]


def load_meta(investigation_id: str) -> tuple[str | None, str | None]:
    """(trace_id, session_id) for an existing investigation.

    Both must be re-supplied on any later write. `investigations` is a ReplacingMergeTree keyed
    on investigation_id, so a save that omits them does not merge — it replaces the row with
    empty strings and silently breaks two links: /narrate's trace reattachment, and the
    session -> investigation association that GET /chat/sessions/{id} depends on.
    """
    rows = get_client().query(
        f"SELECT trace_id, session_id FROM {INVESTIGATIONS} FINAL "
        f"WHERE investigation_id = {{id:String}}",
        parameters={"id": investigation_id},
    ).result_rows
    if not rows:
        return None, None
    return (rows[0][0] or None), (rows[0][1] or None)


_DASHBOARD_FIELDS = [  # everything NOT in _INCIDENT_KEY; those are grouping keys already
    "investigation_id", "window_end", "direction",
    "observed", "expected", "pct_delta", "score", "is_anomaly", "primary_factor",
    "ruled_out_count", "ruled_out_summary", "narrative", "narrated", "trace_url",
]

# One incident = one metric moving in one window in one segment. Re-investigating it is a new
# bundle but not a new finding.
_INCIDENT_KEY = "metric, window_start, localized_segment"


def dataset_bounds(hourly_table: str, client=None) -> tuple[datetime, datetime] | None:
    """(first, last) hour held by a dataset's rollup, or None when it is empty."""
    client = client or get_client()
    count, lo, hi = client.query(
        f"SELECT count(), min(hour), max(hour) FROM {hourly_table}"
    ).result_rows[0]
    return (lo, hi) if count else None


def list_dashboard(limit: int = 50, since: datetime | None = None,
                   within: tuple[datetime, datetime] | None = None) -> list[dict[str, Any]]:
    """Dashboard poll query, straight off `bundles`. `since` (a row's created_at from a prior
    poll) returns only rows created after it, so a polling client doesn't re-fetch everything
    every tick. Excludes the `bundle` JSON column — the card view doesn't need it.

    Deduplicated to DISTINCT INCIDENTS, newest run wins. Investigating the same incident twice
    (a re-run, or a sweep finding you drill again) writes two bundles, and without this the
    switcher lists the same anomaly five times — which is what it did.
    """
    # `within` scopes the feed to the active dataset. bundles holds every investigation ever
    # run, so without it a dev-era incident (requests -43.5% on Jun 21) sits in the switcher
    # while the dashboard is pointed at the streamed slice. The datasets are disjoint in time,
    # so their window_start ranges separate them cleanly.
    clauses = []
    params: dict[str, Any] = {"n": limit}
    if since:
        clauses.append("created_at > {since:DateTime}")
        params["since"] = _naive(since)
    if within:
        clauses.append("window_start >= {wlo:DateTime} AND window_start <= {whi:DateTime}")
        params["wlo"], params["whi"] = _naive(within[0]), _naive(within[1])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # `latest_at`, not `created_at`: aliasing an aggregate to the column name it aggregates makes
    # every other argMax(..., created_at) resolve to the alias and fail as a nested aggregate.
    latest = ", ".join(f"argMax({f}, created_at) AS {f}" for f in _DASHBOARD_FIELDS)
    result = get_client().query(
        f"SELECT {_INCIDENT_KEY}, max(created_at) AS latest_at, {latest} "
        f"FROM {BUNDLES} FINAL {where} "
        f"GROUP BY {_INCIDENT_KEY} ORDER BY latest_at DESC LIMIT {{n:UInt32}}",
        parameters=params,
    )
    rows = [dict(zip(result.column_names, r)) for r in result.result_rows]
    for row in rows:  # callers expect created_at, not the internal ordering alias
        row["created_at"] = row.pop("latest_at")
    return rows


def list_investigations(limit: int = 50) -> list[dict[str, Any]]:
    """Investigation history for the dashboard's past-runs panel: session fields from
    `investigations` (trace/session ids) joined with the evidence summary from `bundles`
    (metric, window, primary factor, localization, detected/narrated flags) via bundle_id.
    `detected` is an alias for `bundles.is_anomaly` — the field name the frontend expects."""
    result = get_client().query(
        f"SELECT i.investigation_id AS investigation_id, i.created_at AS created_at, "
        f"b.metric AS metric, b.window_start AS window_start, b.window_end AS window_end, "
        f"b.primary_factor AS primary_factor, b.localized_segment AS localized_segment, "
        f"b.is_anomaly AS detected, b.narrated AS narrated, "
        f"i.trace_id AS trace_id, i.session_id AS session_id "
        f"FROM {INVESTIGATIONS} AS i FINAL "
        f"LEFT JOIN {BUNDLES} AS b FINAL ON b.investigation_id = i.bundle_id "
        f"ORDER BY i.created_at DESC LIMIT {{n:UInt32}}",
        parameters={"n": limit},
    )
    return [dict(zip(result.column_names, r)) for r in result.result_rows]


# ---- chat sessions ---------------------------------------------------------

def upsert_session(context_id: str, title: str | None = None) -> None:
    now = _now()
    existing = get_client().query(
        f"SELECT created_at, title FROM {SESSIONS} FINAL WHERE context_id = {{id:String}}",
        parameters={"id": context_id},
    ).result_rows
    created = existing[0][0] if existing else now
    resolved = title if title is not None else (existing[0][1] if existing else "")
    get_client().insert(
        SESSIONS, [[context_id, resolved, created, now]],
        column_names=["context_id", "title", "created_at", "updated_at"],
    )


def add_turn(context_id: str, role: str, message: str) -> None:
    get_client().insert(
        TURNS, [[context_id, role, message, _now()]],
        column_names=["context_id", "role", "message", "created_at"],
    )


def get_turns(context_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Oldest-first, capped to the most recent `limit` turns."""
    result = get_client().query(
        f"SELECT role, message, created_at FROM ("
        f"  SELECT role, message, created_at FROM {TURNS} WHERE context_id = {{id:String}} "
        f"  ORDER BY created_at DESC LIMIT {{n:UInt32}}"
        f") ORDER BY created_at ASC",
        parameters={"id": context_id, "n": limit},
    )
    return [dict(zip(result.column_names, r)) for r in result.result_rows]


def list_sessions(limit: int = 100) -> list[dict[str, Any]]:
    result = get_client().query(
        f"SELECT context_id, title, created_at, updated_at FROM {SESSIONS} FINAL "
        f"ORDER BY updated_at DESC LIMIT {{n:UInt32}}",
        parameters={"n": limit},
    )
    return [dict(zip(result.column_names, r)) for r in result.result_rows]


def delete_session(context_id: str) -> bool:
    client = get_client()
    exists = client.query(
        f"SELECT count() FROM {SESSIONS} FINAL WHERE context_id = {{id:String}}",
        parameters={"id": context_id},
    ).result_rows[0][0]
    if not exists:
        return False
    for table in (SESSIONS, TURNS):
        client.command(
            f"ALTER TABLE {table} DELETE WHERE context_id = {{id:String}}",
            parameters={"id": context_id},
        )
    return True


def delete_all_sessions() -> int:
    client = get_client()
    count = client.query(f"SELECT count() FROM {SESSIONS} FINAL").result_rows[0][0]
    for table in (SESSIONS, TURNS):
        client.command(f"TRUNCATE TABLE {table}")
    return count


# ---- trace snapshots -------------------------------------------------------
#
# Langfuse owns the LIVE trace; this owns the HISTORY. The drawer reads the snapshot first, so
# a trace stays readable after Langfuse is reset, wiped (`docker compose down -v`) or is simply
# down — which is exactly how the "Trace not found" dead links happened.

@lru_cache(maxsize=1)
def _ensure_trace_views() -> None:
    """Create the snapshot table on demand, from schema.sql so there is one source of truth.

    Created here rather than requiring a manual DDL step: the table arrived after the initial
    schema, and `CREATE TABLE IF NOT EXISTS` in schema.sql never runs itself.
    """
    from data.load import _statements

    get_client().command(_statements((TRACE_VIEWS,))[0])


def save_trace_view(investigation_id: str, view: dict[str, Any]) -> None:
    """Persist the reshaped trace. Best-effort: losing a snapshot must never fail a request."""
    try:
        _ensure_trace_views()
        get_client().insert(
            TRACE_VIEWS, [[investigation_id, _now(), json.dumps(view)]],
            column_names=["investigation_id", "created_at", "view"],
        )
    except Exception as exc:  # noqa: BLE001 - the live trace answered; the snapshot is an extra
        log.warning("Could not snapshot trace for %s: %s", investigation_id, exc)


def load_trace_view(investigation_id: str) -> dict[str, Any] | None:
    try:
        _ensure_trace_views()
        rows = get_client().query(
            f"SELECT view FROM {TRACE_VIEWS} FINAL WHERE investigation_id = {{id:String}}",
            parameters={"id": investigation_id},
        ).result_rows
    except Exception:  # noqa: BLE001 - no snapshot table yet / DB hiccup -> fall back to live
        return None
    return json.loads(rows[0][0]) if rows else None
