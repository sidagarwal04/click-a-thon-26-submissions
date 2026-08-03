"""CLI entry point: python -m prism_ch <command>."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import Settings
from .db import cluster_nodes, wait_for_clickhouse
from .mcp_server import serve_mcp
from .schema import bootstrap
from .trace_check import run_trace_check
from .ui import serve_ui


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


def cmd_info(settings: Settings) -> int:
    client = wait_for_clickhouse(settings)
    nodes = cluster_nodes(client, settings.cluster)
    if not nodes:
        print(f"cluster {settings.cluster!r} is not configured on this server", file=sys.stderr)
        return 1
    print(json.dumps({"cluster": settings.cluster, "nodes": nodes}, indent=2, default=str))
    return 0


def cmd_bootstrap(settings: Settings) -> int:
    client = wait_for_clickhouse(settings)
    bootstrap(client, settings)
    return 0


def cmd_health(settings: Settings) -> int:
    client = wait_for_clickhouse(settings, timeout=10.0)
    print(client.command("SELECT version()"))
    return 0


def cmd_serve(settings: Settings) -> int:
    """Serve the browser UI."""
    wait_for_clickhouse(settings)
    return serve_ui(settings)


def cmd_instrument(
    settings: Settings,
    spec_path: str | None,
    *,
    execute: bool = True,
    brief: str | None = None,
    events_path: str | None = None,
    name: str | None = None,
    sample_pct: float = 15.0,
) -> int:
    """Run the Instrumentation Agent over a spec."""
    from .agents import InstrumentationAgent, load_spec
    from .tracing import init_tracing, pipeline_run, shutdown

    spec = load_spec(
        spec_path,
        brief=brief,
        events_path=events_path,
        name=name,
        sample_fraction=sample_pct / 100,
    )
    if not spec.brief and not spec.events:
        print(
            "nothing to instrument - pass a spec directory, or --brief and --events",
            file=sys.stderr,
        )
        return 1
    if spec.groups:
        print(
            f"{len(spec.groups)} user action(s) declared in the spec; "
            f"profiling {sample_pct:g}% of each, loading all rows:",
            file=sys.stderr,
        )
        for g in spec.groups:
            print(f"  {g.action:<32} {len(g.events):>6} of {g.total:<7} sampled", file=sys.stderr)
        if spec.undeclared_actions:
            print(f"  undeclared in spec: {spec.undeclared_actions}", file=sys.stderr)
    elif spec.sampled:
        print(
            f"profiling on a sample: {spec.event_count:,} of {spec.events_total:,} "
            f"events ({sample_pct:g}%) - the full file loads into the table once it exists",
            file=sys.stderr,
        )

    init_tracing(settings)
    client = wait_for_clickhouse(settings)
    try:
        with pipeline_run("instrument", spec_name=spec.name, surface="cli") as run:
            agent = InstrumentationAgent(settings, client)
            result = agent.run(spec, execute=execute)
            run.metric("schema.tables", len(result.proposal.tables))
            run.metric("schema.repairs", agent.repairs)
            run.metric("schema.lint_issues", agent.lint_issues)
            run.metric("schema.executed", 1 if execute else 0)
            run.metric("schema.rows_loaded", sum(r.loaded for r in result.load_results))
            run.output(result.proposal.as_dict())

            print(f"\nrun_id: {run.run_id}   trace: {run.trace_id or '(tracing off)'}\n")
            for sql in result.statements:
                print(sql + ";\n")
            if result.proposal.notes:
                print(f"-- notes: {result.proposal.notes}")

            # Every statement that actually reached the server, including the
            # ALTERs the agent decided on by itself.
            if result.executed_statements:
                print("\n-- executed:")
                for st in result.executed_statements:
                    mark = "ok " if st.ok else "ERR"
                    head = " ".join(st.sql.split())[:110]
                    print(f"   [{mark}] {head}")
                    if st.error:
                        print(f"          {st.error}")

            for load in result.load_results:
                status = (
                    f"loaded {load.loaded}/{load.attempted}"
                    if not load.error
                    else f"failed: {load.error}"
                )
                extra = f"  (+{', '.join(load.columns_added)})" if load.columns_added else ""
                print(f"-- {load.table}: {status}{extra}")
            if result.empty_actions:
                print(f"-- declared but no rows in the data: {', '.join(result.empty_actions)}")
            if result.undeclared_actions:
                print(f"-- in the data but not declared: {result.undeclared_actions}")
    finally:
        shutdown()
    return 0


def cmd_context(settings: Settings, base_context: str | None) -> int:
    """Refresh the context layer from the base document and the live database."""
    from .agents import ContextAgent
    from .tracing import init_tracing, pipeline_run, shutdown

    init_tracing(settings)
    client = wait_for_clickhouse(settings)
    try:
        with pipeline_run("context", spec_name="context-refresh", surface="cli") as run:
            agent = ContextAgent(settings, client)
            version, delta, insight_report = agent.run(base_context)
            snapshot = agent.store.load(version)
            run.output(snapshot.as_dict())

            print(f"\ncontext v{version}   run_id: {run.run_id}")
            print(f"entries: {len(snapshot.entries)}   issues: {len(snapshot.issues)}\n")

            if delta.from_version:
                print(
                    f"diff v{delta.from_version} -> v{delta.to_version}: "
                    f"+{len(delta.added)} -{len(delta.removed)} ~{len(delta.changed)}"
                )
            for issue in sorted(snapshot.issues, key=lambda i: i.severity):
                print(f"  [{issue.severity:<6}] {issue.kind:<13} {issue.subject}")
                print(f"           {issue.detail}")
            if agent.last_analytics_run_id:
                print(
                    f"\nauto-analysis run {agent.last_analytics_run_id}: "
                    f"{len(insight_report.insights)} insight(s), "
                    f"{insight_report.queries_run} queries"
                )
    finally:
        shutdown()
    return 0


def cmd_context_log(settings: Settings) -> int:
    """Print the context changelog."""
    from .agents import ContextAgent

    client = wait_for_clickhouse(settings)
    agent = ContextAgent(settings, client)
    for row in agent.store.history():
        print(
            f"v{row['version']:<4} {row['created_at']:<26} "
            f"{row['source']:<15} {row['entry_count']:>4} entries  {row['summary']}"
        )
    return 0


def cmd_analyze(settings: Settings, focus: str | None) -> int:
    """Run the Analytics Agent and print a PM-facing summary."""
    from .agents import AnalyticsAgent
    from .tracing import init_tracing, pipeline_run, shutdown

    init_tracing(settings)
    client = wait_for_clickhouse(settings)
    try:
        with pipeline_run("analyze", spec_name="analytics", surface="cli") as run:
            agent = AnalyticsAgent(settings, client)
            report = agent.run(focus)
            confidences = [i.confidence for i in report.insights]
            run.metric("analysis.insights", len(report.insights))
            run.metric("analysis.queries", report.queries_run)
            run.metric("analysis.context_version", report.context_version)
            if confidences:
                run.metric("analysis.confidence_avg", round(sum(confidences)/len(confidences), 3))
            run.output(report.as_dict())

            print(f"\nrun_id: {run.run_id}   trace: {run.trace_id or '(tracing off)'}")
            print(f"context v{report.context_version}   {report.queries_run} queries\n")
            if report.summary:
                print(report.summary + "\n")
            for n, i in enumerate(
                sorted(report.insights, key=lambda x: -x.confidence), start=1
            ):
                print(f"{n}. [{i.cut}] {i.headline}   (confidence {i.confidence:.2f})")
                if i.detail:
                    print(f"   {i.detail}")
                print(f"   why: {i.why}")
                if i.context_refs:
                    print(f"   context: {', '.join(i.context_refs)}")
                if i.recommendation:
                    print(f"   next: {i.recommendation}")
                print()
            if not report.insights:
                print("no insights produced - check the queries in the trace")
    finally:
        shutdown()
    return 0


COMMANDS = {
    "serve": cmd_serve,
    "bootstrap": cmd_bootstrap,
    "info": cmd_info,
    "health": cmd_health,
    "trace-check": run_trace_check,
    "context-log": cmd_context_log,
    "mcp": serve_mcp,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prism_ch", description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=sorted([*COMMANDS, "instrument", "context", "analyze"]),
        help="serve: run the browser UI (default); bootstrap: apply schema; "
        "info: print cluster layout; health: print server version; "
        "trace-check: emit one demo trace; instrument: run the Instrumentation "
        "Agent over a spec directory; context: refresh the context layer; "
        "context-log: print the context changelog; analyze: run the Analytics "
        "Agent; mcp: serve the agents over MCP",
    )
    parser.add_argument(
        "spec", nargs="?", help="spec directory or spec.md (for `instrument`)"
    )
    parser.add_argument("--brief", help="feature description, instead of a spec.md")
    parser.add_argument("--focus", help="steer the analysis (for `analyze`)")
    parser.add_argument("--events", help="path to sample events (NDJSON or JSON array)")
    parser.add_argument("--name", help="table/spec name; inferred from the path otherwise")
    parser.add_argument(
        "--sample-pct",
        type=float,
        default=15.0,
        help="%% of each user action's rows to profile (for `instrument`; default 15). "
        "Every row is loaded regardless - this only bounds what the LLM reasons from",
    )
    parser.add_argument(
        "--base-context",
        help="path to base_context.md (for `context`); omit to refresh from the database only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the generated DDL but do not create the real tables",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    _configure_logging(settings.log_level)

    if args.command == "instrument":
        if not (args.spec or args.brief or args.events):
            parser.error("instrument needs a spec directory, or --brief/--events")
        return cmd_instrument(
            settings,
            args.spec,
            execute=not args.dry_run,
            brief=args.brief,
            events_path=args.events,
            name=args.name,
            sample_pct=args.sample_pct,
        )

    if args.command == "context":
        return cmd_context(settings, args.base_context)

    if args.command == "analyze":
        return cmd_analyze(settings, args.focus)

    return COMMANDS[args.command](settings)


if __name__ == "__main__":
    raise SystemExit(main())
