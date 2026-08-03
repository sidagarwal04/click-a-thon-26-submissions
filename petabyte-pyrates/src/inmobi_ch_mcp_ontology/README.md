# inmobi_ch_mcp_ontology — Lambda MCP

Streamable HTTP MCP server on AWS Lambda. Serves the InMobi RCA glossary ontology to ClickHouse Cloud Agents.

| Field | Value |
|-------|-------|
| Server name | `inmobi-ch-mcp-ontology` |
| Tool | `get_ontology` |
| Source | `config/glossary_ontology.yaml` (bundled as `ontology.json` at deploy time) |
| Auth | Bearer token (`MCP_AUTH_TOKEN`) |

## Deploy

Prerequisites: AWS CLI with profile `clickathon` (or set `AWS_PROFILE`), IAM role `inmobi-rca-ch-bridge-role`.

```bash
./src/inmobi_ch_mcp_ontology/deploy.sh
```

Outputs:

- Function URL → `src/inmobi_ch_mcp_ontology/.mcp_url`
- Bearer token → `src/inmobi_ch_mcp_ontology/.mcp_auth_token`

## Attach in ClickHouse Agent Builder

1. **MCP servers** → Add server
2. **URL** — contents of `.mcp_url`
3. **Auth** — Bearer token from `.mcp_auth_token`

The agent must call `get_ontology` before any ClickHouse SELECT. Glossary source: `config/glossary_ontology.yaml`.

## Redeploy after ontology changes

Edit `config/glossary_ontology.yaml`, then rerun `deploy.sh`. The script rebuilds `ontology.json` from the YAML via `inmobi_ontology.loader`.

## Files

| File | Purpose |
|------|---------|
| `handler.py` | Lambda MCP handler (stdlib only) |
| `deploy.sh` | Package and deploy to Lambda + Function URL |
| `ontology.json` | Generated bundle (gitignored) |
| `.mcp_url` / `.mcp_auth_token` | Deploy outputs (gitignored) |
