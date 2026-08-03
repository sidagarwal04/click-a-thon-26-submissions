# Clickathon Bengaluru — Atlys Track

Hackathon repo. Read the reference docs before making changes.

## Event & Rules

- `HACKATHON_RULES.md` — clickathon rules, timings, judging criteria.

## Problem Statement (Atlys)

- `Atlys/README_START_HERE.md` — entry point, orientation.
- `Atlys/PROBLEM_STATEMENT.md` — full problem brief.
- `Atlys/base_context.md` — product/user context for Atlys.
- `Atlys/specs/` — five candidate feature specs:
  - `01_express_checkout/`
  - `02_group_family/`
  - `03_status_sharing/`
  - `04_abandoned_checkout_recovery/`
  - `05_instant_forex/`

## Data

- `Atlys/data/ddl.sql` — table schemas.
- `Atlys/data/load.sh` — loader script.
- `Atlys/data/instrumentation_notes.md` — event tracking notes.
- `Atlys/data/*.parquet` — event data (application_started, auth_completed,
  destination_card_clicked, document_uploaded, landing_page_scrolled,
  pay_now_clicked, purchase_completed, search_typed).

## Our Take

- `ATLYS_hackathon_in_human_language.md` — plain-English summary of our usecase.
- `ATLYS_Hackathon_technical_requirements.md` — technical requirements draft.

## Working Rules

- Ground every solution in the parquet data under `Atlys/data/`.
- Cross-check ideas against the chosen spec in `Atlys/specs/`.
- Update `ATLYS_*` docs when the direction changes.
- Do not commit unless explicitly asked.
