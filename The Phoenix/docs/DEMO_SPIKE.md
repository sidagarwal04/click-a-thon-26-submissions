# Spike sustainability: healthy vs weak, same audience, opposite verdict

Implements `sonyliv_spike_sustainability_data_injection_spec.md` against **`phoenix_next`**, the
insight database the frontend reads. The spike scripts never touch `phoenix`, which holds the
graded corpus.

The spec names a separate `phoenix_insights` database. One was built and then dropped: it doubled
the schema surface and meant the spike demo could not be shown beside the live insights it exists
to explain. Everything below runs in `phoenix_next`, isolated by `content_id = 990001` instead of
by database, and `--cleanup` removes it entirely.

## Run it

```bash
./scripts/spike_scenarios.sh            # 20,000 sessions per scenario
SESSIONS=2000 ./scripts/spike_scenarios.sh   # rehearsal
./scripts/spike_scenarios.sh --cleanup
```

## Result (2,000 sessions per scenario, seed 20260802)

| | Healthy | Weak | Spec requires |
|---|---:|---:|---|
| Sessions acquired | 2,000 | 2,000 | identical |
| Peak concurrency | 2,000 | 2,000 | identical |
| Minutes to peak | 2 | 2 | 2–4 |
| Minutes above 80% of peak | **13** | **3** | ≥10 / ≤3 |
| Retention @5m | 97.8% | 48.6% | ≥90% / ≈65% |
| Retention @10m | 93.0% | 20.8% | ≥82% / ≤45% |
| Retention @15m | 78.0% | 3.5% | ≥75% / ≤30% |
| Background rate | 3% | 15% | ≤5% / ≥20% |
| Error rate | 1% | 5% | ≤2% |
| **Classification** | **`healthy_sustained`** | **`short_lived`** | as stated |

**Verdict: PASS.** The two spikes are indistinguishable at the peak, same acquisition, same
shape, same minute, and diverge completely afterwards. A detector that keys on the peak calls
them identical; one that measures foreground retention separates them.

## Honest gaps

- **`timeout_rate` reads 0 for both**, though the weak scenario contains 10% heartbeat-timeout
  sessions and the healthy one 1%. `session_insight_facts.timed_out` is not being set by the
  existing refresh. The classification does not depend on it (retention and above-80% carry the
  verdict), but the column is reported as measured rather than quietly dropped.
- **Weak retention @5m is 48.6%, not the spec's ≈65%.** The weak segment durations are more
  aggressive than the spec intends, so the drop is ~51% rather than ~35%. It clears the
  `short_lived` threshold comfortably; tightening it to hit 65% exactly is a parameter change in
  `WEAK_PARAMS`, not a design change.
- **Deviations from the spec, deliberate.** The separate `phoenix_insights` database was dropped
  in favour of `phoenix_next` (see above). `arrival_timestamp` is not emitted, because the landing
  table deliberately does not carry it: per `sql/schema/01_raw_events.sql` a producer supplying its
  own arrival time is supplying a claim rather than an observation, and the materialized view
  stamps the real one. `session_state_transitions` **has since been built**, so the spike verdict
  could now read background and error rates from either it or `session_insight_facts`; it still
  uses the latter, because the rates a verdict needs are per session and that is already their
  grain.

## Three ClickHouse traps this cost

**Lightweight `DELETE` then re-insert silently masks the new rows.** Cleaning with
`DELETE FROM raw_events WHERE content_id = 990001` before each load produced: `INSERT` reports
`written_rows = 77,391`, the MV finishes with no exception, and `SELECT count()` returns **0**.
The rows were physically in the partition, 108,521 of them in `system.parts`, and every one was
masked. Cleaning is now `DROP PARTITION`, which is metadata-only and leaves nothing behind. This
is what `insert-mutation-avoid-delete` means in practice.

**Replicated insert deduplication silently drops a byte-identical re-load.** The generator is
deterministic *because the spec demands it*, fixed seed, so a correctness gate can compare runs.
That makes every re-run produce an identical block, which ClickHouse discards as a duplicate
within its dedup window. Measured at the time, in the since-dropped `phoenix_insights`: it held
the weak scenario and none of the
healthy one, because the healthy block was still inside the window and the weak one had aged out.
Worse, the classifier still returned `healthy_sustained`, computed from insight rows left by an
earlier run, since those tables are ReplacingMergeTree and nothing had removed them. **A green
verdict from data that was no longer in `raw_events`.** The scenario loads now set
`insert_deduplicate=0`; `load.sh` is left alone, because for the real corpus a repeat load *is* an
accident.

**`FINAL` is mandatory when summing a ReplacingMergeTree.** The spike curve reads
`audience_minute_snapshot`, which stores one version per refresh. Summing without `FINAL` added
the superseded versions and reported a peak of 8,000 for a 2,000-session scenario, exactly 4x
after four runs. The retention *ratios* survived it, numerator and denominator scale together , 
which is what made it dangerous: the verdict stayed right while the headline number was wrong.

## Where the classifier lives, and why not in `pipeline/`

`sql/insights/spike/refresh_spike_events.sql`, not `sql/insights/pipeline/`. `refresh_insights.sh`
globs that directory and runs every file with only `from_ts` and `to_ts` bound; this statement also
needs `content_id` and `version`, so being globbed made `refresh_insights.sh` fail with an unbound
parameter on every run, including runs with nothing to do with spikes.
