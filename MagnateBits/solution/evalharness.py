"""T8 evaluation harness.

    python -m evalharness --all --out out/eval

Two independent tables, built from what is actually on disk / in ClickHouse right now
-- nothing here re-runs the full LLM pipeline, and nothing here names a spec by literal
string. Specs are discovered by listing `../specs/*/` and `tools/mock_specs/*/` at
runtime, exactly like the pipeline itself discovers them.

Table 1 (known specs): reads `pipeline_runs`, `contradiction`, `insights_log` in
ClickHouse plus the `artifacts/runs/<run_id>/` files that `run_pipeline.py` wrote, and
independently RE-VERIFIES the one claim that is cheap and consequential to re-check:
whether the DDL that was actually proposed still dry-runs clean against the live
server. Everything else is read, not re-derived -- if a spec was never run, or was
abandoned mid-run, this table says so instead of inventing a result.

Table 2 (mock topologies): does NOT read history. It drives the deterministic path
(`profile_spec -> derive_semantics -> queries.templates.build_all`) fresh, builds a real
table via `agents.instrumentation.build_fallback_proposal` + `apply` (no LLM anywhere
in this path), and executes every generated query against that table. "Valid SQL" is
measured by running the query, not by inspecting the string.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import traceback
from pathlib import Path
from typing import Any

import agents.instrumentation as instrumentation
import ddl as ddl_mod
import profile as profile_mod
import queries.templates as templates
from agents import analytics
from ch import CH
from contracts import DDLProposal

HERE = Path(__file__).resolve().parent
SPECS_DIR = HERE.parent / "specs"
MOCK_SPECS_DIR = HERE / "tools" / "mock_specs"
ARTIFACTS_RUNS = HERE / "artifacts" / "runs"

PIPELINE_STAGE_ORDER = ("context.load", "instrumentation", "context.reconcile", "analytics", "report")


# --------------------------------------------------------------------------
# discovery -- no literal spec names anywhere in this file
# --------------------------------------------------------------------------


def discover_spec_dirs() -> list[Path]:
    if not SPECS_DIR.exists():
        return []
    return sorted(p for p in SPECS_DIR.iterdir() if p.is_dir() and (p / "spec.md").exists())


def discover_mock_dirs() -> list[Path]:
    if not MOCK_SPECS_DIR.exists():
        return []
    return sorted(p for p in MOCK_SPECS_DIR.iterdir() if p.is_dir() and (p / "spec.md").exists())


# --------------------------------------------------------------------------
# table 1: known specs, from run history
# --------------------------------------------------------------------------


def _fetch_pipeline_rows(ch: CH, slug: str) -> list[dict[str, Any]]:
    sql = (
        "SELECT run_id, ts, stage, status, context_version, detail "
        f"FROM pipeline_runs WHERE feature_slug = '{slug}' ORDER BY ts"
    )
    return ch.run_select(sql, max_rows=500)


def _best_run_id(rows: list[dict[str, Any]]) -> str | None:
    """Pick the run_id that got furthest through the pipeline; ties broken by recency.

    'Furthest' is measured by how many of the five named stages it logged at all --
    an abandoned run (process killed mid-flight) simply stops appearing in this table,
    so stage count is a faithful proxy for how much of the pipeline actually executed.
    """
    by_run: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_run.setdefault(str(r["run_id"]), []).append(r)
    if not by_run:
        return None

    def key(run_id: str) -> tuple[int, Any]:
        stages = {r["stage"] for r in by_run[run_id]}
        named = stages & set(PIPELINE_STAGE_ORDER)
        last_ts = max(r["ts"] for r in by_run[run_id])
        return (len(named), last_ts)

    return max(by_run, key=key)


def _stage_status(rows: list[dict[str, Any]], run_id: str, stage: str) -> dict[str, Any] | None:
    matches = [r for r in rows if str(r["run_id"]) == run_id and r["stage"] == stage]
    return matches[-1] if matches else None


def _run_classification(rows: list[dict[str, Any]], run_id: str) -> str:
    report = _stage_status(rows, run_id, "report")
    analytics_stage = _stage_status(rows, run_id, "analytics")
    if report is None:
        # max() by TIMESTAMP, not by stage-name string: stage names don't sort in
        # pipeline order ("instrumentation" > "context.reconcile" alphabetically, even
        # though it runs first), so a plain max() of the names silently reports the
        # wrong "abandoned after" stage whenever a run gets past instrumentation.
        own = [r for r in rows if str(r["run_id"]) == run_id]
        last = max(own, key=lambda r: r["ts"])["stage"] if own else "(none)"
        return f"INCOMPLETE -- abandoned after `{last}`, no report/artifacts stage recorded"
    if report["status"] == "ok" and analytics_stage is not None and analytics_stage["status"] == "ok":
        return "CLEAN"
    reason = analytics_stage["detail"] if analytics_stage is not None else report["detail"]
    return f"DEGRADED -- {reason[:160]}"


def _wall_clock_s(rows: list[dict[str, Any]], run_id: str) -> float | None:
    ts = [r["ts"] for r in rows if str(r["run_id"]) == run_id]
    if len(ts) < 2:
        return None
    return (max(ts) - min(ts)).total_seconds()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _verify_ddl(ch: CH, proposal_json: dict[str, Any] | None) -> str:
    """Re-run dry_run() against the LIVE server for the proposal that was actually used.

    This is a real check, not a replay of a logged status: the proposal is re-parsed
    from the artifact and re-submitted to ClickHouse right now.
    """
    if proposal_json is None:
        return "N/A -- no proposal.json on disk to verify"
    try:
        proposal = DDLProposal.model_validate(proposal_json)
    except Exception as exc:  # noqa: BLE001
        return f"FAIL -- artifact does not parse as a DDLProposal: {exc}"
    try:
        ok, err = ddl_mod.dry_run(proposal, ch)
    except Exception as exc:  # noqa: BLE001
        return f"FAIL -- dry_run raised: {exc}"
    return "PASS (re-verified now)" if ok else f"FAIL -- {err[:200]}"


def _mv_summary(proposal_json: dict[str, Any] | None) -> str:
    if proposal_json is None:
        return "N/A -- no proposal"
    mvs = proposal_json.get("materialized_views") or []
    if not mvs:
        return "no MV proposed"
    parts = []
    for mv in mvs:
        factor = mv.get("reduction_factor")
        kept = mv.get("kept")
        state = "not measured" if factor is None else ("KEPT" if kept else "DROPPED")
        factor_txt = f"{factor}x" if factor is not None else "?"
        parts.append(f"{mv.get('name', '?')}: {state} ({factor_txt})")
    return "; ".join(parts)


def _contradiction_count(ch: CH, run_id: str) -> str:
    if not run_id:
        return "N/A -- no run"
    sql = (
        "SELECT count(DISTINCT contradiction_id) AS n, "
        "countDistinctIf(contradiction_id, verified = 1) AS n_verified "
        f"FROM contradiction WHERE run_id = '{run_id}'"
    )
    rows = ch.run_select(sql)
    if not rows:
        return "0"
    n, nv = int(rows[0]["n"]), int(rows[0]["n_verified"])
    return f"{n} ({nv} verified)"


def _insight_count(ch: CH, run_id: str, analytics_ok: bool) -> str:
    if not run_id:
        return "N/A -- no run"
    rows = ch.run_select(f"SELECT count() AS n FROM insights_log WHERE run_id = '{run_id}'")
    n = int(rows[0]["n"]) if rows else 0
    if n == 0 and not analytics_ok:
        return "0 (analytics stage did not complete)"
    return str(n)


_SCAN_RE = re.compile(
    r"Scanned\s+([\d,]+)\s+rows(?:\s*/\s*([\d.]+\s*\w+))?\s+in ClickHouse;\s+sent\s+([\d,]+)\s+rows to the model",
    re.IGNORECASE,
)


def _scan_from_report(insight_report_path: Path | None) -> tuple[str, str]:
    """(rows scanned vs sent, measured-or-estimated) parsed from the written report."""
    if insight_report_path is None or not insight_report_path.exists():
        return "N/A -- no insight_report.md", "N/A"
    text = insight_report_path.read_text(encoding="utf-8", errors="replace")
    m = _SCAN_RE.search(text)
    if not m:
        return "N/A -- report has no scan line (degraded run, zero findings)", "N/A"
    scanned, size, sent = m.group(1), m.group(2), m.group(3)
    scan_txt = f"{scanned} rows" + (f" / {size}" if size else "") + f" scanned -> {sent} rows sent"
    measured = "measured, not estimated" in text
    return scan_txt, ("measured" if measured else "estimated")


def build_known_spec_row(ch: CH, spec_dir: Path) -> dict[str, Any]:
    spec_md = spec_dir / "spec.md"
    events = spec_dir / "events.ndjson"
    slug = profile_mod.feature_slug_for(spec_md)

    # Deterministic, LLM-free re-derivation, independent of whether the LLM pipeline
    # ever ran for this spec at all -- so the "what would the source say about this
    # spec's shape" column is populated even for a spec the sweep never touched.
    archetype = "profiling failed"
    try:
        prof = profile_mod.profile_spec(spec_md, events)
        sem = profile_mod.derive_semantics(prof, ch=ch)
        archetype = (
            f"entity_key=`{sem.entity_key}` (confidence {sem.entity_key_confidence:.2f}); "
            f"{len(sem.ordered_steps)}-step funnel; "
            f"disconnected_events={len(sem.disconnected_event_types)}; "
            f"partial_identity_cols={len(sem.partial_identity_columns)}"
        )
    except Exception as exc:  # noqa: BLE001
        archetype = f"profiling failed: {exc}"

    pipeline_rows = _fetch_pipeline_rows(ch, slug)
    run_id = _best_run_id(pipeline_rows)

    proposal_json = None
    insight_report_path = None
    if run_id:
        run_dir = ARTIFACTS_RUNS / run_id
        if (run_dir / "proposal.json").exists():
            proposal_json = _load_json(run_dir / "proposal.json")
        if (run_dir / "insight_report.md").exists():
            insight_report_path = run_dir / "insight_report.md"

    analytics_stage = _stage_status(pipeline_rows, run_id, "analytics") if run_id else None
    analytics_ok = bool(analytics_stage and analytics_stage["status"] == "ok")

    ddl_valid = _verify_ddl(ch, proposal_json)
    mv_summary = _mv_summary(proposal_json)
    contradictions = _contradiction_count(ch, run_id) if run_id else "N/A -- no run recorded"
    insights = _insight_count(ch, run_id, analytics_ok) if run_id else "N/A -- no run recorded"
    scan_txt, measured_flag = _scan_from_report(insight_report_path)
    classification = _run_classification(pipeline_rows, run_id) if run_id else "NOT RUN -- no pipeline_runs entry for this spec"
    wall_clock = _wall_clock_s(pipeline_rows, run_id) if run_id else None

    return {
        "spec": spec_dir.name,
        "feature_slug": slug,
        "run_id": run_id or "",
        "archetype_entity_key": archetype,
        "ddl_valid": ddl_valid,
        "mv_summary": mv_summary,
        "contradictions_found": contradictions,
        "insight_count": insights,
        "rows_scanned_vs_sent": scan_txt,
        "measured_or_estimated": measured_flag,
        "degraded_or_clean": classification,
        "wall_clock_s": f"{wall_clock:.1f}" if wall_clock is not None else "N/A",
    }


# --------------------------------------------------------------------------
# table 2: mock topologies, driven fresh through the deterministic path
# --------------------------------------------------------------------------


def _topology_verdict(n_ok: int, n_total: int) -> str:
    """Verdict from a query-execution tally, pulled out of `build_mock_topology_row` so
    it's unit-testable without ClickHouse.

    `n_total == 0` is deliberately NOT a pass: build_all() legitimately produces nothing
    for a topology with no correlatable/measurable columns, but it could equally be a
    template-coverage gap for this shape -- the harness cannot tell those apart, so it
    must not report the green "PASS" either reading would wrongly imply. Every other
    QuerySpec reaching this point already survived build_all()'s own TemplateError
    guards (degenerate combinations are skipped before being returned, not surfaced as
    failures here), so any execution failure among them is a real template/SQL bug on
    this topology's shape -- there is no count of failures that should read as PASS.
    """
    if n_total == 0:
        return (
            "REVIEW -- zero queries generated; could be a legitimate topology (nothing "
            "correlatable/measurable) or a template-coverage gap, not distinguishable "
            "automatically"
        )
    if n_ok == n_total:
        return "PASS"
    return f"FAIL -- {n_total - n_ok}/{n_total} generated queries did not run cleanly (see flags)"


def build_mock_topology_row(ch: CH, topo_dir: Path) -> dict[str, Any]:
    name = topo_dir.name
    spec_md = topo_dir / "spec.md"
    events = topo_dir / "events.ndjson"
    row: dict[str, Any] = {
        "topology": name,
        "entity_key_confidence": "",
        "funnel_steps_derived": "",
        "valid_sql_fraction": "",
        "flagged_undetermined": "",
        "verdict": "",
    }
    flags: list[str] = []
    try:
        prof = profile_mod.profile_spec(spec_md, events)
        sem = profile_mod.derive_semantics(prof, ch=ch)
    except Exception as exc:  # noqa: BLE001
        row["entity_key_confidence"] = "n/a"
        row["funnel_steps_derived"] = "n/a"
        row["valid_sql_fraction"] = "0/0"
        row["flagged_undetermined"] = f"profile_spec/derive_semantics raised: {exc}"
        row["verdict"] = "FAIL -- crashed before producing anything"
        return row

    row["entity_key_confidence"] = f"`{sem.entity_key}` @ {sem.entity_key_confidence:.2f}"
    row["funnel_steps_derived"] = f"{len(sem.ordered_steps)} steps: {' -> '.join(sem.ordered_steps)}"

    if sem.entity_key_confidence < 0.99:
        flags.append(f"entity key confidence {sem.entity_key_confidence:.2f} < 1.0")
    if prof.entity_key_rationale:
        flags.append(f"entity_key_rationale: {prof.entity_key_rationale}")
    if prof.funnel_derivation:
        flags.append(f"funnel_derivation: {prof.funnel_derivation}")
    if sem.disconnected_event_types:
        flags.append(f"disconnected_event_types={sem.disconnected_event_types}")
    if sem.partial_identity_columns:
        flags.append(f"partial_identity_columns={sem.partial_identity_columns}")

    # Build a real table via the deterministic (no-LLM) fallback, then execute every
    # query build_all() generates for it, for real, against that table.
    try:
        proposal = instrumentation.build_fallback_proposal(prof)
        ok, err = ddl_mod.dry_run(proposal, ch)
        if not ok:
            row["valid_sql_fraction"] = "0/0"
            row["flagged_undetermined"] = " | ".join(flags) if flags else "(none)"
            row["verdict"] = f"FAIL -- fallback DDL does not dry-run clean: {err[:200]}"
            return row
        instrumentation.apply(proposal, ch, events, rebuild=True)
    except Exception as exc:  # noqa: BLE001
        row["valid_sql_fraction"] = "0/0"
        row["flagged_undetermined"] = " | ".join(flags) if flags else "(none)"
        row["verdict"] = f"FAIL -- table build raised: {exc}"
        return row

    # Query generation uses the SAME semantics derive_semantics() produced above --
    # not proposal.semantics -- per the specified deterministic path.
    try:
        specs = templates.build_all(sem)
    except Exception as exc:  # noqa: BLE001
        row["valid_sql_fraction"] = "0/0"
        row["flagged_undetermined"] = " | ".join(flags) if flags else "(none)"
        row["verdict"] = f"FAIL -- build_all raised: {exc}"
        return row

    if not specs:
        flags.append("build_all produced zero queries for this topology")
        row["valid_sql_fraction"] = "0/0 (no queries generated)"
        row["flagged_undetermined"] = " | ".join(flags)
        row["verdict"] = _topology_verdict(0, 0)
        return row

    runs = analytics.execute(specs, ch)
    n_ok = sum(1 for r in runs if not r.error)
    n_total = len(runs)
    row["valid_sql_fraction"] = f"{n_ok}/{n_total}"
    for r in runs:
        if r.error:
            flags.append(f"query `{r.name}` failed: {r.error[:160]}")
    row["flagged_undetermined"] = " | ".join(flags) if flags else "(none stated)"
    row["verdict"] = _topology_verdict(n_ok, n_total)
    return row


# --------------------------------------------------------------------------
# table 3: insight groundedness, RE-VERIFIED (not replayed)
# --------------------------------------------------------------------------

#: A finding whose asserted number cannot be found in the queries it cites is not an
#: insight, it is a plausible sentence. `grounding.py` already demotes these at write
#: time; this table re-derives the verdict from scratch so the guard itself is audited
#: rather than trusted -- the same stance Table 1 takes by re-running `dry_run()`.
DISPUTED_PENALTY = 0.5


def _reproducible_sql(ch: CH, slug: str) -> dict[str, str]:
    """{query_name: SQL} rebuilt from the deterministic templates for this feature.

    Query results are not persisted, so re-verification needs the SQL back. Templates
    are a pure function of derived semantics, so it can be regenerated exactly -- and
    if the template set has since drifted, the name simply won't resolve and the
    finding is reported as unverifiable rather than silently passed.
    """
    spec_dirs = [p for p in SPECS_DIR.iterdir() if p.is_dir() and slug in p.name] if SPECS_DIR.exists() else []
    if not spec_dirs:
        return {}
    try:
        prof = profile_mod.profile_spec(spec_dirs[0] / "spec.md", spec_dirs[0] / "events.ndjson")
        sem = profile_mod.derive_semantics(prof, ch=ch)
        return {q.name: q.sql for q in templates.build_all(sem, max_segment_dims=6)}
    except Exception:  # noqa: BLE001 - an unbuildable spec is a Table 1 problem, not this one
        return {}


def build_groundedness_row(ch: CH, spec_dir: Path) -> dict[str, Any]:
    """Re-execute each finding's cited queries and re-check its asserted number."""
    import grounding
    import metric_policy
    from contracts import Finding, QueryRun

    slug = profile_mod.feature_slug_for(spec_dir / "spec.md")
    row: dict[str, Any] = {
        "spec": spec_dir.name, "findings": 0, "grounded": 0, "unverifiable": 0,
        "policy_notices": 0, "groundedness": "n/a", "disputed_leak": "n/a",
        "composite": "n/a",
    }

    rows = ch.run_select(
        "SELECT payload FROM insights_log WHERE feature_slug = "
        f"'{slug}' AND run_id = (SELECT argMax(run_id, ts) FROM insights_log "
        f"WHERE feature_slug = '{slug}') ",
        max_rows=200,
    )
    if not rows:
        row["groundedness"] = "NOT RUN -- no findings recorded for this spec"
        return row

    findings: list[Finding] = []
    for r in rows:
        try:
            findings.append(Finding.model_validate(json.loads(r["payload"])))
        except Exception:  # noqa: BLE001
            continue
    if not findings:
        row["groundedness"] = "ERROR -- findings recorded but none parse as Finding"
        return row
    row["findings"] = len(findings)

    sql_by_name = _reproducible_sql(ch, slug)
    cache: dict[str, QueryRun] = {}

    def run_of(name: str) -> QueryRun | None:
        if name in cache:
            return cache[name]
        sql = sql_by_name.get(name)
        if not sql:
            return None
        try:
            res = ch.run_select(sql, max_rows=200)
        except Exception:  # noqa: BLE001
            return None
        cache[name] = QueryRun(name=name, sql=sql, rows=len(res), duration_ms=0, result=res)
        return cache[name]

    grounded = unverifiable = policy = 0
    for f in findings:
        # A metric_policy notice is a REFUSAL, not a data claim: it deliberately cites
        # no query and asserts no number. Scoring it as ungrounded would report "this
        # spec's insights were unfounded" when what actually happened is that the guard
        # fired correctly -- exactly backwards. Counted separately instead.
        if "suppressed by metric_policy" in " ".join(f.caveats or []):
            policy += 1
            continue
        if not f.supporting_queries:
            # Citing nothing IS ungrounded by definition, and grounding.py treats it so.
            continue
        resolved = {n: run_of(n) for n in f.supporting_queries}
        if any(q is None for q in resolved.values()):
            # Judging a claim against only the subset of its citations we could rebuild
            # would fail findings whose number lives in the query that didn't resolve.
            # Report it as unverifiable rather than guess.
            unverifiable += 1
            continue
        ok, _ = grounding.check_finding(f, {n: q for n, q in resolved.items() if q})
        grounded += int(ok)

    row["grounded"] = grounded
    row["unverifiable"] = unverifiable
    row["policy_notices"] = policy
    scored = len(findings) - unverifiable - policy
    frac = (grounded / scored) if scored else 0.0
    if scored == 0:
        row["groundedness"] = (
            f"n/a -- no data-claim findings ({policy} policy notice(s), "
            f"{unverifiable} unverifiable)"
        )
    else:
        row["groundedness"] = f"{frac:.2f} ({grounded}/{scored} re-verified)" + (
            f", {unverifiable} unverifiable" if unverifiable else ""
        ) + (f", {policy} policy notice(s)" if policy else "")

    # Did an unqualified number for a DISPUTED metric escape into a finding?
    leak = ""
    try:
        conflicts = metric_policy.load_open_conflicts(ch)
        for f in findings:
            blob = " ".join([f.headline or "", f.metric or "", f.metric_definition_used or ""])
            if metric_policy.mentions_subject(blob, "conversion") and conflicts:
                if not (f.metric_definition_used and "metric.conversion" in f.metric_definition_used):
                    if not metric_policy.is_qualified(blob, conflicts[0]):
                        leak = f"LEAK: {f.headline[:60]}"
                        break
    except Exception as exc:  # noqa: BLE001
        leak = f"check failed: {exc}"
    row["disputed_leak"] = leak or "none"
    penalty = DISPUTED_PENALTY if leak.startswith("LEAK") else 1.0
    row["composite"] = "n/a" if scored == 0 else f"{frac * penalty:.2f}"
    return row


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

TABLE3_COLS = [
    ("spec", "Spec"),
    ("findings", "Findings"),
    ("grounded", "Re-verified grounded"),
    ("unverifiable", "Unverifiable (SQL not reproducible)"),
    ("policy_notices", "Policy notices (excluded)"),
    ("groundedness", "Groundedness"),
    ("disputed_leak", "DISPUTED-metric leak"),
    ("composite", "Composite"),
]

TABLE1_COLS = [
    ("spec", "Spec"),
    ("feature_slug", "Feature slug"),
    ("run_id", "Run id"),
    ("archetype_entity_key", "Archetype / entity key derived"),
    ("ddl_valid", "DDL valid (dry-run, re-verified now)"),
    ("mv_summary", "MV keep/drop (measured reduction)"),
    ("contradictions_found", "Contradictions found"),
    ("insight_count", "Insight count"),
    ("rows_scanned_vs_sent", "Rows scanned vs sent to model"),
    ("measured_or_estimated", "Measured or estimated"),
    ("degraded_or_clean", "Degraded or clean"),
    ("wall_clock_s", "Wall clock (s)"),
]

TABLE2_COLS = [
    ("topology", "Topology"),
    ("entity_key_confidence", "Entity key + confidence"),
    ("funnel_steps_derived", "Funnel steps derived"),
    ("valid_sql_fraction", "Fraction of generated queries valid SQL"),
    ("flagged_undetermined", "Flagged as undetermined / ambiguous"),
    ("verdict", "Verdict"),
]


def _md_table(rows: list[dict[str, Any]], cols: list[tuple[str, str]]) -> str:
    def esc(v: Any) -> str:
        return str(v).replace("\n", " ").replace("|", "\\|")

    header = "| " + " | ".join(h for _, h in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(esc(r.get(k, "")) for k, _ in cols) + " |")
    return "\n".join(lines)


def _write_csv(path: Path, rows: list[dict[str, Any]], cols: list[tuple[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([h for _, h in cols])
        for r in rows:
            w.writerow([r.get(k, "") for k, _ in cols])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="run both tables (currently the only mode)")
    ap.add_argument("--out", type=Path, default=HERE / "out" / "eval")
    args = ap.parse_args(argv)

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    ch = CH()

    t0 = time.perf_counter()
    spec_rows: list[dict[str, Any]] = []
    for spec_dir in discover_spec_dirs():
        print(f"[table1] {spec_dir.name} ...")
        try:
            spec_rows.append(build_known_spec_row(ch, spec_dir))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            spec_rows.append(
                {
                    "spec": spec_dir.name,
                    "feature_slug": "",
                    "run_id": "",
                    "archetype_entity_key": f"HARNESS ERROR: {exc}",
                    "ddl_valid": "ERROR", "mv_summary": "ERROR",
                    "contradictions_found": "ERROR", "insight_count": "ERROR",
                    "rows_scanned_vs_sent": "ERROR", "measured_or_estimated": "ERROR",
                    "degraded_or_clean": "HARNESS ERROR", "wall_clock_s": "ERROR",
                }
            )
    t1 = time.perf_counter()

    mock_rows: list[dict[str, Any]] = []
    for topo_dir in discover_mock_dirs():
        print(f"[table2] {topo_dir.name} ...")
        try:
            mock_rows.append(build_mock_topology_row(ch, topo_dir))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            mock_rows.append(
                {
                    "topology": topo_dir.name,
                    "entity_key_confidence": "ERROR", "funnel_steps_derived": "ERROR",
                    "valid_sql_fraction": "0/0",
                    "flagged_undetermined": f"harness error: {exc}",
                    "verdict": "FAIL -- harness error",
                }
            )
    t2 = time.perf_counter()

    ground_rows: list[dict[str, Any]] = []
    for spec_dir in discover_spec_dirs():
        print(f"[table3] {spec_dir.name} ...")
        try:
            ground_rows.append(build_groundedness_row(ch, spec_dir))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            ground_rows.append(
                {
                    "spec": spec_dir.name, "findings": "ERROR", "grounded": "ERROR",
                    "unverifiable": "ERROR", "groundedness": f"HARNESS ERROR: {exc}",
                    "disputed_leak": "ERROR", "composite": "ERROR",
                }
            )
    t3 = time.perf_counter()

    _write_csv(out_dir / "results.csv", spec_rows, TABLE1_COLS)
    _write_csv(out_dir / "mock_topologies.csv", mock_rows, TABLE2_COLS)
    _write_csv(out_dir / "groundedness.csv", ground_rows, TABLE3_COLS)

    md = [
        "# T8 eval harness results",
        "",
        f"Table 1 built in {t1 - t0:.1f}s. Table 2 in {t2 - t1:.1f}s. "
        f"Table 3 in {t3 - t2:.1f}s.",
        "",
        "## Known specs (from `../specs/*/`, read from run history in ClickHouse + artifacts on disk)",
        "",
        _md_table(spec_rows, TABLE1_COLS),
        "",
        "## Mock topologies (`tools/mock_specs/*/`, run fresh through the deterministic path just now)",
        "",
        _md_table(mock_rows, TABLE2_COLS),
        "",
        "## Insight groundedness (re-verified now, not replayed)",
        "",
        "Each finding's cited queries are regenerated from the deterministic templates, "
        "re-executed against ClickHouse, and its asserted number re-checked with "
        "`grounding.check_finding`. This audits the grounding guard itself rather than "
        "trusting the verdict it recorded at write time -- the same stance Table 1 takes "
        "by re-running `dry_run()`. A finding citing no query counts against the score "
        "(that is ungrounded by definition); a finding whose query name no longer "
        "resolves is reported as *unverifiable* and excluded from the denominator rather "
        "than silently passed. `Composite` = groundedness x "
        f"{DISPUTED_PENALTY} if an unqualified DISPUTED-metric number leaked, else x1.",
        "",
        _md_table(ground_rows, TABLE3_COLS),
        "",
    ]
    (out_dir / "results.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nwrote {out_dir / 'results.md'}")
    print(f"wrote {out_dir / 'results.csv'}")
    print(f"wrote {out_dir / 'mock_topologies.csv'}")
    print(f"wrote {out_dir / 'groundedness.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
