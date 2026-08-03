# Unseen / graded incident bundles — 404Duos

System-generated exports (not hand-written). Each file includes diagnosis + citations, segments, ruled-out, seasonality, waterfall, counterfactual, hypotheses, immutable `trace[]`, and evidence hash.

## Bundles

| Alert | Investigation | Pct | Culprit theme | Export | Evidence hash |
|-------|---------------|-----|---------------|--------|---------------|
| `b82a676d-5e80-f884-0f1a-78a4b44f9b07` | `inv-b82a676d-…` | −50.3% | Requests | [`inv-b82a676d-5e80-f884-0f1a-78a4b44f9b07-export.json`](./inv-b82a676d-5e80-f884-0f1a-78a4b44f9b07-export.json) | `37466a08…727c` |
| `b6b57556-9484-d041-33a5-5bab862dfe4d` | `inv-b6b57556-…` | −12.5% | eCPM | [`inv-b6b57556-9484-d041-33a5-5bab862dfe4d-export.json`](./inv-b6b57556-9484-d041-33a5-5bab862dfe4d-export.json) | `0daed60d…7e88` |
| `70527923-64b5-67a0-a51e-ffa45e4e240c` | `inv-70527923-…` | −52.1% | Revenue residual | [`inv-70527923-64b5-67a0-a51e-ffa45e4e240c-export.json`](./inv-70527923-64b5-67a0-a51e-ffa45e4e240c-export.json) | `527807f4…` |

## Reproduce

```bash
API_URL=https://insightiq-production-be0e.up.railway.app \
  node scripts/export-investigation.mjs --list

API_URL=https://insightiq-production-be0e.up.railway.app \
  node scripts/export-investigation.mjs \
  --alertId=<UUID> \
  --out=./evidence/unseen
```

Or: hosted UI → Alerts → open alert → **Export**.
