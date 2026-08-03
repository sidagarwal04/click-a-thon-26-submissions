# RUN.md — env vars, connection, and the one command that runs the pipeline

This is the judge-facing "how do I run it" doc. For a full from-scratch,
copy-paste machine setup (installing Docker, creating a ClickHouse Cloud
trial, getting an LLM key) see **[SETUP.md](SETUP.md)** instead — this file
assumes that's already done and gets straight to running the agents.

---

## 1. Environment variables

Every variable lives in `.env` (`cp .env.example .env`, then fill in). The
ones that matter for running the pipeline:

| Variable | Purpose |
| --- | --- |
| `CLICKHOUSE_TARGET` | `cloud` — the only supported target; there is no local ClickHouse container |
| `CLICKHOUSE_HOST` / `PORT` / `USER` / `PASSWORD` / `DB` | The ClickHouse Cloud service the agents read and write |
| `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / `gemini-3.5-flash-lite` by default — see [ARCHITECTURE.md §4](ARCHITECTURE.md#4-storage-tracing-and-llm-choices) for why |
| `GOOGLE_API_KEY` (or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) | Matching whichever `LLM_PROVIDER` is set |
| `LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Only needed if you also want tracing (`make up-obs`) — see §4 below |

Full list, with comments on every variable: [`.env.example`](.env.example).

## 2. This submission's ClickHouse Cloud connection

> **For judges:** the `CLICKHOUSE_HOST` / `USER` / `PASSWORD` for the exact
> Cloud service this submission's data lives in is shared out-of-band (event
> Slack / submission form), **not committed here** — real credentials never
> belong in a public git repo. Paste them into `.env` under the
> `CLICKHOUSE_*` keys before running anything below.
>
> Don't have our credentials? Any fresh ClickHouse Cloud trial works too —
> the pipeline is target-agnostic; see [SETUP.md §3](SETUP.md#3-create-a-clickhouse-cloud-service-free)
> to provision your own in under two minutes. You'll start from an empty
> database instead of the 8 pre-loaded event tables, but every agent
> behaves identically.

## 3. One command to run the pipeline end to end

```bash
make up && make context && make instrument SPEC=inputs/specs/01_express_checkout && make analyze
```

What that one line does, in order:

1. `make up` — starts the app container (builds it on first run).
2. `make context` — Context Agent: bootstraps/refreshes the business context
   layer from `base_context.md` against the live schema, publishes a new
   version, and (per the architecture) **automatically triggers an Analytics
   Agent run against the version it just published** — so context freshness
   and the auto-chain are already exercised by this step alone.
3. `make instrument SPEC=inputs/specs/01_express_checkout` — Instrumentation
   Agent: turns one of the 5 known specs into designed, validated, executed
   DDL, loads the sample events, and **automatically re-triggers the same
   Context → Analytics chain** now that a new table exists — this is the
   context-freshness proof in action, not a separate demo path.
4. `make analyze` — Analytics Agent: an explicit run that prints a full,
   product-facing insight report straight to the terminal (see below), so
   you don't have to open the browser UI or Langfuse to see output.

Swap `SPEC=inputs/specs/01_express_checkout` for any of the other four
(`02_group_family`, `03_status_sharing`, `04_abandoned_checkout_recovery`,
`05_instant_forex`), or for the 6th/unseen spec directory once it drops —
the command does not change.

### What you'll see

`make analyze`'s output looks like:

```
run_id: <run-id>   trace: <trace-id>
context v<N>   <k> queries

<2-3 sentence PM-facing summary>

1. [device] <headline>   (confidence 0.78)
   <detail — the numbers behind it>
   why: <causal hypothesis, grounded in the known-issues log or a metric definition>
   context: <K3 iOS OTP autofill, ...>
   next: <what to do about it>
...
```

Every `run_id`/`trace_id` printed is looked up the same way in Langfuse —
see [TRACES.md](submission/TRACES.md) for this submission's actual run
history.

## 4. Optional: turn on tracing to see the reasoning, not just the output

```bash
make up-obs && make langfuse-ready && make langfuse
```

Opens Langfuse at `http://localhost:3000` (auto-logged-in,
`dev@prism.local` / `prismdev123`). Every command in §3 above emits one root
trace with one span per agent step, each carrying its `why` — see
[ARCHITECTURE.md §4](ARCHITECTURE.md#4-storage-tracing-and-llm-choices)
for exactly what's wired in and how.

## 5. Everything else

| Doc | What's in it |
| --- | --- |
| [SETUP.md](SETUP.md) | From a brand-new machine to a running UI, copy-paste, with checkpoints |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The 3 agents, how they hand off, storage/tracing/LLM choices, per-agent flowcharts |
| [README.md](README.md) | Full command reference (`make help`), configuration, troubleshooting |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Requirement-by-requirement tracker against the brief |
| [submission/](submission/) | The graded artifacts: generated DDL, insight reports, context changelog, trace index |
