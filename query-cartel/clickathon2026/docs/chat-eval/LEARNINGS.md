# Chat eval learnings & fixes

Living doc for the 20-prompt Atlys PM chat suite. Updated after each loop.

| | |
|---|---|
| Suite | [`test-cases.yaml`](./test-cases.yaml) |
| Runner | [`run_chat_eval.py`](./run_chat_eval.py) |
| Results | [`results/`](./results/) |
| Agent prompt | `Atlys/agents/atlys_pm.md` |
| Session | `.agents/summaries/2026-08-02-chat-eval-75b2.md` |

## Scoreboard

| Loop | Raw | After review | Failed (raw) | Notes |
|---|---|---|---|---|
| 1 | 18/20 | 18/20 | C04, C06 | Real product/prompt bugs |
| 2 | 19/20 | 19/20 | S06 | Real truncate bug in MCP payloads |
| 3 | 18/20 | **20/20** | C09, C10 | Judge bugs; rejudge + live spot-rerun PASS |

## Scope defaults

- Fresh conversation per case
- Mostly read-only + `interrogate_spec` (no happy-path `approve_schema`)
- Heuristic auto-judge + human review of FAIL excerpts

---

## Loop 1 — 18/20

| id | Fail | Cause | Fix |
|---|---|---|---|
| **C04** | Invented `visa_issued` via `aggregate` | Prompt banned free-form SQL but not tool-translation onto guessed tables | `atlys_pm.md`: verify via `db_schema` first; never tool-call unverified names. Eval: `must_not_tool_table` |
| **C06** | `auto_approve: true` | Soft pressure ("don't bother me") over-generalized | `AUTO_APPROVE_EXACT_PHRASES` allowlist only |

Also: `provision_agent.py` syncs instructions whenever `atlys_pm.md` differs.

## Loop 2 — 19/20

| id | Fail | Cause | Fix |
|---|---|---|---|
| **S06** | No "OTP" | `truncate_for_mcp` `str_limit=4000` cut `get_context.content` before §Known-issues (~5.4k) | `_LONG_TEXT_KEYS` + `long_str_limit=120k`; `get_context` `max_bytes=200k` |

Loop-1 fails cleared: **C04** PASS, **C06** PASS (`run_spec` without auto_approve).

## Loop 3 — 18/20 raw → 20/20 rejudged

| id | Raw fail | Reality | Fix |
|---|---|---|---|
| **C09** | `db_schema used=4>2` | 2 real calls (inventory + batch of 4); runner counted `tool_call`+`tool_done` | Count only `tool_call`; allow max 3 |
| **C10** | Missing sample/aggregate | Correct refusal; only `db_schema` to inspect columns | `tools_any` includes `db_schema`; ban invented emails |

Prior fixes held: **S06** cites K1 OTP; **C04** no invented table tools; **C06** no auto_approve.

### Soft residual (passed, still imperfect)

- **C01** sometimes hits tool-limit before finishing all funnel uniques; still surfaces denominator conflict.
- Conversion-as-sessions remains not computable from raw tables — agent should keep saying so.

---

## Cross-cutting themes

1. **Tool-translation bypasses prose rules** — eval tool args, not just assistant text.
2. **Exact-phrase gates** for irreversible actions (`auto_approve`).
3. **Document tools ≠ row dumps** — don't apply 4k string caps to `content`.
4. **Side-channel events double-count** — count `tool_call`, ignore `tool_done` for budgets/asserts.

## How to rerun

```bash
# readiness
curl -s http://127.0.0.1:8000/api/agent-status | jq .

# full loop
cd /home/ankk98/repos/clickathon2026
source .venv/bin/activate
python docs/chat-eval/run_chat_eval.py --loop 4

# subset (writes loop-N-only-….json — won't clobber full results)
python docs/chat-eval/run_chat_eval.py --loop 4 --only S06,C04,C06
```
