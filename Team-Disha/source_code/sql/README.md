# ClickHouse RCA materialization (`sql/`)

Batch-build anomaly result tables in **`eda`** using ClickHouse functions + `INSERT…SELECT`.
LibreChat agents **read** these tables; they do not discover incidents with the LLM.

**ClickHouse-native path:** dictionaries → wow + seasonality z-scores → factors → segments/combos → day signals → incident clustering → counterfactuals. Python only enriches NL explanation text.

## Tables

| Table | Role |
|---|---|
| `dict_apps` / `dict_geo_device` / `dict_advertisers` | Dimension dictionaries (`dictGet`) |
| `rca_daily_wow` | Day vs T−7 + seasonality z-scores / `seasonal_ok` |
| `rca_ml_expected` | `simpleLinearRegression(T-7 → actual)` expected + residual_z |
| `rca_factor_day` | Requests / fill / eCPM decomposition |
| `rca_segment_day` | Single-dim segment WoW (dict-enriched) |
| `rca_combo_day` | OS×region / format×region WoW |
| `rca_day_signals` | Per-day candidate signals (SQL) |
| `rca_incidents` | Gap-and-island clustered catalog (SQL) |
| `rca_counterfactual` | What-if revenues holding factors at baseline |

## Commands

```bash
# Rebuild RCA layers from current metrics_hourly + ad_events
uv run clickathon materialize

# After loading a new test file into eda.ad_events (+ dims):
uv run clickathon materialize --rollup

# Health / calibration (current synthetic dataset expects 4 windows)
uv run clickathon materialize --check --calibration
uv run python stack/scripts/parity_rca_store_e2e.py
```

## New test file tomorrow

1. Load events into `eda.ad_events` (and refresh `geo_device` / `apps` / `advertisers` if needed).
2. `uv run clickathon materialize --rollup` — rebuilds `metrics_hourly`, then all `rca_*`.
3. `uv run clickathon materialize --check` — assert non-empty wow tables.
4. Agents keep the same tools (`list_all_anomalies` → `rca_incidents`, `counterfactual` → `rca_counterfactual`).

Do **not** use `--calibration` on a new unknown dataset (that flag is for the planted Jun 2026 windows only).

## SQL layout

- `00_metrics_hourly.sql` — truncate+insert rollup from `ad_events`
- `rca/01_functions.sql` — metric / flag UDFs
- `rca/01b_dictionaries.sql` — star-schema dictionaries
- `rca/02_tables.sql` … `03_daily_wow.sql` — DDL + wow + seasonality
- `rca/03b_expected_ml.sql` — simpleLinearRegression expected baselines
- `rca/04_factor_day.sql` … `06_combo_day.sql` — factor/segment layers
- `rca/07_day_signals.sql` — SQL signal assembly
- `rca/08_incidents.sql` — SQL gap-and-island clustering
- `rca/09_counterfactual.sql` — counterfactual evidence pack
