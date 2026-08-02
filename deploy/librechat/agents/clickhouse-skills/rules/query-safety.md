# Discovery and query-safety rules

First discover database/table metadata, columns and comments, engine, sorting
and partition key, and indexes. Start with counts and small samples. Before
any potentially expensive query use `EXPLAIN` or `EXPLAIN ESTIMATE`. Add an
appropriate filter, `LIMIT`, `max_execution_time`, and read/result bounds to
exploration and serving-query validation. Record the final verification query
in the decision trace.

Source rules: `agent-discovery-schema`, `agent-query-safety`.
