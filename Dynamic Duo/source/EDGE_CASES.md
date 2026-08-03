# Edge cases — regression fixture

The dev data has 5 anomalies, all clean single-dimension step changes. The organisers
release an unseen slice in the final hours. A system tuned to the dev anomalies passes
today and fails then.

This fixture plants anomaly *mechanisms* the dev data never had, and declares the
verdict each must produce.

Two things matter more than the individual cases:

- `--randomize-targets` re-rolls which segment each mechanism hits. If the agent only
  ever finds `Android 15`, it memorised the build data. Run one randomized seed before
  submitting.
- Seasonality is tested in **both** directions. Alarming on a normal Sunday is worse
  than missing an anomaly.

## Run it

```bash
# 1. generate (deterministic: same seed -> identical bytes)
python3 tools/gen_edge_cases.py --out-dir /tmp/edge
python3 tools/gen_edge_cases.py --out-dir /tmp/edge_rnd --seed 7 --randomize-targets

# 2. CSV -> Parquet (ClickHouse does it; no pandas needed)
SCHEMA="event_time DateTime64(3,'UTC'), app_id String, geo_device_id String,
        advertiser_id String, ad_format String, is_filled UInt8,
        is_impression UInt8, is_click UInt8, revenue Float64"
cd librechat && docker compose exec -T clickhouse clickhouse-local \
  --input-format CSVWithNames --structure "$SCHEMA" \
  --query "SELECT * FROM table FORMAT Parquet" < /tmp/edge/edge_events.csv \
  > /tmp/edge/edge_events.parquet

# 3. load + detect + investigate
CH_HOST=localhost CH_SECURE=0 CH_USER=rca_rw CH_PASSWORD=rca_rw_dev \
  ./load.sh --events /tmp/edge/edge_events.parquet --dataset edge
export CH_HOST=localhost CH_SECURE=0 CH_TRANSPORT=http CH_USER=rca_rw CH_PASSWORD=rca_rw_dev
python3 -m detector.profiler && python3 -m detector.sweep
cd librechat && docker compose exec -T -e RCA_DATASET=edge rca-mcp python -m agent.prefill

# 4. score
docker compose exec -T rca-mcp python tools/regress_edge_cases.py \
  --manifest /tmp/edge/edge_manifest.json
```

Release day has no oracle. Same tool, report mode — emits the submission artifact
(verdict, numbers, guardrail status, trace id per incident):

```bash
docker compose exec -T rca-mcp python tools/regress_edge_cases.py \
  --report-only --since <first date of the organisers' slice>
```

## The cases

| id | what happens | why it's hard | verdict |
|----|--------------|---------------|---------|
| S01 | one `os_version`'s fill steps down | the control case | `CAUSE_CONFIRMED` |
| S02 | all segments' requests drop 40% | no segment hits 50% of the move — must not name a scapegoat | `GLOBAL_MOVEMENT` |
| S03 | traffic shifts to a weaker `ad_format`, every segment's own rate flat | sweep reads "uniform" and says GLOBAL. Only the Kitagawa split shows mix dominating | `MIX_SHIFT` |
| S04 | fill drops only for `os_version` × `region` | neither dimension alone explains it; residuals shrink but never clear | `INTERACTION` |
| S05 | one `vertical` stops bidding | fill-by-vertical is **undefined** (unfilled rows have no advertiser). Ratio sweep is blind; only a volume sweep on fills finds it | `DEMAND_PULLOUT` |
| S06 | CTR spikes 4.5× in one country, revenue flat | an **up** move — thresholds must be `abs()`. Not a win: it's click fraud | `CAUSE_CONFIRMED` |
| S07 | fill drops 08:00–17:00 only | dilutes below threshold across a full day; window must follow hour buckets | `CAUSE_CONFIRMED` |
| S08 | `geo_device_id`s missing from the dim table | must land in `unknown`. An inner join would **drop the rows that moved** | `CAUSE_CONFIRMED` |
| S09 | fill collapse + unrelated eCPM drop, same day | diagnosing one must not close the other | `CAUSE_CONFIRMED` ×2 |
| S10 | zero events 02:00–06:00 | a pipeline hole, not a segment's fault | `GLOBAL_MOVEMENT` |
| S11 | eCPM drops on one `campaign_type` | price lever, advertiser-side dimensions | `CAUSE_CONFIRMED` |
| S12–14 | eCPM drifts −5% → −10% → −15% over 3 days | no single day is a step, and the ramp poisons its own baseline | `ANY` |
| S15 | real fill collapse **on a Sunday** | seasonality masks it — see below | `CAUSE_CONFIRMED` |
| S16 | weekend-sized −19% volume drop **on a Wednesday** | same number, different day — see below | `GLOBAL_MOVEMENT` |
| S17 | 4-day slice, no history | `min_clean_days < 2`, so q1/q2/q3/q5 are all impossible. Only sibling comparison works | `PEER_OUTLIER` |

S17 ships as a separate file and needs its own pass. Detection is dataset-blind, so a
history-free slice placed after a continuous timeline reads as a week of zero-volume
incidents. Wipe, load only the short slice, sweep, investigate.

## Seasonality

The data has daily (`s24≈0.93`) and weekly (`s168≈0.90`) seasonality. Sunday is −19% on
volume; 00:00–05:00 is −32% against a flat mean. A flat baseline flags every weekend
and every night.

One-sided tests prove nothing — you can pass by being too eager or too lazy. All three
are required:

| test | fails if |
|------|----------|
| 4 clean weekend days raise no **open** incident | baseline is flat or pooled → normal Sunday reads as an incident |
| S15: real collapse planted on a Sunday is still caught | same flat baseline blames the weekend and dismisses a real incident |
| S16: weekend-sized drop on a Wednesday is flagged | baseline isn't weekday-aware — −19% is normal Sunday, an incident Wednesday |

A non-same-weekday baseline must fail at least one. Passing all three is the evidence.

Flagged then closed as `ruled_out_seasonal` = **pass** on the negative test. The
classifier looked and declined to alarm. Only an incident left *open* is a failure.

## Fidelity rules for any synthetic slice

Each cost a wave of false incidents before it was fixed.

1. **Match the parent universe's volume.** The rollup has no `dataset` column and
   `detector/sweep.py` doesn't filter by dataset — `main` and the new slice are one
   timeline to detection. 120K/day against main's 257K made every day a −53% step
   change.
2. **Inherit cross-sectional structure, not just marginals.** eCPM from `ad_format`
   alone collapsed every country to the mean (NG +118%, US −32% at the boundary) →
   ~20 false `revenue:country=*` incidents. Now baked in: `ECPM_BY_COUNTRY` (0.46–1.47),
   `FILL_BY_TIER` (0.86–1.16). Region, category, vertical, eCPM-by-tier all measured
   within 1% of 1.0 — deliberately not modelled.
3. **History-free slices need their own pass** (see S17).
4. **`hourly_continuity` fails by design.** S10 removes 4 hours, so load validation
   reports `1676/1680 pass=0`. A *passing* check means S10 didn't land.
5. **Scenario effects use `*=`, not `=`**, so anomalies ride on top of real structure.

## Reading the score

- **PASS** — expected verdict reached.
- **WARN** — flagged and investigated, verdict differs. Often defensible
  (`GLOBAL_MOVEMENT` where `MIX_SHIFT` was planted is a localisation difference, not
  blindness). Read the headline.
- **FAIL** — nothing detected, nothing investigated, or an incident left open on a
  seasonal-clean day.

`ANY` (S12–S14) means day 1 of a −5% drift is under threshold by design. Recorded as
WARN rather than pretending a miss is a pass. What matters is day 3 being caught.

## Finding: baseline starvation (resolved 2026-08-02)

First scored run: **4 pass, 11 warn, 5 fail**. Nearly every verdict came back
`PEER_OUTLIER` / `NO_PEER_OUTLIER` — the short-history path. The baseline path
(q1/q2/q3/q5), which is what produces `CAUSE_CONFIRMED`, `MIX_SHIFT`, `INTERACTION`
and `DEMAND_PULLOUT`, never ran.

Cause chain:

1. sweep flags an incident on a day (including noise and boundary artifacts)
2. prefill diagnoses it, chronologically
3. q6 excludes that date from every later baseline
4. later incidents run out of clean same-weekday days
5. `min_clean_days < 2` -> peer path -> `PEER_OUTLIER`

For an incident on Mon 2026-07-20, both prior Mondays (07-06, 07-13) were excluded.
`excluded_dates` held 20+ dates — almost the whole history.

Two consequences:

- **Release-day critical.** A noisy unseen slice starves its own baselines. Everything
  degrades to peer comparison, which is explicitly the weaker path ("treat this as the
  leading candidate, confirmed only against history").
- **Seasonal days get re-opened.** 07-11 and 07-18 were correctly closed
  `ruled_out_seasonal` by the detector, then the peer path re-diagnosed them as
  `PEER_OUTLIER`, which is terminal-diagnosed. A correctly-dismissed seasonal window
  became a false positive.

Options to weigh (not yet decided):

- exclude only dates diagnosed for the **same metric/scope**, not all dates globally
- never exclude `ruled_out_seasonal` / `dismissed` dates
- floor it: always keep the N most recent same-weekday days, excluded or not
- let the slice share history — `dataset IN ('main','unseen')`, the open question
  already noted in CLEAN_RUN.md. This fixture is the evidence it matters

**Resolution — a fifth option, adopted: q6 excludes only confirmed-cause verdicts.**
The leak was never the status enum: `PEER_OUTLIER` may stay terminal-`diagnosed`
(the 381c838 position holds). The leak was q6 keying exclusion off `status` alone,
so hedged short-history verdicts — which the narrative itself calls "a leading
candidate, confirmed only against history" — were re-shaping every later baseline.
q6 now joins `diagnoses.verdict_code` and excludes only
CAUSE_CONFIRMED / INTERACTION / MIX_SHIFT / MIX_INTERACTION / DEMAND_PULLOUT /
VOLUME_CANDIDATE / GLOBAL_MOVEMENT. One SQL file changed, zero Python.

Measured on this fixture (seed 20260802, identical runs before/after):
4 pass, 11 warn, 5 fail → **6 pass, 9 warn, 5 fail**, and — the actual point —
**zero peer-path verdicts remain**: every investigation runs the baseline path, the
drift day is `SEASONAL_CONFIRMED`, and both prior consequences are gone (baselines
never starve; the re-opened seasonal days stay closed). On the dev data the
clean-run success table is reachable again: Jun 23 → `CAUSE_CONFIRMED` Android 15.

Still open, now visible **because** the peer fog lifted:

- **q3 residual bar vs large events** (most remaining WARNs): a fixed 0.5 pp
  ruled-out threshold is right-sized for ~3 pp events but a 13 pp step leaves
  correlated shadows above it in sibling dims → verdict lands `INTERACTION` with the
  correct primary segment named. Candidate fix: scale the bar with the candidate's
  contribution (e.g. `max(noise, 0.1 × |global move|)`).
- **Detection misses** (S05 demand pullout, S16 broad-but-sub-z, drift day 1-2):
  sweep-side, unrelated to q6.

