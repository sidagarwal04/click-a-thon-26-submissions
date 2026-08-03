# DYNAMIC_PARAMS — every constant fitted to *this file*, and what breaks if the data differs

> **Summary:** 21 constants in `sql/` and `tools/` were derived from the provided 905,558-row file
> rather than defined by the problem. The two that move the answer are `GAP_S = 150` and
> `TAIL_S = 60` — and the measured sensitivity **inverts the prior**: `GAP_S` sits on a flat region
> (±20% → 0.34% of peak) while `TAIL_S` is a straight ramp (±20% → 1.97%), making it **7.2× more
> elastic** at the shipped value. The deeper structural finding is that both constants are duplicated across **six sites
> including the reconcile gate, the reference interpreter and both data generators**, so *every
> verification instrument we own shares the fitted value and is blind to a mis-fit*. Evidence:
> [evidence/params/](../evidence/params/). Recommendation: [ADR 0028](adr/0028-fitted-parameters-are-declared-inputs-not-derived-per-run.md).

**Status, 2026-08-02: the de-duplication in §5 has been APPLIED; no value has changed.**
[ADR 0032](adr/0032-one-versioned-policy-declaration-read-by-every-consumer.md) collapsed the six
sites of §4 into one declaration (`policy/model.policy` → the generated view `v_model_policy`), read
by the model, the gate, the reference interpreter, both generators and the publisher. Before/after
builds are byte-identical — peak 2,917, 30,323 intervals, all four tiers hash-equal
([evidence/policy/](../evidence/policy/README.md)). Everything else below — the values themselves,
the `TAIL_S` re-derivation (§A2), the adaptive lease (C3) — is still an inventory and a design, not
an applied change. All measurement ran read-only against `default.ev_raw` locally or in scratch db
`params_v2`; the graded `sonyliv` database was never written to.

---

## 0 · The distinction being drawn

A constant is **defined by the problem** if the problem statement or the output grain fixes it — the
60 seconds in "concurrency per minute" is not a tunable, it is the unit of the answer. A constant is
**fitted** if we chose its value by measuring the provided file. Fitted constants are hidden
dependencies on that file, and the unseen day is drawn from the same universe but not guaranteed the
same distribution.

The inventory below separates them, and for every fitted one states **what breaks, in which
direction**, concretely enough to act on.

---

## 1 · Tier A — constants that change the answer

### A1 · `GAP_S = 150` — the heartbeat-gap threshold

`sql/30_build_intervals.sql:79` · duplicated at `sql/90_reconcile.sql:39`,
`tools/reference_interpreter.py:72`, `tools/cruel-gen.sh:64`, `tools/scale-load.sql:192`

**Fitted from:** this file's inter-arrival p99, documented in-file as "49 s" and "~3× p99" (ADR 0007).

**What breaks.** The threshold buys a fixed number of *missed beats of grace*, and that number is
`GAP_S ÷ cadence` — so it silently changes whenever cadence does. At this file's 40 s beat, 150 s
grants 3.75 missed beats. **An emitter on a 40 s cadence keeps 3.75 beats of grace; one on a 75 s
cadence gets only 2.0.** Concretely:

- **Slower cadence than fitted** (say a 90 s beat on a low-power TV profile): 150 s is 1.7 beats, so a
  single dropped heartbeat splits a run that never stopped. Runs fragment, each fragment mints
  another `TAIL_S` credit (§A2), and **the count is inflated** — the direction is *over*-counting,
  which is the direction we deliberately avoid everywhere else.
- **Faster cadence than fitted** (a 10 s beat): 150 s is 15 beats of grace, so a genuine
  backgrounding of up to 2.5 minutes is booked as continuous watching. **Under-exclusion of
  backgrounded time; the count is inflated again**, for the opposite reason.

**Measured sensitivity: low.** ±20% around 150 moves the peak by 10 viewers (0.34%); elasticity
0.0069. The curve only steepens below ~90 s. **This constant is defensible where it sits** — see
[evidence/params/README.md §1](../evidence/params/README.md).

**But the documented rationale does not survive re-measurement.** Re-running ADR 0007's own quantity
today gives **p99 = 45 s** (not 49), and that number is only well-defined because of an unstated
choice: **55.75% of adjacent event pairs share a truncated second**, and whether those count as
arrivals swings p99 from 45 s to **155 s**. Under the second reading 150 s is *below* p99, not 3×
above it. The constant is fine; the sentence justifying it is not.

### A2 · `TAIL_S = 60` — grace credited after a run's last event

`sql/30_build_intervals.sql:82` · duplicated at `sql/90_reconcile.sql:40`,
`tools/reference_interpreter.py:73`, `tools/cruel-gen.sh:64` · **re-encoded implicitly** as `+241`
and `INTERVAL 300 SECOND` in `tools/publish.sh:712,715`

**Fitted from:** "one nominal cadence" — a 60 s beat the data then disproved (the measured beat is
40 s, p95 on *every* platform).

**What breaks.** This is a direct multiplier on the answer, not a threshold. **Exactly 8,978 of
30,323 intervals (29.6%) end at a run end and receive the credit**, so the model books
`8,978 × TAIL_S` seconds of watch time whose only evidence is that a beat was expected. If the unseen
day's cadence is faster, 60 s over-credits every one of those intervals; if slower, it under-credits.
The error does not average out — it is one-signed and applies to nearly a third of all intervals.

**Measured sensitivity: high, and linear with no flat region.** +2.41 viewers per tail-second and
+2.495 h per tail-second, constant across the whole 0–120 s range. ±20 s (one third of the value)
moves the peak by ~48 viewers, 1.65%. **Elasticity 0.0494 — 7.2× `GAP_S`.**

**Nobody has been defending the riskier constant.** The brief asks about `GAP_S`; the measurement
says `TAIL_S` is where the exposure is. T8 already found that over half the explicit-background delta
is this tail, and [doubts/07](../doubts/07-tail-credit-at-explicit-stops.md) attacks *where* it is
applied — but its *size* has been justified by a cadence figure the file contradicts.

**Latent cross-file break.** `tools/publish.sh:712` computes touched minutes as `hi + 241` seconds,
i.e. it assumes interval coverage ends within 4 minutes of the last event. That is a `TAIL_S`
assumption written as a different number in a different language. **Raising `TAIL_S` above 240 s
silently under-covers the publisher's minute window** — buckets go stale with no error. The
`INTERVAL 300 SECOND` prefilter on the same line carries the same assumption with yet a third value.

### A3 · `UNCLOSED_PAUSE_TO_RUN_END = 1` — the conservative fork

`sql/30_build_intervals.sql:92`

**Fitted from:** the measurement that 23% of pauses never resume — the *value* is a judgement call,
but the fact that the question exists at all is a property of this file.

**What breaks.** If the unseen day's client reliably emits `resume`, the constant is inert. If it is
*worse* at closing pauses, the conservative rule eats proportionally more run time and **the count
deflates**. Measured fork on this file: conservative 1,978.1 h / peak 2,917 vs permissive 2,070.0 h /
peak 3,036 (+4.1%). Recorded as mentor Q2 / ADR 0007; not re-litigated here.

### A4 · The pause/resume vocabulary — `event = 'pause'` / `'resume'` matched exactly

`sql/30_build_intervals.sql:129-130`

**Fitted from:** the 47 event-name pairs observed in this file.

**What breaks.** A new pause-like verb on the unseen day (`AdPause`, `speed-pause` and 830 others
already exist and are *not* matched) is invisible to the model, so paused time is booked as watching
— **inflation, silently**. Measured immaterial here (+0.03% if the known variants are included), but
that is a statement about this file's vocabulary mix, not about the next one. The
source-contract gate (ADR 0026) is the only instrument that can see a new verb;
`evidence/liveness/vocabulary.tsv` is the committed baseline.

### A5 · Whole-second timestamp truncation

`sql/30_build_intervals.sql:97` (`toUnixTimestamp`)

**Fitted from:** the observation that 23.67% of adjacent pairs already share a millisecond, making
sub-second ordering mostly moot — and forced into a correctness fix (`>=` resume lookup, ADR 0009).

**What breaks.** A source with finer effective resolution, or a different duplicate-timestamp rate,
changes how many pause/resume pairs collapse into one second. Measured: millisecond-precise
processing moves the peak −1.8% ([doubts/08](../doubts/08-second-truncation-inverts-pause-resume.md)).

---

## 2 · Tier B — physical/schema constants (change cost, not the answer)

These are fitted to this file's *cardinalities*. A wrong value costs latency and bytes, never
correctness — which is why they are a lower tier, but at 100× the cost is the deliverable.

| # | constant | site | fitted from | what breaks if the data differs |
|---|---|---|---|---|
| B1 | `ORDER BY (toStartOfHour(ts), platform, video_session_id, ts)` | `sql/00_schema.sql:45` | 99 hours · **10** platforms · 10,866 sessions · 9,147 rows/hour | Leads with two low-cardinality keys per `schema-pk-cardinality-order`. If platform cardinality rises (device-model granularity, or the ADR 0024 `extra` map promoting a new dimension), the second key stops being a cheap prefix and granule pruning degrades. ADR 0002 measured the alternative at **17.3× worse**; the win is a property of the 10-value platform vocabulary. |
| B2 | `PARTITION BY toYYYYMMDD(event_timestamp)` | `sql/00_schema.sql:44` | a 12-day span, ~75k rows/day | Correct for daily grading. A single-day unseen file makes it one partition (no pruning benefit, harmless); a high-volume day makes daily parts large. At 100× audience in the same window, parts grow 100× with no extra pruning — partitioning by hour would prune better but multiplies part count. |
| B3 | `INDEX idx_content content_id TYPE bloom_filter(0.01)` | `sql/00_schema.sql:40` | **3,357** distinct content_ids in events | False-positive rate tuned for ~3k values. A catalogue-wide day (33,464 ids in play, 10× more) raises FP cost; the index still works, it just prunes less. |
| B4 | `index_granularity = 8192` | `sql/00_schema.sql:46` | ClickHouse default — **not fitted**, listed to close the question | — |
| B5 | `min_bytes_for_wide_part = 0` | `sql/00_schema.sql:49` | forced Wide so per-column compression stats are readable on a small load | An evidence-harness affordance, not a production setting. At real scale Wide is the default anyway; on a tiny unseen file it costs part overhead. |
| B6 | `non_replicated_deduplication_window = 1000` | `sql/00_schema.sql:56` | — | Already documented as **measured false** on Cloud/SharedMergeTree (bug 8). The real replay guard is `tools/load.sh` refusing a non-empty table. Kept because it is real locally and free. |
| B7 | `dict_content` `LAYOUT(COMPLEX_KEY_HASHED)` + `LIFETIME(MIN 300 MAX 600)` | `sql/80_content.sql:134-135` | **33,464** catalogue rows, of which only **3,357** appear in events | Hashed layout assumes the catalogue fits comfortably in memory. A catalogue two orders larger would want `SPARSE_HASHED` or a range/direct layout. The 300–600 s jittered reload is a freshness/thundering-herd tradeoff, fitted to "small and static" — a catalogue that changes mid-day would need it shorter. **0 orphan events measured**, so the `(unknown)` default is currently untested in anger. |
| B8 | window frames `240 / 840 / 3540 PRECEDING` | `sql/85_windows.sql:303-305` | 5/15/60-minute windows at 60 s grain | **Defined by the problem**, not fitted — they are `(N×60)−60` seconds because `RANGE` is inclusive of the current row. Listed so they are not mistaken for fitted values. |

---

## 3 · Tier C — operational constants (change safety and freshness)

| # | constant | site | fitted from | what breaks if the data differs |
|---|---|---|---|---|
| C1 | `PUBLISH_SETTLE_S = 5` | `tools/publish.sh:80` | insert-commit visibility timing on **this service** | Load-bearing: the design assumes no insert takes longer than 5 s from `now64(3)` to full row visibility. A slower or more contended service violates it, and an insert that outlives the window surfaces behind the committed cursor. The ADR 0019 `LOOKBACK_S` bounds the damage; beyond the lookback the work is **lost silently**. It is also the floor on publish lag, so it trades freshness directly. |
| C2 | `PUBLISH_LOOKBACK_S = 900` | `tools/publish.sh:81` | chosen as a wide multiple of C1 | Too small → late markings never re-scanned (silent loss). Too large → every run re-scans more of the change log. Exactness comes from `cc_publish_consumed`, so a large lookback is *safe but slow*; a small one is *fast but lossy*. Asymmetric — err large. |
| C3 | `PUBLISH_LEASE_TTL_S = 60`, `LEASE_SETTLE_S = 2` | `tools/publish.sh:88-89` | longest single phase **measured ≤ 2 s at this scale** | The TTL must exceed the longest phase because a holder only renews *between* phases. At 100× a phase takes proportionally longer; **if any phase exceeds 60 s the lease expires under a live publisher and a second one can acquire** — the exact concurrency failure the lease exists to prevent. This is the operational constant most exposed to scale. |
| C4 | 7-day TTLs on `session_dirty` / `cc_publish_batch` / `cc_publish_consumed` | `sql/12_publish.sql:111,159,203`; `604800` at `:382` | queue-retention reasoning | Doubles as a **correctness bound** (Q11): work that outlives the TTL expires silently and the tiers are wrong with no signal. `retention_alert` trips a day early. A backlog longer than 6 days on a busier stream would hit it. |
| C5 | lease liveness `INTERVAL 60 SECOND` in the view | `sql/12_publish.sql:400` | mirrors C3's default | Informational only, but it is a **third copy** of C3's value that no test binds together. |
| C6 | publisher touched-minute window `+241` and `INTERVAL 300 SECOND` | `tools/publish.sh:712,715` | `TAIL_S = 60` plus slack | See §A2 — a `TAIL_S` dependency written as two different numbers in a third file. |
| C7 | timestamp sanity window `[2020-01-01, 2035-01-01)` | `sql/15_normalise.sql:391` | a 12-day 2026 file; ADR 0025 | Deliberately wide. Breaks only if real events legitimately fall outside — e.g. an archive replay of pre-2020 content. Direction: legitimate rows quarantined, visible in the quarantine summary rather than silent. |
| C8 | version-normalisation rules (`norm_version`, `norm_app_version`) | `sql/15_normalise.sql:208-213` | the version-string shapes present in this file | Trailing-zero stripping and case folding are fitted to observed formats. A new format normalises to itself, so filtered queries split across two spellings — **silent under-count on filtered queries only**, never on the headline. |

---

## 4 · Tier D — the fixtures are fitted too, and that is a circularity

This is the finding I did not expect to make.

| # | site | what is fitted |
|---|---|---|
| D1 | `tools/scale-load.sql:44-75` | **12 constants** fitted to the provided file (`BURST_MEAN 3.4`, `SESS_MEDIAN 53.0`, `P_PAUSE 0.102`, `P_PAUSE_UNCLOSED 0.23`, …) — and at `:192` it **hardcodes the 150 s gap** when synthesising long silences |
| D2 | `tools/cruel-gen.sh:64` | `GAP_S, TAIL_S = 150, 60` |
| D3 | `tools/reference_interpreter.py:72-73` | `GAP_S = 150`, `TAIL_S = 60` |

**The scale evidence cannot detect a `GAP_S` mismatch**, because the generator produces gap structure
*defined by the same 150 s threshold the model tests against*. Likewise the property suite's
reference interpreter (D3) is an independent *implementation* but not an independent *parameter*
choice.

Combined with the gate (`sql/90_reconcile.sql:39-40`) carrying the same two literals, the tally is:

> `GAP_S` and `TAIL_S` are written in **six places** across three languages, in **three different
> encodings** (`150`/`60`, `+241`, `INTERVAL 300 SECOND`) — and the model, the gate, the reference
> interpreter and both data generators all share the fitted value.
>
> **Every instrument we own for detecting a wrong answer is calibrated with the number under
> suspicion.** A mis-fitted `GAP_S` goes green on the reconcile gate, green on the property suite,
> and green on the scale test, simultaneously and by construction.

**CLOSED as of ADR 0032 — but read what was and was not closed.** The six sites are now one
declaration, so the three encodings are gone and the covers are asserted `>= TAIL_S + 60` instead of
drifting. The *sharing* is not gone and cannot be: every instrument still uses one value. What
changed is that it is one **named, versioned** value rather than six numbers that happened to agree,
so the circularity is a fact you can read off `policy/model.policy` instead of a discovery you make
by grepping. Detecting a mis-fit still needs the sweep in [evidence/params/](../evidence/params/) and
the mentor answers in [doubts/](../doubts/), not the refactor.

That — not the value 150 itself — is the real hidden dependency on this file. It is the same class of
blindness `evidence/adversarial/` was built to attack, applied to parameters rather than conventions.

---

## 5 · What I recommend, in one paragraph

Full reasoning and costs in
[ADR 0028](adr/0028-fitted-parameters-are-declared-inputs-not-derived-per-run.md). Summary:
**keep the constants fixed, but promote them from buried literals to one declared, measured,
overridable input with the sensitivity published** — because (a) deriving per-run makes two runs
incomparable, which is disqualifying when a judge compares our unseen-day answer to our benchmark
answer; (b) the derivation rule is *measurably less stable than the constant*, swinging 3.4× on a
definitional choice and 11% on estimator choice; (c) per-segment adaptation was built and moves the
headline by **2 viewers (−0.07%)** while forcing the gate to carry the same segmentation; and (d)
derivation cannot be fused into the build — `arraySplit` needs the parameter that the distribution
has not yet produced — so it costs a **second full pass**, ~6.5 GiB of reads at 100×, which the
brief's own efficiency requirement rules out. The single highest-value change is not adaptivity at
all: it is **de-duplicating the six sites into one declaration** so the gate stops sharing the
model's assumption, and **re-deriving `TAIL_S` from the measured 40 s beat** rather than the 60 s one
the data disproved.

---

## Provenance

Measured 2026-08-02 · local ClickHouse 26.7.1.1315 · `default.ev_raw` 905,558 rows · scratch db
`params_v2` · harness reused from [evidence/adversarial/README.md](../evidence/adversarial/README.md).
Full sweep, reproduction commands and query-log cost evidence:
[evidence/params/README.md](../evidence/params/README.md) · [sweep.tsv](../evidence/params/sweep.tsv).
