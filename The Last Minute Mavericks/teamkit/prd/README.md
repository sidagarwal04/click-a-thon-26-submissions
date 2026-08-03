# PRDs — per-person marching orders

Each person owns one PRD and one directory, and builds against the **frozen contract**
(`teamkit/CONTRACTS.md`) so all three tracks move at once with no waiting.

| PRD | Owner | Directory | One-line mission |
|---|---|---|---|
| [PRD-A](PRD-A-clickhouse.md) | A | `sql/` | ClickHouse is the engine — load, cube, detect, decompose, attribute, verify, all in SQL |
| [PRD-B](PRD-B-agent.md) | B | `agent/` + `run_incident.py` | Turn SQL results into a traced, **unhallucinatable** multi-incident diagnosis |
| [PRD-C](PRD-C-integrations-ui.md) | C | `integrations/` + `ui/` | Make it auditable (Langfuse), observable (ClickStack), demoable (Streamlit); then deliverables |

## How the three tracks decouple (why we don't block each other)
```
A: data → cube → detection → reproduce the 4 incidents ──┐  (produces real numbers)
                                                          ▼
B: run_incident + evidence + validator + narrate ── develops against the GOLDEN FIXTURE ──► swaps in A's SQL
                                                          ▲
C: Langfuse + ClickStack + Streamlit ── also develops against the FIXTURE ────────────────┘
```
The **golden fixture** (`contracts/fixtures/example_bundle.json`, real INC-C numbers) is the
seam: B and C build the entire agent + UI against it with **zero dependency on A**, then flip to
A's live SQL at integration. Freeze the contract at hour 1; after that, code to the shapes.

## The one shared acceptance test (everyone grades against this)
The seen data has four planted incidents (`docs/DATA.md`). Nothing is "done" until the full
pipeline reproduces them — with the numbers, and correctly subordinating the dilution artifacts:

| Incident | Truth to reproduce | Verdict |
|---|---|---|
| **INC-A** Jun 21 | requests −43.5%, **no responsible segment** | `GLOBAL_UNLOCALIZED` |
| **INC-B** Jun 19–22 | eCPM, `category=finance` −34.5% | `LOCALIZED_1D` |
| **INC-C** Jun 23–25 | fill_rate, `os_version=Android 15` −44.8% | `LOCALIZED_1D` |
| **INC-D** Jun 28–30 | fill_rate, `os=iOS 18.1 × region=APAC` −50.7% (neither parent alone) | `LOCALIZED_2D` |
| dilution guard | `device_model=iPhone 14` is −5.91%, an artifact — must be **subordinated, not reported** | `DILUTION_ARTIFACT` |

If the system names iPhone 14 as a cause, or fabricates a culprit for INC-A, it fails — regardless
of how good the demo looks.

## Rules that apply to everyone
- Edit only your directory. Contract changes: announce → `CONTRACTS.md` → `DECISIONS.md` → code.
- Small PRs, pull `main` first (`bash teamkit/sync.sh`), one owner per dir — see `CONTRIBUTING.md`.
- The LLM never sees a raw row and never does arithmetic. Every narrated number → a `query_id`.
- Timeboxes in each PRD are guidance for a 12-hour build; ship the acceptance test early, polish later.
