#!/usr/bin/env python3
"""Regression oracle for the edge-case fixture — and the release-day report runner.

Two modes:

  --manifest PATH   FIXTURE MODE. Scores what the system produced against the
                    planted truth in edge_manifest.json: did each scenario's day
                    yield an incident, did the agent reach the expected verdict,
                    and did the seasonal-clean days stay clean (a false positive
                    there is a failure, not a nuisance).

  --report-only     RELEASE-DAY MODE. No oracle exists for the organisers' slice,
                    so this dumps what the system concluded — incident, verdict,
                    cause segment with its numbers, guardrail status and trace id —
                    as the submission artifact. Run it after loading the real data
                    and running profiler -> sweep -> prefill.

    python3 tools/regress_edge_cases.py --manifest /tmp/edge/edge_manifest.json
    python3 tools/regress_edge_cases.py --report-only --since 2026-08-20

Runs against whatever ClickHouse detector/chdb.py is configured for, so execute it
inside rca-mcp (docker compose exec -T rca-mcp python -m tools.regress_edge_cases)
or with CH_* exported on the host.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from detector import chdb

OK, FAIL, WARN = "PASS", "FAIL", "WARN"


def fetch(since: str, until: str | None = None):
    """Incidents joined to their latest diagnosis, in a window."""
    clause = "WHERE window_start >= {since:String}"
    params = {"since": since}
    if until:
        clause += " AND window_start < {until:String}"
        params["until"] = until
    rows = chdb.query(f"""
        SELECT i.incident_id AS incident_id, toString(toDate(i.window_start)) AS day,
               toString(i.window_start) AS ws, toString(i.window_end) AS we,
               i.metric AS metric, i.scope AS scope, i.status AS status,
               d.verdict_code AS verdict, d.headline AS headline,
               d.numbers_verified AS verified, d.trace_id AS trace_id,
               d.ruled_out AS ruled_out
        FROM rca.incidents AS i FINAL
        LEFT JOIN (
            SELECT incident_id, argMax(verdict_code, version) AS verdict_code,
                   argMax(headline, version) AS headline,
                   argMax(numbers_verified, version) AS numbers_verified,
                   argMax(trace_id, version) AS trace_id,
                   argMax(ruled_out, version) AS ruled_out
            FROM rca.diagnoses GROUP BY incident_id
        ) AS d ON d.incident_id = i.incident_id
        {clause} ORDER BY i.window_start""", params)
    return rows


def score(manifest_path: str) -> int:
    man = json.load(open(manifest_path))
    dates = man["main"]["dates"]
    by_id = {s["id"]: s for s in man["scenarios"]}
    start = man["main"]["start"]
    rows = fetch(start)
    by_day: dict[str, list] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)

    print(f"fixture: seed={man['seed']} randomized_targets={man['randomized_targets']} "
          f"rows={man['main']['rows']:,}")
    print(f"{'ID':<5} {'DATE':<11} {'RESULT':<5} {'EXPECTED':<17} {'GOT':<17} DETAIL")
    print("-" * 108)

    passed = failed = warned = 0
    for sid in sorted(dates):
        sc, day = by_id[sid], dates[sid]
        cands = by_day.get(day, [])
        want = sc["expect_verdict"]
        # the incident whose metric matches the scenario's lever, else any on the day
        match = [c for c in cands if c["metric"] == sc["expect_metric"]] or cands
        got = next((c["verdict"] for c in match if c["verdict"]), None)
        detail = ""
        if not cands:
            res, got = FAIL, "(no incident)"
            detail = "detection produced nothing on this day"
        elif want == "ANY":
            res = OK if got else WARN
            got = got or "(not investigated)"
            detail = sc.get("note", "")
        elif got == want:
            res, detail = OK, (match[0]["headline"] or "")[:52]
        else:
            # a different-but-defensible verdict is a WARN: the day WAS flagged and
            # investigated, the localisation differs. Only silence is a hard FAIL.
            res = WARN if got else FAIL
            got = got or "(not investigated)"
            detail = (match[0]["headline"] or "")[:52]
        print(f"{sid:<5} {day:<11} {res:<5} {want:<17} {str(got):<17} {detail}")
        passed += res == OK; failed += res == FAIL; warned += res == WARN

    # ── seasonality false positives: clean days must stay clean ────────────────
    print("\nSEASONALITY — clean days that must NOT alarm "
          "(volume there is -13%/-19% naturally):")
    for day in man["seasonal_clean_dates"]:
        open_inc = [c for c in by_day.get(day, [])
                    if c["status"] not in ("ruled_out_seasonal", "dismissed")]
        seasonal = [c for c in by_day.get(day, []) if c["status"] == "ruled_out_seasonal"]
        if not by_day.get(day):
            res, note = OK, "no incident raised at all"
        elif not open_inc:
            res, note = OK, f"{len(seasonal)} raised, all closed as seasonal/dismissed"
        else:
            res, note = FAIL, ("still open: " +
                               ", ".join(f"{c['metric']}:{c['scope']}" for c in open_inc))
        print(f"      {day}  {res:<5} {note}")
        passed += res == OK; failed += res == FAIL

    print(f"\n{passed} pass, {warned} warn, {failed} fail")
    return 1 if failed else 0


def report(since: str) -> int:
    """Release-day submission artifact: what the system concluded, with proof."""
    rows = fetch(since)
    if not rows:
        print(f"no incidents at or after {since}"); return 1
    print(f"# RCA submission report — {len(rows)} incident(s) from {since}\n")
    ver = sum(1 for r in rows if r["verified"])
    print(f"guardrail: {ver}/{len(rows)} diagnoses had every figure verified against "
          f"query results\n")
    for r in rows:
        print(f"## {r['incident_id']}")
        print(f"- window   : {r['ws']} -> {r['we']} UTC")
        print(f"- metric   : {r['metric']}   scope: {r['scope'] or 'global'}")
        print(f"- status   : {r['status']}   verdict: {r['verdict'] or '(not investigated)'}")
        print(f"- headline : {r['headline'] or '-'}")
        if r["ruled_out"]:
            print(f"- ruled out: {'; '.join(r['ruled_out'])}")
        print(f"- verified : {bool(r['verified'])}")
        print(f"- trace    : {r['trace_id'] or '-'}")
        print()
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", help="edge_manifest.json (fixture mode)")
    ap.add_argument("--report-only", action="store_true",
                    help="no oracle — dump what the system concluded (release day)")
    ap.add_argument("--since", default="2026-07-06",
                    help="window start for --report-only")
    a = ap.parse_args()
    if a.report_only:
        sys.exit(report(a.since))
    if not a.manifest:
        ap.error("need --manifest PATH or --report-only")
    sys.exit(score(a.manifest))


if __name__ == "__main__":
    main()
