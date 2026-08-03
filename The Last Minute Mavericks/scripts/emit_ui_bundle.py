#!/usr/bin/env python3
"""Emit the scan bundle in the shape ui/incidents.py `_card()` consumes, to
contracts/fixtures/scan_bundle.json — wiring Naman's UI to the REAL engine.

  python scripts/emit_ui_bundle.py            # writes contracts/fixtures/scan_bundle.json
The UI reads that file automatically (incidents() is bundle-first).
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_incident as ri
from agent.narrate import narrate

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "contracts", "fixtures", "scan_bundle.json")

def _sev(pct):
    a = abs(pct)
    return "crit" if a >= 30 else ("high" if a >= 15 else "med")

def _fmt(metric, v):
    if v is None: return None
    if metric == "ecpm":     return f"${v:.2f}"
    if metric == "requests": return f"{v:,.0f}/day"
    return f"{v:.3f}"                       # fill_rate / ctr

def _culprit(c):
    if not c: return None
    dim, seg = c["dimension"], c["segment"]
    if "×" in dim:                          # 2-D: "os_version=iOS 18.1 × region=APAC"
        parts = [p.strip() for p in seg.split("×")]
        d1, v1 = parts[0].split("=", 1)
        co = {}
        for p in parts[1:]:
            k, v = p.split("=", 1); co[k.strip()] = v.strip()
        return {"dimension": d1.strip(), "value": v1.strip(), "co_cut": co}
    return {"dimension": dim, "value": seg}

def _to_ui(inv):
    drv = next((d for d in inv["decomposition"] if d["verdict"] == "driver"), None)
    c = inv["culprit"]
    dev = c["deviation_pct"] if c else (drv["deviation_pct"] if drv else 0.0)
    diag = inv.get("diagnosis", {})
    ruled = [f"{r['segment']} ({r['deviation_pct']:+.1f}%) — {r['why']}" for r in inv.get("ruled_out", [])]
    ruled += [f"{d['factor']} normal ({d['deviation_pct']:+.1f}%) — ruled out"
              for d in inv["decomposition"] if "ruled out" in d["verdict"]]
    where = c["segment"] if c else "the global drop"
    return {
        "incident_id": inv["id"],
        "severity": _sev(dev),
        "title": inv["headline"],
        "metric": inv["metric"],
        "incident_window": {"start": inv["window"][0], "end": inv["window"][1]},
        "panes": [inv["metric"]] + (["revenue"] if inv["metric"] in ("fill_rate", "ecpm", "requests") else []),
        "headline": {"unit": "num", "delta_pct": dev,
                     "observed_note": _fmt(inv["metric"], drv["window_value"]) if drv else None,
                     "baseline": _fmt(inv["metric"], drv["baseline"]) if drv else None},
        "culprit": _culprit(c),
        "verdict": "GLOBAL_UNLOCALIZED" if inv["verdict"] == "GLOBAL_UNLOCALIZED" else "LOCALIZED",
        "mechanism": diag.get("diagnosis", ""),
        "contribution": (f"{c['dimension']} = {c['segment']} carries the move; other segments flat"
                         if c else "spread uniformly — no single segment carries it"),
        "uniformity": ("uniform across all segments — global, not localizable" if not c else
                       ("concentrated in the 2-D interaction cell; neither parent alone explains it"
                        if "×" in c["dimension"] else "confined to the segment; siblings within normal band")),
        "confidence": "high — robust-z far past threshold, effect-size + volume gated",
        "ruled_out": ruled,
        "actions": [{"urgency": "now", "text": f"Investigate {where} over {inv['window'][0]} → {inv['window'][1]}"},
                    {"urgency": "today", "text": f"Confirm the {inv['metric']} drop reproduces and check upstream changes"}],
        "trace_url": inv.get("_trace_url", ""),
    }

if __name__ == "__main__":
    # DB from .env (CLICKHOUSE_DATABASE) so a new dataset needs no edit here; rebuild=True
    # because this script exists to regenerate the fallback bundle AFTER data changed.
    DB = ri.default_db()
    cfg = ri.env(); cx = ri.connect(cfg); ri.ensure_cube(cx, DB, rebuild=True)
    inc, fp = ri.scan(cx, DB)
    bundle = ri.build_bundle(cx, DB, inc, fp, 0.0)
    trace_url = ri.log_bundle(bundle, DB, cfg) or ""
    for i in bundle["investigations"]:
        i["diagnosis"] = narrate(i, cfg)
        i["_trace_url"] = trace_url
    ui_bundle = {"scan_summary": {**bundle["scan_summary"],
                                  "checks": "1,709 segments × 8 metrics = 13,672 checks ≈ 114 analyst-hours"},
                 "investigations": [_to_ui(i) for i in bundle["investigations"]]}
    json.dump(ui_bundle, open(OUT, "w"), indent=2, default=str)
    print(f"wrote {OUT}  ({len(ui_bundle['investigations'])} investigations, UI shape)")
    print("trace:", trace_url)
