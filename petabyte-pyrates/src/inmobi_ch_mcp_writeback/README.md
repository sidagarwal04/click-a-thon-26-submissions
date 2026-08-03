# inmobi_ch_mcp_writeback — Lambda MCP

Streamable HTTP MCP server on AWS Lambda. Closes anomaly investigations by writing back to `gold.metric_anomalies` in ClickHouse Cloud.

| Field | Value |
|-------|-------|
| Server name | `inmobi-ch-mcp-writeback` |
| Tool | `close_anomaly_investigation` |
| Auth | Bearer token (`MCP_AUTH_TOKEN`) |

## Tool: close_anomaly_investigation

Updates a row in `gold.metric_anomalies`:

- `status` → `closed`
- `disposition` → `confirmed` \| `false_positive` \| `inconclusive`
- `rca_description` — plain-language summary
- `evidence_json` — reproducible queries and findings
- `investigated_at` — timestamp

## Deploy

1. Set ClickHouse credentials in repo root `.env`:

```bash
CLICKHOUSE_HOST=your-service.clickhouse.cloud
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-password
```

2. Deploy:

```bash
./src/inmobi_ch_mcp_writeback/deploy.sh
```

Outputs:

- Function URL → `src/inmobi_ch_mcp_writeback/.mcp_url`
- Bearer token → `src/inmobi_ch_mcp_writeback/.mcp_auth_token`

## Attach in ClickHouse Agent Builder

1. **MCP servers** → Add server
2. **URL** — contents of `.mcp_url`
3. **Auth** — Bearer token from `.mcp_auth_token`

## Files

| File | Purpose |
|------|---------|
| `handler.py` | Lambda MCP handler + ClickHouse HTTP client |
| `deploy.sh` | Package and deploy to Lambda + Function URL |
| `.mcp_url` / `.mcp_auth_token` | Deploy outputs (gitignored) |
