# Probe Outputs — Analytics Agent over the 8 existing tables

Run each prompt below in a **new conversation** with the **Analytics Agent** (interactive
mode), then paste the agent's PM-ready output and its Langfuse trace link into the matching
file. These exercise the Analytics Agent the same way for every team (per the guidelines).

Also include one **autonomous run** — a single open request to analyze the existing funnel
end-to-end — in `00_autonomous_8table_report.md`.

| File | Prompt | Status |
| --- | --- | --- |
| `00_autonomous_8table_report.md` | "Analyze the 8 existing Atlys tables and give me the most important product insights." | ⬜ not yet run |
| `01_funnel_issues.md` | "Analyze the existing funnel and surface the most important issues, with the why." | ⬜ not yet run |
| `02_conversion_segments.md` | "Where are we losing conversions, and for which segments (device / geo / destination)?" | ✅ done |
| `03_regressions_trends.md` | "Are there any regressions or trends over the last quarter?" | ⬜ not yet run |
| `04_context_contradictions.md` | "Is anything in the base context wrong, stale, or self-contradictory?" | ⬜ not yet run |

Only `02_conversion_segments.md` currently exists in this folder — run the remaining four
prompts and add their output files before this item is submission-complete.

Paste trace links here **and** in [`agent_traces/`](../agent_traces/).
