#!/usr/bin/env python3
"""Deep Langfuse integration for the battle-test (Langfuse v4 SDK, pinned 4.14.2).

Every battle-test run becomes a Langfuse TRACE (span per stage), the planted incidents become a
Langfuse DATASET, and precision/recall are logged as Langfuse SCORES — so Langfuse is used as an
eval/analytics platform, not just a logger. Traces are set public for judges.

  PYTHONPATH=tests python tests/battletest_langfuse.py --seed 7 --inject 4
"""
import argparse, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battletest as bt
from langfuse import Langfuse

def env(p=".env"):
    c={}
    for l in open(p):
        l=l.strip()
        if l and not l.startswith("#") and "=" in l:
            k,v=l.split("=",1); c[k.strip()]=v.strip().strip('"').strip("'")
    return c

def run(seed, inject):
    cfg=env()
    lf=Langfuse(public_key=cfg["LANGFUSE_PUBLIC_KEY"],secret_key=cfg["LANGFUSE_SECRET_KEY"],
                host=cfg.get("LANGFUSE_BASE_URL"))
    assert lf.auth_check(), "langfuse auth failed"
    client=bt.connect()
    injected=bt.plan_injections(random.Random(seed),inject)
    manifest=bt.KNOWN+injected

    with lf.start_as_current_observation(name=f"anomaly eval · seed {seed}", as_type="chain") as root:
        root.update(input={"seed":seed,"inject":inject,"planted":len(manifest)})
        with lf.start_as_current_observation(name="inject_synthetic_anomalies", as_type="span") as s:
            bt.build_synth(client,injected,seed)
            s.update(input={"incidents":[{**i,"win":list(i["win"])} for i in injected]},
                     output={"synth_rows":client.query("SELECT count() FROM rca_synth.ad_events").result_rows[0][0]})
        with lf.start_as_current_observation(name="detect", as_type="span") as s:
            cand=bt.detect(client,"rca_synth")
            s.update(output={"candidates":len(cand),"sample":cand[:8]})
        found,fp,prec,rec=bt.score(manifest,cand)
        root.update(output={"precision":prec,"recall":rec,"false_positives":len(fp),
                            "found":sum(f["found"] for f in found),"planted":len(manifest)})
        lf.set_current_trace_as_public()
        tid=lf.get_current_trace_id()

    # scores on the trace -> Langfuse analytics track detector quality across runs
    lf.create_score(name="precision",value=float(prec),trace_id=tid,comment=f"seed {seed}")
    lf.create_score(name="recall",value=float(rec),trace_id=tid,comment=f"seed {seed}")

    # the planted incidents become a reusable Langfuse Dataset (ground truth)
    ds="anomaly-eval-set"
    try: lf.create_dataset(name=ds)
    except Exception: pass
    for inc in manifest:
        try:
            lf.create_dataset_item(dataset_name=ds,
                input={"metric":inc["metric"],"dim":inc["dim"],"value":inc.get("value"),"window":list(inc["win"])},
                expected_output={"is_anomaly":True,"source":inc["src"]},
                metadata={"seed":seed}, source_trace_id=tid)
        except Exception: pass

    lf.flush(); lf.shutdown()
    try: url=lf.get_trace_url(trace_id=tid)
    except Exception: url=f"{cfg.get('LANGFUSE_BASE_URL','').rstrip('/')}/trace/{tid}"
    print(f"\n=== logged to Langfuse ===  precision={prec:.2f} recall={rec:.2f}")
    print("trace (public):", url)
    print("dataset:", ds, f"({len(manifest)} items)")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seed",type=int,default=7); ap.add_argument("--inject",type=int,default=4)
    a=ap.parse_args(); run(a.seed,a.inject)
