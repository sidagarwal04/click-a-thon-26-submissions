# `search_typed`

**Kind:** supporting (engagement/discovery) · **Grain:** one row per search query typed
**Rows:** 599,630 · **Span:** 2025-12-31 → 2026-06-30 · **Distinct users:** 599,630 (1:1)

## What it captures
Destination search box usage — search term, result count, and where the search
originated (`source`).

## Data quality
- `application_id` empty 84.6% of the time (same "not always empty" pattern as
  `destination_card_clicked` — 15.4% of searches happen mid-application, e.g. adding
  a second destination).
- `results_count = 0` only 2.5% of the time — search rarely dead-ends, not a big
  "no results" problem in this data.

## Key distributions
| field | breakdown |
|---|---|
| `source` | home_search 49.9%, search_bar 40.0%, suggestion 10.0% |
| `search_term` (top) | evenly spread across ~10 popular destinations (schengen, usa visa, thailand visa, egypt, uk visa, singapore, vietnam, dubai, japan, bali — each ~10% of volume) |

## Notes for instrumentation / analytics design
- Second-highest-volume table after `destination_card_clicked` — a real intent signal,
  but base_context labels it "noisy discovery signal" and de-prioritizes it. The
  search-term list is actually clean and low-cardinality in practice (dominated by ~10
  terms), so it may be more useful for segment/demand analysis than the base context
  implies — worth the Context Agent revisiting that "treat as noise" framing.
- `search_term` looks free-text in schema (`Nullable(String)`) but behaves like a closed
  vocabulary in this sample — confirm whether that's real (curated autocomplete) or a
  synthetic-data artifact before designing a schema around low cardinality.
