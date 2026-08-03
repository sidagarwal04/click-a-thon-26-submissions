#!/usr/bin/env python3
"""Real-time LLM adjudication layer: rules each detected candidate REAL / FALSE_POSITIVE /
INCONCLUSIVE over COMPUTED evidence only, in ONE batched low-latency call.

Judge feedback drove this design: cast the detector net wider (recall mode, 5% floor) and let
a fast LLM do the FP/FN ruling instead of a blanket 10% gate. Iron rules preserved:
- The LLM never computes or invents a number — it reasons over fields the engine computed.
- The LLM can only move candidates between trays (reported / needs_review / suppressed);
  it cannot create a candidate or alter a value.
- Any failure (timeout, bad JSON, no backend) degrades to the deterministic precision-first
  gate: |rel| >= 10% stays reported, the 5-10% band goes to needs_review. The scan never blocks.

  python adjudicate.py bundle.json adjudicated.json          # in place of / after run_incident --json
Backends (first that answers): $LLM_BASE_URL or OpenAI (if OPENAI_API_KEY valid) ->
local Ollama (http://localhost:11434/v1, $ADJ_MODEL default codex-qwen25-coder-7b) -> deterministic.
"""
import json, os, re, sys, time, urllib.request
from datetime import date


def _date(s):
    y, m, d = map(int, s[:10].split("-"))
    return date(y, m, d)

SOLID = 10.0        # |deviation_pct| at/above this: reported even if the LLM is unavailable
TIMEOUT_S = 45      # whole-pass budget incl. one cold model load; past it we degrade, never block
MINCONF = 0.7       # verdicts below this confidence are treated as INCONCLUSIVE (needs_review)
MAXTOK = 1200

SYSTEM = """You are the anomaly adjudicator for an ad-metrics RCA engine. Input: a JSON array of
candidate anomalies. Every number was computed in ClickHouse; you compute nothing. Output strict
JSON only, one verdict object per input id, no prose outside JSON.

Rules, in order — first match wins; use only input fields:
1 SHADOW: ruled_out_context shows this candidate is explained by another incident (residual
  outside the culprit near zero) -> FALSE_POSITIVE, reason "explained by <that segment>".
2 MIX-SHIFT ECHO: metric=ecpm, |deviation_pct| < 10, and overlapping_incidents contains a
  fill_rate incident >= 3x larger whose segment family intersects this one
  -> FALSE_POSITIVE, reason "derived mix shift of <segment>".
3 PAIR-CELL SHADOW: a two-dimension segment whose parent appears in overlapping_incidents with
  |deviation| within 1.4x of this one -> FALSE_POSITIVE.
4 GATE-BOUNDARY NOISE: |deviation_pct| <= 6 AND snr < 8 (deviation under 8x the segment noise),
  days <= 2, no other decomposition factor beyond +-2, no opposite-sign sibling -> FALSE_POSITIVE.
5 SWAP: an opposite-sign deviation on a sibling segment in the same window appears in
  overlapping_incidents -> REAL for both sides (revenue-neutral swaps corroborate, not cancel).
6 REAL-SMALL: |deviation_pct| < 10 with snr >= 10 (10x above segment noise), days >= 2, and no
  larger explaining co-incident -> REAL. snr outranks size: a high-snr small deviation is real.
7 GLOBAL: verdict_type GLOBAL_UNLOCALIZED with |deviation_pct| >= 10 -> REAL.
8 Otherwise, or when evidence conflicts -> INCONCLUSIVE. Never guess.

Hard constraints:
- Every numeral in `reason` must appear in that candidate's fields.
- No world knowledge: no seasonality, holidays, or ad-tech priors. Missing field = unknown.
- Never invent, merge, or drop an id.

Output: {"verdicts":[{"id":"...","verdict":"REAL"|"FALSE_POSITIVE"|"INCONCLUSIVE",
"confidence":0.0-1.0,"reason":"one sentence citing input fields"}]}"""

FEWSHOTS = [
  {"role":"user","content":'[{"id":"x1","metric":"ecpm","verdict_type":"LOCALIZED_1D","segment":"MEA","window":["2026-06-29","2026-06-30"],"days":2,"deviation_pct":-5.3,"snr":5.9,"decomposition":[{"fill_rate":0.2},{"requests":-0.4}],"ruled_out_context":[],"overlapping_incidents":[]}]'},
  {"role":"assistant","content":'{"verdicts":[{"id":"x1","verdict":"FALSE_POSITIVE","confidence":0.85,"reason":"-5.3 over 2 days with flat decomposition and no sibling matches gate-boundary noise"}]}'},
  {"role":"user","content":'[{"id":"x2","metric":"ecpm","verdict_type":"LOCALIZED_2D","segment":"region=EU × category=utility","window":["2026-06-27","2026-06-28"],"days":2,"deviation_pct":-5.8,"snr":7.2,"decomposition":[{"fill_rate":-6.1}],"ruled_out_context":[],"overlapping_incidents":["fill_rate LOCALIZED_1D fill_rate -31.8% at ad_format=rewarded"]},{"id":"x3","metric":"fill_rate","verdict_type":"LOCALIZED_1D","segment":"iOS 17.5","window":["2026-06-08","2026-06-09"],"days":2,"deviation_pct":-6.0,"snr":12.0,"decomposition":[{"ecpm":0.4}],"ruled_out_context":[],"overlapping_incidents":[]}]'},
  {"role":"assistant","content":'{"verdicts":[{"id":"x2","verdict":"FALSE_POSITIVE","confidence":0.9,"reason":"derived mix shift: overlapping fill_rate -31.8% dwarfs -5.8 on an intersecting segment"},{"id":"x3","verdict":"REAL","confidence":0.88,"reason":"-6.0 sustained 2 days with flat decomposition and no co-incident is a real small incident"}]}'},
]


def _post(url, payload, key, timeout):
    req = urllib.request.Request(url, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json",
                                  "Authorization": f"Bearer {key or 'ollama'}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _env(path=".env"):
    c = {}
    try:
        for l in open(path):
            l = l.strip()
            if l and not l.startswith("#") and "=" in l:
                k, v = l.split("=", 1); c[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return c


def backends():
    env = {**_env(), **os.environ}
    # CLAUDE.md's connection block names the team-standard variable LLM_API_KEY; reading only
    # OPENAI_API_KEY silently drops a correctly-filled .env straight to the Ollama/deterministic tier.
    key = env.get("OPENAI_API_KEY") or env.get("LLM_API_KEY", "")
    out = []
    if env.get("LLM_BASE_URL"):
        out.append((env["LLM_BASE_URL"].rstrip("/") + "/chat/completions",
                    env.get("LLM_MODEL", "gpt-4o-mini"), key))
    if key.startswith("sk-"):
        out.append(("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", key))
    # default = the bake-off winner; hermes3-8b misrules the known-FP case
    out.append(("http://localhost:11434/v1/chat/completions",
                env.get("ADJ_MODEL", "codex-qwen25-coder-7b:latest"), ""))
    return out


def candidates_from(bundle):
    """Compact evidence records — only computed fields, ~120 tokens each."""
    invs = bundle.get("investigations", [])
    cands = []
    for i, inv in enumerate(invs):
        c = inv.get("culprit") or {}
        dev = c.get("deviation_pct")
        if dev is None and inv.get("rel") is not None:
            dev = round(inv["rel"] * 100, 1)
        if dev is None:
            m = re.search(r"([+-]?\d+(?:\.\d+)?)%", inv.get("headline", ""))
            dev = float(m.group(1)) if m else None
        fills = [f"{v.get('metric', inv['metric'])} {v.get('verdict', '')} {v.get('headline', '')}"
                 for v in invs if v is not inv and not (inv["window"][1] < v["window"][0]
                                                        or inv["window"][0] > v["window"][1])]
        cands.append({
            "id": inv.get("id", f"inv_{i}"),
            "metric": inv["metric"],
            "verdict_type": inv.get("verdict"),
            "segment": c.get("seg") or c.get("segment") or "(global)",
            "window": inv.get("window"), "days": None if not inv.get("window") else
                1 + (_date(inv["window"][1]) - _date(inv["window"][0])).days,
            "deviation_pct": dev,
            "snr": c.get("snr"),
            "decomposition": [{d["factor"]: d.get("deviation_pct")}
                              for d in inv.get("decomposition", [])][:4],
            "ruled_out_context": [r.get("why", "") for r in inv.get("ruled_out", [])][:4],
            "overlapping_incidents": fills[:3],
        })
    return cands


def adjudicate(bundle):
    cands = [c for c in candidates_from(bundle)
             if c["deviation_pct"] is not None and abs(c["deviation_pct"]) < SOLID]
    if not cands:
        return {}, "none (no sub-gate candidates)", 0.0
    user = ("Rule every candidate. Candidates:\n" +
            json.dumps(cands, ensure_ascii=False))
    t0 = time.time()
    for url, model, key in backends():
        remaining = TIMEOUT_S - (time.time() - t0)
        if remaining < 3:
            break
        try:
            payload = {"model": model, "temperature": 0, "max_tokens": MAXTOK,
                       "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": SYSTEM}, *FEWSHOTS,
                                    {"role": "user", "content": user}]}
            try:
                resp = _post(url, payload, key, remaining)
            except Exception:  # some servers reject response_format — retry once without
                payload.pop("response_format", None)
                resp = _post(url, payload, key, max(3, TIMEOUT_S - (time.time() - t0)))
            txt = resp["choices"][0]["message"]["content"]
            verdicts = {v["id"]: v for v in json.loads(txt)["verdicts"]
                        if v.get("verdict") in ("REAL", "FALSE_POSITIVE", "INCONCLUSIVE")}
            if verdicts:
                return verdicts, f"{model}@{url.split('/')[2]}", time.time() - t0
        except Exception:
            continue
    return {}, "deterministic-fallback", time.time() - t0


def apply(bundle, verdicts, source, latency):
    reported, review, suppressed = [], [], []
    for inv in bundle.get("investigations", []):
        c = inv.get("culprit") or {}
        dev = c.get("deviation_pct")
        if dev is None and inv.get("rel") is not None: dev = inv["rel"] * 100
        if dev is None:
            m = re.search(r"([+-]?\d+(?:\.\d+)?)%", inv.get("headline", "")); dev = float(m.group(1)) if m else 0
        dev = abs(dev)
        v = verdicts.get(inv.get("id"))
        if dev >= SOLID or "GLOBAL" in str(inv.get("verdict", "")):
            # invariant: the LLM cannot suppress a solid or global incident — annotate only
            if v: inv["adjudication"] = {"verdict": "REAL", "confidence": v.get("confidence"),
                                         "reason": "solid (>=10%) — deterministic, LLM annotation only"}
            reported.append(inv); continue
        if v:
            conf = v.get("confidence")
            verdict = v["verdict"]
            if not isinstance(conf, (int, float)) or conf < MINCONF:
                verdict = "INCONCLUSIVE"   # low-confidence suppression is forbidden
            inv["adjudication"] = {"verdict": verdict, "confidence": conf,
                                   "reason": str(v.get("reason", ""))[:300]}
            tray = {"REAL": reported, "FALSE_POSITIVE": suppressed}.get(verdict, review)
        else:  # deterministic fallback: yesterday's precision-first behavior
            inv["adjudication"] = {"verdict": "REAL" if dev >= SOLID else "INCONCLUSIVE",
                                   "confidence": None, "reason": "deterministic gate (LLM unavailable)"}
            tray = reported if dev >= SOLID else review
        tray.append(inv)
    bundle["investigations"] = reported
    bundle["needs_review"] = review
    bundle["suppressed"] = suppressed
    bundle["scan_summary"]["adjudication"] = {
        "source": source, "latency_s": round(latency, 2),
        "reported": len(reported), "needs_review": len(review), "suppressed": len(suppressed)}
    return bundle


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    b = json.load(open(src))
    verdicts, source, latency = adjudicate(b)
    b = apply(b, verdicts, source, latency)
    json.dump(b, open(dst, "w"), indent=2)
    s = b["scan_summary"]["adjudication"]
    print(f"adjudicated via {s['source']} in {s['latency_s']}s: "
          f"{s['reported']} reported, {s['needs_review']} needs_review, {s['suppressed']} suppressed")
