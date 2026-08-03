# AgentHouse

## Track
Atlys

## Project
FeatureMage by AgentHouse — From feature spec to insight: agents that instrument, analyze, and explain.

## Team Members
- Sathvik
- Thushar
- Anil
- Harsha

## What it does
A runtime instrumentation + analytics agent system with a context layer that delivers product insights in minutes instead of weeks. It addresses three problems: manual instrumentation/schema design taking too long, lost context between features/engineering/analytics, and delayed dev cycles causing missed customer opportunities.

Given a feature spec, the **Instrumentation Agent** builds the DDL for new data (using spec + events), updates schema metadata, creates ClickHouse tables + activity MVs, and publishes a new Context version. The **Visualization / Conversation Agent** fetches the latest context, plans queries, and returns charts/insights. The **Context Agent** keeps a versioned business catalog in Postgres so analytics never reads a stale snapshot.

## Hosted Demo
[http://3.109.41.83:3080/](http://3.109.41.83:3080/) — LibreChat product UI

## Demo Video
[https://www.loom.com/share/e8b3bcd1cf3447709c1ce4618a633346](https://www.loom.com/share/e8b3bcd1cf3447709c1ce4618a633346)

## Pitch deck
[`Clickathon.pdf`](./Clickathon.pdf)

## Architecture
See [`Architecture.md`](./Architecture.md) and [`image.png`](./image.png).

Summary:
- **Instrumentation** (Gemini) → ClickHouse tables + Postgres `meta_*` → Context publish
- **Context** → versioned catalog in **Postgres** (`context_versions` / `context_items`)
- **Conversation / Visualization** (Claude by default) → latest context + ClickHouse aggregates
- **Langfuse** traces agent steps; **LibreChat** is the chat UI; ClickHouse holds event facts

How to run: [`RUN.md`](./RUN.md) · env template: [`.env.example`](./.env.example)  
Source code: [`src/`](./src/) (latest `main` from the AgentHouse repo). Run: [`RUN.md`](./RUN.md) / [`run.sh`](./run.sh).

## How we built it
- **ClickHouse**: per-event MergeTree tables + Materialized Views into a Single Activity Schema (`activity_events`); funnel queries via `windowFunnel`
- **Agents**: Agno workflows on FastAPI (AgentOS)
- **Context**: Postgres versioned catalog (copy-forward + deltas on each instrument publish)
- **Frontend**: LibreChat
- **Observability**: Langfuse
- **LLMs**: Gemini (instrumentation), Claude (conversation / SQL)

## How to run it
See [`RUN.md`](./RUN.md).

---

## Atlys evidence map

| Guideline item | Location | Status |
|----------------|----------|--------|
| §1 Code + `RUN.md` | `src/`, `RUN.md`, `run.sh`, `src/.env.example` | Done |
| §2 Architecture | `Architecture.md`, `image.png` | Done |
| §3 Generated DDL (01–05 + 6th) | `unseen_data/generated_ddl_all_specs.txt` | Done |
| §3 Context layer + before/after | `unseen_data/context_layer.json`, `context_before_after_*` | Done (`v5`→`v6` coupon) |
| §3 Analytics report (8 tables) | `analytics/insight_report_existing_tables.md` | Placeholder |
| §3 6th-spec insight + trace | `unseen_data/sixth_spec_insight_summary.md`, `traces/` | Placeholder — **trace mandatory** |
| §4 Langfuse traces | `traces/` + links below | TODO |
| Standard probes 1–4 | `analytics/probes/probe_0{1-4}.md` | Placeholders |

### Langfuse share links (fill before freeze)

- Instrumentation `unseen_data`: 
- Analytics 6th-spec insight: 
- Analytics existing-tables report: 
- Probe 1–4: 
