"""Context Agent (ENGINEERING.md §5.3) — Agent 3.

Maintains the living context layer in `meta.*`: seeds v0 from base_context.md,
versioned snapshots with content_hash + diff, per-object changelog, and runs
reconciliation after every schema change (context.checked → context.updated).
Every row carries the trace_id (§5.4).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from pathlib import Path

from .. import events as ev
from ..bus import EventBus
from ..events import Event
from ..reconcile import Finding, actual_from_store, reconcile

log = logging.getLogger("atlys.agents.context")


class ContextAgent:
    def __init__(self, store, bus: EventBus, settings, tracer=None):
        self.store = store
        self.bus = bus
        self.settings = settings
        self.tracer = tracer

    # -- seeding ------------------------------------------------------------
    def seed_if_empty(self, context_md: str | None = None) -> None:
        """Idempotent v0 seed: snapshot base_context.md + parse known issues.

        Also runs a v0 reconciliation against the live schema so the baseline
        context carries findings from day one (context.checked semantics).
        Traced as `context:seed` (plan §4.4).
        """
        rows = self.store.query_rows("SELECT count() AS c FROM meta.context_snapshots")
        if rows and rows[0]["c"] > 0:
            return
        with self._span("context:seed"):
            md = context_md or self._read_base_context()
            self._save_snapshot(0, md, diff_from_prev="", trace_id="seed")
            for issue in parse_known_issues(md):
                self._upsert_known_issue(issue)
            findings = reconcile(actual_from_store(self.store), md)
            for finding in findings:
                self.log_changelog(
                    0, ev.ACTOR_CONTEXT, "reconciliation_finding",
                    finding.object, finding.diff, finding.rationale, "seed",
                )

    # -- versioning ---------------------------------------------------------
    def next_version(self) -> int:
        rows = self.store.query_rows("SELECT max(version) AS v FROM meta.context_changelog")
        cur = rows[0]["v"] if rows and rows[0]["v"] is not None else 0
        rows2 = self.store.query_rows("SELECT max(version) AS v FROM meta.context_snapshots")
        cur = max(cur, rows2[0]["v"] if rows2 and rows2[0]["v"] is not None else 0)
        return int(cur) + 1

    def latest_snapshot(self) -> dict | None:
        rows = self.store.query_rows(
            "SELECT version, content, content_hash, diff_from_prev, trace_id, created_at "
            "FROM meta.context_snapshots ORDER BY version DESC LIMIT 1"
        )
        return rows[0] if rows else None

    # -- reconciliation handler --------------------------------------------
    def on_schema_created(self, event: Event) -> None:
        """schema.created → reconcile → context.updated (snapshot + changelog)."""
        trace_id = event.trace_id
        spec_dir = event.payload["spec_dir"]
        feature = event.payload["feature"]

        with self._span("context", spec_dir=spec_dir, feature=feature):
            findings = self._run_reconcile(trace_id)
            self.bus.emit(ev.new_event(
                ev.CONTEXT_CHECKED, spec_dir, ev.ACTOR_CONTEXT,
                payload={
                    "spec_dir": spec_dir,
                    "feature": feature,
                    "findings": [f.__dict__ for f in findings],
                },
                trace_id=trace_id,
            ))

            # Build the new context snapshot: v0 content + live schema catalog.
            base = self._read_base_context()
            catalog_md = self._catalog_markdown()
            new_content = f"{base}\n\n---\n## 8. Live schema catalog (auto-maintained)\n\n{catalog_md}"
            prev = self.latest_snapshot()
            prev_content = (prev.get("content") if prev else None) or ""
            diff = "".join(difflib.unified_diff(
                prev_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="context-v{prev_v}".format(prev_v=prev["version"] if prev else 0),
                tofile=f"context-v{self.next_version()}",
            ))
            version = self.next_version()
            self._save_snapshot(version, new_content, diff, trace_id)
            for finding in findings:
                self.log_changelog(
                    version, ev.ACTOR_CONTEXT, "reconciliation_finding",
                    finding.object, finding.diff, finding.rationale, trace_id,
                )

            self.bus.emit(ev.new_event(
                ev.CONTEXT_UPDATED, spec_dir, ev.ACTOR_CONTEXT,
                payload={
                    "spec_dir": spec_dir,
                    "feature": feature,
                    "version": version,
                    "findings": [f.__dict__ for f in findings],
                    "diff": diff,
                },
                trace_id=trace_id,
            ))

    def _run_reconcile(self, trace_id: str) -> list[Finding]:
        actual = actual_from_store(self.store)
        context_md = self._read_base_context()
        findings = reconcile(actual, context_md)
        log.info("reconcile found %d findings (trace %s)", len(findings), trace_id)
        return findings

    # -- changelog / catalog / insights helpers ----------------------------
    def log_changelog(self, version: int, agent: str, action: str, object_: str,
                      diff: str, rationale: str, trace_id: str) -> None:
        self.store.insert(
            "meta.context_changelog",
            ["version", "agent", "action", "object", "diff", "rationale", "trace_id"],
            [[version, agent, action, object_, diff, rationale, trace_id]],
        )

    def add_schema_card(self, card: dict, trace_id: str) -> None:
        """Persist a schema card into the catalog (called by instrumentation)."""
        self.store.insert(
            "meta.schema_catalog",
            ["table_name", "ddl", "rationale", "source_spec", "event_order", "columns",
             "row_count", "trace_id"],
            [[card["table"], card["ddl"], json.dumps(card["rationale"]), card["source_spec"],
              json.dumps(card["event_order"]), json.dumps(card["columns"]), card["row_count"], trace_id]],
        )

    def add_insight(self, insight: dict, trace_id: str) -> None:
        """Upsert an insight card (keyed on spec+title)."""
        self.store.insert(
            "meta.insights",
            ["spec", "title", "summary", "confidence", "evidence", "trace_id"],
            [[insight["spec"], insight["title"], insight["summary"], insight["confidence"],
              # evidence rows can carry datetime objects — serialize as ISO strings
              json.dumps(insight["evidence"], default=str), trace_id]],
        )

    def propose_context_update(self, change: dict, trace_id: str) -> int:
        """context.update.proposed → changelog pending entry (human-in-the-loop)."""
        version = self.next_version()
        self.log_changelog(
            version, ev.ACTOR_USER, "update", change.get("object", "context"),
            json.dumps(change), change.get("rationale", "human-proposed edit"), trace_id,
        )
        return version

    # -- internal helpers ---------------------------------------------------
    def _read_base_context(self) -> str:
        p: Path = self.settings.base_context_path
        if not p.exists():
            log.warning("base_context.md missing at %s", p)
            return "# Atlys Analytics — Base Context Layer (missing)\n"
        return p.read_text()

    def _save_snapshot(self, version: int, content: str, diff_from_prev: str, trace_id: str) -> None:
        self.store.insert(
            "meta.context_snapshots",
            ["version", "content", "content_hash", "diff_from_prev", "trace_id"],
            [[version, content, hashlib.sha256(content.encode()).hexdigest(), diff_from_prev, trace_id]],
        )

    def _upsert_known_issue(self, issue: dict) -> None:
        self.store.insert(
            "meta.known_issues",
            ["issue_id", "title", "evidence", "status"],
            [[issue["issue_id"], issue["title"], issue.get("evidence", ""), "open"]],
        )

    def _catalog_markdown(self) -> str:
        lines = []
        for table in sorted(self.store.all_tables()):
            if table.startswith("meta.") or table in {"event_log", "mv_funnel_daily"}:
                continue
            cols = self.store.columns(table)
            lines.append(f"### `{table}`")
            lines.append("| column | type |")
            lines.append("|---|---|")
            for c in cols:
                lines.append(f"| `{c['name']}` | {c['type']} |")
        return "\n".join(lines) or "_no user tables yet_"

    def _span(self, name: str, **meta):
        if self.tracer is None:
            import contextlib
            return contextlib.nullcontext()
        return self.tracer.span(name, **meta)


# ---------------------------------------------------------------------------
# Known-issue parsing (base_context.md §5 → meta.known_issues)
# ---------------------------------------------------------------------------

KNOWN_ISSUE_EVIDENCE_HINTS = {
    "K1": "otp_entered; iOS otp_success below Android; geo in Gulf (AE SA KW QA BH OM)",
    "K2": "document_uploaded; android capture/retry/threshold up",
    "K3": "high retry_count by destination/citizenship",
    "K4": "Schengen destinations + seasonal timing (Apr-Jun)",
    "K5": "abandoned-checkout reminders via whatsapp reconverting",
    "K6": "coupon_applied / coupon_name = SUMMER20 in purchase evidence",
    "K7": "app_version 7.45.x funnel-timing shifts",
}


def parse_known_issues(context_md: str) -> list[dict]:
    """Parse the numbered known-issues log into {issue_id, title, evidence}."""
    issues: list[dict] = []
    pattern = re.compile(r"(\d+)\.\s+\*\*(K\d+)\s*[—–-]\s*([^*]+)\*\*")
    for m in pattern.finditer(context_md):
        issue_id = m.group(2)
        title = re.sub(r"\s+", " ", m.group(3)).strip().rstrip(".")
        issues.append({
            "issue_id": issue_id,
            "title": title,
            "evidence": KNOWN_ISSUE_EVIDENCE_HINTS.get(issue_id, ""),
        })
    return issues


def _clean_title(raw: str) -> str:
    """Title helper: strip markdown noise (used by tests)."""
    return re.sub(r"\s+", " ", raw.replace("**", "").replace("—", "-")).strip(" .")
