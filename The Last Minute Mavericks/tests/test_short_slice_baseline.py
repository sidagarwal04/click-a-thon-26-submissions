#!/usr/bin/env python3
"""baseline_days on a slice too short to match weekdays.

The 5-day sealed slice (Mon 2026-07-06 .. Fri 2026-07-10) holds ONE of each weekday. The incident
window consumes it, the weekday-matched set comes back empty, and _basep used to emit the literal
`0` predicate -> zero baseline -> LMDI "a factor is zero or missing" on EVERY incident.

Seeds ri._DAYS_CACHE so nothing here touches ClickHouse.  Run: python tests/test_short_slice_baseline.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_incident as ri  # noqa: E402

WEEK = ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"]  # Mon..Fri


def _slice(days):
    """Point _all_days at `days` without a DB round-trip; clear the contamination registry."""
    ri._DAYS_CACHE.clear()
    ri._DAYS_CACHE["t"] = list(days)
    ri._CONTAM.clear()
    return "t"


def test_short_slice_gets_a_baseline_instead_of_nothing():
    db = _slice(WEEK)
    got = ri.baseline_days(None, db, "2026-07-08", "2026-07-09")   # Wed..Thu
    assert got == ["2026-07-06", "2026-07-07"], got
    assert ri._basep(None, db, "2026-07-08", "2026-07-09") != "0"


def test_baseline_is_preceding_only():
    """A live run has no future; later days are leakage (CLAUDE.md: worth 1.7pp)."""
    db = _slice(WEEK)
    for lo, hi in (("2026-07-08", "2026-07-09"), ("2026-07-09", "2026-07-10"),
                   ("2026-07-08", "2026-07-08")):
        got = ri.baseline_days(None, db, lo, hi)
        assert got, f"{lo}..{hi} still empty"
        assert all(d < lo for d in got), (lo, hi, got)


def test_window_at_slice_start_may_look_forward():
    """Only when there is no preceding day at all — otherwise there'd be no baseline."""
    db = _slice(WEEK)
    got = ri.baseline_days(None, db, "2026-07-06", "2026-07-06")
    assert got and all(d > "2026-07-06" for d in got), got


def test_weekend_days_stay_out_of_a_weekday_baseline():
    """The confound weekday-matching exists to prevent: a -20% weekend day in a weekday baseline
    inflates the deviation. Slice = Fri..Tue, window = Mon."""
    db = _slice(["2026-07-03", "2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07"])
    got = ri.baseline_days(None, db, "2026-07-06", "2026-07-06")   # Mon
    assert got == ["2026-07-03"], got                              # Fri, not Sat/Sun


def test_long_slice_is_untouched_by_the_fallback():
    """35 days = 5 of each weekday, so the fallback is unreachable and the baseline stays
    strictly same-weekday and preceding — byte-identical to the old behavior."""
    from datetime import date, timedelta
    start = date(2026, 6, 1)
    db = _slice([str(start + timedelta(days=i)) for i in range(35)])
    lo = hi = "2026-06-24"                                          # a Wednesday
    got = ri.baseline_days(None, db, lo, hi)
    assert got, "long slice lost its baseline"
    assert all(date.fromisoformat(d).isoweekday() == 3 for d in got), got
    assert all(d < lo for d in got), got





# --- the judge-facing footnote -------------------------------------------------------------
# ui/rca_text.py used to hardcode "the same weekdays" regardless of what the engine did, which
# printed a claim the SQL did not support once the short-slice fallback existed.

def test_footnote_reports_the_rule_that_actually_ran():
    from ui.rca_text import _baseline_sentence as h
    weekday = h("same weekdays preceding 2026-06-16..2026-06-18 "
                "(9 days: 2026-05-27..2026-06-11), window + other incidents excluded")
    flat = h("nearest days, weekday match impossible on a slice this short preceding "
             "2026-07-08..2026-07-09 (2 days: 2026-07-06..2026-07-07), "
             "window + other incidents excluded")
    assert "same weekdays" in weekday, weekday
    assert "nearest days" in flat and "same weekdays" not in flat, flat
    assert "(2 days)" in flat, flat


def test_footnote_does_not_invent_a_baseline_when_there_is_none():
    from ui.rca_text import _baseline_sentence as h
    out = h("no baseline available for 2026-07-08..2026-07-09 — decomposition not computed")
    assert "Normal" not in out or "no comparable" in out.lower(), out
    assert "2026" not in out and "Jul" not in out, out


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as e:
            fails += 1
            print(f"  FAIL {name}: {e}")
    print("FAILED" if fails else "all baseline tests pass")
    sys.exit(1 if fails else 0)
