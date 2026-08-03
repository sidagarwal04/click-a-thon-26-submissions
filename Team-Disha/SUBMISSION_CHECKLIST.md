# Submission checklist — Team-Disha (InMobi)

Use before opening PR `[Submission] Team-Disha`.

## Common (root README)

- [x] Team folder `Team-Disha/`
- [x] Project source code (`source_code/`)
- [x] `README.md` with sections from template
- [x] Hosted demo link + judge login in README (`https://metric-mind.ashiqabdulkhader.dev/login`)
- [x] Architecture (`Architecture.md` — expanded from development: data model, `rca_*`, Compose, tools, research) + `design-notes/RESEARCH.md`
- [x] **Demo video** 2–3 min link in README (Google Drive)
- [ ] **`pitch-deck.pdf`** in this folder
- [ ] PR against submissions repo titled `[Submission] Team-Disha`

## InMobi-specific

- [x] Pipeline: detect → drill-down → diagnosis (ClickHouse-native `eda.rca_*`)
- [x] Architecture explains CH does the analysis; LLM narrates
- [x] LibreChat + Langfuse + ClickStack called out
- [x] LLM provider noted (Azure OpenAI)
- [x] How to run (in `README.md`) + `verify_unseen_rca.py`
- [x] **Unseen incident bundle** under `unseen_incident/` (diagnosis + numbers + trace)
- [x] Langfuse offline JSON (`unseen_incident/langfuse/`) + public URLs
- [x] ClickStack evidence (`evidence/clickstack/` screenshots + `otel` table summary)

## Hygiene

- [x] No `.env` secrets in the tree (only `.env.example`)
- [x] No large parquet dumps committed
- [x] Team member list complete in README
- [x] Fork of `click-a-thon-26-submissions` used for the PR
