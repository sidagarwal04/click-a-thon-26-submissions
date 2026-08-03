# Graded artifacts (Atlys §3)

Exported from local ClickHouse (`ops.job_artifacts`) after running specs 01–06 + standard probes.

| Path                        | Contents                                     |
| --------------------------- | -------------------------------------------- |
| `ddl/`                      | Generated CREATE TABLE SQL for specs 01–06   |
| `context/`                  | Changelog, per-feature diffs, contradictions |
| `analytics/`                | 4 standard probes + coupon product ask       |
| `06_promo_coupon_checkout/` | 6th schema + summary + product insight       |
| `langfuse/TRACE_LINKS.md`   | Trace IDs / URLs                             |

Langfuse links point at JP Cloud (`https://jp.cloud.langfuse.com`) for public/shareable traces.
