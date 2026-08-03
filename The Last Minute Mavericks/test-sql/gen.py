#!/usr/bin/env python3
"""Generate a small, self-contained test slice with PLANTED anomalies + a ground-truth answer key.

  python test-sql/gen.py test-sql/test1          # -> dataset.csv (10,000 rows) + answers.json

Why cube rows and not raw events: the engine scans `{db}.cube` (day × segment aggregates) and gates
every segment at 1500 requests/day. 10,000 raw events would be invisible to it. So one "record" here
is one cube row — 25 audience bases × 5 ad formats × 40 days × 2 rows (unfilled / filled) = exactly
10,000 rows standing in for ~2M requests/day. Same columns, same statistical profile as
teamkit/docs/DATA.md (fill 78.1%, render 98.0%, CTR 1.088% of impressions, eCPM ~2.47, weekends
-20%, +0.3%/day trend).

Two rows per (base, format, day) is not padding — it is the real schema. `vertical`/`campaign_type`
come from the advertiser, which is NULL on an unfilled request, so unfilled and filled events of the
same segment land in different cube rows. On the filled row requests == fills by construction.

Every base serves ALL FIVE formats. That is the one structural detail that matters: format is the
dominant eCPM driver (banner 1.3 -> rewarded 3.9), so if a base carried a single format, any
fill-rate incident would yank the format mix of every thin 2-D cell it touches and manufacture
double-digit phantom eCPM moves. Measured: with one format per base, test1's LATAM fill drop alone
produced 4 phantom eCPM cells at -12%..+8%. With all five, the residual mix shift is ~1.7% — under
the detector's 5% floor, which is where a mix artifact belongs.

Anomalies are injected on the funnel, never on the ratio directly, so the identity
requests × fill_rate × render_rate × ecpm/1000 ≡ revenue/day still holds exactly:
  fill_rate drop -> fills (and its downstream impressions/clicks/revenue) shrink; requests untouched
  ecpm drop     -> revenue shrinks; impressions untouched
  requests drop -> every counter scales together, so all ratios stay put

The answer key records the deviation MEASURED from the generated rows under the engine's own
like-for-like baseline (same weekdays, 3 preceding weeks, other incident windows excluded), so
test-sql/verify.py can grade the reported magnitude, not just "did it notice".
"""
import argparse, csv, json, math, random
from datetime import date, timedelta
from pathlib import Path

COLS = ["day", "region", "country", "device_model", "os_version", "category", "publisher_tier",
        "vertical", "campaign_type", "ad_format",
        "requests", "fills", "impressions", "clicks", "revenue"]

# The audience grid: 6 geo slots × 4 devices = 24 bases, + 1 reserved low-volume base. Weights are
# shares of daily requests and each list sums to 1.0, so a base's share is geo_w × device_w.
GEO_SLOTS = [("NAM", "US", 0.24), ("EU", "DE", 0.15), ("EU", "UK", 0.13),
             ("APAC", "IN", 0.22), ("LATAM", "BR", 0.15), ("LATAM", "MX", 0.11)]
DEVICES   = [("iPhone 15", ["iOS 17.5", "iOS 18.1"], 0.32),
             ("Pixel 8", ["Android 14", "Android 15"], 0.20),
             ("Galaxy S24", ["Android 14", "Android 15"], 0.26),
             ("Redmi Note 12", ["Android 14", "Android 15"], 0.22)]
CATS   = ["gaming", "social", "news", "finance", "ecommerce"]
TIERS  = ["tier_1", "tier_2", "tier_3"]
VERTS  = ["gaming", "finance", "travel", "cpg"]
CTYPES = ["CPM", "CPC", "CPI"]
FMT_CPM = {"banner": 1.3, "native": 1.8, "interstitial": 2.4, "video": 3.3, "rewarded": 3.9}
FMT_MIX = {"banner": 0.24, "native": 0.20, "interstitial": 0.20, "video": 0.18, "rewarded": 0.18}
FILL, RENDER, CTR = 0.781, 0.980, 0.01088     # DATA.md global rates
CONTROL = {"region": "MEA", "country": "AE", "device_model": "iPhone 15", "os_version": "iOS 18.1",
           "category": "gaming", "publisher_tier": "tier_3", "vertical": "travel",
           "campaign_type": "CPI"}
BASE_DIMS = list(CONTROL)
BASE_WEEKS = 3                                # must match run_incident.BASE_WEEKS

# ── audience bases: an orthogonal design, not a random sample ──────────────────────────────────
# Every base is a UNIQUE combination of 8 dimensions, so if the bases are drawn at random the
# dimensions come out correlated — with only 24 of them, `region=LATAM` ends up being exactly the
# 3 categories, 3 tiers and 3 verticals its bases happen to carry. Drop LATAM's fill and all 15 of
# those values move by the same -45%: nothing is dominant, and the engine correctly answers
# GLOBAL_UNLOCALIZED. That is a broken fixture, not a broken detector (measured: it cost 2 of 3
# localizations). So geo × device is a full grid and the remaining dims rotate Latin-square style
# over it — each category/tier/vertical then spans several regions and several devices, and a
# region-wide drop shows -45% at the region and only ~-11% anywhere else.
def make_bases(spec, rng):
    n = len(GEO_SLOTS) * len(DEVICES) + 1
    if spec.get("bases", n) != n:
        raise SystemExit(f"spec bases={spec['bases']} but the grid yields {n}")
    bases = []
    for i, (region, country, gw) in enumerate(GEO_SLOTS):
        for j, (device, oses, dw) in enumerate(DEVICES):
            bases.append(_base(rng, region=region, country=country, device_model=device,
                               os_version=oses[(i + j) % 2],
                               category=CATS[(i + 2 * j) % len(CATS)],
                               publisher_tier=TIERS[(i + j) % len(TIERS)],
                               vertical=VERTS[(2 * i + j) % len(VERTS)],
                               campaign_type=CTYPES[(i + 2 * j) % len(CTYPES)], weight=gw * dw))
    ctl = _base(rng, weight=0.0, **CONTROL)
    ctl["reserved"] = True
    ctl["fixed"] = next((i.get("control_volume_per_day", 900) for i in spec["incidents"]
                         if i.get("expect") == "suppressed" and i["dim"] == "country"), 900)
    bases.append(ctl)
    return bases

def _base(rng, weight, **dims):
    """Per-base rates. The spreads are small on purpose: a base is a whole audience, not a user, so
    its fill/eCPM sits near the global rate. Wide spreads would swamp a planted 5% move in noise."""
    p = dict(dims, weight=weight * math.exp(rng.gauss(0, 0.12)), fixed=None,
             fill=min(max(rng.gauss(FILL, 0.04), 0.60), 0.92),
             render=min(max(rng.gauss(RENDER, 0.005), 0.95), 0.995),
             ctr=max(rng.gauss(CTR, 0.0012), 0.004),
             cpm_mult=math.exp(rng.gauss(0, 0.10)))
    mix = {f: FMT_MIX[f] * math.exp(rng.gauss(0, 0.20)) for f in FMT_CPM}
    s = sum(mix.values()); p["mix"] = {f: w / s for f, w in mix.items()}
    return p

def pred_dims(inc):
    out = [] if inc["dim"] == "__global__" else [(inc["dim"], inc["value"])]
    if inc.get("co_dim"): out.append((inc["co_dim"], inc["co_value"]))
    return out

def _hits(p, dims): return all(p.get(d) == v for d, v in dims)

def check_findable(spec, bases):
    """Refuse to ship a slice whose planted segment is too small for the engine's own floors
    (volume >= 1500/day, contribution = share × |deviation| >= 0.5%). Better a loud generator error
    than a test that reports a miss the detector was never given a fair chance at."""
    tot = sum(p["weight"] for p in bases)
    for inc in spec["incidents"]:
        if inc.get("expect") == "suppressed" or inc["dim"] == "__global__": continue
        dims = [(d, v) for d, v in pred_dims(inc) if d in BASE_DIMS]
        share = (sum(p["weight"] for p in bases if _hits(p, dims)) / tot) if dims else 1.0
        if "ad_format" in [d for d, _ in pred_dims(inc)]:
            share *= FMT_MIX[dict(pred_dims(inc))["ad_format"]]
        vol = share * spec["daily_requests"]
        if vol < 5000 or share * inc["drop"] < 0.01:
            raise SystemExit(f"{inc['id']}: segment is {share:.1%} of traffic ({vol:,.0f} req/day) — "
                             f"too small to be findable; widen it or raise the drop")

# ── incidents ──────────────────────────────────────────────────────────────────────────────────
def eff_drop(inc, day):
    """0 outside the window; the full drop inside it — or a linear ramp-in for shape='ramp'."""
    lo, hi = inc["win"]
    if not (lo <= day <= hi): return 0.0
    if inc.get("shape") != "ramp": return inc["drop"]
    n = (date.fromisoformat(hi) - date.fromisoformat(lo)).days + 1
    i = (date.fromisoformat(day) - date.fromisoformat(lo)).days
    return inc["drop"] * (i + 1) / n

def generate(spec):
    rng = random.Random(spec["seed"])
    bases = make_bases(spec, rng)
    check_findable(spec, [p for p in bases if not p.get("reserved")])
    pool = [p for p in bases if not p.get("reserved")]
    tot_w = sum(p["weight"] for p in pool)
    for p in pool: p["base"] = spec["daily_requests"] * p["weight"] / tot_w
    for p in bases:
        if p.get("reserved"): p["base"] = float(p["fixed"])

    day0 = date.fromisoformat(spec["day0"]); rows = []
    for t in range(spec["days"]):
        d = day0 + timedelta(days=t); ds = d.isoformat()
        season = (spec["weekend_factor"] if d.isoweekday() in (6, 7) else 1.0) * \
                 (1.0 + spec["growth_per_day"]) ** t
        for p in bases:
            for fmt, share in p["mix"].items():
                seg = {**{k: p[k] for k in BASE_DIMS}, "ad_format": fmt}
                r = p["base"] * share * season * math.exp(rng.gauss(0, 0.02))
                r = max(20, int(round(r + rng.gauss(0, math.sqrt(r)))))
                f = p["fill"]
                for inc in spec["incidents"]:
                    if inc["metric"] == "fill_rate" and _hits(seg, pred_dims(inc)):
                        f *= (1 - eff_drop(inc, ds))
                fills = min(r, max(0, int(round(r * f + rng.gauss(0, math.sqrt(max(r * f * (1 - f), 1)))))))
                imp = min(fills, max(0, int(round(fills * p["render"] +
                                                 rng.gauss(0, math.sqrt(max(fills * 0.02, 1)))))))
                clk = min(imp, max(0, int(round(imp * p["ctr"] +
                                               rng.gauss(0, math.sqrt(max(imp * p["ctr"], 1)))))))
                rev = imp * FMT_CPM[fmt] * p["cpm_mult"] / 1000.0 * math.exp(rng.gauss(0, 0.01))
                for inc in spec["incidents"]:
                    if inc["metric"] == "ecpm" and _hits(seg, pred_dims(inc)):
                        rev *= (1 - eff_drop(inc, ds))
                    # ctr moves clicks ONLY — in a CPM model clicks buy nothing, which is exactly
                    # why a ctr incident is a control: no scanned metric can see it.
                    if inc["metric"] == "ctr" and _hits(seg, pred_dims(inc)):
                        clk = int(clk * (1 - eff_drop(inc, ds)))
                for inc in spec["incidents"]:             # scale the whole funnel -> ratios unchanged
                    if inc["metric"] == "requests" and _hits(seg, pred_dims(inc)):
                        k = 1 - eff_drop(inc, ds)
                        r, fills, imp, clk, rev = int(r * k), int(fills * k), int(imp * k), int(clk * k), rev * k
                head = [ds, p["region"], p["country"], p["device_model"], p["os_version"],
                        p["category"], p["publisher_tier"]]
                rows.append(head + ["", "", fmt, r - fills, 0, 0, 0, 0.0])
                rows.append(head + [p["vertical"], p["campaign_type"], fmt,
                                    fills, fills, imp, clk, round(rev, 6)])
    return rows, bases

# ── ground truth ───────────────────────────────────────────────────────────────────────────────
IDX = {c: i for i, c in enumerate(COLS)}
NUMDEN = {"requests": ("requests", None), "fill_rate": ("fills", "requests"),
          "ecpm": ("revenue", "impressions"), "ctr": ("clicks", "impressions")}

def baseline_days(all_days, win, other_wins):
    """Mirrors run_incident.baseline_days: same weekdays as the window, the 3 preceding weeks,
    window excluded, days belonging to ANOTHER incident dropped (contamination exclusion)."""
    lo, hi = win
    dows = {date.fromisoformat(d).isoweekday()
            for d in all_days if lo <= d <= hi}
    same = [d for d in all_days if date.fromisoformat(d).isoweekday() in dows and not (lo <= d <= hi)]
    clean = [d for d in same if not any(a <= d <= b for a, b in other_wins if b < lo or a > hi)]
    if len(clean) >= len(dows): same = clean
    prior = [d for d in same if d < lo]
    n = BASE_WEEKS * len(dows)
    return prior[-n:] if len(prior) >= len(dows) else same[:n]

def measure(rows, inc, other_wins):
    """The deviation an ideal analyst would report: window sum/sum vs the like-for-like baseline."""
    dims = pred_dims(inc); num, den = NUMDEN[inc["metric"]]
    lo, hi = inc["win"]; all_days = sorted({r[0] for r in rows})
    base = set(baseline_days(all_days, inc["win"], other_wins))
    wn = wd = bn = bd = 0.0; wdays, bdays = set(), set()
    for r in rows:
        if not all(r[IDX[d]] == v for d, v in dims): continue
        inw = lo <= r[0] <= hi
        if not inw and r[0] not in base: continue
        n = r[IDX[num]]; dv = r[IDX[den]] if den else 1
        if inw: wn += n; wd += dv; wdays.add(r[0])
        else:   bn += n; bd += dv; bdays.add(r[0])
    if den:
        if not wd or not bd: return None, 0.0
        wv, bv = wn / wd, bn / bd
    else:
        if not wdays or not bdays: return None, 0.0
        wv, bv = wn / len(wdays), bn / len(bdays)
    vol = (wd / len(wdays)) if den else (wn / len(wdays))
    return (((wv - bv) / bv) if bv else None), vol

def answers(spec, rows):
    real = [tuple(i["win"]) for i in spec["incidents"] if i.get("expect") != "suppressed"]
    tot = {}
    for r in rows:
        tot[r[0]] = tot.get(r[0], 0) + r[IDX["requests"]]
    out = []
    for inc in spec["incidents"]:
        others = [w for w in real if w != tuple(inc["win"])]
        dev, vol = measure(rows, inc, others)
        days = (date.fromisoformat(inc["win"][1]) - date.fromisoformat(inc["win"][0])).days + 1
        share = vol / (sum(tot.values()) / len(tot)) if inc["metric"] != "ecpm" else None
        out.append({k: inc[k] for k in ("id", "metric", "dim", "value", "win", "drop", "why")
                    if k in inc} |
                   {k: inc[k] for k in ("co_dim", "co_value", "shape") if k in inc} |
                   {"expect": inc.get("expect", "detected"), "window_days": days,
                    "expected_deviation_pct": None if dev is None else round(dev * 100, 2),
                    "segment_volume_per_day": round(vol),
                    "segment_request_share": None if share is None else round(share, 4)})
    return {"name": spec["name"], "database": spec["database"], "rows": len(rows),
            "days": spec["days"], "seed": spec["seed"],
            "baseline_rule": f"same weekdays, {BASE_WEEKS} preceding weeks, window + other incident "
                             "windows excluded (identical to run_incident.baseline_days)",
            "quarantine": "engine/agent/UI code must never read this file — only test-sql/verify.py, "
                          "after the scan has already produced its bundle.",
            "incidents": out}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="test-sql/test1 | test-sql/test2")
    a = ap.parse_args()
    folder = Path(a.folder).resolve()
    spec = json.load(open(folder / "spec.json"))
    rows, bases = generate(spec)
    with open(folder / "dataset.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(COLS); w.writerows(rows)
    ans = answers(spec, rows)
    json.dump(ans, open(folder / "answers.json", "w"), indent=2)
    req = sum(r[IDX["requests"]] for r in rows); fills = sum(r[IDX["fills"]] for r in rows)
    imp = sum(r[IDX["impressions"]] for r in rows); rev = sum(r[IDX["revenue"]] for r in rows)
    print(f"\n {spec['name']} -> {folder}")
    print(f"  dataset.csv   {len(rows):,} rows · {spec['days']} days · {len(bases)} bases × "
          f"{len(FMT_CPM)} formats × 2 (unfilled/filled)")
    print(f"  represents    {req:,} requests · fill {fills/req:.3f} · render {imp/fills:.3f} · eCPM {rev/imp*1000:.3f}")
    print(f"  answers.json  {len(ans['incidents'])} planted "
          f"({sum(i['expect']=='detected' for i in ans['incidents'])} to find, "
          f"{sum(i['expect']=='suppressed' for i in ans['incidents'])} to ignore)")
    for i in ans["incidents"]:
        seg = "(global)" if i["dim"] == "__global__" else f"{i['dim']}={i['value']}"
        if i.get("co_dim"): seg += f" × {i['co_dim']}={i['co_value']}"
        print(f"    {i['id']:<6} {i['metric']:<9} {seg:<40} {i['win'][0]}..{i['win'][1]}  "
              f"{i['expected_deviation_pct']:>7}%  vol/day {i['segment_volume_per_day']:>9,}  [{i['expect']}]")
    print()

if __name__ == "__main__":
    main()
