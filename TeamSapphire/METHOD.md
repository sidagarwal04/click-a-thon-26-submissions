# The method, with worked numbers

Four pieces of arithmetic, each with the real numbers it produced on our data.
No LLM is involved in any of it — the language model only reads the output of
these steps and writes prose.

---

## 1. Baseline — what *should* this hour look like?

**Problem.** Traffic has a daily rhythm (hour 0 ≈ 256K requests, hour 12 ≈ 465K)
and a weekly one (weekdays ≈ 1.38M, weekends ≈ 1.05–1.12M). Compare any hour to
a flat average and every weekend night is an emergency.

**Fix.** Compare like with like: the same weekday *and* the same hour-of-day from
the trailing 4 weeks. Sunday 14:00 is judged against previous Sundays at 14:00.

**Centre = median, not mean.** With only ~4 comparable hours, one contaminated
week drags a mean badly. The median ignores it.

**Does the median break the sum/sum rule?** Asked and measured, because it looks
like it might. The glossary requires ratio metrics to be computed as sum/sum
over a group, never as an average of per-row ratios — and we obey that
everywhere a metric is *computed*: each hour's fill rate is summed fills over
summed requests, and each segment's is too (`localize.py` refuses to sum segment
ratios). The baseline is a different object: a central-tendency estimate over a
reference class of comparable hours, not a metric computed for a group.

Still, "different question" is an argument, not evidence. Comparing both methods
across all 600 training hours:

| | |
|---|---|
| Median difference (median-of-ratios vs ratio-of-sums) | 0.0010 — 0.13% of the metric |
| Worst case across 600 hours | 0.0131 — 1.67% |
| Materiality gate a movement must clear | 8% |

The two never diverge enough to change a verdict. Ratio-of-sums would also be
the worse choice here: it weights by volume, letting the busiest comparable hour
dominate the estimate of "typical".

```
baseline(h) = median{ metric(h − 1wk), metric(h − 2wk), … }
```

Worked: Sundays had 220,775 / 225,383 / **126,052** / 233,943 requests.
The median of the clean Sundays is ~225K, so 126,052 reads as −44%. Had we used a
flat all-days average (~257K/day), *every* Sunday would have looked ~13% low and
the real one would have been just another weekend.

---

## 2. Is the gap real? — spread and the z-score

```
z = (actual − baseline) / spread
```

Everything hinges on `spread` — "how much does this metric wobble when nothing
is wrong?" Get it too small and ordinary noise scores as catastrophe.

**The bug this fixed.** Originally `spread = max(stddev, 2% of baseline)`. For CTR
that floor is far too tight, and the detector flagged **102 of 600 hours** —
noise, on nearly every day.

Why: CTR is a *proportion* of a rare event. Clicks are 0.83% of requests, so with
p ≈ 0.0109 and n ≈ 8,200 impressions in an hour, counting noise alone gives

```
SE = √( p(1−p) / n ) = √( 0.0109 × 0.9891 / 8200 ) ≈ 0.00115
```

which is **10.5% of CTR itself**. So a 21% CTR swing is about 2σ — unremarkable.
The 2% floor scored that same swing past 10σ.

**Fix.** For a proportion, floor the spread at the binomial standard error, which
scales correctly with the denominator:

```
spread = max( stddev , √( p(1−p)/n ) )        # proportions: fill_rate, ctr
spread = max( stddev , 2% × baseline )        # sums: revenue, requests, ecpm
```

CTR flags fell **102 → 4**. Nothing else changed.

**Two gates.** An hour is flagged only when it is *both* statistically unusual
(|z| ≥ 3) *and* materially large (|Δ%| ≥ 8%). In 9M rows, trivial deviations reach
significance constantly.

**Incidents, not hours.** Isolated flagged hours are noise; a sustained run is an
event. Clustering consecutive flagged hours took 14 apparent incidents down to 2
real ones.

---

## 3. Which *factor* moved? — the log decomposition

The revenue identity, in exact form (the glossary's is an approximation):

```
Revenue = Requests × FillRate × RenderRate × (eCPM / 1000)
```

Exact because it telescopes:
`Requests × (Fills/Requests) × (Impressions/Fills) × (Revenue/Impressions) = Revenue`.

**Why logs.** The identity is multiplicative, so subtracting produces cross-terms
that have to be dropped or arbitrarily allocated. Taking logs makes it additive
with no leftover:

```
log(R₁/R₀) = log(Q₁/Q₀) + log(F₁/F₀) + log(RR₁/RR₀) + log(E₁/E₀)
```

Each factor's share is its log-change divided by the total. Shares sum to exactly
100%.

Worked, 2026-06-21:

| factor | actual | baseline | change | share of move |
|---|---|---|---|---|
| requests | 126,052 | 223,079 | −43.5% | **96.0%** |
| eCPM | 2.4186 | 2.4771 | −2.4% | 4.0% |
| fill_rate | 0.7855 | 0.7849 | +0.1% | −0.1% |
| render_rate | 0.9794 | 0.9798 | −0.1% | 0.1% |

Residual **−2.2 × 10⁻¹⁶** — floating-point zero. Every cent is attributed.
Verdict: a volume incident, not a supply or pricing one.

---

## 4. Which *segment* did it? — excess over expected

**The trap.** When revenue falls 44% globally, every large segment also falls
~44%. Rank segments by size of drop and you rank them by *size*, then confidently
name the biggest one. Plausible, reproducible, wrong.

**The right question** is not "which segment fell most" but "which fell more than
its own size explains":

```
expected_delta = baseline_segment × global_pct_change
excess         = actual_delta − expected_delta
```

A segment merely carried along has excess ≈ 0. A segment that *caused* the move
has a large excess and everyone else's is small.

**Two gates again — and the second one matters.** Share-of-excess alone is a
ratio of two possibly-tiny numbers. On 2026-06-21 it named `publisher_tier=tier_1`
"responsible for 100% of the excess movement" on an excess of **315 requests out
of an incident of 97,027** — 0.3%. A fabricated finding, produced confidently on
real data. So attribution also requires the excess to be material to the incident:

```
responsible  ⟺  excess_share ≥ 50%   AND   |excess| / |total_delta| ≥ 10%
```

With that, 06-21 correctly returns **no responsible segment** and rules out all
nine dimensions — "all 3 values moved together, every one within 0.7% of the
global −43.5%; the largest outlier explains only 0.3% of the incident."

*(For ratio factors, segments don't sum, so each is weighted by its share of the
denominator before comparing — a fill-rate change in a tiny segment can't move
the global number much.)*

---

## Why this finds both incidents

| | 2026-06-21 | 2026-06-23 → 25 |
|---|---|---|
| Shape | global, uniform | localized |
| Requests | **−43.5%** | normal |
| Fill rate | normal | **0.785 → 0.433** |
| Seen by | global scan | segment scan only |
| Diagnosis | volume loss, no segment responsible | Android 15 supply failure |

The second is invisible globally: Android 15 is ~1/8 of traffic, so its −44.8%
fill-rate collapse moved the *global* fill rate only ~5% — inside the 8% gate.
That is why every (dimension, value) is scanned independently with the same
arithmetic, and why the ruled-out ledger is kept: on 06-21 the *absence* of a
responsible segment is the finding.

---

## 5. Every threshold, and what it is anchored to

Honest framing: these are **judgment calls tuned against one dataset**, not values derived from theory. Each is listed with the measurement that motivated it and how it would fail. A judge asking "why 8%?" deserves this table rather than a shrug.

| Threshold | Value | Anchored to | How it fails |
|---|---|---|---|
| Robust z | 3.0 | Conventional. Paired with a materiality gate, so it never fires alone | Too low alone — 9M rows make trivial deviations significant constantly |
| Materiality | 8% | Below this, movements on this data are indistinguishable from weekday-to-weekday drift | A real anomaly smaller than 8% globally is missed unless a segment or compound scan catches it |
| Spread floor (proportions) | binomial SE | Derived, not chosen: √(p(1−p)/n). Fixed 2% gave 102 false CTR alarms | None known — this one is principled |
| Spread floor (sums) | 2% of baseline | Prevents a degenerate stddev exploding the z | Arbitrary; a genuinely stable metric could be over-floored |
| Min run | 3 hours | Isolated flagged hours were overwhelmingly noise on this data | A real 2-hour incident is dropped unless |z| ≥ 10 |
| Event severity | 1.0 percent-hours | Measured 20× separation: real events 10.9 and 32.3, typical blips 0.15 | A short sharp event (1h at 60%) scores 0.6 and is suppressed |
| Attribution concentration | 50% of excess | A segment carrying less than half the unexplained movement is not "the" cause | Two segments each at 40% both get dropped |
| Attribution materiality | 10% of incident | **Load-bearing.** Without it, `tier_1` was named for 0.3% of an incident | Set too high, genuinely diffuse causes go unattributed |
| Parent lift (compound) | 2.0× | **Load-bearing.** Flatness rules threw away the −50.6% finding | A compound only 1.5× its parent is missed |
| Min cell requests | 300/day | At 300 requests binomial noise is ~±3%; below that, cells swing wildly | Small-but-real segments invisible |
| Uniformity | 5% of incident | Below this the dimension is positively ruled out | — |

**What we have not done:** a sensitivity analysis. We have not swept these and measured how the findings change. On the unseen incident some may be wrong, and the honest answer to "are these robust?" is *"they are anchored to measurements on this dataset, and we would sweep them given more time."*

**The two that carry the most risk** are the ones marked load-bearing — both were added *because* the system produced a confident wrong answer without them, so both are validated in one direction (they prevent a known failure) and untested in the other (they may suppress a real finding).
