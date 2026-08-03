# ZentraOS Domain

ZentraOS turns recurring business-metric questions into investigations whose claims can be verified and replayed.

## Tenancy and identity

**Tenant**:
A customer organization whose data, policies, costs, and investigations are isolated from every other customer.
_Avoid_: Account, Clerk organization

**User**:
A human identity that may participate in more than one Tenant.
_Avoid_: Tenant user, account

**Membership**:
The relationship granting a User one role—owner, admin, member, or viewer—inside a Tenant.
_Avoid_: User role, guest membership

**Group**:
A Tenant-visible organizational container for related Projects. A Group does
not create a separate authorization boundary.
_Avoid_: Team, workspace ACL

**Project**:
A Tenant-visible organizational container inside one Group for related
Investigation Threads. A Project does not create a separate authorization
boundary.
_Avoid_: Folder ACL, Investigation

## Investigation

**Investigation**:
One attempt to answer a specific business question using governed metrics and traceable evidence.
_Avoid_: Chat, query, run

**Investigation Thread**:
A Tenant-scoped, Project-owned linear conversation containing immutable
messages and zero or more linked Investigations. A Draft Thread may exist while
governed routing awaits clarification.
_Avoid_: Investigation, mutable chat session, Agent transcript

**Thread Message**:
An immutable user, router clarification, or safe system contribution to one
Investigation Thread. Agent progress belongs to the Work Feed, not messages.
_Avoid_: Prompt log, editable chat bubble, reasoning event

**Work Feed**:
A persisted, typed, public projection of Thread and Agent progress, ordered by
an atomically allocated Thread sequence and resumable without exposing prompts,
reasoning, SQL, raw rows, credentials, or provider bodies.
_Avoid_: Agent transcript, log stream, message history

**Visualization Brief**:
A strict factual projection of a published Finding used as the only input to
terminal presentation rendering.
_Avoid_: Prompt, query result, C1 response

**Investigation Replay**:
The ordered record that explains how an Investigation moved from its question to each claim and decision.
_Avoid_: Logs, reasoning dump

## Trust and semantics

**Human Approval**:
A blocking decision by a User that grants, rejects, or modifies work that cannot proceed autonomously.
_Avoid_: Agent approval, confirmation

**Audit Entry**:
An immutable, tenant-scoped fact about an investigation step containing process metadata and artifact references, never raw customer data.
_Avoid_: Log line, prompt record

**Semantic Metric**:
A governed business measure with one agreed definition and grain for a Tenant.
_Avoid_: Calculated field, raw SQL metric

**Semantic Model**:
An immutable Tenant-approved version of governed metrics, dimensions, relationships, classifications, and source mappings.
_Avoid_: Cube schema, inferred schema, data model

**Metric Draft**:
A proposed business measure with definition, formula, grain, filters, time behavior, units, and sources that has not entered an approved Semantic Model version.
_Avoid_: Ad hoc metric, calculated field
