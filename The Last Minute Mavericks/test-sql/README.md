# test-sql — small blind slices with planted anomalies, graded automatically

Two self-contained 10,000-row datasets. Each has anomalies hidden in it and an answer key next to
it. Load, run the real engine against it *blind*, then grade what came back.

```bash
./test-sql/run.sh                  # both folders: load -> scan -> verify
./test-sql/run.sh test2            # just one
REGEN=1 ./test-sql/run.sh          # regenerate the datasets first (deterministic — same bytes)
TRACE=1 ./test-sql/run.sh          # also log each scan to Langfuse and print the public trace URL
```

Traces are public, so a judge can open one without our credentials. Last traced run:
`rca_ts1` → [43fa3b34…](https://cloud.langfuse.com/project/cmsa4wcn20ah0ad0iy746nak4/traces/43fa3b34e4c35bd520869072820b827f),
`rca_ts2` → [06905a95…](https://cloud.langfuse.com/project/cmsa4wcn20ah0ad0iy746nak4/traces/06905a95b93ef7af363ccdbc7875105a).
Each is a root chain with one span per investigation carrying the verdict, culprit, LMDI/Shapley
decomposition, ruled-out list, and evidence objects with their `query_id`.

Current status (both PASS):

| | planted | detected | localized | magnitude | controls silent | false positives |
|---|---|---|---|---|---|---|
| **test1** | 3 (+1 control) | 3/3 | 3/3 | 3/3 exact | 1/1 | 0 |
| **test2** | 3 (+2 controls) | 3/3 | 3/3 | 3/3 exact | 2/2 | 0 |

## What's in a folder

| file | role |
|---|---|
| `spec.json` | the input — seed, shape of the slice, and the incidents to plant. Hand-written. |
| `dataset.csv` | 10,000 cube rows. Generated, deterministic from the seed. |
| `answers.json` | the **answer key** — generated alongside the CSV, including each incident's deviation *measured from the rows that were actually written*. |
| `bundle.json` | the engine's output from the last run. |

**Quarantine rule** (same as `tests/e2e/`): no engine, agent, or UI code may read `answers.json`.
The scan runs blind — `python run_incident.py --db rca_ts1 --json …` — and only `verify.py` opens
the answer key, after the bundle already exists. Tuning a threshold against this file turns the
rehearsal into a memory test.

## Why 10,000 *cube* rows and not 10,000 events

The engine scans `{db}.cube` — day × segment aggregates — and gates every segment at 1500
requests/day. 10,000 raw events spread over 40 days is ~250 events/day and would be invisible to
it: the test would measure nothing. So one record here is one cube row:

```
25 audience bases  ×  5 ad formats  ×  40 days  ×  2 rows (unfilled / filled)  =  10,000
```

standing in for ~2M requests/day, ~80M in total. Two rows per (base, format, day) is the real
schema, not padding: `vertical`/`campaign_type` come from the advertiser, which doesn't exist on an
unfilled request, so unfilled and filled events of one segment land in different cube rows. On the
filled row `requests == fills` by construction.

Statistical profile matches `teamkit/docs/DATA.md`: fill 78.1%, render 98.0%, CTR 1.088% of
impressions, eCPM ~2.47, weekends −20% on volume, +0.3%/day trend.

## What's planted

Every anomaly is injected on the **funnel**, never on the ratio, so
`requests × fill_rate × render_rate × ecpm/1000 ≡ revenue/day` still holds exactly — a fill drop
shrinks fills and everything downstream of them; an eCPM drop shrinks revenue only; a requests drop
scales every counter together so all ratios stay put.

**test1 — one incident per scanned metric, all 1-D**

| | metric | segment | window | planted |
|---|---|---|---|---|
| T1-1 | fill_rate | `region=LATAM` | Jun 23–25 | −45% |
| T1-2 | ecpm | `ad_format=video` | Jun 29–30 | −38% |
| T1-3 | requests | *global, no segment* | Jul 6 | −30% → must return `GLOBAL_UNLOCALIZED` |
| T1-C1 | control | `country=AE`, ~940 req/day | Jun 17–19 | −58% but under the 1500/day floor → must stay silent |

**test2 — the shapes that break naive detectors**

| | metric | segment | window | planted |
|---|---|---|---|---|
| T2-1 | fill_rate | `region=EU × os_version=Android 14` | Jun 24–26 | −50% in a ~10% cell → dilutes to −16.1% at `region=EU` and −13.2% at `os_version=Android 14` (engine's own numbers). Both 1-D views must be ruled out in favour of the cross-cut, each with a residual of +0.0% / +0.1% once the cell is peeled out. |
| T2-2 | ecpm | `category=finance` | Jul 1–2 | −40%; its baseline days fall inside T2-1's window, so it also exercises contamination exclusion |
| T2-3 | fill_rate | `device_model=Pixel 8` | Jul 7–9 | −35% **ramping in** (−11.7 / −23.3 / −35), not a step |
| T2-C1 | control | global eCPM | Jun 22 | −2%, under the 5% relative floor → must stay silent |
| T2-C2 | control | `ctr` @ `country=IN` | Jul 4–5 | −40% CTR and revenue doesn't move a cent — CPM model, clicks buy nothing. Out of scope by design. |

## What `verify.py` checks

1. **DETECTED** — right metric, overlapping window.
2. **LOCALIZED** — the culprit names every planted `dim=value`; a 2-D incident needs both cuts, a
   global one needs a `GLOBAL_*` verdict.
3. **MAGNITUDE** — reported deviation vs the deviation measured straight from the CSV, under the
   engine's own like-for-like baseline (same weekdays, 3 preceding weeks, other incident windows
   excluded). Both tests currently agree to 0.1pp.
4. **SUPPRESSED** — controls produced no investigation at all.
5. **Precision** — any investigation matching no planted incident is a false positive.

Exit code is 0 only if every incident localizes, every control stays silent, and magnitudes are
within 15pp. A magnitude miss under 15pp is a WARN: the engine may descend one dimension deeper
than we planted, which is a different cell, not a wrong answer.

## Notes for whoever changes this

- **Never pass `--rebuild-cube`** against `rca_ts1`/`rca_ts2`. There is no `ad_events` here; the
  cube *is* the dataset, and rebuilding drops it.
- The bases are an **orthogonal design** (geo × device grid, with category/tier/vertical rotated
  Latin-square style over it), not a random sample. This matters: with 24 randomly-drawn bases,
  `region=LATAM` ends up perfectly correlated with the 3 categories and 3 tiers its bases happen to
  carry, so dropping LATAM's fill moves 15 dimension values by the same −45%, nothing is dominant,
  and the engine correctly answers `GLOBAL_UNLOCALIZED`. That cost 2 of 3 localizations and was a
  broken *fixture*, not a broken detector.
- **Every base serves all five ad formats.** Format is the dominant eCPM driver (banner 1.3 →
  rewarded 3.9), so a base carrying a single format lets any fill-rate incident yank the format mix
  of every thin 2-D cell it touches. Measured with one format per base: test1's LATAM fill drop
  alone manufactured 4 phantom eCPM cells at −12%…+8%. With all five, the residual mix shift is
  ~1.7%, below the detector's floor, and those look-alikes land in the "ruled out" table where they
  belong.
- **A clean slice with zero planted incidents returns zero investigations** (verified). So every
  finding in test1/test2 traces to something we planted.
- Measured noise floor on that clean slice — 2-D eCPM cell vs its own median: p50 0.35%, p90 0.94%,
  p99 1.94%, max 4.32%. That's why the sub-floor control is −2% and not −4%: at −4% a cell reached
  −5.5%, crossed the 5% gate, and made the control flaky.
- The grader is not vacuous — it failed loudly during development on real defects (a segment sized
  at 27% of all traffic that stopped being localizable; a control that fired).
