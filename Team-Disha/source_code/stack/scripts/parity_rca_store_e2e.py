#!/usr/bin/env python3
"""Parity: rca_incidents (materialized) vs discover_incidents (Python oracle)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clickathon.incidents import discover_incidents  # noqa: E402
from clickathon.materialize import CALIBRATION_EXPECTED, check_materialize  # noqa: E402
from clickathon.rca_store import list_incidents_from_store  # noqa: E402


def _match(incidents: list[dict], exp: dict) -> bool:
    for r in incidents:
        if r["primary_factor"] != exp["factor"]:
            continue
        ws, we = str(r["window_start"]), str(r["window_end"])
        if not (ws <= exp["window_contains"] <= we):
            continue
        seg = str(r["segment"])
        if any(tok.lower() in seg.lower() for tok in exp["segment_any"]):
            return True
    return False


def main() -> int:
    chk = check_materialize(calibration=True)
    print("store_check", chk)
    if not chk["ok"]:
        print("FAIL: materialize check")
        return 1

    stored = list_incidents_from_store()["incidents"]
    # Force live Python discovery (bypass store shortcut)
    from clickathon import incidents as inc_mod

    live = inc_mod.discover_incidents()["incidents"]

    print(f"stored={len(stored)} live={len(live)}")
    fail = 0
    for exp in CALIBRATION_EXPECTED:
        s_ok = _match(stored, exp)
        l_ok = _match(live, exp)
        mark = "OK" if s_ok and l_ok else "FAIL"
        print(f"{mark} {exp['label']}: store={s_ok} live={l_ok}")
        if not (s_ok and l_ok):
            fail += 1

    if len(stored) != len(live):
        print(f"WARN count differs store={len(stored)} live={len(live)}")

    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
