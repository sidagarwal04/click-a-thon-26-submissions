# queries

`benchmark/` the fixed concurrency questions we are graded on (peak + average,
minute/hour/day grain, with dimension filters). `validation/` the slow-but-obviously-correct
brute-force versions we check the serving layer against.

Every benchmark query records its latency and what it read (`EXPLAIN`, or the
`query_log` rows/bytes) next to it: judges look at what the query reads, not just the wall clock.
