#!/usr/bin/env python3
"""Characterize the shape of both known incidents."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB, _load_env             # noqa: E402
from engine.characterize import characterize    # noqa: E402

CASES = [
    ("Android 15 fill-rate collapse",
     dict(start="2026-06-23 00:00:00", end="2026-06-25 23:00:00",
          factor="fill_rate", dim_name="os_version", dim_value="Android 15")),
    ("2026-06-21 global traffic loss",
     dict(start="2026-06-21 00:00:00", end="2026-06-21 23:00:00", factor="requests")),
]


def main():
    _load_env()
    db = DB()
    for label, kw in CASES:
        s = characterize(db, **kw)
        print("=" * 76)
        print(f"{label}   [{s.scope}]")
        print("=" * 76)
        if s.onset:
            print(f"  onset    {s.onset.at_hour}  {s.onset.before:.4g} -> {s.onset.after:.4g}"
                  f"   shape={s.onset.shape}  step={s.onset.step_fraction:.0%}"
                  f"  day_boundary={s.onset.aligns_to_day_boundary}")
        if s.recovery:
            print(f"  recovery {s.recovery.at_hour}  shape={s.recovery.shape}"
                  f"  day_boundary={s.recovery.aligns_to_day_boundary}")
        print(f"  duration {s.duration_hours}h")
        print(f"  held steady: {s.held_steady or '(none)'}")
        print(f"\n  READING\n    {s.reading}")
        if s.rules_out:
            print("\n  RULES OUT")
            for r in s.rules_out:
                print(f"    - {r}")
        print()


if __name__ == "__main__":
    main()
