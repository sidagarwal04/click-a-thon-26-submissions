# Chat Charts & Tables Plan

> **Status:** Implemented (MVP Waves 0–2) — `ChatChart.jsx` + `atlyschart` fences in `ChatMessage.jsx`; autonomy rules in `atlys_pm.md`.
>
> **Audience:** Implementers of the React chat shell (`Atlys/ui/**`), agent prompt (`Atlys/agents/atlys_pm.md`), and optionally a thin viz-hint helper if we add server-side shaping later.
>
> **Depends on:** Safe DB read tools (`db_schema`, `table_stats`, `aggregate`, `sample_rows`) — already shipped. Chat history persistence is orthogonal (`docs/chat-history-plan.md` if revived).
>
> **North star:** When the agent answers with quantitative or tabular data, the chat shows **clear tables and charts** when they help — decided autonomously by the model from the data shape, not forced every turn.

---

## 0. Problem

PMs ask “show conversion by destination” or “what’s in the DB?” and get prose (or a wall of numbers). The shell already renders GFM markdown tables, but:

1. The prompt never tells the model **when** to emit a table vs a chart vs a short sentence.
2. There is **no chart renderer** — only `react-markdown` + `remark-gfm` + Prism.
3. Tool JSON stays inside LibreChat → LLM context; the UI only sees streamed **text deltas**.
4. Mid-stream incomplete fences would break chart parsing if we naively render every chunk.

**User-facing target:**

| Situation | Chat shows |
|---|---|
| 2–3 headline numbers | Short prose (no chart clutter) |
| Breakdown by category (≤ ~20 rows) | Markdown table + optional bar/pie chart |
| Time series / ordered steps | Table + line/bar chart |
| Schema / column list | Compact table (no chart) |
| Huge / truncated result | Table of what we have + note; no invented series |
| Schema approval / insight narrative | Prose first; viz only if evidence is tabular |

---

## 1. Current state

| Layer | Today | Gap |
|---|---|---|
| Message model | `{ role, content, pending, … }` string only | No structured viz parts |
| Render | `ChatMessage.jsx` → `react-markdown` + `remark-gfm` | Tables work; charts don’t |
| Stream | `chatStream` keeps `delta.content` only | Tool JSON never reaches UI |
| Chart libs | None in `package.json` | Need one lightweight lib |
| Prompt | Prefer aggregates; don’t dump rows | No viz decision policy |
| Caps | `truncate_for_mcp` 64KB / 100 rows (aligned with aggregate max); long-text keys keep full docs | Charts must use small series |

**Key files**

- `Atlys/ui/src/components/chat/ChatMessage.jsx` — markdown render
- `Atlys/ui/src/components/chat/ChatPanel.jsx` — stream accumulate
- `Atlys/ui/src/api/client.js` — SSE parse
- `Atlys/ui/src/index.css` — existing GFM table styles
- `Atlys/agents/atlys_pm.md` — agent behavior
- `Atlys/service/db_read.py` / `payloads.py` — data + caps the model sees

---

## 2. Design principles

1. **Agent decides, UI renders.** The model chooses prose / table / chart from the question + result shape. The UI does not auto-chart every tool call.
2. **Text-compatible contract.** Viz must travel inside the assistant markdown stream (Agents API is text-out). No parallel binary artifact channel for MVP.
3. **Progressive enhancement.** GFM tables work even if chart parsing fails. Charts are optional fences on top of (or instead of repeating) the same numbers.
4. **Finalize-on-idle for charts.** While `pending === true`, render markdown only (or inert placeholders). Mount interactive charts when the stream completes to avoid broken JSON/SVG mid-token.
5. **Truthfulness.** Charts/tables only use numbers present in the tool result the model saw. If `truncated: true`, say so and do not fabricate series.
6. **Small series only.** Prefer ≤ 20 categories for bars/pies; ≤ 60 points for lines. Larger → table top-N + prose.
7. **One primary visual per answer** unless the user asks for more. Avoid dashboard-in-a-bubble.
8. **Keep pipeline UX.** Approval buttons / insight summary stay; viz must not bury the approve CTA.

---

## 3. Viz contract (assistant markdown)

### 3.1 Tables (P0 — prompt-only)

Model emits standard GFM tables (already supported):

```markdown
| destination | users | events |
|---|---:|---:|
| FR | 1200 | 5400 |
| DE | 800 | 3100 |
```

No UI code required beyond prompt + maybe denser table CSS.

### 3.2 Chart fences (P1 — UI + prompt)

Closed fenced block with a fixed language tag: **`atlyschart`** (single token — today’s `ChatMessage` lang regex is `\w+`, so hyphens would truncate; avoid `atlys-chart`).

````markdown
```atlyschart
{
  "type": "bar",
  "title": "Users by destination",
  "x": "destination",
  "y": "users",
  "data": [
    {"destination": "FR", "users": 1200},
    {"destination": "DE", "users": 800}
  ]
}
```
````

**Schema (MVP)**

| Field | Required | Notes |
|---|---|---|
| `type` | yes | `bar` \| `line` \| `pie` \| `horizontal_bar` |
| `title` | no | Short string |
| `x` / `y` | for bar/line | Column keys in `data` |
| `label` / `value` | for pie | Column keys |
| `data` | yes | Array of objects; **max 60** points (UI clamps) |
| `note` | no | e.g. `"truncated sample"` |

Invalid JSON → show the raw fence as a code block (or a small “couldn’t render chart” note) + keep any GFM table above/below.

**Optional later:** `vega-lite` fence if we outgrow the tiny schema — not MVP.

### 3.3 When the agent should choose what

Teach this decision table in `atlys_pm.md` (normative):

| Data shape / question | Prefer |
|---|---|
| Single metric or yes/no | Prose only |
| 2–12 categorical rows (breakdown) | GFM table **and** `bar` or `horizontal_bar` |
| Share-of-whole (parts sum ~100%) | Table + `pie` (only if ≤ 8 slices) |
| Ordered steps / funnel / time | Table + `bar` or `line` |
| Schema / column inventory | GFM table only |
| Sample rows | GFM table only (no chart) |
| > 20 categories | Top 10 table + prose; chart top 10 only |
| Truncated / timeout / error | Prose + partial table; **no** chart from incomplete data |
| Schema approval / run_id gate | Prose + DDL; viz deferred until after metrics exist |

Autonomy rule: if a chart would **not** add clarity beyond the table, skip the chart.

---

## 4. UI implementation

### 4.1 `ChatMessage` custom code renderer

In `react-markdown` `components.code` (or `pre`):

1. If lang is `atlyschart` **and** `!msg.pending`:
   - `JSON.parse` body → validate → `<ChatChart spec={…} />`
2. Else existing Prism path for SQL/json/etc.
3. If pending and fence looks like `atlyschart`: render a compact “Chart loading…” placeholder or plain code until done.
4. Optionally widen the lang regex to `[\w-]+` if we later want hyphenated tags.

### 4.2 `ChatChart` component (new)

- New file e.g. `Atlys/ui/src/components/chat/ChatChart.jsx`
- Library choice (pick one in Wave 0):
  - **Recommended:** [Recharts](https://recharts.org) — React-native API, small surface for bar/line/pie.
  - Alternative: Chart.js + react-chartjs-2.
- Map `type` → chart; empty/invalid → fallback message.
- Clamp `data.length` (e.g. 60); format numbers with locale-aware grouping.
- Match existing chat visual language (CSS variables already in `index.css`) — avoid a second design system.
- Accessibility: title as heading; table of the same data in a `<details>` “View data” disclosure (good default).

### 4.3 Streaming behavior

| Phase | Behavior |
|---|---|
| Chunks arriving | Markdown + GFM tables update live (as today) |
| Open `atlyschart` fence | Placeholder or unparsed code |
| `pending → false` | Parse fences; mount charts once |

No change to `proxy_chat` required for MVP.

### 4.4 Styling

- Tighten `.chat-md table` for numeric columns (tabular nums, right-align `th`/`td` when column is numeric — optional heuristic).
- Chart container: full bubble width, max-height ~280px, no card-in-card chrome beyond a light border if needed for separation from prose.

### 4.5 Out of scope for MVP

- Dashboard side-panel mirroring (nice follow-up: “Open in dashboard”)
- Export PNG / CSV
- Interactive cross-filter between chat charts
- Server-side chart image generation
- Showing raw MCP tool JSON chips (separate UX)

---

## 5. Prompt & agent changes

Update `atlys_pm.md`:

1. Add **Visualization** section with the decision table (§3.3) and the `atlyschart` JSON schema (short example).
2. Rules:
   - After `aggregate` / useful `table_stats`, prefer a GFM table of the returned rows.
   - Add `atlyschart` when categorical/series shape fits §3.3.
   - Data in the chart **must** match the table / tool numbers exactly.
   - Never invent points to “make a nicer chart.”
   - One chart max unless the user asks for multiple views.
3. Re-provision / patch LibreChat agent instructions (same path as DB-read tools).

No new MCP tool required for MVP — viz is a **presentation choice** over existing tool results.

**Optional P2 helper (only if the model is unreliable):** MCP tool `format_viz` that accepts rows + suggested type and returns `{markdown_table, chart_fence}` deterministically. Prefer prompt-first; add only if rehearsal shows consistent failures.

---

## 6. Implementation waves

### Wave 0 — Spike (~1–2h)

1. Confirm GFM tables look acceptable with a hard-coded assistant message in the UI.
2. Pick chart library; spike one bar chart from a static `atlyschart` fence in `ChatMessage`.
3. Verify stream finalize behavior (don’t mount chart while `pending`).

### Wave 1 — Tables excellence (prompt + CSS)

1. Prompt decision table for GFM tables.
2. Polish table CSS (overflow-x, sticky header optional, numeric alignment).
3. Manual chat: aggregate breakdown → readable table.

### Wave 2 — Charts

1. Add dependency; implement `ChatChart` + fence parser.
2. Prompt `atlyschart` examples + autonomy rules.
3. Re-provision agent.
4. Manual: “users by destination”, “funnel steps”, “share by OS” → table + chart; “how many rows?” → prose only.

### Wave 3 — Hardening / polish

1. Invalid fence fallback tests (unit: parse helpers).
2. Truncation / empty data paths.
3. Optional: “View data” disclosure under every chart.
4. Optional: suggest chart in welcome examples / chips.
5. If model under-uses charts: add 2–3 few-shot lines in the prompt (not a new tool).

---

## 7. Safety & quality

| Risk | Mitigation |
|---|---|
| Hallucinated chart data | Prompt: chart ⊆ tool result; UI doesn’t fetch alternate data |
| Huge payloads in fence | UI clamp; prompt max rows; MCP already truncates tool input |
| Broken mid-stream JSON | Render charts only when `!pending` |
| Pie chart misuse | Prompt: ≤ 8 slices, parts-of-whole only |
| Accessibility | Title + data table disclosure |
| Approve CTA buried | Keep viz after narrative; don’t put chart above approval ask |

---

## 8. Test plan

| # | Case | Expected |
|---|---|---|
| 1 | Assistant GFM table only | Renders correctly in bubble |
| 2 | Valid `atlyschart` after stream ends | Chart mounts with title |
| 3 | Same fence while `pending` | No crash; placeholder/code |
| 4 | Invalid JSON in fence | Fallback, rest of message OK |
| 5 | > 60 data points | Clamped; note or silent top-N |
| 6 | Chat: categorical aggregate | Model emits table + bar (rehearsal) |
| 7 | Chat: “row count for X?” | Prose, no chart |
| 8 | Truncated tool result | Model discloses; no fake series |
| 9 | Schema approval turn | No chart blocking approve buttons |

---

## 9. Acceptance criteria

- [ ] Agent autonomously uses GFM tables for multi-row aggregate answers.
- [ ] Agent emits `atlyschart` when categorical/series data clearly benefits from a visual; skips for single metrics.
- [ ] UI renders bar/line/pie from finalized fences without breaking streaming.
- [ ] Invalid/partial fences degrade gracefully.
- [ ] Numbers in charts match tables/tool results; truncation is disclosed.
- [ ] Prompt + agent provisioning updated; no free-form SQL or new write tools.

---

## 10. Effort sketch

| Wave | Effort | Outcome |
|---|---|---|
| Wave 0 | 1–2h | Library + fence spike |
| Wave 1 | ~2–3h | Tables feel intentional |
| Wave 2 | ~0.5–1 day | Charts in chat |
| Wave 3 | optional | Hardening |

**MVP cut:** Waves 0–2.

---

## 11. Appendix — example agent reply

````markdown
Here’s **users by destination** from `events` (fresh `aggregate`):

| destination | users |
|---|---:|
| FR | 1200 |
| DE | 800 |
| US | 450 |

```atlyschart
{
  "type": "bar",
  "title": "Users by destination",
  "x": "destination",
  "y": "users",
  "data": [
    {"destination": "FR", "users": 1200},
    {"destination": "DE", "users": 800},
    {"destination": "US", "users": 450}
  ]
}
```

FR leads; I can break this down by event next if useful.
````
