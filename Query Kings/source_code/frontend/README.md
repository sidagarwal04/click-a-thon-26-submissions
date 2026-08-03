# Frontend / Visualization (Schema Kings · Atlys)

Judge-facing report for the problem statement viz layer.

## Demo flow (recommended)

```bash
cd backend
pnpm cli serve
# open http://127.0.0.1:8787
```

1. Type a PM question in the **Ask** box on the page
2. Wait for the analytics agent
3. Page reloads with the answer + Langfuse link
4. Scroll for features / context / recent insights

Same brain as `pnpm cli ask` — just linked to the HTML.

## Offline / CLI still works

```bash
pnpm cli report              # overview HTML
pnpm cli report <job_id>     # one ask/run page
pnpm cli ask "…"             # also auto-writes HTML
```

Opening `frontend/dist/report.html` as a file works for reading, but the ask box needs `cli serve`.

## Problem statement coverage

| Required              | Where                                  |
| --------------------- | -------------------------------------- |
| Schema over time      | Section 1 · features (+ SQL expander)  |
| Insights + confidence | Ask page / section 3                   |
| Context changelog     | Section 2                              |
| Tracing               | Langfuse links (`LANGFUSE_PROJECT_ID`) |
