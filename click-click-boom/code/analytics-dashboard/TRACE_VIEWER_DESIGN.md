# Trace Viewer UI — Widget Design

Live trace viewer at port 8787 (or embedded in the dashboard). Every agent action
renders as a rich, expandable widget — not a plain log line.

---

## Tool inventory

### Group A — ClickHouse data tools (MCP: atlys_data)

| Tool | Input | Output shape |
|---|---|---|
| `list_tables` | `database` | `{tables: [{table, engine, row_count}], execution_time_ms}` |
| `describe_table` | `table_name`, `database` | `{columns: [{column, type}], execution_time_ms}` |
| `run_query` | `query` (SQL), `database` | `{columns, rows, execution_time_ms}` OR `{scratch_file, preview, row_count}` |
| `grep_scratch` | `scratch_file`, `pattern` | `[matching lines]` |
| `read_scratch` | `scratch_file`, `start_line`, `n_lines` | `[lines]` |
| `execute_python` | `code` (Python) | `{stdout, stderr, exit_code, truncated}` |

### Group B — Context tools (MCP: atlys_context)

| Tool | Input | Output shape |
|---|---|---|
| `list_context_sections` | none | `[{section, summary, confidence}]` |
| `lookup_context` | `sections: [str]` | `[{section, title, summary, body, confidence}]` |

### Group C — Skill tools (agent_runner)

| Tool | Input | Output shape |
|---|---|---|
| `list_skill_files` | `skill_name` | `[{path, size_bytes}]` |
| `read_skill_file` | `skill_name/path` | `{content: string (markdown)}` |

### Group D — Agent events (not tool calls)

| Event | Data |
|---|---|
| `generation` | `input` (payload), `output` (raw JSON), `reasoning` (summary), `model_reasoning` (chain-of-thought), `usage` (tokens) |
| `span_start` / `span_end` | `step` name, metadata |
| `trace_start` / `trace_end` | `agent`, `spec`, `trace_url` |

---

## Widget designs per tool

---

### `run_query` — SQL Query Widget
Most important widget. Shows SQL, result table, timing.

```
┌─ ▶ ClickHouse Query  ·  12.4ms  ·  14 rows ─────────────────── [expand] ┐
│                                                                           │
│  SELECT destination, uniqExactIf(application_id, event='forex_purchased')│  ← syntax-highlighted SQL
│    / uniqExactIf(application_id, event='forex_offer_shown') AS attach...  │     (collapsed to 3 lines)
│                                                          [show full SQL ↓]│
│                                                                           │
│  destination  shown   purchased  attach_pct                               │  ← result table
│  ──────────── ─────── ───────── ──────────                               │
│  GR           240     42        17.50%                                    │
│  US           236     58        24.58%                                    │
│  ID           224     37        16.52%                                    │
│  TH           223     51        22.87%                                    │
│                       ···  10 more rows  ···                              │  ← pagination
│                                                                           │
│  12.4ms  ·  14 rows returned  ·  [copy SQL]  [copy results as CSV]       │
└───────────────────────────────────────────────────────────────────────────┘
```

**Collapsed (default):**
```
▶ 🛢 ClickHouse Query  "SELECT destination, uniqExactIf..."  →  14 rows  12.4ms
```

**Details:**
- SQL rendered with syntax highlighting (keywords blue, strings green, functions amber)
- SQL collapsed to first 3 lines by default, "show full SQL" expands
- If result went to scratch file: show `📄 Saved to scratch: query_abc123.ndjson  ·  2,847 rows  ·  view →`
- Result table: max 10 rows shown, "N more rows" expands to full scrollable table
- Numeric columns right-aligned, percentage columns show a mini inline bar

---

### `execute_python` — Python Execution Widget

```
┌─ 🐍 Python  ·  0.8s  ·  exit 0 ─────────────────────────────── [expand] ┐
│                                                                           │
│  import pandas as pd                                                      │  ← syntax-highlighted Python
│  df = pd.read_json('query_abc123.ndjson', lines=True)                    │
│  print(df.groupby('currency')['attach_rate'].describe())                 │
│                                                          [show full ↓]   │
│                                                                           │
│  stdout ──────────────────────────────────────────────────────────────── │  ← output section
│  currency  count  mean    std     min     25%     50%     75%    max      │
│  AUD       196.0  13.78%  ...                                             │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

**If exit_code ≠ 0:** red border, stderr shown with red text
**Collapsed:**
```
▶ 🐍 Python  "df = pd.read_json(...)"  →  exit 0  0.8s
```

---

### `describe_table` — Schema Widget

```
┌─ 🛢 Schema: forex_addon_events  ·  8 columns  ·  3.1ms ──────── [expand] ┐
│                                                                           │
│  column                    type                                           │
│  ─────────────────────── ──────────────────────────                      │
│  id                        UUID                                           │
│  timestamp                 DateTime                                       │
│  user_id                   String                                         │
│  application_id_normalized LowCardinality(String)  ← highlight LowCard  │
│  event_type                LowCardinality(String)                         │
│  destination               LowCardinality(Nullable(String))               │
│  addon_value_inr           Nullable(Float32)                              │
│  to_currency               LowCardinality(Nullable(String))               │
└───────────────────────────────────────────────────────────────────────────┘
```

**Collapsed:**
```
▶ 🛢 Schema  forex_addon_events  →  8 columns  3.1ms
```

---

### `list_tables` — Tables Widget

```
┌─ 🛢 Tables: atlys  ·  14 tables ─────────────────────────────── [expand] ┐
│                                                                           │
│  table                              engine        rows                   │
│  ──────────────────────────────── ──────────── ────────────              │
│  destination_card_clicked           MergeTree    1,000,000               │
│  application_started                MergeTree    154,413                 │
│  forex_addon_events                 MergeTree    6,240    ← new table   │
│  abandoned_checkout_recovery_events MergeTree    5,920                   │
│  ...                                                                      │
└───────────────────────────────────────────────────────────────────────────┘
```

**Collapsed:**
```
▶ 🛢 Tables  atlys  →  14 tables
```

---

### `lookup_context` — Context Section Widget

```
┌─ 🗂 Context  ·  3 sections ──────────────────────────────────── [expand] ┐
│                                                                           │
│  ┌─ issue:K1 ─────────────────────────── confidence: 0.85 ─────────┐    │
│  │ iOS WebKit OTP autofill regression. On recent iOS builds the     │    │
│  │ payment OTP field fails to autofill. Gulf card users most        │    │
│  │ exposed. Watch pay_now_clicked → purchase_completed for iOS.     │    │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─ metric:conversion_rate ───────────── confidence: 0.9 ──────────┐    │
│  │ purchase_completed users ÷ application_started users             │    │
│  │ (NOT ÷ sessions — those definitions conflict in base_context)    │    │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─ convention:funnel_analysis ─────────────────────────────────────┐   │
│  │ Use uniqExact(user_id) per step. Prefer windowFunnel/sequenceMatch│   │
│  │ Always cut by device, geo, destination before concluding.         │   │
│  └────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

**Collapsed:**
```
▶ 🗂 Context  issue:K1, metric:conversion_rate, convention:funnel_analysis
```

---

### `list_context_sections` — Context Index Widget

```
┌─ 🗂 Context Sections  ·  31 sections ────────────────────────── [expand] ┐
│  section                    summary                            confidence │
│  ─────────────────────────  ─────────────────────────────    ─────────  │
│  issue:K1                   iOS WebKit OTP autofill regression  0.85     │
│  issue:K2                   Passport scan model update Apr 2026 0.80     │
│  metric:conversion_rate     purchase ÷ application_started      0.90     │
│  ...                                                                      │
└───────────────────────────────────────────────────────────────────────────┘
```

---

### `read_skill_file` — Skill Rule Widget

```
┌─ 📘 Skill: clickhouse-best-practices/rules/schema-types-avoid-nullable.md ┐
│                                                                            │
│  # Avoid Nullable columns                                                  │  ← rendered markdown
│  Use `DEFAULT` values instead of Nullable where possible. Nullable adds   │
│  extra overhead and complicates ORDER BY (Nullable columns cannot appear   │
│  in ORDER BY without allow_nullable_key=1).                               │
│                                                                            │
│  **When Nullable IS appropriate:** `application_id` (genuinely null        │
│  before application is created)...                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

**Collapsed:**
```
▶ 📘 Skill  clickhouse-best-practices  /rules/schema-types-avoid-nullable.md  ·  2.1KB
```

---

### `list_skill_files` — Skill Directory Widget

```
┌─ 📘 Skill Files: clickhouse-best-practices  ·  33 files ─────── [expand] ┐
│  rules/                                                                   │
│    schema-types-avoid-nullable.md        3.2KB                            │
│    schema-pk-cardinality-order.md        2.8KB                            │
│    schema-types-lowcardinality.md        1.9KB                            │
│    mv-aggregating-mergetree.md           4.1KB                            │
│    ...  29 more                                                            │
└───────────────────────────────────────────────────────────────────────────┘
```

---

### `grep_scratch` / `read_scratch` — File Peek Widget

```
┌─ 📄 Scratch File: query_abc123.ndjson  ·  lines 0–20 ─────────── [expand] ┐
│  {"event_type":"forex_offer_shown","application_id":"a1b2...","dest":"US"} │
│  {"event_type":"forex_offer_shown","application_id":"c3d4...","dest":"AE"} │
│  ...                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Agent Generation Widget (LLM turn)

```
┌─ ✦ Generation  ·  instrumentation_proposer  ·  2,847 tokens ─── [expand] ┐
│                                                                           │
│  💭 Reasoning ───────────────────────────────────────────────────────── │  ← purple border block
│  The table has 5 event types, all sharing user_id/application_id         │
│  envelope. The PM questions imply a funnel comparison — I'll need a      │
│  MV joining against purchase_completed. Using ordering key by            │
│  (destination, toDate(timestamp), user_id) per perf_tool winner...       │
│                                                                           │
│  Output ──────────────────────────────────────────────────────────────── │
│  { "table_name": "forex_addon_events",                                   │
│    "ordering_key_candidates": [...],                                      │
│    ...                            [show full JSON ↓]                     │
│                                                                           │
│  2,847 tokens  ·  input: 1,204  output: 487  reasoning: 1,156            │
└───────────────────────────────────────────────────────────────────────────┘
```

---

### Span Widget (pipeline stage)

```
┌─ › propose  ────────────────────────────────── 14.2s  [4 events inside] ┐
│  [▶ Skill] [▶ SQL] [▶ Schema] [✦ Generation]                            │
└───────────────────────────────────────────────────────────────────────────┘
```

Spans are collapsible containers. Clicking opens nested tool calls in order.

---

## Event feed layout (full page)

```
┌─ Traces ──────┐  ┌─ Express Checkout · analytics_agent · 2026-08-02 ───────────────────┐
│               │  │ Filter: All  SQL  Python  Context  Skills  Errors        [Langfuse ↗]│
│ ● express_...│  ├────────────────────────────────────────────────────────────────────────┤
│   running     │  │                                                                        │
│               │  │  › analytics_explore                               44.1s  12 events   │
│ ○ forex_...  │  │  ├─ 📘 Skill  context-engine/SKILL.md              2.1KB              │
│   done        │  │  ├─ 🗂 Context  metric:conversion_rate, issue:K1, ...  [expand]       │
│               │  │  ├─ 🛢 Schema  forex_addon_events  8 cols  3.1ms   [expand]           │
│               │  │  ├─ 🛢 Query   "SELECT event_type, count()..."  5 rows  4.2ms [expand]│
│               │  │  ├─ 🛢 Query   "SELECT destination, ..."  14 rows  12.4ms  [expand]   │
│               │  │  ├─ 🐍 Python  "df.groupby(...)"  exit 0  0.8s    [expand]           │
│               │  │  └─ ✦ Generation  analytics_agent  2,847 tok      [expand]           │
│               │  │                                                                        │
│               │  │  › analytics_persist                               0.2s               │
│               │  │    insight_written  confidence=0.78  "Instant Forex..."               │
└───────────────┘  └────────────────────────────────────────────────────────────────────────┘
```

---

## Color system

| Tool family | Icon | Accent color | Usage |
|---|---|---|---|
| ClickHouse SQL | 🛢 | `#f59e0b` amber | Queries, schema, tables |
| Python | 🐍 | `#22c55e` green | execute_python |
| Context | 🗂 | `#5eead4` teal | lookup_context, list_context_sections |
| Skill | 📘 | `#a78bfa` violet | read_skill_file, list_skill_files |
| Scratch file | 📄 | `#94a3b8` slate | grep_scratch, read_scratch |
| LLM Generation | ✦ | `#818cf8` indigo | Generation events |
| Span | › | `#475569` muted | Pipeline stages |
| Error | ✗ | `#f43f5e` red | Any failure |

---

## Interaction model

- **Default:** all widgets collapsed to one line
- **Click header:** expand/collapse in place
- **SQL widget:** "show full SQL" is a separate expand within the expanded widget
- **Result tables:** show max 10 rows, "N more" expands to full scrollable (max-height: 400px, overflow-y: scroll)
- **Filter bar:** filter by tool family — show only SQL, only Python, only Context, etc.
- **Trace URL** in toolbar → opens Langfuse with full nested spans
- **Copy buttons** on SQL, Python code, and result tables

---

## Implementation order

1. **Core widget shell** — collapsed line with icon, label, timing, expand toggle
2. **SQL widget** — syntax highlight + result table (highest value)
3. **Schema widget** — column type table
4. **Context widget** — section cards with confidence
5. **Python widget** — code highlight + stdout/stderr
6. **Skill widget** — markdown render
7. **Generation widget** — reasoning callout + token counts
8. **Span containers** — nested expand/collapse tree
9. **Filter bar + trace link**
