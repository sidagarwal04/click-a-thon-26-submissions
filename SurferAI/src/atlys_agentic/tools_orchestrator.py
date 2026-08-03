"""Orchestrator Tools: Workspace Path Discovery, Fuzzy Input Resolution & Batch Scanning.

Enables the Orchestrator Agent and chat interfaces to understand raw directory paths,
inspect available workspace datasets, resolve ambiguous user inputs, and plan batch
ingestion pipelines for CUJ 1 and CUJ 2.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from atlys_agentic import chdb_client, paths, tools


def Tool_Resolve_Path_Or_Spec(input_str: str) -> dict[str, Any]:
    """Resolve any user-provided string (directory path, file path, spec slug, or ID)
    into a validated filesystem spec package.

    Handles:
    - Relative paths: e.g. 'problem statment/specs/01_express_checkout'
    - Absolute paths: e.g. '/usr/local/.../specs/01_express_checkout'
    - Direct file references: e.g. 'problem statment/specs/01_express_checkout/events.ndjson'
    - Short names / numbers: e.g. '01', 'express_checkout', 'spec 01'
    """
    raw = (input_str or "").strip().strip("\"'").rstrip("/")
    if not raw:
        return {
            "found": False,
            "error": "No path or spec identifier provided.",
            "spec_id": "",
            "spec_dir": "",
            "table_name": "",
        }

    # 1. Strip common prefixes like 'ingest ', 'spec ', 'path '
    cleaned = raw
    for prefix in ("ingest spec ", "ingest ", "spec ", "path: ", "path "):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip().strip("\"'").rstrip("/")

    target_path = Path(cleaned)

    # 2. Direct absolute or repo-relative directory/file resolution
    candidate_paths: list[Path] = []
    if target_path.is_absolute() and target_path.exists():
        candidate_paths.append(target_path)

    # Relative to REPO_ROOT
    repo_rel = paths.REPO_ROOT / cleaned
    if repo_rel.exists():
        candidate_paths.append(repo_rel)

    # Relative to cwd
    cwd_rel = Path.cwd() / cleaned
    if cwd_rel.exists():
        candidate_paths.append(cwd_rel)

    # Under SPECS_DIR
    specs_rel = paths.SPECS_DIR / cleaned
    if specs_rel.exists():
        candidate_paths.append(specs_rel)

    # Check candidates
    for cand in candidate_paths:
        cand_dir = cand if cand.is_dir() else cand.parent
        spec_md_file = cand_dir / "spec.md"
        events_file = cand_dir / "events.ndjson"
        if cand_dir.exists() and (spec_md_file.exists() or events_file.exists()):
            spec_id = cand_dir.name
            spec_text = spec_md_file.read_text(encoding="utf-8") if spec_md_file.exists() else ""
            table_name = tools.Tool_Infer_Table_Name(spec_id, spec_text)
            return {
                "found": True,
                "spec_id": spec_id,
                "spec_dir": str(cand_dir.resolve()),
                "table_name": table_name,
                "has_spec_md": spec_md_file.exists(),
                "has_events_ndjson": events_file.exists(),
                "spec_md_path": str(spec_md_file) if spec_md_file.exists() else None,
                "events_ndjson_path": str(events_file) if events_file.exists() else None,
                "resolved_from": "direct_filesystem_path",
            }

    # 3. Fuzzy matching against available spec directories
    available = paths.available_spec_ids()
    cleaned_lower = cleaned.lower()

    # Exact match on spec_id
    if cleaned in available:
        spec_dir = paths.spec_dir(cleaned)
        spec_md_file = spec_dir / "spec.md"
        events_file = spec_dir / "events.ndjson"
        spec_text = spec_md_file.read_text(encoding="utf-8") if spec_md_file.exists() else ""
        table_name = tools.Tool_Infer_Table_Name(cleaned, spec_text)
        return {
            "found": True,
            "spec_id": cleaned,
            "spec_dir": str(spec_dir.resolve()),
            "table_name": table_name,
            "has_spec_md": spec_md_file.exists(),
            "has_events_ndjson": events_file.exists(),
            "spec_md_path": str(spec_md_file) if spec_md_file.exists() else None,
            "events_ndjson_path": str(events_file) if events_file.exists() else None,
            "resolved_from": "exact_spec_id",
        }

    # Match substrings or number/slug combinations
    for spec in available:
        spec_num = spec.split("_")[0]
        spec_slug = "_".join(spec.split("_")[1:])
        if (
            spec in cleaned_lower
            or cleaned_lower in spec
            or spec_slug in cleaned_lower
            or cleaned_lower in spec_slug
            or f"spec {spec_num}" in cleaned_lower
            or f"spec_{spec_num}" in cleaned_lower
            or (cleaned_lower.isdigit() and int(cleaned_lower) == int(spec_num))
        ):
            spec_dir = paths.spec_dir(spec)
            spec_md_file = spec_dir / "spec.md"
            events_file = spec_dir / "events.ndjson"
            spec_text = spec_md_file.read_text(encoding="utf-8") if spec_md_file.exists() else ""
            table_name = tools.Tool_Infer_Table_Name(spec, spec_text)
            return {
                "found": True,
                "spec_id": spec,
                "spec_dir": str(spec_dir.resolve()),
                "table_name": table_name,
                "has_spec_md": spec_md_file.exists(),
                "has_events_ndjson": events_file.exists(),
                "spec_md_path": str(spec_md_file) if spec_md_file.exists() else None,
                "events_ndjson_path": str(events_file) if events_file.exists() else None,
                "resolved_from": "fuzzy_match",
            }

    return {
        "found": False,
        "error": f"Could not resolve '{input_str}' to any known spec directory or path.",
        "spec_id": "",
        "spec_dir": "",
        "table_name": "",
    }


def Tool_Discover_Workspace_Paths(root_dir: str | None = None) -> list[dict[str, Any]]:
    """Discover all valid spec packages and dataset paths across the workspace."""
    search_roots = [paths.SPECS_DIR, paths.ATLYS_AGENTIC_DIR / "specs", paths.PROBLEM_STATEMENT_DIR]
    if root_dir:
        custom_p = Path(root_dir)
        if custom_p.exists():
            search_roots.insert(0, custom_p)

    seen_specs = set()
    catalog: list[dict[str, Any]] = []

    for root in search_roots:
        if not root or not root.exists():
            continue
        # Scan immediate children and subdirectories
        dirs_to_check = [d for d in root.iterdir() if d.is_dir()]
        if (root / "spec.md").exists() or (root / "events.ndjson").exists():
            dirs_to_check.append(root)

        for d in dirs_to_check:
            spec_md_file = d / "spec.md"
            events_file = d / "events.ndjson"
            if not spec_md_file.exists() and not events_file.exists():
                continue

            spec_id = d.name
            if spec_id in seen_specs:
                continue
            seen_specs.add(spec_id)

            spec_text = spec_md_file.read_text(encoding="utf-8") if spec_md_file.exists() else ""
            table_name = tools.Tool_Infer_Table_Name(spec_id, spec_text)

            # Check if registered in schema_registry
            is_instrumented = False
            try:
                chdb_client.init_schema()
                rows = chdb_client.run(f'SELECT "table" FROM schema_registry WHERE "table" = \'{table_name}\'')
                is_instrumented = bool(rows)
            except Exception:
                pass

            catalog.append({
                "spec_id": spec_id,
                "table_name": table_name,
                "directory_path": str(d.resolve()),
                "relative_path": str(d.relative_to(paths.REPO_ROOT)) if d.is_relative_to(paths.REPO_ROOT) else str(d),
                "has_spec_md": spec_md_file.exists(),
                "has_events_ndjson": events_file.exists(),
                "events_file_size_bytes": events_file.stat().st_size if events_file.exists() else 0,
                "is_instrumented": is_instrumented,
                "status": "instrumented" if is_instrumented else "available for ingestion",
            })

    catalog.sort(key=lambda x: x["spec_id"])
    return catalog


def Tool_Batch_Scan_Specs(folder_path: str) -> list[dict[str, Any]]:
    """Recursively scan a folder for all valid spec directories ready for ingestion."""
    p = Path(folder_path)
    if not p.is_absolute():
        p = paths.REPO_ROOT / folder_path

    if not p.exists() or not p.is_dir():
        return []

    results = []
    # Check if the folder itself is a spec
    if (p / "spec.md").exists() or (p / "events.ndjson").exists():
        spec_text = (p / "spec.md").read_text(encoding="utf-8") if (p / "spec.md").exists() else ""
        results.append({
            "spec_id": p.name,
            "table_name": tools.Tool_Infer_Table_Name(p.name, spec_text),
            "path": str(p.resolve()),
        })
        return results

    # Scan children
    for child in sorted(p.iterdir()):
        if child.is_dir() and ((child / "spec.md").exists() or (child / "events.ndjson").exists()):
            spec_text = (child / "spec.md").read_text(encoding="utf-8") if (child / "spec.md").exists() else ""
            results.append({
                "spec_id": child.name,
                "table_name": tools.Tool_Infer_Table_Name(child.name, spec_text),
                "path": str(child.resolve()),
            })

    return results
