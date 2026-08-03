"""Revenue identity factor decomposition."""

from __future__ import annotations

from datetime import date
from typing import Any

from clickathon.detect import daily_wow, _parse_day
from clickathon.telemetry import investigation_span


def decompose_factors(day: str | date) -> dict[str, Any]:
    """Attribute wow revenue move to requests vs fill vs eCPM.

    Uses log/additive approximation on the identity:
      Revenue ≈ Requests × Fill × eCPM / 1000
    """
    with investigation_span("decompose.factors", metadata={"day": str(_parse_day(day))}):
        wow = daily_wow(day)
        if wow.get("error"):
            return wow

        t, b = wow["actual"], wow["baseline"]
        # Approximate contribution shares via relative factor moves
        req_chg = wow["deltas"]["req_chg"] or 0.0
        fill_chg_rel = 0.0
        if b["fill_rate"]:
            fill_chg_rel = ((t["fill_rate"] or 0) - b["fill_rate"]) / b["fill_rate"]
        ecpm_chg_rel = 0.0
        if b["ecpm"]:
            ecpm_chg_rel = ((t["ecpm"] or 0) - b["ecpm"]) / b["ecpm"]

        abs_parts = {
            "requests": abs(req_chg),
            "fill_rate": abs(fill_chg_rel),
            "ecpm": abs(ecpm_chg_rel),
        }
        total = sum(abs_parts.values()) or 1.0
        shares = {k: v / total for k, v in abs_parts.items()}
        primary = max(shares, key=shares.get)

        # Prefer absolute flag thresholds when present
        flags = wow["flags"]
        req_chg_v = wow["deltas"]["req_chg"] or 0.0
        # Loud volume crashes dominate multi-factor days (e.g. soft eCPM + −44% requests)
        from clickathon.metrics import THRESH_REQ_CHG

        if req_chg_v <= -THRESH_REQ_CHG:
            primary = "requests"
        elif flags.get("volume") and not flags.get("fill") and not flags.get("ecpm"):
            primary = "requests"
        elif (
            flags.get("fill")
            and (wow["deltas"]["fill_chg"] or 0) < 0
            and abs(wow["deltas"]["fill_chg"] or 0)
            >= abs(wow["deltas"]["ecpm_chg"] or 0) / 10
        ):
            primary = "fill_rate"
        elif flags.get("ecpm") and not flags.get("fill") and (wow["deltas"]["ecpm_chg"] or 0) < 0:
            primary = "ecpm"
        elif flags.get("ecpm") and (wow["deltas"]["ecpm_chg"] or 0) > 0:
            # Positive eCPM wow is often a recovery, not a new price incident
            if (wow["deltas"]["fill_chg"] or 0) < 0:
                primary = "fill_rate"
            elif req_chg_v < 0:
                primary = "requests"

        ruled_out = [k for k, on in flags.items() if not on and k in ("volume", "fill", "ecpm")]

        return {
            "day": wow["day"],
            "baseline_day": wow["baseline_day"],
            "identity": "Revenue ~= Requests * Fill_rate * eCPM / 1000",
            "deltas": wow["deltas"],
            "relative_factor_moves": {
                "requests": req_chg,
                "fill_rate": fill_chg_rel,
                "ecpm": ecpm_chg_rel,
            },
            "contribution_shares": shares,
            "primary_factor": primary,
            "flags": flags,
            "ruled_out_factors": ruled_out,
            "actual": t,
            "baseline": b,
        }
