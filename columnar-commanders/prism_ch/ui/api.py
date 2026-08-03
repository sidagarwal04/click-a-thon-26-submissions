"""JSON endpoints behind the UI.

Deliberately thin: each handler builds the same agent the CLI builds and returns
its result. The UI is a second front-end onto one pipeline, not a second
pipeline - so a schema approved in the browser carries the same trace, the same
`run_id`, and the same lint and repair path as one produced from the terminal.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import Settings
from ..db import connect
from ..tracing import pipeline_run

log = logging.getLogger(__name__)


def _client(settings: Settings) -> Any:
    return connect(settings)


def health(settings: Settings) -> dict[str, Any]:
    try:
        client = _client(settings)
        version = client.command("SELECT version()")
        return {
            "ok": True,
            "clickhouse": str(version),
            "database": settings.database,
            "target": settings.clickhouse_target,
            "llm": settings.llm_model if settings.llm_enabled else None,
        }
    except Exception as exc:  # noqa: BLE001 - surfaced in the UI banner
        return {"ok": False, "error": str(exc)[:300]}


def _decode(value: str, what: str) -> str:
    import base64

    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"could not decode the uploaded {what}: {exc}") from exc


def _spec_from_body(settings: Settings, body: dict[str, Any]) -> Any:
    """Build a SpecInput from the browser payload.

    The spec text may be typed into the brief box or uploaded as `spec.md` -
    both reach the same splitter, because the tables come from the spec's user
    actions either way and it should not matter which route it took.

    Events uploaded as a file are sampled per action; events pasted directly
    are used as-is, since a deliberate handful of examples should not be
    thinned again.
    """
    from ..agents.types import build_spec

    brief = body.get("brief") or ""
    if body.get("spec_b64"):
        brief = _decode(body["spec_b64"], "spec")

    if body.get("file_b64"):
        raw_events = _decode(body["file_b64"], "events file")
        fraction = float(body.get("sample_pct") or 15) / 100
    else:
        raw_events = body.get("events") or ""
        fraction = 1.0

    return build_spec(
        name=(body.get("name") or "spec").strip(),
        brief=brief,
        raw_events=raw_events,
        sample_fraction=fraction,
    )


def instrument(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    """Design a schema. `execute` is the approval gate - false previews only.

    One table per user action the spec declares. An existing table is widened
    with `ALTER TABLE ADD COLUMN`, never dropped and never put to a prompt.
    """
    from ..agents import InstrumentationAgent

    try:
        spec = _spec_from_body(settings, body)
    except ValueError as exc:
        return {"error": str(exc)}

    if not spec.brief and not spec.events:
        return {"error": "provide a spec description or sample events"}

    execute = bool(body.get("execute"))
    with pipeline_run("instrument", spec_name=spec.name, via="ui") as run:
        agent = InstrumentationAgent(settings, _client(settings))
        try:
            result = agent.run(spec, execute=execute)
        except Exception as exc:  # noqa: BLE001 - shown in the UI
            log.exception("instrumentation failed")
            return {
                "error": str(exc)[:1200],
                "run_id": run.run_id,
                "decisions": agent.decisions,
                "steps": agent.steps,
                "executed_statements": [s.as_dict() for s in agent.executed_statements],
            }
        run.metric("schema.tables", len(result.proposal.tables))
        run.metric("schema.repairs", agent.repairs)
        run.metric("schema.lint_issues", agent.lint_issues)
        run.metric("schema.executed", 1 if execute else 0)
        run.metric("schema.rows_loaded", sum(r.loaded for r in result.load_results))
        if execute:
            from .history import UIHistoryStore

            try:
                history = UIHistoryStore(agent.client, settings)
                history.ensure_schema()
                actual_changes = [
                    statement
                    for statement in result.executed_statements
                    if statement.kind == "alter_table"
                    or (
                        statement.kind in {"create_table", "create_view"}
                        and statement.table not in agent.preexisting_tables
                    )
                ]
                history.record_schema_changes(run.run_id, actual_changes)
            except Exception:  # noqa: BLE001 - audit failure must not lose the schema result
                log.warning("could not persist schema UI history", exc_info=True)
        return {
            "run_id": run.run_id,
            "trace_id": run.trace_id,
            "executed": result.executed,
            "events_sampled": len(spec.events),
            "events_total": spec.events_total,
            "sampled": spec.sampled,
            "actions": [
                {
                    "action": g.action,
                    "sampled": len(g.events),
                    "total": g.total,
                }
                for g in spec.groups
            ],
            "empty_actions": result.empty_actions,
            "undeclared_actions": result.undeclared_actions,
            "action_source": spec.action_source,
            "ddl": result.statements,
            "executed_statements": [s.as_dict() for s in result.executed_statements],
            "decisions": result.decisions,
            "steps": agent.steps,
            "notes": result.proposal.notes,
            "load_results": [r.as_dict() for r in result.load_results],
            # Set only when execute=true and _notify_context succeeded - the
            # instrument -> context -> analytics chain (ARCHITECTURE.md).
            "context_version": agent.context_version,
            "context_diff": agent.context_delta.as_dict() if agent.context_delta else None,
            "bootstrapped_default_context": agent.bootstrapped_default_context,
            "analytics": agent.last_insight_report.as_dict() if agent.last_insight_report else None,
            "analytics_run_id": agent.last_analytics_run_id,
            "analytics_trace_id": agent.last_analytics_trace_id,
        }


def analyze(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    from ..agents import AnalyticsAgent

    focus = (body.get("focus") or "").strip() or None
    with pipeline_run("analyze", spec_name="analytics", via="ui") as run:
        agent = AnalyticsAgent(settings, _client(settings))
        try:
            report = agent.run(focus)
        except Exception as exc:  # noqa: BLE001
            log.exception("analysis failed")
            return {"error": str(exc)[:1200], "run_id": run.run_id}
        confidences = [i.confidence for i in report.insights]
        run.metric("analysis.insights", len(report.insights))
        run.metric("analysis.queries", report.queries_run)
        if confidences:
            run.metric("analysis.confidence_avg", round(sum(confidences) / len(confidences), 3))
        from .history import UIHistoryStore

        try:
            history = UIHistoryStore(agent.client, settings)
            history.ensure_schema()
            history.record_insights(run.run_id, report)
        except Exception:  # noqa: BLE001 - audit failure must not lose the analysis result
            log.warning("could not persist insight UI history", exc_info=True)
        return {"run_id": run.run_id, "trace_id": run.trace_id, **report.as_dict()}


def dashboard(settings: Settings) -> dict[str, Any]:
    """One read model for the visualization layer."""
    from ..agents.context_store import ContextStore, context_dialect, diff_snapshots
    from .history import UIHistoryStore

    client = _client(settings)
    history = UIHistoryStore(client, settings)
    store = ContextStore(client, context_dialect(settings))
    try:
        # Both stores own tables the dashboard reads. Creating them here is
        # idempotent and keeps a first-boot read from failing on a table the
        # agents have not had a reason to create yet.
        history.ensure_schema()
        store.ensure_schema()
        versions = store.history(limit=12)
        context_changes = []
        for item in versions:
            version = int(item["version"])
            delta = None
            if version > 1:
                delta = diff_snapshots(store.load(version - 1), store.load(version)).as_dict()
            context_changes.append({**item, "diff": delta})
        schema_changes = history.schema_changes()
        insights = history.insights()
        return {
            "schema_changes": schema_changes,
            "insights": insights,
            "context_changes": context_changes,
            # Empty across the board means nothing has run yet, which is a
            # normal first-boot state rather than a failure.
            "empty": not (schema_changes or insights or context_changes),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "error": str(exc)[:500],
            "schema_changes": [],
            "insights": [],
            "context_changes": [],
        }


def context(settings: Settings) -> dict[str, Any]:
    """Latest context version, its issues, and the changelog (C9 / T11)."""
    from ..agents.context_store import ContextStore, context_dialect, diff_snapshots

    store = ContextStore(_client(settings), context_dialect(settings))
    try:
        store.ensure_schema()
        latest = store.load()
        history = store.history()
        delta = None
        if latest.version > 1:
            previous = store.load(latest.version - 1)
            delta = diff_snapshots(previous, latest).as_dict()
        return {
            "version": latest.version,
            "entries": len(latest.entries),
            "has_base_context": any(
                e.source not in {"clickhouse", "instrumentation"} for e in latest.entries
            ),
            "counts": latest.as_dict()["counts"],
            "entry_list": [
                {"kind": e.kind, "key": e.key, "value": e.value,
                 "source": e.source, "detail": e.detail}
                for e in latest.entries
            ],
            "issues": [i.as_dict() for i in latest.issues],
            "history": history,
            "diff": delta,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:300], "version": 0, "issues": [], "history": []}


def context_search(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    """Semantic search over the context layer."""
    from ..agents import llm
    from ..agents.context_store import ContextStore, context_dialect

    query = (body.get("query") or "").strip()
    if not query:
        return {"error": "query is required", "results": []}

    store = ContextStore(_client(settings), context_dialect(settings))
    version = store.latest_version()
    if version == 0:
        return {"results": [], "version": 0}

    if not store.has_embeddings(version):
        return {"error": "no embeddings yet — refresh context first", "results": []}

    try:
        query_vec = llm.embed(settings, [query])[0]
    except Exception as exc:
        return {"error": f"embedding failed: {str(exc)[:200]}", "results": []}

    results = store.semantic_search(
        query_vec, version=version, limit=int(body.get("limit", 10))
    )
    return {"results": results, "version": version, "query": query}


def context_refresh(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    """Initialize the base context once; schema refreshes happen automatically."""
    from ..agents import ContextAgent
    from ..tracing import pipeline_run

    base_text = (body.get("base_context") or "").strip()
    if not base_text:
        return {"error": "base_context is required; database schema refresh is automatic"}

    with pipeline_run("context", spec_name="context-refresh", surface="ui") as run:
        agent = ContextAgent(settings, _client(settings))
        agent.store.ensure_schema()
        current = agent.store.load()
        if any(
            entry.source not in {"clickhouse", "instrumentation"}
            for entry in current.entries
        ):
            return {
                "error": "base context is already initialized",
                "version": current.version,
            }

        import pathlib
        import tempfile

        tmp = pathlib.Path(tempfile.mktemp(suffix=".md"))
        try:
            tmp.write_text(base_text, encoding="utf-8")
            version, delta, insight_report = agent.run(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)

        snapshot = agent.store.load(version)
        if agent.last_analytics_run_id:
            from .history import UIHistoryStore

            try:
                history = UIHistoryStore(agent.client, settings)
                history.ensure_schema()
                history.record_insights(agent.last_analytics_run_id, insight_report)
            except Exception:  # noqa: BLE001
                log.warning("could not persist auto-analysis UI history", exc_info=True)
        run.output(snapshot.as_dict())

        return {
            "version": version,
            "entries": len(snapshot.entries),
            "counts": snapshot.as_dict()["counts"],
            "entry_list": [
                {"kind": e.kind, "key": e.key, "value": e.value,
                 "source": e.source, "detail": e.detail}
                for e in snapshot.entries
            ],
            "issues": [i.as_dict() for i in snapshot.issues],
            "diff": delta.as_dict() if delta else None,
            "run_id": run.run_id,
            "analytics": insight_report.as_dict(),
            "analytics_run_id": agent.last_analytics_run_id,
            "analytics_trace_id": agent.last_analytics_trace_id,
        }


def schema_history(settings: Settings) -> dict[str, Any]:
    """Tables the agents created, newest first (T9)."""
    client = _client(settings)
    try:
        result = client.query(
            "SELECT name, engine, sorting_key, partition_key, total_rows, "
            "metadata_modification_time FROM system.tables WHERE database = {db:String} "
            "ORDER BY metadata_modification_time DESC",
            parameters={"db": settings.database},
        )
        rows = getattr(result, "result_rows", None) or []
        prefix = settings.table_prefix
        return {
            "prefix": prefix,
            "tables": [
                {
                    "name": r[0],
                    "generated": bool(prefix) and str(r[0]).startswith(prefix),
                    "engine": r[1],
                    "order_by": r[2],
                    "partition_by": r[3],
                    "rows": r[4],
                    "modified": str(r[5]),
                }
                for r in rows
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:300], "tables": []}


def reset_local(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    """Danger zone: drop every agent-generated table, for a fresh demo load.

    Scoped to exactly two categories, both computed from what the codebase
    already treats as generated - never a guess: tables carrying the
    configured `table_prefix` (every feature the Instrumentation Agent has
    ever created) and the context layer's own tables
    (`ContextStore.internal_tables` - context_versions/entries/issues/
    embeddings). The 8 original event tables match neither category, so there
    is no way for this to reach them even by accident. The Schema tab's
    button is expected to confirm with the user before calling this - nothing
    here prompts, since a server-side confirmation cannot stop a mis-click.
    """
    from ..agents.context_store import ContextStore, context_dialect

    client = _client(settings)
    try:
        result = client.query(
            "SELECT name FROM system.tables WHERE database = {db:String}",
            parameters={"db": settings.database},
        )
        names = {str(r[0]) for r in (getattr(result, "result_rows", None) or [])}
        internal = set(ContextStore(client, context_dialect(settings)).internal_tables)
        prefix = settings.table_prefix
        to_drop = sorted(
            name for name in names if name in internal or (prefix and name.startswith(prefix))
        )
        for name in to_drop:
            client.command(f"DROP TABLE IF EXISTS `{settings.database}`.`{name}`")
        return {"ok": True, "dropped": to_drop}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}
