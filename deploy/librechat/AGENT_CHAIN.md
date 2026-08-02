# Agent Chain Deployment Guide

## Purpose

The configured agent workflow is a sequential hand-off chain:

```text
instrumentation-agent -> analytics-agent -> aggregate-analyst
                       -> evidence-reviewer -> context-agent
                       -> finalizer-agent -> PM-facing report
```

Instrumentation and Analytics are invoked by the detached UI runner through
LibreChat's authenticated Agents API. Analytics then uses persisted LibreChat
agent edges for its bounded analyst/reviewer/context/finalizer chain. The
bootstrap script refreshes these persisted edges and instructions from the
checked-in runtime contracts.

| Agent | May invoke | Final output |
| --- | --- | --- |
| `instrumentation-agent` | none; runner invokes Analytics after persistence | Verified instrumentation catalogue |
| `analytics-agent` | `aggregate-analyst` | Analytics hand-off |
| `aggregate-analyst` | `evidence-reviewer` | Aggregate evidence |
| `evidence-reviewer` | `context-agent` | Reviewed analytics hand-off |
| `context-agent` | `finalizer-agent` | Enriched context |
| `finalizer-agent` | none | PM-facing report |

`allowSelf: false` prevents a stage from recursively calling itself. The
global `recursionLimit: 100` accommodates the bounded tool and subagent turns
while the graph remains acyclic.

## Runtime observability

LibreChat emits runtime traces to Langfuse using the configured Langfuse
environment settings. The OpenTelemetry collector receives LibreChat OTLP
traffic and exports traces, metrics, and logs to ClickHouse tables consumed by
ClickStack/HyperDX. Use Langfuse for prompt/tool/span-level debugging and
ClickStack for service health, latency, error, and throughput views.

The investigation state tables in ClickHouse are the business workflow audit;
they are not a replacement for Langfuse traces or ClickStack telemetry.

## Adding Subagents to Any Agent

Every agent in the chain can own a set of child subagents. A child is not a
directory nested beneath its parent in the LibreChat UI; it is a separate
`modelSpecs` entry whose ID is explicitly allowed by the parent's
`subagents.agent_ids` list.

For example, an `integration-agent` can delegate work to three specialists:

```yaml
- name: "integration-agent"
  label: "Integration Agent"
  preset:
    endpoint: "OpenAI"
    model: "gpt-5.6-luna"
    subagents:
      enabled: true
      allowSelf: false
      agent_ids:
        - "api-integration-agent"
        - "webhook-integration-agent"
        - "data-integration-agent"
    promptPrefix: |
      Delegate API, webhook, and data-pipeline work only to the matching
      specialist. Preserve each child result and return one combined payload.
```

Each permitted child needs its own entry and instruction file. A leaf agent
does not delegate further:

```yaml
- name: "api-integration-agent"
  label: "API Integration Agent"
  preset:
    endpoint: "OpenAI"
    model: "gpt-5.6-luna"
    subagents:
      enabled: false
      allowSelf: false
      agent_ids: []
    promptPrefix: |
      Produce an API integration payload for the parent agent.
```

To let a child invoke its own children, set that child's `enabled` value to
`true` and provide a new, narrowly scoped `agent_ids` list. Do not add a
parent to its descendant's list: keep the graph acyclic and use the global
recursion limit as a final safety guard.

When a parent delegates, every child should return a self-contained structured
payload with `handoff.from`, `handoff.to`, `status`, `result`, and `open_items`.
The parent includes those child payloads unchanged in its own result before it
returns to its parent or to the user.

## Recommended Integration Decomposition

Split an integration agent into focused child agents whenever one request
mixes source inspection, data-definition design, and implementation
verification. This keeps the primary `integration-agent` responsible for
planning, delegation, and final synthesis while specialists produce evidence
for one concern each.

Recommended children:

| Child agent | Responsibility | Required return to `integration-agent` |
| --- | --- | --- |
| `integration-inspector` | Inspect source systems, APIs, permissions, schemas, and integration constraints. | A verified inventory, assumptions, risks, and unresolved access requirements. |
| `ddl-mv-designer` | Design DDL, materialized views, data flow, refresh behavior, and rollback considerations. | Versioned DDL/MV proposals, dependencies, and operational trade-offs. |
| `ast-skill-verifier` | Validate generated queries, code, tools, or skill definitions against syntax and declared contracts. | Validation findings, corrected artifacts, and an explicit pass/fail status. |

Only the primary integration agent should be authorized to invoke these
specialists. Give it this explicit allowlist:

```yaml
- name: "integration-agent"
  label: "Integration Agent"
  preset:
    endpoint: "OpenAI"
    model: "gpt-5.6-luna"
    subagents:
      enabled: true
      allowSelf: false
      agent_ids:
        - "integration-inspector"
        - "ddl-mv-designer"
        - "ast-skill-verifier"
    promptPrefix: |
      You are the primary Integration Agent. Delegate inspection, DDL/MV
      design, and AST/skill validation only to the approved specialists.
      Combine their complete returned payloads into the final integration plan.
```

Define each specialist as a leaf agent with `subagents.enabled: false` and an
empty `agent_ids` list. Do not place these three IDs in another agent's
`agent_ids` list. This configuration makes the integration agent the only
agent authorized to call them. Add matching instruction files at:

```text
agents/integration-inspector/context.md
agents/ddl-mv-designer/context.md
agents/ast-skill-verifier/context.md
```

As with every agent, mirror each context file's instruction text into the
matching `promptPrefix` entry before deployment.

## Handoff Contract

Use a self-contained structured payload at each boundary. The receiving agent
must receive the preceding payload in full, retain unknown fields, and add its
own section rather than rewriting earlier work.

Instrumentation Agent returns a payload shaped like:

```yaml
schema_version: 1
request: <normalized user request>
instrumentation:
  events: []
  attributes: []
  triggers: []
  payload_examples: []
handoff:
  from: instrumentation-agent
  to: analytics-agent
```

Analytics Agent adds the analytics section and passes the complete object:

```yaml
analytics:
  metrics: []
  funnels: []
  dimensions: []
  aggregations: []
handoff:
  from: analytics-agent
  to: context-agent
```

Context Agent adds the final context section and returns the complete object
to the user:

```yaml
context:
  domain_metadata: {}
  environment_tags: []
  privacy_and_compliance: []
  operational_constraints: []
```

## Where Files and Results Live

Source-controlled agent instructions are kept here:

```text
deploy/librechat/agents/
  instrumentation-agent/context.md
  analytics-agent/context.md
  context-agent/context.md
```

At deployment, `deploy.sh` synchronizes this directory to
`/opt/LibreChat/agents/` on the VM. `deploy-compose.production.yml` mounts it
read-only into the API container at `/app/agents`.

The runtime hand-off and final response are part of the LibreChat conversation
and are persisted in LibreChat's MongoDB database. They are not automatically
written into `agents/` or the repository. Add a dedicated tool or integration
if a workflow needs durable files, a database table, or an external service as
an output destination.

## Keeping Instructions and Configuration in Sync

`context.md` files are the editable, source-controlled instructions. LibreChat
does not interpret `promptPrefix` as a file path, so the same instruction text
is intentionally copied into the matching `promptPrefix` in `librechat.yaml`.

When changing an agent:

1. Update its `agents/<agent-name>/context.md` file.
2. Update the matching `modelSpecs.list[].preset.promptPrefix` text in
   `librechat.yaml`.
3. Preserve the hand-off contract and adjust the downstream agent prompt when
   the payload schema changes.
4. Run `deploy.sh` to sync the YAML and `agents/` directory, then restart the
   API through the script's Compose deployment.

To add another stage, create its context directory, add a matching `modelSpec`,
and change the preceding stage's `subagents.agent_ids` to permit that single
downstream agent. Keep the graph acyclic unless recursion is intentional and
fits within the configured limit.
