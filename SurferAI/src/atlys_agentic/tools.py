"""Atlys Agentic Tools Package Facade.

Aggregates and re-exports tools segregated by CUJ:
- tools_common: Shared data models, vector utilities, confidence scoring, visual snapshotting.
- tools_cuj1: CUJ 1 Schema Ingestion, ClickHouse Storage Architecture & DDL Evolution.
- tools_cuj2: CUJ 2 Telemetry Analytics, Multi-Cut Diagnosis & PM Insight Synthesis.
"""
from __future__ import annotations

from atlys_agentic import ch_client, chdb_client, clickhouse_mcp, paths

# 1. Common / Shared Tools & Models
from atlys_agentic.tools_common import (
    PlannedQuery,
    _assert_select_only,
    _columns_from_ddl,
    _flatten,
    _infer_type,
    _load_events,
    _sample_size_component,
    classify_table_engine,
    cosine_distance,
    embed_text,
    Tool_Emit_Viz,
    Tool_Score_Confidence,
    Tool_Validate_Invariants,
)

# 2. CUJ 1: Instrumentation Agent & Schema Ingestion Tools
from atlys_agentic.tools_cuj1 import (
    Tool_Build_Context_Package,
    Tool_Consult_Internal_Tables,
    Tool_Context_Diff,
    Tool_Context_Upsert,
    Tool_Decide_Strategy,
    Tool_Emit_Submission_Artifacts,
    Tool_Execute_DDL,
    Tool_Explain_Schema_Rationale,
    Tool_Generate_MV,
    Tool_Infer_Schema,
    Tool_Infer_Table_Name,
    Tool_Load_Events,
    Tool_Refresh_CHDB_From_Live,
    Tool_Write_Table_Semantics,
)

# 3. CUJ 2: Analytics Agent & Telemetry Diagnostics Tools
from atlys_agentic.tools_cuj2 import (
    BASE_TABLE_SEMANTICS,
    Tool_Analytics_Compute,
    Tool_Bootstrap_Base_Semantics,
    Tool_Check_Queries,
    Tool_Derive_Signals,
    Tool_Emit_CUJ2_Submission_Artifacts,
    Tool_Live_Probe,
    Tool_Load_Table_Semantics,
    Tool_Match_Known_Issue,
    Tool_Persist_Insight_CUJ2,
    Tool_Plan_Queries,
    Tool_Resolve_And_Answerability,
    Tool_Result_Audit,
    Tool_Semantic_Retrieval,
    Tool_Synthesize_Insight,
)

# 4. Orchestrator Tools
from atlys_agentic.tools_orchestrator import (
    Tool_Batch_Scan_Specs,
    Tool_Discover_Workspace_Paths,
    Tool_Resolve_Path_Or_Spec,
)

# Aliases
infer_table_name_from_spec_or_id = Tool_Infer_Table_Name

__all__ = [
    # Common
    "PlannedQuery",
    "_flatten",
    "_infer_type",
    "_load_events",
    "_columns_from_ddl",
    "_assert_select_only",
    "classify_table_engine",
    "cosine_distance",
    "embed_text",
    "_sample_size_component",
    "Tool_Score_Confidence",
    "Tool_Validate_Invariants",
    "Tool_Emit_Viz",
    # CUJ 1
    "Tool_Infer_Table_Name",
    "infer_table_name_from_spec_or_id",
    "Tool_Infer_Schema",
    "Tool_Generate_MV",
    "Tool_Consult_Internal_Tables",
    "Tool_Explain_Schema_Rationale",
    "Tool_Execute_DDL",
    "Tool_Context_Diff",
    "Tool_Context_Upsert",
    "Tool_Refresh_CHDB_From_Live",
    "Tool_Build_Context_Package",
    "Tool_Decide_Strategy",
    "Tool_Load_Events",
    "Tool_Write_Table_Semantics",
    "Tool_Emit_Submission_Artifacts",
    # CUJ 2
    "Tool_Analytics_Compute",
    "Tool_Semantic_Retrieval",
    "Tool_Load_Table_Semantics",
    "Tool_Live_Probe",
    "Tool_Resolve_And_Answerability",
    "Tool_Match_Known_Issue",
    "Tool_Plan_Queries",
    "Tool_Check_Queries",
    "Tool_Result_Audit",
    "Tool_Derive_Signals",
    "Tool_Synthesize_Insight",
    "Tool_Persist_Insight_CUJ2",
    "Tool_Emit_CUJ2_Submission_Artifacts",
    # Orchestrator
    "Tool_Resolve_Path_Or_Spec",
    "Tool_Discover_Workspace_Paths",
    "Tool_Batch_Scan_Specs",
]
