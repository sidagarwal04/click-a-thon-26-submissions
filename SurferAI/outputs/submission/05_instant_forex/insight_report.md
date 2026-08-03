# PM Insight Report — Instant Forex Orders (`05_instant_forex`)

**Diagnostic Question:** What is the attach rate and revenue impact of Instant Forex across different visa applicant destinations?  
**Target Table:** `None`  
**Evaluation Timestamp:** 2026-08-02T03:58:09.815683+00:00  
**Public Langfuse Trace URL:** https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/51e71909154adb878463a51c75265e99  
**Calibrated Confidence Score:** None

---

## Executive Summary & Diagnostic Breakdown

### I can't answer that from the instrumented tables

**What you asked for:** attach_rate

**Why it isn't derivable:** The instant_forex_add table tracks the event of adding the service but lacks the 'value' column for revenue and the total application volume (denominator) required to calculate an attach rate.

- value column (required to calculate revenue impact)
- total application counts (the table only contains 'add' events, so the denominator for an attach rate is missing)

**What I could answer instead:**
- conversion through to purchase_completed, cut by device, geo, destination
- drop-off at any funnel stage present in the event stream
- payment latency at the confirmation step

No query was run and no number was estimated.
🔍 Trace: https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/51e71909154adb878463a51c75265e99

---

### ClickHouse Query Execution & Signal Derivation
- **Resolved Table Engine:** `None` (Classification: `raw`)
- **Queries Executed:** 0 ClickHouse Cloud SQL statements
- **Anomalies / Signals Derived:** 0
- **Context Governance:** Synchronized with living `chDB` metadata and registered table semantics.

---
*Generated autonomously by Atlys Product Analyst Agent (CUJ 2) via ClickHouse Cloud.*
