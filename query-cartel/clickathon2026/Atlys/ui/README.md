# Atlys React UI

React + Vite front end for the Atlys Copilot demo. Talks to FastAPI (`/api/*`); chat is
proxied to LibreChat via `POST /api/proxy/chat`.

See [`../SETUP.md`](../SETUP.md) §1.6 for the full local + Docker workflow.

```bash
npm ci
npm run dev      # http://localhost:5173 (proxies /api → :8000)
npm run build    # → ../service/static/ (served by FastAPI at /)
npm run lint
npm run preview
```

In Docker, `Dockerfile.service` Stage 1 runs the production build; compose serves the UI at
`http://localhost:8000`.
