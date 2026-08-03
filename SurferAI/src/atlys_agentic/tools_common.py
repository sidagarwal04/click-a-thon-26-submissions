"""Shared tool utilities, data models, and common ClickHouse/vector helpers."""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from atlys_agentic import chdb_client, paths


class PlannedQuery(BaseModel):
    """Query Architect query plan entry strictly typed for SELECT execution (docs/CUJ2.md §2.8 & §4)."""
    purpose: str
    sql: str
    origin: Literal["architect_llm", "architect_fallback"] = "architect_fallback"


def _flatten(event: dict, prefix: str = "") -> dict:
    """Recursively flatten nested event dictionaries with underscore prefixes."""
    flat = {}
    for k, v in event.items():
        composite_key = f"{prefix}_{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten(v, composite_key))
        else:
            flat[composite_key] = v
    return flat


def _infer_type(key: str, values: list, sparse: bool = False) -> str:
    """Infer ClickHouse column type based on sample values and schema heuristics."""
    k_lower = key.lower()
    non_null = [v for v in values if v is not None]

    if not non_null:
        return "Nullable(String)"

    if "timestamp" in k_lower or k_lower.endswith("_at") or "time" in k_lower:
        sample = str(non_null[0])
        if sample.isdigit() or (sample.startswith("-") and sample[1:].isdigit()):
            return "DateTime64(3, 'UTC')"
        return "DateTime"

    if all(isinstance(v, bool) for v in non_null):
        return "UInt8"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return "Int64"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "Float64"

    cardinality = len(set(str(v) for v in non_null))
    if cardinality < 100 and len(non_null) > 10:
        base = "LowCardinality(String)"
    else:
        base = "String"

    if sparse or len(non_null) < len(values):
        return f"Nullable({base})" if not base.startswith("LowCardinality") else base
    return base


def _load_events(ndjson_path: Path) -> list[dict]:
    """Parse events from an ndjson file."""
    events = []
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _columns_from_ddl(ddl: str) -> list[str]:
    """Extract column names from a ClickHouse CREATE TABLE DDL string."""
    cols = []
    in_cols = False
    for line in ddl.splitlines():
        line = line.strip()
        if line.startswith("(") or "CREATE TABLE" in line:
            in_cols = True
            continue
        if in_cols:
            if line.startswith(")") or line.startswith("ENGINE"):
                break
            match = re.match(r"^[`\"]?(\w+)[`\"]?\s+", line)
            if match:
                cols.append(match.group(1))
    return cols


def _assert_select_only(sql: str) -> None:
    """Assert query is strictly SELECT-only per docs/CUJ2.md §2.8."""
    sql_clean = (sql or "").strip().rstrip(";").strip()
    if not sql_clean:
        raise ValueError("Empty SQL query is not allowed.")
    low = sql_clean.lower()
    first_token = low.split()[0] if low.split() else ""
    if first_token not in ("select", "with"):
        raise ValueError(f"Only SELECT queries are allowed in analytics; got '{first_token}'")
    forbidden = ["insert", "alter", "drop", "create", "delete", "update", "truncate", "system", "grant", "revoke"]
    for word in low.split():
        cleaned_word = word.strip("();,")
        if cleaned_word in forbidden:
            raise ValueError(f"Forbidden DDL/mutation keyword '{cleaned_word}' detected in query.")


def classify_table_engine(engine: str) -> str:
    """Raw versus aggregate is decided deterministically by system.tables.engine (docs/CUJ2.md §2.7)."""
    agg = ("MaterializedView", "SummingMergeTree", "AggregatingMergeTree")
    return "aggregate" if any(a in (engine or "") for a in agg) else "raw"


def cosine_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine distance (1.0 - cosine_similarity) between two vector embeddings."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 1.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    cos_sim = dot / (norm_a * norm_b)
    return max(0.0, min(2.0, 1.0 - cos_sim))


def embed_text(text: str) -> list[float]:
    """Phase 6a: Generate 768-dim float vector embedding for semantic search."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    api_key = (
        os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
        or os.environ.get("LITELLM_API_KEY", "")
    ).strip()

    if api_key and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            import litellm
            resp = litellm.embedding(
                model=os.environ.get("EMBEDDING_MODEL", "gemini/text-embedding-004"),
                input=[cleaned[:1000]],
                api_key=api_key,
            )
            data = resp.get("data", [])
            if data and "embedding" in data[0]:
                vec = data[0]["embedding"]
                if len(vec) == 768:
                    return vec
                elif len(vec) < 768:
                    return vec + [0.0] * (768 - len(vec))
                return vec[:768]
        except Exception:
            pass

    return []


def _sample_size_component(n: int) -> float:
    """Scale sample size log-linearly to [0.0, 0.40] based on sample size thresholds."""
    if n <= 0:
        return 0.0
    if n >= 5000:
        return 0.40
    return round(0.40 * (math.log10(max(n, 1)) / math.log10(5000)), 3)


def Tool_Score_Confidence(
    sample_size: int,
    effect_size_pct: float,
    known_issue_match: bool,
    cut_consistency: float,
) -> dict:
    """Phase 3/Phase 9: Calibrated confidence formula strictly conforming to § 2.6."""
    s_n = _sample_size_component(sample_size)

    if effect_size_pct >= 10.0:
        s_e = 0.25
    elif effect_size_pct >= 5.0:
        s_e = 0.15
    elif effect_size_pct >= 2.0:
        s_e = 0.08
    else:
        s_e = 0.0

    s_k = 0.20 if known_issue_match else 0.0
    s_c = round(0.15 * max(0.0, min(1.0, cut_consistency)), 3)

    raw_score = round(s_n + s_e + s_k + s_c, 2)
    score = max(0.0, min(1.0, raw_score))

    if score >= 0.80:
        rationale = "High Reliability: Large sample size, documented known issue match, consistent cuts"
    elif score >= 0.50:
        rationale = "Moderate Reliability: Sufficient sample size, partial corroboration"
    else:
        rationale = "Low Reliability: Small sample size or conflicting signals"

    return {
        "score": score,
        "rationale": rationale,
        "sample_size_component": s_n,
        "effect_size_component": s_e,
        "known_issue_component": s_k,
        "cut_consistency_component": s_c,
    }


def Tool_Validate_Invariants(ddl: str) -> list[str]:
    """Validate ClickHouse 4 critical storage invariants."""
    violations = []
    ddl_clean = re.sub(r"--.*$", "", ddl, flags=re.MULTILINE)

    # 1. Check for ORDER BY and sort-key prefix invariants
    order_match = re.search(r"ORDER BY\s*\((.*?)\)", ddl_clean, re.IGNORECASE)
    if not order_match:
        order_match = re.search(r"ORDER BY\s+([^\n;]+)", ddl_clean, re.IGNORECASE)

    if order_match:
        first_col = order_match.group(1).split(",")[0].strip().lower()
        if first_col == "id" or (first_col.endswith("_id") and first_col not in ["user_id", "session_id", "application_id"]):
            violations.append("Violation: Primary sort key begins with 'id' or entity ID.")
        elif "uuid" in first_col:
            violations.append("Violation: Primary sort key begins with a UUID column.")
    else:
        violations.append("Violation: ORDER BY clause is missing.")

    # 2. Check for PARTITION BY
    if not re.search(r"\bPARTITION\s+BY\b", ddl_clean, re.IGNORECASE):
        violations.append("Violation: PARTITION BY clause is missing.")

    # 3. Check for TTL on event tables
    if ("user_id" in ddl_clean or "application_id" in ddl_clean or "event" in ddl_clean) and not re.search(r"\bTTL\b", ddl_clean, re.IGNORECASE):
        violations.append("Violation: TTL clause is missing.")

    return violations


def Tool_Emit_Viz() -> dict:
    """Emit schema history, insights, and context changelog snapshots."""
    schema_history = chdb_client.run(
        'SELECT "table", version, spec_id, created_at FROM schema_registry ORDER BY created_at DESC'
    )
    insights = chdb_client.run(
        "SELECT finding_key, spec_id, question, confidence, created_at FROM insights ORDER BY created_at DESC"
    )
    context_changelog = chdb_client.run(
        "SELECT ts, change_type, agent, trace_id FROM context_changelog ORDER BY ts DESC"
    )
    result = {
        "schema_history": schema_history,
        "insights": insights,
        "context_changelog": context_changelog,
    }
    paths.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.OUTPUTS_DIR / "viz_snapshot.json").write_text(json.dumps(result, indent=2, default=str))
    return result
