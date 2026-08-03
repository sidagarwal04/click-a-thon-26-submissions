#!/usr/bin/env python3
"""Observability validation — score the detector against the Langfuse `anomaly-eval-set` ground
truth as a Langfuse EXPERIMENT (a dataset run). Each item: run the detector, compare its answer to
the expected cause + verdict, log localization/verdict scores. Shows up in Langfuse → Experiments.

  python tests/experiment.py
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_incident as ri
from langfuse import Langfuse

def _norm(s): return re.sub(r"\s+", "", (s or "").lower()).replace("×", "x")

def _detector_answer(inv):
    c = inv.get("culprit")
    if not c: return {"verdict": inv["verdict"], "cause": "global"}
    cause = c["segment"] if "×" in c["dimension"] else f"{c['dimension']}={c['segment']}"
    return {"verdict": inv["verdict"], "cause": cause, "deviation_pct": c["deviation_pct"]}

# run the detector ONCE; each experiment item just looks up its matching investigation
_CFG = ri.env()
_cx = ri.connect(_CFG); ri.ensure_cube(_cx, "rca")
_inc, _fp = ri.scan(_cx, "rca")
_INVS = ri.build_bundle(_cx, "rca", _inc, _fp, 0)["investigations"]

def _match(item_input):
    m, (lo, hi) = item_input["metric"], item_input["window"]
    for inv in _INVS:
        if inv["metric"] == m and not (inv["window"][1] < lo or inv["window"][0] > hi):
            return inv
    return None

def task(*, item, **_):
    inv = _match(item.input)
    return _detector_answer(inv) if inv else {"verdict": "NOT_DETECTED", "cause": "none"}

def eval_localization(*, input, output, expected_output, metadata, **_):
    exp = expected_output or {}
    if exp.get("verdict") == "GLOBAL_UNLOCALIZED":
        ok = output.get("cause") == "global"
    else:
        e, g = _norm(exp.get("cause")), _norm(output.get("cause"))
        ok = bool(g) and g != "none" and (e in g or g in e)
    return {"name": "localization_correct", "value": 1.0 if ok else 0.0,
            "comment": f"expected [{exp.get('cause')}] · detector [{output.get('cause')}]"}

def eval_verdict(*, input, output, expected_output, metadata, **_):
    ok = output.get("verdict") == (expected_output or {}).get("verdict")
    return {"name": "verdict_correct", "value": 1.0 if ok else 0.0}

if __name__ == "__main__":
    lf = Langfuse(public_key=_CFG["LANGFUSE_PUBLIC_KEY"], secret_key=_CFG["LANGFUSE_SECRET_KEY"],
                  host=_CFG.get("LANGFUSE_BASE_URL"))
    ds = lf.get_dataset("anomaly-eval-set")
    print(f"scoring the detector against {len(ds.items)} ground-truth incidents ...\n")
    res = ds.run_experiment(name="detector vs ground truth",
                            description="run_incident.py localization/verdict scored on the seen incidents",
                            task=task, evaluators=[eval_localization, eval_verdict])
    lf.flush()
    # per-item + aggregate
    loc = ver = n = 0
    for r in getattr(res, "item_results", []) or []:
        n += 1
        for s in (r.evaluations or []):
            if s.name == "localization_correct": loc += s.value
            if s.name == "verdict_correct": ver += s.value
    if n:
        print(f"  localization_correct: {loc:.0f}/{n}   ({loc/n:.0%})")
        print(f"  verdict_correct:      {ver:.0f}/{n}   ({ver/n:.0%})")
    url = getattr(res, "dataset_run_url", None) or getattr(res, "url", None)
    if url: print(f"\n  Experiment in Langfuse: {url}")
    print("  (Langfuse → Datasets → anomaly-eval-set → Experiments)")
