# Feature Context Graph

The context layer is a versioned semantic control plane above versioned physical schemas. It borrows the useful graph property of Atlassian's Teamwork Graph—typed entities connected by explicit relationships—while remaining purpose-built for product analytics.

## Node types

| Type | Purpose | Example |
|---|---|---|
| `business_domain` | Scope and north star | Atlys pre-purchase journey |
| `entity` | Stable business identity and grain | User, Application, Destination |
| `feature` | Product capability introduced by a spec | Express Checkout |
| `event` | Observed behavior with evidence | `otp_entered` |
| `table` / `column` | Physical address and schema version | `express_checkout_events_v1` |
| `dimension` | Governed analytical cut with explicit business meaning and aliases | observed event city, device category |
| `metric` | Numerator, denominator, grain, dimensions | Express completion rate |
| `funnel` | Ordered business journey | application → purchase |
| `role_profile` | Goals and answer contract by audience | Product Manager |
| `business_question` | Questions explicitly enabled by a feature | platform failure rate |
| `analysis_playbook` | Typed intent, evidence contract, and governed SQL strategy | platform failure v1 |
| `known_issue` | Evidence-aware caveat or hypothesis | K1 iOS OTP regression |
| `operating_principle` | Invariants for agents | aggregate in ClickHouse |

Edges such as `EMITS`, `STORED_IN`, `PRECEDES`, `COMPUTED_FROM`, `SEGMENTED_BY`, `GROUPS_BY`, `ENABLES_QUESTION`, `MAY_AFFECT`, and `INTERESTED_IN` make retrieval explainable. Every node and edge carries a status, confidence, source, and context version.

Physical presence does not automatically make a column a business dimension. The Context Agent promotes only profiled fields from the governed semantic catalog, records their meaning and aliases, and binds them to metrics. For example, `city` means the city observed on the entrant event; it does not mean residence, hometown, nationality, or travel destination. A requested dimension must be present in the current feature context and in the executed aggregate evidence before LLM synthesis is allowed.

## Version invariant

`context vN = context vN-1 + verified feature delta`

A delta is publishable only when the feature spec, observed event sample, approved schema, successful insert, and row verification agree. Context versions link to physical schema versions in `schema_registry`; open conflicts remain first-class rather than being silently resolved.

## Evolution test for each of five features

1. Before-add negative: the parent context must not claim knowledge of the feature.
2. After-add positive: the child context must answer the feature's declared PM questions.
3. Event semantics coverage: every observed event is linked to the feature and table.
4. Role-aware grounding: metric, grain, dimensions, guardrails, and allowed tables are explicit.
5. Version grounding: every insight cites its context and schema versions.
6. Regression preservation: all prior graph nodes remain addressable.
7. Isolated replay: replay each feature from v0 separately to detect accidental order dependence.
8. Declared-question coverage: every spec question must produce its required evidence or an explicit answerability boundary.
9. Distinct analysis plans: different intents must not silently reuse the same SQL.
10. Evidence completeness: requested dimensions and required aggregate fields must be present before synthesis; otherwise execution fails closed with an explicit trace step.

The five known specs are development tests. A sealed sixth feature remains the honest holdout for generalization.
