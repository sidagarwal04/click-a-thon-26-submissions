AeroOps/AdOps Root-Cause Analyst — InMobi Click-a-thon 2026
=============================================================


PROBLEM STATEMENT
------------------
Ad revenue anomalies (unexpected drops/spikes) happen across a huge number
of ad-tech dimensions (country, device, campaign type, publisher, etc.),
and finding *which* segment caused a given anomaly manually is slow —
we needed a tool that detects the anomaly, ranks every dimension by how
much it contributed, and explains the "why" in plain English, with every
number traceable back to a real query (no guessing).

HOW WE SOLVED IT — STEP BY STEP
---------------------------------

1. Connected to ClickHouse Cloud and explored the raw dataset
   Used the ClickHouse MCP server to inspect the existing `ganesh` schema
   (hourly metrics, per-dimension aggregates, a materialized-view baseline
   of median/MAD per day-of-week + hour, and a flagged-anomalies table).
   Found and fixed a real double-counting bug in how the `vertical`
   dimension's contribution percentage was computed.

2. Pivoted to a richer pipeline: the `py` database
   Mid-hackathon, migrated the whole backend from `ganesh` to a new `py`
   pipeline: 9 dimensions instead of 11, 5 time granularities (we expose
   1h and 6h), and a rolling weekday/weekend + hour-of-day baseline
   instead of an exact-day-of-week one. Rewrote every ClickHouse query in
   the backend to match `py`'s own materialized views exactly, so the
   dashboard's numbers never disagree with the pipeline's own detection.

3. Built the FastAPI backend (backend/app/)
   - db.py: all ClickHouse access (detection, day trend, per-dimension
     contribution ranking, dimension trend series + anomaly points).
   - narrate.py: a deterministic (no LLM) diagnosis-text generator — every
     sentence reads a number ClickHouse already computed.
   - Found and fixed a sign bug: when every segment in a dimension moves
     the same direction, the raw contribution ratio can come out positive
     even though the segment itself fell. Fixed with a "signed
     concentration" helper applied everywhere a % is shown.
   - Fixed a thread-safety bug where a single shared ClickHouse client
     crashed under FastAPI's thread pool; switched to one client per thread.

4. Built the dashboard frontend (frontend/, vanilla JS + Chart.js)
   - A multi-line trend chart (one line per segment) with a Category and
     Y-axis metric dropdown, calendar date range, and a 1h/6h toggle.
     Anomaly points are colored by severity (yellow -> orange -> dark red)
     based on z-score, not just flagged/not-flagged.
   - Clicking a point loads a full incident view: KPIs, the deterministic
     diagnosis, a full-day actual-vs-expected trend, a compact factor
     decomposition (volume / fill rate / price), and a radar chart showing
     all 9 dimensions' top-segment impact at once (click a radar point to
     drill into that dimension).
   - A promoted Drill-down panel (its own dimension dropdown, synced with
     the trend chart) showing the top segments for whichever category is
     selected, with a bar chart and table.
   - Iterated repeatedly based on live feedback: removed a redundant
     "contribution strip" once the Drill-down panel replaced it, fixed a
     null-value bug that was silently blanking the entire drill-down table,
     and made "Overall" the default landing view.

5. Added AI narration on top of the deterministic numbers
   Added two on-demand "Generate AI summary" features (drill-down table,
   and full incident) that send Claude Haiku *only* the exact numbers
   already fetched and rendered on screen, with a strict instruction to
   never invent a figure or a root cause — so the AI text can never drift
   from what's on the chart.

6. Integrated LibreChat for open-ended follow-up questions
   - Auto-login: a shared demo LibreChat account is logged into
     server-to-server from the dashboard's backend, and the resulting
     session cookie is forwarded to the browser — since cookies are
     scoped by hostname (not port), this lets the embedded LibreChat
     iframe skip its own login screen entirely.
   - Wired up a standalone ClickHouse MCP server (its own Docker
     container, since LibreChat's own container has no C compiler to
     build one in-process) so LibreChat can query the `py` database
     directly during a chat.
   - Set Claude Sonnet 5 as LibreChat's hard default model.

RESULT
------
A live dashboard where every chart, table, and AI summary traces back to
a real ClickHouse query against the `py` pipeline — click an anomaly,
see what happened, why, which segment is most responsible, and optionally
ask an LLM (constrained to the same numbers) or LibreChat (with live
database access) for more detail.
