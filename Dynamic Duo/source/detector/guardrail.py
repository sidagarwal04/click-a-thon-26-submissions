"""Guardrail: every number in the narrative must exist in the evidence bundle.

    from detector.guardrail import verify
    check = verify(narrative_text, evidence)   # evidence: dict/list or JSON string
    check["ok"]        -> bool: publishable
    check["misses"]    -> [{"token": "12.7%", "value": 12.7, "context": "...fell 12.7% in..."}]
    check["matched"]   -> [(token, evidence_value_it_matched)]

Set diagnoses.numbers_verified from check["ok"]; a False MUST block publication —
"a single fabricated figure costs more than a missed anomaly".

Matching rules (deliberately mechanical, no NLP):
  * every numeric token in the narrative must match some numeric value in the
    evidence within half a unit of the token's displayed precision
    (narrative "4.4%" matches evidence 0.04407 via the x100 form; "0.4333" exact)
  * admitted forms per evidence value v: v and v*100 (fraction <-> percent)
  * dates/times/incident-ids are stripped first; bare small integers (<= 31, no
    decimal/%/$) are exempt — day-of-month and counts like "3 days"; metric
    figures must be cited with their decimals or units, which real narratives do
"""
from __future__ import annotations

import json
import re
import sys

# strip non-metric numerics before extraction
_STRIP_RES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\b"),  # ISO date/time
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),                          # clock time
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
               r"(?:\s*[-–]\s*\d{1,2})?\b", re.IGNORECASE),               # "Jun 23-25"
    re.compile(r"\b\d{1,2}\s*[-–]\s*\d{1,2}\s+"
               r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", re.IGNORECASE),
    re.compile(r"\b\S*_\S*\b"),                                           # ids: inc_2026..., Q1_x
    re.compile(r"\b\d{4}\b(?=\s*(?:$|\W))"),                              # bare years
]
_NUM_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?\s*(?:%|pp|percentage points?)?")


def _extract(narrative: str) -> list[dict]:
    text = narrative
    for rx in _STRIP_RES:
        text = rx.sub(" ", text)
    out = []
    for m in _NUM_RE.finditer(text):
        tok = m.group(0).strip()
        core = tok.lstrip("+-$").replace(",", "")
        unit = ""
        for u in ("percentage points", "percentage point", "pp", "%"):
            if core.endswith(u):
                core, unit = core[: -len(u)].strip(), u
                break
        if not core:
            continue
        val = float(core)
        decimals = len(core.split(".")[1]) if "." in core else 0
        plain_small_int = (decimals == 0 and not unit and "$" not in tok and val <= 31)
        if plain_small_int:
            continue
        ctx = narrative[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
        out.append({"token": tok, "value": abs(val), "decimals": decimals, "context": ctx})
    return out


def _collect(node, acc: set) -> None:
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        v = abs(float(node))
        acc.add(v)
        acc.add(v * 100)          # fraction <-> percent
        return
    if isinstance(node, str):
        try:
            _collect(json.loads(node), acc)   # nested JSON strings (steps.result etc.)
            return
        except (ValueError, TypeError):
            for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", node.replace(",", "")):
                v = abs(float(m.group(0)))
                acc.add(v)
                acc.add(v * 100)
            return
    if isinstance(node, dict):
        for v in node.values():
            _collect(v, acc)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect(v, acc)


def verify(narrative: str, evidence) -> dict:
    if isinstance(evidence, str):
        evidence = json.loads(evidence)
    pool: set[float] = set()
    _collect(evidence, pool)
    matched, misses = [], []
    for tok in _extract(narrative):
        tol = 0.5 * 10 ** (-tok["decimals"]) + 1e-9
        hit = next((v for v in pool if abs(v - tok["value"]) <= tol), None)
        if hit is None:
            misses.append({k: tok[k] for k in ("token", "value", "context")})
        else:
            matched.append((tok["token"], hit))
    return {"ok": not misses, "n_checked": len(matched) + len(misses),
            "matched": matched, "misses": misses}


def _selftest() -> None:
    evidence = {
        "q1": {"fill_rate_delta_pp": -3.455, "requests_pct": 4.36, "inc_fill_rate": 0.4333},
        "q2": [{"seg": "Android 15", "val_base": 0.785, "contribution_pp": -3.368}],
        "note": "share of drop 0.98",
    }
    good = ("On Jun 23-25 fill rate fell 3.455 pp; Android 15 ran 0.4333 vs its usual "
            "0.785 and explains 98% of the drop. Requests (+4.36%) were normal, as were "
            "the other 3 dimensions we checked.")
    bad = "Fill rate fell 12.7% because of Android 15."
    r1, r2 = verify(good, evidence), verify(bad, evidence)
    assert r1["ok"], f"false misses: {r1['misses']}"
    assert not r2["ok"] and r2["misses"][0]["token"] == "12.7%", r2
    # dates/ids/counts exempt; real figures never exempt
    r3 = verify("inc_20260623T00_fill_rate_global spanned 3 days from Jun 23.", evidence)
    assert r3["ok"] and r3["n_checked"] == 0, r3
    print(f"guardrail selftest PASS  (good: {r1['n_checked']} checked, "
          f"bad: caught {r2['misses'][0]['token']})")


if __name__ == "__main__":
    if len(sys.argv) == 3:      # guardrail.py narrative.txt evidence.json
        n = open(sys.argv[1]).read()
        e = open(sys.argv[2]).read()
        res = verify(n, e)
        print(json.dumps(res, indent=2, default=str))
        sys.exit(0 if res["ok"] else 1)
    _selftest()
