# Governed Analytics Agent

The production Analytics Agent is a constrained pipeline rather than an unconstrained text-to-SQL chatbot.

1. Pin the published context version and verified schema version.
2. Resolve the role, feature, question intent, metric grain, allowed dimensions, known issues, and answerability boundary.
3. Compile one ontology-linked query playbook that can read only its allowlisted ClickHouse tables.
4. Execute aggregation in ClickHouse; never pull raw event rows into the LLM.
5. Produce a deterministic evidence-backed draft.
6. Optionally send the analysis contract, compact context slice, aggregate evidence, limitations, and draft to an OpenAI-compatible LLM.
7. Validate that every required aggregate and requested dimension was returned. Fail closed before synthesis when evidence is incomplete.
8. Validate the structured JSON response. Preserve the original evidence, SQL, trace ID, context version, and schema version. Cap LLM confidence at the deterministic evidence confidence.
8. Fall back to the deterministic draft on timeout, provider failure, malformed JSON, missing fields, or unsafe confidence.

The `analytics.llm_synthesize` OpenTelemetry span records the provider, model, prompt version, role, playbook, context version, governed input, and validated output. Langfuse therefore shows both the deterministic query phase and the generation phase in one trace.

## Feature decision bundle

After the declared questions complete, the Analytics Agent publishes one feature-level decision bundle. Three additional governed ClickHouse plans provide:

- a unique-entity event funnel;
- a weekly completion-rate trend, switching to monthly for longer ranges;
- ranked completion cuts across the verified device, OS, geography, destination, channel, group-size, and currency dimensions that are actually present.

The bundle contains chart-ready aggregate series, KPI values, the three highest-priority role-aware actions, context and schema versions, and the exact SQL and aggregate output for each dashboard query. The LLM does not calculate or modify KPI and chart values. A partial query failure degrades the corresponding visual instead of fabricating evidence or failing the complete feature run.

## Portfolio conversation

`POST /api/conversations` accepts an open business question, role, optional feature scope, the active feature scope from the prior answer, and recent conversation history. The Analytics Agent:

1. resolves explicit feature names, portfolio language, and follow-up references;
2. carries the previous feature scope when the next question is contextual;
3. compiles and executes one governed analysis contract per selected feature;
4. keeps incompatible feature entity identifiers and event definitions separate;
5. synthesizes the resulting aggregate evidence into a portfolio answer;
6. returns question-relevant charts, source feature answers, follow-up prompts, and a complete trace.

Trend, segment-comparison, and funnel-diagnosis follow-ups compile to dedicated ClickHouse plans. Cross-feature completion charts use the published entry event, completion event, and semantic entity grain for each feature; they are product-health comparisons, not shared-population experiments. Unsupported questions still fail closed at the individual feature contract.

## Runtime configuration

```text
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=...
LLM_TIMEOUT=30s
LLM_PROMPT_VERSION=analytics-insight:v1
```

With no key or model, the service remains fully functional in deterministic mode. `/health` reports the active Analytics Agent mode, and every insight includes provenance.

For OpenRouter, use `LLM_PROVIDER=openrouter`, `LLM_BASE_URL=https://openrouter.ai/api/v1`, and an OpenRouter model slug. The adapter requests strict JSON Schema output and requires OpenRouter to route only to providers that support the requested structured-output parameters.
