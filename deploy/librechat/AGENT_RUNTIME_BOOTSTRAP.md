# LibreChat investigation runtime bootstrap

The investigation UI invokes one persisted LibreChat workflow agent through
`POST /api/agents/v1/chat/completions`. It does not attach function tools or
run an agent loop locally. This document is the required production setup
before deploying the UI configuration.

## 1. Create the runtime tools in LibreChat

Create a server-side MCP server named `atlys-investigation`. Its tools must run
in the LibreChat API container and have access to ClickHouse credentials there.
Do not point these tools at the investigation UI process.

Expose the following narrow operations:

- `clickhouse_execute`: permit scoped `CREATE TABLE`, `SELECT`,
  `DESCRIBE`, `EXPLAIN`, and `CREATE MATERIALIZED VIEW` statements against the
  investigation namespace. Return bounded result sets and query IDs.
- `investigation_record`: write the validated tables, materialized views,
  aggregations, and findings hand-off to the investigations table.

The MCP server must never expose blob download/upload, source-file content, or
bulk inserts. A separate programmatic ingestion service owns source transfer,
parsing, batching, and reconciliation and writes a compact manifest for the
agent. The MCP server must not accept arbitrary host paths, credentials, or
unrestricted SQL.

## 2. Create persisted agents and graph

Use LibreChat's Agent Builder while signed in as the service user. Create three
persisted agents, all using `gpt-5.6-luna`:

1. `Instrumentation Agent`: attach every `atlys-investigation` tool and the
   instrumentation system prompt. Give it an outgoing agent edge to Analytics.
2. `Analytics Agent`: attach read/query and `investigation_record` tools. Give
   it an outgoing edge to Context.
3. `Context Agent`: attach read/query, `investigation_record`, and the
   business-context filesystem tool. It returns the final hand-off.

The instrumentation prompt must require this order:

`read programmatic profile -> create base tables -> programmatic ingest ->`
`query base tables -> create/validate MV targets -> record hand-off -> analytics -> context`.

The workflow agent must never report success with an empty `tables` array. If
base-table creation or ingestion cannot be verified, it must return a blocker
and must not call the downstream agents.

Copy the persisted ID of the Instrumentation Agent (`agent_...`). A preset name
such as `instrumentation-agent` is not an agent ID and will result in a 404.

## 3. Grant API access

Create a LibreChat API key for the same service user. Ensure its role has
`remoteAgents.use` and permission to use all three persisted agents. Verify it
before UI deployment:

```bash
curl -fsS \
  -H "Authorization: Bearer $LIBRECHAT_AGENTS_API_KEY" \
  https://clickathon26librechat.nannan.in/api/agents/v1/models
```

The response must contain the Instrumentation Agent's `agent_...` ID. An OpenAI
provider key will not authenticate this endpoint.

## 4. Configure and deploy the UI

Set these ignored `deploy/ui/.env` values:

```dotenv
LIBRECHAT_AGENTS_API_URL=https://clickathon26librechat.nannan.in/api/agents/v1/chat/completions
LIBRECHAT_AGENTS_API_KEY=<LibreChat API key>
LIBRECHAT_INSTRUMENTATION_AGENT_ID=agent_<instrumentation-agent-id>
```

Then run `./deploy/ui/deploy.sh`. The deployment script deliberately no longer
copies `OPENAI_API_KEY` into the UI runner; model-provider credentials remain
inside LibreChat.
