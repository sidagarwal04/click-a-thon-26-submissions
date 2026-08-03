"""Memory-free CrewAI agent personas.

No agent below sets CrewAI's native Short/Long/Entity memory — every context
an agent needs is passed in explicitly via task input or fetched at call time
through a tool, never recalled from opaque agent memory (see final_wiby.md
§2, the "no hidden LLM memory" principle).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from atlys_agentic import paths, tools

load_dotenv(paths.ATLYS_AGENTIC_DIR / "config" / ".env")
load_dotenv(paths.REPO_ROOT / ".env")

try:
    from crewai import Agent, LLM
    from crewai.tools import tool
except ImportError:  # pragma: no cover
    class LLM:  # type: ignore
        def __init__(self, model: str = "", is_litellm: bool = True, temperature: float = 0.0):
            self.model = model
            self.is_litellm = is_litellm
            self.temperature = temperature

    def tool(name: str):  # type: ignore
        def decorator(fn):
            fn.name = name
            return fn
        return decorator

    class Agent:  # type: ignore
        def __init__(
            self,
            role: str = "",
            goal: str = "",
            backstory: str = "",
            tools: list = None,
            llm=None,
            memory: bool = False,
            verbose: bool = True,
            allow_delegation: bool = False,
            max_iter: int = 5,
            **kwargs,
        ):
            self.role = role
            self.goal = goal
            self.backstory = backstory
            self.tools = tools or []
            self.llm = llm
            self.memory = memory
            self.verbose = verbose
            self.allow_delegation = allow_delegation
            self.max_iter = max_iter


def llm() -> LLM:
    """Routes through LiteLLM explicitly (is_litellm=True) rather than
    CrewAI's native per-provider SDKs, so LiteLLM's Langfuse callback
    (see tracing.init_litellm_callbacks) actually sees every call."""
    model = os.environ.get("LLM_MODEL", "gemini/gemini-3-flash-preview")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0"))
    return LLM(model=model, is_litellm=True, temperature=temperature)


@tool("consult_internal_tables")
def _consult_internal_tables_tool(spec_id: str, candidate_columns: list[str], table_name: str) -> dict:
    """Consult chDB schema_registry and business_context to inspect existing tables and determine strategy (CREATE_NEW, ALTER_EXISTING, REUSE_EXISTING)."""
    return tools.Tool_Consult_Internal_Tables(spec_id, candidate_columns, table_name)


@tool("infer_schema")
def _infer_schema_tool(ndjson_path: str, spec_md_text: str, table_name: str) -> str:
    """Infer a production ClickHouse DDL from an NDJSON event sample and spec text."""
    return tools.Tool_Infer_Schema(Path(ndjson_path), spec_md_text, table_name)


@tool("generate_mv")
def _generate_mv_tool(table_name: str, ddl: str) -> str:
    """Generate a materialized view DDL for a table, if one is justified."""
    return tools.Tool_Generate_MV(table_name, ddl)


@tool("explain_schema_rationale")
def _explain_schema_rationale_tool(table_name: str, ddl: str, mv_ddl: str, consultation: dict, spec_text: str) -> dict:
    """Explain the 6-pillar ClickHouse storage mechanics rationale (ORDER BY, PARTITION BY, LowCardinality, MV, TTL)."""
    return tools.Tool_Explain_Schema_Rationale(table_name, ddl, mv_ddl, consultation, spec_text)


@tool("execute_ddl")
def _execute_ddl_tool(ddl: str, table_name: str, spec_id: str) -> dict:
    """Execute approved DDL on ClickHouse Cloud and mirror it to schema_registry."""
    return tools.Tool_Execute_DDL(ddl, table_name, spec_id)


@tool("context_diff")
def _context_diff_tool(new_table: str, new_columns: list[str]) -> dict:
    """Diff a new table's columns against business_context; surface conflicts and gaps."""
    return tools.Tool_Context_Diff(new_table, new_columns)


@tool("context_upsert")
def _context_upsert_tool(section: str, key: str, definition: str, agent: str, trace_id: str) -> int:
    """Write a new versioned business_context row and a context_changelog entry."""
    return tools.Tool_Context_Upsert(section, key, definition, agent, trace_id)


@tool("analytics_compute")
def _analytics_compute_tool(select_sql: str) -> dict:
    """Run a read-only SELECT against ClickHouse Cloud and return JSON rows."""
    return tools.Tool_Analytics_Compute(select_sql)


@tool("score_confidence")
def _score_confidence_tool(
    sample_size: int, effect_size_pct: float, known_issue_match: bool, cut_consistency: float
) -> dict:
    """Score confidence in an insight from sample size, effect size, known-issue match, cut consistency."""
    return tools.Tool_Score_Confidence(sample_size, effect_size_pct, known_issue_match, cut_consistency)


_DEFAULT_AGENTS_CONFIG = {
    "instrumentation_agent": {
        "role": "Staff ClickHouse Systems & Telemetry Architect",
        "goal": (
            "Transform product feature specifications and raw telemetry event streams into production-grade, "
            "high-performance ClickHouse DDL and high-leverage Materialized Views with zero schema anti-patterns."
        ),
        "backstory": (
            "You are a veteran ClickHouse database architect specializing in high-throughput event telemetry "
            "and real-time analytical engines. Always lead ordering keys with query filter predicates (timestamp, user_id). "
            "Always partition raw tables by toYYYYMM(timestamp), strictly enforce LowCardinality types, apply 12-month TTLs, "
            "and only generate Materialized Views that earn their keep with clear justification."
        ),
        "allow_delegation": False,
        "verbose": True,
        "max_iter": 5,
    },
    "context_agent": {
        "role": "Lead Business-Logic Integrity Auditor & Context Gatekeeper",
        "goal": (
            "Maintain an authoritative, version-controlled business context layer in chDB, proactively detecting, "
            "versioning, and surfacing every schema contradiction, metric gap, or semantic drift."
        ),
        "backstory": (
            "You are the meticulous guardian of organizational business logic, metric definitions, and event schemas. "
            "You treat initial documentation and base context with rigorous, constructive skepticism. Diff every schema change, "
            "actively detect context traps (denominator ambiguity, data quality caveats, anti-patterns, boundary issues), "
            "and record versioned changelog entries with trace attribution."
        ),
        "allow_delegation": False,
        "verbose": True,
        "max_iter": 5,
    },
    "analytics_agent": {
        "role": "Principal Product Analytics & Growth Data Scientist",
        "goal": (
            "Deliver high-impact, PM-actionable product insights that uncover the root cause ('the why') behind "
            "funnel conversion changes, supported by multi-dimensional cuts and calibrated confidence scores."
        ),
        "backstory": (
            "You are a seasoned Principal Product Data Scientist who bridges complex ClickHouse analytics and executive "
            "product strategy. Never pull raw rows into context; push aggregation into ClickHouse, mandate 3-way multi-cuts "
            "(device_type, geoip_country_code, destination), match known platform issues (K1–K7), score confidence objectively, "
            "and eliminate all SQL/DB jargon for PM audiences."
        ),
        "allow_delegation": False,
        "verbose": True,
        "max_iter": 5,
    },
    "query_architect": {
        "role": "Staff ClickHouse Query & DDL Translation Architect",
        "goal": (
            "Render validated schema design intent, column structures, and analytical queries into highly performant, "
            "syntactically optimal ClickHouse DDL, Materialized Views, and SQL statements."
        ),
        "backstory": (
            "You are a precision SQL and DDL compiler specializing in ClickHouse Cloud syntax. "
            "You take structured design intent, column types, and field mappings from the Instrumentation Agent "
            "and translate them into clean CREATE TABLE, ALTER TABLE, CREATE MATERIALIZED VIEW, and INSERT statements. "
            "You never make schema design decisions on your own and you never execute queries against any database directly."
        ),
        "allow_delegation": False,
        "verbose": True,
        "max_iter": 5,
    },
}
# Legacy aliases
_DEFAULT_AGENTS_CONFIG["instrumentation_engineer"] = _DEFAULT_AGENTS_CONFIG["instrumentation_agent"]
_DEFAULT_AGENTS_CONFIG["context_librarian"] = _DEFAULT_AGENTS_CONFIG["context_agent"]
_DEFAULT_AGENTS_CONFIG["product_analyst"] = _DEFAULT_AGENTS_CONFIG["analytics_agent"]


def load_agents_config() -> dict:
    """Load agent persona configuration (role, goal, backstory, parameters) from YAML config file."""
    config_file = getattr(paths, "AGENTS_CONFIG_YAML", paths.ATLYS_AGENTIC_DIR / "config" / "agents.yaml")
    if config_file.exists():
        try:
            import yaml
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict) and loaded:
                    return loaded
        except Exception:
            pass
    return _DEFAULT_AGENTS_CONFIG


def build_instrumentation_agent() -> Agent:
    cfg = load_agents_config()
    agent_cfg = cfg.get("instrumentation_agent") or cfg.get("instrumentation_engineer", _DEFAULT_AGENTS_CONFIG["instrumentation_agent"])
    return Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"].strip(),
        tools=[
            _infer_schema_tool,
            _generate_mv_tool,
            _explain_schema_rationale_tool,
        ],
        llm=llm(),
        memory=False,
        verbose=agent_cfg.get("verbose", True),
        allow_delegation=agent_cfg.get("allow_delegation", False),
        max_iter=agent_cfg.get("max_iter", 5),
    )


def build_context_agent() -> Agent:
    cfg = load_agents_config()
    agent_cfg = cfg.get("context_agent") or cfg.get("context_librarian", _DEFAULT_AGENTS_CONFIG["context_agent"])
    return Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"].strip(),
        tools=[
            _consult_internal_tables_tool,
            _context_diff_tool,
            _execute_ddl_tool,
            _context_upsert_tool,
        ],
        llm=llm(),
        memory=False,
        verbose=agent_cfg.get("verbose", True),
        allow_delegation=agent_cfg.get("allow_delegation", False),
        max_iter=agent_cfg.get("max_iter", 5),
    )


def build_analytics_agent() -> Agent:
    cfg = load_agents_config()
    agent_cfg = cfg.get("analytics_agent") or cfg.get("product_analyst", _DEFAULT_AGENTS_CONFIG["analytics_agent"])
    return Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"].strip(),
        tools=[_analytics_compute_tool, _score_confidence_tool],
        llm=llm(),
        memory=False,
        verbose=agent_cfg.get("verbose", True),
        allow_delegation=agent_cfg.get("allow_delegation", False),
        max_iter=agent_cfg.get("max_iter", 5),
    )


def build_query_architect() -> Agent:
    cfg = load_agents_config()
    agent_cfg = cfg.get("query_architect", _DEFAULT_AGENTS_CONFIG["query_architect"])
    return Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"].strip(),
        tools=[],
        llm=llm(),
        memory=False,
        verbose=agent_cfg.get("verbose", True),
        allow_delegation=agent_cfg.get("allow_delegation", False),
        max_iter=agent_cfg.get("max_iter", 5),
    )


# Agent naming aliases matching problem statement and locked CUJ specifications
build_instrumentation_engineer = build_instrumentation_agent
build_context_librarian = build_context_agent
build_product_analyst = build_analytics_agent


@tool("resolve_path_or_spec")
def _resolve_path_or_spec_tool(input_str: str) -> dict:
    """Resolve raw directory path, file path, or spec slug into a validated spec directory."""
    from atlys_agentic import tools_orchestrator
    return tools_orchestrator.Tool_Resolve_Path_Or_Spec(input_str)


@tool("discover_workspace_paths")
def _discover_workspace_paths_tool(root_dir: str = "") -> list:
    """Discover all available spec directories and telemetry datasets across the workspace."""
    from atlys_agentic import tools_orchestrator
    return tools_orchestrator.Tool_Discover_Workspace_Paths(root_dir or None)


@tool("batch_scan_specs")
def _batch_scan_specs_tool(folder_path: str) -> list:
    """Recursively scan a parent folder for all valid spec directories ready for ingestion."""
    from atlys_agentic import tools_orchestrator
    return tools_orchestrator.Tool_Batch_Scan_Specs(folder_path)


def build_orchestrator_agent() -> Agent:
    """Build the front-door Orchestrator Agent responsible for path resolution,
    workspace discovery, intent routing, and multi-spec batch coordination."""
    return Agent(
        role="Atlys Systems Orchestrator & Concierge",
        goal="Parse raw user requests, resolve filesystem directory paths and feature specs, discover workspace datasets, and coordinate CUJ 1 and CUJ 2 flows seamlessly.",
        backstory="""You are the lead Systems Orchestrator for Atlys Agentic Analytics. You understand developer intent,
fuzzy directory paths, multi-spec batch ingestion workflows, and catalog discovery. You resolve ambiguous paths to verified
spec packages and dispatch tasks cleanly to the Instrumentation Engineer or Product Analyst.""",
        tools=[_resolve_path_or_spec_tool, _discover_workspace_paths_tool, _batch_scan_specs_tool],
        llm=llm(),
        memory=False,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )




