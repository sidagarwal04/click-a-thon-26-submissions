"""Persistence for the monitoring layer: breach events, incidents, and the
coverage receipts for each sweep.

Separate from engine/store.py, which owns the older investigation/chat tables,
purely so the two can be reasoned about independently -- but it follows the same
hard rule: EVERY write here is best-effort and never raises to the caller. A
persistence failure must not fail or block detection. The deterministic verdict is
already correct and already returned; losing the history row is a lesser harm than
dropping the finding.

The one deliberate exception to "best effort" is that failures are always LOGGED
with the row count that was lost, so a silently shrinking audit trail is visible
rather than inferred.

Reads use FINAL on the ReplacingMergeTree tables. That is not caution for its own
sake: metric_events is keyed on (metric, scope, grain, window_start) so a
re-sweep of the same window replaces rather than duplicates -- but before a merge
completes, a plain read returns BOTH versions, and a duplicated event would be
counted twice in an incident's dollar total.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from engine.ch_client import get_client
from engine.config import settings

logger = logging.getLogger(__name__)

_EVENT_COLUMNS = [
    "event_id", "sweep_run_id", "metric", "scope_type", "scope_value", "grain",
    "window_start", "window_end", "seasonal_cell", "direction", "severity",
    "value", "center", "spread", "deviation_score", "baseline_method",
    "sample_count", "consecutive_points", "expected", "actual", "impact_usd",
    "gated_by_impact", "incident_id", "signature", "status", "label",
]

_COVERAGE_COLUMNS = [
    "run_id", "started_at", "scope_type", "metric", "grain", "window_start", "window_end",
    "entities_total", "entities_evaluated", "entities_breached",
    "skipped_low_power", "skipped_no_band", "skipped_cadence", "skipped_incomplete_window",
    "power_floor", "min_denom_seen", "max_denom_seen", "finest_valid_grain", "skip_reason",
]

_RUN_COLUMNS = [
    "run_id", "started_at", "as_of", "duration_ms", "grains_swept", "scopes_swept",
    "metrics_swept", "cells_total", "evaluations", "breaches", "events_written",
    "incidents_opened", "skipped_low_power", "skipped_no_band", "skipped_cadence",
    "skipped_incomplete_window", "queries_issued", "error",
]

_INCIDENT_COLUMNS = [
    "incident_id", "opened_at", "last_seen_at", "closed_at", "root_scope_type",
    "root_scope_value", "root_metric", "grain", "direction", "signature",
    "signature_confidence", "mechanism", "owner", "impact_usd", "impact_usd_per_day",
    "windows_spanned", "member_event_count",
    "breached_metrics", "fingerprint", "narration", "narration_available",
    "investigation_id", "langfuse_trace_url", "evidence_json", "label",
    "gated_by_impact", "evidence_score", "analysis_json",
]

# The incident's own diagnosis, persisted independently of whether an LLM
# investigation ran for it. See the analysis_json comment in monitoring_state.sql.
_ANALYSIS_KEYS = (
    "ruled_out", "seasonality", "impact_breakdown", "history",
    "absorbed", "evidence_score_detail",
)

_EPOCH = datetime(1970, 1, 1)


def _absorbed_preview(absorbed: Optional[list]) -> tuple:
    """(preview, true_total) for an incident's absorbed symptom clusters.

    Absorbed clusters are the audit trail for a merge decision -- "this breached too,
    and here is why it is the same cause rather than a second incident". They are
    unbounded by nature: one real incident on this dataset absorbed 2,520 of them at
    ~380 characters each, which put 900 KB into every /api/incidents/{id} response,
    into every LLM prompt about that incident, and into 2,520 <li> elements on the
    page (the same class of failure as gotcha 31's 5,153px member table).

    Capped by |impact_usd| descending, the same significance order get_incident already
    uses for members, and ALWAYS with the true total returned alongside so a preview
    can never be read as the complete set.
    """
    items = list(absorbed or [])
    total = len(items)
    if total <= settings.absorbed_preview_limit:
        return items, total
    items.sort(key=lambda a: abs(float((a or {}).get("impact_usd") or 0.0)), reverse=True)
    return items[:settings.absorbed_preview_limit], total


def save_sweep(result, incidents: Optional[list] = None) -> None:
    """Writes one sweep's events, coverage rows and summary. Never raises."""
    save_events(result.verdicts, result.run_id)
    save_coverage(result)
    save_run(result, incidents_opened=len(incidents or []))


def save_events(verdicts: list, sweep_run_id: str) -> int:
    """One row per confirmed breach. Returns how many were written."""
    if not verdicts:
        return 0
    rows = []
    for v in verdicts:
        detail = getattr(v, "impact_detail", {}) or {}
        rows.append([
            str(uuid.uuid4()), sweep_run_id, v.metric, v.scope_type, v.scope_value, v.grain,
            v.window_start, v.window_end, v.seasonal_cell, v.direction, v.severity,
            float(v.value), float(v.center), float(v.spread), float(v.deviation_score),
            v.method, int(v.sample_count), int(getattr(v, "consecutive_points", 1)),
            float(detail.get("expected_units", 0.0)), float(detail.get("actual_units", 0.0)),
            float(getattr(v, "impact_usd", 0.0)),
            1 if getattr(v, "gated_by_impact", False) else 0,
            getattr(v, "incident_id", None), getattr(v, "signature", ""),
            getattr(v, "status", "open"), "",
        ])
    try:
        get_client().insert("metric_events", rows, _EVENT_COLUMNS, step="monitor_store:save_events")
        return len(rows)
    except Exception as e:
        logger.warning("Failed to persist %d metric_event row(s): %s", len(rows), e)
        return 0


def save_coverage(result) -> int:
    if not result.coverage:
        return 0
    rows = []
    for c in result.coverage:
        rows.append([
            result.run_id, result.started_at, c.scope_type, c.metric, c.grain,
            c.window_start or _EPOCH, c.window_end or _EPOCH,
            int(c.entities_total), int(c.entities_evaluated), int(c.entities_breached),
            int(c.skipped_low_power), int(c.skipped_no_band), int(c.skipped_cadence),
            int(getattr(c, "skipped_incomplete_window", 0)),
            float(c.power_floor), float(c.min_denom_seen), float(c.max_denom_seen),
            c.finest_valid_grain, c.skip_reason,
        ])
    try:
        get_client().insert("sweep_coverage", rows, _COVERAGE_COLUMNS, step="monitor_store:save_coverage")
        return len(rows)
    except Exception as e:
        logger.warning("Failed to persist %d sweep_coverage row(s): %s", len(rows), e)
        return 0


def save_run(result, incidents_opened: int = 0) -> None:
    cov = result.coverage
    row = [
        result.run_id, result.started_at, result.as_of, float(result.duration_ms),
        sorted({c.grain for c in cov}), sorted({c.scope_type for c in cov}),
        sorted({c.metric for c in cov if c.metric != "*"}),
        int(sum(c.entities_total for c in cov)),
        int(sum(c.entities_evaluated for c in cov)),
        int(len(result.all_breaches)),
        int(len(result.verdicts)),
        int(incidents_opened),
        int(sum(c.skipped_low_power for c in cov)),
        int(sum(c.skipped_no_band for c in cov)),
        int(sum(c.skipped_cadence for c in cov)),
        int(sum(getattr(c, "skipped_incomplete_window", 0) for c in cov)),
        int(result.queries_issued),
        json.dumps(result.errors)[:4000] if result.errors else "",
    ]
    try:
        get_client().insert("sweep_runs", [row], _RUN_COLUMNS, step="monitor_store:save_run")
    except Exception as e:
        logger.warning("Failed to persist sweep_run %s: %s", result.run_id, e)


def save_incidents(incidents: list) -> int:
    if not incidents:
        return 0
    rows = []
    for i in incidents:
        analysis = {k: getattr(i, k, None) for k in _ANALYSIS_KEYS}
        # Capped at the write side too, so no new 900 KB analysis_json is ever
        # stored -- but the count is stored, so the cap costs the audit trail its
        # long tail and never its arithmetic.
        analysis["absorbed"], analysis["absorbed_total"] = _absorbed_preview(analysis.get("absorbed"))
        score = 0
        detail = getattr(i, "evidence_score_detail", None) or {}
        if isinstance(detail, dict):
            score = int(detail.get("score") or 0)
        rows.append([
            i.incident_id, i.opened_at, i.last_seen_at, i.closed_at,
            i.root_scope_type, i.root_scope_value, i.root_metric, i.grain, i.direction,
            i.signature, float(i.signature_confidence), i.mechanism, i.owner,
            float(i.impact_usd), float(getattr(i, "impact_usd_per_day", 0.0)),
            int(getattr(i, "windows_spanned", 1) or 1),
            int(i.member_event_count), list(i.breached_metrics),
            i.fingerprint, i.narration or "", 1 if i.narration_available else 0,
            i.investigation_id, i.langfuse_trace_url or "",
            json.dumps(i.evidence, default=str) if i.evidence else "", i.label or "",
            1 if getattr(i, "gated_by_impact", False) else 0,
            max(0, min(100, score)),
            json.dumps(analysis, default=str),
        ])
    try:
        get_client().insert("incidents", rows, _INCIDENT_COLUMNS, step="monitor_store:save_incidents")
        return len(rows)
    except Exception as e:
        logger.warning("Failed to persist %d incident row(s): %s", len(rows), e)
        return 0


def attach_events_to_incident(incident_id: str, verdicts: list, signature: str) -> None:
    """Re-writes the member events with their incident id and signature.

    Relies on metric_events being a ReplacingMergeTree keyed on
    (metric, scope_type, scope_value, grain, window_start): re-inserting the same
    key with a later detected_at replaces the row rather than adding a second one.
    That is why the key is what it is -- an UPDATE would be a mutation, which on a
    hot path is far more expensive and not atomic either.
    """
    for v in verdicts:
        v.incident_id = incident_id
        v.signature = signature
        v.status = "clustered"
    save_events(verdicts, getattr(verdicts[0], "sweep_run_id", str(uuid.uuid4())) if verdicts else str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
class _ScratchTrace:
    """Discard sink, same purpose as store._ScratchTrace: these reads are
    plumbing, not part of any investigation's evidence trace."""

    def record(self, entry) -> None:
        pass


def _q(sql: str, step: str) -> list:
    try:
        return get_client().query(sql, step=step, trace=_ScratchTrace())
    except Exception as e:
        logger.warning("%s failed: %s", step, e)
        return []


def list_events(limit: int = 200, grain: Optional[str] = None, scope_type: Optional[str] = None,
                min_impact: Optional[float] = None, only_alertable: bool = False) -> list:
    limit = min(max(1, limit), 2000)
    where = ["1"]
    if grain:
        where.append(f"grain = '{grain[:32].replace(chr(39), '')}'")
    if scope_type:
        where.append(f"scope_type = '{scope_type[:64].replace(chr(39), '')}'")
    if min_impact is not None:
        where.append(f"abs(impact_usd) >= {float(min_impact)}")
    if only_alertable:
        where.append("gated_by_impact = 0")
    rows = _q(
        "SELECT event_id, detected_at, metric, scope_type, scope_value, grain, window_start, "
        "window_end, seasonal_cell, direction, severity, value, center, spread, deviation_score, "
        "baseline_method, sample_count, consecutive_points, expected, actual, impact_usd, "
        "gated_by_impact, incident_id, signature, status, label "
        f"FROM metric_events FINAL WHERE {' AND '.join(where)} "
        # Signed, for the same reason as list_incidents: losses first, gains last.
        f"ORDER BY impact_usd DESC, detected_at DESC LIMIT {limit}",
        step="monitor_store:list_events",
    )
    for r in rows:
        r["event_id"] = str(r["event_id"])
        r["incident_id"] = str(r["incident_id"]) if r.get("incident_id") else None
    return rows


# Reduces each incident's ROOT-slice breaches to the peak of the movement.
#
# `incidents` stores no magnitude at all -- no deviation_score, no value/center/spread. Those
# live on metric_events, one row per breached window, which is why this is an aggregate rather
# than a plain join: 618 of 825 incidents have more than one root-slice window (up to four),
# and joining them raw multiplies the incident out into duplicate queue rows.
#
# argMax on abs(deviation_score) picks the window where the metric was furthest from its band --
# the peak of the spike, not its first or last moment. Grouping on the root key rather than on
# incident_id alone is what keeps it to the ROOT slice: an incident's members span many scopes,
# and the largest deviation among all of them may belong to a symptom rather than to the cause.
# Measured 1:1 across the whole table -- 825 rows in, 825 out, none unmatched.
_ROOT_MOVEMENT_CTE = """
WITH root AS (
    SELECT incident_id AS iid, metric, scope_type, scope_value, grain,
           argMax(deviation_score, abs(deviation_score)) AS root_deviation_score,
           argMax(value,           abs(deviation_score)) AS root_value,
           argMax(center,          abs(deviation_score)) AS root_center,
           argMax(spread,          abs(deviation_score)) AS root_spread,
           argMax(severity,        abs(deviation_score)) AS root_severity,
           argMax(window_start,    abs(deviation_score)) AS root_peak_window
    FROM metric_events FINAL
    WHERE incident_id IS NOT NULL
    GROUP BY iid, metric, scope_type, scope_value, grain
)
"""

_ROOT_MOVEMENT_JOIN = """
LEFT JOIN root r
       ON r.iid        = i.incident_id
      AND r.metric     = i.root_metric
      AND r.scope_type = i.root_scope_type
      AND r.scope_value= i.root_scope_value
      AND r.grain      = i.grain
"""


def list_incidents(limit: int = 100, open_only: bool = False, gated: bool | None = None) -> list:
    """The work queue, newest first, carrying how far each root metric actually moved.

    ORDERED BY TIME, NOT BY DOLLARS
    This used to be `ORDER BY impact_usd_per_day DESC`. The reasons recorded for that ordering
    were about *magnitude* comparisons -- raw window dollars are not comparable across grains,
    and ranking on abs() lets a gain outrank a loss -- and neither failure mode is reintroduced
    by ordering on time. What ordering on dollars did do was make the screen a cost report:
    the queue answered "what is this costing" when the question the system exists to answer is
    "what moved, and where". impact_usd_per_day is still computed, still gates, and is still
    carried on every row; it is no longer what decides what a reader sees first.

    The LEFT JOIN is deliberate: an incident whose metric_events were pruned still lists, with
    null movement fields, rather than vanishing from the queue.

    `gated` selects which side of the impact gate to return: None for both, False for alertable
    only, True for suppressed only. It exists BECAUSE the ordering is chronological -- 791 of
    825 incidents are below the gate, so a time-ordered page of 25 is mostly suppressed rows
    and the console showed "top 9 of 34". Under the old impact ordering the two happened to
    coincide, since gated incidents are by definition the cheap ones and sorted to the bottom.
    """
    limit = min(max(1, limit), 500)
    where = "closed_at IS NULL" if open_only else "1"
    if gated is True:
        where += " AND gated_by_impact != 0"
    elif gated is False:
        where += " AND gated_by_impact = 0"
    rows = _q(
        _ROOT_MOVEMENT_CTE +
        "SELECT i.incident_id, i.opened_at, i.last_seen_at, i.closed_at, i.root_scope_type, "
        "i.root_scope_value, i.root_metric, i.grain, i.direction, i.signature, "
        "i.signature_confidence, i.mechanism, i.owner, "
        "i.impact_usd, i.impact_usd_per_day, i.windows_spanned, i.member_event_count, "
        "i.breached_metrics, i.fingerprint, "
        "i.narration, i.narration_available, i.investigation_id, i.langfuse_trace_url, i.label, "
        "i.gated_by_impact, i.evidence_score, "
        "r.root_deviation_score, r.root_value, r.root_center, r.root_spread, "
        "r.root_severity, r.root_peak_window "
        f"FROM incidents i FINAL {_ROOT_MOVEMENT_JOIN} WHERE {where} "
        f"ORDER BY i.opened_at DESC, i.last_seen_at DESC LIMIT {limit}",
        step="monitor_store:list_incidents",
    )
    for r in rows:
        r["incident_id"] = str(r["incident_id"])
        r["investigation_id"] = str(r["investigation_id"]) if r.get("investigation_id") else None
        r["gated_by_impact"] = bool(r.get("gated_by_impact"))
        r["narration_available"] = bool(r.get("narration_available"))
        _clean_movement(r)
    return rows


# bands.py assigns CONSTANT_HISTORY_SCORE (100.0) when a perfectly flat trailing history makes
# the spread zero -- there is no band to be sigmas away from, so the number is a sentinel, not
# a measurement. It must never reach a screen that prints "100x band" as though it were one.
_SENTINEL_DEVIATION = 100.0


def _clean_movement(row: dict) -> None:
    """Nulls the movement fields when they carry a sentinel rather than a measurement."""
    dev = row.get("root_deviation_score")
    if dev is not None and abs(float(dev)) >= _SENTINEL_DEVIATION:
        row["root_deviation_score"] = None


def count_incidents(open_only: bool = False) -> dict:
    """Totals over the WHOLE table: counts, and the summed daily exposure.

    Every figure here is a COUNT/SUM over the table, never derived from a page of
    list_incidents(). Deriving from the page was wrong in a way that always looked reassuring:
    the list was ordered by impact_usd_per_day DESC and gated incidents are by definition the
    cheap ones, so with a limit of 25 and 25 alertable incidents the "suppressed" figure came
    out as 25 - 25 = 0 -- the console reported that nothing had been hidden while several
    hundred were. Now that the list is ordered by TIME, deriving any total from it would be
    worse still: the page is the 25 most recent, which is not a population at all.

    at_risk_usd_per_day is loss-direction only (> 0). Including above-band moves would net a
    click-fraud spike against a fill outage and understate the real exposure.
    """
    where = "closed_at IS NULL" if open_only else "1"
    rows = _q(
        "SELECT countIf(gated_by_impact = 0) AS alertable, countIf(gated_by_impact != 0) AS gated, "
        "sumIf(impact_usd_per_day, gated_by_impact = 0 AND impact_usd_per_day > 0) "
        "AS at_risk_usd_per_day "
        f"FROM incidents FINAL WHERE {where}",
        step="monitor_store:count_incidents",
    )
    row = rows[0] if rows else {}
    return {
        "alertable": int(row.get("alertable") or 0),
        "gated": int(row.get("gated") or 0),
        "at_risk_usd_per_day": float(row.get("at_risk_usd_per_day") or 0.0),
    }


def dataset_state_counts() -> dict:
    """How much monitoring state the CURRENT dataset actually has.

    Answers "has this dataset ever been swept?" for GET /api/datasets. `baselines`
    is the one that matters: with no bands there is nothing to compare against, so a
    sweep evaluates nothing and the console renders an empty page that is
    indistinguishable from a healthy one. Reporting the number lets the switcher say
    "not provisioned" instead of showing a blank and implying calm.

    One query rather than four round trips, and read WITHOUT FINAL deliberately: this
    is an order-of-magnitude "is there anything here", not a figure anything is
    computed from, and FINAL over 1.17M baseline rows would be real work to answer a
    question that only cares whether the count is zero.
    """
    rows = _q(
        "SELECT (SELECT count() FROM baselines) AS baselines, "
        "(SELECT count() FROM incidents) AS incidents, "
        "(SELECT count() FROM metric_events) AS metric_events, "
        "(SELECT count() FROM sweep_runs) AS sweep_runs",
        step="monitor_store:dataset_state_counts",
    )
    row = rows[0] if rows else {}
    return {
        "baselines": int(row.get("baselines") or 0),
        "incidents": int(row.get("incidents") or 0),
        "metric_events": int(row.get("metric_events") or 0),
        "sweep_runs": int(row.get("sweep_runs") or 0),
    }


def count_incidents_by_owner(open_only: bool = False) -> dict:
    """Alertable incidents per owning team, over the whole table.

    Same reason as count_incidents: tallying this from a page made the owner chips sum to the
    page size (25) while sitting beside a headline that said 34, and dropped whole owners --
    `pricing` had one incident and no chip at all.
    """
    where = "closed_at IS NULL" if open_only else "1"
    rows = _q(
        "SELECT if(owner = '', 'unassigned', owner) AS owner_label, count() AS n "
        f"FROM incidents FINAL WHERE gated_by_impact = 0 AND {where} "
        "GROUP BY owner_label ORDER BY n DESC",
        step="monitor_store:count_incidents_by_owner",
    )
    return {str(r["owner_label"]): int(r["n"]) for r in rows}


def peak_movement(as_of=None, open_only: bool = False) -> dict:
    """The single largest metric movement currently outside its band, over the whole table.

    This is the ops home's headline. It replaces a summed dollar figure with the thing the
    system actually detects -- one metric, one segment, how far it went -- so the screen leads
    with what happened rather than with what it costs.

    WHY `as_of` GATES THIS
    One incident in the table opens on 2026-07-11 against data that ends 2026-07-05: its whole
    evaluation window lies past the last event, so the window is empty, the observed value is
    0.0, and the deviation is the largest in the table by a wide margin. Ranked on dollars that
    surfaced as "$480/day" and looked like an ordinary big finding; ranked on movement it reads
    "revenue fell 100%", which is a fabricated-looking alarm about a window that simply has no
    data in it. The same class of defect the window-completeness invariant exists to prevent, so
    the headline refuses to be drawn from a window the data cannot support. The incident itself
    is not hidden -- it stays in the queue, where its empty window is visible in context.
    """
    where = "closed_at IS NULL" if open_only else "1"
    clock = ""
    if as_of is not None:
        clock = f"AND i.opened_at <= toDateTime('{as_of:%Y-%m-%d %H:%M:%S}') "
    rows = _q(
        _ROOT_MOVEMENT_CTE +
        "SELECT i.root_metric, i.root_scope_type, i.root_scope_value, i.grain, i.direction, "
        "r.root_deviation_score, r.root_value, r.root_center, r.root_severity, i.incident_id "
        f"FROM incidents i FINAL {_ROOT_MOVEMENT_JOIN} "
        f"WHERE i.gated_by_impact = 0 AND {where} {clock}AND r.root_deviation_score IS NOT NULL "
        f"AND abs(r.root_deviation_score) < {_SENTINEL_DEVIATION} "
        "ORDER BY abs(r.root_deviation_score) DESC LIMIT 1",
        step="monitor_store:peak_movement",
    )
    if not rows:
        return {}
    row = rows[0]
    row["incident_id"] = str(row["incident_id"])
    return row


def get_incident(incident_id: str) -> Optional[dict]:
    safe = str(incident_id).replace("'", "")
    rows = _q(
        f"SELECT * FROM incidents FINAL WHERE incident_id = '{safe}' LIMIT 1",
        step="monitor_store:get_incident",
    )
    if not rows:
        return None
    row = rows[0]
    row["incident_id"] = str(row["incident_id"])
    row["investigation_id"] = str(row["investigation_id"]) if row.get("investigation_id") else None
    row["gated_by_impact"] = bool(row.get("gated_by_impact"))
    row["narration_available"] = bool(row.get("narration_available"))
    if row.get("evidence_json"):
        try:
            row["evidence"] = json.loads(row["evidence_json"])
        except Exception:
            row["evidence"] = None
    # The incident's own diagnosis, lifted to top-level keys so a client does not
    # have to know it was stored as a blob. Present regardless of whether an LLM
    # investigation ran.
    analysis = {}
    if row.get("analysis_json"):
        try:
            analysis = json.loads(row["analysis_json"]) or {}
        except Exception:
            analysis = {}
    for key in _ANALYSIS_KEYS:
        row[key] = analysis.get(key)
    # Capped on READ as well as on write, because the rows already in ClickHouse were
    # written before the write-side cap existed -- one of them carries 2,520 entries.
    # A stored absorbed_total wins over the length of the list, since on those older
    # rows the list IS the total and on newer ones it is only the preview.
    preview, counted = _absorbed_preview(row.get("absorbed"))
    row["absorbed"] = preview
    row["absorbed_total"] = int(analysis.get("absorbed_total") or counted)
    # Drop the raw blobs: the parsed forms above are what a client should read, and
    # shipping both doubles a payload that already contains a full SQL trace.
    row.pop("analysis_json", None)
    row.pop("evidence_json", None)
    members = _q(
        "SELECT metric, scope_type, scope_value, grain, direction, severity, value, center, spread, "
        "deviation_score, impact_usd, window_start, window_end, seasonal_cell, baseline_method, sample_count "
        f"FROM metric_events FINAL WHERE incident_id = '{safe}' ORDER BY abs(impact_usd) DESC LIMIT 500",
        step="monitor_store:get_incident_members",
    )
    row["members"] = members
    return row


def set_label(incident_id: str, label: str) -> bool:
    """Records a post-mortem verdict on an incident and its member events.

    This is the feedback loop the design calls for: with labels accumulated,
    per-slice precision becomes measurable and band thresholds can be tuned from
    evidence instead of taste. It is a mutation rather than a re-insert because it
    is rare, human-driven, and must apply to rows written long ago.
    """
    safe_id = str(incident_id).replace("'", "")
    safe_label = "".join(ch for ch in str(label) if ch.isalnum() or ch in "_-")[:64]
    if not safe_label:
        return False
    try:
        client = get_client()
        trace = _ScratchTrace()
        client.command(
            f"ALTER TABLE incidents UPDATE label = '{safe_label}' WHERE incident_id = '{safe_id}' "
            "SETTINGS mutations_sync = 1",
            step="monitor_store:label_incident", trace=trace,
        )
        client.command(
            f"ALTER TABLE metric_events UPDATE label = '{safe_label}' WHERE incident_id = '{safe_id}' "
            "SETTINGS mutations_sync = 1",
            step="monitor_store:label_events", trace=trace,
        )
        return True
    except Exception as e:
        logger.warning("Failed to label incident %s: %s", incident_id, e)
        return False


def latest_sweep() -> Optional[dict]:
    rows = _q(
        "SELECT * FROM sweep_runs ORDER BY started_at DESC LIMIT 1",
        step="monitor_store:latest_sweep",
    )
    if not rows:
        return None
    r = rows[0]
    r["run_id"] = str(r["run_id"])
    return r


def coverage_matrix(run_id: Optional[str] = None) -> list:
    """The coverage grid for a sweep -- what was evaluated and what was not, per
    (scope, metric, grain). This is the queryable form of the coverage claim."""
    if run_id:
        safe = str(run_id).replace("'", "")
        where = f"run_id = '{safe}'"
    else:
        where = "run_id = (SELECT run_id FROM sweep_runs ORDER BY started_at DESC LIMIT 1)"
    return _q(
        "SELECT scope_type, metric, grain, window_start, window_end, entities_total, "
        "entities_evaluated, entities_breached, skipped_low_power, skipped_no_band, "
        "skipped_cadence, power_floor, min_denom_seen, max_denom_seen, finest_valid_grain, skip_reason "
        f"FROM sweep_coverage WHERE {where} ORDER BY scope_type, grain, metric",
        step="monitor_store:coverage_matrix",
    )
