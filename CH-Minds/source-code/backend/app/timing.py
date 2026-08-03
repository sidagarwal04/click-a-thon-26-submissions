"""Per-stage wall-clock timing. The clickhouse_ms/llm_ms split is what makes
"ClickHouse analyzes, the LLM only narrates" a measured claim, not just a
design assertion - stage names match the Langfuse span names 1:1."""
import time
from contextlib import contextmanager

_LATENCY_STATS_QUERY = """
    SELECT
        count() AS n,
        quantile(0.50)(total_ms) AS p50_ms,
        quantile(0.95)(total_ms) AS p95_ms,
        quantile(0.99)(total_ms) AS p99_ms,
        max(total_ms) AS max_ms,
        quantile(0.95)(clickhouse_ms) AS p95_clickhouse_ms,
        quantile(0.95)(llm_ms) AS p95_llm_ms
    FROM inmobi_rca.request_latencies
    WHERE endpoint = {endpoint:String}
"""


def log(admin_client, endpoint: str, timings_dict: dict) -> None:
    try:
        admin_client.insert(
            "inmobi_rca.request_latencies",
            [[endpoint, timings_dict["total_ms"], timings_dict["clickhouse_ms"], timings_dict["llm_ms"]]],
            column_names=["endpoint", "total_ms", "clickhouse_ms", "llm_ms"],
        )
    except Exception:
        pass


def stats(ro_client, endpoint: str) -> dict:
    row = ro_client.query(_LATENCY_STATS_QUERY, parameters={"endpoint": endpoint}).result_rows[0]
    n, p50, p95, p99, max_ms, p95_ch, p95_llm = row
    if not n:
        return {"endpoint": endpoint, "n": 0}
    return {
        "endpoint": endpoint,
        "n": int(n),
        "p50_ms": round(float(p50), 1),
        "p95_ms": round(float(p95), 1),
        "p99_ms": round(float(p99), 1),
        "max_ms": round(float(max_ms), 1),
        "p95_clickhouse_ms": round(float(p95_ch), 1),
        "p95_llm_ms": round(float(p95_llm), 1),
    }


class Timings:
    def __init__(self):
        self._stages: dict = {}
        self._counts: dict = {}
        self._start = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._stages[name] = self._stages.get(name, 0.0) + elapsed_ms
            self._counts[name] = self._counts.get(name, 0) + 1

    def measure(self, name: str, func):
        with self.stage(name):
            return func()

    def as_dict(self, clickhouse_stages=(), llm_stages=()) -> dict:
        total_ms = (time.perf_counter() - self._start) * 1000.0
        stages = {
            name: {"ms": round(ms, 1), "calls": self._counts[name]}
            for name, ms in self._stages.items()
        }
        clickhouse_ms = sum(self._stages.get(s, 0.0) for s in clickhouse_stages)
        llm_ms = sum(self._stages.get(s, 0.0) for s in llm_stages)
        return {
            "total_ms": round(total_ms, 1),
            "clickhouse_ms": round(clickhouse_ms, 1),
            "llm_ms": round(llm_ms, 1),
            "other_ms": round(max(0.0, total_ms - clickhouse_ms - llm_ms), 1),
            "stages": stages,
        }
