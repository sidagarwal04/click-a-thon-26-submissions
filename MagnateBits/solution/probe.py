"""Run the Analytics Agent against the 8 PRE-EXISTING production tables.

    python probe.py                 # the 4 standard probe prompts, traced
    python probe.py --question "…"  # one ad-hoc question
    python probe.py --list          # show the standard prompts

Everything else in this project analyses a *feature spec*: one table, an `event`
discriminator column, semantics profiled from raw NDJSON. The pre-existing tables are
shaped the other way -- one table per event type, eight of them, no spec to profile --
so the funnel that matters spans tables rather than rows.

Rather than write a second set of templates for that shape (which would double the
surface area and mean the probe outputs were produced by different code than everything
else), this presents the eight tables to the existing stack as one event stream:

    CREATE VIEW base_events AS
        SELECT <30 shared envelope columns>, 'destination_card_clicked' AS event FROM ...
        UNION ALL ... (x8)

The 30 columns are the ones genuinely common to all eight tables, computed at runtime
rather than listed here, so a table gaining or losing a column changes the view instead
of breaking it. With that view in place every T01-T12 template, the confidence scoring,
the numeric grounding and the metric policy apply unchanged -- the probe answers are
produced by exactly the same machinery as the feature-spec answers, which is the point.

The per-table columns (`amount`, `scroll_depth_pct`, `search_term`, ...) are deliberately
NOT in the view: they exist on one table each, so as union columns they would be null
for 7/8 of the stream, and the empty-string-counted-as-a-value trap this codebase
guards against everywhere else would apply to all of them at once. Questions needing
those go to the individual tables.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

import tracing
from ask import Session, show
from ch import CH
from contracts import FeatureSemantics, MeasureSpec

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "probe"

#: The four prompts every team is asked to run against the existing tables, verbatim
#: from the track's submission guidelines. Deliberately open-ended -- surfacing what
#: matters is the system's job, so they are not rewritten into something easier.
STANDARD_PROBES: list[str] = [
    "Analyze the existing funnel and surface the most important issues, with the why.",
    "Where are we losing conversions, and for which segments (device / geo / destination)?",
    "Are there any regressions or trends over the last quarter?",
    "Is anything in the base context wrong, stale, or self-contradictory?",
]

VIEW = "base_events"

#: NOT a hardcoded funnel. The first version of this file listed the *documented*
#: product funnel (landing -> search -> card -> application -> ...) and the data
#: flatly contradicted it: of the 299,659 users with both, `search_typed` precedes
#: `landing_page_scrolled` in 299,659 cases and follows it in ZERO. Every downstream
#: `windowFunnel` then reported 0 entities past step 1 -- not "nobody converted", but
#: "this funnel cannot be satisfied by construction", which reads like a catastrophic
#: drop-off rather than a wrong assumption.
#:
#: So the order is derived the same way `profile.py` derives it for a feature spec:
#: pairwise per-entity timestamp precedence, ranked by Copeland score. Assuming the
#: order was the one thing this project says never to do, and it was wrong.

con = Console()


def base_tables(ch: CH) -> list[str]:
    """The 8 production tables: everything that isn't generated or an ops table."""
    generated = ("f_", "agg_", "mv_", "context_", "pipeline_", "insights_",
                 "contradiction", "schema_", VIEW)
    return sorted(t for t in ch.list_tables() if not t.startswith(generated))


def shared_columns(ch: CH, tables: list[str]) -> list[str]:
    """Columns present on EVERY base table, computed rather than hardcoded."""
    per: list[set[str]] = []
    for t in tables:
        rows = ch.run_select(
            "SELECT name FROM system.columns WHERE database = currentDatabase() "
            f"AND table = '{t}'",
            max_rows=500,
        )
        per.append({str(r["name"]) for r in rows})
    return sorted(set.intersection(*per)) if per else []


def column_types(ch: CH, table: str) -> dict[str, str]:
    return {
        str(r["name"]): str(r["type"])
        for r in ch.run_select(
            "SELECT name, type FROM system.columns WHERE database = currentDatabase() "
            f"AND table = '{table}'",
            max_rows=500,
        )
    }


def ensure_view(ch: CH, tables: list[str], cols: list[str]) -> str:
    """(Re)create the union view. Cheap, and keeps it honest if a table changed.

    UUID columns are projected as String. The legacy tables type `id` as `UUID`, and
    every template in this project guards identity columns with `col != ''` because the
    house rules forbid `Nullable` and default identities to the empty string -- but
    ClickHouse cannot compare a UUID to `''`, so `t10_data_quality` fails outright
    against these tables. Casting here rather than special-casing the templates keeps
    that guard working, and it matches the rule the generated schemas already follow:
    ids are `String`, never `UUID` (the raw ids are 32-char hex, which `UUID` rejects).
    """
    types = column_types(ch, tables[0]) if tables else {}
    projected = []
    for c in cols:
        t = types.get(c, "")
        if "UUID" in t:
            projected.append(f"toString(`{c}`) AS `{c}`")
        else:
            projected.append(f"`{c}`")
    select_list = ", ".join(projected)
    parts = [
        f"SELECT {select_list}, '{t}' AS event FROM {ch.database}.{t}" for t in tables
    ]
    sql = f"CREATE OR REPLACE VIEW {ch.database}.{VIEW} AS\n" + "\nUNION ALL\n".join(parts)
    ch.execute_ddl(sql)
    return sql


def derive_funnel(ch: CH, events: list[str]) -> tuple[list[str], str]:
    """Order the event types by pairwise per-entity timestamp precedence (Copeland).

    For every pair, count the entities whose first A precedes their first B and vice
    versa; the type that wins more pairwise contests ranks earlier. This is the same
    signal `profile.py::_copeland` uses on a feature spec's raw events, computed in
    ClickHouse here because these events live in tables rather than NDJSON.

    Returns (order, rationale) -- the rationale is recorded so the ordering is
    reviewable rather than magic.
    """
    import itertools

    wins = {e: 0 for e in events}
    decisive: list[str] = []
    for a, b in itertools.combinations(events, 2):
        r = ch.run_select(
            "SELECT countIf(ta > toDateTime(0) AND tb > toDateTime(0) AND ta < tb) AS a_first, "
            "countIf(ta > toDateTime(0) AND tb > toDateTime(0) AND tb < ta) AS b_first FROM ("
            f"SELECT minIf(timestamp, event = '{a}') AS ta, "
            f"minIf(timestamp, event = '{b}') AS tb "
            f"FROM {ch.database}.{VIEW} GROUP BY user_id)",
            max_rows=1,
        )[0]
        af, bf = int(r["a_first"]), int(r["b_first"])
        if af > bf:
            wins[a] += 1
        elif bf > af:
            wins[b] += 1
        total = af + bf
        if total:
            decisive.append(f"{a}<{b}: {af}/{total}" if af > bf else f"{b}<{a}: {bf}/{total}")
    order = sorted(events, key=lambda e: (-wins[e], e))
    rationale = (
        "derived by pairwise per-entity timestamp precedence (Copeland); wins: "
        + ", ".join(f"{e}={wins[e]}" for e in order)
    )
    return order, rationale


def base_semantics(ch: CH, tables: list[str], cols: list[str]) -> FeatureSemantics:
    """FeatureSemantics for the union view, so every existing template applies.

    Funnel order is DERIVED from the data (see `derive_funnel`), never assumed.
    """
    present, funnel_rationale = derive_funnel(ch, tables)
    counts = {
        str(r["event"]): int(r["n"])
        for r in ch.run_select(
            f"SELECT event, count() AS n FROM {ch.database}.{VIEW} GROUP BY event",
            max_rows=50,
        )
    }
    # Segment dims: low-cardinality shared columns that are genuinely segmentable.
    candidates = ["device_type", "os", "geoip_country_code", "destination", "city",
                  "client_lib", "app_version", "language", "funnel_type", "citizenship"]
    segment_dims = [c for c in candidates if c in cols]
    measures = [
        MeasureSpec(column=c, kind="count")
        for c in ("co_travelers",) if c in cols
    ]
    return FeatureSemantics(
        feature_slug="base_tables",
        table_fqn=f"{ch.database}.{VIEW}",
        event_types=present,
        entity_key="user_id",
        entity_key_confidence=1.0,
        secondary_keys=[c for c in ("application_id", "app_session_id") if c in cols],
        ordered_steps=present,
        step_order_source="timestamp_median",
        segment_dims=segment_dims,
        measures=measures,
        flags=[funnel_rationale] + [f"volume:{t}={counts.get(t, 0)}" for t in present],
        partial_identity_columns=[],
    )


def _funnel_sanity(ch: CH, sem: FeatureSemantics) -> list[str]:
    """Report where event volume does NOT decrease down the funnel.

    Not a failure -- these tables are independently populated and a later step CAN
    out-count an earlier one -- but it is exactly the kind of thing the probe questions
    are asking about, so it is surfaced rather than hidden.
    """
    counts = {
        str(r["event"]): int(r["n"])
        for r in ch.run_select(
            f"SELECT event, count() AS n FROM {ch.database}.{VIEW} GROUP BY event",
            max_rows=50,
        )
    }
    notes = []
    for a, b in zip(sem.ordered_steps, sem.ordered_steps[1:]):
        if counts.get(b, 0) > counts.get(a, 0):
            notes.append(f"{b} ({counts.get(b,0):,}) out-counts {a} ({counts.get(a,0):,})")
    return notes


def build_session(ch: CH) -> tuple[Session, dict]:
    tables = base_tables(ch)
    if len(tables) < 2:
        raise SystemExit(f"expected the pre-existing tables, found {tables}")
    cols = shared_columns(ch, tables)
    ensure_view(ch, tables, cols)
    sem = base_semantics(ch, tables, cols)
    meta = {
        "tables": tables,
        "shared_columns": len(cols),
        "funnel": sem.ordered_steps,
        "segment_dims": sem.segment_dims,
        "anomalies": _funnel_sanity(ch, sem),
        "funnel_rationale": next((f for f in sem.flags if f.startswith("derived by")), ""),
    }
    return Session(ch=ch, semantics=sem, slug="base_tables",
                   questions=list(STANDARD_PROBES)), meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--question", type=str, help="one ad-hoc question instead of the standard set")
    ap.add_argument("--list", action="store_true", help="print the standard prompts and exit")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    if args.list:
        for i, q in enumerate(STANDARD_PROBES, 1):
            con.print(f"{i}. {q}")
        return 0

    ch = CH()
    con.rule("[bold]Analytics Agent · the 8 pre-existing tables[/bold]")
    sess, meta = build_session(ch)
    con.print(f"[cyan]tables[/cyan]  {len(meta['tables'])}, {meta['shared_columns']} shared columns "
              f"-> view `{VIEW}`")
    con.print(f"[cyan]funnel[/cyan]  {' -> '.join(meta['funnel'])}")
    for note in meta["anomalies"]:
        con.print(f"[yellow]volume[/yellow]  {note}")

    questions = [args.question] if args.question else list(STANDARD_PROBES)
    args.out.mkdir(parents=True, exist_ok=True)
    results = []

    for i, q in enumerate(questions, 1):
        con.rule(f"[bold]{i}/{len(questions)}[/bold] {q[:70]}")
        ans, ungrounded = sess.answer(q)
        show(ans, ungrounded, sess.scanned)
        results.append(
            {
                "n": i,
                "question": q,
                "answer": ans.answer,
                "confidence": ans.confidence,
                "numbers_cited": ans.numbers_cited,
                "ungrounded_numbers": ungrounded,
                "supporting_queries": ans.supporting_queries,
                "caveats": list(ans.caveats),
                "trace_url": ans.__dict__.get("_trace_url", ""),
                "rows_scanned": sess.scanned,
            }
        )

    stamp = datetime.now(timezone.utc).replace(tzinfo=None)
    (args.out / "probe_results.json").write_text(
        json.dumps({"generated_at": stamp.isoformat(), "meta": meta, "results": results},
                   indent=2, default=str),
        encoding="utf-8",
    )

    md = [
        "# Standard probe set — the 8 pre-existing tables",
        "",
        f"Generated {stamp:%Y-%m-%d %H:%M} UTC by `python probe.py`. The four prompts are "
        "verbatim from the track's submission guidelines.",
        "",
        f"**Subject.** The {len(meta['tables'])} production tables, presented to the "
        f"analytics stack as one event stream via a `{VIEW}` view over their "
        f"{meta['shared_columns']} shared envelope columns — so every T01–T12 template, "
        "the confidence scoring, the numeric grounding and the metric policy apply "
        "unchanged. These answers come from the same machinery as the feature-spec "
        "answers, not a parallel path.",
        "",
        f"**Funnel analysed.** {' → '.join(meta['funnel'])}",
        "",
    ]
    if meta["anomalies"]:
        md += ["**Volume anomalies noticed while building the funnel** (these tables are "
               "independently populated, so a later step out-counting an earlier one is "
               "possible and is itself worth reporting):", ""]
        md += [f"- {a}" for a in meta["anomalies"]] + [""]

    for r in results:
        md += [
            f"## {r['n']}. {r['question']}",
            "",
            r["answer"],
            "",
            f"- **Confidence** {r['confidence']}",
            f"- **Grounded** {len(r['numbers_cited']) - len(r['ungrounded_numbers'])}"
            f"/{len(r['numbers_cited'])} figures matched their cited results"
            + (f" — **UNVERIFIED: {r['ungrounded_numbers']}**" if r["ungrounded_numbers"] else ""),
            f"- **Queries** {', '.join(f'`{q}`' for q in r['supporting_queries']) or '—'}",
            f"- **Rows scanned in ClickHouse** {r['rows_scanned']:,}",
            f"- **Trace** {r['trace_url'] or '(tracing off)'}",
            "",
        ]
        if r["caveats"]:
            md += ["**Caveats the agent attached:**", ""] + [f"- {c}" for c in r["caveats"]] + [""]

    (args.out / "PROBE_RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    tracing.flush()
    con.rule("[bold green]done[/bold green]")
    con.print(f"wrote {args.out / 'PROBE_RESULTS.md'}")
    con.print(f"wrote {args.out / 'probe_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
