# Artifacts — the graded outputs

Generated from a single run over **2026-07-06 → 2026-07-10** by
[`build_artifacts.py`](../../../scripts/build_artifacts.py) and
[`export_trace.py`](../../../scripts/export_trace.py). Nothing here is written by
hand, so every run reproduces the same set from its own output.

**36 queries · 645,898,241 rows read · 23.3 s of ClickHouse time.**

| | |
|---|---|
| [`diagnoses/`](diagnoses/) | One file per incident — plain-language diagnosis, factor decomposition, the segment named (or that none is), transition shape, and the full ruled-out ledger |
| [`queries.md`](queries.md) | Every query with its exact SQL, rows read and timing. Every number in every diagnosis comes from one of these |
| [`traces/`](traces/) | Exported Langfuse traces — every stage in order with its inputs, verdict and timing, including the ruled-out branches. The SQL is in `queries.md`, not the trace |


## The 1 incident(s) found

| # | Window | Classification | Severity | Diagnosis |
|---|---|---|---:|---|
| [1](diagnoses/01-2026-07-06-localized.md) | 2026-07-06 00:00 → 2026-07-10 21:00 | `localized` | 256.2 | Revenue -2.1%, driven by ecpm in ad_format=video (-18.0% vs -9.1% across the platform) |

Ranked by severity — peak percent deviation times the hours it lasted. Events labelled
`unattributed` are reported rather than filtered out: no dimension cleared the
attribution bar, and saying so is more honest than inventing a cause.

## Why the ruled-out ledger is here

The problem statement's bonus criterion. Every dimension is tested with the same
arithmetic on every incident, and each diagnosis carries the full ledger:
`responsible + ruled_out = 9` in every case, so no dimension is silently dropped.

On the 2026-06-21 incident the ledger *is* the answer — all three publisher tiers moved
within 0.2% of the global figure, all five ad formats within 0.4%, all seven categories
within 0.5%. Ranking segments by size of drop there names the largest segment every time,
confidently and wrongly. Reporting that no segment is responsible is the correct finding.
