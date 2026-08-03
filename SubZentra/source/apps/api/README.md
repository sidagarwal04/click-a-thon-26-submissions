# ZentraOS API

FastAPI composition root for the ZentraOS modular monolith. It owns HTTP and
lifespan concerns while delegating investigation rules to the domain and
application packages.

Phase 1A provides health and authenticated context endpoints plus the
deterministic investigation trust loop:

- `GET /health/live`
- `GET /health/ready`
- `GET /v1/context`
- `POST /v1/investigations`
- `GET /v1/investigations/{investigation_id}`
- `POST /v1/investigations/{investigation_id}/approvals/{approval_id}/decision`

Run it through Nx:

```bash
npm exec -- nx serve api
```

The API requires provider identity bindings for authenticated requests. It
resolves tenant identity internally and never accepts a caller-supplied tenant
identifier.
