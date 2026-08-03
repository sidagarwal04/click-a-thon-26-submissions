"""Use-case toolkit: read catalog + publish context version."""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Sequence

from agno.tools import Toolkit

import context_agent.catalog as _catalog
from context_agent.catalog import get_feature_meta, get_latest_context_items
from context_agent.publish import publish_context_version


def _row_to_dict_compatible(row: Any) -> dict[str, Any]:
    """RowMapping (.mappings()) has no usable ._mapping attr — use dict(row)."""
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# catalog._row_to_dict breaks on SQLAlchemy RowMapping; patch without editing catalog.py
_catalog._row_to_dict = _row_to_dict_compatible


def _next_context_version(current: str | None) -> str:
    """Bump ``vN`` → ``vN+1``; seed ``v1`` when nothing is current."""
    if not current:
        return "v1"
    match = re.fullmatch(r"v(\d+)", current.strip(), flags=re.IGNORECASE)
    if match:
        return f"v{int(match.group(1)) + 1}"
    return f"{current.strip()}+1"


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[no-any-return]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _upserts_from_workflow(payload: dict[str, Any]) -> tuple[str | None, str, list[dict[str, Any]]]:
    """Derive feature_id, summary, and upserts from Instrumentation workflow output.

    Feature journeys are NOT written as ``funnel_step`` rows (see TABLES.md).
    """
    register = _as_dict(payload.get("register_meta"))
    metadata = _as_dict(register.get("metadata") or payload.get("metadata"))
    plan = _as_dict(payload.get("pipeline_plan") or payload.get("apply_clickhouse"))

    feature_id = (
        (metadata.get("feature_id") or plan.get("feature_id") or payload.get("feature_id") or "")
        .strip()
        or None
    )
    feature_summary = (metadata.get("feature_summary") or "").strip()
    rationale = (plan.get("rationale") or "").strip()
    action = (plan.get("action") or "").strip()

    journey = metadata.get("journey") or []
    event_refs: list[dict[str, Any]] = []
    if isinstance(journey, list):
        for ev in journey:
            if not isinstance(ev, dict):
                continue
            event_refs.append(
                {
                    "event_name": ev.get("event_name"),
                    "journey_order": ev.get("journey_order"),
                    "ch_table": ev.get("ch_table"),
                }
            )

    summary_parts = []
    if feature_id:
        summary_parts.append(f"Instrumentation reconcile for {feature_id}")
    if action:
        summary_parts.append(f"pipeline={action}")
    if rationale:
        summary_parts.append(rationale)
    if feature_summary and not rationale:
        summary_parts.append(feature_summary)
    summary = "; ".join(summary_parts) if summary_parts else "Instrumentation context publish"

    # Entity delta only — do not materialize feature journey as funnel_step.
    upserts: list[dict[str, Any]] = []
    if feature_id:
        upserts.append(
            {
                "kind": "entity",
                "item_key": f"feature:{feature_id}",
                "label": feature_id,
                "payload": {
                    "feature_id": feature_id,
                    "feature_summary": feature_summary or None,
                    "events": event_refs,
                    "pipeline_action": action or None,
                    "events_to_materialize": plan.get("events_to_materialize") or [],
                    "pipeline_changes": plan.get("pipeline_changes") or [],
                    "events_created": register.get("events_created") or [],
                    "events_linked": register.get("events_linked") or [],
                },
            }
        )

    return feature_id, summary, upserts


class ContextCatalogTools(Toolkit):
    """Deterministic tools for Conversation / operators (not free-form SQL)."""

    def __init__(self):
        tools = [
            self.get_latest_context_items,
            self.get_feature_meta,
            self.publish_context_version,
        ]
        super().__init__(name="context_catalog", tools=tools)

    def get_latest_context_items(self, kinds: Optional[str] = None) -> str:
        """Load the current living context (version + items).

        Call this first for any analytics question. Returns context_version and
        context_items (entities, metrics, joins, core funnel_steps, issues,
        contradictions).

        Args:
            kinds: Optional comma-separated kinds to filter, e.g.
                   \"metric,issue,funnel_step\". Omit for all kinds.
        """
        kind_list: Sequence[str] | None = None
        if kinds and kinds.strip():
            kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
        result = get_latest_context_items(kinds=list(kind_list) if kind_list else None)
        return json.dumps(result, default=str)

    def get_feature_meta(self, feature_id: str) -> str:
        """Load Instrumentation meta for one feature (meta_features + meta_events).

        Events are ordered by journey_order from meta_features.journey.
        ch_table is the per-event ClickHouse table; SAS sink is activity_events
        with envelope + payload (JSON). Event-specific fields are in
        events.columns / JSONExtract on payload.

        Args:
            feature_id: e.g. \"01_express_checkout\"
        """
        result = get_feature_meta(feature_id=feature_id)
        return json.dumps(result, default=str)

    def publish_context_version(
        self,
        context_version: str = "",
        source: str = "",
        summary: Optional[str] = None,
        feature_id: Optional[str] = None,
        parent_version: Optional[str] = None,
        upserts_json: Optional[str] = None,
        deletes_json: Optional[str] = None,
        copy_forward: bool = True,
        workflow_json: Optional[str] = None,
    ) -> str:
        """Publish a new context version (copy-forward parent items + deltas).

        Use for seed or after Instrumentation reconcile. Does not write meta_*.

        When ``workflow_json`` is supplied (Instrumentation workflow outputs),
        missing ``context_version`` / ``source`` / ``summary`` / ``feature_id`` /
        upserts are derived from that payload. Explicit args still win.

        Args:
            context_version: New version id, e.g. \"v1\" or \"v3\". Optional when
                ``workflow_json`` is set (auto-bumps from current).
            source: e.g. \"seed\", \"instrumentation\", \"manual\".
            summary: Short human summary of what changed.
            feature_id: Optional feature that triggered this publish.
            parent_version: Parent to copy from; omit to use current is_current.
            upserts_json: JSON array of
                {\"kind\",\"item_key\",\"label?\",\"payload?\"}.
                kind: entity|metric|join|funnel_step|issue|contradiction.
            deletes_json: JSON array of {\"kind\",\"item_key\"} removed after copy.
            copy_forward: If true (default), copy all parent items first.
            workflow_json: Optional JSON object from Instrumentation workflow
                (register_meta + pipeline_plan / apply_clickhouse).
        """
        try:
            upserts = json.loads(upserts_json) if upserts_json else []
            deletes = json.loads(deletes_json) if deletes_json else []
            if not isinstance(upserts, list) or not isinstance(deletes, list):
                return json.dumps(
                    {"error": "upserts_json and deletes_json must be JSON arrays"}
                )

            derived_feature_id: str | None = None
            derived_summary: str | None = None
            if workflow_json and workflow_json.strip():
                workflow_payload = json.loads(workflow_json)
                if not isinstance(workflow_payload, dict):
                    return json.dumps({"error": "workflow_json must be a JSON object"})
                derived_feature_id, derived_summary, derived_upserts = _upserts_from_workflow(
                    workflow_payload
                )
                if not upserts:
                    upserts = derived_upserts
                if not (feature_id or "").strip():
                    feature_id = derived_feature_id
                if summary is None or not str(summary).strip():
                    summary = derived_summary
                if not (source or "").strip():
                    source = "instrumentation"

            version = (context_version or "").strip()
            if not version:
                if not workflow_json:
                    return json.dumps({"error": "context_version is required"})
                latest = get_latest_context_items()
                version = _next_context_version(latest.get("context_version"))

            src = (source or "").strip()
            if not src:
                return json.dumps({"error": "source is required"})

            result = publish_context_version(
                context_version=version,
                source=src,
                summary=summary,
                feature_id=feature_id,
                parent_version=parent_version,
                upserts=upserts,
                deletes=deletes,
                copy_forward=copy_forward,
            )
            return json.dumps(result, default=str)
        except (ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc)})


def get_context_catalog_tools() -> ContextCatalogTools:
    """Factory for other agents: read tools + publish_context_version."""
    return ContextCatalogTools()


class ContextReadTools(Toolkit):
    """Read-only catalog tools for the Context Agent (no publish)."""

    def __init__(self):
        tools = [
            self.get_latest_context_items,
            self.get_feature_meta,
        ]
        super().__init__(name="context_read", tools=tools)

    def get_latest_context_items(self, kinds: Optional[str] = None) -> str:
        """Load the current living context (version + all items by default).

        Omit kinds to fetch every context_item for the current version.

        Args:
            kinds: Optional comma-separated filter, e.g. \"metric,funnel_step\".
        """
        kind_list: Sequence[str] | None = None
        if kinds and kinds.strip():
            kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
        result = get_latest_context_items(kinds=list(kind_list) if kind_list else None)
        return json.dumps(result, default=str)

    def get_feature_meta(self, feature_id: str) -> str:
        """Load Instrumentation meta for one feature (journey + columns).

        Args:
            feature_id: e.g. \"01_express_checkout\" or \"unseen_data\"
        """
        result = get_feature_meta(feature_id=feature_id)
        return json.dumps(result, default=str)


def get_context_read_tools() -> ContextReadTools:
    """Factory for the Context Agent: read-only (no publish)."""
    return ContextReadTools()
