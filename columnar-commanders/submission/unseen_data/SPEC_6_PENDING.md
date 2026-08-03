# The 6th / unseen spec — pending

Not run yet. Per the brief, this spec is released to all teams simultaneously
in the final hours of the event — it does not exist in this repository or on
this machine before that point, so it cannot be rehearsed on directly (only
generalized to, by never special-casing any of the 5 known specs in agent
code — see `REQUIREMENTS.md`'s "biggest risk" callout).

This file documents the **exact runbook** that will be executed the instant
it drops, so the only variable at that moment is the spec itself, not the
process.

## Runbook (unattended, one command)

```bash
make instrument SPEC=inputs/specs/06_<name> SAMPLE_PCT=15
```

This one command:

1. Loads the spec + its sample events (`load_spec()` handles a directory
   with `spec.md` + an events file, a single `spec.md`, or `--brief`/`--events`
   passed directly if the drop isn't shaped like the other 5).
2. Runs the full Instrumentation Agent pipeline: profile → design (LLM) →
   lint → validate (scratch database) → repair loop if needed → execute DDL
   against the real database → reconcile any pre-existing tables → load every
   row.
3. **Automatically** chains into the Context Agent (`_notify_context`) and
   then the Analytics Agent (`refresh_after_schema_change` → `_run_analytics`)
   — no second command needed. This is the same auto-chain exercised by all
   5 known-spec runs in [`../TRACES.md`](../TRACES.md).
4. Prints the generated DDL, the executed statements, load results, and the
   `run_id`/`trace_id` to run for verification.

## What gets captured, immediately after

```bash
# The schema + insight summary + trace, all from the one run_id printed above:
python -m prism_ch context-log                     # context version + diff that the new table produced
LANGFUSE_HOST=http://localhost:3000 python -m prism_ch analyze > spec_6_insights.txt  # full PM-facing summary, if not already auto-triggered output is enough
```

The auto-triggered Analytics run from step 3 above already produces the
required "insight summary for spec 6" as part of the same trace as the
instrumentation run — re-running `analyze` separately is a belt-and-braces
verification, not a required second step.

## Freeze protocol (per `REQUIREMENTS.md` §5)

- No code edits between the spec drop and this command running — the trace
  must be clean evidence that the frozen pipeline (the one described in
  [`ARCHITECTURE.md`](../../ARCHITECTURE.md) and exercised by the 5 known
  specs in [`../TRACES.md`](../TRACES.md)) handled a spec it had never seen.
- This has already been rehearsed 5 times over, on 5 different real specs,
  producing 5 different schemas with no spec-specific code path — that
  repetition **is** the dress rehearsal.

## Once the spec lands, replace this file's contents with

- The generated DDL (link to a `submission/ddl/06_<name>.log`, same format
  as the other 5).
- The insight summary (product-audience text, not a database audience —
  same format as [`../insights/`](../insights/)).
- The `run_id`/`trace_id` and a line in [`../TRACES.md`](../TRACES.md)'s
  table, matching the existing 5-spec row format.
