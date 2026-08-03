#!/usr/bin/env python3
"""Profile the SonyLIV raw event dataset and validate the concurrency model.

    python3 scripts/profile_dataset.py RAW.csv CONTENT.csv

CONCURRENCY MODEL (jury ruling): a minute counts for a session if that minute
contains at least one `event_type = 'VideoHeartbeat'` row. No timeout, no grace
period, no gap rule, no pause/background handling.

    CCU(minute) = count of distinct sessions with >=1 heartbeat in that minute

That model rests on ONE assumption, which check_model_assumption() tests:

    the heartbeat interval must be shorter than 60 seconds

If heartbeats arrive every 40s, any minute of genuine viewing contains at least
one -- so presence-per-minute and actually-watching are the same thing. If the
interval ever exceeds 60s, active minutes start coming up empty and we silently
UNDERCOUNT. Nothing else in the pipeline would notice.

That is the check worth running on the unseen day. The rest is data hygiene.
"""
import csv
import collections
import datetime as dt
import sys

MINUTE_MS = 60_000


def load(path):
    """-> {session_id: [(ts_ms, event, event_type)]}, dim counters, content ids."""
    rd = csv.reader(open(path, newline=""))
    hdr = next(rd)
    I = {c: i for i, c in enumerate(hdr)}
    sessions = collections.defaultdict(list)
    dims = collections.defaultdict(collections.Counter)
    content_of = {}
    dimcols = ["platform", "country", "audio_language", "subtitle_language",
               "app_version", "player_version"]
    for r in rd:
        s = r[I["video_session_id"]]
        sessions[s].append((int(r[I["event_timestamp"]]), r[I["event"]], r[I["event_type"]]))
        content_of[s] = r[I["content_id"]]
        for c in dimcols:
            dims[c][r[I[c]]] += 1
    for s in sessions:
        sessions[s].sort()
    return sessions, dims, content_of


def pct(sorted_vals, q):
    return sorted_vals[min(int(len(sorted_vals) * q), len(sorted_vals) - 1)]


def check_shape(sessions):
    n = sum(len(v) for v in sessions.values())
    ts = [t for v in sessions.values() for t, _, _ in v]
    lo, hi = min(ts), max(ts)
    print(f"rows={n:,}  sessions={len(sessions):,}")
    print(f"time: {dt.datetime.fromtimestamp(lo/1000, dt.UTC)} .. "
          f"{dt.datetime.fromtimestamp(hi/1000, dt.UTC)} UTC  ({(hi-lo)/3600000:.1f}h span)")
    day = collections.Counter(dt.datetime.fromtimestamp(t/1000, dt.UTC).date() for t in ts)
    for k in sorted(day):
        print(f"    {k}  {day[k]:>9,}")


def check_model_assumption(sessions):
    """THE check. Is the heartbeat interval short enough for minute-presence?

    Measures gaps between consecutive VideoHeartbeat rows within a session. The
    model is safe while the upper percentiles sit below 60s. Sustained gaps above
    60s mean active minutes contain no heartbeat and we undercount them."""
    print("\n=== MODEL ASSUMPTION: heartbeat interval < 60s ===")
    gaps = []
    for v in sessions.values():
        ts = [t for t, _, et in v if et == "VideoHeartbeat"]
        gaps += [(b - a) / 1000 for a, b in zip(ts, ts[1:])]
    if not gaps:
        print("  FATAL: no VideoHeartbeat rows at all -- the model cannot run.")
        return
    gaps.sort()
    for q in (0.5, 0.9, 0.99, 0.999):
        print(f"    p{q*100:<5.1f} {pct(gaps, q):>9.1f}s")
    over = sum(1 for g in gaps if g > 60)
    print(f"    gaps > 60s: {over:,}/{len(gaps):,} ({over/len(gaps):.2%})")
    p99 = pct(gaps, 0.99)
    if p99 < 60:
        print(f"  >> OK. p99 = {p99:.1f}s < 60s, so an active minute reliably "
              f"contains a heartbeat.")
    else:
        print(f"  >> WARNING. p99 = {p99:.1f}s >= 60s. Minutes of genuine viewing will")
        print(f"  >> contain no heartbeat and be counted inactive: CCU is UNDERSTATED.")
        print(f"  >> Do not submit without review.")


def check_concurrency(sessions):
    """CCU under the model, with the naive figure for contrast."""
    print("\n=== CONCURRENCY (minute contains >=1 heartbeat) ===")
    ccu = collections.Counter()
    naive = collections.Counter()
    for v in sessions.values():
        for m in {t // MINUTE_MS for t, _, et in v if et == "VideoHeartbeat"}:
            ccu[m] += 1
        for m in range(v[0][0] // MINUTE_MS, v[-1][0] // MINUTE_MS + 1):
            naive[m] += 1
    if not ccu:
        return
    pk = max(ccu.items(), key=lambda k: k[1])
    pn = max(naive.items(), key=lambda k: k[1])
    fmt = lambda m: dt.datetime.fromtimestamp(m * 60, dt.UTC).strftime("%Y-%m-%d %H:%M")
    print(f"  peak CCU        : {pk[1]:,} at {fmt(pk[0])}")
    print(f"  naive peak      : {pn[1]:,} at {fmt(pn[0])}   ({pn[1]/pk[1]:.2f}x inflated)")
    print(f"  watch-minutes   : {sum(ccu.values()):,}  ({sum(ccu.values())/60:,.0f} h)")
    print(f"  naive minutes   : {sum(naive.values()):,}  "
          f"({sum(naive.values())/sum(ccu.values()):.2f}x)")


def check_completeness(sessions):
    """Cases the provided day contains none of -- so any logic handling them
    stays untested until the unseen day arrives."""
    print("\n=== session completeness ===")
    tot = len(sessions)
    types = {s: collections.Counter(et for _, _, et in v) for s, v in sessions.items()}
    no_end = sum(1 for s in types if "VideoSessionEnd" not in types[s])
    no_hb = sum(1 for s in types if "VideoHeartbeat" not in types[s])
    dup = sum(1 for s in types if types[s].get("VideoSessionStart", 0) > 1)
    print(f"  total                : {tot:,}")
    print(f"  no VideoSessionEnd   : {no_end:,} ({no_end/tot:.1%})   <- open sessions")
    print(f"  NO HEARTBEAT AT ALL  : {no_hb:,} ({no_hb/tot:.1%})   <- invisible to the model")
    print(f"  duplicate Start      : {dup:,}")


def check_dims(dims, content_path, content_of):
    print("\n=== dimension hygiene ===")
    for c, v in dims.items():
        fold = collections.Counter()
        for k, n in v.items():
            fold[k.strip().lower().split("-")[0] or "unknown"] += n
        print(f"  {c:20s} raw={len(v):>4}  casefold+suffix-strip={len(fold):>4}  "
              f"empty={v.get('',0):,}")
    rd = csv.reader(open(content_path))
    next(rd)
    cids, vt = set(), collections.Counter()
    for row in rd:
        cids.add(row[0])
        vt[row[2]] += 1
    ev = set(content_of.values())
    miss = ev - cids
    print(f"\n  content join: {len(ev):,} ids in events, {len(miss):,} missing "
          f"({len(miss)/max(len(ev),1):.1%})")
    print(f"  video_type: {dict(vt)}   (blank -> vod in silver)")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sessions, dims, content_of = load(sys.argv[1])
    check_shape(sessions)
    check_model_assumption(sessions)
    check_concurrency(sessions)
    check_completeness(sessions)
    check_dims(dims, sys.argv[2], content_of)


if __name__ == "__main__":
    main()
