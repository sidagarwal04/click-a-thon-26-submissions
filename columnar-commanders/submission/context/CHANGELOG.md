# Context-freshness proof: before/after changelog

The requirement: show the context layer updating when a new table is added.
Below is the real before/after across all six context versions produced this
session — v1 is the bootstrap from `base_context.md` against the original 8
tables; v2–v6 are each one instrumentation run's automatic schema refresh
(`refresh_after_schema_change`), one per known spec, with **zero manual
intervention** between "table created" and "context updated."

## Version history (from `context_versions`, real rows)

| Version | Source | Summary | Entries |
| --- | --- | --- | --- |
| 1 | `bootstrap` | bootstrap of atlys | 322 |
| 2 | `instrumentation` | schema refresh: express_checkout_selected, express_checkout_shown, express_payment_confirmed, otp_entered, saved_method_used | 401 |
| 3 | `instrumentation` | schema refresh: group_started, group_submitted, traveller_added, traveller_removed | 471 |
| 4 | `instrumentation` | schema refresh: channel_selected, link_generated, link_opened, recipient_cta_clicked, share_clicked | 538 |
| 5 | `instrumentation` | schema refresh: abandonment_detected, reconverted, reminder_cta_clicked, reminder_opened, reminder_sent, resumed_at_step | 634 |
| 6 | `instrumentation` | schema refresh: amount_entered, currency_selected, forex_added_to_cart, forex_offer_shown, forex_purchased | 720 |

Each row happened as an automatic side effect of `make instrument SPEC=...` —
see [`../TRACES.md`](../TRACES.md) for the run/trace id that produced each one.

## Before (v1) vs. after (v6)

| Entry kind | v1 (before any of the 5 specs) | v6 (after all 5) | Change |
| --- | --- | --- | --- |
| `table` | 17 | 42 | **+25** |
| `column` | 276 | 648 | **+372** |
| `relationship` | 3 | 4 | +1 |
| `metric` | 7 | 7 | 0 |
| `entity` | 8 | 8 | 0 |
| `definition` | 3 | 3 | 0 |
| `known_issue` | 8 | 8 | 0 |

`diff_snapshots(v1, v6)`: **+398 added, -0 removed, ~2 changed** (full JSON:
[`after_and_diff.json`](after_and_diff.json)).

## The 25 new tables the Analytics Agent could see immediately after

Every one of these appeared in the context layer the moment its
instrumentation run finished — no separate "refresh context" step, no lag:

```
prism_abandonment_detected      prism_forex_offer_shown
prism_amount_entered            prism_forex_purchased
prism_channel_selected          prism_group_started
prism_currency_selected         prism_group_submitted
prism_express_checkout_selected prism_link_generated
prism_express_checkout_shown    prism_link_opened
prism_express_payment_confirmed prism_otp_entered
prism_forex_added_to_cart       prism_recipient_cta_clicked
                                 prism_reconverted
                                 prism_reminder_cta_clicked
                                 prism_reminder_opened
                                 prism_reminder_sent
                                 prism_resumed_at_step
                                 prism_saved_method_used
                                 prism_share_clicked
                                 prism_traveller_added
                                 prism_traveller_removed
```

## Proof the Analytics Agent actually reads the newest version, not a stale one

`AnalyticsAgent.discover()` reads `store.load()` with no version argument —
`ContextStore.load()` defaults to `MAX(version)`. Every analytics trace in
[`../TRACES.md`](../TRACES.md) logs the context version it used as part of
its `discover` step; the 5 spec-instrumentation runs' auto-triggered analytics
each read the version *that same run just published* (v2 read v2, v3 read
v3, ...), confirmed in each trace's `discover` span
(`context_version` field) — see the exported JSONs under
[`../traces/`](../traces/).

## Raw data behind this page

- [`before_v1.json`](before_v1.json) — full v1 snapshot (entries by kind, issues)
- [`after_and_diff.json`](after_and_diff.json) — full v6 snapshot, version history, and the v1→v6 diff
- [`00_bootstrap_run.log`](00_bootstrap_run.log) — the `make context` run that produced v1, including the Context Agent's own contradiction/gap detection over the seeded `base_context.md` (4 issues found — the base context is intentionally imperfect, per the brief, and finding its flaws is itself part of the deliverable)
