# Chat Identity & History Plan

> **Status:** Implemented (Option B — Atlys JSON store under `generated/chats/`).
> Waves 1–2 shipped: conversation ids, reload restore, New chat, past-chats sidebar.
>
> **Audience:** Implementers of the React shell (`Atlys/ui/**`) and FastAPI chat proxy (`Atlys/service/api.py`).
>
> **Relationship to ENGINEERING.md:** ENGINEERING D12 originally assumed an **iframe of LibreChat**, which would own conversation identity, reload restore, and past-chat listing for free. The shipped shell is a **custom chat panel** + `POST /api/proxy/chat`, so that persistence never landed. This doc owns the replacement contract. Pipeline state stays in ClickHouse (D3); chat transcripts stay out of CH unless we explicitly decide otherwise (§3).

---

## 0. Problem

Visiting / reloading the dashboard always starts a blank chat (welcome message only). There is no conversation identifier in the URL or client, no restore path, no “New chat”, and no list of past chats.

**Root cause (stacked):**

1. `ChatPanel` keeps messages only in React `useState`; remount resets to `WELCOME_MSG`.
2. The UI never creates, stores, or restores a `conversationId`.
3. `chatStream` posts `{ messages, stream: true }` only — omits the optional ID the backend already accepts.
4. Atlys has no list/get history APIs for conversations.
5. Architecture drift: iframe LibreChat (history built-in) → custom UI without replacing persistence.

**User-facing target:**

| Action | Behavior |
|---|---|
| Open / reload dashboard | Same active chat restored (same id + messages) |
| New chat | New identifier; empty/welcome thread; URL updates |
| Past chats | Sidebar (or equivalent) lists prior conversations; click restores |
| Send message | Continues the active conversation id |

---

## 1. Current state

| Layer | Today | Gap |
|---|---|---|
| UI messages | In-memory only (`ChatPanel.jsx`) | Lost on reload |
| Conversation id | None in UI; optional on `ChatRequest` | Never sent |
| Client | `POST /api/proxy/chat` with `{ messages, stream }` | No id round-trip; no list/load helpers |
| FastAPI | Forwards optional `conversationId` to LibreChat Agents API | No list/get proxies |
| Storage | LibreChat Mongo may persist agent turns when an id is used | Shell never participates |
| URL / routing | Single `/` shell, no chat param | Reload cannot target a chat |
| Auth | Agents API key injected server-side for chat completions | List/history endpoints may need a different LibreChat auth story (§3) |

**Key files today**

- `Atlys/ui/src/components/chat/ChatPanel.jsx` — message state
- `Atlys/ui/src/api/client.js` — `chatStream`
- `Atlys/ui/src/App.jsx` — layout; no chat routing
- `Atlys/service/api.py` — `ChatRequest.conversationId`, `proxy_chat`
- `Atlys/docker-compose.yml` — `mongo` + `librechat`

**Data flow today**

```
Browser ChatPanel (useState only)
  → POST /api/proxy/chat { messages, stream }   ✗ no conversationId
  → LibreChat Agents /api/agents/v1/chat/completions
  → Mongo may store something, but shell cannot list or reload it
```

---

## 2. Design principles

1. **One active conversation id in the shell.** Reload restores that id; “New chat” allocates a new one.
2. **URL is the source of truth for which chat is open** (shareable / bookmarkable within the demo). Prefer `?chat=<id>` or `/c/<id>` — pick one in Wave 0 and stick to it.
3. **Do not put chat transcripts in ClickHouse** unless LibreChat APIs prove unusable for list/restore (D3: CH is pipeline data). Prefer LibreChat Mongo as the transcript store.
4. **FastAPI stays the only browser-facing API.** Browser never talks to LibreChat directly; proxy list + get + chat with the same key injection pattern as today.
5. **MVP over product polish.** Titles can be first-user-message truncation; no search, folders, or multi-user ACL for the hackathon.
6. **Keep sending messages for the active turn** (current OpenAI-style array) until we confirm Agents API can continue a thread from id alone; then optionally slim the client payload.

---

## 3. Storage decision

### Option A — LibreChat Mongo via `conversationId` (preferred)

Reuse what ENGINEERING already assumes for chat infra.

| Concern | Approach |
|---|---|
| Identity | Client generates UUID (or accepts id returned by Agents API) as `conversationId` |
| Persist turns | Pass `conversationId` on every `POST /api/proxy/chat` |
| List | Proxy `GET /api/convos` (or Agents-equivalent) → `GET /api/conversations` |
| Restore | Proxy `GET /api/messages/:conversationId` → `GET /api/conversations/:id/messages` |
| New chat | New UUID; clear messages to welcome; update URL |

**Spike (Wave 0 — must complete before coding UI):**

1. With Agents API key, does `conversationId` on `/api/agents/v1/chat/completions` create/update a Mongo conversation the list APIs can see?
2. Do `GET /api/convos` and `GET /api/messages/:id` accept the Agents API key, a login JWT, or only cookie sessions?
3. Does the stream response include a stable `conversationId` we should adopt instead of client-generated UUIDs?
4. Message shape for restore: map LibreChat message fields → UI `{ id, role, content, ts }`.

If (1)–(2) fail under demo auth, prefer Option B for MVP rather than inventing LibreChat login in the shell.

### Option B — Atlys-owned chat store (fallback)

Thin tables (or JSON files under `Atlys/generated/chats/`) owned by FastAPI:

- `conversations(id, title, created_at, updated_at)`
- `messages(id, conversation_id, role, content, created_at)`

Still send `conversationId` to LibreChat when useful for agent memory; **authoritative history for the shell is Atlys**. Acceptable for hackathon; document the divergence from D3/D12 intent.

### Decision log

| ID | Decision | Default |
|---|---|---|
| C1 | Transcript store | **B** Atlys JSON (`generated/chats/`) — chosen to avoid LibreChat list-auth coupling; still forwards `conversationId` to Agents API |
| C2 | Active chat in URL | **Yes** — `?chat=<uuid>` (minimal change to Vite SPA) |
| C3 | Last-active fallback | If URL has no `chat`, restore last id from `localStorage`; else new chat |
| C4 | Welcome message | Synthetic UI-only message; not stored as a user/assistant turn |
| C5 | Delete / rename | Out of scope for MVP (optional P2) |

---

## 4. Target UX

```
┌─────────────────────────────────────────────────────────────┐
│ Atlys Copilot                    [New chat]                 │
├──────────────┬──────────────────────────┬───────────────────┤
│ Past chats   │  Active thread           │  Dashboard        │
│ · Express…   │  (messages for chat id)  │  Insights / …     │
│ · Schema…    │                          │                   │
│ · …          │  [upload] [input] [send] │                   │
└──────────────┴──────────────────────────┴───────────────────┘
```

- **Past chats:** title (truncated of first user message or LibreChat title), relative `updatedAt`, active row highlighted.
- **New chat:** always available from header or history panel; does not delete the previous conversation.
- **Reload:** same `?chat=` → same messages; browser back/forward switches chats if history entries exist.
- **Empty state:** welcome only; first send creates/binds persistence.

---

## 5. API contract (Atlys-facing)

All under FastAPI; implement with Option A proxies or Option B store.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/proxy/chat` | **Extend** — require/echo `conversationId`; parse stream for returned id if present |
| `GET` | `/api/conversations` | List `{ id, title, updatedAt }[]` (newest first, limit ~50) |
| `GET` | `/api/conversations/{id}` | Metadata |
| `GET` | `/api/conversations/{id}/messages` | Ordered messages for restore |
| `POST` | `/api/conversations` | Optional — create empty conversation (or create lazily on first message) |

**Chat request (updated):**

```json
{
  "conversationId": "uuid",
  "messages": [ { "role": "user", "content": "…" } ],
  "stream": true
}
```

**Chat response (non-stream headers or first SSE event):** ensure client can learn/confirm `conversationId` if the server minted it.

**Errors:** unknown id → 404; LibreChat down → 503 with clear message (history list empty is OK; active send fails loud).

---

## 6. Frontend contract

| Concern | Behavior |
|---|---|
| State | Lift `conversationId` + `messages` (or keep in `ChatPanel` + props from `App`) |
| Bootstrap | Read `?chat=` → else `localStorage.atlys.activeChat` → else create new id and `replaceState` URL |
| Load | `GET .../messages` → replace `messages` (prepend welcome if thread empty) |
| Send | Include `conversationId` in `chatStream`; keep optimistic UI append |
| New chat | New UUID → clear to welcome → update URL + localStorage → refresh list |
| History UI | Fetch list on mount + after each completed turn (or on focus) |
| Streaming | Unchanged chunk handling; do not lose id if remount mid-stream (disable navigation while `loading` or cancel stream) |

**Client API additions** (`client.js`):

- `chatStream(messages, onChunk, onDone, { conversationId, token })`
- `listConversations()`
- `getConversationMessages(id)`

---

## 7. Implementation waves

### Wave 0 — Spike (½ day)

- [ ] Prove Agents chat + `conversationId` persistence in Mongo
- [ ] Prove list + messages readable with the same credential FastAPI already has
- [ ] Record choice **A vs B** in this doc’s decision log
- [ ] Confirm stream payload fields for id echo

**Exit:** Written decision A or B; sample curl transcripts checked into notes or appendix.

### Wave 1 — Identity + reload same chat (P0)

- [ ] UI generates/stores `conversationId`; put in URL + `localStorage`
- [ ] `client.chatStream` sends `conversationId`
- [ ] Proxy always forwards it; surface returned id if LibreChat provides one
- [ ] “New chat” control
- [ ] If Option B: write messages on each completed turn; load on bootstrap

**Exit:** Reload keeps the same thread; New chat starts a fresh one.

### Wave 2 — Past chats (P0)

- [ ] `GET /api/conversations` (+ messages by id)
- [ ] History sidebar (or compact drawer on mobile)
- [ ] Click → update URL → load messages
- [ ] Title = first user message truncated (or LibreChat title)

**Exit:** Demo can switch between at least two saved chats after reload.

### Wave 3 — Hardening (P1)

- [ ] Loading / error empty states for history
- [ ] Don’t double-send full history if Agents API continues from id alone (optional)
- [ ] Stale list refresh after stream `onDone`
- [ ] Guard against navigating away mid-stream
- [ ] Basic test: proxy forwards id; list/get shape contract

### Wave 4 — Nice-to-have (P2)

- [ ] Rename / archive / delete
- [ ] Search
- [ ] Deep-link from Langfuse / run_id → related chat (if correlatable)
- [ ] Revisit ENGINEERING D12 wording (custom shell + history, not iframe)

---

## 8. Out of scope

- Multi-user auth / per-PM isolation (hackathon is single-operator)
- Syncing chat history into ClickHouse or Langfuse as a second transcript store
- Replacing the custom UI with a LibreChat iframe (possible long-term, not this plan)
- Mobile-first redesign beyond a collapsible history drawer
- Message editing / branching / regenerate

---

## 9. Success criteria

1. Reload with `?chat=<id>` shows the same messages that were present before reload.
2. “New chat” yields a new id; previous chats remain listable.
3. Past-chats UI shows prior conversations after at least one completed turn each.
4. Chat continue still drives MCP tools (interrogate → run → approve) on a restored thread.
5. No chat transcript tables required in ClickHouse if Option A works.

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| Agents API key cannot list/read convos | Fall back to Option B immediately after Wave 0 |
| LibreChat stores incomplete tool/assistant payloads | Normalize on restore; tolerate missing tool rows in UI |
| Client still re-sends full history + server also loads history → duplication | Spike message semantics; if duplicate, send only the new user turn when id is set |
| URL id vs Mongo id mismatch | Prefer server-echoed id after first response; migrate localStorage |
| History panel clutters demo layout | Collapsible; default open on desktop only if space allows |

---

## 11. Suggested first PR slice

Smallest vertical: **Wave 1 only** — `conversationId` in client + proxy + URL/localStorage + New chat, with **Option B file/JSON store** if the LibreChat spike is not done yet. Wave 2 can swap the store to LibreChat proxies without changing the UI contract in §5–§6.
