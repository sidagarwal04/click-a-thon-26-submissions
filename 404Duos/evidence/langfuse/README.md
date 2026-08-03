# Langfuse evidence (InMobi / Click-a-thon)

## What’s here

| File | Purpose |
|------|---------|
| `1785643387197-lf-events-export-….csv` | Bulk export of live chat/narrate observations |
| `SHARE_LINKS.md` | Public session share URL |

Langfuse does not offer a project-wide public link — use the CSV plus shared session/trace URLs. See [SHARE_LINKS.md](./SHARE_LINKS.md).

## Wiring (in product code)

- `apps/api/src/instrumentation.js` — OTEL → Langfuse  
- `apps/api/src/index.js` — chat / investigate / narrate spans  
- `apps/api/.env.example` — `LANGFUSE_*` (secrets redacted)

## Live check

```bash
curl -s https://insightiq-production-be0e.up.railway.app/health
# langfuse: true, langfuseBaseUrl: https://jp.cloud.langfuse.com
```
