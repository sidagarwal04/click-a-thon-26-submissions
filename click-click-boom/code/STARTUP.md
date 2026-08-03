# LibreChat Local Setup with ClickHouse Cloud

Minimal guide to run LibreChat locally with ClickHouse Cloud MCP integration.

---

## Prerequisites

- **Docker Desktop** - Must be running
- **Git** - For cloning the repository
- **ClickHouse Cloud credentials** - Host, username, and password

---

## Setup Steps

### 1. Clone and Setup Environment

```bash
git clone https://github.com/danny-avila/LibreChat.git
cd LibreChat
cp .env.example .env
```

### 2. Create Docker Compose Override

Create `docker-compose.override.yml`:

```yaml
services:
  api:
    volumes:
      - type: bind
        source: ./librechat.yaml
        target: /app/librechat.yaml

  mcp-clickhouse:
    image: mcp/clickhouse
    container_name: mcp-clickhouse
    ports:
      - 8001:8000
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - CLICKHOUSE_HOST=your-host.clickhouse.cloud
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=your_password
      - CLICKHOUSE_MCP_SERVER_TRANSPORT=sse
      - CLICKHOUSE_MCP_BIND_HOST=0.0.0.0
```

**Replace these values** with your ClickHouse Cloud credentials:
- `CLICKHOUSE_HOST` - Your ClickHouse Cloud host
- `CLICKHOUSE_USER` - Your username (usually `default`)
- `CLICKHOUSE_PASSWORD` - Your password

### 3. Create LibreChat Configuration

Create `librechat.yaml`:

```yaml
version: 1.3.13

cache: true

interface:
  mcpServers:
    use: true

mcpSettings:
  allowedDomains:
    - 'host.docker.internal'
    - 'localhost'
  allowedAddresses:
    - 'host.docker.internal:8001'
    - '127.0.0.1:8001'

mcpServers:
  clickhouse-cloud:
    type: sse
    url: http://host.docker.internal:8001/sse
    timeout: 60000
```

### 4. Start LibreChat

```bash
docker compose up -d
```

First startup takes several minutes to download images. Subsequent starts are faster.

### 5. Access LibreChat

Open browser: **http://localhost:3080**

- Register first account (becomes admin)
- Configure API keys in Settings (OpenAI, Anthropic, etc.)

### 6. Use ClickHouse MCP

1. Start a new conversation
2. Click the MCP tools icon
3. Select "clickhouse-cloud"
4. Query your ClickHouse data via chat

---

## Common Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f

# View MCP logs
docker compose logs mcp-clickhouse

# Restart
docker compose restart
```

---

## Troubleshooting

**Port 3080 in use?**
Change port in `docker-compose.override.yml`:
```yaml
services:
  api:
    ports:
      - "3081:3080"
```

**ClickHouse connection issues?**
```bash
# Check MCP container
docker compose logs mcp-clickhouse

# Verify credentials
docker compose exec mcp-clickhouse env | grep CLICKHOUSE
```

**Apple Silicon (M-series) Macs?**
Add to `docker-compose.override.yml`:
```yaml
services:
  mongodb:
    image: mongo:4.4.18
```

---

## Update LibreChat

```bash
docker compose down
git pull
docker compose pull
docker compose up -d
```

---

**Docs**: https://www.librechat.ai/docs
**ClickHouse MCP**: https://clickhouse.com/docs/use-cases/AI/MCP/librechat
