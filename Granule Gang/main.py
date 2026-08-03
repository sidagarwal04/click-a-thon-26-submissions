import argparse
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
import clickhouse_connect
from agents.config import get_config, make_llm_call_fn
from agents.setup import ensure_control_tables, is_business_context_seeded
from agents.context.agent import ContextAgent
from agents.instrumentation.agent import InstrumentationAgent
from agents.analytics.agent import AnalyticsAgent
from agents.analytics.mcp_client import ClickHouseMCPClient
from agents.tracing.agent import get_tracer
from agents.visualization.dashboard_builder import DashboardBuilder
import dataclasses
import json
from collections import defaultdict


def _log(stage: str, message: str, t0: float = None) -> None:
    """Timestamped, stage-tagged console log for pipeline runs -- every major
    step prints [HH:MM:SS][stage] so an e2e run is traceable start to finish
    from stdout alone (+ elapsed time once a stage has a start time)."""
    ts = datetime.now().strftime("%H:%M:%S")
    elapsed = f" (+{time.monotonic() - t0:.1f}s)" if t0 is not None else ""
    print(f"[{ts}][{stage}] {message}{elapsed}")


def _build_llm_call_fn(or_config):
    """Adapt OpenRouterConfig into the (prompt, span_name) -> str callable
    ContextAgent expects. Degrades gracefully (matching the fallback pattern
    already used by InstrumentationAgent/AnalyticsAgent) if no OPENROUTER_API_KEY
    is configured, so the pipeline still runs -- just without context
    audit/enrichment -- rather than crashing on the first ContextAgent call."""
    if or_config and or_config.enabled:
        return make_llm_call_fn(or_config)

    print("Warning: OPENROUTER_API_KEY not set -- ContextAgent will run without LLM audit/enrichment.")

    def _noop_llm_call_fn(prompt: str, span_name: str = "context_llm_call") -> str:
        if span_name == "context_audit":
            return "[]"
        if span_name == "context_resolve":
            return json.dumps({"resolved_value": "", "resolution_notes": "LLM not configured"})
        return json.dumps({"schema_comments": {}, "business_rules": []})

    return _noop_llm_call_fn


def _extract_scalar(value):
    if isinstance(value, dict):
        for key in ("amount", "currency", "latency_ms", "value", "id", "code", "name"):
            if key in value and not isinstance(value[key], (dict, list)):
                return value[key]
        return None
    if isinstance(value, list):
        return json.dumps(value)
    return value


def _parse_timestamp(value):
    """events.ndjson carries timestamp as an ISO-ish string
    ("2026-06-08T06:00:00.000"); clickhouse_connect's DateTime writer needs an
    actual datetime object (it calls .timestamp() on each value client-side),
    so passing the raw string through failed every single row insert."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _parse_event_id(value):
    """The `id` column is UUID; known specs' raw ids are 32-char lowercase hex
    (no dashes), which clickhouse_connect parses fine, but a single
    non-hex/malformed id in a batch throws client-side and fails the WHOLE
    table's insert, not just that row -- a real risk for an unseen spec's data
    (base_context.md repeatedly flags "known texture": nulls, backfills,
    dupes). Fall back to a freshly generated UUID rather than lose the batch;
    log so it's traceable, not silent."""
    if isinstance(value, str):
        try:
            return str(uuid.UUID(value))
        except ValueError:
            print(f"  Warning: event id '{value}' isn't a valid UUID/hex string, substituting a generated one")
            return str(uuid.uuid4())
    return value


def _default_for_column(col):
    """A raw event can legitimately have a null on a field the generated
    schema marked non-nullable (e.g. an LLM schema-generation pass deciding
    `os` is always present, when a web session's raw events never carry
    one) -- exactly the "known texture" base_context.md flags repeatedly.
    clickhouse_connect raises client-side on a None in a non-Nullable column
    and fails the WHOLE batch, not just that row, so substitute a
    type-appropriate default rather than lose every row in the table."""
    base_type = col.type.strip()
    while base_type.startswith("LowCardinality(") and base_type.endswith(")"):
        base_type = base_type[len("LowCardinality("):-1].strip()
    if base_type == "UUID":
        return str(uuid.uuid4())
    if base_type in ("DateTime", "DateTime64", "Date"):
        return datetime.now()
    if base_type.startswith("UInt") or base_type.startswith("Int") or base_type.startswith("Float"):
        return 0
    return ""


def _flatten_event_row(row: dict) -> dict:
    flattened = {}
    for key, value in row.items():
        if key == "event":
            continue
        if key == "timestamp":
            flattened[key] = _parse_timestamp(value)
            continue
        if key == "id":
            flattened[key] = _parse_event_id(value)
            continue
        if isinstance(value, dict):
            # Prefix with the parent key (e.g. "payment": {"amount": ...} ->
            # "payment_amount") rather than hoisting sub-keys unprefixed. A
            # prior version dropped the parent key entirely and then
            # hand-remapped "amount"/"currency" to "value"/"currency" as a
            # special case for the express_payment_confirmed event alone --
            # but that remap target didn't match this spec's actual generated
            # schema (payment_amount/payment_currency/payment_latency_ms), so
            # every insert into that table failed on an unrecognized column.
            # Prefixing generically matches whatever naming convention the
            # schema-generation LLM already uses for a nested payload (it
            # names columns after the source object), for any event with a
            # nested field, not just this one.
            for sub_key, sub_value in value.items():
                flattened[f"{key}_{sub_key}"] = _extract_scalar(sub_value)
            continue
        flattened[key] = _extract_scalar(value)
    return flattened


def _event_to_table(row: dict) -> str | None:
    event_name = row.get("event")
    if not event_name:
        return None
    mapping = {
        "express_checkout_shown": "express_checkout_shown",
        "express_checkout_selected": "express_checkout_selected",
        "saved_method_used": "saved_method_used",
        "otp_entered": "otp_entered",
        "express_payment_confirmed": "express_payment_confirmed",
    }
    return mapping.get(event_name, event_name)


def _extract_pm_questions(spec_md: str) -> list:
    """Pull the "## Questions the PM will ask" bullet list out of a spec.md, so
    AnalyticsAgent can be prompted to answer this spec's actual questions
    instead of only producing generic funnel commentary."""
    match = re.search(r"^##\s*Questions the PM will ask\s*\n(.*?)(?=\n##|\Z)", spec_md, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return [line.lstrip("- ").strip() for line in match.group(1).splitlines() if line.strip().startswith("-")]


def _resolve_path(base: Path, *parts: str) -> Path:
    candidate = base.joinpath(*parts)
    if candidate.exists():
        return candidate
    repo_root = base.parent
    alt = repo_root.joinpath(*parts)
    return alt if alt.exists() else candidate

def run_pipeline(spec_dir: str):
    repo_root = Path(__file__).resolve().parent
    spec_path = _resolve_path(repo_root, spec_dir)
    if not spec_path.exists():
        print(f"Error: {spec_dir} does not exist.")
        return

    pipeline_t0 = time.monotonic()
    _log("pipeline", f"Starting pipeline for spec: {spec_dir}")

    # 1. Init Configs & Tracing
    ch_config, lf_config, or_config = get_config()
    tracer = get_tracer()
    tracer.enabled = lf_config.enabled
    _log("pipeline", f"Tracing {'enabled (Langfuse)' if tracer.enabled else 'disabled -- no LANGFUSE_* configured'}")

    trace_id = tracer.start_trace("pipeline_run", metadata={"spec_dir": str(spec_dir)})

    try:
        with tracer.trace_span("pipeline.initialize"):
            client = clickhouse_connect.get_client(
                host=ch_config.host,
                port=ch_config.port,
                username=ch_config.user,
                password=ch_config.password,
                secure=ch_config.secure,
                database=ch_config.database,
            )
        _log("pipeline", f"Connected to ClickHouse at {ch_config.host} (database={ch_config.database})")

        # 2. Run ContextAgent
        stage_t0 = time.monotonic()
        _log("context", "Running Context Agent...")
        with tracer.trace_span("pipeline.context"):
            ensure_control_tables(client)
            llm_call_fn = _build_llm_call_fn(or_config)
            ca = ContextAgent(client=client, llm_call_fn=llm_call_fn)
            if not is_business_context_seeded(client):
                seeded = ca.load_v1()
                print(f"  Seeded business-context document (v{seeded}).")
            else:
                print("  Business context document already seeded, skipping load_v1().")
        _log("context", "Context Agent done", stage_t0)

        # 3. Run InstrumentationAgent
        stage_t0 = time.monotonic()
        _log("instrumentation", "Running Instrumentation Agent...")
        with tracer.trace_span("pipeline.instrumentation"):
            print("  Parsing spec and generating schema...")
            ia = InstrumentationAgent(
                clickhouse_client=client,
                context_agent=ca,
                openrouter_config=or_config,
                database=ch_config.database
            )
            # process_spec() already executes the generated DDL, registers each
            # table, updates context, and creates the rollup MV (execute_ddl=True
            # by default) -- emit_ddl() below is just the written record, not a
            # second execution pass. A prior version of this function re-parsed
            # and re-ran emit_ddl()'s output here, which just re-issued every
            # CREATE TABLE/VIEW a second time and errored on "already exists".
            schemas = ia.process_spec(spec_path)
            print("  Emitting DDL record...")
            ddl_out = ia.emit_ddl()
            out_file = spec_path / "generated_schema.sql"
            out_file.write_text(ddl_out)

            print(f"Created and registered {len(schemas)} schemas ({len(ia.materialized_views)} materialized view(s)).")
            
            # Load Data
            events_file = spec_path / "events.ndjson"
            if events_file.exists():
                print("Loading sample event data into ClickHouse...")
                events_by_table = defaultdict(list)
                missing_tables = defaultdict(int)

                with open(events_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue
                        table_name = _event_to_table(data)
                        if not table_name or table_name not in ia.schemas:
                            missing_tables[table_name or "<unknown>"] += 1
                            continue
                        events_by_table[table_name].append(_flatten_event_row(data))

                for table, rows in events_by_table.items():
                    if not rows:
                        continue
                    schema = ia.get_schema(table)
                    if not schema:
                        print(f"  Warning: no schema found for {table}, skipping")
                        continue

                    column_names = [c.name for c in schema.columns]
                    data_tuples = []
                    substituted_columns = defaultdict(int)
                    for r in rows:
                        row_values = []
                        for col in schema.columns:
                            value = r.get(col.name)
                            if value is None and not col.nullable:
                                value = _default_for_column(col)
                                substituted_columns[col.name] += 1
                            row_values.append(value)
                        data_tuples.append(tuple(row_values))
                    for col_name, n in substituted_columns.items():
                        print(f"  Warning: {table}.{col_name} is non-nullable but {n} row(s) had no value -- substituted a default")

                    try:
                        client.insert(f"{ch_config.database}.{table}", data_tuples, column_names=column_names)
                        print(f"  Inserted {len(rows)} rows into {table}")
                    except Exception as e:
                        print(f"  Warning: failed to insert data into {table}: {e}")

                if missing_tables:
                    print("  Skipped unsupported events:")
                    for table_name, count in missing_tables.items():
                        print(f"    - {table_name}: {count} rows")
        _log("instrumentation", f"Instrumentation Agent done -- {len(schemas)} table(s), {len(ia.materialized_views)} MV(s)", stage_t0)

        # 4. Run AnalyticsAgent -- queries ClickHouse through the ClickHouse MCP
        # server (agents/analytics/mcp_client.py) when it's available, falling
        # back to the direct clickhouse_connect client otherwise.
        stage_t0 = time.monotonic()
        _log("analytics", "Running Analytics Agent...")
        mcp_client = ClickHouseMCPClient.connect_or_none(ch_config)
        _log("analytics", f"ClickHouse MCP {'connected' if mcp_client else 'unavailable -- querying ClickHouse directly'}")
        try:
            with tracer.trace_span("pipeline.analytics"):
                aa = AnalyticsAgent(
                    client=client,
                    database=ch_config.database,
                    context_agent=ca,
                    openrouter_config=or_config,
                    mcp_client=mcp_client,
                )
                spec_tables = list(ia.schemas.keys())
                spec_name = ia.last_analysis.feature_name if ia.last_analysis else spec_path.name
                pm_questions = _extract_pm_questions(ia.last_analysis.raw_spec_md) if ia.last_analysis else []
                insights = aa.run_full_analysis(spec_tables=spec_tables, pm_questions=pm_questions, spec_name=spec_name)
                md_out = spec_path / "insight_summary.md"
                aa.export_insights(md_out, format="markdown")
                print(f"  Saved {len(insights)} insights to {md_out}")
            _log("analytics", f"Analytics Agent done -- {len(insights)} insight(s)", stage_t0)

            # 4.5 Interactive Q&A -- only when run from a real terminal. Guarded on
            # isatty() so pytest/CI (piped/redirected stdin) never blocks forever
            # on input(); a human running `python main.py specs/...` directly gets
            # prompted for their own analytics questions before the dashboard is built.
            if sys.stdin.isatty():
                with tracer.trace_span("pipeline.analytics.interactive"):
                    aa.run_interactive()
                aa.export_insights(md_out, format="markdown")
                print(f"  Re-saved {len(insights)} insight(s) (including interactive ones) to {md_out}")
        finally:
            if mcp_client is not None:
                mcp_client.close()

        # 5. Build the dashboard
        stage_t0 = time.monotonic()
        _log("visualization", "Building Dashboard UI...")
        with tracer.trace_span("pipeline.visualization"):
            insights_dicts = [dataclasses.asdict(i) for i in insights]
            builder = DashboardBuilder(insights_dicts, spec_path.name)
            html_out = builder.build_html()
            dash_file = spec_path / "dashboard.html"
            dash_file.write_text(html_out)
            print(f"  Saved interactive dashboard to {dash_file}")
        _log("visualization", "Dashboard done", stage_t0)

        _log("pipeline", "Pipeline completed successfully!", pipeline_t0)

    except Exception as e:
        tracer.end_span(trace_id, status="error", error=str(e))
        _log("pipeline", f"Pipeline FAILED: {e}", pipeline_t0)
        raise
    finally:
        tracer.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atlys Agent Pipeline Orchestrator")
    parser.add_argument("spec_dir", help="Path to the feature spec directory")
    args = parser.parse_args()
    
    run_pipeline(args.spec_dir)
