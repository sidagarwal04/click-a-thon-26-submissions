#!/usr/bin/env python3
"""Event simulator — replays the SonyLIV raw CSV to the collector over the network.

Stands in for SonyLIV's device fleet / edge publishing the live event feed: it sends
events in event-time order as newline-delimited JSON (the *raw* source fields — the
collector's VRL does the epoch->datetime + normalization transform, just like a real
device would leave that to the ingest edge).

The dataset spans a full day+, so real-time replay is impractical. We compress
*delivery* time with --speed (event-seconds per real-second). We deliberately do NOT
compress the event timestamps themselves — that would squash the ~40s heartbeat cadence
into a single minute and destroy the minute-grain concurrency signal. --rebase-now
applies a constant shift (which preserves every gap/cadence) so the stream looks recent
on a live dashboard.

    speed 60    -> one event-hour per real minute (a day in ~24 min)
    speed 3600  -> one event-hour per real second (a day in ~24 s)

Usage:
    python3 collector/simulator.py                 # full replay at 3600x
    python3 collector/simulator.py --speed 86400   # blast it through fast
    python3 collector/simulator.py --limit 5000 --rebase-now

Config: reads collector/.env (RAW_CSV, HTTP_PORT, COLLECTOR_URL). Pure stdlib.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env(path):
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def post_ndjson(url, events, timeout=30):
    body = "\n".join(json.dumps(e) for e in events).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-ndjson"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def main():
    load_env(os.path.join(HERE, ".env"))
    ap = argparse.ArgumentParser(description="SonyLIV event simulator -> collector")
    ap.add_argument("csv", nargs="?", default=os.environ.get("RAW_CSV"))
    port = os.environ.get("HTTP_PORT", "8080")
    ap.add_argument("--url", default=os.environ.get("COLLECTOR_URL", f"http://localhost:{port}/ingest"))
    ap.add_argument("--speed", type=float, default=3600.0,
                    help="event-seconds per real-second (time compression)")
    ap.add_argument("--window", type=int, default=60,
                    help="event-time seconds delivered per POST batch")
    ap.add_argument("--limit", type=int, default=0, help="cap number of events (0=all)")
    ap.add_argument("--rebase-now", action="store_true",
                    help="constant-shift timestamps so the stream starts ~now (cadence preserved)")
    args = ap.parse_args()
    if not args.csv:
        sys.exit("no CSV path (pass as arg or set RAW_CSV in collector/.env)")

    # read + sort by event_timestamp (keep raw values; build JSON lazily at send time)
    rows = []
    with open(args.csv, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        ti = header.index("event_timestamp")
        si = header.index("session_start_epoch")
        for values in reader:
            try:
                ts = int(values[ti])
            except (ValueError, IndexError):
                continue
            rows.append((ts, values))
            if args.limit and len(rows) >= args.limit:
                break
    if not rows:
        sys.exit("no events to send")
    rows.sort(key=lambda r: r[0])

    t0, tn = rows[0][0], rows[-1][0]
    offset = int(time.time() * 1000) - t0 if args.rebase_now else 0
    span_s = (tn - t0) / 1000.0
    print(f"simulator -> {args.url}")
    print(f"  {len(rows)} events | event span {span_s / 3600:.1f}h | speed {args.speed:g}x "
          f"-> ~{span_s / args.speed:.0f}s wall ({span_s / args.speed / 60:.1f} min)"
          f"{'  [rebased to now]' if offset else ''}")

    def build(values):
        if offset:
            values = list(values)
            values[ti] = str(int(values[ti]) + offset)
            try:
                values[si] = str(int(values[si]) + offset)
            except (ValueError, IndexError):
                pass
        return dict(zip(header, values))

    def send(batch):
        try:
            post_ndjson(args.url, [build(v) for _, v in batch])
        except urllib.error.URLError as e:
            sys.exit(f"failed to reach collector at {args.url}: {e}\n"
                     f"  is it running?  (cd collector && docker compose up -d)")

    win_ms = args.window * 1000
    batch, batch_end, sent = [], t0 + win_ms, 0
    start = time.monotonic()
    for ts, values in rows:
        if ts >= batch_end and batch:
            send(batch)
            sent += len(batch)
            print(f"  t+{(batch_end - t0) / 3.6e6:5.1f}h  sent {sent:>7d}/{len(rows)}", flush=True)
            batch = []
            while ts >= batch_end:
                batch_end += win_ms
            # pace: sleep until this window's real-time target
            target = start + ((batch_end - t0) / 1000.0) / args.speed
            time.sleep(max(0.0, target - time.monotonic()))
        batch.append((ts, values))
    if batch:
        send(batch)
        sent += len(batch)
    print(f"done: {sent} events streamed in {time.monotonic() - start:.0f}s wall clock")


if __name__ == "__main__":
    main()
