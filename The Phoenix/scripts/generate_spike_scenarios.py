#!/usr/bin/env python3
"""Deterministic spike-sustainability scenarios: one healthy spike, one weak spike.

    python3 scripts/generate_spike_scenarios.py --scenario both
    python3 scripts/generate_spike_scenarios.py --scenario healthy --sessions 2000   # rehearsal

Two spikes acquire an identical audience (20,000 sessions over three minutes) and then behave
completely differently. The healthy one holds; the weak one bleeds out through early ends,
backgrounding that never returns, heartbeat timeouts and errors. Peak concurrency is nearly the
same for both, which is the entire point: a system that only detects spikes cannot tell them
apart, and a system that measures *foreground* retention can.

WHY THIS IS GENERATED TO CSV AND NOT INSERTED SERVER-SIDE, unlike scripts/live_producer.sh. That
producer wants realistic volume at wall-clock speed and does not care whether two runs agree. This
wants the opposite: byte-identical output for a given seed, so a correctness gate can compare a
ground-truth derivation against the optimized one and blame any difference on the pipeline rather
than on the data having moved. Determinism beats throughput here.

WHY arrival_timestamp IS NOT EMITTED, though the spec asks for it. raw_events_landing deliberately
does not carry that column: it matches the CSV exactly, and per sql/schema/01_raw_events.sql a
producer that supplies its own arrival time is supplying a claim rather than an observation. The
real value is materialised by raw_events_mv as now64(3) at insert. Out-of-order tests still work,
because lateness is measured against that observed arrival and not against a self-reported one.

The fixed dimension values below are deliberately OUT of the corpus vocabulary
(app_version 'spike-test-1.0.0', player 'synthetic-player-1'). That is test isolation, not drift:
content_id 990001 and these markers make every synthetic row identifiable for cleanup, and this
scenario runs in phoenix_next, isolated by content_id rather than by database, and phoenix (the
graded corpus) is never written to.
"""
import argparse
import csv
import json
import os
import random
from datetime import datetime, timedelta, timezone

CONTENT_ID = 990001
HEARTBEAT_S = 30
NEUTRAL_HEARTBEATS = ["network-activity", "buffer-health", "video-resize", "BufferStart", "BufferEnd"]

COLUMNS = [
    "content_id", "video_session_id", "user_id", "event_type", "event", "event_timestamp",
    "platform", "app_version", "country", "audio_language", "subtitle_language",
    "player_version", "session_start_epoch",
]

FIXED_DIMS = {
    "platform": "ANDROID_PHONE",
    "app_version": "spike-test-1.0.0",
    "country": "india",
    "audio_language": "hindi",
    "subtitle_language": "none",
    "player_version": "synthetic-player-1",
}

# Wave sizes as fractions, so --sessions scales a rehearsal without changing the shape.
WAVES = [0.30, 0.35, 0.35]

# (name, share, kind). Shares must sum to 1.0; asserted at startup rather than trusted.
HEALTHY_SEGMENTS = [
    ("H-long",              0.75, "end_at"),        # active 20 min, then end
    ("H-mid",               0.15, "end_at"),        # 12 min
    ("H-short",             0.05, "end_at"),        # 6 min
    ("H-background-return", 0.03, "bg_return"),     # background at 6 min, back at 7.5, end at 18
    ("H-timeout",           0.01, "timeout"),       # heartbeats simply stop after 7 min
    ("H-error",             0.01, "error"),         # VideoError after 9 min
]
HEALTHY_PARAMS = {
    "H-long": (1200, 1200), "H-mid": (720, 720), "H-short": (360, 360),
    "H-background-return": (1080, 1080), "H-timeout": (420, 420), "H-error": (540, 540),
}

WEAK_SEGMENTS = [
    ("W-early-end",             0.20, "end_at"),
    ("W-background-no-return",  0.15, "bg_no_return"),
    ("W-heartbeat-timeout",     0.10, "timeout"),
    ("W-short-stay",            0.20, "end_at"),
    ("W-mid-stay",              0.20, "end_at"),
    ("W-long-stay",             0.10, "end_at"),
    ("W-video-error",           0.05, "error"),
]
WEAK_PARAMS = {
    "W-early-end":            (150, 240),
    "W-background-no-return": (120, 300),
    "W-heartbeat-timeout":    (120, 240),
    "W-short-stay":           (300, 480),
    "W-mid-stay":             (540, 720),
    "W-long-stay":            (900, 900),
    "W-video-error":          (120, 300),
}


def ms(dt):
    return int(dt.timestamp() * 1000)


def assign_segments(segments, n, rng):
    """Exact counts, not per-session sampling: 20,000 draws at p=0.01 does not reliably give 200,
    and the acceptance thresholds in the spec are tight enough that the difference shows."""
    out = []
    for name, share, kind in segments[:-1]:
        out += [(name, kind)] * int(round(share * n))
    last = segments[-1]
    out += [(last[0], last[2])] * (n - len(out))
    rng.shuffle(out)
    return out


def session_events(sid, uid, start, segment, kind, params, rng):
    """One session's events, in event-time order. Returns a list of dicts."""
    lo, hi = params[segment]
    duration = lo if lo == hi else rng.randint(lo, hi)
    rows = []

    def add(ts, event_type, event):
        rows.append({
            "content_id": CONTENT_ID, "video_session_id": sid, "user_id": uid,
            "event_type": event_type, "event": event,
            "event_timestamp": ms(ts), "session_start_epoch": ms(start), **FIXED_DIMS,
        })

    add(start, "VideoSessionStart", "Start")
    add(start + timedelta(seconds=1), "VideoPlay", "Play")

    # Heartbeats run to `hb_until`; what happens at the end is the segment's business.
    hb_until = duration
    bg_at = fg_at = None
    if kind == "bg_return":
        bg_at, fg_at = 360, 450
    elif kind == "bg_no_return":
        bg_at = duration
        hb_until = duration          # keeps emitting telemetry while backgrounded, as a real app does
    elif kind == "timeout":
        hb_until = duration          # last heartbeat, then silence and no end event

    t = HEARTBEAT_S
    i = 0
    while t <= hb_until:
        # A backgrounded session still sends telemetry. Neutral heartbeats carry the last decisive
        # state forward, so these do NOT resurrect it; that is exactly why the keepalive must be
        # neutral and must never be 'resume'.
        add(start + timedelta(seconds=t), "VideoHeartbeat", NEUTRAL_HEARTBEATS[i % 5])
        t += HEARTBEAT_S
        i += 1

    if kind == "bg_return":
        add(start + timedelta(seconds=bg_at), "AppBackgrounded", "AppBackgrounded")
        add(start + timedelta(seconds=fg_at), "AppForegrounded", "AppForegrounded")
        add(start + timedelta(seconds=fg_at + 1), "VideoPlay", "Play")
        add(start + timedelta(seconds=duration), "VideoSessionEnd", "VideoSessionEnd")
    elif kind == "bg_no_return":
        add(start + timedelta(seconds=bg_at), "AppBackgrounded", "AppBackgrounded")
    elif kind == "error":
        add(start + timedelta(seconds=duration), "VideoError", "VideoError")
    elif kind == "end_at":
        add(start + timedelta(seconds=duration), "VideoSessionEnd", "VideoSessionEnd")
    # kind == "timeout": nothing. The 90s tolerance closes it, which is the behaviour under test.

    rows.sort(key=lambda r: r["event_timestamp"])
    return rows


def generate(scenario, prefix_s, prefix_u, start_at, n, rng, dup_pct, ooo_pct, path):
    segments = HEALTHY_SEGMENTS if scenario == "healthy" else WEAK_SEGMENTS
    params = HEALTHY_PARAMS if scenario == "healthy" else WEAK_PARAMS
    assert abs(sum(s[1] for s in segments) - 1.0) < 1e-9, f"{scenario} shares do not sum to 1"

    assigned = assign_segments(segments, n, rng)
    counts, total_rows, dups, ooos = {}, 0, 0, 0

    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        idx = 0
        for wave_no, frac in enumerate(WAVES):
            wave_n = int(round(frac * n)) if wave_no < len(WAVES) - 1 else n - idx
            wave_start = start_at + timedelta(minutes=wave_no)
            for _ in range(wave_n):
                segment, kind = assigned[idx]
                counts[segment] = counts.get(segment, 0) + 1
                sid = f"{prefix_s}{idx:06d}"
                uid = f"{prefix_u}{idx:06d}"
                # Joins are spread across the wave's minute rather than stacked on its first
                # second, so the minute-grain curve ramps instead of stepping.
                start = wave_start + timedelta(milliseconds=rng.randint(0, 59_999))
                rows = session_events(sid, uid, start, segment, kind, params, rng)

                # Robustness injections, per spec section 7. Both must leave the final answer
                # unchanged: a duplicate is the same row twice, and out-of-order changes only the
                # order rows ARRIVE in, never their event_timestamp.
                if rng.random() < dup_pct:
                    hbs = [r for r in rows if r["event_type"] == "VideoHeartbeat"]
                    if hbs:
                        rows.append(dict(rng.choice(hbs)))
                        dups += 1
                if rng.random() < ooo_pct and len(rows) >= 3:
                    j = rng.randrange(len(rows) - 1)
                    rows[j], rows[j + 1] = rows[j + 1], rows[j]
                    ooos += 1

                w.writerows(rows)
                total_rows += len(rows)
                idx += 1

    return {"sessions": n, "rows": total_rows, "segments": counts,
            "duplicates_injected": dups, "out_of_order_injected": ooos,
            "start": start_at.isoformat().replace("+00:00", "Z")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["healthy", "weak", "both"], default="both")
    ap.add_argument("--sessions", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20260802)
    ap.add_argument("--healthy-start", default="2026-08-02T06:00:00Z")
    ap.add_argument("--weak-start", default="2026-08-02T07:00:00Z")
    ap.add_argument("--output-dir", default="data/generated")
    ap.add_argument("--duplicate-percent", type=float, default=2.0)
    ap.add_argument("--out-of-order-percent", type=float, default=2.0)
    a = ap.parse_args()

    os.makedirs(a.output_dir, exist_ok=True)
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    manifest = {"seed": a.seed, "content_id": CONTENT_ID,
                "duplicate_percent": a.duplicate_percent,
                "out_of_order_percent": a.out_of_order_percent}

    for scenario, prefix_s, prefix_u, start in (
        ("healthy", "spike-h-", "user-h-", parse(a.healthy_start)),
        ("weak",    "spike-w-", "user-w-", parse(a.weak_start)),
    ):
        if a.scenario not in (scenario, "both"):
            continue
        # One RNG per scenario, seeded from the base seed, so generating only the weak scenario
        # produces byte-identical weak output to generating both.
        rng = random.Random(a.seed + (0 if scenario == "healthy" else 1))
        path = os.path.join(a.output_dir, f"spike_{scenario}_events.csv")
        info = generate(scenario, prefix_s, prefix_u, start, a.sessions, rng,
                        a.duplicate_percent / 100.0, a.out_of_order_percent / 100.0, path)
        info["file"] = path
        manifest[scenario] = info
        print(f"{scenario}: {info['sessions']} sessions, {info['rows']} rows -> {path}")
        for k, v in sorted(info["segments"].items()):
            print(f"    {k:24s} {v}")

    mpath = os.path.join(a.output_dir, "spike_manifest.json")
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"manifest -> {mpath}")


if __name__ == "__main__":
    main()
