# sonyliv-mcp — the serving layer over MCP

An MCP server that lets an assistant answer viewing-trend questions against the SonyLIV
concurrency serving layer, and **nothing else**. No per-user data, no event stream, no
system tables, no writes.

## Why not ClickHouse Cloud's hosted MCP

`mcpEnabled: true` on the service, and there is a hosted server at
`https://mcp.clickhouse.cloud/mcp`. It was measured and rejected, for one reason:

**it cannot be narrowed.** Its tool list includes `get_organizations`,
`get_organization_cost`, `list_service_backups`, `get_service_details`, `list_clickpipes`
and the Postgres tools, none of which can be turned off. Authenticated with a Cloud API
key it returns organisation-wide control-plane data — verified: `get_organizations`
returned the whole GobbleCube org. Authenticated with a plain ClickHouse user the
control-plane tools return `401 Key is not found` *and* `run_select_query` cannot resolve
the service, so it is unusable for data.

There is no configuration in which it exposes the serving layer and only the serving
layer. Hence this server.

## How "serving layer only" is enforced

Two independent layers. The order matters.

**1. The grant — this is the boundary.** `ingest/sql/manual/009_mcp_reader.sql` creates
`sonyliv_mcp` with `SELECT` on eight serving objects and `dictGet` on `content_dict`.
Nothing else. Whatever SQL arrives, ClickHouse refuses to read `events_clean` or
`session_intervals` for this user.

**2. The guard — this is the explanation.** `guard.go` validates every statement before
it is sent: single statement, `SELECT`/`WITH` only, relations checked against an
allowlist, table-valued functions that reach off-box (`url`, `s3`, `remote`,
`clusterAllReplicas`, …) refused by name.

The guard is a parser, and parsers get talked past. It exists so a refusal says *"that
table is outside the serving layer"* instead of `ACCESS_DENIED`, which a model can act
on — not because it is trusted. If it is ever wrong, the grant still holds.

`main.go` refuses to start if the connected user can read `events_clean` or
`session_intervals`, so an over-privileged deployment fails loudly at boot rather than
being discovered later by someone reading `user_id` through the model.

### The line being drawn

Withheld deliberately, because they carry `user_id` / `user_key` /
`canonical_user_id`: `events_raw`, `events_clean`, `events_dedup`,
`events_raw_to_clean_mv`, `fleet_sessions`, `session_intervals`.

The serving layer is aggregate-only — its narrowest row is one dimension combination in
one minute, and no row identifies a person. That, not "the tables the dashboards happen
to use", is the split.

## Setup

**1. Create the restricted user.** Needs an admin: `sonyliv_svc` holds no
`ACCESS MANAGEMENT` privilege, so it cannot create this account (verified —
`CREATE USER` returns `ACCESS_DENIED`).

```bash
# choose a password, substitute it, and run as an admin
sed "s/__MCP_PASSWORD__/$(openssl rand -hex 24)/" ingest/sql/manual/009_mcp_reader.sql \
  | clickhouse client --host <host> --secure --user <admin> --password --multiquery
```

**2. Prove the grants.** Positive and negative cases, straight against ClickHouse:

```bash
MCP_CH_PASSWORD=<password> ./ingest/cmd/sonyliv-mcp/check-grants.sh
```

**3. Deploy.** See `deploy/deploy-mcp.sh` for the box prerequisites and
`/etc/sonyliv/mcp.env` contents.

```bash
MCP_HOST=ec2-user@<ip> ./deploy/deploy-mcp.sh
MCP_HOST=ec2-user@<ip> ./deploy/deploy-mcp.sh --check
```

The unit binds `${MCP_ADDR}` from `/etc/sonyliv/mcp.env`. On the demo box that is
`172.17.0.1:8848`, the Docker bridge gateway, because LibreChat runs in a container and a
container cannot reach the host's loopback. The bridge is still a host-local interface —
nothing plaintext leaves the box, and 8848 is not in the security group.

**Anything that publishes this port off-box must terminate TLS in front of it** — the
bearer token is SQL access and must not cross a network in plaintext.

The HTTP transport refuses to start without `SONYLIV_MCP_TOKEN`. `--allow-no-auth` drops
that requirement but then refuses any non-loopback bind, so the unauthenticated and
off-loopback cases can never combine.

## Client configuration

```json
{
  "mcpServers": {
    "sonyliv-serving": {
      "type": "http",
      "url": "https://<your-tls-frontend>/mcp",
      "headers": { "Authorization": "Bearer <SONYLIV_MCP_TOKEN>" }
    }
  }
}
```

Claude Code: `claude mcp add --transport http sonyliv-serving https://<host>/mcp --header "Authorization: Bearer <token>"`

Local stdio, no HTTP, for development:
`bin/sonyliv-mcp --transport stdio`

## What it exposes

| Tool | For |
|---|---|
| `list_serving_tables` | what exists, with columns and purpose |
| `data_freshness` | how current each layer is — **call before reporting any drop** |
| `viewing_trend` | concurrency over time at minute / hour / day |
| `peak_and_average` | the two headline numbers for a window |
| `rank_dimension` | rank platforms, categories, content types |
| `top_titles` | title leaderboard |
| `detect_drops` | slices falling against their own trailing median |
| `run_select_query` | anything else, guarded |

Plus the knowledge, which is the point of building this rather than pointing a generic
SQL MCP at the database:

- **`initialize` instructions** — the additivity rule and the grouping rule reach the
  model before its first tool call, not only if it happens to read a resource.
- **`sonyliv://serving/guide`** resource — the full model: schema semantics, grouping
  selection with read costs, freshness, reference figures, query recipes.
- **`viewing-trends`** and **`investigate-drop`** prompts — ordered procedures.

Every rule in the guide is one that has already been got wrong on this data: summing a
peak, blending the eleven groupings (measured 9,411.64 against a true 855.58), reading an
unpublished minute as zero viewers, an inclusive right edge adding 4.3%.

## Verification

```bash
# start locally, then:
MCP_TOKEN=<token> ./ingest/cmd/sonyliv-mcp/check-mcp.sh
```

45 checks: handshake, tool list, knowledge, the graded reference figures, every curated
tool, and — the ones that matter — the refusals. Per-user tables by bare name, by
database-qualified name, behind a comment, behind a quoted identifier, via a JOIN; writes;
stacked statements; `url()`, `remote()`, `clusterAllReplicas()`; and bearer-token auth.

`--dev-unrestricted` starts the server against an over-privileged user so the guard can be
exercised before an admin has created `sonyliv_mcp`. It skips only the grant preflight,
logs loudly, and must never be used in a deployment.
