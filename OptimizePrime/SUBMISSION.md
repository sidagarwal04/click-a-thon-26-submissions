# SUBMISSION — the claims, the evidence, and how to regenerate both

> **Summary:** Click-a-thon India 2026 · SonyLIV foreground-only concurrency, on ClickHouse Cloud
> with ClickStack. This file maps each judging criterion — correctness, query performance, update
> handling, design quality, the unseen day — to the claim we make, the committed evidence that
> proves it, and the command that regenerates it. The official submission contract was re-fetched
> at problem commit `c1e1c69` and submission commit `c446938` on **2026-08-02**. The portal closes
> automatically at **12:00 PM IST on 2026-08-02**. The contract requires a hosted
> demo, 2–3 minute video, self-contained team folder and live ClickStack walkthrough with committed
> wiring; repository visibility and a named Team Captain are not requirements in that contract.

## ⚠ Before submitting — official-package blockers

**Hard deadline: 12:00 PM IST, 2026-08-02.** Do not plan a final upload at the boundary; the portal
closes automatically.

The current official rules require a self-contained folder in the submission repository, not that
this development repository be public. They also contain no Team Captain rule. The actual blockers
are a hosted demo, a 2–3 minute video, a final pitch PDF, and proof of the live ClickStack integration.

Final-package checklist:

- [x] **Secret scan the full history**, not just HEAD. **Re-run 2026-08-02 against the live `.env`
      values** — this is a measurement, not a recollection:
      - `.env` was **never committed** — `git log --all -- .env` is empty. ✓
      - The Cloud **password appears in 0 commits and 0 files at HEAD**
        (`git log --all -S"$CH_PASSWORD"`, `git grep -F "$CH_PASSWORD" HEAD`). ✓
      - The Cloud **service identity appears in 4 tracked files, 40 lines** —
        `evidence/graded-inventory/09-ddl-history-sonyliv.txt` (35 lines),
        `evidence/load-guard.txt` (3), `evidence/cruel/misscol.run.txt` (1),
        `evidence/cruel/newcol.run.txt` (1). It spreads because evidence files capture real
        command output.

        **Correction:** an earlier version of this line said 3 files / 4 lines. That scan grepped
        the **fully-qualified** hostname, and the largest exposure — 35 of the 40 lines — writes the
        **service subdomain alone**, which the FQDN pattern cannot match. Grep for the subdomain,
        not the FQDN, or you will conclude the exposure is a tenth of its actual size.
      - **Control-plane org and service UUIDs** appear in `api.clickhouse.cloud` URLs in
        `evidence/alerting/clickstack-alerts.txt` and `...-BEFORE-having-fix.txt`. A hostname grep
        cannot catch these — they need their own pattern.
      - **Do not panic-grep for bare UUIDs.** That matches 14 files under `evidence/`, and almost
        all of them are `query_id=` values from the query log — which are exactly what the contract
        asks us to publish as proof the pipeline produced our numbers. Scrubbing those would delete
        the evidence. Match UUIDs **inside `api.clickhouse.cloud` URLs**, not UUIDs generally.

      **Do not reflexively scrub the hostname.** The common submission contract *requires* that we
      "identify the ClickHouse service and tables" used as the destination. A hostname is therefore
      a **deliverable here, not a leak** — scrubbing it would remove something the contract asks
      for. A hostname alone grants no access; the credential that would is verified absent.

      **The real control is rotation**, which is the next checklist item and should happen
      regardless. Re-run before publishing if anything changes: `gitleaks git .` (or
      `trufflehog git file://.`).
- [ ] Rotate the ClickHouse Cloud password and any ClickStack/HyperDX API keys **after** the event
      regardless — they were pasted into local `.env` files on several machines.
- [x] **Fresh-clone check — done 2026-08-02, and this is the first thing a judge will do.** Cloned
      `main` to a clean directory and ran it with **no `.env` present**:
      - `.env` did not travel into the clone ✓
      - `demo/run.sh --offline` — **exit 0**, all five beats complete
      - `make ci` — **exit 0**: lint `0 issues`, `go test -race` green across all five packages
        (`cmd/sonyliv`, `internal/chdb`, `internal/config`, `internal/otelemit`,
        `internal/pipelinehealth`), binary builds
- [x] **`tools/fetch_data.sh` reaches the organiser's public repos anonymously** — verified
      2026-08-02 with no credentials: docs base `HTTP 200`, LFS data base `HTTP 206` on a range
      request. The 223 MB of data is deliberately not committed, so this path is what makes the
      submission reproducible by someone who is not us.
- [ ] Put source, final `README.md`, architecture, pitch PDF and video link in one team-named folder.
- [ ] Add the hosted demo link and document which source column backs every dashboard filter.
- [ ] Include the ClickStack deployment/config wiring, redacted `.env.example`, OTel config, the
      ClickHouse service and destination tables, and dashboard/search captures.
- [ ] Walk through the real ClickStack dashboards in both the hosted demo and the 2–3 minute video;
      screenshots alone are explicitly insufficient.
- [ ] Open one PR titled `[Submission] Team Name` against the official submission repository.

## What was verified, when

Every number below was re-executed against the graded ClickHouse Cloud service (database
`sonyliv`, server 26.2.1.525) on **2026-08-01**, read-only. Serving-layer state at verification:
`ev_raw` 905,558 events · 10,866 sessions · `session_intervals` 30,323 · `cc_minute_delta` 28,073
· `cc_hour_agg` 26,254 · `cc_minute_stateless` 91,292 · `content_dim` 33,464. If any document in
this repo disagrees with `evidence/`, the evidence file is right.

---

## 1 · Correctness

**Claim.** Foreground-only means foreground-only: concurrency counts exclude backgrounded, paused
and heartbeat-missing periods. Peak **2,917** @ 2026-07-26 10:56 UTC (naive session-span says
3,708 — a 21.3% overcount). Total counted watch time **1,978.1 h** vs 2,976.9 h naive — **33.6%
of apparent watch time excluded**. The serving layer is proven equal to truth recomputed from raw
events: **17,028 of 17,028 minutes match, 0 mismatches, max diff 0** — including idle minutes,
which are compared as `0 = 0`, not skipped.

**Why the gate is believable, not self-confirming:** truth is recomputed from `ev_raw` only, by a
*different implementation* of the same spec (window functions vs `arraySplit`), so a bug in either
side surfaces as a disagreement. It has been negative-tested: inject one bad delta row → exit 1.

| Evidence | Regenerate |
|---|---|
| [`evidence/reconcile.txt`](evidence/reconcile.txt) — the gate, all three headline numbers | `TARGET=cloud tools/reconcile.sh` |
| [`evidence/tie-break-determinism.txt`](evidence/tie-break-determinism.txt) — peak-*minute* attribution is deterministic under ties ([ADR 0014](docs/adr/0014-peak-minute-ties-resolve-to-the-earliest-minute.md)) | inline commands in file |
| [`evidence/dedup.txt`](evidence/dedup.txt) — duplicate rows proven inert at total/peak grain | inline commands in file |
| [`evidence/truncation.txt`](evidence/truncation.txt) — open sessions absorbed correctly | `tools/truncation-test.sh` |
| [`evidence/reconcile-content-views.txt`](evidence/reconcile-content-views.txt) — content tier, 0 mismatches | inline commands in file |
| Independent hour-tier check: hour-cube day peak = minute-tier peak = 2,917 | `SELECT max(peak) FROM v_concurrency_hour_total WHERE toDate(hour)='2026-07-26'` |

User-level concurrency (required deliverable): peak **2,844** concurrent users vs 2,917 sessions at
the same minute — 72 users hold multiple concurrent sessions at the peak, which is why the user
tier uses `uniqExact` states rather than summing session deltas.

## 2 · Query performance

**Claim.** Benchmark-shaped queries answer in **7.0–44.5 ms server-side median** (median of 3,
query cache off), reading **≤ 814 KiB / ≤ 60,086 rows** each — from the serving tiers, never from
raw history. Judges look at what queries read: every timed run's `query_id` and
`log_comment` are committed, so each number is auditable in `system.query_log`, and each query's
`EXPLAIN indexes=1` is committed alongside.

**Stated up front:** the organiser now specifies result classes, not a fixed SQL set: peak and average
concurrency at minute, hour and day grain with dimension filters. These 13 queries are **our coverage
matrix** of the shapes the problem statement names — peak AND average at
minute/hour/day grain, with dimension filters — plus the one shape the hour tier deliberately does
NOT serve (a partial platform filter), so the documented minute-scan fallback is measured
(9.4 ms), not guessed.

| Evidence | Regenerate |
|---|---|
| [`evidence/bench.txt`](evidence/bench.txt) — the table: bytes read, rows read, server + wall ms | `tools/bench.sh` |
| [`evidence/benchmark/`](evidence/benchmark/) — 13 queries + params + answers + EXPLAINs + query_ids | same |
| Serving vs re-expansion: 299 KB / 23 ms vs 2.55 MB / 56 ms — 8.5× cheaper | [`WALKTHROUGH.md`](WALKTHROUGH.md) §4 |

## 3 · Update handling

**Claim.** Late arrivals and still-open sessions are absorbed **incrementally, without rebuild**:
an MV on `ev_raw` records which sessions each insert touched (`session_dirty`); the publisher
claims them, re-derives only those sessions, and corrects all four serving tiers by appended
diffs — negation rows for the minute deltas, superseding versions for intervals, hours and user
buckets ([ADR 0013](docs/adr/0013-continuous-publication-by-incremental-finalizer.md),
[ADR 0016](docs/adr/0016-publisher-owns-the-user-and-hour-tiers.md)). Measured in a scratch
database: **0 differing cells vs a from-scratch rebuild across all four tiers**, through
bootstrap, growth, shrink, a dimension change, a 46-minute straggler, and 200 forced
republications. Adoption over an existing database is one DDL round-trip and does **not**
re-derive history. Delta correction is window-bounded and **flat — ~0.3 s at every scale measured**; tier maintenance (hour cube + user buckets) rides along in the same run and scales with audience × window: 0.25 s at 1×, **7.3 s at 100×** on the test box ([ADR 0020](docs/adr/0020-correction-cost-is-delta-flat-plus-tier-proportional.md)). The older "3.4 s" figure is retired — it measured a publisher that maintained two tiers, not four.

**Honesty note — read before crediting this.** The proof ran in scratch databases
(`sonyliv_pub`/`sonyliv_pub_ctl`). On the **graded** database the publication layer is installed
but has **committed zero runs** (verified live 2026-08-01: `cc_publish_runs` is empty) — every
served number there was produced by batch rebuild (`tools/build-model.sh`), and its user tier
still carries the pre-ADR-0016 representation, which is correct under rebuild but cannot retract
incrementally. The capability is real and proven; it is not what currently maintains the graded
numbers.

| Evidence | Regenerate |
|---|---|
| [`evidence/publish.txt`](evidence/publish.txt) — 11 phases, convergence tables all zero | `make publish-test` |
| [`evidence/truncation.txt`](evidence/truncation.txt) — day-boundary truncation absorbed | `tools/truncation-test.sh` |
| [`evidence/load-guard.txt`](evidence/load-guard.txt) — re-loading a CSV cannot double the data | `tools/load-guard-test.sh` |
| [`evidence/target-resolution.txt`](evidence/target-resolution.txt) — one command → one database, no silent fallback ([ADR 0018](docs/adr/0018-one-target-one-database-no-cross-target-fallback.md)) | inline commands in file |

## 4 · Design quality

**Claim.** Every consequential choice is an ADR with the trade-off measured, not asserted — and the
repo keeps a record of the choices that *lost*, with the numbers that killed them.

- **16 ADRs** in [docs/adr/](docs/adr/). Start with
  [0007](docs/adr/0007-gate-answers-pause-needs-explicit-handling.md) (pause survives heartbeats —
  0.756/min vs 0.047/min backgrounded — so gap detection alone is provably insufficient),
  [0003](docs/adr/0003-hour-clipped-interval-splitting.md) (hour-clipped deltas: every hour is
  absolute, no query scans from t=0), and
  [0008](docs/adr/0008-all-seven-raw-dimensions-carried.md) (delta rows are hard-bounded
  regardless of dimension count — the "dimensions may increase" requirement).
- **Measured-and-rejected is documented:** the `ev_raw` projection (12.8× read reduction for the
  finalizer's shape, +91% storage — shipped: no, [`evidence/publish.txt`](evidence/publish.txt)
  PHASE 8/10); the two-tier lambda architecture (ADR 0004, collapsed by ADR 0013); heartbeat
  leases (ADR 0005, declined with reasoning).
- **Scale behaviour is measured, not extrapolated:** the same pipeline at 1×/10×/100× audience —
  fitted growth exponents are linear (k ≤ 0.98), the serving reconcile still passes at 100×
  (6,799 minutes, peak 251,668), and the first thing to break is named with numbers: the interval
  derivation's memory (~4.2 GiB at 100× on a 5.6 GiB laptop server, thread-dependent) —
  [`evidence/scale.txt`](evidence/scale.txt), regenerate `tools/scale-test.sh 1 10 100`.
- **Vendored official ClickHouse skill rules are cited in ADRs** and overturned one of our own
  schema choices ([ADR 0002](docs/adr/0002-order-by-time-bucket-then-platform.md)).
- Cross-model review: [docs/codex-validation/](docs/codex-validation/) — a different model audited
  our *claims*, and its findings (stale tiers, scope limits) were fixed or documented, not argued
  away.

## 5 · The unseen day

**Claim.** The pipeline is rehearsed for the drop, and the timings below are the **contract-first**
ones — the path we would actually run, not the build alone:

| | 6.9k events | 30k | 850k |
|---|---:|---:|---:|
| source-contract gate (throwaway DB) | 24 s | 26 s | 38 s |
| build — schema, load, derivation, views, answers, gate | 66 s | 67 s | 82 s |
| **total to plan against** | **90 s** | **93 s** | **120 s** |

Fixed-cost dominated rather than volume dominated: **123× the events costs 1.3× the time.**

⚠ An earlier version of this section claimed **58 s**, which was the build alone and predated the
source-contract step. That understated the real path by 1.7–2.1×, and the understatement mattered
more than the number: **the step an understated budget drops is the contract gate** — the one thing
standing between a malformed file and a confidently wrong submission. Re-measured 2026-08-02.

The runbook is written to be followed under time pressure, and answers come from the pipeline with
query-log evidence — no hand computation.

| Evidence | Regenerate |
|---|---|
| [`docs/RUNBOOK_UNSEEN.md`](docs/RUNBOOK_UNSEEN.md) — read BEFORE the data drops | — |
| [`evidence/unseen-rehearsal.txt`](evidence/unseen-rehearsal.txt) — end-to-end dry run, timed per stage | `tools/unseen-run.sh` |

(The rehearsal predates [ADR 0009](docs/adr/0009-same-second-resume-and-deterministic-attribution.md)'s
re-baseline, so its peak figure reads 2,887 where the current model says 2,917 — the *timings and
mechanics* are what that file evidences. Its gate findings have since been fixed in
`sql/90_reconcile.sql`.)

## 6 · OSS integration (ClickStack)

**Claim.** ClickStack is used two ways, both meaningful: (a) the concurrency visualization itself —
HyperDX charts reading our serving views (no hand-rolled frontend), and (b) **self-observation of
our own pipeline** — the Go CLI (`sonyliv observe`) emits OTLP for ingestion watermark lag, build
timing and the reconcile gate, landing in 6 provisioned dashboards / 41 tiles.

**New official evidence rule, fetched 2026-08-02.** Using ClickStack now carries an explicit
submission contract: commit the service deployment and integration wiring, keep secrets redacted,
state which ClickHouse service and tables receive its data, include the dashboards/searches actually
used in the team README, and demonstrate them live in the hosted demo and video. Existing screenshots
remain useful evidence but cannot establish integration by themselves. This package is not complete
until those artifacts are copied into the self-contained submission folder.

| Evidence | Regenerate |
|---|---|
| [`docs/CLICKSTACK_DASHBOARDS.md`](docs/CLICKSTACK_DASHBOARDS.md) — every panel, captured live | `make clickstack-cloud` |
| [`evidence/clickstack-dashboards.txt`](evidence/clickstack-dashboards.txt) | `tools/clickstack-artifact.sh` |
| [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) — what we emit and why | `sonyliv observe -target cloud` |

---

## Known limitations and open questions — the honest list

**0. Two known defects in our own model, disclosed before anything else.** Both were found by our own
property suite and confirmed independently; neither is a mentor question, both are ours.

- **Q35 · A viewer who generated exactly one event is counted as watching nothing.** A single-event
  run produces a zero-length segment that is dropped *before* the 60 s tail is applied. **182 runs**
  are affected, and counting them moves the peak **2,917 → 2,927** and adds **5.0 h** (80 changed
  minutes, +18,127 s, confirmed against live rows). We answer "counts nothing" **by accident** — it
  is a side effect of an `arrayFilter`, not a rule anyone chose. **Our gate cannot see it**, because
  `sql/90_reconcile.sql` carries the same filter. Unresolved and stated deliberately:
  **2,917 is our submitted number**, and this is the one internal question that would change it.
- **Q34 · User concurrency exceeds session concurrency in 82 cells**, worst excess **+1**, no total
  affected — the headline pair 2,844 ≤ 2,917 is correct. An invariant that "mostly holds" is not an
  invariant, so it is listed rather than dismissed.



None of these are hidden in footnotes; each has evidence and, where possible, a measured cost.

1. **The benchmark set is our reconstruction** (§2). If the official shapes differ, our latencies
   are indicative, not comparable.
2. **`resume` semantics are worth 9.7% of the headline number** — the largest fork *in the
   interval derivation* (the membership question in item 6a is larger still).
   `resume` fires for at least four distinct reasons (9,958 back-to-back `resume→resume` runs; 900
   sessions whose first pause/resume event *is* a resume), so whether the first `resume` after a
   `pause` genuinely ends the pause moves counted watch time by 189.2 h. Unknowable from the file;
   asked in [doubts/02](doubts/02-resume-semantics.md) with a decision table per answer. Five more evidence-backed questions in [doubts/](doubts/),
   seventeen in [docs/MENTOR_QUESTIONS.md](docs/MENTOR_QUESTIONS.md).
3. **The unclosed-pause rule is a policy call:** 23% of pauses never resume. Conservative
   (shipped) vs permissive differ by ~99 h / 5% (measured pre-ADR-0009; deliberately not
   re-scaled — see [WALKTHROUGH.md](WALKTHROUGH.md) §5).
4. **The graded database is batch-rebuilt** — the incremental publisher is proven in scratch but
   has never committed a run there (§3).
5. **Dedup is not inert at filter grain.** The 4,210 duplicate rows provably do not move totals or
   the 2,917 peak, but at the current 7-dimension grain they move a handful of per-dimension
   curves (UNK audio peak 183 → 184). Policy decision pending
   ([doubts/06](doubts/06-dedup-at-filter-grain.md)).
6. **The inclusive minute-boundary rule is self-confirming:** model and gate share it, so a green
   gate cannot decide inclusive vs half-open (moves 91 minutes; peak 2,917 → 2,916 under the
   alternative). Definition question for the organisers
   ([doubts/05](doubts/05-minute-boundary-membership.md)).

   **6a. And the broader form of that question is our single largest open number.** "Concurrent at
   minute M" can mean *active for any part of M* (what we ship) or *active at the instant M
   begins* — how a sampled gauge reads. Measured by rebuilding the derivation under both readings:
   peak **2,917 → 2,507, −410 viewers, −14.1%**, at the same peak minute. That is larger than the
   `resume` fork in item 2 and larger than every other assumption we probed. The gate is blind to
   it by construction — `sql/90_reconcile.sql` expands minutes with the same convention the model
   does, so both sides agree under *either* reading.

   We are not hedging our answer: **2,917 is our number**, under a stated and consistently applied
   convention, and we think any-overlap is the right reading for a concurrency metric. But a judge
   a judge sampling minute boundaries would see a systematic 14% gap with no
   defect anywhere in our pipeline, so it belongs in the open, not in a footnote
   ([doubts/09](doubts/09-minute-membership-instant-reading.md), full ledger of 21 probed
   assumptions in [evidence/adversarial/](evidence/adversarial/README.md) — ten came back safe at
   ≤0.1%).
7. **Serving paths expose different dimension subsets.** The minute delta tier carries all 7 raw
   dimensions; the hour/day cube, user tier, window views and stateless baseline carry
   platform/country/content only. Anything outside a shipped shape needs custom SQL over the delta
   tier — supported, but not pre-packaged ([WALKTHROUGH.md](WALKTHROUGH.md) §5 scope limits).
8. **`VideoHeartbeat` is not the documented 60-second beat** — inter-arrival p50 is 0 s (bursty
   telemetry). The organiser's data dictionary and their shipped file disagree; we model what the
   file does ([doubts/01](doubts/01-heartbeat-cadence.md)).
