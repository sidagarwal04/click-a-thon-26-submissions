"""atlys-mcp — agent-native tools for LibreChat / any MCP client.

Every tool returns a `trace_url` (empty string when Langfuse is unset) so a PM
conversation stays falsifiable. Aggregation stays in ClickHouse; the model never
sees raw event rows.

    python -m atlys_mcp                  # streamable-http on :8100/mcp
    ATLYS_MCP_PORT=8100 python -m atlys_mcp
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import agents.context_agent as context_agent  # noqa: E402
import metric_policy  # noqa: E402
import profile as profile_mod  # noqa: E402
import tracing  # noqa: E402
from ask import Session  # noqa: E402
from ch import CH  # noqa: E402

SPECS_DIR = HERE.parent / "specs"

INSTRUCTIONS = """\
You are talking to the Atlys agentic analytics layer, not a raw SQL console.

Rules:
1. For any product question about a feature, prefer `ask` — it pushes aggregation
   into ClickHouse and returns interpreted, numerically-grounded findings.
2. Never SELECT raw event rows. If you need schema/context, use `list_features`,
   `get_context`, `list_contradictions`, or `explain_metric`.
3. If `explain_metric` or `ask` reports a metric as DISPUTED, do NOT invent a
   single headline number. Report both labelled definitions.
4. Every tool response includes `trace_url`. Surface that link to the user.
"""

mcp = MCPServer(
    name="atlys",
    instructions=INSTRUCTIONS,
    version="0.1.0",
)


#: Native MCP capability hints. A client (LibreChat, Claude Desktop, an agent) can then
#: tell a safe read from a mutating call WITHOUT parsing our docstrings -- which is the
#: difference between a host that can auto-approve exploration and one that must prompt
#: for everything. Six of these only ever SELECT; `run_pipeline` proposes and executes
#: DDL, so it is the one that must be flagged.
_READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)

#: `run_pipeline` writes. It is NOT destructive (the approval gate stands between a
#: proposal and any executed DDL, and loads are idempotent by truncate-then-insert) and
#: NOT idempotent (a second call mints a new run_id and re-proposes a schema).
_MUTATES = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)


def _ch() -> CH:
    return CH()


def _norm(text: str) -> str:
    """Lowercase, and flatten every separator to a single space.

    Unifies the shapes the same field takes across a conversation and a schema:
    a PM writes `payment.latency_ms`, the column is `payment_latency_ms`, and both
    normalise to `payment latency ms`.
    """
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _feature_tokens(ch: CH) -> dict[str, set[str]]:
    """slug -> the tokens that could identify it: its own name parts + its columns.

    One query for every feature table's columns rather than one per table.
    """
    tables = [t for t in ch.list_tables() if t.startswith("f_") and t.endswith("_events")]
    if not tables:
        return {}
    quoted = ", ".join("'" + t.replace("'", "''") + "'" for t in tables)
    rows = ch.run_select(
        "SELECT table, name FROM system.columns "
        f"WHERE database = currentDatabase() AND table IN ({quoted})",
        max_rows=5000,
    )
    out: dict[str, set[str]] = {}
    for t in tables:
        slug = t[len("f_") : -len("_events")]
        out[slug] = set(p for p in slug.split("_") if p)
    for r in rows:
        slug = str(r["table"])[len("f_") : -len("_events")]
        if slug in out:
            out[slug].add(str(r["name"]))
    return out


def _rank_features(question: str, tokens_by_slug: dict[str, set[str]]) -> list[tuple[str, float]]:
    """Score each feature against the question, most likely first.

    A token is worth 1/(number of features carrying it): `event`, `timestamp` and
    `user_id` live on every table and so decide nothing, while a token unique to one
    feature decides it outright. That falls out of the data -- no feature is named
    anywhere in this file, so an unseen spec is ranked on exactly the same footing.
    """
    q = _norm(question)
    carriers: dict[str, int] = {}
    for toks in tokens_by_slug.values():
        for tok in toks:
            carriers[tok] = carriers.get(tok, 0) + 1

    ranked: list[tuple[str, float]] = []
    for slug, toks in tokens_by_slug.items():
        score = 0.0
        for tok in toks:
            if len(tok) < 3:
                continue  # 'os', 'id' -- too short to be evidence of anything
            if _norm(tok).strip() and _norm(tok) in q:
                score += 1.0 / carriers[tok]
        ranked.append((slug, round(score, 4)))
    ranked.sort(key=lambda kv: (-kv[1], kv[0]))
    return ranked


def _resolve_feature(ch: CH, question: str, feature_slug: str) -> tuple[str, str]:
    """(slug, how_it_was_chosen). Raises _Ambiguous rather than guessing.

    Silently defaulting to the first table is what this replaces: every unqualified
    question landed on whichever feature sorted first, so a question about one
    feature was answered -- fluently, and with correct numbers -- about a different
    one. The answer being internally consistent is exactly what made it dangerous.
    """
    tokens_by_slug = _feature_tokens(ch)
    if not tokens_by_slug:
        raise _Ambiguous("no instrumented feature tables found", [])

    if feature_slug.strip():
        want = feature_slug.strip().lower()
        if want in tokens_by_slug:
            return want, "explicit"
        near = [s for s in tokens_by_slug if want in s or s in want]
        if len(near) == 1:
            return near[0], f"explicit (matched {feature_slug!r})"
        raise _Ambiguous(
            f"feature_slug={feature_slug!r} matches {len(near)} features", sorted(tokens_by_slug)
        )

    ranked = _rank_features(question, tokens_by_slug)
    best, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    # Require a real signal AND a clear winner: a tie means the question genuinely
    # did not say, and picking either would be a coin flip presented as an answer.
    if best_score <= 0.0 or best_score <= runner_up:
        raise _Ambiguous(
            "the question does not identify which feature to analyse",
            sorted(tokens_by_slug),
            ranked=ranked[:5],
        )
    return best, f"inferred from the question (score {best_score} vs {runner_up} runner-up)"


class _Ambiguous(Exception):
    def __init__(self, why: str, available: list[str], ranked: list[tuple[str, float]] | None = None):
        super().__init__(why)
        self.why = why
        self.available = available
        self.ranked = ranked or []


def _pack(payload: dict[str, Any], *, trace_url: str = "") -> str:
    out = dict(payload)
    out["trace_url"] = trace_url or tracing.current_trace_url() or ""
    return json.dumps(out, default=str, indent=2)


@mcp.tool(annotations=_READ_ONLY)
def list_features() -> str:
    """List instrumented feature tables and their derived semantics summaries."""
    tracing.init_tracing()
    run_id = tracing.new_run_id()
    with tracing.trace_run(spec="mcp.list_features", run_id=run_id, context_version=0):
        ch = _ch()
        tables = [
            t
            for t in ch.list_tables()
            if t.startswith("f_") and t.endswith("_events")
        ]
        features: list[dict[str, Any]] = []
        for t in tables:
            slug = t[len("f_") : -len("_events")]
            spec_dirs = sorted(SPECS_DIR.glob(f"*_{slug}")) if SPECS_DIR.exists() else []
            # Also match dirs that end with the slug (numbered prefixes).
            if not spec_dirs and SPECS_DIR.exists():
                spec_dirs = [p for p in SPECS_DIR.iterdir() if p.is_dir() and slug in p.name]
            row: dict[str, Any] = {"slug": slug, "table": t}
            if spec_dirs:
                try:
                    spec = spec_dirs[0] / "spec.md"
                    events = spec_dirs[0] / "events.ndjson"
                    if spec.exists() and events.exists():
                        prof = profile_mod.profile_spec(spec, events)
                        sem = profile_mod.derive_semantics(prof, ch=ch)
                        row.update(
                            {
                                "entity_key": sem.entity_key,
                                "entity_key_confidence": sem.entity_key_confidence,
                                "ordered_steps": sem.ordered_steps,
                                "event_types": sem.event_types,
                                "partial_identity_columns": sem.partial_identity_columns,
                            }
                        )
                except Exception as exc:  # noqa: BLE001
                    row["semantics_error"] = f"{type(exc).__name__}: {exc}"
            features.append(row)
        tracing.flush()
        return _pack({"features": features, "count": len(features)})


@mcp.tool(annotations=_READ_ONLY)
def ask(question: str, feature_slug: str = "") -> str:
    """Answer a PM question about ONE instrumented feature, grounded in ClickHouse.

    `feature_slug` picks the feature (see `list_features`). Leave it empty only when
    the question itself names the feature or one of its fields -- it is then inferred,
    and the response reports which feature was chosen and why. If the question does
    not identify a feature, this returns an `error` listing the available ones instead
    of guessing: answering the wrong feature's data produces a fluent, correctly-
    computed, completely wrong answer.
    """
    tracing.init_tracing()
    ch = _ch()
    try:
        slug, resolved_by = _resolve_feature(ch, question, feature_slug)
    except _Ambiguous as exc:
        return _pack(
            {
                "error": f"could not determine which feature to analyse: {exc.why}",
                "available_features": exc.available,
                "ranked_guesses": [{"slug": s, "score": v} for s, v in exc.ranked],
                "next_step": "call ask again with feature_slug set to one of "
                "available_features, or use list_features first",
            }
        )

    spec_dirs = (
        [p for p in SPECS_DIR.iterdir() if p.is_dir() and slug in p.name]
        if SPECS_DIR.exists()
        else []
    )
    if not spec_dirs:
        return _pack({"error": f"no spec directory found for slug={slug}"})

    run_id = tracing.new_run_id()
    ctx = context_agent.snapshot(ch=ch, run_id=run_id, note="mcp.ask")
    with tracing.trace_run(spec=f"mcp.ask:{slug}", run_id=run_id, context_version=ctx.version):
        sess = Session(spec_dirs[0], ch)
        # Session reloads its own snapshot; reuse the warm path.
        ans, ungrounded = sess.answer(question)
        tracing.flush()
        return _pack(
            {
                "feature_slug": slug,
                "feature_resolved_by": resolved_by,
                "question": question,
                "answer": ans.answer,
                "confidence": ans.confidence,
                "numbers_cited": ans.numbers_cited,
                "ungrounded_numbers": ungrounded,
                "supporting_queries": ans.supporting_queries,
                "caveats": ans.caveats,
                "context_version": sess.ctx.version,
                "rows_scanned": sess.scanned,
            },
            trace_url=ans.__dict__.get("_trace_url", ""),
        )


@mcp.tool(annotations=_MUTATES)
def run_pipeline(spec_dir: str, rebuild: bool = False, confirm: bool = False) -> str:
    """Run the full instrumentation→context→analytics pipeline on a spec directory.

    WRITES. Proposes and executes ClickHouse DDL and loads data — the only tool here
    that is not read-only. Requires `confirm=true`; called without it, this returns a
    description of what would happen and does nothing.

    `spec_dir` is a path relative to Atlys/specs/ (e.g. `05_<feature>`) or an
    absolute path containing spec.md + events.ndjson. Returns run_id, artifacts path,
    and trace_url. This takes 20–90s.
    """
    tracing.init_tracing()
    path = Path(spec_dir)
    if not path.is_absolute():
        path = SPECS_DIR / spec_dir
    spec = path / "spec.md"
    events = path / "events.ndjson"
    if not spec.exists() or not events.exists():
        return _pack({"error": f"spec.md / events.ndjson not found under {path}"})

    # A chat model will call a tool because its name looked relevant. `read_only_hint`
    # lets a host warn, but nothing stops the call -- so the refusal lives server-side,
    # where it actually binds. Deliberately checked AFTER path validation so a
    # confirm-less call still reports a bad path rather than a misleading prompt.
    if not confirm:
        return _pack(
            {
                "status": "confirmation_required",
                "message": (
                    "This runs the full pipeline on "
                    f"{path.name}: it will propose ClickHouse DDL, and on approval "
                    "create/replace the feature table, load its events, and write "
                    "context + insight rows. Takes 20-90s. Call again with "
                    "confirm=true to proceed."
                ),
                "spec_dir": spec_dir,
                "rebuild": rebuild,
                "note": (
                    "DDL still passes through the human approval gate "
                    "(`pipeline_approvals`) before anything executes; confirm=true "
                    "starts the run, it does not pre-approve the schema."
                ),
            }
        )

    cmd = [
        sys.executable,
        str(HERE / "run_pipeline.py"),
        "--spec",
        str(spec),
        "--events",
        str(events),
    ]
    if rebuild:
        cmd.append("--rebuild")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HERE), timeout=900)
    # Best-effort: pull the latest run for this slug from pipeline_runs.
    # Numbered dirs are like NN_<feature_slug> — strip the numeric prefix.
    import re

    m = re.match(r"^\d+_(.+)$", path.name)
    slug = m.group(1) if m else path.name
    ch = _ch()
    rows = ch.run_select(
        f"SELECT run_id, stage, status, detail, trace_id, trace_url FROM pipeline_runs "
        f"WHERE feature_slug = '{slug}' ORDER BY ts DESC LIMIT 10"
    )
    run_id = rows[0]["run_id"] if rows else ""
    art = HERE / "artifacts" / "runs" / run_id if run_id else None
    trace = ""
    if art and (art / "trace_url.txt").exists():
        trace = (art / "trace_url.txt").read_text().strip()
    if not trace and rows:
        trace = str(rows[0].get("trace_url") or "")
    return _pack(
        {
            "exit_code": proc.returncode,
            "feature_slug": slug,
            "run_id": run_id,
            "artifacts_dir": str(art) if art else "",
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1000:],
            "recent_stages": rows,
        },
        trace_url=trace,
    )


@mcp.tool(annotations=_READ_ONLY)
def get_context(version: int = 0) -> str:
    """Return the living context layer as the prompt text agents actually consume.

    Pass version=0 for the latest snapshot.
    """
    tracing.init_tracing()
    run_id = tracing.new_run_id()
    with tracing.trace_run(spec="mcp.get_context", run_id=run_id, context_version=version):
        ch = _ch()
        snap = context_agent.snapshot(ch=ch, run_id=run_id, note="mcp.get_context")
        # Snapshot API returns latest; if a specific older version is requested, filter.
        entries = snap.entries
        if version and version != snap.version:
            entries = [e for e in entries if int(e.version) <= version]
        text = snap.as_prompt()
        if version and version != snap.version:
            text = (
                f"(requested v{version}; latest is v{snap.version} — showing entries "
                f"with version <= {version})\n\n"
            ) + "\n\n".join(
                f"### {e.entry_id}@v{e.version} ({e.kind})\n{e.body}" for e in entries[:80]
            )
        tracing.flush()
        return _pack(
            {
                "version": snap.version,
                "requested_version": version or snap.version,
                "entry_count": len(entries),
                "prompt": text[:20000],
            }
        )


@mcp.tool(annotations=_READ_ONLY)
def list_contradictions() -> str:
    """List verified contradictions in the context layer, each with proof SQL."""
    tracing.init_tracing()
    run_id = tracing.new_run_id()
    with tracing.trace_run(spec="mcp.list_contradictions", run_id=run_id, context_version=0):
        ch = _ch()
        rows = ch.run_select(
            "SELECT contradiction_id, kind, title, claim, evidence, "
            "verification_sql, verification_result, verified, severity, detected_by, "
            "entry_ids, detected_at "
            "FROM contradiction ORDER BY detected_at DESC LIMIT 100",
            max_rows=100,
        )
        # Deduplicate by (kind, title) keeping latest.
        seen: set[tuple[str, str]] = set()
        uniq: list[dict[str, Any]] = []
        for r in rows:
            key = (str(r.get("kind")), str(r.get("title")))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        tracing.flush()
        return _pack({"contradictions": uniq, "count": len(uniq)})


@mcp.tool(annotations=_READ_ONLY)
def explain_metric(name: str) -> str:
    """Look up the definition(s) in force for a metric. Reports DISPUTED when a
    definition_conflict is open — the answer LibreChat must surface for
    'what is our conversion rate?'."""
    tracing.init_tracing()
    run_id = tracing.new_run_id()
    with tracing.trace_run(spec="mcp.explain_metric", run_id=run_id, context_version=0):
        ch = _ch()
        ctx = context_agent.snapshot(ch=ch, run_id=run_id, note="mcp.explain_metric")
        info = metric_policy.explain_metric(ch, name, ctx)
        tracing.flush()
        return _pack(info)


@mcp.tool(annotations=_READ_ONLY)
def context_diff(from_version: int, to_version: int) -> str:
    """Summarise what changed in the context layer between two versions."""
    tracing.init_tracing()
    run_id = tracing.new_run_id()
    with tracing.trace_run(spec="mcp.context_diff", run_id=run_id, context_version=to_version):
        ch = _ch()
        rows = ch.run_select(
            f"SELECT ts, run_id, action, entry_id, from_version, to_version, summary, detail "
            f"FROM context_changelog "
            f"WHERE to_version > {int(from_version)} AND to_version <= {int(to_version)} "
            f"ORDER BY ts LIMIT 200",
            max_rows=200,
        )
        tracing.flush()
        return _pack(
            {
                "from_version": from_version,
                "to_version": to_version,
                "changes": rows,
                "count": len(rows),
            }
        )


@mcp.tool(annotations=_READ_ONLY)
def diagnose_segments(question: str = "", feature_slug: str = "") -> str:
    """Diagnose a feature's worst-converting segments AND the likeliest cause, in ONE query.

    This runs the hybrid retrieval-⨝-analytics query: in a single ClickHouse statement it
    ranks the known-issue whose meaning is nearest to `question` (semantic `cosineDistance`
    over the HNSW-indexed context embeddings) and CROSS JOINs it with a per-segment funnel
    conversion computed by `windowFunnel` over the feature table. Each returned row pairs a
    real segment metric with the semantically-closest documented issue — diagnosis and
    evidence together. It is the query no relational-only or vector-only store can express.
    Requires the vector index (built during a `ATLYS_CONTEXT_RETRIEVAL=vector` pipeline run).
    """
    tracing.init_tracing()
    run_id = tracing.new_run_id()
    with tracing.trace_run(spec="mcp.diagnose_segments", run_id=run_id, context_version=0):
        import vector_rag
        ch = _ch()
        try:
            slug, how = _resolve_feature(ch, question, feature_slug)
        except _Ambiguous as amb:
            return _pack({"error": "ambiguous_feature", "why": amb.why,
                          "available_features": amb.available, "ranked": amb.ranked})
        table = f"f_{slug}_events"
        # derive events/entity/segment generically from the feature's own semantics.
        # ALL of these carry safe defaults set here, so a profiling failure below degrades
        # gracefully rather than leaving any of them unbound (P1 fix — event_col too).
        first_event = last_event = None
        entity_col, segment_col, event_col = "user_id", "device_type", "event"
        spec_dirs = [p for p in SPECS_DIR.iterdir() if p.is_dir() and slug in p.name] \
            if SPECS_DIR.exists() else []
        if spec_dirs:
            try:
                prof = profile_mod.profile_spec(spec_dirs[0] / "spec.md",
                                                spec_dirs[0] / "events.ndjson")
                sem = profile_mod.derive_semantics(prof, ch=ch)
                steps = sem.ordered_steps or sem.event_types
                if steps:
                    first_event, last_event = steps[0], steps[-1]
                entity_col = sem.entity_key or entity_col
                event_col = sem.event_column or event_col
                if sem.segment_dims:
                    segment_col = sem.segment_dims[0]
            except Exception:  # noqa: BLE001 — fall back to generic defaults
                pass
        if not ch.table_exists(vector_rag.TABLE):
            return _pack({"error": "no_vector_index",
                          "hint": "run a pipeline with ATLYS_CONTEXT_RETRIEVAL=vector to build "
                                  "context_embeddings, then retry."})
        rows = vector_rag.hybrid_issue_funnel(
            ch, table, question or f"{slug} conversion drop by segment",
            event_col=event_col,
            entity_col=entity_col, segment_col=segment_col,
            first_event=first_event, last_event=last_event,
        )
        tracing.flush()
        return _pack({
            "feature": slug, "resolved_by": how, "table": table,
            "segment_col": segment_col, "funnel": [first_event, last_event],
            "diagnosis": rows,
            "note": "One ClickHouse query: semantic issue-retrieval CROSS JOIN windowFunnel "
                    "segment conversion. Worst-converting segment first; each paired with the "
                    "nearest documented known-issue by cosine distance.",
        })


def main() -> None:
    host = os.getenv("ATLYS_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("ATLYS_MCP_PORT", "8100"))
    tracing.init_tracing()
    mcp.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
