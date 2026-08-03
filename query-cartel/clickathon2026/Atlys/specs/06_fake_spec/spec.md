# Feature spec — Fake "6th spec" (hardening fixture, M8)

Deliberately awkward shapes to prove the pipeline is content-driven and
degrades gracefully: nested objects, array fields, nulls, mixed types, and a
**missing user_id** on some rows.

## What it does
A demo widget. Nothing real — this is the team's own sixth spec for hardening
against the Day-2 unseen spec.

## User actions (raw events emitted)
- `widget_viewed` — the widget renders (nested `meta`: `source`, `variant`)
- `widget_toggled` — the user toggles it (`enabled` bool)
- `widget_configured` — config saved (`retry_count`, `tags` array)
- `widget_purchased` — paid (`price` float, `units` int)

Envelope as usual, but `user_id` is **absent** on some rows.
