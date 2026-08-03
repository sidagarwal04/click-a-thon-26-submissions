# SonyLiv Click-a-thon 2026

Submission repo for [Click-a-thon 2026](https://clickhouse.com/clickathon/india2026) — ClickHouse's 24-hour hackathon in Bengaluru (1–2 August 2026), SonyLiv problem statement track.

Problem statement reference: https://github.com/sidagarwal04/click-a-thon-2026/tree/main/SonyLiv
(Full text is revealed to all teams at 12:00 pm IST on 1 August — nothing here is pre-built against it.)

## Status

Active build.

The **ingestion layer** is in [`ingest/`](ingest/README.md): a Go pipeline on the
ClickHouse native connector that loads the two supplied CSVs, plus an event
generator that drives a synthetic stream at a target concurrency through the same
write path. Design record and measurements in
[`ingest/ARCHITECTURE.md`](ingest/ARCHITECTURE.md). Verified end to end against
the supplied extract: 905,558 events, 0 rejected, 0 unjoinable content ids, and a
byte-identical replay that adds no rows.

Events land in two tables: `events_raw` keeps every source row verbatim and is
never deduplicated in place, so the duplicate rate stays measurable and a
normalization rule stays correctable; `events_clean` is a
`ReplacingMergeTree` derivation carrying the normalized values, read through an
`argMax` view that is correct whether or not a merge has run. Verified against
the live Cloud service: 905,558 landed, 901,348 after dedup, 4,210 collapsed
(4,209 exact duplicates plus one conflicting-payload row that remains
recoverable from `events_raw` and is already gone from `events_clean`), 0
rejected, 0 unjoinable content ids, 11.01 MiB on disk across both tables at
35.8x compression.

The independent evidence-backed ClickHouse design, executable SQL,
semantic policy, and embedded verification are in [`solution/`](solution/README.md).
It was created during the 24-hour hack window and intentionally leaves the
concurrent `docs/` / `prototype/` draft untouched for end-of-session comparison.

Current verified reference result for the supplied source hashes and policy
`sonyliv-active-v1`: 31,947 active intervals; exact hot-hour peak 2,305 and
time-weighted average 855.578199 sessions. These are correctness-oracle outputs,
not ClickHouse Cloud latency claims. The executable late-pause test also proves
that touched-session corrections converge exactly with a fresh full-source
rebuild and reject duplicate publication retries.

The canonical time contract is UTC end to end: source transport timestamps are
Unix epoch milliseconds, ClickHouse stores `DateTime64(3,'UTC')`, service days
are UTC, and any `Asia/Kolkata` rendering happens only in the consuming query or
UI.

## Team

| Role | Name | GitHub |
|---|---|---|
| Team Captain | | |
| Member | | |
| Member | | |
| Member | | |

Team name (as registered): _TBD_
Track: _TBD — confirmed once the problem statement is revealed_

## Stack requirements (from the Participant Handbook)

- **ClickHouse** as the primary database (mandatory).
- At least one of the following, meaningfully integrated (not superficial):
  - [ClickStack](https://github.com/ClickHouse/clickstack) — open source observability stack
  - [Langfuse](https://github.com/langfuse/langfuse) — open source LLM observability & analytics
  - [LibreChat](https://github.com/danny-avila/LibreChat) — open source AI chat platform

All three are integrated, over the same serving layer. Architecture, setup and the
verification script are in [`deploy/README.md`](deploy/README.md).

- **ClickStack** — dashboards over the concurrency serving layer, including a
  benchmark-answers board and a per-dimension drop alert.
- **LibreChat** — self-hosted on the EC2 box, hosting an analyst that answers
  viewing-trend questions. It reaches ClickHouse only through
  [`sonyliv-mcp`](ingest/cmd/sonyliv-mcp/README.md), an MCP server that connects as a
  restricted user granted `SELECT` on eight aggregate objects and nothing carrying
  `user_id`. Asked for a person, it refuses — and the refusal is enforced by the grant,
  not by the prompt.
- **Langfuse** — prompt management is the versioned source of truth for the analyst's
  system prompt, rendered into the deployment at deploy time and failing closed if it
  cannot be read. Model calls route through a LiteLLM sidecar, so every turn, tool call,
  latency and token count is traced.

## Submission checklist

Required components, per §2.3 / §5.2 of the Participant Handbook:

- [ ] Working project in this public GitHub repo, MIT-licensed
- [ ] Solution summary (plain text, ≤500 words)
- [ ] Demo video link (YouTube or Loom, ≤5 minutes)
- [ ] Pitch deck (PDF, ≤15 slides, ≤20 MB)
- [ ] Project title (≤100 chars) and optional tagline (≤160 chars)

Deadlines:
- Submission portal opens: 12:00 pm IST, Sat 1 Aug 2026
- Code freeze (portal closes automatically, no extensions): 12:00 pm IST, Sun 2 Aug 2026

Repo must stay **public** from submission through the end of the judging period.

## License

[MIT](LICENSE) — required by the event rules (Apache 2.0 or another ClickHouse-pre-approved permissive license would also qualify).
