# Data Profile — read this instead of loading 98 MB

All synthetic. Measured directly from `ad_events.parquet`. The **data-of-record is the team
ClickHouse service**, not files in this repo — load once, everyone queries the same service.
Do NOT commit the parquet (gitignore it or use Git LFS); commit the loader instead.

## Getting the files — one command, repo-relative, no absolute paths
Data lives in a **repo-relative `./data/`** (gitignored — the 98 MB parquet never enters git).
From the repo root, after cloning:
```bash
bash scripts/fetch_data.sh
```
This pulls **all four files** (parquet + 3 CSVs) into `./data/` from the organizer's public repo
and verifies sizes/row counts. Everyone gets identical data at the **same path**, so all code
reads `./data/…` — never a machine-specific absolute path.

> Why a script and not a plain clone: the parquet is a normal blob on `raw.githubusercontent`,
> but the three CSVs are **Git LFS pointers** (130-byte stubs on a plain clone → loader fails at
> 2am). `fetch_data.sh` grabs the parquet from `raw` and the CSVs from the `media` LFS endpoint.
> Manual fallback: `git lfs pull --include="InMobi/*"` inside an upstream clone.

Verify: `data/ad_events.parquet` ≈ **98 MB**; CSV rows **2000 / 500 / 5000** (excluding header).

## Files (from the InMobi package)
| File | Rows | Notes |
|---|---|---|
| `ad_events.parquet` | **9,000,000** | fact table, 9 row groups, ~98 MB |
| `apps.csv` | 2,000 | dimension |
| `advertisers.csv` | 500 (+`adv` blank on unfilled) | dimension |
| `geo_device.csv` | 5,000 | dimension |

## Fact schema (`ad_events`)
```
event_time     timestamp[ms]   2026-06-01 00:00:00 → 2026-07-05 23:59:59  (5 weeks)
app_id         string          2,000 distinct
geo_device_id  string          5,000 distinct
advertiser_id  string          501 distinct; '' when is_filled=0
ad_format      string          banner|native|interstitial|video|rewarded
is_filled      uint8           Σ 7,027,910  (mean 0.781)
is_impression  uint8           Σ 6,887,058  (mean 0.765)
is_click       uint8           Σ    74,940  (mean 0.0083)
revenue        double          Σ 17,020.36
```

## Global baselines (what "normal" is)
| Metric | Value |
|---|---|
| Fill rate | 0.7809 (78.09%) |
| Render rate (imp/fill) | 0.9800 (98.00%) |
| **CTR** | **0.01088 (1.088%)** |
| eCPM | 2.4714 |
| RPR (revenue/request) | 0.001891 |
| Revenue / day | ~500–550 (weekends dip to ~410–460) |
| Requests / day | ~215k (weekend) – ~288k (weekday, rising trend) |

> **CORRECTED.** This table previously listed `CTR ~0.83%`. That is `74,940 / 9,000,000` —
> clicks over **requests**, i.e. the `is_click` column mean. CTR is defined over
> **impressions**: `74,940 / 6,887,058 = 0.01088`. Anything baselined against 0.83% is 31% low.
> The column means in the schema block above are *not* metric values — do not reuse them as
> baselines. This is exactly the avg-over-wrong-denominator trap the next line warns about.

Decomposition backbone: `Revenue ≈ Requests × fill_rate × ecpm/1000`.
Ratios are **sum/sum** over the group, never avg-of-ratios.

## Search space (drives the detector's cost and its false-positive budget)
Low-cardinality dimensions: `ad_format 5 · category 7 · publisher_tier 3 · region 5 ·
country 16 · device_model 8 · os_version 8 · vertical 7 · campaign_type 3`

→ **62** one-dimension slices · **1,647** two-dimension pairs · **1,709** candidate segments.
Across 8 metrics that is **13,672** metric-slice checks — 114 human-hours at 30s/slice.
That ratio is our Problem-fit number; it is computed, not claimed.

`app_id` (2,000), `advertiser_id` (500) and `geo_device_id` (5,000) contain **no planted
anomaly**. Do not scan them as candidates — 7,500 extra segments is pure false-positive risk.
Drill into them only *after* a low-cardinality segment is already localized.

## Integrity facts (assert these after load)
- The funnel is **perfectly consistent**: zero impressions without fills, zero clicks without
  impressions, zero revenue without impressions.
- `advertiser_id = ''` on exactly **1,972,090** rows = exactly `9,000,000 − 7,027,910`, the
  unfilled set. This is structural, not dirty data. Do not drop it, and do not let it become a
  silent dimension value in advertiser attribution.
- **`render_rate` and `ctr` are flat across all 35 days** (0.9793–0.9806 and 0.01014–0.01138).
  Neither contains a planted anomaly. A detector that fires on either is fabricating.

## Dimension values (for Adtributor whitelists)
- `ad_format`: banner, native, interstitial, video, rewarded
- `apps.category`: gaming, social, entertainment, news, ecommerce, utility, finance
- `apps.publisher_tier`: tier_1, tier_2, tier_3
- `advertisers.vertical`: gaming, ecommerce, finance, travel, entertainment, auto, cpg
- `advertisers.campaign_type`: CPM, CPC, CPI
- `geo_device.region`: **NAM** (not NA), EU, APAC, LATAM, MEA
- `geo_device.country`: **exactly 16** — US, CA, UK, DE, FR, ES, IN, JP, ID, PH, BR, MX, AR, ZA, AE, …
- `geo_device.device_model`: iPhone / Pixel / Galaxy / Redmi models
- `geo_device.os_version`: iOS 16.4/17.2/17.5/18.1, Android 12/13/14/15

## Seasonality & trend — data characteristics (needed for a correct baseline, NOT answers)
Real structure the baseline must respect so normal variation isn't mistaken for an anomaly:
- **Weekly seasonality** — weekends run ≈ −20% on volume. Compare same-weekday, never a flat mean.
- **Hour-of-day** swing ≈ 1.8× (only matters if you go sub-daily; the cube is day-grain).
- **Growth trend** ≈ +9% over 4 weeks (Mon Jun 1 → Mon Jun 29). A flat global mean would drift.
- `render_rate` and `ctr` are **flat** across all 35 days — inherent data facts, not answers.

## Ground truth lives in `tests/`, NOT here — the detector never reads it
This file is a **neutral data reference** (schema · paths · baselines · integrity · dimensions).
It deliberately does **not** list "the anomalies" or their causes. That answer key — used only to
**score** the detector — is quarantined in `tests/detection_eval.py` / `tests/battletest.py`.

Why: the detector must **recompute anomalies live from ClickHouse every run** and be *graded*
against that manifest — it must never *read* the answer. Keep the pre-freeze check green:
```
grep -rnE "2026-06-2[0-9]|Android 15|iOS 18\.1|finance|APAC|INC-[ABCD]" sql/ agent/ run_incident.py
```
should return nothing. To *see* the current anomalies, don't read a doc — run the detector:
`python run_incident.py` (or `--audit` for the full segment landscape).

## Loading into ClickHouse (sketch — real loader lives in `sql/00_load.sql` / `load.sh`)
```sql
-- paths are repo-relative ./data/ (populated by scripts/fetch_data.sh)
INSERT INTO rca.ad_events   FROM INFILE 'data/ad_events.parquet' FORMAT Parquet;
INSERT INTO rca.apps        FROM INFILE 'data/apps.csv'         FORMAT CSVWithNames;
INSERT INTO rca.advertisers FROM INFILE 'data/advertisers.csv'  FORMAT CSVWithNames;
INSERT INTO rca.geo_device  FROM INFILE 'data/geo_device.csv'   FORMAT CSVWithNames;
```
Loader must be **schema-tolerant** (read column names from the file) so the unseen slice can't
break ingestion. Verify `count()=9,000,000` and the date range before trusting any analysis.
