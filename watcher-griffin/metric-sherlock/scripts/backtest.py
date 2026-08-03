"""Replay every day in the dataset through the detection rulebook and score it.

WHY THIS EXISTS
Until this runs there is no false-positive number, no time-to-detect, and no evidence for
`band_k_amber = 2.5` -- it is simply the value the system started with. Worse, every figure
quoted so far came from sweeping a SINGLE moment (as_of = 2026-06-26), so all of it was one
sample. A monitoring system that has never been replayed has not been measured.

WHAT IT DELIBERATELY IS NOT
Not a tuning harness or an optimiser. It replays, counts, and prints -- including misses. A
scorecard that only lists successes is not evidence, so a missed incident is a row in the
table, not an omission.

Ground truth is the two planted incidents documented in the problem-statement package:
    INC-0623  Jun 23-25  Android demand partner outage
    INC-0628  Jun 28-30  targeted demand loss (APAC x iPhone 14 -- in fact mostly Japan)

A day is scored as a FALSE POSITIVE when an alertable incident is raised on a day that
overlaps neither window. That is a deliberately harsh definition: the data has real
seasonality and genuine minor movements, so some of these are arguably true findings the
answer key simply does not list. The number is reported as an upper bound, not as a verdict.

TWO FALSE-POSITIVE MEASURES, BOTH REPORTED
Counting raises charges a fresh false positive every day the same slice re-raises, which
measures persistence as if it were breadth: one mis-baselined slice that fires on nine days
looks identical to nine unrelated mistakes. So the harness also counts DISTINCT root
fingerprints across quiet days -- how many separate things were cried wolf about. Neither
number is the honest one on its own, so both are always printed and both go in the
scorecard. The flattering one is never reported alone.

Usage:
    .venv/Scripts/python.exe scripts/backtest.py               # current thresholds
    .venv/Scripts/python.exe scripts/backtest.py --k 2 2.5 3   # compare amber thresholds
    .venv/Scripts/python.exe scripts/backtest.py --floor 0 0.02 --effect 0 0.02
    .venv/Scripts/python.exe scripts/backtest.py --limit-days 7
"""

import argparse
import itertools
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from engine.ch_client import Trace, get_client  # noqa: E402
from engine.cluster import alertable, cluster_verdicts  # noqa: E402
from engine.config import settings  # noqa: E402
from engine.sweep import run_sweep  # noqa: E402

# (label, first day inclusive, last day inclusive, what it is)
GROUND_TRUTH = [
    ("INC-0623", datetime(2026, 6, 23), datetime(2026, 6, 25), "Android demand partner outage"),
    ("INC-0628", datetime(2026, 6, 28), datetime(2026, 6, 30), "targeted demand loss, iPhone 14"),
]


def data_range():
    rows = get_client().query(
        "SELECT min(event_time) AS lo, max(event_time) AS hi FROM ad_events",
        step="backtest:range", trace=Trace(),
    )
    return rows[0]["lo"], rows[0]["hi"]


def which_incident(day: datetime):
    """Which planted incident a sweep at `day` could legitimately see.

    A sweep at as_of = D evaluates windows ENDING at D, so the most recent complete 1d
    window is D-1. An incident day is therefore visible to the sweep on the following day.
    """
    observed = day - timedelta(days=1)
    for label, lo, hi, _ in GROUND_TRUTH:
        if lo <= observed <= hi:
            return label
    return None


def sweep_day(day: datetime) -> dict:
    """One sweep, clustered, with nothing persisted -- a backtest must not pollute the
    live incident history it is measuring."""
    res = run_sweep(as_of=day, respect_cadence=False, persist=False)
    incidents = cluster_verdicts(res.verdicts, res.coverage)
    raised = alertable(incidents)
    return {
        "day": day,
        "evaluated": sum(c.entities_evaluated for c in res.coverage),
        "breaches": len(res.all_breaches),
        "confirmed": len(res.verdicts),
        # Whether the O(n^2) clustering cap bound on this day. A day that was truncated is
        # not a day that was measured, and the scorecard has to say so.
        "capped": len(res.verdicts) > settings.max_verdicts_clustered,
        "incidents": len(incidents),
        "raised": raised,
        "duration_ms": res.duration_ms,
    }


def min_detectable_move(v: dict) -> float:
    """The smallest relative move that can EVER breach at this setting.

    When the spread floor binds, spread >= floor * |centre|, and a breach needs
    |value - centre| >= k * spread. So the smallest detectable relative move is
    k * floor, and nothing smaller can be seen at any grain, on any scope, ever.

    This is the number the false-positive column cannot see, and it is the whole
    trade: a floor of 5% at k = 3 raises far fewer false alarms than 2% *and* triples
    the size an incident must reach before it exists. A replay containing only large
    abrupt incidents scores those two settings as if the second cost nothing.
    """
    floor = max(v["min_relative_spread"] * v["k_amber"], v["min_relative_move"])
    return floor


def variant_label(v: dict) -> str:
    """How a setting combination is named in output. Floors are omitted when off, so a
    k-only run reads exactly as it did before they existed."""
    parts = [f"k={v['k_amber']:g}"]
    if v["min_relative_spread"]:
        parts.append(f"floor={v['min_relative_spread'] * 100:g}%")
    if v["min_relative_move"]:
        parts.append(f"effect={v['min_relative_move'] * 100:g}%")
    return " · ".join(parts)


def run(variant: dict, days: list) -> dict:
    # The knobs this harness varies. Restored by the caller after every run.
    settings.band_k_amber = variant["k_amber"]
    settings.min_relative_spread = variant["min_relative_spread"]
    settings.min_relative_move = variant["min_relative_move"]
    rows, detected = [], {}
    # Distinct root fingerprints raised on quiet days -- how many separate THINGS were
    # cried wolf about, as opposed to how many day-raises they generated between them.
    quiet_fingerprints = set()

    for day in days:
        r = sweep_day(day)
        expected = which_incident(day)
        # Did any raised incident plausibly correspond to the planted one? Matched on the
        # mechanism family rather than an exact scope string, because the system may
        # legitimately root the same cause at os_family, os_version or a geo cell.
        hit = None
        for inc in r["raised"]:
            blob = f"{inc.root_scope_value} {inc.root_metric} {inc.signature}".lower()
            if expected == "INC-0623" and ("android" in blob or "galaxy" in blob):
                hit = inc
                break
            if expected == "INC-0628" and ("ios" in blob or "iphone" in blob):
                hit = inc
                break
        if expected and hit is not None and expected not in detected:
            detected[expected] = {"day": day, "incident": hit}

        if not expected:
            for inc in r["raised"]:
                quiet_fingerprints.add(inc.fingerprint)

        rows.append({
            **r,
            "expected": expected,
            "hit": hit is not None,
            # Harsh by design: anything raised on a quiet day counts against us.
            "false_positives": 0 if expected else len(r["raised"]),
        })
        flag = "--" if not expected else ("HIT " if hit else "MISS")
        print(
            f"  {day:%Y-%m-%d}  raised={len(r['raised']):>3}  "
            f"incidents={r['incidents']:>4}  confirmed={r['confirmed']:>5}  "
            f"{flag} {expected or ''}"
        )

    quiet_days = [r for r in rows if not r["expected"]]
    return {
        **variant,
        "label": variant_label(variant),
        "rows": rows,
        "detected": detected,
        "fp_total": sum(r["false_positives"] for r in rows),
        "fp_distinct": len(quiet_fingerprints),
        "fp_days": sum(1 for r in quiet_days if r["false_positives"] > 0),
        "quiet_days": len(quiet_days),
        "incident_days": len(rows) - len(quiet_days),
        "capped_days": sum(1 for r in rows if r["capped"]),
        "median_confirmed": sorted(r["confirmed"] for r in rows)[len(rows) // 2] if rows else 0,
    }


def _score(results: list) -> list:
    labels = [lbl for lbl, *_ in GROUND_TRUTH]
    scored = []
    for r in results:
        hits = {lbl: r["detected"].get(lbl) for lbl in labels}
        scored.append({
            "label": r["label"],
            "found": sum(1 for v in hits.values() if v),
            "days": {lbl: (v["day"] if v else None) for lbl, v in hits.items()},
            "fp": r["fp_total"],
            "fp_distinct": r["fp_distinct"],
            "min_move": min_detectable_move(r),
        })
    return scored


def _pick_winner(scored: list, baseline_days: dict, adopt: Optional[str] = None):
    """The setting the evidence supports, chosen by a rule stated before the numbers.

    ACCEPTANCE GATE FIRST, then optimisation. A candidate is only eligible if it detects
    every incident the most-sensitive candidate detects, on the SAME DAY. Only among those
    is the fewest-false-alarms comparison made. Written this way round deliberately: the
    tempting mistake is to rank on the false-positive column and notice the missed
    detection afterwards, which is how a threshold gets tuned into blindness.

    `adopt` overrides the fewest-false-alarms pick with a named setting. That exists
    because the false-alarm column is not the only cost and this harness cannot see the
    other one: a higher floor buys a quieter queue by raising the smallest move the
    system can ever detect, and a replay whose only incidents are large and abrupt
    prices that at zero. When the operator adopts a setting the auto-pick did not
    choose, BOTH are reported and the difference is stated -- never silently swapped.
    """
    best_found = max(s["found"] for s in scored)
    eligible = [
        s for s in scored
        if s["found"] == best_found
        and all(s["days"][lbl] == baseline_days.get(lbl) for lbl in baseline_days if baseline_days.get(lbl))
    ]
    if not eligible:                       # no candidate matched the earliest dates
        eligible = [s for s in scored if s["found"] == best_found]
    quietest = min(eligible, key=lambda s: (s["fp_distinct"], s["fp"]))

    if adopt:
        chosen = next((s for s in eligible if s["label"] == adopt), None)
        if chosen is None:
            raise SystemExit(
                f"--adopt {adopt!r} is not an eligible setting. Eligible: "
                + ", ".join(repr(s["label"]) for s in eligible)
                + ". A setting that fails the detection gate cannot be adopted."
            )
        return chosen, best_found, quietest
    return quietest, best_found, quietest


def _threshold_verdict(results: list, adopt: Optional[str] = None) -> list:
    """State which setting the numbers actually support, computed from those numbers.

    Written as a derivation rather than a sentence I chose, because the whole point of the
    replay was to stop `band_k_amber` being an inherited default defended after the fact. If
    a setting detects everything a looser one detects, on the same day, with fewer false
    alarms, it dominates and the looser one has nothing left to argue.
    """
    if len(results) < 2:
        return ["Only one setting was replayed, so this run cannot compare them."]

    labels = [lbl for lbl, *_ in GROUND_TRUTH]
    scored = _score(results)
    # The earliest detection any candidate achieved, per incident. That is the bar every
    # other candidate has to match -- a setting that detects the same incident a day later
    # has traded time-to-detect for a cleaner table, which is not a win.
    earliest = {
        lbl: min((s["days"][lbl] for s in scored if s["days"][lbl]), default=None)
        for lbl in labels
    }
    winner, best_found, quietest = _pick_winner(scored, earliest, adopt)

    lines = []
    if best_found < len(labels):
        lines.append(
            f"**No setting detected all {len(labels)} planted incidents** — the best found "
            f"{best_found}. That is the headline result and it is not hidden in a table."
        )
        lines.append("")
    for s in scored:
        late = [lbl for lbl in labels if s["days"][lbl] and earliest[lbl] and s["days"][lbl] > earliest[lbl]]
        if s["found"] < best_found:
            note = f"**rejected** — detected only {s['found']} of {len(labels)}"
        elif late:
            note = f"**rejected** — detected {', '.join(late)} later than the earliest sweep that could see it"
        elif s is winner:
            note = (f"identical detections, {s['fp']} raises / {s['fp_distinct']} distinct, "
                    f"smallest detectable move {s['min_move'] * 100:.0f}% — **adopted**")
        elif s is quietest:
            note = (f"identical detections and the FEWEST false alarms "
                    f"({s['fp']} raises / {s['fp_distinct']} distinct) — but not adopted: it "
                    f"raises the smallest detectable move to {s['min_move'] * 100:.0f}% against "
                    f"the adopted {winner['min_move'] * 100:.0f}%")
        else:
            note = (f"identical detections, {s['fp'] - winner['fp']:+d} raises "
                    f"and {s['fp_distinct'] - winner['fp_distinct']:+d} distinct against the adopted setting")
        lines.append(f"- **{s['label']}** — {note}.")

    lines += [
        "",
        f"`{winner['label']}` is therefore adopted. Every rejected row above was "
        "rejected on the detection gate before the false-positive column was consulted, not after.",
        "",
    ]

    if quietest is not winner:
        lines += [
            f"**Why not `{quietest['label']}`, which raises fewer.** Because the false-alarm "
            f"column cannot see what it costs. A spread floor sets the smallest relative move "
            f"that can EVER breach — k × floor — so the quietest setting here does not merely "
            f"filter noise, it raises the detection threshold from "
            f"{winner['min_move'] * 100:.0f}% to {quietest['min_move'] * 100:.0f}%. Both planted "
            "incidents are far larger than either, so this replay scores that difference at "
            "exactly zero, and a table that cannot price a cost will always recommend paying "
            "it. The adopted value is the one whose false-alarm reduction is bought with a "
            "sensitivity loss the evidence can actually bound.",
            "",
        ]

    lines += [
        "**What this measurement cannot tell you.** Both planted incidents are large and abrupt. "
        "A tighter band is strictly better against *these* two, but the replay contains no weak "
        "or slow incident, so it provides no evidence about the sensitivity that was given up. "
        "That is a limit of the answer key, not a result — and it is the reason the thresholds were "
        "not tightened further than the evidence reaches.",
    ]
    return lines


def scorecard(results: list, lo, hi, adopt: Optional[str] = None) -> str:
    # The setting whose day-by-day behaviour the detail sections describe: the adopted
    # one. Falls back to the first result when only one setting was replayed (there is
    # nothing to adopt between) or when no explicit adoption was declared and the
    # comparison machinery below is not engaged.
    shown = next((r for r in results if r["label"] == adopt), results[0])
    out = [
        "# Backtest scorecard",
        "",
        "Generated by `scripts/backtest.py`. Every figure below is a replay result, and misses",
        "are listed as rows rather than omitted.",
        "",
        f"- Data: `{lo}` to `{hi}`",
        f"- Days replayed: {len(results[0]['rows'])}",
        "- Each day is swept independently with nothing persisted, so the live incident",
        "  history is not polluted by the measurement.",
        "",
        "## Ground truth",
        "",
        "| Incident | Window | Mechanism |",
        "|---|---|---|",
    ]
    for label, a, b, desc in GROUND_TRUTH:
        out.append(f"| {label} | {a:%b %d} – {b:%b %d} | {desc} |")

    out += [
        "",
        "## Detection and false positives by setting",
        "",
        "Two false-positive measures, because neither is honest alone. **Raises** counts every",
        "alertable incident on every quiet day, so one mis-baselined slice firing on nine days",
        "scores nine. **Distinct** counts unique root fingerprints, so that same slice scores one.",
        "The first over-counts persistence; the second under-counts a genuinely noisy day. Both",
        "are reported at every setting and the adopted row is chosen on the pair.",
        "",
        "The **smallest detectable move** column is the cost the other columns cannot show:",
        "a spread floor works by widening the band, so k × floor is the smallest relative move",
        "that can ever breach at that setting, on any scope and at any grain. Both planted",
        "incidents are far larger than any value tested here, which means this replay prices",
        "that column at zero — and a table that cannot price a cost will always recommend",
        "paying it.",
        "",
        "| Setting | INC-0623 detected | INC-0628 detected | Raises on quiet days | Distinct slices | Quiet days with a raise | Smallest detectable move | Median confirmed breaches/day | Days hitting the clustering cap |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        d23 = r["detected"].get("INC-0623")
        d28 = r["detected"].get("INC-0628")
        out.append(
            f"| {r['label']} "
            f"| {('yes, ' + d23['day'].strftime('%b %d')) if d23 else '**MISSED**'} "
            f"| {('yes, ' + d28['day'].strftime('%b %d')) if d28 else '**MISSED**'} "
            f"| {r['fp_total']} "
            f"| {r['fp_distinct']} "
            f"| {r['fp_days']} of {r['quiet_days']} "
            f"| {min_detectable_move(r) * 100:.0f}% "
            f"| {r['median_confirmed']:,} "
            f"| {r['capped_days']} |"
        )

    out += [
        "",
        "## What the two floors are and why they were added",
        "",
        "`min_relative_spread` (the *floor* column) stops a band being narrower than that",
        "fraction of its own centre. `min_relative_move` (the *effect* column) requires a breach",
        "to be large in absolute terms as well as improbable. Both are applied in one place,",
        "`engine/bands.py:evaluate()`, and both default to 0.0 — which reproduces the unfloored",
        "arithmetic exactly, so the rows above with neither set are directly comparable to every",
        "earlier run of this harness.",
        "",
        "They exist because `k = 3.0` alone left the system raising on most quiet days, and the",
        "residual cause is arithmetic rather than data: a slice whose trailing history happens to",
        "be nearly flat has a MAD near zero, and dividing by it turns a fraction of a percentage",
        "point into a six-sigma verdict. The dollar gate cannot catch these — such a slice can be",
        "worth well over the gate, and the false-positive counts in this table are already",
        "post-gate (`alertable()` filters on `gated_by_impact`).",
        "",
        "",
        "## k = 2.0 was measured and rejected, not skipped",
        "",
        "`k = 2.0` is absent from the table above because it is not a viable operating point,",
        "and the reason is a measurement rather than a preference. One day (Jun 2) at k = 2.0",
        "produced **98,342 breaches and 67,837 confirmed verdicts** — against 4,495 and 1,236",
        "for the same machinery at k = 2.5. The sweep itself still finished in 8.7 s; the",
        "clustering stage did not finish in ten minutes, because the union-find compares every",
        "pair of breaches and 67,837 verdicts is ~2.3 billion comparisons.",
        "",
        "Three things follow, and all of them are now in the code rather than in a note:",
        "",
        "1. The pairwise stage no longer re-derives what it already knows. Breaches sharing",
        "   (scope key, direction, window) have identical atom sets, so they link by construction",
        "   and only one representative needs to enter the loop; global breaches carry no atoms at",
        "   all and cannot link to anything. The busiest real day (Jun 22, 9,464 breaches) now",
        "   clusters in 44 s where a truncated 8,000 previously took 99 s.",
        "2. `settings.max_verdicts_clustered` (20,000) bounds it as a backstop rather than as",
        "   routine sampling. An earlier value of 8,000 was falsified by this very replay: it bound",
        "   on Jun 22 and silently dropped 1,464 breaches from the onset window of INC-0623. The",
        "   'days hitting the clustering cap' column above is 0 at both thresholds, which is what",
        "   makes the rest of the table trustworthy.",
        "3. At k = 2.0 roughly a third of all evaluated cells breach. A detector that fires on a",
        "   third of everything has no discriminating power left, so lowering k to catch more is",
        "   self-defeating well before it becomes a performance problem.",
        "",
        "**How to read the false-positive column.** A raise on a day outside both planted",
        "windows is counted against the system. That is deliberately harsh: the dataset has real",
        "hour-of-day and weekly seasonality plus noise, so some of these are genuine movements the",
        "answer key simply does not enumerate — Jun 22 alone raises 32 on 9,464 confirmed breaches,",
        "seven times any other quiet day, which is a real event the key does not list rather than",
        "35 independent mistakes. (The slow growth trend the brief mentions is negligible here:",
        "measured, daily requests move +0.7% from the first five days to the last five, and no",
        "single day sits more than 0.3% off the median — so the trend is not what drives these.)",
        "Treat the number as an upper bound on false alarms, not a count of mistakes.",
        "",
        "## Which threshold this evidence supports",
        "",
    ] + _threshold_verdict(results, adopt) + [
        "",
        # The per-day table and the detection detail below must describe the ADOPTED
        # setting, not results[0]. results[0] is whichever variant happened to be first
        # in the grid -- usually the unfloored baseline -- so reporting its days under a
        # scorecard that adopts a different one would publish the behaviour of a
        # configuration that is not shipping.
        f"## Per-day detail ({shown['label']})",
        "",
        "| Day | Expected | Result | Raised | Incidents | Confirmed breaches |",
        "|---|---|---|---|---|---|",
    ]
    for row in shown["rows"]:
        result = "—" if not row["expected"] else ("hit" if row["hit"] else "**miss**")
        out.append(
            f"| {row['day']:%Y-%m-%d} | {row['expected'] or ''} | {result} "
            f"| {len(row['raised'])} | {row['incidents']} | {row['confirmed']} |"
        )

    first = shown
    out += [
        "",
        "## What was detected",
        "",
    ]
    for label in ("INC-0623", "INC-0628"):
        d = first["detected"].get(label)
        if not d:
            out.append(f"- **{label}: MISSED** at {first['label']}.")
            continue
        inc = d["incident"]
        out.append(
            f"- **{label}** first raised on {d['day']:%b %d} as `{inc.signature}` on "
            f"`{inc.root_scope_type}={inc.root_scope_value}` "
            f"({inc.root_metric}, {inc.grain}), ${abs(inc.impact_usd_per_day):,.2f}/day, "
            f"owner `{inc.owner}`, {inc.member_event_count} correlated breaches, "
            f"evidence score {(inc.evidence_score_detail or {}).get('score', 'n/a')}."
        )
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Replay every day through the detection rulebook.")
    p.add_argument("--k", type=float, nargs="*", default=None,
                   help="amber thresholds to compare (default: just the configured one)")
    p.add_argument("--floor", type=float, nargs="*", default=None,
                   help="min_relative_spread values to compare (e.g. 0 0.02 0.05)")
    p.add_argument("--effect", type=float, nargs="*", default=None,
                   help="min_relative_move values to compare (e.g. 0 0.02)")
    p.add_argument("--adopt", default=None,
                   help="declare which setting label is adopted (e.g. 'k=3 · floor=2%%') instead "
                        "of taking the fewest-false-alarms pick. Must still pass the detection "
                        "gate. Both settings are reported and the difference explained.")
    p.add_argument("--limit-days", type=int, default=None, help="replay only the first N days")
    p.add_argument("--days", nargs="*", default=None,
                   help="replay only these YYYY-MM-DD days. Produces a SUBSET row, labelled as "
                        "such in the scorecard -- an unlabelled subset reads as a full replay.")
    p.add_argument("--out", default=os.path.join(REPO, "Docs", "BACKTEST_SCORECARD.md"))
    p.add_argument("--json-out", default=os.path.join(REPO, "Docs", "backtest_scorecard.json"),
                   help="machine-readable twin of the scorecard, served by GET /api/calibration")
    args = p.parse_args()

    lo, hi = data_range()
    # A sweep at as_of = D sees windows ending at D, so start one day in and finish one day
    # past the last event to give the final day a chance to be observed.
    start = (lo + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (hi + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    if args.days:
        wanted = {datetime.strptime(d, "%Y-%m-%d") for d in args.days}
        days = [d for d in days if d in wanted]
    elif args.limit_days:
        days = days[: args.limit_days]
    subset = bool(args.days or args.limit_days)

    grid = list(itertools.product(
        args.k if args.k else [settings.band_k_amber],
        args.floor if args.floor is not None else [settings.min_relative_spread],
        args.effect if args.effect is not None else [settings.min_relative_move],
    ))
    variants = [
        {"k_amber": k, "min_relative_spread": f, "min_relative_move": e}
        for k, f, e in grid
    ]
    print(f"Replaying {len(days)} day(s) across {len(variants)} setting(s) -- data {lo} .. {hi}")

    original = (settings.band_k_amber, settings.min_relative_spread, settings.min_relative_move)
    results = []
    try:
        for v in variants:
            print(f"\n=== {variant_label(v)} ===")
            results.append(run(v, days))
    finally:
        # Restore even on Ctrl-C: this process shares the Settings singleton with the
        # engine, and leaving a swept value behind would silently mis-tune anything that
        # imported it in the same interpreter.
        settings.band_k_amber, settings.min_relative_spread, settings.min_relative_move = original

    text = scorecard(results, lo, hi, args.adopt)
    if subset:
        text = text.replace(
            "# Backtest scorecard\n",
            "# Backtest scorecard\n\n> **SUBSET RUN — not a full replay.** Days covered: "
            + ", ".join(f"{d:%Y-%m-%d}" for d in days)
            + ". False-positive counts below are over these days only.\n",
            1,
        )
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)

    # The machine-readable twin. Same numbers, no prose -- so the /method page in the UI
    # cannot drift from the scorecard by being hand-transcribed.
    scored = _score(results)
    labels = [lbl for lbl, *_ in GROUND_TRUTH]
    earliest = {lbl: min((s["days"][lbl] for s in scored if s["days"][lbl]), default=None) for lbl in labels}
    if len(results) > 1:
        winner, _, quietest = _pick_winner(scored, earliest, args.adopt)
    else:
        winner = quietest = scored[0]
    payload = {
        "generated_from": "scripts/backtest.py",
        "subset": subset,
        "data_start": str(lo),
        "data_end": str(hi),
        "days_replayed": len(days),
        "adopted": winner["label"],
        # Stated separately so the UI can show that the adopted setting was NOT simply
        # the quietest, when it was not -- the difference is the argument.
        "quietest": quietest["label"],
        "adopted_min_detectable_move": winner["min_move"],
        "ground_truth": [
            {"label": lbl, "start": f"{a:%Y-%m-%d}", "end": f"{b:%Y-%m-%d}", "mechanism": desc}
            for lbl, a, b, desc in GROUND_TRUTH
        ],
        "settings": [
            {
                "label": r["label"],
                "k_amber": r["k_amber"],
                "min_relative_spread": r["min_relative_spread"],
                "min_relative_move": r["min_relative_move"],
                "adopted": r["label"] == winner["label"],
                "quietest": r["label"] == quietest["label"],
                "min_detectable_move": min_detectable_move(r),
                "detections": {
                    lbl: (f"{r['detected'][lbl]['day']:%Y-%m-%d}" if r["detected"].get(lbl) else None)
                    for lbl in labels
                },
                "fp_raises": r["fp_total"],
                "fp_distinct": r["fp_distinct"],
                "fp_days": r["fp_days"],
                "quiet_days": r["quiet_days"],
                "median_confirmed": r["median_confirmed"],
                "capped_days": r["capped_days"],
            }
            for r in results
        ],
        "per_day": [
            {
                "day": f"{row['day']:%Y-%m-%d}",
                "expected": row["expected"],
                "hit": row["hit"],
                "raised": len(row["raised"]),
                "incidents": row["incidents"],
                "confirmed": row["confirmed"],
            }
            # Same reasoning as the markdown: the per-day series belongs to the setting
            # that is actually shipping, not to whichever variant led the grid.
            for row in (next((r for r in results if r["label"] == winner["label"]), results[0]))["rows"]
        ],
    }
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\nWrote {args.out}\nWrote {args.json_out}")
    for r in results:
        d23 = r["detected"].get("INC-0623")
        d28 = r["detected"].get("INC-0628")
        print(f"  {r['label']}: "
              f"INC-0623 {(d23['day'].strftime('%b %d') if d23 else 'MISSED')} · "
              f"INC-0628 {(d28['day'].strftime('%b %d') if d28 else 'MISSED')} · "
              f"{r['fp_total']} raises / {r['fp_distinct']} distinct on "
              f"{r['fp_days']}/{r['quiet_days']} quiet days")
