---
type: contradiction
title: duplicate_id / is_back_filled markers ignored by metric formulas
description: Envelope contains dedup and backfill markers but no metric definition mentions handling them.
severity: medium
status: open
timestamp: 2026-08-02
tags: [contradiction, data-quality, metrics]
---

# Claim A

The standard envelope (shared by all event tables including `destination_card_clicked`) includes:
- `duplicate_id` (nullable string) — deduplication marker
- `is_back_filled` (uint8) — 1 = event was backfilled after the fact

These imply a dedup/backfill pipeline that can produce duplicate or retroactively-inserted rows.

# Claim B

All metric definitions (`conversion-rate`, `drop-off-rate`, `step-through-rate`, `click-to-application-rate`, etc.) count distinct `user_id` or raw event counts **without filtering or deduplicating** on these markers.

# Why it matters

If `duplicate_id` is non-null, the row may be a known duplicate. If `is_back_filled = 1`, the event timestamp may not reflect real user action time. Ignoring these could inflate counts or skew time-based funnels.

# Recommended resolution

- Clarify the semantics: does `duplicate_id IS NOT NULL` mean "this row IS a duplicate" (exclude it) or "this row HAS a duplicate elsewhere" (keep one)?
- Decide whether `is_back_filled = 1` events should be included in funnel metrics or flagged separately.
- Update metric formulas to explicitly state their dedup/backfill handling (even if the decision is "include all").
- The Analytics Agent should note which choice it makes and why.

# Source

`specs/08_destination_card_clicked/spec.md` — envelope fields. `base_context.md` §4 — metric formulas (no mention of dedup/backfill).

# Affects

- [destination_card_clicked](/tables/destination_card_clicked.md)
- [conversion-rate](/metrics/conversion-rate.md)
- [drop-off-rate](/metrics/drop-off-rate.md)
- [click-to-application-rate](/metrics/click-to-application-rate.md)
