#!/usr/bin/env python3
"""Runs the REAL detect->decompose->drill-down->narrate pipeline against the
synthetic test dataset (scripts/generate_test_dataset.py) in a separate
ClickHouse database (clickathon_test), and checks its findings against the
known ground truth (test_data_ground_truth.json) -- not just "did it run",
but "did it find the right answer".

Does not touch the real `clickathon` database or implementation/.env at all:
points rca.pipeline.get_client at clickathon_test directly.

Usage: python3 scripts/validate_test_dataset.py
"""

import json
import sys
from datetime import timedelta
from pathlib import Path

import clickhouse_connect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rca import pipeline, baseline  # noqa: E402
from rca.config import settings  # noqa: E402

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "test_data_ground_truth.json"

_client = clickhouse_connect.get_client(
    host=settings.clickhouse_host, port=settings.clickhouse_port,
    username=settings.clickhouse_user, password=settings.clickhouse_password,
    database="clickathon_test", secure=settings.clickhouse_secure,
)
pipeline.get_client = lambda: _client  # only affects pipeline.scan/investigate's lookups

PASS, FAIL = [], []


def check(cond: bool, msg: str):
    (PASS if cond else FAIL).append(msg)
    print(f"  {'PASS' if cond else 'FAIL'}: {msg}")


def walk_chain(drill_down):
    chain = []
    level = drill_down
    while level and level.get("primary_segment"):
        chain.append(level["primary_segment"])
        level = level.get("deeper")
    return chain


def main():
    manifest = json.loads(MANIFEST_PATH.read_text())
    print(f"Loaded manifest: {manifest['date_range']}, {len(manifest['scenarios'])} scenarios\n")

    for sc in manifest["scenarios"]:
        print(f"=== {sc['name']} ({sc['metric']}, {sc['window'][0]}..{sc['window'][1]}) ===")
        metric = sc["metric"]
        win_start, win_end = pipeline.parse_date(sc["window"][0]), pipeline.parse_date(sc["window"][1])

        # --- Detection: does scan() notice something overlapping this window? ---
        scan_start, scan_end = win_start - timedelta(days=3), win_end + timedelta(days=3)
        results = pipeline.scan(scan_start, scan_end, metrics=[metric], lookback_weeks=4)
        incidents = results[0]["incidents"] if results else []
        overlapping = [
            inc for inc in incidents
            if inc.start <= win_end and inc.end >= win_start
        ]
        check(len(overlapping) >= 1, f"scan() detected an incident overlapping the planted window (found {len(incidents)} incident(s) total)")

        # --- Attribution: investigate the EXACT planted window, check the real answer ---
        result = pipeline.investigate(metric, win_start, win_end, max_depth=2)
        chain = walk_chain(result["drill_down"])
        depth = len(chain)

        check(depth == sc["expected_depth"], f"drill depth == {sc['expected_depth']} (got {depth})")

        if sc["expected_depth"] == 0:
            check(chain == [], "no primary segment at any level (correctly broad-based)")
        elif "expected_dimension_path" in sc:
            for i, (dim, val) in enumerate(sc["expected_dimension_path"]):
                if i < len(chain):
                    check(chain[i]["dimension"] == dim, f"level {i} dimension == {dim} (got {chain[i]['dimension']})")
                    check(chain[i]["value"] == val, f"level {i} value == {val} (got {chain[i]['value']})")
                else:
                    check(False, f"level {i} missing from chain entirely")
        else:
            if chain:
                check(chain[0]["dimension"] == sc["expected_dimension"], f"root dimension == {sc['expected_dimension']} (got {chain[0]['dimension']})")
                check(chain[0]["value"] == sc["expected_value"], f"root value == {sc['expected_value']} (got {chain[0]['value']})")
            else:
                check(False, "expected a localized segment but chain is empty")

        print(f"  narrative: {result['narrative'][:200]}...")
        print()

    print("=" * 60)
    print(f"TOTAL: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("\nFailures:")
        for f in FAIL:
            print(" -", f)
        sys.exit(1)
    print("\nALL SCENARIOS VALIDATED CORRECTLY")


if __name__ == "__main__":
    main()
