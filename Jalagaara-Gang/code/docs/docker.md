# Running the whole stack with Docker

One command brings up the stack as separate containers. **The RCA ClickHouse stays external**
(Cloud, via `.env`) — everything else runs locally. Langfuse is self-hosted **v3**, which runs
its own infra (postgres + clickhouse + redis + minio), separate from the RCA Cloud ClickHouse.

| Service        | Container(s)                                   | URL                    | Notes |
|----------------|------------------------------------------------|------------------------|-------|
| Dashboard      | `frontend` (nginx)                             | http://localhost:5173  | The React UI |
| Backend        | `backend` (FastAPI)                            | http://localhost:8000  | `/health`, `/investigate`, `/v1/chat/completions` |
| Langfuse       | `langfuse-web` + `langfuse-worker` + `-postgres` / `-clickhouse` / `-redis` / `-minio` | http://localhost:3000 | Self-hosted **v3**; keys pre-seeded |
| LibreChat      | `api` + `mongodb`                              | http://localhost:3080  | Conversational RCA UI |
| RCA ClickHouse | — (external Cloud)                             | your `CLICKHOUSE_HOST` | Not a container |

## Run it

```bash
cp .env.example .env
# Fill CLICKHOUSE_* with your Cloud service creds. Langfuse dev keys are already filled in.
# (Optional) add AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY to enable Bedrock narration.

docker compose up --build
```

First run pulls the Langfuse v3 images (its ClickHouse + MinIO are ~large) and builds the two
local images (backend, frontend) — budget a few minutes, and expect `langfuse-web` to take an
extra moment after its ClickHouse/Postgres migrations before `:3000` answers. Compose auto-merges
`docker-compose.override.yml`, which mounts `librechat.yaml`.

Then open **http://localhost:5173**.

Stop with `Ctrl-C`; `docker compose down` to remove containers (add `-v` to wipe the Langfuse
postgres/clickhouse/minio + Mongo volumes).

> **Backend needs the v4 Langfuse SDK.** The tracing code uses `propagate_attributes` /
> `start_as_current_observation` (Langfuse SDK v3/v4). `backend/Dockerfile` installs `langfuse>=3`
> for this reason — an older SDK ImportErrors and 500s `/investigate`.

## How the wiring works

- **Backend → ClickHouse**: `CLICKHOUSE_*` from `.env`. If unset/unreachable the backend still
  boots and serves **fixture mode** (`/health` reports `engine: fixture`).
- **Backend → Langfuse**: `LANGFUSE_HOST` is overridden to `http://langfuse-web:3000` inside the
  network. The `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` in `.env` are the same keys
  `LANGFUSE_INIT_*` seeds into `langfuse-web` — so tracing works with no manual UI setup.
- **Frontend → Backend / LibreChat**: Vite bakes `http://localhost:8000` and
  `http://localhost:3080` at build time (host-browser URLs, since the browser runs on your
  machine). To change them, rebuild: `docker compose build frontend`.
- **LibreChat → Backend**: `librechat.yaml` points at `http://host.docker.internal:8000/v1`,
  i.e. the backend's published host port. `extra_hosts` makes that name resolve in the container.

## Narration (AWS Bedrock) in containers

The narrator authenticates via the AWS credential chain. A host venv reads `~/.aws`
automatically; the **container cannot see it**. To enable prose in Docker, put
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (and `AWS_SESSION_TOKEN` if using SSO) in `.env`.
Without them, investigations still run end-to-end — only the narrative is skipped.

## Trace links

Langfuse trace URLs on a bundle are built from `LANGFUSE_HOST`, which is `langfuse-web:3000`
inside the network — that hostname won't open from your browser. The traces are still recorded;
find them in the Langfuse UI at **http://localhost:3000** (log in as `admin@clickathon.local`
/ `LANGFUSE_INIT_USER_PASSWORD` — **don't sign up**, that creates a separate empty org).

## Gotchas

- **`.env` is required** — compose reads Langfuse keys from it. `cp .env.example .env` first.
- **Ports 3000 / 3080 / 5173 / 8000 must be free.** Change the left side of a `ports:` mapping
  in `docker-compose.yml` if one is taken.
- **LibreChat first visit**: registration is open (`ALLOW_REGISTRATION=true`) — create a local
  account, then pick **RCA Analyst** in the model dropdown.
- The `CREDS_KEY` / dev secrets in the compose file are for a throwaway local stack. Regenerate
  before exposing any of this beyond localhost.
