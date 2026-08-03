#!/usr/bin/env python3
"""Generate a FROM-SCRATCH ~10M-row synthetic dataset for end-to-end product testing.

Unlike tests/battletest.py (which mutates a copy of the organizer's rca.ad_events), this builds a
fully independent dataset — same schema, same DATA.md statistical profile (fill 78%, render 98%,
CTR 1.088% of impressions, eCPM ~2.5, weekday/weekend volume + rising trend, funnel perfectly
consistent) — with PLANTED anomalies and a ground-truth manifest. Everything is generated
server-side (INSERT ... SELECT FROM numbers()): no data crosses the wire.

  python scripts/gen_e2e_dataset.py                               # default 5 incidents -> rca_e2e
  python scripts/gen_e2e_dataset.py --spec tests/e2e/spec_t1.json # calibrated incident spec
  python run_incident.py --db rca_e2e --rebuild-cube              # the product must find them

Spec JSON: {"database": "rca_t1", "rows": 10000000, "incidents": [
  {"id":"T1-1","metric":"fill_rate","dim":"os_version","value":"Android 13",
   "win":["2026-06-10","2026-06-12"],"drop":0.3,
   "co_dim":"region","co_value":"EU",     # optional -> 2-D incident
   "shape":"ramp"}]}                      # optional: linear ramp-in (default: step)

Incident dims must be attributes derived in-row: region, country, device_model, os_version,
category, ad_format (+ __global__ for requests). requests incidents must be __global__.
"""
import argparse, json, clickhouse_connect
from datetime import date, timedelta

DAY0, N_DAYS = date(2026, 6, 1), 35  # same 5-week window as the real slice

CATS  = "['gaming','social','entertainment','news','ecommerce','utility','finance']"
TIERS = "['tier_1','tier_2','tier_3']"
VERTS = "['gaming','ecommerce','finance','travel','entertainment','auto','cpg']"
CTYPE = "['CPM','CPC','CPI']"
CTRY  = "['US','CA','UK','DE','FR','ES','IN','JP','ID','PH','SG','BR','MX','AR','ZA','AE']"
REGN  = "['NAM','NAM','EU','EU','EU','EU','APAC','APAC','APAC','APAC','APAC','LATAM','LATAM','LATAM','MEA','MEA']"
MODEL = "['iPhone 13','iPhone 14','iPhone 15','Pixel 7','Pixel 8','Galaxy S23','Galaxy S24','Redmi Note 12']"
IOS   = "['iOS 16.4','iOS 17.2','iOS 17.5','iOS 18.1']"
ANDR  = "['Android 12','Android 13','Android 14','Android 15']"
CPM   = "[1.3, 1.8, 2.4, 3.3, 3.9]"  # banner/native/interstitial/video/rewarded -> global eCPM ~2.5
FMT   = "['banner','native','interstitial','video','rewarded']"
FACT_DIMS = {"region", "country", "device_model", "os_version", "category", "ad_format"}

# Default ground truth (PR #40's original 5). run_incident scans requests / fill_rate / ecpm.
DEFAULT = {"database": "rca_e2e", "rows": 10_000_000, "incidents": [
    {"id": "E2E-1", "metric": "fill_rate", "dim": "region",     "value": "LATAM",      "win": ["2026-06-12", "2026-06-14"], "drop": 0.45},
    {"id": "E2E-2", "metric": "ecpm",      "dim": "category",   "value": "ecommerce",  "win": ["2026-06-18", "2026-06-20"], "drop": 0.50},
    {"id": "E2E-3", "metric": "requests",  "dim": "__global__", "value": None,         "win": ["2026-06-24", "2026-06-24"], "drop": 0.30},
    {"id": "E2E-4", "metric": "fill_rate", "dim": "os_version", "value": "Android 14", "win": ["2026-06-28", "2026-06-30"], "drop": 0.50},
    {"id": "E2E-5", "metric": "ecpm",      "dim": "ad_format",  "value": "video",      "win": ["2026-07-02", "2026-07-03"], "drop": 0.55},
]}

def env(p=".env"):
    c = {}
    for l in open(p):
        l = l.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1); c[k.strip()] = v.strip().strip('"').strip("'")
    return c

def connect():
    c = env()
    return clickhouse_connect.get_client(
        host=c["CLICKHOUSE_HOST"], port=int(c.get("CLICKHOUSE_PORT", 8443)),
        username=c.get("CLICKHOUSE_USER", "default"), password=c["CLICKHOUSE_PASSWORD"], secure=True)

def in_win(inc, day):
    return inc["win"][0] <= day <= inc["win"][1]

def day_drop(inc, day):
    """Effective drop for `day`: flat step, or linear ramp-in across the window."""
    if inc.get("shape") != "ramp":
        return inc["drop"]
    lo, hi = (date.fromisoformat(d) for d in inc["win"])
    n = (hi - lo).days + 1
    idx = (date.fromisoformat(day) - lo).days
    return inc["drop"] * (idx + 1) / n

def pred(inc):
    p = f"{inc['dim']}='{inc['value']}'"
    for co in ("co", "co2"):  # up to 3-D incidents
        if inc.get(f"{co}_dim"):
            p += f" AND {inc[f'{co}_dim']}='{inc[f'{co}_value']}'"
    return f"({p})"

def day_volumes(total, incidents):
    """Weekday ~1.3x weekend, mild rising trend, deterministic jitter; scaled to `total`."""
    raw = []
    for i in range(N_DAYS):
        d = DAY0 + timedelta(days=i)
        base = (0.78 if d.weekday() >= 5 else 1.0) * (1 + 0.004 * i)
        base *= 1 + ((i * 2654435761 % 41) - 20) / 1000  # +-2% deterministic day noise
        raw.append(base)
    scale = total / sum(raw)
    vols = {}
    for i, b in enumerate(raw):
        day = str(DAY0 + timedelta(days=i))
        n = int(b * scale)
        for inc in incidents:  # global volume incidents cut the row count directly
            if inc["metric"] == "requests" and in_win(inc, day):
                n = int(n * (1 - day_drop(inc, day)))
        vols[day] = n
    return vols

def fact_insert_sql(db, day, n, incidents):
    """One day's rows, fully server-side. Segment attrs are the SAME hash formulas as the dims."""
    unfill = " OR ".join(
        f"({pred(i)} AND cityHash64('unfill{i['id']}',number)%1000 < {int(day_drop(i, day)*1000)})"
        for i in incidents if i["metric"] == "fill_rate" and in_win(i, day)) or "0"
    rev = "arrayElement({cpm}, fmt_i+1) * (0.5 + (cityHash64('rev',number,'{d}')%1000)/1000.)".format(cpm=CPM, d=day)
    for i in incidents:
        if i["metric"] == "ecpm" and in_win(i, day):
            rev = f"if({pred(i)}, ({rev})*{1-day_drop(i, day)}, {rev})"
    return f"""
    INSERT INTO {db}.ad_events
    SELECT
        toDateTime('{day} 00:00:00') + (cityHash64('ts',number,'{day}') % 86400) AS event_time,
        concat('app_',  leftPad(toString(app_i), 4, '0'))                        AS app_id,
        concat('geo_',  leftPad(toString(geo_i), 4, '0'))                        AS geo_device_id,
        if(f = 1, concat('adv_', leftPad(toString(cityHash64('adv',number,'{day}') % 500), 3, '0')), '') AS advertiser_id,
        ad_format,
        f  AS is_filled,
        im AS is_impression,
        cl AS is_click,
        if(im = 1, {rev} / 1000, 0.) AS revenue
    FROM (
        SELECT number,
            cityHash64('app', number, '{day}') % 2000                            AS app_i,
            cityHash64('geo', number, '{day}') % 5000                            AS geo_i,
            cityHash64('fmt', number, '{day}') % 5                               AS fmt_i,
            arrayElement({FMT},  fmt_i + 1)                                      AS ad_format,
            arrayElement({CATS}, (cityHash64('cat',  app_i) % 7) + 1)            AS category,
            arrayElement({REGN}, (cityHash64('ctry', geo_i) % 16) + 1)           AS region,
            arrayElement({CTRY}, (cityHash64('ctry', geo_i) % 16) + 1)           AS country,
            cityHash64('mdl', geo_i) % 8                                         AS mdl_i,
            arrayElement({MODEL}, mdl_i + 1)                                     AS device_model,
            if(mdl_i < 3, arrayElement({IOS},  (cityHash64('osv', geo_i) % 4) + 1),
                          arrayElement({ANDR}, (cityHash64('osv', geo_i) % 4) + 1)) AS os_version,
            if(({unfill}), 0, toUInt8(cityHash64('fill', number, '{day}') % 1000  < 780))   AS f,
            toUInt8(f = 1 AND  cityHash64('imp',  number, '{day}') % 10000 < 9800)          AS im,
            toUInt8(im = 1 AND cityHash64('clk',  number, '{day}') % 100000 < 1088)         AS cl
        FROM numbers({n})
    )"""

DIM_SQL = {
    "apps": f"""INSERT INTO {{db}}.apps SELECT concat('app_', leftPad(toString(number),4,'0')),
        arrayElement({CATS}, (cityHash64('cat', number) % 7) + 1),
        arrayElement({TIERS}, (cityHash64('tier', number) % 3) + 1) FROM numbers(2000)""",
    "advertisers": f"""INSERT INTO {{db}}.advertisers SELECT concat('adv_', leftPad(toString(number),3,'0')),
        arrayElement({VERTS}, (cityHash64('vert', number) % 7) + 1),
        arrayElement({CTYPE}, (cityHash64('ct', number) % 3) + 1) FROM numbers(500)""",
    "geo_device": f"""INSERT INTO {{db}}.geo_device SELECT concat('geo_', leftPad(toString(number),4,'0')),
        arrayElement({REGN},  (cityHash64('ctry', number) % 16) + 1),
        arrayElement({CTRY},  (cityHash64('ctry', number) % 16) + 1),
        arrayElement({MODEL}, (cityHash64('mdl', number) % 8) + 1),
        if(cityHash64('mdl', number) % 8 < 3,
           arrayElement({IOS},  (cityHash64('osv', number) % 4) + 1),
           arrayElement({ANDR}, (cityHash64('osv', number) % 4) + 1)) FROM numbers(5000)""",
}
DIM_DDL = {  # same shapes as scripts/load_clickhouse.py (CONTRACTS §1)
    "apps":        "app_id String, category String, publisher_tier String",
    "advertisers": "advertiser_id String, vertical String, campaign_type String",
    "geo_device":  "geo_device_id String, region String, country String, device_model String, os_version String",
}

def validate(incidents):
    for i in incidents:
        assert i["metric"] in ("fill_rate", "ecpm", "requests"), f"{i['id']}: unsupported metric"
        if i["metric"] == "requests":
            assert i["dim"] == "__global__", f"{i['id']}: requests incidents must be __global__"
        else:
            assert i["dim"] in FACT_DIMS, f"{i['id']}: dim {i['dim']} not derivable in-row"
            for co in ("co_dim", "co2_dim"):
                if i.get(co):
                    assert i[co] in FACT_DIMS, f"{i['id']}: {co} {i[co]} not derivable"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="JSON spec: {database, rows, incidents:[...]}")
    ap.add_argument("--rows", type=int)
    ap.add_argument("--database")
    a = ap.parse_args()
    spec = {**DEFAULT, **(json.load(open(a.spec)) if a.spec else {})}
    if a.rows: spec["rows"] = a.rows
    if a.database: spec["database"] = a.database
    db, incidents = spec["database"], spec["incidents"]
    validate(incidents)
    cl = connect()
    print(f"connected: {cl.server_version} -> {db} ({len(incidents)} incidents)")

    cl.command(f"CREATE DATABASE IF NOT EXISTS {db}")
    cl.command(f"DROP TABLE IF EXISTS {db}.ad_events")
    cl.command(f"""CREATE TABLE {db}.ad_events
        (event_time DateTime, app_id String, geo_device_id String, advertiser_id String, ad_format String,
         is_filled UInt8, is_impression UInt8, is_click UInt8, revenue Float64)
        ENGINE = MergeTree ORDER BY (event_time, app_id)""")
    for name, ddl in DIM_DDL.items():
        cl.command(f"DROP TABLE IF EXISTS {db}.{name}")
        cl.command(f"CREATE TABLE {db}.{name} ({ddl}) ENGINE = MergeTree ORDER BY {ddl.split()[0]}")
        cl.command(DIM_SQL[name].format(db=db))

    for day, n in day_volumes(spec["rows"], incidents).items():
        cl.command(fact_insert_sql(db, day, n, incidents))
        print(f"  {day}  {n:>8,} rows")

    total = cl.query(f"SELECT count() FROM {db}.ad_events").result_rows[0][0]
    fr, rr, ctr, ecpm = cl.query(f"""SELECT sum(is_filled)/count(),
        sum(is_impression)/nullIf(sum(is_filled),0), sum(is_click)/nullIf(sum(is_impression),0),
        sum(revenue)/nullIf(sum(is_impression),0)*1000 FROM {db}.ad_events""").result_rows[0]
    bad = cl.query(f"""SELECT countIf(is_impression=1 AND is_filled=0) + countIf(is_click=1 AND is_impression=0)
        + countIf(revenue>0 AND is_impression=0) FROM {db}.ad_events""").result_rows[0][0]
    assert bad == 0, "funnel inconsistency"
    print(f"\n{db}.ad_events = {total:,} rows · fill {fr:.4f} · render {rr:.4f} · ctr {ctr:.5f} · ecpm {ecpm:.3f} · funnel OK")

    manifest = {"database": db, "rows": total, "incidents": incidents}
    out = f"tests/e2e/manifest_{db}.json" if a.spec else "tests/e2e/manifest.json"
    json.dump(manifest, open(out, "w"), indent=2)
    print(f"wrote {out} — now run: python run_incident.py --db {db} --rebuild-cube")

if __name__ == "__main__":
    main()
