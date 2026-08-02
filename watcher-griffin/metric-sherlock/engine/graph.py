"""The Investigation Engine's orchestration, reapproached with LangGraph.

Every node below is a thin wrapper around the SAME engine functions already
built and tested (baseline.check_baseline, decompose.decompose_revenue,
rank.rank_dimensions, drilldown.drilldown, rule_out.*, evidence.build_evidence,
narrator.narrate) -- no query logic, no contribution math, no SQL is
rewritten here, only the sequencing. What LangGraph buys over the previous
hand-rolled Python sequence: genuine recursive drill-down as a graph node
that loops back on itself (keep drilling into whichever dimension still
concentrates the deviation) until either nothing concentrates enough to
matter, or engine/config.py's max_drilldown_depth is hit -- instead of a
hardcoded two-level special case.

Hard constraint carried over unchanged: this graph only sequences
deterministic ClickHouse-backed Python calls. No node lets an LLM decide
what to query -- narrate is the only LLM-touching node, it runs last, and it
only sees the already-built EvidenceBundle (see engine/narrator.py).
"""

from datetime import datetime
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from engine.baseline import BaselineResult, check_baseline
from engine.ch_client import Trace, get_client
from engine.config import REVENUE_DECOMPOSITION_FACTORS, settings
from engine.decompose import DecomposeResult, decompose_revenue
from engine.drilldown import drilldown
from engine.evidence import EvidenceBundle, build_evidence
from engine.narrator import NarrationResult, narrate
from engine.rank import rank_dimensions
from engine.rule_out import check_seasonality, rule_out_dimensions, rule_out_factors


class InvestigationState(TypedDict, total=False):
    metric: str
    window_start: datetime
    window_end: datetime
    trace: Trace
    metric_baseline: BaselineResult
    decompose_result: Optional[DecomposeResult]
    primary_factor: str
    levels: list  # list[list[DimensionRanking]] -- one entry per recursion depth
    filters: list  # accumulated [(dimension, value), ...] chain from every prior level
    excluded_dimensions: set
    depth: int
    ruled_out: list
    evidence: EvidenceBundle
    narration: NarrationResult


def node_baseline(state: InvestigationState) -> dict:
    result = check_baseline(get_client(), state["trace"], state["metric"], state["window_start"], state["window_end"])
    return {"metric_baseline": result}


def should_decompose(state: InvestigationState) -> str:
    return "decompose" if state["metric"] == "revenue" else "set_primary_factor"


def node_decompose(state: InvestigationState) -> dict:
    """Every factor baseline is derived from the windows node_baseline ALREADY
    fetched -- see check_baseline's `windows` parameter. A WindowStats carries all
    five raw measures, so requests/fill_rate/render_rate/ecpm over the same range need
    no further data, and this node now issues zero queries where it used to issue 20
    serial ones for numbers already in memory."""
    client = get_client()
    windows = state["metric_baseline"].windows
    factor_baselines = {
        factor: check_baseline(client, state["trace"], factor, state["window_start"],
                               state["window_end"], windows=windows)
        for factor in REVENUE_DECOMPOSITION_FACTORS
    }
    result = decompose_revenue(state["metric_baseline"], factor_baselines)
    return {"decompose_result": result, "primary_factor": result.primary_factor}


def node_set_primary_factor(state: InvestigationState) -> dict:
    """Non-revenue metrics skip decomposition entirely -- the requested
    metric itself is what gets ranked/drilled."""
    return {"primary_factor": state["metric"]}


def node_rank(state: InvestigationState) -> dict:
    rankings = rank_dimensions(state["primary_factor"], state["window_start"], state["window_end"], state["trace"])
    top = rankings[0] if rankings else None
    if top is not None and top.top_segment is not None:
        filters = [(top.dimension, top.top_segment.value)]
        excluded = {top.dimension}
    else:
        filters, excluded = [], set()
    return {"levels": [rankings], "filters": filters, "excluded_dimensions": excluded, "depth": 0}


def should_keep_drilling(state: InvestigationState) -> str:
    levels = state.get("levels") or []
    if not levels or not levels[-1]:
        return "rule_out"
    top = levels[-1][0]  # rank_dimensions/drilldown both sort by |share_of_total_delta| desc
    if top.top_segment is None:
        return "rule_out"
    if abs(top.top_segment.share_of_total_delta) < settings.drilldown_concentration_threshold:
        return "rule_out"
    if state["depth"] + 1 >= settings.max_drilldown_depth:
        return "rule_out"
    return "drilldown"


def node_drilldown(state: InvestigationState) -> dict:
    rankings = drilldown(
        state["primary_factor"], state["filters"], state["excluded_dimensions"],
        state["window_start"], state["window_end"], state["trace"],
    )
    new_levels = state["levels"] + [rankings]
    top = rankings[0] if rankings else None
    new_filters = list(state["filters"])
    new_excluded = set(state["excluded_dimensions"])
    if top is not None and top.top_segment is not None:
        new_filters.append((top.dimension, top.top_segment.value))
        new_excluded.add(top.dimension)
    return {"levels": new_levels, "filters": new_filters, "excluded_dimensions": new_excluded, "depth": state["depth"] + 1}


def node_rule_out(state: InvestigationState) -> dict:
    ruled_out = []
    if state.get("decompose_result") is not None:
        ruled_out.extend(rule_out_factors(state["decompose_result"]))
    ruled_out.extend(rule_out_dimensions(state["levels"][0]))
    ruled_out.append(check_seasonality(get_client(), state["trace"], state["window_start"], state["window_end"]))
    return {"ruled_out": ruled_out}


def node_evidence(state: InvestigationState) -> dict:
    evidence = build_evidence(
        metric=state["metric"],
        window_start=state["window_start"],
        window_end=state["window_end"],
        baseline_trailing_weeks=settings.baseline_trailing_weeks,
        metric_baseline_result=state["metric_baseline"],
        decompose_result=state.get("decompose_result"),
        levels=state["levels"],
        ruled_out_checks=state["ruled_out"],
        trace=state["trace"],
    )
    return {"evidence": evidence}


def node_narrate(state: InvestigationState) -> dict:
    return {"narration": narrate(state["evidence"])}


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        g = StateGraph(InvestigationState)
        g.add_node("baseline_check", node_baseline)
        g.add_node("decompose", node_decompose)
        g.add_node("set_primary_factor", node_set_primary_factor)
        g.add_node("rank", node_rank)
        g.add_node("drilldown", node_drilldown)
        g.add_node("rule_out", node_rule_out)
        g.add_node("evidence", node_evidence)
        g.add_node("narrate", node_narrate)

        g.add_edge(START, "baseline_check")
        g.add_conditional_edges("baseline_check", should_decompose, {"decompose": "decompose", "set_primary_factor": "set_primary_factor"})
        g.add_edge("decompose", "rank")
        g.add_edge("set_primary_factor", "rank")
        g.add_conditional_edges("rank", should_keep_drilling, {"drilldown": "drilldown", "rule_out": "rule_out"})
        g.add_conditional_edges("drilldown", should_keep_drilling, {"drilldown": "drilldown", "rule_out": "rule_out"})
        g.add_edge("rule_out", "evidence")
        g.add_edge("evidence", "narrate")
        g.add_edge("narrate", END)

        _compiled_graph = g.compile()
    return _compiled_graph


def run_graph(metric: str, window_start: datetime, window_end: datetime, trace: Trace) -> tuple:
    """Runs the graph end to end. Returns (evidence, narration) -- the same
    pair engine/pipeline.py's run_investigation() has always returned, so
    nothing above this layer (API, store, scanner, chat) needs to change."""
    initial_state: InvestigationState = {
        "metric": metric,
        "window_start": window_start,
        "window_end": window_end,
        "trace": trace,
        "levels": [],
        "filters": [],
        "excluded_dimensions": set(),
        "depth": 0,
        "ruled_out": [],
    }
    final_state = get_graph().invoke(initial_state, config={"recursion_limit": 50})
    return final_state["evidence"], final_state["narration"]
