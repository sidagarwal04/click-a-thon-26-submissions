# Pointing LibreChat at the RCA backend

The backend exposes an OpenAI-compatible endpoint, so LibreChat treats it as a model provider.
No adapter or plugin is involved.

```
POST /v1/chat/completions      (also mounted at /chat/completions)
```

## librechat.yaml

```yaml
version: 1.2.8

endpoints:
  custom:
    - name: "RCA Analyst"
      apiKey: "not-required"          # no auth on the backend; must still be non-empty
      baseURL: "http://host.docker.internal:8000/v1"
      models:
        default: ["rca-analyst"]
        fetch: false                  # we do not implement GET /v1/models
      titleConvo: true
      titleModel: "rca-analyst"
      modelDisplayLabel: "RCA Analyst"
```

- `baseURL` must end in `/v1` — LibreChat appends `/chat/completions`. The endpoint is also
  mounted without the prefix, so `http://host.docker.internal:8000` works too.
- Use `host.docker.internal` when LibreChat runs in Docker and the backend runs on the host.
  Both in the same compose network: use the service name, e.g. `http://backend:8000/v1`.
- `fetch: false` matters. There is no `GET /v1/models`, and LibreChat will show an empty model
  list if it tries to discover them.

Start the backend with:

```bash
cd backend && uvicorn api.main:app --reload --port 8000
```

## What a conversation looks like

Slot filling collects what an investigation needs across turns, so the model never has to parse
a whole request in one shot.

```
you   ▸ why did revenue drop?
bot   ▸ Which time period should I investigate?
you   ▸ the 23rd
bot   ▸ Revenue fell 15.2% ... fill rate fell from 82% to 61% ...
        **Localized to:** country=IN AND os_version=Android 13 AND app_id=app_00123
        **Checked and ruled out:** request_volume, ctr_quality, ecpm_price, seasonality
        _investigation `a8982011-...`_ · [trace](...)
```

This works with no state machine on the LibreChat side, because LibreChat replays the whole
message history on every turn and the backend re-reads it. Turn 1 supplies the metric, turn 2
supplies the date.

## Response shape

A valid chat completion, with our fields alongside. OpenAI clients ignore unknown keys, so one
endpoint serves both LibreChat and the dashboard.

```jsonc
{
  "id": "chatcmpl-...", "object": "chat.completion", "created": 1785200000,
  "model": "rca-analyst",
  "choices": [{ "index": 0,
                "message": { "role": "assistant", "content": "Revenue fell 15.2% ..." },
                "finish_reason": "stop" }],

  // extensions — LibreChat ignores these, the dashboard reads them
  "contextId": "...",
  "template": { "metric": "revenue", "window": "2026-06-23/2026-06-24",
                "segment": null, "contextId": "..." },
  "isReadyForInvestigation": true,
  "missingFields": [],
  "investigation": { /* full EvidenceBundle */ },
  "verification": { "passed": true, "unverified_numbers": [] },
  "isPlottable": true, "plotKind": "metric_tree", "plotData": [ /* drilldown nodes */ ]
}
```

## Streaming

`stream: true` returns SSE: `data:` chunks carrying `choices[0].delta.content`, terminated by
`data: [DONE]`. LibreChat sends `stream: true` by default.

The analysis is **not** streamed. The pipeline runs to completion first and only the finished
text is chunked — deterministic work does not belong in a token stream, and it means a stream
can never emit a number the guardrail has not already verified.

## Sessions

Pass `X-Session-Id` to pin a conversation; otherwise LibreChat's `conversation_id` is used, and
failing that a fresh id is generated per request. That id becomes:

- `context_id` in `chat_sessions` / `chat_turns`
- `session_id` on the stored investigation
- the Langfuse session, so all traces from one conversation group together

## Current limitation

`_run_investigation` in `api/main.py` still returns the fixture bundle. The conversation,
routing, persistence, streaming and wire format are all real — only the analysis is stubbed.
It becomes real when Lane B's `build_bundle()` lands (JAL-79); that swap touches one function.

So the numbers in a reply are currently fixture values, not computed from ClickHouse. Do not
demo this as a real diagnosis until JAL-79 is merged.

## Verify it works

```bash
curl -s localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"rca-analyst","messages":[{"role":"user","content":"why did revenue drop on june 23?"}]}' \
  | python -m json.tool
```

Expect `isReadyForInvestigation: true` and a populated `investigation` object.
