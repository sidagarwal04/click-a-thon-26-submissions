# Click-a-thon 2026

Problem packages for the **ClickHouse Click-a-thon 2026** — a 24-hour hackathon where every solution is built on [ClickHouse](https://clickhouse.com) as the primary datastore and analytical engine. All data in this repo is **synthetic**.

## The problems

Pick a track, read its start-here guide, and build.

### PROBLEM STATEMENT 1 (NOT OURS)

### PROBLEM STATEMENT 2 (NOT OURS)

### [Atlys](Atlys/) — From feature spec to insight: agents that instrument, analyze, and explain

Every new product feature needs instrumentation, schema design, and analysis — today that loop is manual and slow. Build a system of three agents on ClickHouse that collapses it: one turns a feature spec into production-ready table schemas, one analyzes the data and writes insights a product manager would act on, and one keeps the business context layer fresh as tables are added — all fully traced.

| | |
|---|---|
| Start here | [Atlys/README_START_HERE.md](Atlys/README_START_HERE.md) |
| Problem statement | [Atlys/PROBLEM_STATEMENT.md](Atlys/PROBLEM_STATEMENT.md) |
| Base context | [Atlys/base_context.md](Atlys/base_context.md) |
| Data | [Atlys/data/](Atlys/data/) — 8 raw event tables (4-step conversion funnel + 4 supporting), ~2.5M rows |
| Feature specs | [Atlys/specs/](Atlys/specs/) — 5 specs (1-page brief + raw NDJSON) |

## Ground rules (both tracks)

- **ClickHouse is the primary datastore and analytical engine.** Load the data into your team's own ClickHouse Cloud service, provisioned with your event credits.
- **Meaningfully integrate at least one of** [ClickStack](https://clickhouse.com/use-cases/observability) (observability), [Langfuse](https://langfuse.com) (LLM observability & analytics), or [LibreChat](https://www.librechat.ai) (conversational interface). Superficial inclusion won't count.
- **Build for the unseen data.** A sealed evaluation dataset for each track is released to all teams simultaneously in the final hours of the hackathon. Your submission must include your system's output on it, with evidence it ran through your pipeline.

## Getting the data

Large data files are stored with [Git LFS](https://git-lfs.com). To clone with the real files instead of pointer stubs:

```bash
git lfs install
git clone https://github.com/sidagarwal04/click-a-thon-2026.git
```

Already cloned without LFS? Run `git lfs install && git lfs pull` inside the repo.

---

Good luck — build something extraordinary.