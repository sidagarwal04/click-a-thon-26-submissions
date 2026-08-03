"""Analytics Agent — genuine multi-turn exploration, not pre-baked seed queries.

Design (revised): the orchestrator does NOT run deterministic "seed queries" or
pre-fetch context sections anymore. That approach silently produced wrong numbers
whenever a table's shape didn't match the seed queries' baked-in assumptions — a
real run computed a 0.0% "feature adoption rate" for a table whose feature actors
are keyed by `share_id`, not `user_id`, because the generic seed query joined on
the wrong column and nobody (query or LLM) caught it until manual inspection.

Instead, the LibreChat analytics agent gets a minimal payload (spec_name,
table_name, database, spec_markdown) and does everything itself via its own MCP
tools: load the `context-engine` skill, explore context sections, inspect the
table's real shape, then answer the spec's PM questions one by one with queries it
writes itself — genuinely agentic, not templated. It's the same tool-loop pattern
already used by the proposer/reviewer/chronicler agents.

Output changed too: instead of a JSON evidence blob the dashboard renders into
fixed chart components, the agent now writes a complete, self-contained HTML
report (see ANALYTICS_AGENT in agents/prompts.py for the exact structure it's
told to produce) — persisted alongside the summary fields so a list view can show
the short version and link out to the full report.

One deterministic check remains: a bare `SELECT count()` for the orchestrator's
hard small-n confidence cap. This carries no interpretive assumption about how
the table is keyed (unlike the old seed queries), so it doesn't reintroduce the
failure mode being removed here — it's a safety net, not evidence handed to the LLM.
"""
from __future__ import annotations

import json
import os
import uuid

from agent_meta.db import get_client
from tracing import traced_run

# Import shared agent helpers from their own module to avoid a circular import
# (pipeline.py lazily imports analytics_agent; analytics_agent must not import
# pipeline at module load time or the cycle breaks when the lazy import is hoisted).
from orchestrator.agent_io import AgentOutputError, _call_json_agent


def _total_row_count(table_name: str) -> int:
    """Bare row count, purely for the orchestrator's hard confidence cap below —
    NOT handed to the LLM as evidence. No join, no assumption about how the table
    is keyed, so this can't produce the wrong-join-key failure mode the old seed
    queries had."""
    client = get_client(database="atlys")
    try:
        return client.query(f"SELECT count() FROM atlys.{table_name}").result_rows[0][0]
    except Exception:
        return 0


def _call_analytics(run, spec_name: str, table_name: str, spec_markdown: str) -> dict:
    """Calls the LibreChat analytics agent with a minimal payload. The agent loops
    via its own MCP tools (context-engine skill, list_context_sections/
    lookup_context, describe_table, run_query, execute_python) to explore the
    table and answer the spec's PM questions, then returns the final structured
    JSON including a full HTML report."""
    payload = {
        "trigger": "new_table_executed",
        "spec_name": spec_name,
        "table_name": table_name,
        "database": "atlys",
        # Full spec, not truncated — the "Questions the PM will ask" section is
        # what the agent works through one by one, and truncating risks cutting
        # it off for a longer spec.
        "spec_markdown": spec_markdown,
        "instruction": (
            "A new feature table has just been instrumented into ClickHouse. "
            "Follow your system prompt's stages in order: load context-engine "
            "first, understand this table's real shape before querying it, "
            "answer the spec's PM questions one by one with your own queries, "
            "correlate with known issues, then write the full HTML report."
        ),
    }
    result, _r = _call_json_agent(
        "analytics_agent", payload, run, "analytics",
        required_keys=["title", "summary", "confidence", "report_html"],
        reasoning_fn=lambda parsed: parsed.get("summary"),
        spec_name=spec_name, table_name=table_name,
    )
    return result


def _call_analytics_custom(run, prompt: str) -> dict:
    """Same call as _call_analytics, but for a free-text investigation with no
    single table_name/spec handed to the agent -- see ANALYTICS_AGENT's
    `custom_investigation` branch in agents/prompts.py. The agent decides which
    table(s) matter itself via list_tables."""
    payload = {
        "trigger": "custom_investigation",
        "prompt": prompt,
        "database": "atlys",
        "instruction": (
            "A person asked a free-text question directly -- there is no single "
            "table_name handed to you. Follow your system prompt's "
            "custom_investigation branch of each stage: list_tables and pick "
            "what's relevant, understand the real shape of each table you pick, "
            "work through the question(s) in the prompt one by one with your own "
            "queries, correlate with known issues, then write the full HTML report."
        ),
    }
    result, _r = _call_json_agent(
        "analytics_agent", payload, run, "analytics",
        required_keys=["title", "summary", "confidence", "report_html"],
        reasoning_fn=lambda parsed: parsed.get("summary"),
        prompt=prompt[:200],
    )
    return result


def _write_insight(meta_client, spec_name: str, analysis: dict, trace_url: str, prompt: str = "") -> str:
    insight_id = str(uuid.uuid4())
    known_issues_raw = analysis.get("related_known_issues", [])
    ki_serialized = [
        json.dumps(ki) if isinstance(ki, dict) else str(ki)
        for ki in known_issues_raw
    ]

    meta_client.insert(
        "insights",
        [[
            insight_id, spec_name,
            analysis.get("title", ""),
            analysis.get("summary", ""),
            analysis.get("segment_cuts", []),
            json.dumps({"confidence_drivers": analysis.get("confidence_drivers", "")}),
            ki_serialized,
            float(analysis.get("confidence", 0.0)),
            trace_url,
            analysis.get("report_html", ""),
            prompt,
        ]],
        column_names=["insight_id", "spec_name", "title", "summary",
                      "segment_cuts", "evidence", "related_known_issues",
                      "confidence", "trace_url", "report_html", "prompt"],
    )
    return insight_id


def run_analytics(run, spec_name: str, table_name: str, spec_markdown: str,
                  meta_client) -> dict | None:
    """Full analytics loop: call the analytics agent (which explores and queries
    entirely on its own) → persist the insight + HTML report. Returns the insight
    dict or None if the agent isn't configured."""
    if not os.environ.get("OPENAI_API_KEY"):
        run.log(step="analytics_skipped", input=None,
                output="OPENAI_API_KEY not set — skipping analytics")
        return None

    total_events = _total_row_count(table_name)
    run.log(step="small_n_gate", input=None,
            output={"total_events": total_events, "sparse": total_events < 100})

    with run.span("analytics_explore"):
        try:
            analysis = _call_analytics(run, spec_name, table_name, spec_markdown)
        except AgentOutputError as e:
            run.log(step="analytics_json_error", input=e.raw_text[:1000], output=str(e.parse_error))
            return None

    # Hard small-n confidence cap — the LLM's confidence is advisory, this is enforced.
    # Prompts alone don't reliably gate confidence; make it deterministic.
    if total_events < 100 and analysis.get("confidence", 0) > 0.5:
        analysis["confidence"] = 0.5
        analysis["confidence_drivers"] = (
            f"[capped by orchestrator] total_feature_events={total_events} (<100); "
            + analysis.get("confidence_drivers", "")
        )
        run.log(step="confidence_capped", input=None,
                output={"total_events": total_events, "capped_to": 0.5})

    with run.span("analytics_persist"):
        insight_id = _write_insight(meta_client, spec_name, analysis, run.url)
        run.log(step="insight_written", input=None,
                output={"insight_id": insight_id, "confidence": analysis.get("confidence"),
                        "title": analysis.get("title", "")[:120]})

    analysis["insight_id"] = insight_id
    analysis["trace_url"] = run.url
    return analysis


def run_analytics_custom(run, prompt: str, meta_client) -> dict | None:
    """Same loop as run_analytics(), for a free-text investigation with no
    single spec/table attached. Skips the small-n row-count cap entirely --
    that cap is keyed to one feature table's total row count, which doesn't
    mean anything once the agent may be looking across several tables of very
    different sizes; the agent's own per-query SMALL-N GATE (see
    ANALYTICS_AGENT's Stage 3) is what actually governs confidence here."""
    if not os.environ.get("OPENAI_API_KEY"):
        run.log(step="analytics_skipped", input=None,
                output="OPENAI_API_KEY not set — skipping analytics")
        return None

    with run.span("analytics_explore"):
        try:
            analysis = _call_analytics_custom(run, prompt)
        except AgentOutputError as e:
            run.log(step="analytics_json_error", input=e.raw_text[:1000], output=str(e.parse_error))
            return None

    with run.span("analytics_persist"):
        insight_id = _write_insight(meta_client, "", analysis, run.url, prompt=prompt)
        run.log(step="insight_written", input=None,
                output={"insight_id": insight_id, "confidence": analysis.get("confidence"),
                        "title": analysis.get("title", "")[:120]})

    analysis["insight_id"] = insight_id
    analysis["trace_url"] = run.url
    return analysis


def _latest_executed_table(meta_client, spec_name: str) -> str | None:
    """The table this spec landed as, IF its most recent proposal actually
    reached 'executed' -- the same gate the dashboard's "Create Insight"
    button enforces client-side (only executed specs are selectable), checked
    again here since this is the real authority: a proposal that's
    needs_rework/rejected/still mid-pipeline has no real table to analyze."""
    rows = meta_client.query(
        "SELECT argMax(table_name, ts) AS table_name, argMax(status, ts) AS status "
        "FROM agent_meta.schema_proposals WHERE spec_name = %(spec)s GROUP BY spec_name",
        parameters={"spec": spec_name},
    ).result_rows
    if not rows or rows[0][1] != "executed":
        return None
    return rows[0][0]


def _latest_spec_markdown(meta_client, spec_name: str) -> str | None:
    rows = meta_client.query(
        "SELECT argMax(spec_markdown, ts) AS spec_markdown "
        "FROM agent_meta.spec_sources WHERE spec_name = %(spec)s GROUP BY spec_name",
        parameters={"spec": spec_name},
    ).result_rows
    return rows[0][0] if rows and rows[0][0] else None


def run_analytics_for_spec(spec_name: str) -> dict:
    """Explicit, dashboard-triggered entry point -- the counterpart to
    orchestrator.ingest_spec for the analytics half of the pipeline, now that
    executing a schema no longer implicitly runs analytics (see
    orchestrator/pipeline.py's ingest_spec docstring). Looks up the spec's
    latest EXECUTED table and its persisted spec_markdown (agent_meta.spec_sources
    -- written by ingest_spec, see the same file), opens its own traced_run
    (this is a separate step now, not nested inside the ingest trace), and runs
    the same analytics loop as run_analytics(). Returns a summary dict shaped
    like ingest_spec()'s return value so the dashboard's live-run panel can
    treat both the same way.
    """
    meta_client = get_client(database="agent_meta")

    table_name = _latest_executed_table(meta_client, spec_name)
    if not table_name:
        return {
            "status": "failed",
            "error": f"Spec '{spec_name}' has no executed proposal — schema must be executed before analytics can run.",
        }

    spec_markdown = _latest_spec_markdown(meta_client, spec_name)
    if not spec_markdown:
        return {
            "status": "failed",
            "error": f"No stored spec markdown for '{spec_name}' — re-run ingestion to capture it (older runs predate spec_sources).",
        }

    with traced_run(agent="analytics", spec=spec_name) as run:
        analysis = run_analytics(run, spec_name, table_name, spec_markdown, meta_client)
        if analysis is None:
            return {
                "status": "failed",
                "error": "Analytics agent did not produce a usable result (not configured, or output couldn't be parsed) — check the trace.",
                "trace_url": run.url,
            }
        return {
            "status": "completed",
            "insight_id": analysis.get("insight_id"),
            "title": analysis.get("title"),
            "confidence": analysis.get("confidence"),
            "table_name": table_name,
            "trace_url": analysis.get("trace_url", run.url),
        }


def run_analytics_for_prompt(prompt: str) -> dict:
    """Dashboard-triggered entry point for a free-text investigation -- the
    counterpart to run_analytics_for_spec for when the person has a question
    rather than a specific just-executed table in mind (see ANALYTICS_AGENT's
    `custom_investigation` trigger). No spec/table lookup -- the agent decides
    what's relevant to `prompt` itself via list_tables. Returns a summary dict
    shaped like run_analytics_for_spec's so the dashboard's live-run panel can
    treat both the same way.
    """
    if not prompt or not prompt.strip():
        return {"status": "failed", "error": "Prompt is empty."}

    meta_client = get_client(database="agent_meta")

    with traced_run(agent="analytics", spec="") as run:
        analysis = run_analytics_custom(run, prompt.strip(), meta_client)
        if analysis is None:
            return {
                "status": "failed",
                "error": "Analytics agent did not produce a usable result (not configured, or output couldn't be parsed) — check the trace.",
                "trace_url": run.url,
            }
        return {
            "status": "completed",
            "insight_id": analysis.get("insight_id"),
            "title": analysis.get("title"),
            "confidence": analysis.get("confidence"),
            "trace_url": analysis.get("trace_url", run.url),
        }
