#!/usr/bin/env python3
"""Run the real RCA scanner against many synthetic ClickHouse datasets.

Each seed gets a disposable DB, a hidden manifest, the production `run_incident.py` command, and a
score artifact. This is the closest local rehearsal for the unseen judging dataset.

Usage:
  python tests/eval_many.py --seeds 1-20 --inject 4
  python tests/eval_many.py --seeds 7 --inject 4 --keep-db
"""
import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import battletest as bt
from score_detection import score_bundle

ROOT = Path(__file__).resolve().parents[1]


def parse_seeds(raw):
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = [int(x) for x in part.split("-", 1)]
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    return out


def manifest_for(seed, source_db, target_db, injected, rows):
    incidents = []
    for idx, inc in enumerate(bt.KNOWN, 1):
        incidents.append({
            "id": inc["src"],
            "src": inc["src"],
            "metric": inc["metric"],
            "dim": inc["dim"],
            "value": inc["value"],
            "win": list(inc["win"]),
            "expected_culprit": ({} if inc["dim"] == "__global__" else {inc["dim"]: inc["value"]}),
        })
    for idx, inc in enumerate(injected, 1):
        incidents.append({
            "id": f"SYN-{seed:03d}-{idx:03d}",
            "src": "SYN",
            "metric": inc["metric"],
            "dim": inc["dim"],
            "value": inc["value"],
            "win": list(inc["win"]),
            "drop": inc.get("drop"),
            "direction": "drop",
            "expected_culprit": ({} if inc["dim"] == "__global__" else {inc["dim"]: inc["value"]}),
        })
    return {
        "seed": seed,
        "source_database": source_db,
        "database": target_db,
        "rows": rows,
        "incidents": incidents,
    }


def drop_database(client, db):
    bt.db_name(db)
    client.command(f"DROP DATABASE IF EXISTS {db}")


def run_one(args, client, seed):
    target_db = f"{args.db_prefix}{seed}"
    bt.db_name(target_db)
    run_dir = Path(args.out_dir) / f"seed_{seed}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    rng = random.Random(seed)
    injected = bt.plan_injections(rng, args.inject)

    t0 = time.time()
    bt.build_synth(client, injected, seed, source_db=args.source_db, target_db=target_db)
    rows = client.query(f"SELECT count() FROM {target_db}.ad_events").result_rows[0][0]
    manifest = manifest_for(seed, args.source_db, target_db, injected, rows)
    manifest_path = run_dir / "manifest.json"
    bundle_path = run_dir / "scan_bundle.json"
    score_path = run_dir / "score.json"
    log_path = run_dir / "scan.log"
    json.dump(manifest, open(manifest_path, "w"), indent=2, default=str)

    cmd = [
        sys.executable,
        "run_incident.py",
        "--db",
        target_db,
        "--rebuild-cube",
        "--json",
        str(bundle_path),
    ]
    if args.trace:
        cmd.append("--trace")

    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    log_path.write_text(proc.stdout + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else ""))
    if proc.returncode:
        result = {
            "seed": seed,
            "database": target_db,
            "status": "failed",
            "returncode": proc.returncode,
            "log": str(log_path),
            "elapsed_s": round(time.time() - t0, 2),
        }
        json.dump(result, open(score_path, "w"), indent=2)
        if not args.keep_db:
            drop_database(client, target_db)
        return result

    bundle = json.load(open(bundle_path))
    score = score_bundle(manifest, bundle)
    score.update({
        "seed": seed,
        "database": target_db,
        "status": "ok",
        "elapsed_s": round(time.time() - t0, 2),
        "manifest_path": str(manifest_path),
        "bundle_path": str(bundle_path),
        "log_path": str(log_path),
    })
    json.dump(score, open(score_path, "w"), indent=2, default=str)
    if not args.keep_db:
        drop_database(client, target_db)
    return score


def aggregate(results):
    oks = [r for r in results if r.get("status") == "ok"]
    if not oks:
        return {"runs": len(results), "ok": 0}

    def mean(key):
        vals = [float(r[key]) for r in oks]
        return round(sum(vals) / len(vals), 4)

    def p10(key):
        vals = sorted(float(r[key]) for r in oks)
        return round(vals[max(0, int(len(vals) * 0.1) - 1)], 4)

    misses = {}
    for r in oks:
        for metric, count in r.get("misses_by_metric", {}).items():
            misses[metric] = misses.get(metric, 0) + count

    return {
        "runs": len(results),
        "ok": len(oks),
        "failed": len(results) - len(oks),
        "precision_mean": mean("precision"),
        "precision_p10": p10("precision"),
        "detection_recall_mean": mean("detection_recall"),
        "detection_recall_p10": p10("detection_recall"),
        "localization_recall_mean": mean("localization_recall"),
        "localization_recall_p10": p10("localization_recall"),
        "false_positives_per_run": round(sum(r["false_positives"] for r in oks) / len(oks), 4),
        "avg_elapsed_s": round(sum(r["elapsed_s"] for r in oks) / len(oks), 2),
        "misses_by_metric": misses,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="7", help="comma list or range, e.g. 1-50 or 1,7,11")
    ap.add_argument("--inject", type=int, default=4)
    ap.add_argument("--source-db", default="rca")
    ap.add_argument("--db-prefix", default="rca_synth_seed_")
    ap.add_argument("--out-dir", default="tests/eval_runs")
    ap.add_argument("--trace", action="store_true", help="pass --trace to run_incident.py")
    ap.add_argument("--keep-db", action="store_true", help="keep synthetic DBs for manual debugging")
    args = ap.parse_args()

    seeds = parse_seeds(args.seeds)
    client = bt.connect()
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    results = []
    for seed in seeds:
        print(f"\n=== seed {seed} · inject={args.inject} ===")
        result = run_one(args, client, seed)
        results.append(result)
        if result.get("status") == "ok":
            print(
                f"precision={result['precision']:.2f} "
                f"detection_recall={result['detection_recall']:.2f} "
                f"localization_recall={result['localization_recall']:.2f} "
                f"fp={result['false_positives']} "
                f"elapsed={result['elapsed_s']}s"
            )
        else:
            print(f"FAILED rc={result['returncode']} log={result['log']}")

    summary = aggregate(results)
    summary_path = Path(args.out_dir) / "summary.json"
    json.dump({"summary": summary, "runs": results}, open(summary_path, "w"), indent=2, default=str)

    print("\n=== aggregate ===")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\nwrote {summary_path}")


if __name__ == "__main__":
    main()
