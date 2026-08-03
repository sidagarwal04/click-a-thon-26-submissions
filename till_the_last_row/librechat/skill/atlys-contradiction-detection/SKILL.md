---
name: atlys-contradiction-detection
description: Surface conflicts and gaps in the Atlys context (base_context.md is deliberately imperfect) as explicit OKF contradiction concepts — the dual "conversion" definition, the ETA column mismatch, os=NULL envelope gaps, the legacy sort key smell, and non-computable post-purchase metrics. Invoke on every context run after writing concept docs. Full checklist in references/atlys-context-taxonomy.md.
---

# Skill: Contradiction Detection

The base context is known to be imperfect — with **planted** contradictions. Surfacing them
explicitly is rewarded; silently resolving them is a failure. For each finding, write a
`/contradictions/{slug}.md` concept (`type: contradiction`) stating:

- the **claim**,
- the **conflicting claim / evidence**,
- **where** each came from (file + section, or live schema),
- a **recommended resolution** — do **not** silently pick a winner.

Cross-link each contradiction from the concept(s) it affects.

## Known planted contradictions to always check (non-exhaustive)

1. **Dual "conversion" definition.** `base_context.md` §4 headline (*purchases ÷ sessions*) vs
   the §4 note (*purchase_completed users ÷ application_started users*). These differ. Note that
   "sessions" is not a table (approximate via `app_session_id`).
2. **ETA column mismatch.** `base_context.md` §2 says `application_started` carries
   `visa_issuance_eta_days` (integer); the real DDL has **no such column** — it has
   `eta_shown Nullable(String)`. Use `eta_shown`; flag the discrepancy.
3. **`os = NULL` while `device_type = 'android'`** — an envelope data gap (346 such rows
   observed).
4. **Legacy `ORDER BY (id, timestamp, user_id)`** on the raw tables — queries filter by
   time/segment, never by `id`. Flag it as a schema smell the Instrumentation Agent should NOT
   copy (the new design uses `payload.event`-first keys).
5. **On-time delivery / `visa_issuance_eta_days`** — referenced as a metric but declared
   post-purchase and **not computable** from the funnel tables → a gap, not a metric.
6. **Passport pass-rate column naming** — `is_crossed_failed_attempt_threshold` matches the DDL,
   but wording elsewhere may lag; always resolve to the DDL column.

> Run the **full contradiction/gap checklist** in
> [references/atlys-context-taxonomy.md](references/atlys-context-taxonomy.md) — it is the
> authoritative list and may extend beyond the above.

## Rules

- **Always** surface contradictions as explicit `contradiction` concepts; never silently resolve
  a conflict in `base_context.md`.
- State provenance precisely (which file/section, or live schema).
- Recommend a resolution but leave the final choice explicit — the Analytics Agent chooses per
  question, citing the reason.
