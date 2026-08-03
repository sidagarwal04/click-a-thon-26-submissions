#!/usr/bin/env python3
"""LOCAL EXPERIMENT — engine v2: run_incident with four depth fixes, measured against the
fabricated datasets. Imports the team engine (v1) and overrides only detection/attribution;
report + bundle + evidence plumbing are reused verbatim. NOT for commit until validated.

Fixes over v1:
  F1 residual MAD    — MAD over same-weekday residuals, so weekday/weekend spread no longer
                       inflates the noise estimate for `requests` (v1 missed -15/-30% global drops).
  F2 dominance gate  — before declaring GLOBAL_UNLOCALIZED, check whether one candidate dwarfs
                       the group (top |rel| >= 2.5x group median): a -55% single segment bleeding
                       ~-15% into every dim is localized, not global.
  F3 peeling         — instead of labeling all co-candidates "correlated", PROVE it: re-measure
                       each candidate excluding the culprit's rows (one cube query). Deviation
                       persists -> it's an independent concurrent incident, investigated next.
  F4 deep scan       — additionally scan 2-D dimension pairs and recursively descend (up to 3-D)
                       while a sub-cell concentrates the drop >=1.4x and siblings are ~normal.
                       A pure 3-D incident is INVISIBLE to 1-D-first scanning (a -60% drop in a
                       0.6%-of-traffic cell dilutes to ~-4% at every 1-D parent, under MINREL).

  python run_incident_v2.py --db rca_t3 --json bundle.json
"""
import argparse, statistics as st, time, json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # import the root engine
import run_incident as v1
from run_incident import (METRICS, DIMS, SCAN_METRICS, MINVOL, Z, MINREL, MINCONTRIB,
                          _ord, _days, _group_by_window, group_windows, metric_total_vol,
                          env, connect, ensure_cube, report, build_bundle)

PAIR_DIMS = ["region", "country", "device_model", "os_version", "category", "ad_format"]
MINCONTRIB_DEEP = 0.002   # 2-D cells are small by construction; v1's 0.005 kills legit deep cells
# F5 (from the D2 frontier sweep): ratio-metric noise p95 is 0.3-1.7%, so MINREL=0.10 — not noise —
# was the binding miss cause at 6-9% drops. 0.05 is still ~5x the worst measured noise.
# PRECISION-FIRST (user directive 2026-08-01): never report a wrong anomaly, misses are
# acceptable. Every observed FP was a sub-10% ratio-metric finding — the 10% floor is the
# precision guard. (0.05 bought the 6-9% recall rungs at the cost of boundary FPs.)
MINRELS = {"requests": 0.10, "fill_rate": 0.10, "ecpm": 0.10}

MAX_PEEL = 5
MAX_DEPTH = 3

def _series(cx, db, metric, dims):
    """Per-(segment,day) series; dims may be 1 or 2 columns."""
    num, den = METRICS[metric]
    ds = f"sum({den})" if den else "toUInt64(0)"
    cols = ", ".join(dims)
    sel = (cols + ", ") if cols else ""
    grp = (cols + ", day") if cols else "day"
    rows = cx.query(f"SELECT {sel}day, toDayOfWeek(day) dow, sum({num}) n, {ds} d "
                    f"FROM {db}.cube GROUP BY {grp} ORDER BY {grp}").result_rows
    out = {}
    for r in rows:
        segvals, (day, dow, n, d) = r[:len(dims)], r[len(dims):]
        out.setdefault(tuple(zip(dims, map(str, segvals))), []).append((str(day), dow, n, d))
    return out

def candidates_for(cx, db, metric, dims):
    """v1's candidate logic + F1: MAD over residuals vs the (per-dow) baseline, not raw values."""
    num, den = METRICS[metric]; cands = []
    for filters, pts in _series(cx, db, metric, dims).items():
        vals = []
        for day, dow, n, d in pts:
            if den and not d: continue
            v = (n / d) if den else n; vol = d if den else n
            vals.append((day, dow, v, vol))
        if len(vals) < 5: continue
        # F6: robust multiplicative detrend (median week-over-week ratio via same-weekday pairs).
        # The +0.4%/day growth leaves +-3-6% residuals in a trend-blind weekday median (MAD 4.6%
        # of level on rca_t2), so a -15% global drop lands at z=2.9 — and a drop on the NEWEST,
        # highest-trend day is systematically under-measured (-10% planted read as -1.4%).
        byday = {day: v for day, _, v, _ in vals}
        o0 = _ord(vals[0][0])
        ratios = sorted(byday[d2] / byday[d1] for d1 in byday
                        if (d2 := _next7(d1)) in byday and byday[d1] > 0)
        # IQR-trimmed median: an anomaly window contaminates the ratios crossing its edges
        # (a 5-day suppression poisons 10/28 of them and fabricated a -2.1%/wk trend on a flat
        # CTR series, inflating MAD 79% and hiding the incident). A genuine trend keeps all
        # ratios clustered, so the trim preserves it.
        core = ratios[len(ratios) // 4: -(len(ratios) // 4) or None]
        wg = min(max(st.median(core), 0.9), 1.1) if len(ratios) >= 10 else 1.0   # stats-audit F5: short-slice guard
        trend = lambda day: wg ** ((_ord(day) - o0) / 7)
        dvals = [(day, dow, v / trend(day), vol) for day, dow, v, vol in vals]
        if metric == "requests":
            base = {}
            for _, dow, v, _ in dvals: base.setdefault(dow, []).append(v)
            base = {k: st.median(x) for k, x in base.items()}
            getbase = lambda dow: base[dow]
        else:
            med = st.median([v for _, _, v, _ in dvals]); getbase = lambda dow: med
        resid = [v - getbase(dow) for _, dow, v, _ in dvals]                    # F1
        mad = st.median([abs(r) for r in resid]) or 1e-9                        # F1
        flagged = []
        for day, dow, v, vol in dvals:
            b = getbase(dow)
            if not b or vol < MINVOL: continue
            z = 0.6745 * (v - b) / mad; rel = (v - b) / b
            if abs(z) > Z and abs(rel) > MINRELS[metric]: flagged.append((day, rel, vol, abs(z)))  # F5
        for lo, hi in group_windows([f[0] for f in flagged]):
            w = [f for f in flagged if lo <= f[0] <= hi]
            seg = (" × ".join(f"{d}={x}" for d, x in filters) if len(filters) > 1
                   else (filters[0][1] if filters else "(global)"))
            cands.append({"metric": metric, "dim": "×".join(d for d, _ in filters) or "__global__", "seg": seg,
                          "filters": list(filters), "win": (lo, hi),
                          "rel": st.mean([f[1] for f in w]), "vol": int(st.mean([f[2] for f in w])),
                          "snr": round(st.mean([f[3] for f in w]) / 0.6745, 1)})  # |dev| in MAD units
    return cands

def _next7(day):
    from datetime import date, timedelta
    y, m, d = map(int, day.split("-"))
    return str(date(y, m, d) + timedelta(days=7))

def _where(filters):
    return " AND ".join(f"{d}='{v}'" for d, v in filters)

def refine_deeper(cx, db, metric, filters, rel, win):
    """One more dimension concentrating the drop inside the current cell (v1's refine criteria)."""
    num, den = METRICS[metric]; lo, hi = win
    used = {d for d, _ in filters}
    for d2 in ["region", "os_version", "device_model", "category", "country", "ad_format"]:
        if d2 in used: continue
        rows = cx.query(f"""SELECT {d2} s2,
            sumIf({num}, day BETWEEN '{lo}' AND '{hi}') wn, {'sumIf('+den+", day BETWEEN '"+lo+"' AND '"+hi+"')" if den else '0'} wd,
            sumIf({num}, NOT(day BETWEEN '{lo}' AND '{hi}')) bn, {'sumIf('+den+", NOT(day BETWEEN '"+lo+"' AND '"+hi+"'))" if den else '0'} bd
            FROM {db}.cube WHERE {_where(filters)} GROUP BY s2""").result_rows
        cells = []
        for s2, wn, wd, bn, bd in rows:
            if den:
                if not wd or not bd: continue
                wv, bv, vol = wn / wd, bn / bd, wd
            else:
                wv, bv, vol = wn, bn, wn
            r = (wv - bv) / bv if bv else 0; cells.append((s2, r, vol))
        if len(cells) < 2: continue
        # direction-aware: descend toward the candidate's own sign (a +6% spike must not
        # "refine" into an unrelated -3% cell) and the cell must itself clear the rel gate
        worst = (min if rel < 0 else max)(cells, key=lambda c: c[1])
        rest = [c for c in cells if c[0] != worst[0]]
        rest_rel = st.mean([c[1] for c in rest]) if rest else 0
        deeper_ok = worst[1] < rel * 1.4 if rel < 0 else worst[1] > rel * 1.4
        if deeper_ok and abs(worst[1]) >= MINRELS[metric] and abs(rest_rel) < 0.10 and worst[2] > MINVOL:
            return (d2, str(worst[0]), worst[1], worst[2])
    return None

def descend(cx, db, metric, cand):
    """F4: recursive root-cause descent from any candidate, up to MAX_DEPTH dims."""
    filters = list(cand.get("filters") or [(cand["dim"], cand["seg"])])
    rel, vol, changed = cand["rel"], cand["vol"], False
    while len(filters) < MAX_DEPTH:
        nxt = refine_deeper(cx, db, metric, filters, rel, cand["win"])
        if not nxt: break
        filters.append((nxt[0], nxt[1])); rel, vol = nxt[2], nxt[3]; changed = True
    if not changed: return None
    return {"seg": " × ".join(f"{d}={v}" for d, v in filters),
            "dim": "×".join(d for d, _ in filters), "rel": rel, "vol": int(vol), "filters": filters}

def excl_rel(cx, db, metric, cand, culprit_filters):
    """F3: candidate's deviation EXCLUDING the culprit's rows. Baseline = MEDIAN of daily values
    outside the window — a sum-baseline is contaminated by OTHER incidents' windows and produced
    fake +5% residuals that let clean candidates survive peeling (seen on rca_e2e)."""
    num, den = METRICS[metric]; lo, hi = cand["win"]
    where = _where(cand.get("filters") or [(cand["dim"], cand["seg"])])
    excl = _where(culprit_filters)
    ds = f"sum({den})" if den else "toUInt64(0)"
    rows = cx.query(f"SELECT day, toDayOfWeek(day) dow, sum({num}) n, {ds} d FROM {db}.cube "
                    f"WHERE {where} AND NOT({excl}) GROUP BY day").result_rows
    win_dows = set(); wn = wd = 0; brows = []
    for day, dow, n, d in rows:
        day = str(day)
        if den and not d: continue
        if lo <= day <= hi: wn += n; wd += (d if den else 1); win_dows.add(dow)
        else: brows.append((dow, (n / d) if den else n))
    # stats-audit F6: requests baseline must be weekday-matched or a weekend window
    # reads as a fake -23% "independent incident" against the bimodal daily volumes
    base = [v for dow, v in brows if den or dow in win_dows] or [v for _, v in brows]
    if len(base) < 5 or not (wd if den else wn): return None, 0
    ndw = len(_days(lo, hi))
    wv = (wn / wd) if den else wn / ndw
    bv = st.median(base)
    if not bv: return None, 0
    return (wv - bv) / bv, (wd / ndw if den else wv)

def scan(cx, db):
    incidents = []; false_pos = []
    for metric in SCAN_METRICS:
        allc = []
        dims = [d for d, rs in DIMS.items() if rs or metric in ("ctr", "ecpm")]
        for dim in dims:
            allc.extend(candidates_for(cx, db, metric, [dim]))
        allc.extend(candidates_for(cx, db, metric, []))   # global-series candidate for EVERY metric:
                                                          # a -4.5% global ratio event flags <12 segments
                                                          # with P=0.73 and would misreport as LOCALIZED
        deep = []
        if metric != "requests":                                                # F4 pair scan
            pool = [d for d in PAIR_DIMS if d in dims]
            for i in range(len(pool)):
                for j in range(i + 1, len(pool)):
                    deep.extend(candidates_for(cx, db, metric, [pool[i], pool[j]]))
        for c in allc + deep:
            tot = metric_total_vol(cx, db, metric, *c["win"])
            c["contrib"] = (c["vol"] * len(_days(*c["win"])) / tot) * abs(c["rel"])
        allc = [c for c in allc if c["contrib"] >= MINCONTRIB]
        # keep only 2-D candidates NOT already explained by a flagged 1-D parent
        for c in deep:
            if c["contrib"] < MINCONTRIB_DEEP: continue
            parents = [p for p in allc if len(p["filters"]) == 1 and p["filters"][0] in c["filters"]
                       and not (c["win"][1] < p["win"][0] or c["win"][0] > p["win"][1])]
            if not parents or all(abs(c["rel"]) >= 1.4 * abs(p["rel"]) for p in parents):
                allc.append(c)
        if not allc: continue
        for grp in _group_by_window(allc):
            grp.sort(key=lambda c: -abs(c["rel"]) * c["vol"])
            remaining, peel = grp, 0
            while remaining and peel < MAX_PEEL:
                peel += 1
                remaining.sort(key=lambda c: -abs(c["rel"]) * c["vol"])   # audit F8: re-rank each peel
                g = next((c for c in remaining if c["dim"] == "__global__"), None)
                if peel == 1 and g:
                    loc = [c for c in remaining if c["dim"] != "__global__"]
                    if not loc or max(abs(c["rel"]) for c in loc) < 2.5 * abs(g["rel"]):
                        incidents.append({"metric": metric, "win": g["win"], "verdict": "GLOBAL_UNLOCALIZED",
                                          "culprit": None, "rel": g["rel"]})
                        break
                remaining = [c for c in remaining if c["dim"] != "__global__"]
                if not remaining: break
                # uniformity/dominance judged on 1-D candidates only: pair cells are derived
                # views of the same mass and inflate the median (real INC-B went "global" off 15
                # finance-adjacent pair cells) — they stay in `remaining` for descent/peeling
                oneD = [c for c in remaining if len(c.get("filters") or [0]) == 1] or remaining
                mx = max(oneD, key=lambda c: abs(c["rel"]))
                dominant = abs(mx["rel"]) >= 2.5 * st.median([abs(c["rel"]) for c in oneD])       # F2
                # within the dominant cluster (rels within ~15% of max) prefer volume: the parent
                # (region=LATAM -44.8%, vol 48k) must beat its own child (country=MX -45.1%, 12k)
                cluster = [c for c in oneD if abs(c["rel"]) >= abs(mx["rel"]) / 1.15]
                top = max(cluster, key=lambda c: abs(c["rel"]) * c["vol"]) if dominant else remaining[0]
                dims_hit = {c["dim"] for c in oneD}
                if peel == 1 and len(oneD) >= 12 and len(dims_hit) >= 4 and not dominant:
                    incidents.append({"metric": metric, "win": top["win"], "verdict": "GLOBAL_UNLOCALIZED",
                                      "culprit": None, "rel": st.mean([c["rel"] for c in remaining])})
                    break
                deeper = descend(cx, db, metric, top)
                if deeper:
                    culprit, verdict = deeper, f"LOCALIZED_{len(deeper['filters'])}D"
                    false_pos.append({**top, "why": f"dilution — explained by {deeper['seg']}"})
                else:
                    culprit = top
                    verdict = f"LOCALIZED_{len(top.get('filters') or [0])}D"
                incidents.append({"metric": metric, "win": top["win"], "verdict": verdict, "culprit": culprit})
                cf = culprit.get("filters") or [(culprit["dim"], culprit["seg"])]
                nxt = []
                for c in remaining:                                       # audit F1: [1:] skipped the
                    if c is top: continue                                 # head when dominant top != head
                    r, vol = excl_rel(cx, db, metric, c, cf)                    # F3
                    if r is None or vol < MINVOL or abs(r) < MINRELS[metric]:
                        false_pos.append({**c, "why": f"explained by {culprit['seg']} "
                                          f"(residual {'-' if r is None else f'{r*100:+.1f}%'} outside it)"})
                    else:
                        nxt.append({**c, "rel": r, "vol": int(vol)})      # audit F8: refresh vol too
                remaining = nxt
            for c in remaining:                                           # audit F3: peel-cap leftovers
                false_pos.append({**c, "why": "peel budget exhausted — unverified, needs manual look"})
    def _fset(i):
        c = i.get("culprit") or {}
        return set(c.get("filters") or ([(c["dim"], c["seg"])] if c else []))
    fills = [i for i in incidents if i["metric"] == "fill_rate" and i.get("culprit")]
    keep = []
    for i in incidents:
        c = i.get("culprit")
        if i["metric"] == "ecpm" and c and abs(c["rel"]) < 0.10:
            parent = next((f for f in fills
                           if not (i["win"][1] < f["win"][0] or i["win"][0] > f["win"][1])
                           and _fset(i) & _fset(f)
                           and abs(f["culprit"]["rel"]) >= 3 * abs(c["rel"])), None)
            if parent:
                false_pos.append({**c, "metric": "ecpm", "win": i["win"],
                                  "why": f"derived mix shift of fill_rate incident at {parent['culprit']['seg']}"})
                continue
        keep.append(i)
    return keep, false_pos

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default="rca")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--rebuild-cube", action="store_true")
    ap.add_argument("--recall", action="store_true",
                    help="recall mode: ratio floor 0.05 — the 5-10%% band is emitted for LLM "
                         "adjudication (adjudicate.py) instead of silent suppression")
    a = ap.parse_args()
    if a.recall:
        MINRELS["fill_rate"] = MINRELS["ecpm"] = 0.05
    t0 = time.time(); cfg = env(); cx = connect(cfg); ensure_cube(cx, a.db, a.rebuild_cube)
    inc, fp = scan(cx, a.db); report(inc, fp, a.db)
    if a.json:
        bundle = build_bundle(cx, a.db, inc, fp, time.time() - t0)
        by_win = {(i["metric"], tuple(i["win"])): (i.get("culprit") or {}).get("snr") for i in inc}
        for inv in bundle["investigations"]:   # signal-to-noise passthrough for the adjudicator
            snr = by_win.get((inv["metric"], tuple(inv["window"])))
            if snr and inv.get("culprit"): inv["culprit"]["snr"] = snr
        json.dump(bundle, open(a.json, "w"), indent=2, default=str)
        print(f"  bundle → {a.json}  ({len(bundle['investigations'])} investigations)\n")
