# ClickHouse MCP (Model Context Protocol) Setup Guide

This repository is configured to support **Model Context Protocol (MCP)** for ClickHouse DB connections. MCP allows AI assistants (Antigravity, Cursor, Claude Desktop, VS Code MCP extensions) and LlamaIndex agents to query, inspect schemas, and analyze tables directly from ClickHouse.

---

## 1. Quick Overview

- **Official Package Installed**: `mcp-clickhouse` (Python FastMCP implementation for ClickHouse).
- **Configuration Files Created**:
  - Global Antigravity Config: `~/.gemini/config/mcp_config.json`
  - Workspace Repository Config: `.mcp.json`
  - Environment Template: `.env.example`

---


## 2. Configuration Options

### Option A: Local / Docker ClickHouse Container
When running ClickHouse locally via Docker or local installation:

```json
{
  "mcpServers": {
    "clickhouse": {
      "command": "mcp-clickhouse",
      "args": [],
      "env": {
        "CLICKHOUSE_HOST": "localhost",
        "CLICKHOUSE_PORT": "8123",
        "CLICKHOUSE_USER": "default",
        "CLICKHOUSE_PASSWORD": "",
        "CLICKHOUSE_SECURE": "false"
      }
    }
  }
}
```

### Option B: ClickHouse Cloud
When connecting to ClickHouse Cloud (`https://<instance>.clickhouse.cloud:8443`):

```json
{
  "mcpServers": {
    "clickhouse": {
      "command": "mcp-clickhouse",
      "args": [],
      "env": {
        "CLICKHOUSE_HOST": "your-instance.clickhouse.cloud",
        "CLICKHOUSE_PORT": "8443",
        "CLICKHOUSE_USER": "default",
        "CLICKHOUSE_PASSWORD": "YOUR_CLOUD_PASSWORD",
        "CLICKHOUSE_SECURE": "true"
      }
    }
  }
}
```

---

## 3. Supported MCP Tools

Once the MCP server connects to ClickHouse, the following standard tools become available to AI agents:

1. `list_databases`: Lists all accessible ClickHouse databases.
2. `list_tables`: Lists tables within a target database.
3. `describe_table`: Returns table column schemas, data types, and primary keys.
4. `run_query`: Executes read-only SQL `SELECT` queries against ClickHouse.

---

## 4. Verification & Testing

### Testing the MCP Server Executable
Run the following in terminal to confirm the executable is available:

```bash
mcp-clickhouse --help
```

### Testing ClickHouse DB Connection with Python
```bash
python3 -c "
import os
import clickhouse_connect

client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
    username=os.getenv('CLICKHOUSE_USER', 'default'),
    password=os.getenv('CLICKHOUSE_PASSWORD', '')
)
print('Connected to ClickHouse! Version:', client.server_version)
"
```

---

## 5. Integrating with LlamaIndex & Fastify Backend

The Fastify backend (`src/routes/v1/chat.ts` & `src/clickClient.ts`) uses `@clickhouse/client` and can leverage MCP tools for interactive chat sessions.

Set up `.env` from `.env.example`:

```bash
cp .env.example .env
```

Fill in your `CLICKHOUSE_HOST`, `CLICKHOUSE_PASSWORD`, and `DEEPSEEK_API_KEY` to start using the backend!
