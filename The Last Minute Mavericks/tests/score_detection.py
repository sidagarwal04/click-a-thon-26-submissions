#!/usr/bin/env python3
"""Score a run_incident.py JSON bundle against a synthetic anomaly manifest.

This is intentionally outside the detector path. The engine runs blind; only this scorer opens the
manifest after the scan and grades detection/localization quality.

Usage:
  python tests/score_detection.py --manifest tests/eval_runs/seed_7/manifest.json \
    --bundle tests/eval_runs/seed_7/scan_bundle.json
"""
import argparse
import json
from pathlib import Path


def _win(item):
    return list(item.get("win") or item.get("window") or ["", ""])


def overlaps(a, b):
    return not (a[1] < b[0] or a[0] > b[1])


def culprit_pairs(culprit):
    pairs = set()
    if not culprit:
        return pairs
    dim = culprit.get("dimension") or culprit.get("dim")
    seg = str(culprit.get("segment") or culprit.get("seg") or culprit.get("value") or "")
    if "=" in seg:
        for part in seg.split("×"):
            d, _, value = part.partition("=")
            if d.strip() and value.strip():
                pairs.add((d.strip(), value.strip()))
    elif dim and seg:
        pairs.add((str(dim), seg))
    co = culprit.get("co_cut") or {}
    if isinstance(co, dict):
        pairs.update((str(k), str(v)) for k, v in co.items())
    return pairs


def expected_pairs(inc):
    expected = inc.get("expected_culprit")
    if isinstance(expected, dict) and expected:
        return {(str(k), str(v)) for k, v in expected.items()}
    if inc.get("dim") == "__global__":
        return set()
    pairs = {(str(inc["dim"]), str(inc["value"]))}
    for prefix in ("co", "co2"):
        if inc.get(f"{prefix}_dim"):
            pairs.add((str(inc[f"{prefix}_dim"]), str(inc[f"{prefix}_value"])))
    return pairs


def match_result(inc, inv):
    if inv.get("metric") != inc.get("metric"):
        return None
    if not overlaps(_win(inc), _win(inv)):
        return None
    if inc.get("dim") == "__global__":
        verdict = str(inv.get("verdict", ""))
        localized = not inv.get("culprit") or verdict.startswith("GLOBAL")
        return {"detected": True, "localized": localized}
    expected = expected_pairs(inc)
    actual = culprit_pairs(inv.get("culprit"))
    return {"detected": True, "localized": expected.issubset(actual)}


def _manifest_incidents(manifest):
    if isinstance(manifest, list):
        return manifest
    return manifest.get("incidents") or manifest.get("manifest") or []


def score_bundle(manifest, bundle):
    incidents = _manifest_incidents(manifest)
    invs = bundle.get("investigations", [])
    used = set()
    rows = []

    candidates = {
        idx: [(i, res) for i, inv in enumerate(invs) if (res := match_result(inc, inv))]
        for idx, inc in enumerate(incidents)
    }

    hits = {}
    for idx in range(len(incidents)):
        hit = next((c for c in candidates[idx] if c[0] not in used and c[1]["localized"]), None)
        if hit:
            used.add(hit[0])
            hits[idx] = hit
    for idx in range(len(incidents)):
        if idx in hits:
            continue
        hit = next((c for c in candidates[idx] if c[0] not in used), None)
        if hit:
            used.add(hit[0])
            hits[idx] = hit

    for idx, inc in enumerate(incidents):
        res = hits.get(idx, (None, {"detected": False, "localized": False}))[1]
        rows.append({
            "id": inc.get("id") or inc.get("src") or f"INC-{idx + 1}",
            "metric": inc.get("metric"),
            "dim": inc.get("dim"),
            "value": inc.get("value"),
            "window": _win(inc),
            "detected": bool(res["detected"]),
            "localized": bool(res["localized"]),
        })

    fps = [inv for i, inv in enumerate(invs) if i not in used]
    detected = sum(r["detected"] for r in rows)
    localized = sum(r["localized"] for r in rows)
    n = len(rows)
    precision = (len(invs) - len(fps)) / len(invs) if invs else 1.0
    detection_recall = detected / n if n else 1.0
    localization_recall = localized / n if n else 1.0

    misses_by_metric = {}
    misses_by_dimension = {}
    for row in rows:
        if row["localized"]:
            continue
        misses_by_metric[row["metric"]] = misses_by_metric.get(row["metric"], 0) + 1
        misses_by_dimension[row["dim"]] = misses_by_dimension.get(row["dim"], 0) + 1

    evidence_complete = True
    for inv in invs:
        evidence = inv.get("evidence") or []
        if not evidence or any(not ev.get("query_id") for ev in evidence):
            evidence_complete = False
            break

    return {
        "precision": round(precision, 4),
        "detection_recall": round(detection_recall, 4),
        "localization_recall": round(localization_recall, 4),
        "found": detected,
        "localized": localized,
        "expected": n,
        "reported": len(invs),
        "false_positives": len(fps),
        "evidence_complete": evidence_complete,
        "wall_clock_s": bundle.get("scan_summary", {}).get("wall_clock_s"),
        "misses_by_metric": misses_by_metric,
        "misses_by_dimension": misses_by_dimension,
        "incidents": rows,
        "false_positive_investigations": [
            {
                "metric": inv.get("metric"),
                "window": _win(inv),
                "verdict": inv.get("verdict"),
                "headline": inv.get("headline"),
                "culprit": inv.get("culprit"),
            }
            for inv in fps
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    bundle = json.load(open(args.bundle))
    score = score_bundle(manifest, bundle)

    print(
        "score "
        f"precision={score['precision']:.2f} "
        f"detection_recall={score['detection_recall']:.2f} "
        f"localization_recall={score['localization_recall']:.2f} "
        f"fp={score['false_positives']} "
        f"evidence_complete={score['evidence_complete']}"
    )
    if score["misses_by_metric"]:
        print("misses_by_metric:", score["misses_by_metric"])
    if score["false_positive_investigations"]:
        print("false_positives:")
        for inv in score["false_positive_investigations"]:
            print(f"  - {inv['metric']} {inv['window']} {inv['verdict']} {inv['headline']}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump(score, open(args.out, "w"), indent=2, default=str)


if __name__ == "__main__":
    main()
