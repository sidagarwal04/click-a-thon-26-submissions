# Agent query set — deterministic, dumb runner

The runner is intentionally stupid: it fills placeholders, fires queries in a fixed
order, and compares returned numbers to fixed thresholds. Zero SQL is generated at
runtime; zero decisions are made by the LLM.

## Why these queries exist

Detection decides that **something** is wrong and **when**. The agent answers **what**
and **who**, by asking four fixed questions — always the same, always in this order.

| # | question | query |
|---|---|---|
| 1 | Which past days were incidents? Don't use those as "normal." | q6 |
| 2 | **What** moved — traffic, fill rate, render rate, or price? | q1 |
| 3 | **Who** moved it — which segment explains the drop? | q2 |
| 4 | Were the other suspicious segments real, or just shadows? | q3 |

Then the LLM writes one paragraph, using only numbers the queries returned.

Why each earns its place:

- **q6** — comparing next Sunday to anomalous Jun 21 reads +86%: a false alarm. Poisoned
  days must never define "normal."
- **q1** — knowing *which* lever moved tells you the problem type and which dimensions
  are even worth looking at. Everything after is targeted, not a fishing trip.
- **q2** — rank by *share of the damage* (size × change), not by biggest drop: a tiny
  segment can crash hard and still explain nothing.
- **q3** — the difference between naming one right cause and naming four causes, three
  wrong. Its before/after numbers are the "checked and ruled out" lines in the report.

**Worked example (Jun 23–25).** q1: fill rate −3.4 pp, other three levers flat → a fill
problem. q2: slice fill by OS, region, device, format → Android 15 fell 0.785 → 0.433,
explaining **98% of the whole drop**. q3: EU and Galaxy S23 also looked bad, but removing
Android 15 traffic collapses both to ~0 — they merely *contain* Android 15 phones, so
they are shadows, ruled out. Report: *"Revenue fell because fill rate dropped for
Android 15 (0.433 vs 0.785, 98% of the drop). EU and Galaxy S23 were checked and ruled
out as side effects."*

Two special cases have their own queries. **No history** (the unseen incident): q1–q3
compare against past weeks a fresh slice may not have, so **q4** compares each segment to
its siblings *right now* — Android 15 at 0.43 next to seven other OS versions at ~0.78 is
unmissable; run it twice, once to find the outlier and once with it removed to clear
shadows. **Everyone dropped equally**: before calling it global, **q5** checks whether
nobody's rate changed and traffic merely shifted toward naturally-weaker segments (more
tier-3 → global average falls); if so, the story is whose *share* moved. (Jun 21: all
regions −43…−44% uniformly → genuinely global.)

Three standing rules: the agent never closes a case on its own (q1 finding nothing where
detection flagged something is a DISAGREEMENT → log both sides, flag a human); every real
signal gets its own case (a second lever over its own threshold is its own incident); and
the LLM only narrates, appearing once at the end, with every number it writes checked
against the query results before the report is accepted.

## Placeholder convention

| kind | example | filled by |
|---|---|---|
| `{x:Type}` | `{inc_dates:Array(Date)}` | ClickHouse bound params (`--param_x` / driver params) |
| `__TOKEN__` | `__DIM__`, `__METRIC_NUM__` | runner string-substitution **from the whitelist below only** |

## Fragment whitelist

**Metrics** (ratio form `sum(num)/sum(den)`):

| lever | `__METRIC_NUM__` | `__METRIC_DEN__` | scale |
|---|---|---|---|
| fill_rate | `is_filled` | `1` | 1 |
| render_rate | `is_impression` | `is_filled` | 1 |
| ctr | `is_click` | `is_impression` | 1 |
| ecpm | `revenue` | `is_impression` | 1000 |

Weights in q2a/q5 are den-shares automatically — the `__METRIC_DEN__` substitution *is*
the "weight by the metric's own denominator" rule.

**Volume expressions** (q2b): `__VOLUME_EXPR__` ∈ `1` (requests) | `is_filled` (fills)
| `is_impression` (impressions).

**Dimensions** (`__DIM__`): `ad_format`, `category`, `publisher_tier`, `vertical`,
`campaign_type`, `region`, `country`, `device_model`, `os_version`, `app_id`,
`advertiser_id`.

**Segment filter** (`__SEG_FILTER__`): `1` normally; `is_filled = 1` whenever
`__DIM__` ∈ {vertical, campaign_type, advertiser_id} (advertiser attrs only exist on
filled rows).

**Scope filter** (`__SCOPE_FILTER__`): `1` for global incidents; for a segment-scoped
incident row (`scope = "country=ID"`), the equality from the scope — `country = 'ID'`.
Applied to every enriched query (q1–q5). Without it, a correct segment alert dies of
dilution at global grain: ID is 7% of traffic, so a −20 pp ID fill collapse reads −1.4 pp
globally — under q1's 2 pp threshold → wrongful dismissal. Rollup variants can't
scope-filter across dimensions (single-dim table) → scoped incidents use enriched variants.

**Special case — fill-rate lever × advertiser dims**: fill rate *by vertical* is
undefined (unfilled rows have no vertical). Use **q2b with `__VOLUME_EXPR__ = is_filled`**
instead: the vertical whose fills collapsed is the advertiser who pulled out.

## Which table each query reads

| query | table | why |
|---|---|---|
| q1 decompose | enriched | needs per-day medians + log shares; runs once per incident |
| q2a sweep | **rollup** (`q2a_sweep_ratio_rollup.sql`) first pass | dimension is a bound param (long format), ~3× faster, same numbers (validated); enriched variant for `app_id` at higher volume floors or when a `dataset` filter is required |
| q2b volume | enriched | per-day per-segment medians |
| q3 confound | **enriched only** | cross-dimension exclusion — rollup is single-dim by construction |
| q4 peer | enriched (rollup pattern works if hot) | runs once per incident |
| q5 mix | enriched | needs exact den-share weights per window |

Rollup caveats: no `dataset` column (deliberate — unseen continues the same universe);
advertiser dims carry a `'(none)'` bucket = the `__SEG_FILTER__` counterpart, excluded in
the rollup sweep; SummingMergeTree → always `sum()` on read, never trust a raw row.

## Fixed flow

Every incident — sweep or live — arrives as a classifier-passed `incidents` row with a
bucket-merged window (live alerts trigger a targeted sweep; ARCHITECTURE contract). The
agent computes no boundaries and issues no seasonality verdicts:

```
q6_excluded_dates                  → excluded_dates param for q1
q1_decompose  (scoped from the row)→ which lever + magnitudes for the narrative
                                     (returns base_days_used → pass to q2/q3/q5 verbatim)
   ├─ no lever moved               → DISAGREEMENT flag: log both sides' numbers,
   │                                 human eyes — never a silent verdict
   ├─ min_clean_days < 2           → SHORT-HISTORY PATH (below)
   └─ lever moved                  → BASELINE PATH (below)

BASELINE PATH
q2a/q2b sweep (per dim of lever, parallel)
   ├─ candidate (≥50% contribution or 3× runner-up)
   │    q3_confound (per dim that showed signal in q2, parallel; flat dims are
   │                 already ruled out by their q2 numbers)
   │       ├─ all residuals < noise → CAUSE_CONFIRMED + ruled-out list → narrate
   │       └─ residual shrinks but persists → interaction: drill cross of top-2
   │                                          candidates (q2a with combined filter)
   └─ all deltas ≈ 0 (or Σcontribution + mix ≠ global: additivity broken)
        q5_mix (per swept dim)
           ├─ |mix| dominant   → MIX_SHIFT: q2b volume sweep finds whose share
           │                     changed → that segment is the story → narrate
           ├─ |interaction| big → segment shifted share AND changed rate:
           │                     name it on both counts → narrate
           └─ all ≈ 0          → GLOBAL_MOVEMENT, no segment named → narrate

SHORT-HISTORY PATH  (no base_dates exist → q2/q3/q5 are all impossible:
                     each needs a baseline window. q4 does both jobs instead)
q4_peer (per dim of lever, parallel)     → outlier vs sibling median
   ├─ outlier found → q4 again on OTHER dims with outlier excluded
   │                  (__SCOPE_FILTER__ = "os_version != 'Android 15'")
   │                  → shadows collapse to peer-normal = ruled out → narrate
   └─ no outlier    → cannot distinguish global from normal without a baseline:
                      the global-level verdict rests on detection's models →
                      narrate detection's numbers, agent adds per-segment evidence
narrate → LLM gets the bundle, writes prose
```

Baseline path: q6 + q1 serial, q2 ×dims parallel, q3 ×signal-dims parallel ≈ 10 queries,
3 round-trips. Short-history path: q6 + q1 + q4 ×dims + q4-exclusion ×dims ≈ same.

Runner policy (dismissal protocol, latency budget) lives in `../../agent_requirements.md`;
the detection ⇄ agent contract in `../../ARCHITECTURE.md`. This file is mechanics only.

## Thresholds (fixed, from measured noise — freeze at checkpoint B)

| check | threshold |
|---|---|
| q1 requests_pct | ±10 % |
| q1 fill/render delta | ±2 pp |
| q1 ecpm_delta | ±0.05 (~2 %) |
| q1 log shares valid | `shares_valid = 1` AND `abs(revenue_log_delta) ≥ 0.01` |
| q1 min_clean_days_per_dow | ≥ 2 else q4-only path |
| q2 candidate | \|contribution\| ≥ 50 % of global move OR \|delta\| > 3× next |
| q3 ruled out | max \|delta_excl\| < 0.5 pp (fill) / metric-scaled |
| q4 anomalous | \|vs_peer\| > 5 pp (fill) / metric-scaled |
| q5 verdict | dominant of \|within\| vs \|mix\|; identity residual < 0.001 pp |

Every query returns in <1 s on 9M rows locally (validated; see `VALIDATED.md`).
