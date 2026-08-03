# fast and furious

## Track
SonyLIV

## Project
Foreground-only concurrency at streaming scale — a ClickHouse-native pipeline and
serving layer that answers "how many viewers, right now" without counting sessions
sitting idle in the background.

## Team Members
- Ishant Dahiya ([@ishantd](https://github.com/ishantd))
- Siddhartha Mishra ([@SiddharthaMishra](https://github.com/SiddharthaMishra))

## What it does
Ingests the supplied SonyLIV event extract into ClickHouse Cloud, resolves each
session into foreground-only active intervals, and serves a concurrency curve
(peaks, ramps, hot-hour) with filters over the dataset's own dimensions
(content/asset, device/platform, geo/region, subscription tier). Verified against
two independent read paths off the same underlying data.

## Hosted Demo
[Dashboard](https://fastandfurious.live/)
[Chat with Data ](https://chat.fastandfurious.live/) Please signup before using. No friction, only email required.

## Demo Video
[Demo Video](https://clickathon.blr1.digitaloceanspaces.com/demo-video.mp4)

## Pitch Deck
[Pitch Deck](https://clickathon.blr1.digitaloceanspaces.com/pitch-deck.pdf)

## Architecture
Three stages, all on ClickHouse Cloud (`sonyliv` database, `ap-south-1`):

1. **Ingest** ([`ingest/`](ingest/README.md)) — Go pipeline on the ClickHouse native
   connector, loading the supplied CSVs plus a synthetic-traffic generator for the
   same write path. Design notes and measurements in
   [`ingest/ARCHITECTURE.md`](ingest/ARCHITECTURE.md).
2. **Analytics design** ([`solution/`](solution/README.md)) — the concurrency model,
   executable SQL, and a chDB-verified correctness harness
   (`solution/tools/verify_embedded.py`), independent of the Cloud deployment.
3. **Serving pipeline** ([`pipeline/sql/`](pipeline/sql)) — the Cloud-deployed
   stages that build `active_intervals_current`, `concurrency_deltas`, and the
   bucket/checkpoint tables the concurrency curve and filters read from.

Dashboards and the observability/analyst stack (ClickStack, Langfuse, LibreChat)
are documented in [`deploy/README.md`](deploy/README.md).

Full build log, every Cloud-specific defect found and fixed along the way, and the
verified reference figures are in [`ENGINEERING_LOG.md`](ENGINEERING_LOG.md).

## How we built it
- **ClickHouse Cloud** as the primary database — ingestion, the concurrency model,
  and the serving layer all run against it, not a local substitute.
- **Go** for the ingest pipeline (native ClickHouse connector).
- **chDB** for an embedded, reference-data correctness harness that runs
  independently of the live Cloud deployment.
- **ClickStack**, **Langfuse**, **LibreChat** — integrated over the same serving
  layer; see [`deploy/README.md`](deploy/README.md) for how each is wired in.

## How to run it
1. `cd ingest && make check` — runs the Go test suite, `vet`, and `gofmt`.
2. `python3 solution/tools/verify_embedded.py` — runs the chDB correctness harness
   against the supplied CSVs.
3. Deploying against a live ClickHouse Cloud service: see
   [`ingest/README.md`](ingest/README.md) and [`pipeline/`](pipeline) for the DDL
   and population statements, and [`deploy/README.md`](deploy/README.md) for the
   ClickStack/Langfuse/LibreChat stack.

## Dataset filters
Filters exposed over the concurrency curve, and the dataset column backing each:
see [`solution/README.md`](solution/README.md) and [`pipeline/sql/020_serving_layer.sql`](pipeline/sql/020_serving_layer.sql)
for the filter dimensions (content/asset, device/platform, geo/region, subscription
tier) and the columns they read from.


