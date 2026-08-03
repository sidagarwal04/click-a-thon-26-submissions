# ClickHouse best-practice rules

Vendored from [ClickHouse/agent-skills](https://github.com/ClickHouse/agent-skills)
(`skills/clickhouse-best-practices/rules/`), Apache-2.0.

They live here rather than as a link so the Instrumentation Agent reasons from
the **actual rule text**, and so a citation like `schema-pk-cardinality-order`
in a trace resolves to something a reviewer can read in this repo.

## Provenance

Retrieved over HTTP, not from a clone — a few were reconstructed from the
upstream content rather than copied byte-for-byte. Re-sync against a clone
before relying on exact wording:

    git clone --depth 1 https://github.com/ClickHouse/agent-skills.git /tmp/ch-skills
    make sync-rules CH_SKILLS=/tmp/ch-skills

Only the rules that bear on schema design are here. Join and insert rules
(`query-join-*`, `insert-*`) matter for the Analytics Agent and are not yet
vendored.
