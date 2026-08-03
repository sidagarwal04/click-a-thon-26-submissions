# Chat stream vs store truth — fix plan

> **Status:** Plan only — not implemented.
>
> **Audience:** Implementers of chat proxy / runs (`Atlys/service/chat_runs.py`, `api.py`), chat store (`chat_store.py`), and React shell (`Atlys/ui/src/components/chat/ChatPanel.jsx`, `api/client.js`).
>
> **Related:** Empty-stream incident (Langfuse `b8b7a32d…`, UI hint in `ChatPanel.jsx`); concurrency notes in `docs/chat-concurrency-analysis.md` (same-chat last-write-wins).
>
> **North star:** SSE is for **live paint only**. The server conversation store is the **source of truth**. The UI always **converges by polling / final GET** when a run ends — never commits an empty client buffer over a richer server transcript.

---

## 0. Problem

### Symptom

After native MCP tools finish, the UI sometimes shows:

> Tools finished, but no reply was streamed. Type **continue** if you want me to keep going.

Meanwhile Langfuse shows a completed agent turn with a full final `AIMessage` (`finish_reason: stop`, multi‑KB content). Tools ran; the answer existed upstream; Atlys never displayed it.

### Why it hurts

| Layer | What happened |
|---|---|
| LibreChat / LangGraph | Final generation completed (visible in Langfuse) |
| Atlys SSE → browser | Tool side-channel (`atlys_progress`) arrived; **no** (or incomplete) `delta.content` text events |
| UI `onDone` | `finalAssistantText === ''` → empty-stream hint; `PUT` full-replaces store |
| Poll path | Exists for disconnect/reload only — **not** used when the SSE subscription “succeeds” empty |

Correctness is tied to one flaky pipe (LibreChat Agents SSE + client parse). Background `ChatRun` persistence cannot save the day if (a) upstream never emits content deltas the builder understands, and/or (b) the client overwrites the store on done.

### Design mistake (concise)

We built **reconnect polling** but kept **client SSE buffer as the commit authority**. Polling should be the commit path; SSE should be a cache.

---

## 1. Current state

```
Browser ChatPanel
  → POST /api/proxy/chat (SSE subscriber)
  → ChatRun (background): LibreChat stream + progress_hub → broadcast SSE
       └─ _TranscriptBuilder periodically save_messages(status=running)
  → UI paints from SSE events (text / thinking / tool_*)
  → onDone: persistMessages(clientTranscript)  ← full replace, last-write-wins
  → startPolling only on stream disconnect / reload mid-run
```

| Piece | Role today | Gap |
|---|---|---|
| `ChatRun._TranscriptBuilder` | Best-effort server transcript from deltas + Atlys progress | Same parse limits as client; no LibreChat history backfill |
| `GET …/messages` + `status` | Reload / disconnect recovery | Not consulted after a “successful” empty stream |
| `PUT …/messages` from UI | Commit path | Overwrites server even when client saw less |
| Empty-stream hint | Avoid silent auto-continue loops | Treats empty **SSE** as empty **turn** |
| `client.js` `handleDelta` | String `delta.content` + reasoning fields | No array/`parts` content; no final non-delta message harvest |

**Key files**

- `Atlys/service/chat_runs.py` — background run, builder, persist
- `Atlys/service/chat_store.py` — `save_messages`, `get_status`
- `Atlys/service/api.py` — `proxy_chat`, conversation CRUD
- `Atlys/ui/src/api/client.js` — SSE parse
- `Atlys/ui/src/components/chat/ChatPanel.jsx` — paint, hint, `persistMessages`, `startPolling`

---

## 2. Target model

| Layer | Role |
|---|---|
| **SSE** | Optional accelerator — stream tokens and tool chips for snappy UX |
| **Server store** | Source of truth — `ChatRun` owns the running transcript; status `running` → `idle` |
| **Poll / final GET** | Commit — when the run ends (or SSE closes), UI **replaces** local state from `GET /conversations/{id}/messages` |

```
  LibreChat SSE --> ChatRun (+ progress_hub) --persist--> ChatStore
                         |
                         | fan-out SSE (paint only)
                         v
                   Browser cache
                         |
               on idle / stream end
                         v
              GET messages -> replace UI
```

**Hard rules**

1. Client must **never** full-replace the store with a transcript that has tools but no assistant answer if the server copy is richer (or still `running`).
2. “No reply streamed” means **store has no answer after `idle`**, not “my SSE buffer is empty.”
3. SSE death mid-turn must still converge via poll (already partly true — keep it).
4. Prefer **merge / server-wins** over blind `PUT` from the browser after a proxied run.

---

## 3. Phased plan

### Phase A — Stop the bleeding (UI commit path)

**Goal:** Empty SSE can no longer wipe or falsely finalize a turn.

1. **On stream end (`onDone` / natural close):**  
   - `GET /api/conversations/{id}/messages`  
   - If `status === 'running'` → `startPolling` (don’t hint, don’t idle-PUT).  
   - If `status === 'idle'` → **hydrate from store** into the UI (replace local transcript for that chat).

2. **Gate client `persistMessages` after a proxied run:**  
   - Do **not** `PUT` the client buffer as the final transcript when the turn used native tools (or always prefer server after `proxy/chat`).  
   - Allow client `PUT` only for: user message before send, explicit stop notes the server didn’t write, or offline/legacy paths if any.

3. **Empty-stream hint:**  
   - Fire only after hydrate/poll shows: tools present, no contentful assistant after the last user turn, status idle.  
   - Optional: if server has thinking but no content, show thinking / “answer buffered as thinking” instead of the continue hint.

4. **Same-chat race:** document that two tabs still last-write-wins until Phase D; Phase A at least stops *empty* client wins.

**Acceptance**

- Reproduce empty SSE (or mock `chatStream` with tools + no text): UI ends on server transcript, not hint, when builder had text.  
- If both client and server lack text → hint once (current copy OK).

### Phase B — Harden server transcript build

**Goal:** Store is more likely to hold the final answer even when the browser subscriber glitches.

1. **Normalize content in `_handle_delta` / shared helper** (mirror in `client.js`):  
   - `content: string`  
   - `content: [{ type: 'text', text }]` (and similar parts)  
   - Ignore empty arrays / nulls safely (no throw in think-tag splitter).

2. **On upstream `[DONE]` / run finally:**  
   - If the builder’s last user turn has tools but no contentful assistant text, attempt a **backfill** (in order of preference):  
     a. Last OpenAI-style chunk with `choices[0].message.content` (non-delta) if seen.  
     b. Optional: LibreChat messages API for `conversationId` if available and cheap.  
     c. Else leave empty — UI hint after idle is correct.

3. **Persist force on run completion** before broadcasting subscriber close (`done`), so the first poll after SSE end always sees the final builder state.

4. **Don’t persist the continue-hint from the client** into the store if the server already has a real answer (Phase A hydrate makes this moot; still avoid writing hints server-side).

**Acceptance**

- Unit tests: array content parts → `append_text`; string content unchanged.  
- Integration/fake upstream: tools then final message-only chunk → store has assistant text after `idle`.

### Phase C — Poll as first-class completion (UX)

**Goal:** Streaming feels live; completion always feels authoritative.

1. After send: keep SSE paint as today.  
2. When SSE ends **or** subscriber timeout while `status=running`: poll every ~1s (existing `startPolling`) until `idle`.  
3. On each poll tick: replace messages from store (already mostly does this) — avoid merging client-only hint rows over server.  
4. Loading / “Generating reply…” stays bound to `status === 'running'`, not to “SSE still open.”  
5. Stop button: server cancel + idle (existing) → one final GET.

**Acceptance**

- Reload mid-run and wait: final answer appears without re-sending.  
- SSE closes early while run continues: UI keeps polling and shows final text.  
- Happy path with good SSE: no visible double-flash worse than today (acceptable: one replace on idle).

### Phase D — Optional / later

| Item | Why later |
|---|---|
| ETag / revision on `save_messages` | Real multi-tab merge; concurrency doc already flags this |
| Server-side “continue” when idle + tools + no answer | Product choice; risk of tool re-entry loops (why hint exists) |
| Drop SSE entirely for tools-only turns | Not needed if store+poll is solid |
| LibreChat-version pin / upstream bugfix | Track separately if content never appears on the wire |

---

## 4. Concrete code changes (checklist)

### Server

- [ ] `chat_runs.py`: shared `normalize_delta_content(delta) -> str`  
- [ ] `chat_runs.py`: harvest non-delta `message.content` on final chunks  
- [ ] `chat_runs.py`: guarantee final `save_messages(..., status=idle)` before `done`  
- [ ] `chat_store.py` / `api.py` (optional): `PATCH` or “merge” save that rejects empty-assistant overwrite when existing messages have more assistant text for the same turn — *or* simply stop accepting client final PUT (Phase A)

### Client

- [ ] `client.js`: same content normalization; never pass non-strings into `splitThinkTags`  
- [ ] `ChatPanel.jsx`: onDone → GET (+ poll if running) → hydrate; remove final full-replace PUT for proxy turns  
- [ ] `ChatPanel.jsx`: empty-stream hint only after store-backed idle empty answer  
- [ ] `ChatPanel.jsx`: user-turn persist before send stays (reload safety)

### Tests

- [ ] Builder: multimodal content parts  
- [ ] API/UI contract: mock run idle with assistant text; client onDone with empty buffer still shows text after GET  
- [ ] Regression: disconnect mid-run still polls to completion  

### Docs / ops

- [ ] Update `docs/chat-concurrency-analysis.md` lifecycle diagram (store commit via poll, not client PUT)  
- [ ] One-line note in `Atlys/SETUP.md` or chat troubleshooting: empty hint ⇒ check store + Langfuse; prefer refresh over blind continue

---

## 5. Out of scope

- Fixing LibreChat/LangGraph so Agents SSE always emits `delta.content` (worth reporting upstream; not required for Atlys correctness if store+backfill work).  
- Multi-user ACL / Redis.  
- Re-enabling silent auto-continue for native MCP tools (still dangerous).  
- Recovering answers only present in Langfuse and never on any Atlys/LibreChat wire (ops/manual).

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Double UI update (SSE paint then GET replace) | Replace only on idle; keep message ids stable in builder where possible |
| Server builder also empty (upstream never streamed content) | Phase B backfill; hint remains valid fallback |
| Stale poll shows previous turn | Key off `status` + conversation id; clear pending rows on idle |
| Client-only edits lost | Demo has no client-only edits beyond hints/stop notes — write those via small server events or accept loss |

---

## 7. Success criteria

1. Langfuse-complete turn with tools + final text **never** ends as empty-stream hint if Atlys received that text on the proxy wire (any chunk shape we normalize).  
2. Browser SSE abort / empty client buffer **never** deletes a richer server transcript.  
3. Reload during generation still converges to the final answer without typing `continue`.  
4. Empty hint appears only when the idle store truly lacks a post-tool assistant answer.

---

## 8. Suggested implementation order

1. Phase A (half day) — highest user impact, smallest surface.  
2. Phase B content normalize + final persist (half day) + tests.  
3. Phase C polish (poll tied to status as primary completion signal).  
4. Phase D only if multi-tab or upstream backfill becomes necessary.

---

## 9. Incident anchors (for implementers)

- UI hint: `Atlys/ui/src/components/chat/ChatPanel.jsx` (`sawNativeTools && !finalAssistantText`)  
- SSE parse: `Atlys/ui/src/api/client.js` (`handleDelta`)  
- Server builder: `Atlys/service/chat_runs.py` (`_handle_delta`, `_persist`, `run` finally)  
- Example Langfuse export: local `trace-b8b7a32da12ef4684c67aede7a4cb0ab.json` — final gen had full content; Atlys store/UI did not.
