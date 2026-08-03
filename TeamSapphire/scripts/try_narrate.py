#!/usr/bin/env python3
"""Investigate the training window, then narrate the top events."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.db import DB, _load_env       # noqa: E402
from engine.investigate import investigate  # noqa: E402
from engine.narrate import narrate         # noqa: E402

TRAIN_START = "2026-06-08 00:00:00"
SEALED_FROM = "2026-07-03 00:00:00"


def main():
    _load_env()
    db = DB()
    inv = investigate(db, TRAIN_START, SEALED_FROM)

    for n, event in enumerate(inv.events[:2], 1):
        e = event.to_dict()
        print("=" * 78)
        print(f"EVENT {n} [{e['classification'].upper()}]  {e['start']} -> {e['end']}")
        print("=" * 78)

        result = narrate(e)
        print(result.text)
        print()
        print(f"  model:  {result.model}  ({result.input_tokens} in / {result.output_tokens} out)")
        if result.all_numbers_verified:
            print("  numbers: ALL VERIFIED against the computed payload")
        else:
            print(f"  numbers: UNVERIFIED -> {result.unverified_numbers}")
        print()


if __name__ == "__main__":
    main()
