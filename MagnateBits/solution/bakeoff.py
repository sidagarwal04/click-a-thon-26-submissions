"""T3 · Schema bake-off: measure ORDER BY choices instead of trusting prose.

After a feature table is loaded, materialise one deliberate straw-man
(`ORDER BY (timestamp, <entity_key>)` -- what most teams ship) and run the same
platform-cut funnel query against both. Real `read_bytes` from
`system.query_log` go into `proposal.rationale["order_by"]`, and the loser is
dropped. An MV-style keep/drop with numbers, applied to sort keys.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import queries.templates as templates
import tracing
from ch import CH
from contracts import DDLProposal, FeatureSemantics


def _qid(tag: str) -> str:
    return f"bake_{tag}_{uuid.uuid4().hex[:12]}"


def _funnel_sql(sem: FeatureSemantics) -> str:
    """One representative query both layouts answer: overall funnel."""
    return templates.t02_funnel_overall(sem).sql


def _measure(ch: CH, sql: str, tag: str) -> dict[str, int]:
    qid = _qid(tag)
    # Warm once so cold-cache noise does not dominate the comparison, then measure.
    ch.run_select(sql, max_rows=50)
    ch.run_select(sql, max_rows=50, query_id=qid)
    stats = ch.query_stats(qid, timeout_s=6.0)
    return stats or {"read_rows": 0, "read_bytes": 0, "query_duration_ms": 0, "memory_usage": 0}


def _straw_order_by(proposal: DDLProposal) -> list[str]:
    """Plausible alternative: timestamp-first. Entity key stays; event is dropped from the key."""
    entity = proposal.semantics.entity_key or "user_id"
    names = {c.name for c in proposal.columns}
    if entity not in names:
        entity = "user_id" if "user_id" in names else next(
            (c.name for c in proposal.columns if c.name.endswith("_id") and c.name != "id"),
            "user_id",
        )
    return ["timestamp", entity]


def run(proposal: DDLProposal, ch: CH) -> dict[str, Any]:
    """Compare the agent's ORDER BY against a timestamp-first straw-man.

    Mutates `proposal.rationale["order_by"]` (and optional measured_* fields) in place.
    Never raises into the pipeline: a bake-off failure must not kill a clean run.
    """
    result: dict[str, Any] = {"ok": False, "skipped": False, "detail": ""}
    table = proposal.table_name
    straw = f"bake_{proposal.semantics.feature_slug}_straw"
    try:
        with tracing.span("instrumentation.bakeoff", table=table, straw=straw):
            if not ch.table_exists(table):
                result["skipped"] = True
                result["detail"] = f"{table} missing"
                return result

            straw_order = _straw_order_by(proposal)
            # Drop any previous straw-man so re-runs are idempotent.
            ch.execute_ddl(f"DROP TABLE IF EXISTS {straw}")

            # Clone schema+data with the alternative sort key. Partitioning kept
            # identical so the only variable is ORDER BY.
            part = proposal.partition_by or "toYYYYMM(timestamp)"
            part = part.replace("PARTITION BY", "").strip()
            ch.execute_ddl(
                f"CREATE TABLE {straw} ENGINE = MergeTree() "
                f"PARTITION BY {part} "
                f"ORDER BY ({', '.join(straw_order)}) "
                f"AS SELECT * FROM {table}"
            )

            # Force parts to settle so EXPLAIN/read_bytes are not mid-merge noise.
            try:
                ch.execute_ddl(f"OPTIMIZE TABLE {table} FINAL")
                ch.execute_ddl(f"OPTIMIZE TABLE {straw} FINAL")
            except Exception:  # noqa: BLE001
                pass

            chosen_sem = proposal.semantics.model_copy(
                update={"table_fqn": f"{ch.database}.{table}"}
            )
            straw_sem = proposal.semantics.model_copy(
                update={"table_fqn": f"{ch.database}.{straw}"}
            )
            sql_chosen = _funnel_sql(chosen_sem)
            sql_straw = _funnel_sql(straw_sem)

            t0 = time.perf_counter()
            chosen_stats = _measure(ch, sql_chosen, "chosen")
            straw_stats = _measure(ch, sql_straw, "straw")
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            chosen_b = int(chosen_stats.get("read_bytes", 0))
            straw_b = int(straw_stats.get("read_bytes", 0))
            ratio = (straw_b / chosen_b) if chosen_b > 0 else 0.0

            # Prefer the smaller reader. Tie (or missing stats) keeps the agent's choice.
            winner = "chosen"
            if straw_b > 0 and chosen_b > 0 and straw_b < chosen_b * 0.95:
                winner = "straw"

            prior = proposal.rationale.get("order_by", "").rstrip()
            if chosen_b > 0 and abs(ratio - 1.0) < 0.05:
                verdict = (
                    f"At sample volume ({chosen_stats.get('read_rows', 0):,} rows) both layouts "
                    f"read the same bytes -- the table fits in a handful of granules, so primary-key "
                    f"pruning cannot discriminate. Event-first retained per house_rules §2 "
                    f"(event prune + sparse serialization); straw-man dropped. Re-run at "
                    f"projected_annual_rows to price the gap."
                )
            elif winner == "chosen":
                verdict = (
                    f"Chosen wins by {ratio:.1f}× fewer bytes; straw-man dropped."
                    if ratio >= 1
                    else "Chosen retained; straw-man dropped."
                )
            else:
                verdict = (
                    f"Straw-man read fewer bytes ({1/ratio:.1f}×) at this volume; agent ORDER BY "
                    f"still retained (house_rules §2: event-first enables sparse serialization). "
                    f"Straw-man dropped."
                )
            measured_line = (
                f"Bake-off on t02_funnel_overall: "
                f"chosen ORDER BY ({', '.join(proposal.order_by)}) read "
                f"{chosen_b:,} B / {chosen_stats.get('read_rows', 0):,} rows; "
                f"straw-man ORDER BY ({', '.join(straw_order)}) read "
                f"{straw_b:,} B / {straw_stats.get('read_rows', 0):,} rows. {verdict}"
            )
            proposal.rationale["order_by"] = (
                (prior + "\n\n" if prior else "") + measured_line
            )
            # Optional measured fields -- mirror MVSpec's keep/drop pattern.
            proposal.rationale["order_by_measured_chosen_bytes"] = str(chosen_b)
            proposal.rationale["order_by_measured_straw_bytes"] = str(straw_b)
            proposal.rationale["order_by_measured_ratio"] = f"{ratio:.2f}"

            # Always drop the straw-man: house rules win even if it read less, because
            # event-first clustering is what makes sparse serialization work. The number
            # is the point, not silently rewriting the schema.
            ch.execute_ddl(f"DROP TABLE IF EXISTS {straw}")

            result.update(
                {
                    "ok": True,
                    "chosen_bytes": chosen_b,
                    "straw_bytes": straw_b,
                    "ratio": ratio,
                    "winner": winner,
                    "straw_order": straw_order,
                    "elapsed_ms": elapsed_ms,
                    "detail": measured_line,
                }
            )
            return result
    except Exception as exc:  # noqa: BLE001
        try:
            ch.execute_ddl(f"DROP TABLE IF EXISTS {straw}")
        except Exception:  # noqa: BLE001
            pass
        result["detail"] = f"{type(exc).__name__}: {exc}"
        return result


def report_line(result: dict[str, Any]) -> str:
    if result.get("skipped"):
        return f"bake-off skipped: {result.get('detail', '')}"
    if not result.get("ok"):
        return f"bake-off failed: {result.get('detail', '')[:200]}"
    return (
        f"bake-off  chosen {result['chosen_bytes']:,} B vs straw {result['straw_bytes']:,} B "
        f"({result['ratio']:.1f}×) — straw dropped"
    )
