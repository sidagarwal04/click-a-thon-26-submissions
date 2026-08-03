"""Analytics Agent (ENGINEERING.md §5.2) — Agent 2.

ClickHouse computes; the insight summary is a deterministic template (D6). The
playbook (P1–P6) is built from the **spec's** event order and columns — never
hardcoded. Every query result becomes evidence `{label, kind, sql, rows|error}`;
a failing query is recorded, never crashes the run (§5.2.2). The evidence list
is the anti-hallucination guarantee and the trace content.
"""
from __future__ import annotations

import logging
from typing import Any

from .. import events as ev
from ..bus import EventBus
from ..ch_errors import evidence_error
from ..events import Event
from ..schema import _slug
from ..sqlsafe import sanitize_identifier, sql_string_literal

log = logging.getLogger("atlys.agents.analytics")

SEGMENT_KEYS = ["os", "device_type", "geoip_country_code", "destination"]
# Per-user timing dumps must stay bounded (MCP → chat context).
# P0.5 — cap unbounded per-user dumps so huge tables cannot hang the demo.
P6_USER_LIMIT = 50


class AnalyticsAgent:
    def __init__(self, store, bus: EventBus, settings, tracer=None):
        self.store = store
        self.bus = bus
        self.settings = settings
        self.tracer = tracer

    # -- handler ------------------------------------------------------------
    def on_context_updated(self, event: Event) -> None:
        """context.updated → run playbook → insight.created."""
        spec_dir = event.payload["spec_dir"]
        feature = event.payload["feature"]
        trace_id = event.trace_id
        table = f"{_slug(feature)}_events"

        with self._span("analytics", feature=feature, table=table,
                        ch_version=getattr(self.store, "server_version", None)):
            card = self._latest_schema_card(table)
            if card is None:
                log.warning("no schema card for %s — skipping analytics", table)
                return
            event_order = card["event_order"]
            has_user_id = card.get("has_user_id", True)
            user_col = "user_id" if has_user_id else "''"
            columns = card.get("columns", {})

            evidence = self.run_playbook(feature, table, event_order, has_user_id, user_col, columns)
            summary = synthesize(feature, table, event_order, evidence, has_user_id)
            confidence = confidence_from_evidence(evidence)
            matched = self._correlate(evidence, table, feature)

            insight = {
                "spec": spec_dir,
                "feature": feature,
                "title": f"{feature.replace('_', ' ').title()} feature health",
                "summary": summary,
                "confidence": confidence,
                "evidence": evidence,
                "event_order": event_order,
                "matched_known_issues": [m["issue_id"] for m in matched],
                "trace_id": trace_id,
                "context_version": self._latest_context_version(),
            }
            self._upsert_insight(insight)
            self._write_insight_md(feature, insight)

            self.bus.emit(ev.new_event(
                ev.INSIGHT_CREATED, spec_dir, ev.ACTOR_ANALYTICS,
                payload={"spec_dir": spec_dir, "feature": feature, "insight": insight},
                trace_id=trace_id,
            ))

    # -- playbook -----------------------------------------------------------
    def playbook(self, feature: str, table: str, event_order: list[str],
                 has_user_id: bool = True, user_col: str = "user_id",
                 columns: dict | None = None) -> list[dict]:
        """Build P1–P6 queries from the spec's event order (never hardcoded)."""
        if not event_order:
            return []
        table = sanitize_identifier(table)
        first, last = event_order[0], event_order[-1]
        first_lit, last_lit = sql_string_literal(first), sql_string_literal(last)
        if has_user_id:
            u = sanitize_identifier(user_col)
        else:
            u = "'unused'"

        def uniq_if(event_name: str) -> str:
            return f"uniqIf({u}, event = {sql_string_literal(event_name)})"

        p1 = {
            "label": "funnel step-through",
            "kind": "funnel",
            "sql": "SELECT " + ", ".join(
                f"{uniq_if(e)} AS u{i}" for i, e in enumerate(event_order)
            ) + f" FROM {table};",
        }
        p2 = {
            "label": "event overview",
            "kind": "overview",
            "sql": f"SELECT event, count() AS events, uniqExact({u}) AS users FROM {table} GROUP BY event;",
        }
        p3s = []
        for key in SEGMENT_KEYS:
            seg_col = sanitize_identifier(key)
            p3s.append({
                "label": f"segment skew by {key}",
                "kind": "segment",
                "sql": f"SELECT {seg_col} AS seg, {uniq_if(first)} AS a, {uniq_if(last)} AS b "
                       f"FROM {table} GROUP BY seg ORDER BY a DESC LIMIT 10;",
            })
        # P4: timing/amounts — numeric feature columns get p50/p90; otherwise
        # fall back to completion-time quantiles.
        numeric_cols = [c for c, t in (columns or {}).items()
                        if any(k in t for k in ("Float", "UInt", "Int"))
                        and "DateTime" not in t]
        safe_numeric = []
        for c in numeric_cols[:4]:
            try:
                safe_numeric.append(sanitize_identifier(c))
            except ValueError:
                log.warning("skipping unsafe numeric column name in playbook: %r", c)
        if safe_numeric:
            p4_sql = "SELECT " + ", ".join(
                f"quantile(0.5)({c}) AS p50_{c}, quantile(0.9)({c}) AS p90_{c}"
                for c in safe_numeric
            ) + f", count() AS n FROM {table} WHERE event = {last_lit};"
            p4_label = "timings/amounts (p50, p90)"
        else:
            p4_sql = f"SELECT quantile(0.5)(timestamp) AS p50_ts, quantile(0.9)(timestamp) AS p90_ts, " \
                      f"count() AS n FROM {table} WHERE event = {last_lit};"
            p4_label = "completion timing (p50, p90)"
        p4 = {"label": p4_label, "kind": "timing", "sql": p4_sql}

        # P5: cross-funnel conversion — buckets no-user_id specs under '' (doc §5.1)
        p5_u = "user_id" if has_user_id else "''"
        p5 = {
            "label": "cross-funnel conversion to purchase",
            "kind": "cross_funnel",
            "sql": f"SELECT uniqExact(p.user_id) AS converted, "
                   f"(SELECT uniqExact({p5_u}) FROM {table} WHERE event = {last_lit}) AS users "
                   f"FROM purchase_completed p WHERE p.user_id IN "
                   f"(SELECT {p5_u} FROM {table} WHERE event = {last_lit});",
        }
        # P6 capped (P0.5) — never dump unbounded per-user rows on huge tables.
        p6 = {
            "label": "funnel timing first→last",
            # distinct kind on purpose: synthesize's completion-sample lookup
            # (kind == "timing") must never pick this user-level query, whose
            # columns are user_id/t0/t1, not a count.
            "kind": "funnel_timing",
            "sql": f"SELECT user_id, minIf(timestamp, event = {first_lit}) AS t0, "
                   f"maxIf(timestamp, event = {last_lit}) AS t1 FROM {table} "
                   f"GROUP BY user_id LIMIT {P6_USER_LIMIT};",
        }

        queries = [p1, p2, *p3s, p4, p5, p6]

        # Prefer the flagship funnel MV when present — cheap segment rollup over
        # ~2.5M raw funnel rows (P0.5). Failure is recorded like any other step.
        if self._mv_funnel_daily_available():
            queries.append({
                "label": "funnel MV daily segments (mv_funnel_daily)",
                "kind": "mv_funnel",
                "sql": (
                    "SELECT day, os, geoip_country_code, destination, "
                    "uniqMerge(users_at_step) AS users, countMerge(events) AS events "
                    "FROM mv_funnel_daily GROUP BY day, os, geoip_country_code, destination "
                    "ORDER BY day DESC LIMIT 30;"
                ),
            })
        return queries

    def _mv_funnel_daily_available(self) -> bool:
        try:
            return bool(self.store.table_exists("mv_funnel_daily"))
        except Exception:  # noqa: BLE001
            return False

    def run_playbook(self, feature: str, table: str, event_order: list[str],
                     has_user_id: bool = True, user_col: str = "user_id",
                     columns: dict | None = None) -> list[dict]:
        """Execute each playbook query → evidence rows; errors recorded, never fatal.

        Each span carries output metadata (row_count / elapsed_ms / error) so the
        Langfuse trace shows the numbers behind the insight (plan §4.3).
        """
        import time

        evidence: list[dict] = []
        for q in self.playbook(feature, table, event_order, has_user_id, user_col, columns):
            t0 = time.monotonic()
            span_out = {"row_count": 0, "elapsed_ms": 0}
            with self._span("playbook:" + q["kind"], label=q["label"], output=span_out):
                try:
                    rows = self.store.query(q["sql"])
                    span_out["row_count"] = len(rows)
                    evidence.append({
                        "label": q["label"],
                        "kind": q["kind"],
                        "sql": q["sql"],
                        "rows": rows,
                        "row_count": len(rows),
                    })
                except Exception as e:  # noqa: BLE001 — record, never crash (§5.2.2)
                    err = evidence_error(e, q["sql"])
                    span_out["error"] = err.get("error")
                    span_out["error_class"] = err.get("error_class")
                    log.warning("playbook query failed (%s): %s [%s]",
                                q["label"], err.get("error"), err.get("error_class"))
                    evidence.append({
                        "label": q["label"],
                        "kind": q["kind"],
                        "sql": q["sql"],
                        "row_count": 0,
                        **err,
                    })
                # set BEFORE the span exits so the tracer captures the real value
                # (output is read at __exit__)
                span_out["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        return evidence

    # -- meta persistence ---------------------------------------------------
    def _latest_schema_card(self, table: str) -> dict | None:
        rows = self.store.query_rows(
            "SELECT table_name, ddl, rationale, source_spec, event_order, columns, "
            "row_count, trace_id FROM meta.schema_catalog WHERE table_name = {t:String} "
            "ORDER BY created_at DESC LIMIT 1",
            {"t": table},
        )
        if not rows:
            return None
        r = rows[0]
        import json
        return {
            "table": r["table_name"],
            "ddl": r["ddl"],
            "rationale": json.loads(r["rationale"]) if r["rationale"] else {},
            "source_spec": r["source_spec"],
            "event_order": json.loads(r["event_order"]) if r["event_order"] else [],
            "columns": json.loads(r["columns"]) if r["columns"] else {},
            "row_count": r["row_count"],
            "trace_id": r["trace_id"],
        }

    def _latest_context_version(self) -> int | None:
        rows = self.store.query_rows("SELECT max(version) AS v FROM meta.context_snapshots")
        return rows[0]["v"] if rows and rows[0]["v"] is not None else None

    def _upsert_insight(self, insight: dict) -> None:
        self.store.insert(
            "meta.insights",
            ["spec", "title", "summary", "confidence", "evidence", "trace_id"],
            [[insight["spec"], insight["title"], insight["summary"], insight["confidence"],
              # evidence rows can carry datetime objects (quantile-over-timestamp,
              # funnel_timing t0/t1) — serialize them as ISO strings
              __import__("json").dumps(insight["evidence"], default=str), insight["trace_id"]]],
        )

    def _write_insight_md(self, feature: str, insight: dict) -> None:
        out = self.settings.generated_dir / feature
        out.mkdir(parents=True, exist_ok=True)
        md = [
            f"# {insight['title']}",
            "",
            f"**Confidence:** {insight['confidence']}",
            f"**Trace:** `{insight['trace_id']}`",
            "",
            "## Summary",
            "",
            insight["summary"],
            "",
            "## Evidence",
            "",
        ]
        for e in insight["evidence"]:
            md.append(f"### {e['label']} (`{e['kind']}`)")
            md.append("")
            md.append("```sql")
            md.append(e["sql"])
            md.append("```")
            if "error" in e:
                cls = e.get("error_class", "unknown")
                md.append(f"\n_error [{cls}]: {e['error']}_\n")
            elif e.get("rows"):
                md.append("```")
                md.append(__import__("json").dumps(e["rows"], default=str))
                md.append("```")
            md.append("")
        if insight.get("matched_known_issues"):
            md.append("## Known-issue matches\n")
            md.append(", ".join(insight["matched_known_issues"]))
            md.append("")
        (out / "insight.md").write_text("\n".join(md))

    # -- correlation (delegates to the rule engine) -------------------------
    def _correlate(self, evidence: list[dict], table: str, feature: str) -> list[dict]:
        from .correlation import correlate
        return correlate(evidence, table, feature, known_issues=self._known_issues())

    def _known_issues(self) -> list[dict]:
        rows = self.store.query_rows(
            "SELECT issue_id, title, evidence, status FROM meta.known_issues"
        )
        return rows or []

    def _span(self, name: str, **meta):
        if self.tracer is None:
            import contextlib
            return contextlib.nullcontext()
        return self.tracer.span(name, **meta)


# ---------------------------------------------------------------------------
# Deterministic insight summary (§5.2.5) + confidence (§5.2.3)
# ---------------------------------------------------------------------------

def confidence_from_evidence(evidence: list[dict]) -> str:
    """Last-step sample size: ≥1000 high, ≥200 medium, else low (§5.2.3)."""
    for e in evidence:
        if e.get("kind") == "funnel" and e.get("rows"):
            last = e["rows"][0][-1]
            if last is not None and last >= 1000:
                return "high"
            if last is not None and last >= 200:
                return "medium"
            return "low"
    return "low"


def synthesize(feature: str, table: str, event_order: list[str],
               evidence: list[dict], has_user_id: bool = True) -> str:
    """Deterministic template summary built from evidence numbers alone (no LLM)."""
    parts: list[str] = []

    # P1 funnel step-through
    funnel = next((e for e in evidence if e["kind"] == "funnel"), None)
    if funnel and funnel.get("rows"):
        row = funnel["rows"][0]
        pairs = list(zip(event_order, row))
        chain = " → ".join(f"{name} {int(v):,}" for name, v in pairs if v is not None)
        if len(row) >= 2 and row[-1] is not None and row[0]:
            pct = 100.0 * row[-1] / row[0]
            parts.append(f"{_title(feature)}: {chain}. Overall completion from first to last step is "
                         f"{pct:.1f}%.")

    # P2 overview: biggest event
    overview = next((e for e in evidence if e["kind"] == "overview"), None)
    if overview and overview.get("rows"):
        total = sum(r[1] for r in overview["rows"]) or 0
        parts.append(f"The feature produced {total:,} events across {len(overview['rows'])} event types "
                     f"({', '.join(r[0] for r in overview['rows'])}).")

    # P4 timings (from completion row) — `n` is the LAST column (count());
    # the earlier columns are quantiles and can legitimately be NULL.
    timing = next((e for e in evidence if e["kind"] == "timing"), None)
    if timing and timing.get("rows"):
        r = timing["rows"][0]
        n = r[-1]
        if n is not None:
            parts.append(f"Completion sample: {int(n):,} events.")

    # P5 cross-funnel conversion
    cross = next((e for e in evidence if e["kind"] == "cross_funnel"), None)
    if cross and cross.get("rows"):
        r = cross["rows"][0]
        converted, users = r[0], r[1]
        if users:
            rate = 100.0 * converted / users
            parts.append(f"Cross-funnel: {int(converted):,} of {int(users):,} feature completers also "
                         f"converted on purchase_completed ({rate:.1f}%).")

    if not parts:
        parts.append(f"No computable evidence for {_title(feature)} (queries may have failed — see evidence).")

    return " ".join(parts)


def _title(feature: str) -> str:
    return feature.replace("_", " ").title()
