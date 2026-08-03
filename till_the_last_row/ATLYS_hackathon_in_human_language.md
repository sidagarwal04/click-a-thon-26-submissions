# Atlys Problem — Explained for the Team

## The story (why this problem exists)

Atlys is a digital visa platform. Every time they ship a new product feature — say "Express Checkout" or "Group Applications" — someone has to:

1. **Figure out what to track** (which events, what fields)
2. **Design database tables** for those events in ClickHouse
3. **Write queries** to analyze how the feature is performing
4. **Write up insights** for the product manager to act on

Today this whole loop is **manual and slow**. A PM writes a tracking doc → engineers create tables weeks later → analysts write queries → by the time the insight arrives, the team has moved on to the next feature.

**Our job: automate the entire loop with AI agents.**

---

## What we're building (in plain English)

Imagine a system where a PM drops a 1-page description of a new feature into a folder, and out the other end comes:
- A production-ready database table, already created in ClickHouse
- A written insight report: *"On iOS in India, Express Checkout is converting 15% worse than Android — likely tied to the known OTP autofill bug"*
- A trace showing exactly how the AI figured that out

That's the deliverable. Three AI agents working together on top of ClickHouse.

---

## The 3 agents (think of them as 3 teammates)

### Agent 1 — The Instrumentation Engineer
- **Reads**: a feature spec (1-page markdown) + some sample raw JSON events
- **Does**: designs an optimal ClickHouse table for those events — picks column types, ordering keys, partitioning
- **Creates**: the actual `CREATE TABLE` in our ClickHouse database
- **Analogy**: the data engineer who normally takes 2 weeks to set up tracking

### Agent 2 — The Data Analyst
- **Reads**: the new tables (from Agent 1) + the old 8 tables + business context
- **Does**: writes SQL, runs queries, spots trends and anomalies, compares segments (iOS vs Android, India vs UAE, etc.)
- **Writes**: a PM-friendly insight summary — not charts, actual sentences with the *why*
- **Analogy**: the senior data analyst who explains what's actually happening in the numbers

### Agent 3 — The Context Keeper
- **Maintains**: a living document of "what our business means" — metric definitions, entity relationships, known bugs
- **Does**: when a new table appears, updates the context. Spots contradictions in the existing docs. Feeds fresh context to Agent 2 so it doesn't work from outdated info
- **Analogy**: the tech lead who keeps the team's mental model of the business current

---

## The data we have to work with

**8 existing tables** representing Atlys's conversion funnel:

```
User taps destination → starts application → uploads passport → pays
```

Plus 4 supporting tables (search, scroll, login, pay-now-click). About 2.5 million rows total. **This data is intentionally messy** — real production is messy (null fields, weird OS values, duplicate flags). Our agents need to handle it.

**5 feature specs** for new features to instrument:
1. Express Checkout (one-tap payment)
2. Group / Family Applications
3. Visa Status Sharing (viral referrals)
4. Abandoned Checkout Recovery (nudges)
5. Instant Forex Add-on (upsell)

Each has a description + a JSON sample of what raw events look like. **No table schema provided** — that's Agent 1's whole job.

**A "base context" document** that describes the business. ⚠️ **It's deliberately imperfect** — has planted contradictions. Agent 3 needs to spot them.

---

## The twist — the unseen 6th feature

In the final hours of the hackathon, a **secret 6th feature spec** drops. Every team gets the same input at the same time. Our pipeline has to process it end-to-end automatically and produce:
- A new table
- Insights on it
- A trace proving the AI did it (not us hand-writing it)

**This is where the win is decided.** Teams that hardcode logic for the 5 known specs will fall apart on the 6th. We have to build something *general*.

---

## The rules

1. **ClickHouse is the database** — everything lives there, all queries run there
2. **Langfuse for tracing** — every AI decision must be logged and inspectable. **No trace = no credit.**
3. **LLM cost matters** — never dump raw rows into the LLM. Let ClickHouse do the math, LLM just narrates the result
4. **Anything goes for the code** — any language, any agent framework, any LLM provider

---

## How judges score us

| What they look at     | What they want to see                                                            |
| --------------------- | -------------------------------------------------------------------------------- |
| **Schema quality**    | Smart ordering keys, right partitioning, materialized views that earn their keep |
| **Insight quality**   | Would a PM actually act on this? Does it explain the *why*?                      |
| **Context freshness** | Does the analyst agent use updated context, or stale info?                       |
| **Traceability**      | Can a judge open Langfuse and follow the reasoning chain?                        |
| **The 6th spec**      | Weighted heavily. Same input for everyone → directly comparable results          |

---

## Our biggest risks

1. **Token burn** — if we're not careful, LLM costs explode. Rule: **ClickHouse computes, LLM narrates**
2. **Fragile agents** — if we tune for the 5 known specs, the 6th one will break us
3. **Stale context** — Agent 2 must always pull the latest context from Agent 3, not a snapshot
4. **Weak traces** — every LLM call, every SQL query must be in Langfuse. This is a hard gate.

---

## In one sentence

> We're building an AI team of 3 agents — an engineer who creates tables, an analyst who writes insights, and a context keeper who keeps them both grounded — all traced, all running on ClickHouse, ready to handle a surprise feature at the end.
