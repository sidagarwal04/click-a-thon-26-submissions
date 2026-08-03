#!/usr/bin/env python3
"""Load a test-sql folder's dataset.csv into ClickHouse as {database}.cube.

  python test-sql/load.py test-sql/test1

10,000 rows is one insert. The table is dropped and recreated each run, so the slice is exactly
what dataset.csv says it is — a stale cube from an earlier spec is the one way this harness can
lie to you. Only `cube` is created: run_incident scans the cube and ensure_cube() leaves an
existing one alone, so no ad_events / joins are needed.
"""
import argparse, csv, json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_incident as R                                     # env() + connect() — one source of creds

DDL = Path(__file__).resolve().parent / "cube.sql"
INTS = ["requests", "fills", "impressions", "clicks"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    a = ap.parse_args()
    folder = Path(a.folder).resolve()
    spec = json.load(open(folder / "spec.json")); db = spec["database"]
    csv_path = folder / "dataset.csv"
    if not csv_path.exists():
        sys.exit(f"missing {csv_path} — run: python test-sql/gen.py {a.folder}")

    with open(csv_path) as fh:
        rd = csv.DictReader(fh); cols = rd.fieldnames
        rows = [[date.fromisoformat(r["day"])] +
                [r[c] for c in cols[1:10]] +
                [int(r[c]) for c in INTS] + [float(r["revenue"])] for r in rd]

    cx = R.connect(R.env())
    # drop -- lines BEFORE splitting: a leading comment block would otherwise swallow the statement
    # it documents (the whole chunk starts with '--'), silently skipping CREATE DATABASE.
    ddl = "\n".join(l for l in DDL.read_text().replace("{db}", db).splitlines()
                    if not l.strip().startswith("--"))
    for stmt in (s.strip() for s in ddl.split(";")):
        if stmt: cx.command(stmt)
    cx.insert(f"{db}.cube", rows, column_names=cols)
    # no cache invalidation needed: the scan runs as a separate process, so run_incident's memoised
    # day/volume lookups start empty. Loading and scanning in ONE process would need one.
    n, d0, d1 = cx.query(f"SELECT count(), min(day), max(day) FROM {db}.cube").result_rows[0]
    print(f"  loaded {n:,} rows -> {db}.cube  ({d0} .. {d1})")

if __name__ == "__main__":
    main()
