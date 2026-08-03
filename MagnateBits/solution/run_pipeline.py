"""THE entrypoint. Feature spec in -> instrumented table, fresh context, insights out.

    python run_pipeline.py --spec <path/to/spec.md> --events <path/to/events.ndjson>

Five stages, all inside ONE Langfuse trace so a judge reads a single reasoning chain:

  1. context.load        -> snapshot vN
  2. instrumentation     -> profile -> propose DDL -> lint -> dry-run -> execute -> load -> measure MVs
  3. context.reconcile   -> absorb the new table, run contradiction checks, bump to vN+1
  4. analytics           -> plan -> execute -> interpret, USING vN+1 (not the vN loaded in step 1)
  5. report              -> artifacts on disk + trace URL

Step 4 reading a *newer* snapshot than step 1 is the point: that is the context-freshness
evidence, and the trace records the version each LLM call actually consumed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

import agents.analytics as analytics
import agents.context_agent as context_agent
import agents.instrumentation as instrumentation
import ddl as ddl_mod
import bakeoff
import grounding
import llm
import profile as profile_mod
import report as report_mod
import tracing
from ch import CH
from contracts import InsightReport, PipelineResult, StageStatus

HERE = Path(__file__).parent
HOUSE_RULES = HERE / "house_rules.md"
ARTIFACTS = HERE / "artifacts" / "runs"

# The five stages, in order. Every run reports a status for every one of them.
PIPELINE_STAGES = ("context.load", "instrumentation", "context.reconcile", "analytics", "report")

# Exit codes: 0 clean, 1 hard failure (nothing written), 2 degraded (artifacts written),
# 3 declined (a real proposal existed and dry-ran clean, but was not approved).
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_DEGRADED = 2
EXIT_DECLINED = 3

# How long a non-interactive run (stdin not a TTY -- e.g. launched as a subprocess by
# the Streamlit console) waits for someone to approve/reject via `pipeline_approvals`
# before giving up. Bounded so an abandoned run cleans itself up rather than hanging.
APPROVAL_POLL_S = 2
DEFAULT_APPROVAL_TIMEOUT_S = 1800

con = Console()


def _write_approval(
    ch: CH, run_id: str, table_name: str, ddl_sql: str, rationale: str,
    decision: str, decided_by: str,
) -> None:
    """Append-only, like context_entry_log: never UPDATE, just write a later row for
    the same run_id. Whoever resolves it first wins -- the CLI's stdin prompt and the
    UI's Approve/Reject buttons are racing to write the SAME table, not coordinating."""
    ch.insert_rows(
        "pipeline_approvals",
        [
            {
                "run_id": run_id,
                "ts": datetime.now(timezone.utc).replace(tzinfo=None),
                "table_name": table_name,
                "ddl_sql": ddl_sql,
                "rationale": rationale,
                "decision": decision,
                "decided_by": decided_by,
            }
        ],
    )


def _poll_approval(ch: CH, run_id: str, timeout_s: int) -> tuple[bool, str]:
    """Block (via sleep, not stdin) until a decision row lands or the timeout hits."""
    waited = 0
    while waited < timeout_s:
        rows = ch.run_select(
            "SELECT decision, decided_by FROM pipeline_approvals "
            f"WHERE run_id = '{run_id}' ORDER BY ts DESC LIMIT 1",
            max_rows=1,
        )
        if rows and rows[0]["decision"] != "pending":
            return rows[0]["decision"] == "approved", str(rows[0]["decided_by"]) or "unknown"
        time.sleep(APPROVAL_POLL_S)
        waited += APPROVAL_POLL_S
    return False, f"timed out after {timeout_s}s waiting for a decision"


def _resolve_approval(
    ch: CH, run_id: str, proposal, *, auto_yes: bool, timeout_s: int,
) -> tuple[bool, str]:
    """Show the proposed schema, then get a yes/no from wherever one can come from:
    --yes, an interactive terminal, or (for a non-interactive caller, e.g. the
    Streamlit console's subprocess) polling pipeline_approvals until someone decides.

    Nothing downstream of this has run yet -- the DDL dry-ran clean but was never
    executed, so a decline is cheap: no table, no load, nothing to undo.
    """
    ddl_sql = "\n".join(ddl_mod.render(proposal))
    rationale = json.dumps(proposal.rationale, indent=2, default=str)
    _write_approval(ch, run_id, proposal.table_name, ddl_sql, rationale, "pending", "")

    con.rule("[bold]Schema proposed — review before anything is executed[/bold]")
    con.print(f"[cyan]table[/cyan] {proposal.table_name}  ({len(proposal.columns)} columns, "
              f"{len(proposal.materialized_views)} materialized view(s))")
    for k, v in proposal.rationale.items():
        con.print(f"  [dim]{k}[/dim]: {str(v)[:240]}")
    con.print(ddl_sql)

    if auto_yes:
        _write_approval(ch, run_id, proposal.table_name, ddl_sql, rationale, "approved", "auto (--yes)")
        con.print("[green]auto-approved[/green] (--yes)")
        return True, "auto (--yes)"

    if sys.stdin.isatty():
        ans = con.input("\nProceed with this schema? [y/N] ").strip().lower()
        approved = ans in ("y", "yes")
        _write_approval(
            ch, run_id, proposal.table_name, ddl_sql, rationale,
            "approved" if approved else "rejected", "cli",
        )
        return approved, "cli"

    con.print(
        f"[yellow]waiting[/yellow] up to {timeout_s}s for a decision written to "
        f"`pipeline_approvals` (run_id={run_id[:12]}) -- e.g. via the Streamlit console"
    )
    approved, decided_by = _poll_approval(ch, run_id, timeout_s)
    if not approved and decided_by.startswith("timed out"):
        # _poll_approval only reads; the row it left behind is still "pending" forever
        # otherwise, which would misreport a long-dead run as still awaiting a decision
        # to anyone (including the UI) who queries this table later.
        _write_approval(ch, run_id, proposal.table_name, ddl_sql, rationale, "timed_out", decided_by)
    return approved, decided_by


def _stage(ch: CH, run_id: str, slug: str, stage: str, status: str, version: int, detail: str = "") -> None:
    """Every stage lands in pipeline_runs so the dashboard has a timeline."""
    try:
        ch.insert_rows(
            "pipeline_runs",
            [
                {
                    "run_id": run_id,
                    "ts": datetime.now(timezone.utc).replace(tzinfo=None),
                    "feature_slug": slug,
                    "stage": stage,
                    "status": status,
                    "context_version": version,
                    "trace_id": tracing.current_trace_id(),
                    "trace_url": tracing.current_trace_url(),
                    "detail": detail[:2000],
                }
            ],
        )
    except Exception:  # observability must never break the run
        pass


def _degraded_insight(
    slug: str, run_id: str, version: int, stage: str, error: str
) -> InsightReport:
    """A minimal, valid InsightReport for a run whose analytics stage died.

    report.render_markdown requires an InsightReport; `findings` may be empty. Writing
    this instead of nothing is the whole point of degraded mode: the schema, the DDL
    rationale and the context diff are already paid for and still true.
    """
    return InsightReport(
        feature_slug=slug,
        run_id=run_id,
        context_version=version,
        summary=(
            f"DEGRADED RUN -- the `{stage}` stage failed with: {error}. "
            "Instrumentation and context reconciliation completed before the failure, so the "
            "schema, the DDL rationale and the context diff in this document are real. "
            "No analytics findings were produced for this run."
        ),
        findings=[],
        caveats=[
            f"`{stage}` stage failed: {error}",
            "Zero findings here means the analysis did not run, NOT that the feature is healthy.",
        ],
        unanswered_questions=[
            f"Every question this run set out to answer is unanswered: `{stage}` did not complete."
        ],
        trace_url=tracing.current_trace_url(),
    )


def _fallback_artifacts(run_dir: Path, result: PipelineResult, error: str) -> dict[str, Path]:
    """Last resort: report.write_artifacts itself raised. Write each piece independently
    so one bad renderer cannot take the whole directory down."""
    run_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    pieces = [
        ("proposal.json", lambda: json.dumps(result.proposal.model_dump(mode="json"), indent=2)),
        (
            "semantics.json",
            lambda: json.dumps(result.proposal.semantics.model_dump(mode="json"), indent=2),
        ),
        ("schema.sql", lambda: report_mod.render_schema_sql(result)),
        ("context_diff.md", lambda: report_mod.render_context_diff_markdown(result)),
        ("trace_url.txt", lambda: (result.insight.trace_url or result.trace_url or "") + "\n"),
    ]
    for name, render in pieces:
        try:
            path = run_dir / name
            path.write_text(render(), encoding="utf-8")
            written[name] = path
        except Exception:
            continue
    stage_lines = "\n".join(f"| `{s.stage}` | {s.status} | {s.detail} |" for s in result.stages)
    text = (
        f"# Insight report - {result.feature_slug} (DEGRADED)\n\n"
        f"Run `{result.run_id}`.\n\n"
        f"The report renderer itself failed: {error}\n\n"
        "| stage | status | detail |\n| --- | --- | --- |\n"
        f"{stage_lines}\n\n"
        f"Summary from the run: {result.insight.summary}\n"
    )
    try:
        path = run_dir / "insight_report.md"
        path.write_text(text, encoding="utf-8")
        written["insight_report.md"] = path
    except Exception:
        pass
    return written


def _log_insights(ch: CH, run_id: str, slug: str, insight) -> None:
    rows = [
        {
            "run_id": run_id,
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "feature_slug": slug,
            "headline": f.headline[:500],
            "metric": f.metric,
            "confidence": float(f.confidence.score),
            "severity": f.severity,
            "context_refs": list(f.context_refs),
            "payload": f.model_dump_json(),
        }
        for f in insight.findings
    ]
    if rows:
        try:
            ch.insert_rows("insights_log", rows)
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Atlys agentic analytics pipeline")
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--events", required=True, type=Path)
    ap.add_argument("--rebuild", action="store_true", help="drop the feature table first")
    ap.add_argument("--out", type=Path, default=ARTIFACTS)
    ap.add_argument(
        "--run-id",
        default="",
        help="use this run_id instead of generating one -- lets a caller (e.g. the "
        "Streamlit console) poll pipeline_runs for this exact id from the moment it "
        "launches the subprocess, instead of scraping stdout for the id this print",
    )
    ap.add_argument(
        "--yes", "-y", action="store_true",
        help="auto-approve the proposed schema instead of asking -- skips the review "
        "gate between dry-run and execute/load; use for CI/regression sweeps, not demos",
    )
    ap.add_argument(
        "--approval-timeout", type=int, default=DEFAULT_APPROVAL_TIMEOUT_S,
        help=f"seconds a non-interactive run waits for a pipeline_approvals decision "
        f"before giving up (default {DEFAULT_APPROVAL_TIMEOUT_S})",
    )
    ap.add_argument(
        "--instructions", default="",
        help="G6 human-in-the-loop steering: free-text operator guidance for the schema "
        "designer this run (e.g. 'retain 24 months', 'partition daily', 'treat plan as the "
        "primary cut', 'PII-mask client_ip'). Injected as authoritative-but-lint-bounded "
        "constraints — cannot produce invalid DDL or an id-leading ORDER BY.",
    )
    args = ap.parse_args()

    t0 = time.perf_counter()
    ch = CH()
    run_id = args.run_id or tracing.new_run_id()
    house_rules = HOUSE_RULES.read_text()

    # -- 1. context.load ----------------------------------------------------
    ctx_before = context_agent.snapshot(ch=ch, run_id=run_id, note="pre-run load")
    slug = profile_mod.feature_slug_for(args.spec, None)

    con.rule(f"[bold]{slug}[/bold]  run {run_id[:12]}")
    con.print(f"llm      : {llm.backend_info()}")
    con.print(f"tracing  : {'on' if tracing.tracing_enabled() else 'OFF (no Langfuse keys)'}")
    con.print(f"context  : loaded v{ctx_before.version} ({len(ctx_before.entries)} entries)\n")

    # Every stage starts as "not reached" and is overwritten as it happens, so a run that
    # dies mid-flight still describes itself accurately instead of going silent.
    stages: dict[str, StageStatus] = {
        name: StageStatus(stage=name, status="skipped", detail="did not run")
        for name in PIPELINE_STAGES
    }

    def mark(stage: str, status: str, version: int, detail: str = "") -> None:
        """Record a stage outcome to pipeline_runs AND to the in-memory status block."""
        _stage(ch, run_id, slug, stage, status, version, detail)
        key = stage if stage in stages else next(
            (s for s in PIPELINE_STAGES if stage.startswith(s + ".")), None
        )
        if key:
            stages[key] = StageStatus(stage=key, status=status, detail=detail[:400])

    with tracing.trace_run(spec=slug, run_id=run_id, context_version=ctx_before.version):
        mark("context.load", "ok", ctx_before.version, f"{len(ctx_before.entries)} entries")

        # -- 2. instrumentation --------------------------------------------
        with tracing.span("instrumentation", spec=str(args.spec)):
            prof = profile_mod.profile_spec(args.spec, args.events)
            con.print(f"[cyan]profile[/cyan]  {prof.row_count} rows, {len(prof.event_types)} event types, "
                      f"entity_key={prof.entity_key}, funnel={' -> '.join(prof.derived_funnel)}")

            proposal = instrumentation.propose_ddl(
                prof, house_rules, ctx_before, ch, instructions=args.instructions)
            violations = ddl_mod.lint(proposal)
            if violations:
                con.print(f"[yellow]lint[/yellow]     {len(violations)} violation(s): {violations[:3]}")
            ok, err = ddl_mod.dry_run(proposal, ch)
            if not ok:
                mark("instrumentation.dry_run", "error", ctx_before.version, err)
                con.print(f"[red]dry-run failed[/red] {err[:300]}")
                # Nothing downstream can be built without a table: no PipelineResult is
                # constructible (it requires a LoadResult and a ContextDiff), so this is a
                # hard stop rather than a degraded run.
                return EXIT_FAILED
            mark("instrumentation.dry_run", "ok", ctx_before.version, "clean")

            # Gate: the DDL is proven runnable but NOTHING has been executed yet -- no
            # table, no data, nothing to roll back. This is deliberately the last
            # possible moment before that changes.
            mark("instrumentation.awaiting_approval", "pending", ctx_before.version,
                 f"{proposal.table_name}: {len(proposal.columns)} columns, "
                 f"{len(proposal.materialized_views)} MV(s)")
            approved, decided_by = _resolve_approval(
                ch, run_id, proposal, auto_yes=args.yes, timeout_s=args.approval_timeout,
            )
            mark(
                "instrumentation.approval",
                "ok" if approved else "declined",
                ctx_before.version,
                f"{'approved' if approved else 'declined'} by {decided_by}",
            )
            if not approved:
                con.print(f"[red]declined[/red] schema not approved ({decided_by}); "
                          "nothing executed or loaded")
                return EXIT_DECLINED

            load = instrumentation.apply(proposal, ch, args.events, rebuild=args.rebuild)
            con.print(f"[cyan]load[/cyan]     {proposal.table_name}: {load.rows_inserted}/{load.rows_read} rows, "
                      f"{load.rejected} rejected")
            for line in instrumentation.mv_report(proposal):
                con.print(f"           {line}")

            # T3: measure ORDER BY against a timestamp-first straw-man. Numbers go into
            # rationale["order_by"]; failure here must not kill the run.
            bake = bakeoff.run(proposal, ch)
            con.print(f"[cyan]{bakeoff.report_line(bake)}[/cyan]")

            mark("instrumentation", "ok" if not load.rejected else "warn",
                 ctx_before.version, f"{load.rows_inserted} rows into {proposal.table_name}")

        semantics = proposal.semantics

        # -- 3. context.reconcile ------------------------------------------
        with tracing.span("context.reconcile", table=proposal.table_name):
            diff = context_agent.reconcile(
                ch=ch, new_tables=[proposal.table_name], proposal=proposal,
                run_id=run_id, note=f"instrumented {slug}",
            )
            con.print(f"[cyan]context[/cyan]  v{diff.from_version} -> v{diff.to_version}: "
                      f"+{len(diff.added)} added, {len(diff.updated)} updated, "
                      f"{len(diff.contradictions)} contradiction(s)")
            for c in diff.contradictions[:4]:
                con.print(f"           [yellow]{c.kind}[/yellow] {c.title[:88]}")
            mark("context.reconcile", "ok", diff.to_version,
                 f"{len(diff.contradictions)} contradictions")

        # -- 4. analytics: MUST use the post-reconcile snapshot -------------
        # DEGRADED MODE. By this point the run already holds prof, proposal, load and diff --
        # all of the expensive work. An exception from here on must not throw that away: it
        # is recorded, and the run still writes every artifact it can.
        ctx_after = ctx_before
        insight = None
        ungrounded: list[str] = []
        degraded = False
        try:
            ctx_after = context_agent.snapshot(ch=ch, run_id=run_id, note="post-reconcile")
            if ctx_after.version == ctx_before.version:
                con.print(f"[yellow]note[/yellow]     context version unchanged (v{ctx_after.version})")
            else:
                con.print(f"[green]fresh[/green]    analytics will reason on v{ctx_after.version}, "
                          f"not the v{ctx_before.version} loaded at start")

            # Opt-in: keep the vector-RAG embedding index in sync with the fresh context.
            # Only runs when ATLYS_CONTEXT_RETRIEVAL=vector; never breaks the run.
            try:
                import vector_rag
                if vector_rag.enabled():
                    n_emb = vector_rag.reindex(ch, ctx_after)
                    con.print(f"[green]rag[/green]      embedded {n_emb} context entries "
                              f"(cosineDistance/HNSW retrieval enabled)")
            except Exception as _rag_exc:  # noqa: BLE001
                con.print(f"[yellow]rag[/yellow]      reindex skipped: {_rag_exc}")

            with tracing.span("analytics", context_version=ctx_after.version):
                plan = analytics.plan_queries(prof, semantics, ctx_after, ch)
                runs = analytics.execute(plan, ch)
                failed = [r for r in runs if r.error]
                con.print(f"[cyan]queries[/cyan]  {len(runs)} executed, {len(failed)} failed")

                cols = analytics.describe_table(ch, semantics.table_fqn)
                quality = analytics.probe_quality(ch, semantics, cols)
                insight = analytics.interpret(
                    runs, ctx_after, prof, semantics,
                    run_id=run_id, quality=quality, exec_stats=analytics.last_exec_stats(),
                )
                insight.trace_url = tracing.current_trace_url()
                insight.context_version = ctx_after.version

            # -- 4b. numeric grounding: no number survives that its own cited query
            #        did not actually return. Deterministic, not a second LLM call.
            with tracing.span("analytics.verify_grounding", findings=len(insight.findings)):
                insight, ungrounded = grounding.verify(insight, runs)
                if ungrounded:
                    con.print(f"[red]grounding[/red] {len(ungrounded)}/{len(insight.findings)} "
                              f"finding(s) demoted — number absent from cited queries")
                    for n in ungrounded:
                        con.print(f"           {n[:110]}")
                else:
                    con.print(f"[green]grounding[/green] all {len(insight.findings)} findings "
                              f"matched their cited query results")
            mark("analytics", "ok", ctx_after.version,
                 f"{len(insight.findings)} findings, {len(ungrounded)} ungrounded")
        except Exception as exc:  # noqa: BLE001 -- degraded mode is the whole point
            degraded = True
            err = f"{type(exc).__name__}: {exc}"
            con.print(f"[red]analytics failed[/red] {err[:400]}")
            con.print("[yellow]degraded[/yellow] continuing to report stage; "
                      "schema + context artifacts will still be written")
            traceback.print_exc()
            mark("analytics", "error", ctx_after.version, f"{err} | {traceback.format_exc()[-600:]}")
            insight = _degraded_insight(slug, run_id, ctx_after.version, "analytics", err)

        # -- 5. report ------------------------------------------------------
        result = PipelineResult(
            run_id=run_id, feature_slug=slug, trace_url=tracing.current_trace_url(),
            profile=prof, proposal=proposal, load=load, context_diff=diff, insight=insight,
            # The report stage is, by construction, whatever wrote the file you are reading;
            # a failure after this point is recorded to pipeline_runs and printed, and the
            # fallback writer restates it in the artifact itself.
            stages=[
                *[s for k, s in stages.items() if k != "report"],
                StageStatus(stage="report", status="ok",
                            detail="this document and its sibling artifacts"),
            ],
            degraded=degraded,
        )
        paths: dict[str, Path] = {}
        try:
            paths = report_mod.write_artifacts(result, args.out / run_id)
            context_agent.render_markdown(ch=ch, run_id=run_id)
            _log_insights(ch, run_id, slug, insight)
            mark("report", "ok" if not degraded else "warn", ctx_after.version,
                 str(paths.get("insight_report.md", paths.get("insight_report", ""))))
        except Exception as exc:  # noqa: BLE001
            degraded = True
            err = f"{type(exc).__name__}: {exc}"
            con.print(f"[red]report failed[/red] {err[:400]}")
            traceback.print_exc()
            mark("report", "error", ctx_after.version, f"{err} | {traceback.format_exc()[-600:]}")
            result.degraded = True
            result.stages = list(stages.values())
            paths = _fallback_artifacts(args.out / run_id, result, err)
            con.print(f"[yellow]degraded[/yellow] wrote {len(paths)} artifact(s) the long way")

    tracing.flush()

    # -- summary ------------------------------------------------------------
    t = Table(show_header=False, box=None, pad_edge=False)
    t.add_row("table", f"{proposal.table_name}  ({load.rows_inserted} rows, {load.rejected} rejected)")
    t.add_row("order by", ", ".join(proposal.order_by))
    t.add_row("context", f"v{diff.from_version} -> v{diff.to_version}, {len(diff.contradictions)} contradictions")
    t.add_row("findings", str(len(insight.findings)))
    scanned_bytes = int(getattr(insight, "bytes_scanned_in_clickhouse", 0) or 0)
    t.add_row(
        "scanned",
        f"{insight.rows_scanned_in_clickhouse:,} rows in ClickHouse"
        + (f" / {scanned_bytes / 1024 ** 2:.1f} MB (system.query_log)" if scanned_bytes else ""),
    )
    t.add_row("sent to LLM", f"{insight.rows_sent_to_llm:,} rows")
    t.add_row("artifacts", str(args.out / run_id))
    t.add_row("trace", insight.trace_url or "(tracing disabled)")
    t.add_row("elapsed", f"{time.perf_counter() - t0:.1f}s")
    t.add_row("stages", "  ".join(f"{s.stage}={s.status}" for s in stages.values()))
    con.print()
    con.rule("[bold green]done[/bold green]" if not degraded else "[bold red]done (DEGRADED)[/bold red]")
    con.print(t)

    for f in insight.findings[:5]:
        con.print(f"\n[bold]{f.severity.upper()}[/bold] {f.headline}")
        con.print(f"  why : {f.why[:180]}")
        con.print(f"  conf: {f.confidence.score:.2f}  refs: {', '.join(f.context_refs) or '-'}")

    if degraded:
        broken = [s.stage for s in stages.values() if s.status == "error"]
        con.print(f"\n[red]DEGRADED[/red] stage(s) {', '.join(broken) or '?'} failed. "
                  f"Artifacts were still written to {args.out / run_id}; exiting {EXIT_DEGRADED} "
                  "so CI notices.")
        return EXIT_DEGRADED
    return EXIT_OK


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        con.print("[red]pipeline failed[/red]")
        traceback.print_exc()
        raise SystemExit(1)
