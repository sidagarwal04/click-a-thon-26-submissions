# ADR 0001 — Derive inactivity from heartbeat gaps, not background events

> **Summary:** Active intervals are closed by heartbeat gaps, with `AppBackgrounded`/`AppForegrounded`
> used only as corroboration. Chosen because those events are documented as not guaranteed and are
> measurably unpaired in the provided data. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01

## Context
The problem is to count only *truly active* playback. Two candidate signals exist: explicit
background/foreground state events, and the 60-second heartbeat cadence.

## Decision
Heartbeat gaps are the **primary** signal. A gap greater than `HEARTBEAT_GAP_S` closes the active
interval. Background/foreground events **corroborate** (they may close an interval earlier) but are
never required and never solely relied upon.

## Why
The data dictionary states these events "are not guaranteed and sometimes depend on the system." The
provided file confirms it: **14,700 `AppBackgrounded` vs 14,321 `AppForegrounded`** — 379 unmatched —
and **418 sessions background and never return**. A pairing model is therefore wrong on roughly 4% of
sessions here, and wrong by an unknown and different amount on the unseen day. The heartbeat, by
contrast, has a defined cadence and is 93% of all events.

## Consequences
- We must choose a gap threshold; too tight fragments intervals, too loose credits inactivity.
  Default 150s ≈ 2.5 missed beats. This is a tunable in `sql/10_intervals.sql` and a defensible
  trade-off to state out loud.
- The final heartbeat of an interval gets one cadence of credit, not the full gap.
- We can still *report* background-derived exclusion as a cross-check, which doubles as evidence that
  the two signals agree where both exist.
