"""Sweep: batch detection over the full loaded range.

    python3 -m detector.sweep [--dry-run] [--z-hi 3.0] [--grain both|hour|day]

Pipeline (ARCHITECTURE.md — detection stages 3-5):
  score     run the ensemble SQL (hourly + daily grains)
  flag      |z_primary| >= Z_HI  AND  practical significance  AND  volume floor
            (plus naive-source candidates: deviant ONLY under the seasonality-blind
             model — these exist to be classified as seasonal/trend and ruled out)
  window    merge consecutive flagged buckets; persistence gate
  classify  ensemble disagreement -> anomaly | seasonal_expected | trend | data_gap
  dedup     overlapping windows cluster; head = most global scope, metric priority,
            hourly before daily; the rest attach as corroborating signals
  write     rca.incidents (chronological) + a step_no=0 'detect' row per incident
            in rca.investigation_steps carrying model verdicts + corroboration

Statuses: anomaly -> 'detected' (agent picks these up); seasonal_expected ->
'ruled_out_seasonal' (the checked-and-ruled-out record); trend/data_gap -> 'dismissed'.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import chdb, config

SQL_DIR = Path(__file__).parent / "sql"
PRE_Z_MARGIN = 0.5          # fetch context slightly below Z_HI so merges see neighbors
MODELS = ("naive", "hod", "how", "stl", "flat")
STATUS = {"anomaly": "detected", "seasonal_expected": "ruled_out_seasonal",
          "trend": "dismissed", "data_gap": "dismissed"}


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def load_scored(grain: str, z_hi: float) -> dict[tuple, list[dict]]:
    fname = "score_hourly.sql" if grain == "hour" else "score_daily.sql"
    rows = chdb.query_file(SQL_DIR / fname,
                           params={"pre_z": z_hi - PRE_Z_MARGIN, "naive_z": z_hi})
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        r["window_start"] = _ts(r["window_start"])
        for f in ("actual", "vol", "e_naive", "z_naive", "e_hod", "z_hod", "e_how",
                  "z_how", "e_stl", "z_stl", "e_flat", "z_flat", "e_primary", "z_primary"):
            r[f] = _num(r.get(f))
        by_key.setdefault((r["dimension"], r["value"], r["metric"]), []).append(r)
    for v in by_key.values():
        v.sort(key=lambda r: r["window_start"])
    return by_key


def practical_ok(actual, expected, metric: str, grain: str) -> bool:
    kind, thr = config.practical(grain)[metric]
    if kind is None or actual is None or expected is None:
        return False
    if kind == "rel":
        return expected != 0 and abs(actual / expected - 1) >= thr
    return abs(actual - expected) >= thr


def is_flagged(r: dict, grain: str, source: str, z_hi: float) -> bool:
    z = r["z_primary"] if source == "primary" else r["z_naive"]
    e = r["e_primary"] if source == "primary" else r["e_naive"]
    if z is None or abs(z) < z_hi:
        return False
    if (r["vol"] or 0) < config.volume_floor(grain):
        return False
    return practical_ok(r["actual"], e, r["metric"], grain)


def build_windows(key, rows, grain: str, source: str, z_hi: float) -> list[dict]:
    step = timedelta(hours=1) if grain == "hour" else timedelta(days=1)
    gap = (config.MERGE_GAP_HOURS + 1) * step if grain == "hour" else step
    persist = config.PERSIST_HOURS if grain == "hour" else config.PERSIST_DAYS
    if source == "naive" and grain == "day":
        persist = 1   # rule-out records aren't alarms: a single seasonal Saturday must
                      # still be captured (and head its cluster at global scope)

    flagged = [r for r in rows if is_flagged(r, grain, source, z_hi)]
    if source == "naive":   # only windows the primary did NOT flag (pure trap candidates)
        flagged = [r for r in flagged if not is_flagged(r, grain, "primary", z_hi)]
    zf = "z_primary" if source == "primary" else "z_naive"
    windows, cur = [], []
    for r in flagged:
        sign_flip = cur and (r[zf] or 0) * (cur[-1][zf] or 0) < 0
        if cur and ((r["window_start"] - cur[-1]["window_start"]) > gap or sign_flip):
            windows.append(cur)
            cur = []
        cur.append(r)
    if cur:
        windows.append(cur)

    out = []
    for members in windows:
        zs = [abs(m["z_primary" if source == "primary" else "z_naive"] or 0) for m in members]
        if len(members) < persist and max(zs) < config.Z_EXTREME:
            continue
        start, end = members[0]["window_start"], members[-1]["window_start"]
        context = [r for r in rows if start <= r["window_start"] <= end]
        out.append({"key": key, "grain": grain, "source": source, "step": step,
                    "start": start, "end": end, "members": members, "context": context})
    return out


def model_medians(window: dict) -> dict:
    meds = {}
    for m in MODELS:
        vals = [r[f"z_{m}"] for r in window["context"] if r.get(f"z_{m}") is not None]
        meds[m] = statistics.median(vals) if vals else None
    vals = [r["z_primary"] for r in window["context"] if r["z_primary"] is not None]
    meds["primary"] = statistics.median(vals) if vals else None
    return meds


def classify(window: dict) -> str | None:
    dim, value, metric = window["key"]
    meds = window["meds"] = model_medians(window)
    if metric == "requests" and all((m["actual"] or 0) == 0 for m in window["members"]):
        return "data_gap"
    if window["source"] == "primary":
        return "anomaly"
    # naive-source candidate: deviant only under the seasonality-blind model.
    how, stl = meds.get("how"), meds.get("stl")
    how_clear = how is None or abs(how) < config.Z_CLEAR
    stl_clear = stl is None or abs(stl) < config.Z_CLEAR
    if how_clear and stl_clear:
        return "seasonal_expected"     # slot + STL both say "expected at this hour"
    if stl_clear:
        return "trend"                 # trend+seasonal explains what slots alone don't
    return None                        # genuinely deviant — the primary path owns it


def window_aggregates(window: dict) -> tuple[float, float]:
    """Window-level (actual, expected): sums for volume metrics, medians for ratios."""
    metric = window["key"][2]
    src = "e_primary" if window["source"] == "primary" else "e_naive"
    pairs = [(m["actual"], m[src]) for m in window["members"]
             if m["actual"] is not None and m[src] is not None]
    if not pairs:
        return 0.0, 0.0
    if metric in ("requests", "revenue"):
        return sum(p[0] for p in pairs), sum(p[1] for p in pairs)
    return (statistics.median([p[0] for p in pairs]),
            statistics.median([p[1] for p in pairs]))


def window_change(window: dict) -> float:
    a, e = window_aggregates(window)
    return a / e - 1 if e else 0.0


def window_z(window: dict) -> float:
    zf = "z_primary" if window["source"] == "primary" else "z_naive"
    zs = [m[zf] for m in window["members"] if m[zf] is not None]
    return max(zs, key=abs) if zs else 0.0


def dedup(windows: list[dict]) -> list[dict]:
    """Head-first absorption, per verdict class.

    Strongest head (most global scope, metric priority, hourly grain, |z|) absorbs
    every window overlapping ITS OWN span (+/- one step) — deliberately NOT
    transitive clustering: post-incident echoes must not chain a bridge from one
    incident into the next and swallow it (the Jun 21 -> Jun 23-25 failure mode).
    """
    def cls(w):
        return "anomaly" if w["verdict"] == "anomaly" else "ruled_out"

    heads = []
    for klass in ("anomaly", "ruled_out"):
        # Head strength: scope generality, then metric priority, then |z| — NOT grain:
        # a weak hourly blip must never out-rank and swallow a strong multi-day event.
        pool = sorted([w for w in windows if cls(w) == klass],
                      key=lambda w: (config.scope_rank(w["key"][0]),
                                     config.METRIC_PRIORITY.index(w["key"][2]),
                                     -abs(window_z(w))))
        while pool:
            head = pool.pop(0)
            pad = head["step"]
            hz, hmetric = window_z(head), head["key"][2]
            absorbed = [w for w in pool
                        if w["start"] <= head["end"] + pad and w["end"] >= head["start"] - pad
                        # same-metric echoes must share direction: an eCPM up-step and an
                        # adjacent eCPM down-dip are two incidents, not one. Cross-metric
                        # echoes may legitimately flip sign (fill down -> unfilled up).
                        and (w["key"][2] != hmetric or window_z(w) * hz >= 0)]
            pool = [w for w in pool if not any(w is a for a in absorbed)]
            head["corroborating"] = [{
                "scope": scope_of(w), "metric": w["key"][2], "grain": w["grain"],
                "window": [_fmt(w["start"]), _fmt(w["end"] + w["step"])],
                "z": round(window_z(w), 2), "verdict": w["verdict"],
            } for w in absorbed]
            heads.append(head)
    return sorted(heads, key=lambda w: w["start"])


def scope_of(w: dict) -> str:
    dim, value, _ = w["key"]
    return "global" if dim == "global" else f"{dim}={value}"


def slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s)


def run(z_hi: float, grains: list[str], dry_run: bool) -> list[dict]:
    windows = []
    for grain in grains:
        by_key = load_scored(grain, z_hi)
        for key, rows in by_key.items():
            primary_ws = build_windows(key, rows, grain, "primary", z_hi)
            naive_ws = build_windows(key, rows, grain, "naive", z_hi)
            # Naive-echo suppression: for ~72h after a real incident the trailing
            # naive baseline is contaminated by the incident itself; a naive-only
            # window in its wake is an artifact, not seasonality to rule out.
            echo_horizon = timedelta(hours=72)
            naive_ws = [w for w in naive_ws
                        if not any(p["end"] <= w["start"] <= p["end"] + echo_horizon
                                   or p["start"] - w["step"] <= w["start"] <= p["end"]
                                   for p in primary_ws)]
            for w in primary_ws + naive_ws:
                a, e = window_aggregates(w)
                if not practical_ok(a, e, key[2], grain):   # window-level significance
                    continue
                w["verdict"] = classify(w)
                if w["verdict"]:
                    windows.append(w)
    heads = dedup(windows)

    run_id = f"sweep_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    incidents, steps = [], []
    for w in heads:
        dim, value, metric = w["key"]
        scope = scope_of(w)
        end_excl = w["end"] + w["step"]
        inc_id = f"inc_{w['start']:%Y%m%dT%H}_{metric}_{slug(scope)}"
        incidents.append({
            "incident_id": inc_id, "run_id": run_id, "source": "sweep",
            "metric": metric, "scope": scope,
            "window_start": _fmt(w["start"]), "window_end": _fmt(end_excl),
            "z_score": round(window_z(w), 3),
            "pct_change": round(window_change(w), 5),
            "status": STATUS[w["verdict"]],
        })
        steps.append({
            "incident_id": inc_id, "step_no": 0, "step_type": "detect",
            "hypothesis": f"sweep[{w['grain']}] {scope} {metric}: "
                          f"{len(w['members'])} flagged {w['grain']}(s), source={w['source']}",
            "sql_text": f"-- detector/sql/score_{w["grain"]} "
                        f"params: pre_z={z_hi - PRE_Z_MARGIN}, naive_z={z_hi}; "
                        f"gates: z_hi={z_hi}, practical={config.practical(w['grain'])[metric]}, "
                        f"vol_floor={config.volume_floor(w['grain'])}",
            "result": json.dumps({
                "model_median_z": {k: (round(v, 2) if v is not None else None)
                                   for k, v in w["meds"].items()},
                "corroborating": w.get("corroborating", []),
            }),
            "decision": f"verdict={w['verdict']} -> status={STATUS[w['verdict']]}; "
                        f"{len(w.get('corroborating', []))} corroborating signal(s) attached",
            "duration_ms": 0,
        })

    print(f"{'incident_id':44s} {'status':20s} {'grain':5s} {'z':>7s} {'pct':>8s} corr")
    for i, w in zip(incidents, heads):
        print(f"{i['incident_id']:44s} {i['status']:20s} {w['grain']:5s} "
              f"{i['z_score']:7.1f} {i['pct_change']*100:7.1f}% {len(w.get('corroborating', []))}")
    if dry_run:
        print(f"\n[dry-run] would write {len(incidents)} incidents (run_id {run_id})")
    else:
        chdb.insert_rows("rca.incidents", incidents)
        chdb.insert_rows("rca.investigation_steps", steps)
        print(f"\nwrote {len(incidents)} incidents + detect steps (run_id {run_id})")
    return incidents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--z-hi", type=float, default=config.Z_HI)
    ap.add_argument("--grain", choices=["both", "hour", "day"], default="both")
    a = ap.parse_args()
    grains = ["hour", "day"] if a.grain == "both" else [a.grain]
    run(a.z_hi, grains, a.dry_run)


if __name__ == "__main__":
    main()
