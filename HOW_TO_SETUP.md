# How to set up and run

This repository runs an investigation workflow with these components:

```text
Browser / API client
        |
        v
Investigations UI ──> Azure Blob Storage
        |
        v
Instrumentation runner ──> LibreChat Agent Chain
                              |
                              v
                     Instrumentation Agent
                              |
                              v
                     Analytics Agent
                       |          |
                       v          v
             Aggregate Analyst  Evidence Reviewer
                                    |
                                    v
                              Context Agent
                                    |
                                    v
                              Finalizer Agent
                                    |
                                    v
                         PM-facing investigation report

ClickStack/OTel and Langfuse observe the LibreChat runtime; ClickHouse stores
the generated data objects, workflow state, artifacts, and context history.
```

The UI accepts files and exposes status. The runner executes the long-lived
LibreChat request. The Instrumentation Agent decides the schema and invokes
bounded MCP tools; bulk NDJSON ingestion is streamed programmatically by the
UI runtime, not by the agent.

## 1. Prerequisites

On the deployment VM install:

- Docker Engine and the Docker Compose plugin
- Nginx and Certbot
- Git, OpenSSH server, `rsync`, and `curl`

The VM needs network access to:

- OpenAI
- ClickHouse Cloud
- Azure Blob Storage
- the configured Langfuse endpoint, if tracing is enabled

Expose only ports `80` and `443` publicly. LibreChat and the UI bind to
loopback-only host ports (`8080` and `8090` respectively).

## 2. Configure LibreChat

Clone a reviewed, immutable LibreChat release into `/opt/LibreChat` on the VM.
Do not use a moving branch such as `main`.

Create `/opt/LibreChat/.env` from the LibreChat production environment example
for the pinned release. Set at least:

```dotenv
OPENAI_API_KEY=<provider key for gpt-5.6-luna>
CLICKHOUSE_USER=<instrumentation ClickHouse user>
CLICKHOUSE_PASSWORD=<instrumentation ClickHouse password>
CLICKHOUSE_ENDPOINT=https://<service>.clickhouse.cloud:8443
CLICKHOUSE_CLOUD_ORGANIZATION_ID=<organization UUID>
CLICKSTACK_SERVICE_ID=<Managed ClickStack service UUID>
CLICKHOUSE_CLOUD_API_KEY_ID=<Service Admin or Org Admin API key ID>
CLICKHOUSE_CLOUD_API_KEY_SECRET=<API key secret>
CLICKSTACK_APP_URL=<ClickStack/HyperDX application base URL>
INVESTIGATION_RUNTIME_TOKEN=<random 32-byte hex token>
AGENT_MODEL=gpt-5.6-luna
```

Generate all LibreChat application secrets with `openssl rand`; protect the
file with `chmod 600 /opt/LibreChat/.env`. Never commit it.

On the deployment workstation, create ignored `deploy/librechat/.env`:

```dotenv
SSH_TARGET=<user>@<vm-host-or-ip>
SSH_PASSWORD=<ssh-password-or-use-key-auth>
LIBRECHAT_REF=<pinned-librechat-tag-or-commit>
AGENT_MODEL=gpt-5.6-luna
```

Deploy LibreChat, its MCP configuration, Context Store, and agent files:

```bash
./deploy/librechat/deploy.sh
```

The deployment creates/recreates `context-store-mcp`, LibreChat API, and the
internal LibreChat Nginx proxy. It also installs the host Nginx site for
`clickathon26librechat.nannan.in`.

## 3. Bootstrap persisted LibreChat agents

The checked-in `context.md` files are source control. LibreChat persists agent
instructions separately, so refresh the persisted agents after changing any
agent prompt or MCP-tool assignment.

On the VM, obtain the service user ID once, then run:

```bash
cd /opt/LibreChat
docker compose -f deploy-compose.yml -f deploy-compose.production.yml exec -T \
  -e BOOTSTRAP_USER_ID=<librechat-service-user-id> api \
  node /app/agents/bootstrap-investigation-agents.cjs
```

The command prints the persisted IDs for Instrumentation, Analytics, Aggregate
Analyst, Evidence Reviewer, Context, and Finalizer. Store the Instrumentation
and Analytics IDs in the UI configuration. API-key creation is opt-in; store
any machine key only in private environment files, never in Git or logs.

## 4. Configure and deploy the Investigations UI and runner

Create ignored `deploy/ui/.env` on the deployment workstation:

```dotenv
SSH_TARGET=<user>@<vm-host-or-ip>
SSH_PASSWORD=<ssh-password-or-use-key-auth>
REMOTE_DIR=/opt/clickathon-investigations

AZURE_STORAGE_CONNECTION_STRING=<azure-storage-connection-string>
AZURE_CONTAINER_NAME=investigations

LIBRECHAT_AGENTS_API_URL=https://clickathon26librechat.nannan.in/api/agents/v1/chat/completions
LIBRECHAT_AGENTS_API_KEY=<LibreChat machine API key>
LIBRECHAT_INSTRUMENTATION_AGENT_ID=agent_<persisted-instrumentation-id>
LIBRECHAT_ANALYTICS_AGENT_ID=agent_<persisted-analytics-id>

MAX_UPLOAD_BYTES=268435456
SAS_TTL_MINUTES=30
POLL_INTERVAL_SECONDS=2
```

Deploy:

```bash
./deploy/ui/deploy.sh
```

The script copies the UI, refreshes the private VM UI environment from
LibreChat/Azure settings, installs the UI Nginx site, and starts both services:

- `investigations-ui`: upload, status, history, and internal tool API
- `instrumentation-runner`: polls queued investigations and calls LibreChat

Verify on the VM:

```bash
cd /opt/clickathon-investigations/deploy/ui
docker compose ps
curl -fsS http://127.0.0.1:8090/health
```

## 5. Submit and monitor an investigation

Inputs must be named exactly `events.ndjson` and `spec.md`.

```bash
curl -fsS -X POST https://clickathon26.nannan.in/api/investigations \
  -F events=@/absolute/path/events.ndjson \
  -F spec=@/absolute/path/spec.md \
  -F feature_key=express-checkout
```

The response contains an investigation ID and status URL. Poll it:

```bash
curl -fsS https://clickathon26.nannan.in/api/investigations/<investigation-id>
```

Or open:

```text
https://clickathon26.nannan.in/investigations/<investigation-id>
```

The runner first calls Instrumentation. Once the instrumentation state is
persisted, it sends the exact handoff to the persisted Analytics Agent. The
Analytics chain runs Aggregate Analyst and Evidence Reviewer, then hands its
internal result to Context. Context updates schema/context history and hands
the enriched result to Finalizer. Finalizer publishes the PM-facing envelope
through the investigation-data tool; only then is the investigation complete.

The UI status page exposes each stage (`instrumentation-agent`,
`analytics-agent`, `context-agent`, and `finalizer-agent`).

## 6. Access schema and context history

Schema history:

```text
GET /api/schema-history/<feature_key>
GET /api/schema-versions/<schema_version_id>/diff
```

Context semantic diff:

```text
GET /api/context-versions/<version_number>/diff
```

All are available through `https://clickathon26.nannan.in`.

## 7. Routine operations

### View logs

```bash
cd /opt/clickathon-investigations/deploy/ui
docker compose logs -f investigations-ui instrumentation-runner

cd /opt/LibreChat
docker compose -f deploy-compose.yml -f deploy-compose.production.yml logs -f api context-store-mcp analytics-runner-mcp otel-collector
```

### Deploy a prompt-only change

```bash
./deploy/librechat/deploy.sh
# Then rerun the persisted-agent bootstrap command from section 3.
```

### Deploy UI/runtime changes

```bash
./deploy/ui/deploy.sh
```

### Check reverse proxies

```bash
sudo nginx -t
curl -fsS http://127.0.0.1:8080/health   # LibreChat internal proxy
curl -fsS http://127.0.0.1:8090/health   # UI
```

## Security rules

- Keep `.env` files local/private and rotate credentials deliberately.
- Do not expose ClickHouse, MongoDB, or LibreChat API ports directly.
- Do not give users Azure SAS URLs, ClickHouse credentials, or runtime tokens.
- Use separate ClickHouse users for instrumentation, analytics, UI persistence,
  and telemetry when moving beyond a demo environment.
- Back up the LibreChat data volumes and ClickHouse state tables before upgrades.
