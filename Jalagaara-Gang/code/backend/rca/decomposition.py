"""Lane B (JAL-30): factor decomposition via the revenue identity.

Revenue ~= Requests x FillRate x eCPM/1000. We attribute the total revenue change across those three
factors with an LMDI (Log-Mean Divisia Index) decomposition — the exact, additive form of a
"log-additive" attribution: each factor's contribution is `L(R_obs, R_exp) * ln(f_obs/f_exp)`, where
L is the logarithmic mean, and the three contributions sum EXACTLY to the revenue delta. The factor
carrying the largest-magnitude contribution is `primary_factor`; small/offsetting ones fall out as
near-zero (and become ruled_out upstream, JAL-31).

Note the identity omits render_rate (~0.98 here, stable), so it reconstructs revenue up to that
constant — it cancels in the percentages. Numbers come from one logged SQL query (traceability).
"""
from __future__ import annotations

import math
from datetime import datetime

from config import config
from config import hourly_source as _hourly
from data.client import run_query
from metrics import ecpm, fill_rate, revenue_from_identity, safe_div
from models import Factor, FactorDecomposition, Window

_RCA = config()["rca"]
_IDENTITY = _RCA["revenue_identity_factors"]  # ["requests", "fill_rate", "ecpm"]
_OFFSET_FLOOR = 0.75  # if |net revenue delta| < this * gross factor movement, factors offset -> use share-of-gross

# One place mapping each identity factor to its value from a dict of component sums.
_FACTOR_VALUE = {
    "requests": lambda s: float(s["requests"]),
    "fill_rate": lambda s: fill_rate(s["fills"], s["requests"]),
    "ecpm": lambda s: ecpm(s["revenue"], s["impressions"]),
}


# ---- pure LMDI attribution (no DB) -----------------------------------------

def _logmean(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return a if a == b else (a - b) / (math.log(a) - math.log(b))


def decompose_from_sums(obs: dict, exp: dict) -> FactorDecomposition:
    """LMDI-decompose the revenue change implied by component sums into the identity factors."""
    ov = {f: _FACTOR_VALUE[f](obs) for f in _IDENTITY}
    ev = {f: _FACTOR_VALUE[f](exp) for f in _IDENTITY}
    r_obs = revenue_from_identity(ov["requests"], ov["fill_rate"], ov["ecpm"])
    r_exp = revenue_from_identity(ev["requests"], ev["fill_rate"], ev["ecpm"])
    total = r_obs - r_exp
    weight = _logmean(r_obs, r_exp)

    contribution = {}
    for f in _IDENTITY:
        fo, fe = ov[f], ev[f]
        contribution[f] = weight * (math.log(fo) - math.log(fe)) if fo > 0 and fe > 0 else 0.0

    # contribution_pct is a factor's share of the revenue delta (c/total). When factors OFFSET, the
    # net delta collapses toward zero while the gross factor movement doesn't, so c/total explodes
    # (thousands of percent). In that regime report share-of-GROSS-movement instead — bounded in
    # [-1,1], signed by each factor's own direction — which is the honest read when revenue is ~flat.
    gross = sum(abs(c) for c in contribution.values()) or 1.0
    offsetting = abs(total) < _OFFSET_FLOOR * gross
    denom = gross if offsetting else total

    factors = [Factor(factor=f, contribution_pct=round(safe_div(contribution[f], denom), 4),
                      from_=ev[f], to=ov[f]) for f in _IDENTITY]
    primary = max(_IDENTITY, key=lambda f: abs(contribution[f]))
    return FactorDecomposition(factors=factors, primary_factor=primary)


# ---- engine (runs against ClickHouse) --------------------------------------

_TGT = "hour >= toDateTime({target_start:String}) AND hour < toDateTime({target_end:String})"
_BASE = "hour >= toDateTime({base_start:String}) AND hour < toDateTime({base_end:String})"
_COMPONENTS = ("requests", "fills", "impressions", "revenue")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def decompose(metric: str, target: Window, baseline: Window) -> tuple[FactorDecomposition, list[dict]]:
    """Attribute the revenue change over `target` (vs `baseline`) across the identity factors.

    The decomposition is always over the revenue identity — it explains what drove revenue, which is
    the headline metric regardless of `metric`. Returns (FactorDecomposition, queries).
    """
    cols = ", ".join(f"sumIf({c}, {_TGT}) AS {c}_o, sumIf({c}, {_BASE}) AS {c}_e" for c in _COMPONENTS)
    sql = f"SELECT {cols} FROM {_hourly()} WHERE ({_TGT} OR {_BASE})"
    params = {
        "target_start": _fmt(target.start), "target_end": _fmt(target.end),
        "base_start": _fmt(baseline.start), "base_end": _fmt(baseline.end),
    }
    res = run_query(sql, params, name="sql:factor-sums")
    row = res["rows"][0]
    obs = {c: (row[2 * i] or 0) for i, c in enumerate(_COMPONENTS)}
    exp = {c: (row[2 * i + 1] or 0) for i, c in enumerate(_COMPONENTS)}

    decomposition = decompose_from_sums(obs, exp)
    query = {"id": "q_decompose", "sql": res["resolved_sql"],
             "result_summary": {"primary_factor": decomposition.primary_factor,
                                 "factors": {f.factor: f.contribution_pct for f in decomposition.factors}}}
    return decomposition, [query]
