# Atlys track — What to submit at code freeze

Your submission is scored on the event's standard 6-criteria rubric (ClickHouse &
OSS Stack 25% · Problem Fit 20% · Technical Implementation 20% · Innovation 20% · 
Scalability & Impact 10% · Presentation 5%). The items below are the **evidence the
judges need** to score those criteria for this track. Missing evidence can't be
scored.

Track problem statement:
[PROBLEM_STATEMENT.md](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/Atlys/PROBLEM_STATEMENT.md)
— *"From feature spec to insight: agents that instrument, analyze, and explain."*

## 1. Code + how to run it

The three agents (Instrumentation, Analytics, Context) + tracing + visualization (optional),
with a `RUN.md`: env vars, your ClickHouse Cloud connection, and one command to run
the pipeline end to end.

## 2. Architecture (1–2 pager explanation and/or a diagram)

- The three agents and how they hand off
- **Where your context layer is stored** (file / ClickHouse table / vector store) and why
- How Langfuse tracing is wired; additionally if you integrated ClickStack / LibreChat - tell us how
(see [what evidence to include](README.md#using-clickstack-langfuse-or-librechat) for each tool)
- LLM provider(s) used and why



## 3. Unseen Data/Surprise Round folder (the graded outputs)

- **Generated DDL** for the 5 known feature specs **and** the 6th spec
- Your **Analytics Agent's insight report** over the 8 existing tables (an autonomous run)
- Your **context layer** + a **before/after changelog** showing it updated when a new
table was added (the context-freshness proof)
- The **6th-spec bundle**: generated schema + insight summary (written by the agent for the product  
audience) + the trace



## 4. Langfuse trace links

Shared or exported traces for each agent run. **The 6th-spec run's trace is**  
**mandatory** for that output.

---



## Standard probe set (run these and include the outputs)

So every team's Analytics Agent is exercised the same way, run these four prompts
against the existing tables and include the outputs (and their traces) in your
artifacts. They are intentionally open-ended — surfacing what matters is your
system's job.

1. "Analyze the existing funnel and surface the most important issues, with the why."
2. "Where are we losing conversions, and for which segments (device / geo / destination)?"
3. "Are there any regressions or trends over the last quarter?"
4. "Is anything in the base context wrong, stale, or self-contradictory?"

