# Schema design rules

Use `ORDER BY` only after identifying likely filters from the specification
and observed profile. It is immutable, so record those query patterns first.
Put lower-cardinality, frequently filtered dimensions before date/time and
higher-cardinality identifiers; keep the key short. Validate with `EXPLAIN
indexes = 1` on representative serving queries.

Use native types when source values validate: `Date` for dates, `DateTime` or
`DateTime64` only to source precision, narrow signed/unsigned integers,
`Bool`, and exact `Decimal(P,S)` for money. Use `UUID` only for consistently
validated UUID values. Use `LowCardinality(String)` for repeated strings with
under roughly 10,000 distinct values; preserve opaque or evolving identifiers
as `String`. Avoid `Nullable` unless null is semantically different from a
documented default. Keep dynamic fields in typed JSON only when their shape is
actually variable and useful.

Partitioning supports lifecycle operations, not a substitute for a good sort
key. If retention/lifecycle is absent or volume is modest, use no partition.
If a time lifecycle is explicit, use a bounded time partition (normally
monthly), never an event/user/session partition. Add TTL only for an explicit
retention policy, aligned to that lifecycle.

Source rules: `schema-pk-plan-before-creation`,
`schema-pk-cardinality-order`, `schema-pk-prioritize-filters`,
`schema-types-native-types`, `schema-types-minimize-bitwidth`,
`schema-types-lowcardinality`, `schema-types-avoid-nullable`,
`schema-partition-low-cardinality`, `schema-partition-lifecycle`,
`schema-partition-start-without`.

