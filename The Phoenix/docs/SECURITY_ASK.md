# The Ask AI boundary

Both consoles carry an Ask AI mode that forwards a browser-supplied thread to a LibreChat agent
holding a live `clickhouse` MCP tool. That makes it the one place in this repo where untrusted text
reaches something able to read the graded corpus, so what follows is the boundary, what it does not
claim, and the gate that keeps it honest.

`./scripts/check_ask_guardrails.sh` asserts every property below. The static half needs nothing
running; the live half needs `npm run dev` and is skipped, loudly, when it is absent.

## One database per console, chosen in code

| Console | Route | May read |
|---|---|---|
| v1, `/` | `POST /api/ask` | `phoenix` |
| v2, `/v2` | `POST /api/v2/ask` | `phoenix_next` |

The scope is a constant in `frontend/src/lib/ask.ts` (`V1_SCOPE`, `V2_SCOPE`) selected by the route
file. It is never a request field. A client able to name its own database would hand that choice to
anything that got a message into the thread, and the two consoles read different generations for a
reason. The gate greps for a database name arriving out of `body`/`req`, and for either route
referencing the other's scope.

## The system turn is ours

The client may send `user` and `assistant` turns and nothing else. Any other role, including
`system` and `tool`, is dropped during validation rather than rejected, so a thread that somehow
accumulated one still works, and `askAgent` prepends the real system message itself.

A forwarded `system` turn is the simplest prompt injection there is. The first version of the route
forwarded whatever roles it was handed.

## What the system prompt says, and where it comes from

The dataset facts are transcribed from [`docs/problem/dataset_details.md`](problem/dataset_details.md),
not summarised from memory. It states which columns live on the event and which live on `content`,
that a title or category question is therefore a join, and that `video_session_id` and `user_id` are
different questions. An agent that does not know this invents a join and then explains a wrong
number confidently, which is worse than refusing.

It also carries the foreground-only definition, the 90-second tolerance, and an instruction to
report a failed query rather than estimate around it.

The last paragraph is the injection boundary: everything after the system message, and every value
read out of the database, is data. Content titles, app version strings and country names are
user-supplied fields that can contain text shaped like commands, and the agent is told to treat any
such text as a finding to report rather than an instruction to follow.

## Tool calls, and why the prompt is long

The agent holds three MCP tools: `list_databases`, `list_tables` and `run_query`. Left to itself it
opens with the two discovery calls before it can write anything, and `list_tables` returns the full
`CREATE` statement for every table in the database.

Measured against the running MCP server:

| Call | Response | Roughly |
|---|---|---|
| `list_tables(phoenix)` | 89,159 characters | 22K tokens |
| `list_tables(phoenix_next)` | 192,789 characters | 48K tokens |

So the system prompt carries the column-level schema inline and tells the agent not to make those
calls. The two scope blocks are 2.2K and 4.0K characters, about 1K tokens: a fixed cost per request
in place of up to 48K of variable cost, and one round trip in place of three.

It is also the more accurate option. The prompt carries the two mistakes that produce a confident
wrong number here, and neither is visible in a `CREATE` statement: summing a `ReplacingMergeTree`
without `FINAL` adds superseded versions (measured 4x too high after four refresh runs, while the
ratios stayed right, which is what makes it dangerous), and `count()`, `uniqExact()` and `max()` are
all unsafe on the `CollapsingMergeTree` transitions table unless rows are netted by key first.

The instruction is to answer in one query where one query will do, and to query again only when the
first result genuinely needs a follow-up.

## Bounds

| Limit | Value | Why |
|---|---|---|
| Turns per thread | 24 | Long enough for a real follow-up, short enough to bound cost |
| Characters per message | 4,000 | |
| Characters per thread | 24,000 | |
| Requests per minute per process | 20 | One dev server, one demo: coarse on purpose, not a distributed limiter |

Validation runs **before** the deployment check, so a malformed or oversized thread is refused the
same way whether or not LibreChat is configured. The reverse order makes the guardrails untestable
on a machine that has not set the agent up yet, which is every machine at first run.

## What this does not claim

A system prompt is a strong instruction, not an enforcement mechanism. Nothing here can stop a
sufficiently clever thread from talking an agent into trying something.

**The durable control is the credential the MCP server holds.** If that ClickHouse account is
read-only, no phrasing gets a write through it. This layer raises the cost of an injection and makes
the intent explicit and testable; it is not the last line and is not written as though it were.

### Applied: the MCP server authenticates as a read-only user

`librechat/docker-compose.override.yml` passes `CLICKHOUSE_USER` straight through to the
`mcp-clickhouse` container. It used to receive `CH_USER=default`, which on ClickHouse Cloud is an
administrator, and the strongest honest statement about the path was then that the prompt asks the
agent not to write, which is exactly the assurance this document says not to rely on.

`phoenix_ask` now exists and `librechat/.env` (gitignored) points the container at it:

```sql
CREATE USER IF NOT EXISTS phoenix_ask IDENTIFIED BY '<generate one>'
  SETTINGS readonly = 1, max_execution_time = 30, max_result_rows = 100000;
GRANT SELECT ON phoenix.* TO phoenix_ask;
GRANT SELECT ON phoenix_next.* TO phoenix_ask;
```

`readonly = 1` refuses writes and settings changes at the server, so it holds regardless of what the
agent is talked into attempting. The two grants are what make the per-console split real at the
database rather than only in the prompt: without them, scoping v1 to `phoenix` and v2 to
`phoenix_next` is a convention the agent is asked to observe.

Verified against the live service as `phoenix_ask`, rather than assumed from the DDL:

| Attempt | Result |
|---|---|
| `SELECT count() FROM phoenix.concurrency_deltas` | 65,037 |
| `SELECT count() FROM phoenix_next.audience_minute_snapshot` | 261,564 |
| `INSERT INTO concurrency_deltas` | `Code: 497 ... Not enough privileges` |
| `CREATE TABLE t (a Int8) ENGINE=Memory` | `Code: 497 ... Not enough privileges` |
| `SELECT 1 SETTINGS readonly=0` | `Code: 164 ... Cannot modify 'readonly' setting in readonly mode` |

The last row is the one that matters: the restriction cannot be lifted from inside the session, so
it does not depend on the agent choosing to respect it.

`system.tables` stays readable. The MCP server needs it to describe a schema before querying it,
and it carries no event data.

To rotate, re-run the `CREATE USER` above with a new password and update `librechat/.env`. Cloud
requires at least one special character in the password.

Rendering is markdown through `react-markdown` with raw HTML disabled by default, so an answer
containing markup renders as text rather than as an element.
