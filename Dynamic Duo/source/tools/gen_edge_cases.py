#!/usr/bin/env python3
"""Deterministic edge-case data generator — the regression fixture for the RCA agent.

Synthesises an ad_events slice shaped like the InMobi feed (real dim ids, real
diurnal + weekly seasonality, real per-format funnel rates measured from `main`)
with known anomalies planted on known days. Every scenario declares the verdict the
agent MUST reach, so the output doubles as a regression oracle: generate -> load ->
sweep -> prefill -> compare (tools/regress_edge_cases.py).

BUILT FOR THE UNSEEN INCIDENT. Two properties matter more than the specific
anomalies below:

1. `--randomize-targets` re-rolls WHICH segment each scenario hits (a random
   os_version / country / device_model / vertical, drawn from the dim tables). The
   mechanisms stay fixed, the targets move. If the agent only ever finds
   "Android 15" it is tuned to the build data and will fail on release day. Run at
   least one randomized seed before submitting.
2. Seasonality is tested in BOTH directions, because the expensive failure is not a
   missed anomaly, it is alarming on a normal Sunday:
     - negative: clean weekends and the 00:00-05:00 diurnal trough must produce NO
       incident, though volume there is -19% and -32% against a flat average
     - positive: a real collapse planted ON the lowest-traffic day (S15) must still
       be caught, and the same numeric move on a WEEKDAY (S16) must be flagged
   A flat-average baseline passes neither pair. Only a same-weekday baseline does.

Deterministic: same --seed produces byte-identical CSVs, so a run is replayable and
a diff in agent behaviour is never a diff in the data.

    python3 tools/gen_edge_cases.py --out-dir /tmp/edge
    python3 tools/gen_edge_cases.py --out-dir /tmp/edge2 --seed 7 --randomize-targets
    -> edge_events.csv        35 days, 16 planted scenarios (baseline path)
    -> edge_short_events.csv   4 days, no history            (peer path)
    -> edge_manifest.json      resolved targets + expected verdict per scenario

Day layout keeps >=2 clean same-weekday days behind every incident (q1 needs
min_clean_days >= 2 or it drops to the peer path): weeks 1-2 are entirely clean and
carry the baselines, weeks 3-5 hold the anomalies, at most 3 per weekday slot.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from datetime import date, datetime, timedelta

# ── measured from the loaded `main` dataset (9M events, 2026-06-01..07-05) ──────
HOUR_FACTOR = [0.684, 0.695, 0.737, 0.801, 0.885, 0.981, 1.080, 1.179,
               1.239, 1.240, 1.238, 1.244, 1.240, 1.242, 1.243, 1.241,
               1.180, 1.082, 0.977, 0.879, 0.798, 0.736, 0.696, 0.683]
WEEKDAY_FACTOR = [1.073, 1.075, 1.079, 1.060, 1.030, 0.870, 0.813]   # 0 = Monday

# Per-segment structure measured from `main`. WITHOUT these the slice is flat on
# every dimension except ad_format, and the flatness itself is a step change against
# the parent universe: the first sweep produced ~20 false incidents, nearly all
# `revenue:country=*` / `ecpm:country=*`, because every country's eCPM converged to
# the global mean (NG +118%, US -32% at the boundary). A fixture must inherit the
# real cross-sectional structure, not just the real marginals.
ECPM_BY_COUNTRY = {"AE": 0.4602, "AR": 0.5501, "BR": 0.5501, "CA": 1.4678, "DE": 1.1937,
                   "ES": 1.1921, "FR": 1.1924, "ID": 0.6429, "IN": 0.6424, "JP": 0.6433,
                   "MX": 0.5510, "NG": 0.4578, "PH": 0.6441, "UK": 1.1932, "US": 1.4700,
                   "ZA": 0.4585}
FILL_BY_TIER = {"tier_1": 1.1619, "tier_2": 1.0352, "tier_3": 0.8561}
# region / category / vertical / ecpm-by-tier all measured within 1% of 1.0 — omitted
# deliberately rather than modelled as noise.

FORMATS = {
    "banner":       {"share": 0.348, "fill": 0.8184, "render": 0.9800, "ctr": 0.00595, "ecpm": 0.869},
    "native":       {"share": 0.261, "fill": 0.7885, "render": 0.9800, "ctr": 0.00986, "ecpm": 1.977},
    "interstitial": {"share": 0.174, "fill": 0.7692, "render": 0.9797, "ctr": 0.01174, "ecpm": 2.683},
    "video":        {"share": 0.130, "fill": 0.7089, "render": 0.9801, "ctr": 0.01749, "ecpm": 6.518},
    "rewarded":     {"share": 0.087, "fill": 0.7394, "render": 0.9801, "ctr": 0.02468, "ecpm": 4.888},
}

START_DATE = date(2026, 7, 6)      # Monday, continues straight on from `main`
N_DAYS = 35
# MUST match the parent universe's daily volume (main = 9M/35d = 257,143). The
# rollup has no `dataset` column and detector/sweep.py does not filter by dataset
# (only the agent's runner does), so main + this slice are ONE continuous timeline
# to detection. Generating at a different scale makes every day of the slice read
# as a step change in requests against main's baselines, and the resulting false
# incidents swamp the real ones. Also keeps every os_version segment far above the
# 10K-requests-in-window trust floor.
REQ_PER_DAY = 257_143
SHORT_START = date(2026, 8, 17)
SHORT_DAYS = 4

# Days with NO anomaly whatsoever. Their volume is naturally -13%/-19% (weekend) and
# the 00:00-05:00 hours run -32% against a flat mean. Any incident on these days is a
# false positive and fails the regression.
SEASONAL_CLEAN_DAYS = [5, 6, 12, 13]

# ── scenarios ──────────────────────────────────────────────────────────────────
# target: (dim, default_value) — value is re-rolled under --randomize-targets.
SCENARIOS = [
    dict(id="S01", day=14, kind="fill_segment", target=("os_version", "Android 15"),
         name="single-dimension fill collapse",
         edge_case="The baseline case: one segment's own rate steps down.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="fill_rate"),
    dict(id="S02", day=15, kind="global_volume", target=(None, None),
         name="uniform global request drop",
         edge_case="Every segment moves together — no segment explains >=50%. The agent "
                   "must NOT force-name a scapegoat segment.",
         expect_verdict="GLOBAL_MOVEMENT", expect_metric="requests"),
    dict(id="S03", day=16, kind="mix_shift", target=("ad_format", "video"),
         name="mix shift, no rate change",
         edge_case="Traffic reshuffles toward a naturally weaker ad_format. Global fill "
                   "falls while EVERY segment's own fill is flat. A naive sweep reads "
                   "'uniform' and would say GLOBAL; the Kitagawa split must catch that "
                   "the mix term dominates.",
         expect_verdict="MIX_SHIFT", expect_metric="fill_rate"),
    dict(id="S04", day=17, kind="interaction", target=("os_version", "Android 14"),
         target2=("region", "EU"),
         name="interaction segment (os_version x region)",
         edge_case="Cause is the CROSS of two dimensions, not either alone. Single-dim "
                   "sweeps see a partial signal on both and confounder-elimination "
                   "shrinks but never clears the residual.",
         expect_verdict="INTERACTION", expect_metric="fill_rate"),
    dict(id="S05", day=18, kind="demand_pullout", target=("vertical", "finance"),
         name="advertiser demand pullout",
         edge_case="A vertical stops bidding. fill_rate BY vertical is undefined "
                   "(unfilled rows carry no advertiser), so the ratio sweep is "
                   "structurally blind — only a volume sweep on fills finds it.",
         expect_verdict="DEMAND_PULLOUT", expect_metric="fill_rate"),
    dict(id="S06", day=19, kind="ctr_spike", target=("country", "ID"),
         name="CTR spike (click fraud), revenue flat",
         edge_case="An UP move, not a drop — thresholds must be abs(). Revenue stays "
                   "flat, so it is not a monetisation win; the narrative must not read "
                   "it as good news.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="ctr"),
    dict(id="S07", day=20, kind="partial_day", target=("country", "PH"),
         name="partial-day onset (08:00-17:00 only)",
         edge_case="Measured across the whole calendar day the move dilutes below "
                   "threshold; the window must follow detection's hour buckets, not "
                   "the date.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="fill_rate"),
    dict(id="S08", day=21, kind="unknown_dim", target=("os_version", "unknown"),
         name="unseen dimension values (dictionary miss)",
         edge_case="New geo_device_ids absent from the dim table. dictGetOrDefault "
                   "sends them to the 'unknown' bucket; an inner join would silently "
                   "DROP the very rows that moved. Closest analogue to release-day "
                   "data carrying values we have never seen.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="fill_rate"),
    dict(id="S09", day=22, kind="two_incidents", target=("device_model", "Pixel 7"),
         target2=("campaign_type", "CPC"),
         name="two independent simultaneous incidents",
         edge_case="Two unrelated levers move on the same day (a fill collapse and an "
                   "eCPM drop). Diagnosing one must not close the other.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="fill_rate"),
    dict(id="S10", day=23, kind="ingestion_gap", target=(None, None),
         name="ingestion gap (zero events 02:00-06:00)",
         edge_case="Absence of data is itself a finding. A volume 'drop' that is really "
                   "a pipeline hole must not be attributed to a segment.",
         expect_verdict="GLOBAL_MOVEMENT", expect_metric="requests"),
    dict(id="S11", day=24, kind="ecpm_drop", target=("campaign_type", "CPC"),
         name="eCPM price drop on one campaign_type",
         edge_case="Price lever rather than volume/fill — exercises the eCPM branch and "
                   "its advertiser-side dimensions.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="ecpm"),
    dict(id="S12", day=25, kind="ramp", ramp=0.95, target=(None, None),
         name="slow ramp, day 1 of 3 (-5%)",
         edge_case="A drift, not a step. Each day alone may sit under threshold and the "
                   "ramp poisons its own trailing baseline; step detection can miss it.",
         expect_verdict="ANY", expect_metric="ecpm",
         note="Day 1 legitimately may not flag — see EDGE_CASES.md"),
    dict(id="S13", day=26, kind="ramp", ramp=0.90, target=(None, None),
         name="slow ramp, day 2 of 3 (-10%)",
         edge_case="Mid-ramp. Still no step change on any single day.",
         expect_verdict="ANY", expect_metric="ecpm"),
    dict(id="S14", day=27, kind="ramp", ramp=0.85, target=(None, None),
         name="slow ramp, day 3 of 3 (-15%)",
         edge_case="By day 3 cumulative drift should clear threshold even though no "
                   "single day is a step.",
         expect_verdict="ANY", expect_metric="ecpm"),
    # ── seasonality, positive direction ────────────────────────────────────────
    dict(id="S15", day=34, kind="fill_segment", target=("os_version", "iOS 17.2"),
         name="SEASONALITY: real collapse on the lowest-traffic day (Sunday)",
         edge_case="The masking test. Sunday already runs -19% on volume, so a flat or "
                   "pooled baseline attributes the drop to the weekend and dismisses a "
                   "genuine incident. Only a same-weekday baseline (Sunday vs prior "
                   "Sundays) still sees it. This is the false-NEGATIVE that seasonality "
                   "causes.",
         expect_verdict="CAUSE_CONFIRMED", expect_metric="fill_rate"),
    dict(id="S16", day=30, kind="global_volume", volume=0.81, target=(None, None),
         name="SEASONALITY: weekend-sized volume drop on a WEEKDAY",
         edge_case="The mirror test. -19% is normal on Sunday and an incident on "
                   "Wednesday — the SAME number. A baseline that is not weekday-aware "
                   "must fail exactly one of S15/S16, so passing both is the real proof "
                   "the seasonality handling works.",
         expect_verdict="GLOBAL_MOVEMENT", expect_metric="requests"),
]

RANDOMIZABLE = {"os_version", "country", "device_model", "vertical", "campaign_type",
                "region", "ad_format"}


def load_dims(data_dir: str):
    def read(name):
        with open(os.path.join(data_dir, name), newline="") as fh:
            return list(csv.DictReader(fh))
    return read("apps.csv"), read("advertisers.csv"), read("geo_device.csv")


def build_index(rows, key):
    idx: dict[str, list] = {}
    for r in rows:
        idx.setdefault(r[key], []).append(r)
    return idx


def resolve_targets(scenarios, rng, randomize, pools):
    """Bind each scenario's (dim, value). --randomize-targets re-rolls the value from
    the dim's real domain so the fixture never trains the agent on fixed segments."""
    out = []
    for s in scenarios:
        s = dict(s)
        for key in ("target", "target2"):
            if key not in s:
                continue
            dim, val = s[key]
            if randomize and dim in RANDOMIZABLE and dim in pools:
                choices = [v for v in pools[dim] if v != "unknown"]
                val = rng.choice(sorted(choices))
            s[key] = (dim, val)
        out.append(s)
    return out


def gen_slice(rng, days, start, apps, advs, geos, geo_idx, scenarios, writer,
              req_per_day, growth=True):
    fmt_names = list(FORMATS)
    fmt_weights = [FORMATS[f]["share"] for f in fmt_names]
    by_day = {s["day"]: s for s in scenarios}
    n_rows = 0

    for d in range(days):
        day = start + timedelta(days=d)
        dow = day.weekday()
        sc = by_day.get(d)
        kind = sc["kind"] if sc else None
        tdim, tval = sc.get("target", (None, None)) if sc else (None, None)
        t2dim, t2val = sc.get("target2", (None, None)) if sc else (None, None)
        trend = 1.0 + (0.004 * d if growth else 0.0)

        for h in range(24):
            if kind == "ingestion_gap" and 2 <= h < 6:
                continue                                   # emit nothing at all

            n = req_per_day / 24 * HOUR_FACTOR[h] * WEEKDAY_FACTOR[dow] * trend
            if kind == "global_volume":
                n *= sc.get("volume", 0.60)
            n = int(rng.gauss(n, n * 0.01))

            weights = fmt_weights
            if kind == "mix_shift":
                weights = [w * (2.6 if f == tval else 0.55 if f == "banner" else 1.0)
                           for f, w in zip(fmt_names, fmt_weights)]

            for _ in range(max(n, 0)):
                fmt = rng.choices(fmt_names, weights=weights, k=1)[0]
                spec = FORMATS[fmt]

                # bias sampling toward the targeted segment so it carries real weight
                geo = None
                if kind == "unknown_dim" and rng.random() < 0.06:
                    geo = {"geo_device_id": "gd_9%04d" % rng.randrange(9999)}
                elif tdim in ("os_version", "country", "device_model", "region") \
                        and rng.random() < 0.28 and tval in geo_idx[tdim]:
                    geo = rng.choice(geo_idx[tdim][tval])
                if geo is None:
                    geo = rng.choice(geos)

                app = rng.choice(apps)
                cand = rng.choice(advs)      # decided BEFORE fill, so a pullout can
                                             # turn would-be fills into unfilled rows
                # inherit the parent universe's cross-sectional structure
                fill_p = min(0.995, spec["fill"] * FILL_BY_TIER.get(app["publisher_tier"], 1.0))
                ctr_mult = 1.0
                rev_mult = ECPM_BY_COUNTRY.get(geo.get("country", ""), 1.0)
                hit = tdim and geo.get(tdim) == tval

                if kind == "fill_segment" and hit:
                    fill_p = 0.43
                elif kind == "unknown_dim" and geo["geo_device_id"].startswith("gd_9"):
                    fill_p = 0.42
                elif kind == "interaction" and hit and geo.get(t2dim) == t2val:
                    fill_p = 0.40                                  # the CROSS only
                elif kind == "partial_day" and hit and 8 <= h < 17:
                    fill_p = 0.42
                elif kind == "demand_pullout" and cand.get(tdim) == tval:
                    fill_p = 0.05
                elif kind == "two_incidents" and hit:
                    fill_p = 0.45

                if kind == "ctr_spike" and hit:
                    ctr_mult = 4.5
                if kind == "ecpm_drop" and cand.get(tdim) == tval:
                    rev_mult *= 0.55
                if kind == "two_incidents" and cand.get(t2dim) == t2val:
                    rev_mult *= 0.62
                if kind == "ramp":
                    rev_mult *= sc["ramp"]

                is_filled = 1 if rng.random() < fill_p else 0
                advertiser = cand["advertiser_id"] if is_filled else ""
                is_impression = 1 if is_filled and rng.random() < spec["render"] else 0
                is_click = 1 if is_impression and rng.random() < spec["ctr"] * ctr_mult else 0
                revenue = (max(0.0, rng.gauss(spec["ecpm"] / 1000.0,
                                              spec["ecpm"] / 1000.0 * 0.25)) * rev_mult
                           if is_impression else 0.0)

                ts = datetime(day.year, day.month, day.day, h,
                              rng.randrange(60), rng.randrange(60))
                writer.writerow([ts.strftime("%Y-%m-%d %H:%M:%S"), app["app_id"],
                                 geo["geo_device_id"], advertiser, fmt,
                                 is_filled, is_impression, is_click, round(revenue, 6)])
                n_rows += 1
    return n_rows


HEADER = ["event_time", "app_id", "geo_device_id", "advertiser_id", "ad_format",
          "is_filled", "is_impression", "is_click", "revenue"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--data-dir", default="../click-a-thon-2026/InMobi/data")
    ap.add_argument("--seed", type=int, default=20260802)
    ap.add_argument("--req-per-day", type=int, default=REQ_PER_DAY)
    ap.add_argument("--randomize-targets", action="store_true",
                    help="re-roll which segment each scenario hits (unseen-incident drill)")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    apps, advs, geos = load_dims(a.data_dir)
    geo_idx = {k: build_index(geos, k)
               for k in ("os_version", "country", "device_model", "region")}
    pools = {k: sorted(geo_idx[k]) for k in geo_idx}
    pools["vertical"] = sorted({r["vertical"] for r in advs})
    pools["campaign_type"] = sorted({r["campaign_type"] for r in advs})
    pools["ad_format"] = sorted(FORMATS)

    rng = random.Random(a.seed)
    scenarios = resolve_targets(SCENARIOS, rng, a.randomize_targets, pools)

    main_csv = os.path.join(a.out_dir, "edge_events.csv")
    with open(main_csv, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(HEADER)
        n_main = gen_slice(rng, N_DAYS, START_DATE, apps, advs, geos, geo_idx,
                           scenarios, w, a.req_per_day)

    # ── short slice: 4 days, no trailing history -> forces the peer path
    short = [dict(id="S17", day=2, kind="fill_segment",
                  target=("os_version", "iOS 18.1"),
                  name="peer outlier on a history-free slice",
                  edge_case="Too few days for any same-weekday baseline. q1/q2/q3/q5 are "
                            "all impossible; only sibling comparison inside the window "
                            "can find the outlier. This is the release-day shape if the "
                            "unseen slice ships without history.",
                  expect_verdict="PEER_OUTLIER", expect_metric="fill_rate")]
    rng_s = random.Random(a.seed + 1)
    short = resolve_targets(short, rng_s, a.randomize_targets, pools)
    short_csv = os.path.join(a.out_dir, "edge_short_events.csv")
    with open(short_csv, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(HEADER)
        n_short = gen_slice(rng_s, SHORT_DAYS, SHORT_START, apps, advs, geos, geo_idx,
                            short, w, a.req_per_day, growth=False)

    def pub(s):
        d = {k: v for k, v in s.items() if k not in ("kind", "ramp", "volume")}
        d["target"] = {"dim": s["target"][0], "value": s["target"][1]}
        if "target2" in s:
            d["target2"] = {"dim": s["target2"][0], "value": s["target2"][1]}
        return d

    manifest = {
        "seed": a.seed, "randomized_targets": a.randomize_targets,
        "req_per_day": a.req_per_day,
        "main": {"csv": os.path.basename(main_csv), "rows": n_main,
                 "start": START_DATE.isoformat(), "days": N_DAYS,
                 "dates": {s["id"]: (START_DATE + timedelta(days=s["day"])).isoformat()
                           for s in scenarios}},
        "short": {"csv": os.path.basename(short_csv), "rows": n_short,
                  "start": SHORT_START.isoformat(), "days": SHORT_DAYS,
                  "dates": {short[0]["id"]:
                            (SHORT_START + timedelta(days=short[0]["day"])).isoformat()}},
        "seasonal_clean_dates": [(START_DATE + timedelta(days=d)).isoformat()
                                 for d in SEASONAL_CLEAN_DAYS],
        "scenarios": [pub(s) for s in scenarios] + [pub(s) for s in short],
    }
    with open(os.path.join(a.out_dir, "edge_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"main slice : {n_main:>9,} rows  {main_csv}")
    print(f"short slice: {n_short:>9,} rows  {short_csv}")
    print(f"scenarios  : {len(manifest['scenarios'])}"
          f"{'  (targets RANDOMIZED)' if a.randomize_targets else ''}")
    for s in manifest["scenarios"]:
        t = s["target"]
        print(f"  {s['id']}  {str(t['dim'] or '-'):<14} {str(t['value'] or '-'):<16} "
              f"-> {s['expect_verdict']}")


if __name__ == "__main__":
    main()
