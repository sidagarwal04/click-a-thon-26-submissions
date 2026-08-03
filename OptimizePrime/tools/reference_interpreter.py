#!/usr/bin/env python3
# tools/reference_interpreter.py — the REFERENCE implementation of the counting
# spec: plain Python over sets of whole seconds, no ClickHouse, no cleverness.
# Derived from the SPEC (docs/EXPLAINER.md, the interval-math skill, the ADRs),
# NOT from sql/30_build_intervals.sql — porting the SQL would only prove the
# code equals itself. Where the spec is ambiguous the STATED repo convention is
# implemented and the dossier is named inline. `model_compat=True` reproduces
# the shipped SQL's two known point-activity drops (see SPEC vs COMPAT below).
#
# This file is deliberately slow and obvious. Its only job is to be trusted by
# inspection. tools/property-test.sh feeds it random sessions and compares it
# against the real pipeline in a scratch database.
#
# ---------------------------------------------------------------------------
# THE SPEC, as implemented here (each convention with its source):
#
#   C1  All boundary arithmetic on WHOLE SECONDS: floor(ms/1000). The shipped
#       derivation truncates the same way; millisecond order inside one second
#       is invisible to both. [doubts/08]
#   C2  EVERY event grants liveness — the instant set is all events of the
#       session, any type. [doubts/11 — shipped allow-all]
#   C3  A session splits into RUNS wherever the gap between consecutive
#       instants exceeds GAP_S=150 (strict >). [ADR 0007; doubts/01;
#       evidence/adversarial #10]
#   C4  Pause/resume are matched on `event` == 'pause' / 'resume' EXACTLY.
#       AdPause, speed-pause, download_resumed are NOT pauses.
#       [doubts/02 §5; evidence/adversarial #9]
#   C5  A pause at second p (with run_start <= p < run_end) is paused from
#       p+1 through r-1 where r is the FIRST resume >= p, session-wide
#       (`>=`: a resume in the same truncated second closes it — ADR 0009).
#       The viewer is still counted AT p (they demonstrably acted at p) and
#       again AT r. If no resume lands inside the run (r absent or beyond
#       run_end), the pause is UNCLOSED: paused from p+1 through run_end
#       inclusive — the CONSERVATIVE rule. [ADR 0007; mentor Q2]
#   C6  The last instant of a run earns TAIL_S=60 of grace — the viewer was
#       watching until at least the next expected beat — but ONLY if the run's
#       last instant is not paused-through (an unclosed pause eats it).
#       A trailing pause AT run_end is outside C5's window ([start, end)), so
#       the run still earns tail: that is the SHIPPED convention, questioned
#       but unresolved in [doubts/07].
#   C7  An active interval [a, b] (closed, b includes tail) covers every
#       minute from floor(a/60) to floor(b/60) INCLUSIVE — membership is
#       any-overlap, not presence-at-the-instant. [doubts/09 — shipped]
#   C8  Dimensions are attributed PER INTERVAL: the DOMINANT (most frequent)
#       raw value among the events inside [a, b-before-tail], ties broken by
#       the smallest value. Duplicate event rows vote. [ADR 0008/0009;
#       doubts/06]
#   C9  A session with no VideoSessionEnd (event_type) is OPEN — flagged, still
#       counted. Events after an end extend the session: "ended" is not
#       "sealed". [ADR 0007]
#
# SPEC vs COMPAT — the one place this file KNOWINGLY disagrees with sql/30:
# the shipped derivation drops zero-length segments (arrayFilter(x -> x.2 >
# x.1)) BEFORE granting tail. Under the spec reading above, point activity is
# still activity:
#   (a) a LONE-EVENT RUN (one instant, >150s from both neighbours): the viewer
#       demonstrably acted at t. Spec: active [t, t+TAIL]. Shipped SQL: nothing.
#   (b) a resume (or pause) landing EXACTLY at a segment boundary, e.g. resume
#       at run_end, or a pause opening the run: the boundary instant itself.
# model_compat=True reproduces the shipped drop so the harness can look PAST
# this family for deeper disagreements. Neither doubts/ nor the ADRs state the
# drop as a convention for case (a)/(b) — sql/30 only justifies it for the
# same-second pause tie, where the two implementations agree anyway.
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policy_reader  # noqa: E402  — tools/ is not a package

# ---------------------------------------------------------------------------
# THE POLICY (ADR 0032). These were literals here until 2026-08-02, which made
# this file an independent IMPLEMENTATION of the spec but not an independent
# CHOICE of parameter — it agreed with the model on GAP_S/TAIL_S by
# construction, so it could never have caught a mis-fit
# (docs/DYNAMIC_PARAMS.md §D3). They now come from policy/model.policy, the one
# declaration the model, the gate and the fixtures also read.
#
# Read from the FILE, not from ClickHouse: this interpreter's whole value is
# that it runs on a list of events with no database, no SQL and no shared code
# with the pipeline. Values are unchanged — GAP_S=150, TAIL_S=60.
# ---------------------------------------------------------------------------
GAP_S = policy_reader.get_int("GAP_S")    # C3 — ADR 0007
TAIL_S = policy_reader.get_int("TAIL_S")  # C6 — ADR 0007; doubts/01 questions the size, not the mechanism
POLICY_STAMP = policy_reader.stamp()

# The seven raw dimensions, in the order they appear everywhere downstream.
DIM_COLS = ("app_version", "audio_language", "subtitle_language",
            "player_version", "user_id", "content_id", "platform", "country")


@dataclass(frozen=True)
class Event:
    """One ev_raw row. ts_ms is the epoch-millisecond event_timestamp."""
    video_session_id: str
    user_id: str
    content_id: int
    event_type: str
    event: str
    ts_ms: int
    platform: str
    app_version: str
    country: str
    audio_language: str
    subtitle_language: str
    player_version: str

    @property
    def sec(self) -> int:
        return self.ts_ms // 1000  # C1


class Interval(NamedTuple):
    """One active interval. start_s/end_s are closed epoch-second bounds;
    end_s already includes tail grace where C6 grants it."""
    video_session_id: str
    user_id: str
    content_id: int
    platform: str
    country: str
    app_version: str
    audio_language: str
    subtitle_language: str
    player_version: str
    start_s: int
    end_s: int
    is_open: int


def _dominant(values: list) -> object:
    """C8: most frequent value, ties to the smallest — a pure function of the
    multiset, so two runs over the same input cannot disagree (ADR 0009)."""
    counts = Counter(values)
    return min(counts, key=lambda v: (-counts[v], v))


def _runs(instants: list[int]) -> list[list[int]]:
    """C3: split the sorted distinct instants where the gap exceeds GAP_S."""
    runs: list[list[int]] = []
    for t in instants:
        if runs and t - runs[-1][-1] <= GAP_S:
            runs[-1].append(t)
        else:
            runs.append([t])
    return runs


def _active_ranges_spec(run: list[int], pauses: list[int], resumes: list[int],
                        conservative: bool) -> list[tuple[int, int]]:
    """C5/C6 the obvious way: a set of active whole seconds, pauses subtracted,
    then the contiguous ranges read back off. Absurdly slow; obviously right."""
    start, end = run[0], run[-1]
    active = set(range(start, end + 1))
    for p in (p for p in pauses if start <= p < end):
        r = next((r for r in resumes if r >= p), None)          # C5: >=
        if r is None and not conservative:
            # permissive variant (NOT shipped; kept so ADR 0007's fork is
            # one flag away): paused only to the next event of any kind.
            r = next((t for t in run if t > p), end)
        if r is not None and r <= end:
            active -= set(range(p + 1, r))                      # counted at p and r
        else:
            active -= set(range(p + 1, end + 1))                # unclosed: eats run
    ranges: list[tuple[int, int]] = []
    for s in sorted(active):
        if ranges and s == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], s)
        else:
            ranges.append((s, s))
    return ranges


def _active_ranges_compat(run: list[int], pauses: list[int], resumes: list[int],
                          conservative: bool) -> list[tuple[int, int]]:
    """The shipped segment fold (sql/30_build_intervals.sql): identical to the
    spec version EXCEPT that zero-length segments are dropped — a lone-event
    run and a boundary-instant resume/pause produce nothing. Exists so the
    harness can look past that known family. This is a knowing port; the SPEC
    version above is the one derived from first principles."""
    start, end = run[0], run[-1]
    windows: list[tuple[int, int]] = []
    for p in (p for p in pauses if start <= p < end):
        r = next((r for r in resumes if r >= p), None)
        if r is None:
            r = end if conservative else next((t for t in run if t > p), end)
        w = (p, min(r, end))
        if w[1] > w[0]:
            windows.append(w)
    segs: list[tuple[int, int]] = []
    cursor = start
    for a, b in sorted(windows):
        if a > cursor:
            segs.append((cursor, a))
        cursor = max(cursor, b)
    if end > cursor:
        segs.append((cursor, end))
    return segs


def derive_intervals(events: Iterable[Event], *, conservative: bool = True,
                     model_compat: bool = False) -> list[Interval]:
    """events (any order, any sessions) -> active intervals, C1..C9."""
    by_session: dict[str, list[Event]] = {}
    for ev in events:
        by_session.setdefault(ev.video_session_id, []).append(ev)

    out: list[Interval] = []
    for sid in sorted(by_session):
        evs = by_session[sid]
        instants = sorted({e.sec for e in evs})                          # C1/C2
        pauses = sorted(e.sec for e in evs if e.event == "pause")        # C4
        resumes = sorted(e.sec for e in evs if e.event == "resume")     # C4
        is_open = int(not any(e.event_type == "VideoSessionEnd" for e in evs))  # C9

        for run in _runs(instants):
            derive = _active_ranges_compat if model_compat else _active_ranges_spec
            for a, b in derive(run, pauses, resumes, conservative):
                # C8: attribute BEFORE tail — no event exists inside the grace.
                seg_events = [e for e in evs if a <= e.sec <= b]
                dims = {c: _dominant([getattr(e, c) for e in seg_events])
                        for c in DIM_COLS}
                # C6: tail only where the segment ends because the run ended.
                end_s = b + (TAIL_S if b == run[-1] else 0)
                out.append(Interval(
                    video_session_id=sid,
                    user_id=dims["user_id"], content_id=dims["content_id"],
                    platform=dims["platform"], country=dims["country"],
                    app_version=dims["app_version"],
                    audio_language=dims["audio_language"],
                    subtitle_language=dims["subtitle_language"],
                    player_version=dims["player_version"],
                    start_s=a, end_s=end_s, is_open=is_open))
    return out


# ---------------------------------------------------------------------------
# Expansion — intervals to per-minute counts, C7. Used both on this file's own
# intervals and on intervals fetched back from the scratch database, so each
# pipeline stage can be checked in isolation.
# ---------------------------------------------------------------------------

def minutes_covered(start_s: int, end_s: int) -> range:
    """C7: every epoch minute from floor(start/60) to floor(end/60) inclusive."""
    return range(start_s // 60 * 60, end_s // 60 * 60 + 60, 60)


def session_minute_counts(intervals: list[Interval]) -> dict[int, int]:
    """Total concurrency: distinct sessions covering each minute (C7).
    uniqExact semantics — one session counts once however many intervals it
    lands on the minute (the merge in 40_deltas exists for exactly this)."""
    per_min: dict[int, set[str]] = {}
    for iv in intervals:
        for m in minutes_covered(iv.start_s, iv.end_s):
            per_min.setdefault(m, set()).add(iv.video_session_id)
    return {m: len(s) for m, s in per_min.items()}


def merged_minute_runs(intervals: list[Interval]) -> list[tuple]:
    """The 40_deltas merge, mirrored from its STATED convention (ADR 0003/0012):
    per session, sort intervals at minute grain and fold; intervals whose minute
    ranges touch or overlap (next start_min <= last end_min + 60) join one run;
    the run keeps the FIRST interval's dimension tuple; disjoint intervals open
    a new run. Returns (sid, start_min, end_min, dims7) rows where dims7 =
    (platform, country, content_id, subtitle, player, audio, app) — the
    cc_minute_delta grain order."""
    by_session: dict[str, list[tuple]] = {}
    for iv in intervals:
        # the SQL sorts (start_min, end_min, app, audio, sub, player,
        # platform, country, content_id) — mirror that sort exactly.
        by_session.setdefault(iv.video_session_id, []).append((
            iv.start_s // 60 * 60, iv.end_s // 60 * 60,
            iv.app_version, iv.audio_language, iv.subtitle_language,
            iv.player_version, iv.platform, iv.country, iv.content_id))
    out: list[tuple] = []
    for sid in sorted(by_session):
        cur_end = -1
        for s, e, app, aud, sub, ply, plat, ctry, cid in sorted(by_session[sid]):
            if not out or out[-1][0] != sid or s > cur_end + 60:
                out.append((sid, s, e, (plat, ctry, cid, sub, ply, aud, app)))
                cur_end = e
            else:
                cur_end = max(cur_end, e)
                last = out[-1]
                out[-1] = (last[0], last[1], cur_end, last[3])
    return out


def grain_minute_counts(intervals: list[Interval]) -> dict[tuple, int]:
    """(minute, dims7) -> concurrent sessions, at the full serving grain.
    Merged runs of one session are minute-disjoint by construction, so a plain
    count per key is a distinct-session count."""
    counts: dict[tuple, int] = {}
    for _sid, s, e, dims in merged_minute_runs(intervals):
        for m in range(s, e + 60, 60):
            counts[(m, dims)] = counts.get((m, dims), 0) + 1
    return counts


def user_minute_sets(intervals: list[Interval]) -> dict[tuple, set[str]]:
    """The user tier, mirrored from sql/45_user_concurrency.sql AS IT IS NOW.

    Folds each session's MINUTE-ADJACENT intervals into one run and attributes
    the whole run to the dimensions of the interval that OPENED it — ADR 0012
    first-wins, matching sql/40_deltas.sql.

    UPDATED 2026-08-02. This mirrored the pre-fix shape (per INTERVAL, not
    merged run) and was not updated when ADR 0031 rewrote sql/45. The mismatch
    showed up as property P6 failing on 3 of 200 cases, every failure
    mirror-only: reference=1 on one platform and 0 on another, same minutes —
    the signature of per-interval expansion against a merge-fold.

    The product defect this oracle used to catch is CLOSED: user concurrency
    exceeded session concurrency in 82 of 91,692 cells (63 with zero sessions)
    and is now 0. An oracle that lags the code it mirrors reports the fix as a
    failure, which is how a suite trains people to ignore it."""
    runs: dict[str, list[Interval]] = {}
    for iv in intervals:
        runs.setdefault(iv.video_session_id, []).append(iv)

    out: dict[tuple, set[str]] = {}
    for _sid, ivs in runs.items():
        ivs = sorted(ivs, key=lambda i: (i.start_s, i.end_s))
        cur_start, cur_end, cur_dims, cur_user = None, None, None, None
        for iv in ivs:
            dims = (iv.platform, iv.country, iv.content_id)
            # minute-adjacent: the next interval opens in the same minute the
            # current one closes, or earlier. Anything further apart is a new run.
            if cur_start is not None and iv.start_s // 60 <= cur_end // 60:
                cur_end = max(cur_end, iv.end_s)          # extend, keep opening dims
                continue
            if cur_start is not None:
                for m in minutes_covered(cur_start, cur_end):
                    out.setdefault((m, cur_dims), set()).add(cur_user)
            cur_start, cur_end, cur_dims, cur_user = iv.start_s, iv.end_s, dims, iv.user_id
        if cur_start is not None:
            for m in minutes_covered(cur_start, cur_end):
                out.setdefault((m, cur_dims), set()).add(cur_user)
    return out
