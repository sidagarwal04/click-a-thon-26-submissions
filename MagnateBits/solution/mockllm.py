"""Deterministic mock LLM backend (ported from `loop`, generalized).

Purpose: run the ENTIRE pipeline — including the interpret/insight LLM calls — with
zero credentials and zero network, deterministically, for reproducible eval and offline
development. `solution` already has a no-LLM *deterministic path* for schema proposal
(`build_fallback_proposal`), but the analytics interpret step and any other
`complete_json`/`complete_text` call still need a model. This backend fills that gap.

Design: because `llm.complete_json()` embeds the FULL JSON Schema of the expected pydantic
type into the system prompt, this mock parses that schema and synthesizes a *schema-valid*
instance — so it works across contract types (DDLProposal, QueryPlan, DraftReport, …)
without knowing them, which is strictly more general than a tag-routed stub. It honours the
common JSON-Schema keywords (types, enum/const, $ref, anyOf/oneOf/Optional, required,
min/max, exclusive bounds, multipleOf, min/maxItems, min/maxLength, pattern, prefixItems);
a truly exotic constraint (e.g. an interdependent multi-field validator) could still slip
through, in which case that one call burns its retries and `complete_json` raises — the mock
is for offline/eval convenience, not a substitute for validating against a real model.

Opt-in only: activated by `ATLYS_LLM_BACKEND=mock`. The default (`cli`) and `api` backends
are untouched. Nothing about `solution`'s "LLM proposes, SQL adjudicates" thesis changes —
the mock's output still passes through every downstream deterministic gate (lint, dry-run,
grounding, evidence reconciliation), so a mock run degrades in insight *prose quality*, never
in correctness or safety.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def _seed(system: str, user: str) -> int:
    return int(hashlib.md5((system + "\x00" + user).encode()).hexdigest(), 16)


def _extract_schema(system: str) -> dict | None:
    """llm._JSON_RULES appends 'JSON Schema:\\n{...}'. Recover that object."""
    marker = "JSON Schema:"
    idx = system.rfind(marker)
    if idx == -1:
        return None
    tail = system[idx + len(marker):].strip()
    start = tail.find("{")
    if start == -1:
        return None
    # STRING-AWARE brace matching: braces inside JSON string values (e.g. a `description`
    # containing a literal '{') must not throw off the depth counter.
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(tail)):
        c = tail[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(tail[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _pick_number(rng: int, lo: float, hi: float) -> float:
    span = hi - lo
    return lo + (rng % 1000) / 1000.0 * span


def _synth(schema: dict, defs: dict, rng: int, key_hint: str = "", depth: int = 0) -> Any:
    """Synthesize a schema-valid value. Deterministic in `rng`; varies output per field."""
    if depth > 8:
        return None
    # $ref resolution
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return _synth(defs.get(ref, {}), defs, rng, key_hint, depth + 1)
    # anyOf/oneOf (e.g. Optional[...]): prefer the first non-null branch
    for combiner in ("anyOf", "oneOf", "allOf"):
        if combiner in schema:
            branches = [b for b in schema[combiner] if b.get("type") != "null"] or schema[combiner]
            return _synth(branches[0], defs, rng, key_hint, depth + 1)
    if "enum" in schema and schema["enum"]:
        vals = schema["enum"]
        return vals[rng % len(vals)]
    if "const" in schema:
        return schema["const"]

    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0])

    if t == "object" or ("properties" in schema):
        out: dict[str, Any] = {}
        props = schema.get("properties", {})
        required = set(schema.get("required", list(props.keys())))
        for i, (name, subschema) in enumerate(props.items()):
            if name in required or (rng >> (i % 16)) & 1:
                out[name] = _synth(subschema, defs, rng * 31 + i * 7 + 1, name, depth + 1)
        return out
    if t == "array":
        # typed tuple (JSON-Schema prefixItems / pydantic tuple[...]): one value per position
        if "prefixItems" in schema:
            pref = schema["prefixItems"]
            return [_synth(s, defs, rng * 17 + j * 13 + 3, key_hint, depth + 1)
                    for j, s in enumerate(pref)]
        items = schema.get("items", {"type": "string"})
        n = 1 + (rng % 2)  # 1-2 items — enough to be valid, small enough to be cheap
        n = max(n, schema.get("minItems", 0))
        if schema.get("maxItems") is not None:
            n = min(n, schema["maxItems"])
        return [_synth(items, defs, rng * 17 + j * 13 + 3, key_hint, depth + 1) for j in range(n)]
    if t == "integer":
        lo = schema.get("minimum")
        if lo is None and "exclusiveMinimum" in schema:
            lo = schema["exclusiveMinimum"] + 1
        lo = int(lo if lo is not None else 0)
        hi = schema.get("maximum")
        if hi is None and "exclusiveMaximum" in schema:
            hi = schema["exclusiveMaximum"] - 1
        hi = int(hi if hi is not None else max(lo + 100, 100))
        val = int(_pick_number(rng, lo, min(hi, lo + 1000)))
        mult = schema.get("multipleOf")
        if mult:  # snap into range on a multiple
            val = max(lo, min(hi, (val // int(mult)) * int(mult)))
            if val < lo:
                val += int(mult)
        return max(lo, min(hi, val))
    if t == "number":
        lo = schema.get("minimum")
        if lo is None and "exclusiveMinimum" in schema:
            lo = schema["exclusiveMinimum"] + 1e-6
        lo = float(lo if lo is not None else 0.0)
        hi = schema.get("maximum")
        if hi is None and "exclusiveMaximum" in schema:
            hi = schema["exclusiveMaximum"] - 1e-6
        hi = float(hi if hi is not None else (1.0 if "confidence" in key_hint.lower() else 100.0))
        val = _pick_number(rng, lo, hi)
        mult = schema.get("multipleOf")
        if mult:
            val = max(lo, min(hi, (int(val / mult)) * mult))
        return round(max(lo, min(hi, val)), 4)
    if t == "boolean":
        return bool(rng & 1)
    if t == "null":
        return None
    # string (default): produce something legible and deterministic, honouring constraints
    return _mock_string(key_hint, rng, schema)


def _mock_string(key_hint: str, rng: int, schema: dict | None = None) -> str:
    schema = schema or {}
    # a `pattern` (or format) constraint dominates — a legible label won't satisfy a regex,
    # so emit a minimal deterministic token that fits common patterns.
    pat = schema.get("pattern")
    if pat:
        # try a couple of trivially-safe fillers; fall back to a short alnum token
        for cand in ("A", "a", "0", "AAA", "aaa", "000"):
            filler = cand * 8
            try:
                import re as _re
                if _re.search(pat, filler):
                    return _clamp_len(filler, schema)
            except _re.error:
                break
        return _clamp_len("mock", schema)
    k = key_hint.lower()
    tag = f"{rng % 100000:05d}"
    if any(w in k for w in ("headline", "title", "what", "summary")):
        return f"[mock] finding {tag}: a segment deviates from the baseline"
    if "why" in k or "rationale" in k or "reason" in k:
        return "[mock] deterministic explanation generated offline (no LLM)"
    if "so_what" in k or "impact" in k or "recommend" in k or "action" in k:
        return "[mock] recommended action: investigate the flagged segment"
    if "metric_definition_used" in k or "definition" in k:
        return "metric.mock@v1"
    if "sql" in k:
        return "SELECT 1"
    if "severity" in k:
        return "info"
    if k.endswith("_id") or k == "id":
        return _clamp_len(f"mock_{tag}", schema)
    return _clamp_len(f"[mock:{k or 'text'}] {tag}", schema)


def _clamp_len(s: str, schema: dict) -> str:
    """Respect minLength/maxLength on a string schema."""
    lo, hi = schema.get("minLength"), schema.get("maxLength")
    if hi is not None and len(s) > hi:
        s = s[:hi]
    if lo is not None and len(s) < lo:
        s = (s + "x" * lo)[:lo]
    return s


def mock_call(system: str, user: str) -> tuple[str, dict[str, Any]]:
    """Return (text, stats) mirroring `_cli_call`. If the system prompt carries a JSON
    Schema (complete_json path), synthesize a conforming instance; otherwise return a
    deterministic line (complete_text path)."""
    rng = _seed(system, user)
    schema = _extract_schema(system)
    if schema is not None:
        defs = schema.get("$defs", schema.get("definitions", {}))
        obj = _synth(schema, defs, rng)
        text = json.dumps(obj)
    else:
        text = f"[mock] {rng % 100000:05d}: offline deterministic response"
    # honest zero-cost stats; token counts are rough character-based estimates
    stats = {
        "input_tokens": (len(system) + len(user)) // 4,
        "output_tokens": len(text) // 4,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
        "session_id": "mock",
    }
    return text, stats
