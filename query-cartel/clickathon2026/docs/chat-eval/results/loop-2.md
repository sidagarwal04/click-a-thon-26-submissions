# Chat eval — loop 2

finished: 2026-08-02T06:04:27+05:30
score: **19/20** passed (1 failed)

> Note: a later `--only S06` verify briefly overwrote `loop-2.json`; full transcript
> detail lives in `loop-2-console.log`. S06 post-fix: PASS (see `s06-verify.json`).

| id | tier | result | tools | elapsed | failures |
|---|---|---|---|---|---|
| S01 | simple | PASS | db_schema | 8.65s |  |
| S02 | simple | PASS | db_schema, table_stats | 11.78s |  |
| S03 | simple | PASS | db_schema, aggregate | 18.36s |  |
| S04 | simple | PASS | db_schema | 22.25s |  |
| S05 | simple | PASS | db_schema, aggregate | 17.96s |  |
| S06 | simple | FAIL | get_context, get_changelog, list_insights, get_insight, reconcile | 98.56s | must_mention:OTP |
| S07 | simple | PASS | interrogate_spec | 13.1s |  |
| S08 | simple | PASS | list_insights | 12.18s |  |
| S09 | simple | PASS | db_schema, aggregate | 17.64s |  |
| S10 | simple | PASS | db_schema, aggregate, save_document | 39.31s |  |
| C01 | corner | PASS | list_insights, get_context, db_schema, aggregate | 33.0s |  |
| C02 | corner | PASS | db_schema, aggregate | 30.42s |  |
| C03 | corner | PASS | db_schema, aggregate | 32.59s |  |
| C04 | corner | PASS | db_schema, aggregate | 11.2s |  |
| C05 | corner | PASS | db_schema, aggregate | 45.13s |  |
| C06 | corner | PASS | interrogate_spec, run_spec, db_schema, table_stats | 17.33s |  |
| C07 | corner | PASS | interrogate_spec, get_changelog, get_context, list_insights | 23.42s |  |
| C08 | corner | PASS | db_schema, aggregate | 35.61s |  |
| C09 | corner | PASS | db_schema | 20.63s |  |
| C10 | corner | PASS | db_schema, sample_rows | 32.6s |  |

## Failures detail
### S06 — Known issues from context
- Root cause: `truncate_for_mcp` `DEFAULT_STR_LIMIT=4000` clipped `get_context.content` before §5 Known-issues (OTP / K1).
- Agent reconstructed from reconcile + insights; never said "OTP".
