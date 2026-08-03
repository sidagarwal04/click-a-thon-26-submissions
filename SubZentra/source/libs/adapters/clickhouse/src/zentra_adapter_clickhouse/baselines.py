"""Report what Phase 2 actually costs and how long it actually takes.

Lives in the ClickHouse adapter because it is a read of the audit ledger and
nothing else — the same table, the same client, the same grants.

Deliberately built on the audit ledger rather than on a metrics vendor. Every
number below is already in ClickHouse, because an Agent Execution's model,
tokens, cost and latency are part of the Replay record and were being written
before this file existed. Answering "what does an Investigation cost?" by
standing up a second telemetry backend would mean paying twice to store the
same numbers, and the second copy would be the one nobody could audit.

**This reports observations. It does not set thresholds.** Every figure is
labelled with the window and the sample size it came from, and the exit code is
always zero, because a baseline that fails a build is a threshold wearing a
different hat — and #23 explicitly asks for baselines *without* inventing a
production threshold. Deciding that p95 Insight latency of 4.2s is too slow is
a product decision somebody makes with this output in hand.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

import clickhouse_connect

#: Percentiles worth reporting. p50 says what usually happens; p95 says what a
#: Tenant complains about. A mean would hide both.
_QUANTILES = (0.5, 0.95)


@dataclass(frozen=True, slots=True)
class AgentBaseline:
    agent_id: str
    model: str
    #: Derived from `event_type`, not from the `status` column. `status` on an
    #: agent row holds the *Investigation's* status ("running"), so grouping by
    #: it would put every execution in one bucket and quietly report failures
    #: as successes.
    #:
    #: Grouped rather than filtered to successes: a failed call still spends
    #: money and still takes time, and a budget that only counts the calls that
    #: worked is not a budget.
    outcome: str
    executions: int
    latency_p50_ms: float
    latency_p95_ms: float
    cost_p50_usd: float
    cost_p95_usd: float
    total_cost_usd: float
    total_tokens: int


_AGENT_QUERY = """
SELECT
    agent_id,
    coalesce(model, 'unknown') AS model,
    if(event_type = 'agent.execution_failed', 'failed', 'succeeded') AS outcome,
    count() AS executions,
    quantile({q50:Float64})(latency_ms) AS latency_p50,
    quantile({q95:Float64})(latency_ms) AS latency_p95,
    quantile({q50:Float64})(total_cost_usd) AS cost_p50,
    quantile({q95:Float64})(total_cost_usd) AS cost_p95,
    sum(total_cost_usd) AS cost_total,
    sum(input_tokens + output_tokens) AS tokens_total
FROM audit_entries
WHERE created_at >= now() - INTERVAL {days:UInt32} DAY
  AND agent_id IS NOT NULL
  -- `_started` rows carry no latency, cost or tokens; averaging them in would
  -- halve every figure below.
  AND event_type IN ('agent.execution_completed', 'agent.execution_failed')
GROUP BY agent_id, model, outcome
ORDER BY cost_total DESC
"""

#: Cost per Investigation, not per execution — the number that decides whether
#: the product is viable is what one Tenant question costs end to end.
_INVESTIGATION_QUERY = """
SELECT
    count() AS investigations,
    quantile({q50:Float64})(cost) AS cost_p50,
    quantile({q95:Float64})(cost) AS cost_p95,
    sum(cost) AS cost_total,
    quantile({q50:Float64})(span_ms) AS latency_p50,
    quantile({q95:Float64})(span_ms) AS latency_p95
FROM (
    SELECT
        investigation_id,
        sum(total_cost_usd) AS cost,
        dateDiff('millisecond', min(started_at), max(completed_at)) AS span_ms
    FROM audit_entries
    WHERE created_at >= now() - INTERVAL {days:UInt32} DAY
    GROUP BY investigation_id
)
"""


def _client():
    return clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "zentra_audit_app"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", "zentra_audit_app"),
        database=os.environ.get("CLICKHOUSE_DATABASE", "zentra_audit"),
        secure=os.environ.get("CLICKHOUSE_SECURE", "false").lower() == "true",
    )


def agent_baselines(client, *, days: int) -> list[AgentBaseline]:
    result = client.query(
        _AGENT_QUERY,
        parameters={"days": days, "q50": _QUANTILES[0], "q95": _QUANTILES[1]},
    )
    return [
        AgentBaseline(
            agent_id=row[0],
            model=row[1],
            outcome=row[2],
            executions=row[3],
            latency_p50_ms=float(row[4]),
            latency_p95_ms=float(row[5]),
            cost_p50_usd=float(row[6]),
            cost_p95_usd=float(row[7]),
            total_cost_usd=float(row[8]),
            total_tokens=int(row[9]),
        )
        for row in result.result_rows
    ]


def investigation_baseline(client, *, days: int) -> dict[str, float]:
    result = client.query(
        _INVESTIGATION_QUERY,
        parameters={"days": days, "q50": _QUANTILES[0], "q95": _QUANTILES[1]},
    )
    if not result.result_rows:
        return {}
    row = result.result_rows[0]
    return {
        "investigations": int(row[0]),
        "cost_p50_usd": float(row[1]),
        "cost_p95_usd": float(row[2]),
        "cost_total_usd": float(row[3]),
        "latency_p50_ms": float(row[4]),
        "latency_p95_ms": float(row[5]),
    }


def render(
    agents: list[AgentBaseline],
    investigations: dict[str, float],
    *,
    days: int,
) -> str:
    lines = [
        f"Phase 2 observed baselines — last {days} day(s)",
        "Observations, not thresholds. Read with the sample size.",
        "",
    ]
    if not investigations or not investigations.get("investigations"):
        lines.append("No Investigations in the window. Nothing to report.")
        return "\n".join(lines)

    count = int(investigations["investigations"])
    lines += [
        f"Per Investigation (n={count})",
        f"  cost   p50 ${investigations['cost_p50_usd']:.4f}"
        f"   p95 ${investigations['cost_p95_usd']:.4f}"
        f"   total ${investigations['cost_total_usd']:.2f}",
        f"  wall   p50 {investigations['latency_p50_ms']:.0f}ms"
        f"   p95 {investigations['latency_p95_ms']:.0f}ms",
        "",
        "Per Agent",
    ]
    for agent in agents:
        lines += [
            f"  {agent.agent_id} ({agent.model}) [{agent.outcome}], "
            f"n={agent.executions}",
            f"    latency p50 {agent.latency_p50_ms:.0f}ms"
            f"  p95 {agent.latency_p95_ms:.0f}ms",
            f"    cost    p50 ${agent.cost_p50_usd:.4f}"
            f"  p95 ${agent.cost_p95_usd:.4f}"
            f"  total ${agent.total_cost_usd:.2f}"
            f"  tokens {agent.total_tokens:,}",
        ]
    if count < 30:
        lines += [
            "",
            f"n={count} is too small for p95 to mean much. Treat the p50 as "
            "indicative and the p95 as an anecdote.",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    client = _client()
    try:
        print(
            render(
                agent_baselines(client, days=args.days),
                investigation_baseline(client, days=args.days),
                days=args.days,
            )
        )
    finally:
        client.close()
    # Always zero: see the module docstring. A baseline that can fail a build
    # is a threshold, and this one is deliberately not.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
