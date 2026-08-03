# `application_started`

**Kind:** funnel, step 2 · **Grain:** one row per application (application created here)
**Rows:** 154,413 · **Span:** 2026-01-01 → 2026-07-01 · **Distinct users:** 154,413 (1:1)

## What it captures
The moment `application_id` is minted. Carries the applicant's stated purpose,
co-traveller count, destination, and the ETA shown to the user.

## Data quality
- `application_id` populated 100% (as expected — this is where it's created).
- `os` NULL 5.8% (android-only nulls, consistent with card-click table).
- **`eta_shown` is a `Nullable(String)` bucket** (`"3-5 days"`, `"5-7 days"`, `"7-10 days"`,
  `"24 hours"`) — **not** the integer `visa_issuance_eta_days` that `base_context.md`
  describes. If "on-time delivery rate" is ever implemented against this table, the
  formula as documented doesn't type-check against the real column.

## Key distributions
| field | breakdown |
|---|---|
| `purpose` | tourism 84.9%, business 10.1%, transit 3.0%, medical 2.0% |
| `co_travelers` | 0 → 55.1%, 1 → 23.8%, 2 → 12.2%, 3 → 6.0%, 4 → 2.9% |
| `eta_shown` | 3-5 days 39.9%, 5-7 days 30.0%, 7-10 days 20.0%, 24 hours 10.1% |
| `flow` | standard 90.0%, express 10.0% |
| `device_type` | ios 41.1%, android 32.1%, web-user-b2c 19.8%, Desktop 6.9% |
| `destination` (top) | AE 16.4%, US 9.8%, ID 8.8%, TH 6.4%, VN 5.3% (mirrors card-click mix — no destination-level drop-off skew yet) |

## Notes for instrumentation / analytics design
- This is the **funnel conversion denominator** per `base_context.md`'s own metric
  definition ("conversion = purchases ÷ application_started"), so its quality matters
  more than its raw volume suggests — it's the number every downstream rate is divided by.
- `co_travelers` here is the *stated* count at application start; the "Group / Family"
  spec's `group_size` is a related-but-different concept (a group can be started without
  necessarily setting `co_travelers` the same way) — worth reconciling when the Group
  feature is instrumented, not assuming they're the same field twice.
- `eta_shown` as a bucketed string is fine for display but useless for numeric SLA
  math (e.g. "did we deliver faster than promised") — flag to the Context Agent as a
  metric-definition gap, not just rename it in context.
