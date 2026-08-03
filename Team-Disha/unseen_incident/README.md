# Unseen incident bundle (Day-2)

Per [InMobi submission guidelines](../../INMOBI_SUBMISSION_GUIDELINES.md).

| Artifact | File | Status |
|---|---|---|
| Plain-language diagnosis | [`diagnosis.md`](./diagnosis.md) | Done |
| Numbers / SQL evidence | [`numbers.md`](./numbers.md) | Done |
| Langfuse trace | [`trace.md`](./trace.md) | Done |
| Langfuse JSON export | [`langfuse/`](./langfuse/) | Done |
| Materialize summary | [`materialize_summary.json`](./materialize_summary.json) | Done |
| ClickStack evidence | [`../evidence/clickstack/`](../evidence/clickstack/) | Done |

## Load + verify (separate `eda`, no append)

Full instructions live in the team [`README.md`](../README.md#3-day-2-unseen-dataset-separate-eda-no-append). Short form from `source_code/`:

```bash
uv run python stack/scripts/upload_unseen.py /path/to/InMobi/unseen_data
uv run clickathon materialize --rollup
uv run python stack/scripts/verify_unseen_rca.py   # re-query CH; check vs diagnosis.md
```

- `eda.ad_events` = **only** Jul 6–10 unseen (1.5M rows)
- Dims replaced from unseen CSVs
- T−7 baselines read from **`default.ad_events`** (history not copied into `eda`)
- Restore original later: `uv run python stack/scripts/restore_eda_from_default.py`

## Incidents found

| Id | Probe | Factor | Segment |
|---|---|---|---|
| A | 2026-07-07 | ecpm | video × APAC |
| B | 2026-07-08 | fill_rate | iOS 17.5 |
| C | 2026-07-10 | ecpm | video × APAC |
