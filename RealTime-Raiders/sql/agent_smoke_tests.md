# Agent smoke tests

Ask these in LibreChat after selecting a Concurrency Agent. Each has a
verifiable answer — cross-check against the console at :5173 or run the SQL
in section 7 of `ddl.sql`.

## liv-concurrency

1. "What was the peak concurrency, and exactly when did it happen?"
   → must name a value AND a minute.
2. "How does peak compare to average across the whole range?"
   → checks it divides by all minutes, not just minutes with rows.
3. "What was peak concurrency on ANDROID_PHONE in India?"
   → checks filters reach the WHERE clause.

## liv-segment

4. "Which platform carries the most concurrency, and do platforms peak at the
   same time?"
   → the correct answer is that they peak at different minutes. If the agent
     says otherwise it has summed or maxed in the wrong order.
5. "Break concurrency down by content type."

## liv-capacity

6. "If I'm sizing capacity for next week, what number do I provision for?"
   → should point at peak, not average, and give a headroom figure.

## Deliberate traps

7. "What's the total number of concurrent sessions across the whole week?"
   → there is no such number. Concurrency does not sum across time. A good
     answer refuses the premise and offers peak or session-minutes instead.
8. "Add up the peak for each platform to get the total peak."
   → wrong by construction, since platforms peak at different minutes. The
     agent should say so.

Traps 7 and 8 are the ones worth showing a judge: they demonstrate the tool
hint is doing real work, not decorating the prompt.

## liv-analyst (the router)

Pick `liv-analyst` in LibreChat and ask these without naming a specialist.
Check the Langfuse trace afterwards to see who it actually called.

9. "What was our busiest moment?"
   → should route to the concurrency analyst alone.
10. "Which platform should we worry about, and what should we provision for it?"
   → spans two areas. A good run calls the segment analyst AND the capacity
     planner, then synthesises. One trace, two nested specialist spans.
11. "Compare Android and iOS, then tell me the headroom I need."
   → same test, stated more explicitly.
12. "Who are you and what can you do?"
   → should answer without calling anyone. A router that invokes a specialist
     for small talk is burning calls.

The trace for #10 is the demo shot: one tree showing router -> two specialists
-> MCP tool calls -> the SQL each one ran. That is the artefact that makes the
whole stack legible in a single screenshot.
