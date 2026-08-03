#!/usr/bin/env python3
"""
Atlys schema-timeline model builder.

Reconstructs "Schema changes over time" (PROBLEM_STATEMENT.md §4 — Tracing and
Visualization Layer) purely from artifacts that already exist in the repo — no new
infrastructure, no ClickHouse credentials:

  * git commit history of `Atlys/schemas/*.sql`  -> when each schema changed & why
  * each `.sql` file's structured header comment  -> spec, validation, deviations, DDL objects
  * each `.metrics.json` manifest                 -> the metrics a schema serves
  * each `.insights.json` manifest                -> agent-generated insights + confidence scores
  * `librechat/context_docs/log.md`               -> context_version bumps + per-file diffs

Covers all three §4 viz requirements: schema changes over time, agent-generated insights
with confidence scores, and the context layer diff / changelog.

The result is a single JSON document consumed by the web UI (static/index.html) and
also printable as a structured CLI timeline (`python timeline.py`).

Pure Python standard library only (subprocess + json + re + pathlib). Read-only.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# --- repo layout ------------------------------------------------------------
# This file lives at <repo>/Atlys/schema-timeline/timeline.py
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SCHEMAS_DIR = REPO_ROOT / "Atlys" / "schemas"
CONTEXT_LOG = REPO_ROOT / "librechat" / "context_docs" / "log.md"


# --- git helpers ------------------------------------------------------------
def _git(*args: str) -> str:
    """Run a git command in the repo, return stdout (empty string on failure)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _is_git_repo() -> bool:
    return bool(_git("rev-parse", "--is-inside-work-tree").strip())


def schema_commits() -> list[dict]:
    """
    Every commit that touched a file under Atlys/schemas/, newest first, with the
    list of schema files it changed and their git status (A/M/D).
    """
    # %x1e = record separator (leads each commit), %x1f = unit separator between
    # header fields — both safe against odd chars in subjects/paths.
    fmt = "%x1e%H%x1f%an%x1f%aI%x1f%s"
    raw = _git(
        "log",
        "--no-merges",  # keep merges out of the timeline
        f"--pretty=format:{fmt}",
        "--name-status",
        "--",
        "Atlys/schemas/",
    )
    commits: list[dict] = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        header, *rest = record.split("\n")
        parts = header.split("\x1f")
        if len(parts) < 4:
            continue
        sha, author, date, subject = parts[0], parts[1], parts[2], parts[3]
        files = []
        for line in rest:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            status, path = line.split("\t", 1)
            if not path.startswith("Atlys/schemas/"):
                continue
            files.append({"status": status[:1], "path": path})
        if files:
            commits.append(
                {
                    "sha": sha,
                    "short": sha[:8],
                    "author": author,
                    "date": date,
                    "subject": subject,
                    "files": files,
                }
            )
    return commits


# --- .sql header parsing ----------------------------------------------------
_HEADER_FIELD_RE = re.compile(r"^--\s{2,}([a-z_ ]+?)\s{2,}:\s*(.+?)\s*$")


def parse_sql_header(text: str) -> dict:
    """
    Pull the structured `-- key : value` metadata + DEVIATIONS block out of a
    generated schema's leading comment. Tolerant of the two header variants seen
    in the repo (01_ has a lean header, 08_ a rich one).
    """
    meta: dict[str, str] = {}
    deviations: list[str] = []
    in_dev = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("--"):
            # first non-comment line ends the header
            if stripped and not stripped.startswith("--"):
                break
            continue
        if "DEVIATIONS" in stripped:
            in_dev = True
            continue
        if in_dev:
            m = re.match(r"^--\s*(\[D\d+\].*)$", stripped)
            if m:
                deviations.append(m.group(1).strip())
            continue
        m = _HEADER_FIELD_RE.match(stripped)
        if m:
            key = m.group(1).strip().replace(" ", "_")
            meta[key] = m.group(2).strip()
    return {"meta": meta, "deviations": deviations}


# --- DDL object extraction (lightweight, no full SQL parse) -----------------
def _strip_sql_comments(text: str) -> str:
    """Drop `-- ...` line comments so header citations don't pollute DDL parsing."""
    out = []
    for line in text.splitlines():
        # remove a trailing/leading line comment but keep the code before it
        idx = line.find("--")
        out.append(line if idx < 0 else line[:idx])
    return "\n".join(out)


def parse_ddl_objects(text: str) -> list[dict]:
    """Identify the CREATE ... objects and a few salient properties for display."""
    text = _strip_sql_comments(text)
    objects: list[dict] = []
    patterns = [
        (r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([\w.`]+)", "table"),
        (r"CREATE\s+MATERIALIZED\s+VIEW\s+IF\s+NOT\s+EXISTS\s+([\w.`]+)", "materialized_view"),
        (r"CREATE\s+DATABASE\s+IF\s+NOT\s+EXISTS\s+([\w.`]+)", "database"),
    ]
    for pat, kind in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            objects.append({"kind": kind, "name": m.group(1).replace("`", "")})

    order_by = re.search(r"ORDER\s+BY\s*\(([^)]*)\)", text, re.IGNORECASE)
    partition = re.search(r"PARTITION\s+BY\s+([^\n]+)", text, re.IGNORECASE)
    engines = re.findall(r"ENGINE\s*=\s*(\w+)", text, re.IGNORECASE)
    indexes = re.findall(r"INDEX\s+(\w+)\s+[^\n]*?TYPE\s+(\w+)", text, re.IGNORECASE)
    ttl = re.search(r"TTL\s+([^\n]+)", text, re.IGNORECASE)

    props = {
        "engines": engines,
        "order_by": order_by.group(1).strip() if order_by else None,
        "partition_by": partition.group(1).strip().rstrip(";") if partition else None,
        "skip_indexes": [{"name": n, "type": t} for n, t in indexes],
        "ttl": ttl.group(1).strip().rstrip(";") if ttl else None,
    }
    return objects, props


# --- metrics manifest -------------------------------------------------------
def load_metrics(spec_name: str) -> dict | None:
    path = SCHEMAS_DIR / f"{spec_name}.metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


# --- insights manifest (agent-generated insights + confidence) --------------
def load_insights(spec_name: str) -> dict | None:
    path = SCHEMAS_DIR / f"{spec_name}.insights.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _confidence_bucket(score) -> str:
    """Map a numeric confidence in [0,1] to a label consistent with the agent's H/M/L."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "unknown"
    if s >= 0.75:
        return "High"
    if s >= 0.45:
        return "Medium"
    return "Low"


def _normalize_insights(manifest: dict) -> list[dict]:
    """
    Return the manifest's insights[] with a stable, UI-friendly shape. Tolerant of a
    partially-populated manifest (the LLM may omit optional fields); fills a derived
    confidence_label from the numeric score when the agent didn't provide one.
    """
    out: list[dict] = []
    for i, raw in enumerate(manifest.get("insights", []) or []):
        conf = raw.get("confidence")
        label = raw.get("confidence_label") or _confidence_bucket(conf)
        out.append(
            {
                "id": raw.get("id") or f"insight-{i + 1}",
                "headline": raw.get("headline", ""),
                "metric": raw.get("metric"),
                "evidence": raw.get("evidence"),
                "why": raw.get("why"),
                "confidence": conf,
                "confidence_label": label,
                "confidence_reason": raw.get("confidence_reason"),
                "direction": raw.get("direction"),
                "dimensions": raw.get("dimensions", []) or [],
                "segments": raw.get("segments", []) or [],
                "related_known_issues": raw.get("related_known_issues", []) or [],
                "related_metrics": raw.get("related_metrics", []) or [],
                "suggested_next_step": raw.get("suggested_next_step"),
                "evidence_sql": raw.get("evidence_sql"),
            }
        )
    return out


def _insights_meta(manifest: dict) -> dict:
    """Top-level provenance from an insights manifest (trace, window, caveats)."""
    return {
        "generated_by": manifest.get("generated_by"),
        "generated_at": manifest.get("generated_at"),
        "trace_url": manifest.get("trace_url"),
        "time_window": manifest.get("time_window"),
        "data_caveats": manifest.get("data_caveats"),
    }


# --- context changelog (log.md) --------------------------------------------
_CTX_HEADER_RE = re.compile(r"^##\s+v(\d+)\s+—\s+(\S+)\s+—\s+(.*)$")


def parse_context_log() -> list[dict]:
    """
    Parse librechat/context_docs/log.md into version entries. Each entry:
      { version, timestamp, trigger, changes: [{kind, path, reason}], source }
    kind is derived from the `added:/updated:/contradictions ...` prefix.
    """
    if not CONTEXT_LOG.exists():
        return []
    entries: list[dict] = []
    current: dict | None = None
    for raw in CONTEXT_LOG.read_text().splitlines():
        line = raw.rstrip()
        m = _CTX_HEADER_RE.match(line.replace("-", "—") if " — " not in line else line)
        # be lenient about hyphen vs em-dash
        if not m:
            m = re.match(r"^##\s+v(\d+)\s+[—-]+\s+(\S+)\s+[—-]+\s+(.*)$", line)
        if m:
            if current:
                entries.append(current)
            current = {
                "version": int(m.group(1)),
                "timestamp": m.group(2),
                "trigger": m.group(3).strip(),
                "changes": [],
                "source": None,
            }
            continue
        if current is None:
            continue
        item = re.match(r"^-\s+(.*)$", line)
        if not item:
            continue
        body = item.group(1).strip()
        low = body.lower()
        if low.startswith("source:"):
            current["source"] = body.split(":", 1)[1].strip()
            continue
        kind = "updated"
        if low.startswith("added:"):
            kind, body = "added", body.split(":", 1)[1].strip()
        elif low.startswith("updated:"):
            kind, body = "updated", body.split(":", 1)[1].strip()
        elif low.startswith("contradictions added") or low.startswith("contradiction added"):
            kind, body = "contradiction", body.split(":", 1)[1].strip()
        elif low.startswith("contradictions updated") or low.startswith("contradiction updated"):
            kind, body = "contradiction", body.split(":", 1)[1].strip()
        # split "path (reason)"
        pm = re.match(r"^(\S+)\s*(?:\((.*)\))?$", body)
        if pm and pm.group(1).startswith("/"):
            current["changes"].append(
                {"kind": kind, "path": pm.group(1), "reason": (pm.group(2) or "").strip()}
            )
        else:
            current["changes"].append({"kind": kind, "path": None, "reason": body})
    if current:
        entries.append(current)
    return entries


# --- top-level model --------------------------------------------------------
def build_schemas() -> list[dict]:
    """
    One entry per generated schema (.sql), enriched with header meta, DDL objects,
    metrics, and its git history (first-seen / last-changed / revision count).
    """
    commits = schema_commits()

    # map filepath -> ordered list of commits (newest first)
    file_history: dict[str, list[dict]] = {}
    for c in commits:
        for f in c["files"]:
            file_history.setdefault(f["path"], []).append(
                {"sha": c["short"], "date": c["date"], "subject": c["subject"], "status": f["status"]}
            )

    schemas: list[dict] = []
    if not SCHEMAS_DIR.exists():
        return schemas
    for sql_path in sorted(SCHEMAS_DIR.glob("*.sql")):
        spec_name = sql_path.stem
        text = sql_path.read_text()
        header = parse_sql_header(text)
        objects, props = parse_ddl_objects(text)
        metrics = load_metrics(spec_name)
        insights = load_insights(spec_name)
        insight_list = _normalize_insights(insights) if insights else []
        rel = f"Atlys/schemas/{sql_path.name}"
        hist = file_history.get(rel, [])
        n_tables = sum(1 for o in objects if o["kind"] == "table")
        n_mvs = sum(1 for o in objects if o["kind"] == "materialized_view")
        schemas.append(
            {
                "spec_name": spec_name,
                "file": rel,
                "header": header["meta"],
                "deviations": header["deviations"],
                "objects": objects,
                "properties": props,
                "counts": {
                    "tables": n_tables,
                    "materialized_views": n_mvs,
                    "skip_indexes": len(props["skip_indexes"]),
                    "metrics": len(metrics["metrics"]) if metrics else 0,
                    "insights": len(insight_list),
                },
                "metrics": metrics["metrics"] if metrics else [],
                "insights": insight_list,
                "insights_meta": _insights_meta(insights) if insights else None,
                "history": hist,
                "first_seen": hist[-1]["date"] if hist else None,
                "last_changed": hist[0]["date"] if hist else None,
                "revisions": len(hist),
            }
        )
    return schemas


def build_events() -> list[dict]:
    """A flat, newest-first timeline merging schema commits and context versions."""
    events: list[dict] = []
    for c in schema_commits():
        # keep only real schema artifacts; skip probe/temp files
        real_files = [
            f
            for f in c["files"]
            if f["path"].endswith(".sql")
            or f["path"].endswith(".metrics.json")
            or f["path"].endswith(".insights.json")
        ]
        if not real_files:
            continue
        specs = sorted(
            {
                Path(f["path"]).stem.replace(".metrics", "").replace(".insights", "")
                for f in real_files
            }
        )
        events.append(
            {
                "type": "schema-commit",
                "date": c["date"],
                "title": c["subject"],
                "ref": c["short"],
                "author": c["author"],
                "specs": specs,
                "files": real_files,
            }
        )
    for e in parse_context_log():
        counts = {"added": 0, "updated": 0, "contradiction": 0}
        for ch in e["changes"]:
            counts[ch["kind"]] = counts.get(ch["kind"], 0) + 1
        events.append(
            {
                "type": "context-version",
                "date": e["timestamp"],
                "title": f"Context v{e['version']} — {e['trigger']}",
                "ref": f"v{e['version']}",
                "trigger": e["trigger"],
                "counts": counts,
                "changes": e["changes"],
                "source": e["source"],
            }
        )
    # newest first; entries without a parseable date sink to the bottom
    events.sort(key=lambda x: (x["date"] or ""), reverse=True)
    return events


def build_insights(schemas: list[dict]) -> dict:
    """
    Flatten every schema's insights into one list (newest schema first) plus a small
    summary: confidence distribution (H/M/L) and which known issues (K1-K7) are cited.
    """
    flat: list[dict] = []
    conf_dist = {"High": 0, "Medium": 0, "Low": 0, "unknown": 0}
    known_issues: dict[str, int] = {}
    for s in schemas:
        meta = s.get("insights_meta") or {}
        for ins in s.get("insights", []):
            label = ins.get("confidence_label") or "unknown"
            conf_dist[label] = conf_dist.get(label, 0) + 1
            for k in ins.get("related_known_issues", []):
                known_issues[k] = known_issues.get(k, 0) + 1
            flat.append(
                {
                    **ins,
                    "spec_name": s["spec_name"],
                    "base_table": s.get("header", {}).get("base_table"),
                    "trace_url": meta.get("trace_url"),
                    "generated_at": meta.get("generated_at"),
                }
            )
    return {
        "count": len(flat),
        "confidence_distribution": conf_dist,
        "known_issues_cited": known_issues,
        "insights": flat,
    }


def build_model() -> dict:
    schemas = build_schemas()
    context = parse_context_log()
    events = build_events()
    insights = build_insights(schemas)
    totals = {
        "schemas": len(schemas),
        "tables": sum(s["counts"]["tables"] for s in schemas),
        "materialized_views": sum(s["counts"]["materialized_views"] for s in schemas),
        "metrics": sum(s["counts"]["metrics"] for s in schemas),
        "insights": insights["count"],
        "schema_commits": sum(1 for e in events if e["type"] == "schema-commit"),
        "context_versions": len(context),
    }
    return {
        "generated_from": (
            "git history + .sql headers + .metrics.json + .insights.json + context_docs/log.md"
        ),
        "repo_root": str(REPO_ROOT),
        "is_git_repo": _is_git_repo(),
        "totals": totals,
        "schemas": schemas,
        "insights": insights,
        "context_versions": context,
        "events": events,
    }


# --- CLI (structured text) --------------------------------------------------
def _cli() -> None:
    m = build_model()
    t = m["totals"]
    print("\n  ATLYS — SCHEMA CHANGES OVER TIME")
    print("  " + "-" * 52)
    print(
        f"  schemas={t['schemas']}  tables={t['tables']}  "
        f"MVs={t['materialized_views']}  metrics={t['metrics']}  "
        f"insights={t['insights']}  "
        f"schema-commits={t['schema_commits']}  context-versions={t['context_versions']}"
    )
    if not m["is_git_repo"]:
        print("  (warning: not a git repo — history is empty)")
    print("\n  TIMELINE (newest first)")
    print("  " + "-" * 52)
    for e in m["events"]:
        icon = "▣" if e["type"] == "schema-commit" else "◇"
        date = (e["date"] or "")[:10]
        print(f"  {icon} {date}  {e['ref']:>9}  {e['title']}")
        if e["type"] == "schema-commit" and e.get("specs"):
            print(f"        specs: {', '.join(e['specs'])}")
        if e["type"] == "context-version":
            c = e["counts"]
            print(
                f"        +{c.get('added',0)} added  "
                f"~{c.get('updated',0)} updated  "
                f"!{c.get('contradiction',0)} contradictions"
            )
    print("\n  SCHEMAS")
    print("  " + "-" * 52)
    for s in m["schemas"]:
        c = s["counts"]
        print(
            f"  {s['spec_name']:<32} "
            f"tables={c['tables']} MVs={c['materialized_views']} "
            f"idx={c['skip_indexes']} metrics={c['metrics']} rev={s['revisions']}"
        )
        if s["properties"]["order_by"]:
            print(f"      ORDER BY ({s['properties']['order_by']})")
        for d in s["deviations"]:
            print(f"      deviation: {d[:80]}")

    ins = m["insights"]
    if ins["count"]:
        cd = ins["confidence_distribution"]
        print("\n  AGENT-GENERATED INSIGHTS")
        print("  " + "-" * 52)
        print(
            f"  {ins['count']} insights  "
            f"(High={cd.get('High',0)} Medium={cd.get('Medium',0)} Low={cd.get('Low',0)})"
            + (f"  known-issues cited: {', '.join(sorted(ins['known_issues_cited']))}"
               if ins["known_issues_cited"] else "")
        )
        for i in ins["insights"]:
            score = i.get("confidence")
            bar = ""
            if isinstance(score, (int, float)):
                filled = round(float(score) * 10)
                bar = "█" * filled + "░" * (10 - filled)
            print(
                f"  ▸ [{i.get('confidence_label','?'):>6}] {bar} "
                f"{(i.get('headline') or '')[:70]}"
            )
            ki = i.get("related_known_issues") or []
            if ki:
                print(f"        known-issue: {', '.join(ki)}   spec: {i['spec_name']}")
    print()


if __name__ == "__main__":
    import sys

    if "--json" in sys.argv:
        print(json.dumps(build_model(), indent=2))
    else:
        _cli()
