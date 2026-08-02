# Ingestion rules

The data-plane service streams the NDJSON directly to ClickHouse; it is the
only ingestion route. Create a new empty table, use JSONEachRow, ingest the
entire source once, and reconcile accepted against source rows. Direct batches
of 10,000–100,000 rows are preferred; a smaller bounded fixture can be one
insert. Do not use mutations or `OPTIMIZE FINAL` as validation.

Source rules: `insert-batch-size`, `decision-ingestion-strategy`.

