#!/usr/bin/env python3
"""Battle-test: plant FRESH synthetic anomalies (not the known 4), run detection, score it.

This is the rehearsal for the unseen incident — it proves the detector generalizes to anomalies
we never hand-tuned to. It builds a synthetic copy of rca.ad_events in `rca_synth` with random
planted anomalies, runs a baseline detector, and reports precision / recall vs ground truth.

  python tests/battletest.py --seed 7 --inject 4
The detector here is a BASELINE (same-weekday median + MAD gate). Swap in sql/ detection when ready
— the injector + scorer are the durable part.
"""
import argparse, json, random, re, sys, clickhouse_connect

# low-card dimensions we plant into / scan (app/advertiser/geo ids are NOT anomaly-bearing — DATA.md)
DIM_SRC = {  # dim -> (join table, column); None table = column on ad_events
    "region":      ("geo_device", "region"),
    "os_version":  ("geo_device", "os_version"),
    "category":    ("apps", "category"),
    "ad_format":   (None, "ad_format"),
}
POOLS = {
    "region":    ["NAM", "EU", "APAC", "LATAM", "MEA"],
    "os_version":["iOS 16.4","iOS 17.2","iOS 17.5","iOS 18.1","Android 12","Android 13","Android 14","Android 15"],
    "category":  ["gaming","social","entertainment","news","ecommerce","utility","finance"],
    "ad_format": ["banner","native","interstitial","video","rewarded"],
}
JOINKEY = {"geo_device":"geo_device_id","apps":"app_id","advertisers":"advertiser_id"}
DAYS = [f"2026-06-{d:02d}" for d in range(8,31)] + [f"2026-07-{d:02d}" for d in range(1,4)]  # avoid edges
DB_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def db_name(name):
    if not DB_RE.match(name):
        raise ValueError(f"unsafe ClickHouse database name: {name!r}")
    return name

def env(p=".env"):
    c={}
    for l in open(p):
        l=l.strip()
        if l and not l.startswith("#") and "=" in l:
            k,v=l.split("=",1); c[k.strip()]=v.strip().strip('"').strip("'")
    return c
def connect():
    c=env(); return clickhouse_connect.get_client(host=c["CLICKHOUSE_HOST"],port=int(c.get("CLICKHOUSE_PORT",8443)),
        username=c.get("CLICKHOUSE_USER","default"),password=c["CLICKHOUSE_PASSWORD"],secure=True)

# ---- the KNOWN 4 also live in the copy, so they belong in ground truth too (DATA.md) ----
KNOWN = [
    {"metric":"requests","dim":"__global__","value":None,"win":("2026-06-21","2026-06-21"),"src":"INC-A"},
    {"metric":"ecpm","dim":"category","value":"finance","win":("2026-06-19","2026-06-22"),"src":"INC-B"},
    {"metric":"fill_rate","dim":"os_version","value":"Android 15","win":("2026-06-23","2026-06-25"),"src":"INC-C"},
    {"metric":"fill_rate","dim":"os_version","value":"iOS 18.1","win":("2026-06-28","2026-06-30"),"src":"INC-D"},
]

def plan_injections(rng, n):
    """Pick n fresh, non-overlapping-window incidents avoiding the known windows/segments."""
    used_days=set(); known_segs={(k["metric"],k.get("value")) for k in KNOWN}
    out=[]
    metrics=["fill_rate","ctr","ecpm"]
    for _ in range(n*6):
        if len(out)>=n: break
        if rng.random()<0.2:  # occasional global volume incident
            m,dim,val="requests","__global__",None
        else:
            m=rng.choice(metrics); dim=rng.choice(list(DIM_SRC)); val=rng.choice(POOLS[dim])
        if (m,val) in known_segs: continue
        start=rng.randint(0,len(DAYS)-3); win=(DAYS[start],DAYS[start+2])
        wd=set(range(start,start+3))
        if wd & used_days: continue
        used_days|=wd
        drop=round(rng.uniform(0.35,0.6),2)   # magnitude of the drop
        out.append({"metric":m,"dim":dim,"value":val,"win":win,"drop":drop,"src":"SYN"})
    return out

def target_sql(inc, jcols):
    """Boolean expr selecting the incident's target rows (segment × window) on the joined row."""
    lo,hi=inc["win"]; win=f"(toDate(e.event_time) BETWEEN '{lo}' AND '{hi}')"
    if inc["dim"]=="__global__": return win
    tbl,col=DIM_SRC[inc["dim"]]; ref=(f"e.{col}" if tbl is None else f"{jcols[tbl]}.{col}")
    return f"({ref}='{inc['value']}' AND {win})"

def build_synth(client, incidents, seed, source_db="rca", target_db="rca_synth"):
    source_db = db_name(source_db)
    target_db = db_name(target_db)
    jt={t for i in incidents if i['dim']!='__global__' for t,_ in [DIM_SRC[i['dim']]] if t}
    jt |= set()  # ensure set
    joins="".join(f" LEFT JOIN {source_db}.{t} {t[:3]} ON e.{JOINKEY[t]}={t[:3]}.{JOINKEY[t]}" for t in ["geo_device","apps"])
    jcols={"geo_device":"geo","apps":"app"}
    salt=f"syn{seed}"
    hsel=lambda p:(f"(cityHash64(concat(toString(e.event_time),e.app_id,e.geo_device_id,'{salt}')) % 1000) < {int(p*1000)}")
    # unfill flag (fill_rate incidents): unfill selected rows -> also zero imp/click/rev (funnel stays consistent)
    unfill=" OR ".join(f"({target_sql(i,jcols)} AND {hsel(i['drop'])})" for i in incidents if i["metric"]=="fill_rate") or "0"
    # ctr incidents: zero clicks on selected impression rows
    unclick=" OR ".join(f"({target_sql(i,jcols)} AND {hsel(i['drop'])})" for i in incidents if i["metric"]=="ctr") or "0"
    # ecpm incidents: scale revenue down in target
    rev_expr="e.revenue"
    for i in [x for x in incidents if x["metric"]=="ecpm"]:
        rev_expr=f"if({target_sql(i,jcols)}, {rev_expr}*{1-i['drop']}, {rev_expr})"
    # requests/global incidents: drop selected rows entirely
    drop_rows=" OR ".join(f"({target_sql(i,jcols)} AND {hsel(i['drop'])})" for i in incidents if i["metric"]=="requests") or "0"

    client.command(f"CREATE DATABASE IF NOT EXISTS {target_db}")
    client.command(f"DROP TABLE IF EXISTS {target_db}.ad_events")
    client.command(f"""CREATE TABLE {target_db}.ad_events
      (event_time DateTime, app_id String, geo_device_id String, advertiser_id String, ad_format String,
       is_filled UInt8, is_impression UInt8, is_click UInt8, revenue Float64)
      ENGINE=MergeTree ORDER BY (event_time, app_id)""")
    sql=f"""INSERT INTO {target_db}.ad_events
      SELECT e.event_time, e.app_id, e.geo_device_id, e.advertiser_id, e.ad_format,
             if(({unfill}), 0, e.is_filled)                          AS f,
             if(({unfill}), 0, e.is_impression)                      AS im,
             if(({unfill}) OR ({unclick}), 0, e.is_click)            AS cl,
             if(({unfill}), 0, {rev_expr})                           AS rev
      FROM {source_db}.ad_events e{joins}
      WHERE NOT ({drop_rows})"""
    client.command(sql)
    # dims: reuse rca's (unchanged)
    for name in ["apps","advertisers","geo_device"]:
        client.command(f"CREATE TABLE IF NOT EXISTS {target_db}.{name} AS {source_db}.{name}")
        client.command(f"TRUNCATE TABLE {target_db}.{name}")
        client.command(f"INSERT INTO {target_db}.{name} SELECT * FROM {source_db}.{name}")

MEXPR={"fill_rate":"sum(e.is_filled)/count()","ctr":"sum(e.is_click)/nullIf(sum(e.is_impression),0)",
       "ecpm":"sum(e.revenue)/nullIf(sum(e.is_impression),0)*1000","requests":"count()"}

def detect(client, db, z_thresh=4.0, min_req=1500, min_rel=0.15):
    """Baseline detector: same-weekday median + MAD, gated. Returns candidate (metric,dim,value,day)."""
    import statistics as st
    cand=[]
    scans=[("requests","__global__",None,None)]+[(m,d,DIM_SRC[d][0],DIM_SRC[d][1]) for m in ["fill_rate","ctr","ecpm"] for d in DIM_SRC]
    for metric,dim,tbl,col in scans:
        me=MEXPR[metric]
        if dim=="__global__":
            sql=(f"SELECT toDate(e.event_time) d, '' seg, toDayOfWeek(e.event_time) dow, {me} v, count() n "
                 f"FROM {db}.ad_events e GROUP BY d,seg,dow ORDER BY d")
        else:
            joinsql=f" INNER JOIN {db}.{tbl} g ON e.{JOINKEY[tbl]}=g.{JOINKEY[tbl]}" if tbl else ""
            segcol=f"g.{col}" if tbl else f"e.{col}"
            sql=(f"SELECT toDate(e.event_time) d, {segcol} seg, toDayOfWeek(e.event_time) dow, {me} v, count() n "
                 f"FROM {db}.ad_events e{joinsql} GROUP BY d,seg,dow ORDER BY d")
        by={}
        for d,seg,dow,v,n in client.query(sql).result_rows:
            by.setdefault((seg,dow),[]).append((str(d),v,n))
        for (seg,dow),pts in by.items():
            vals=[v for _,v,_ in pts if v is not None]
            if len(vals)<2: continue
            med=st.median(vals); mad=st.median([abs(x-med) for x in vals]) or 1e-9
            for d,v,n in pts:
                if v is None or n<min_req or not med: continue
                z=0.6745*(v-med)/mad; rel=(v-med)/med
                if abs(z)>z_thresh and abs(rel)>min_rel:
                    cand.append({"metric":metric,"dim":dim,"value":(None if dim=="__global__" else seg),
                                 "day":d,"z":round(z,1),"rel":round(rel,3)})
    return cand

def score(manifest, cand):
    def match(inc,c):
        if c["metric"]!=inc["metric"]: return False
        if inc["dim"]!="__global__" and c["value"]!=inc["value"]: return False
        if inc["dim"]=="__global__" and c["dim"]!="__global__": return False
        lo,hi=inc["win"]; return lo<=c["day"]<=hi
    found=[];
    for inc in manifest:
        hit=[c for c in cand if match(inc,c)]
        found.append({**{k:inc[k] for k in ("metric","dim","value","win","src")},"found":bool(hit),"n_hits":len(hit)})
    matched_days=set()
    for inc in manifest:
        for c in cand:
            if match(inc,c): matched_days.add((c["metric"],c["value"],c["day"]))
    fp=[c for c in cand if (c["metric"],c["value"],c["day"]) not in matched_days]
    recall=sum(f["found"] for f in found)/len(found) if found else 0
    precision=1-(len(fp)/len(cand)) if cand else 1.0
    return found,fp,precision,recall

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seed",type=int,default=7); ap.add_argument("--inject",type=int,default=4)
    a=ap.parse_args(); rng=random.Random(a.seed)
    client=connect(); print("connected:",client.server_version)
    injected=plan_injections(rng,a.inject)
    manifest=KNOWN+injected
    print(f"\nplanting {len(injected)} fresh incidents (+{len(KNOWN)} known) with seed {a.seed} ...")
    build_synth(client,injected,a.seed)
    print("synth built:",client.query("SELECT count() FROM rca_synth.ad_events").result_rows[0][0],"rows")
    cand=detect(client,"rca_synth")
    found,fp,prec,rec=score(manifest,cand)
    print(f"\n=== RESULT  precision={prec:.2f}  recall={rec:.2f}  ({len(cand)} candidates, {len(fp)} false-pos) ===")
    for f in found:
        seg=f["value"] or "(global)"; lo,hi=f["win"]
        print(f"  {'FOUND ' if f['found'] else 'MISSED'} [{f['src']}] {f['metric']} {f['dim']}={seg} {lo}..{hi}")
    json.dump({"seed":a.seed,"manifest":[{**m,'win':list(m['win'])} for m in manifest],"candidates":cand,
               "precision":prec,"recall":rec},open("tests/last_battletest.json","w"),indent=2,default=str)
    print("\nwrote tests/last_battletest.json")
