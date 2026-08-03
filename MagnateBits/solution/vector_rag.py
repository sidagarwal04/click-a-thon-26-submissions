"""In-ClickHouse vector RAG for context retrieval (ported from `loop`, adapted).

DEFAULT ON — `ATLYS_CONTEXT_RETRIEVAL=full` opts back out.
---------------------------------------------------------
This was originally opt-in because the full-dump path is deterministic and, at ~60-150
entries, fits a prompt under 20k chars (see contextlayer/schema.sql header and
docs/EVALUATION.md). Two things changed that calculus:

  1. The layer outgrew "small". It is now ~400 active entries and climbs with every
     instrumented feature — the argument for dumping it wholesale was explicitly
     conditioned on a size the layer no longer has.
  2. The determinism objection does not apply to THIS implementation. The embedding is a
     local hashing function (no network, same text -> same vector), so which entries are
     retrieved is reproducible and auditable — the property the full dump was protecting.

Ranked mode also never surfaces LESS governance context than the full dump: `_ALWAYS_KINDS`
below are included unconditionally, and an empty/missing index falls back to the full dump.
So the failure modes are bounded in the safe direction.

Everything stays in ClickHouse — embeddings in a column, `cosineDistance` + an HNSW
`vector_similarity` index, plus a `text` inverted-index keyword fallback — so the
"everything in one engine" story holds and no external vector DB is introduced.

Everything stays in ClickHouse — embeddings in a column, `cosineDistance` + an HNSW
`vector_similarity` index, plus a `text` inverted-index keyword fallback — so the
"everything in one engine" story holds and no external vector DB is introduced.

The embedding is a deterministic local hashing embedding (no network, same text -> same
vector). Swap `EMBED_PROVIDER` later for a real model — note that doing so trades this
reproducibility for semantic quality, which is the point at which the determinism argument
above would need revisiting.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

from ch import CH
from contracts import ContextEntry, ContextSnapshot

DIM = 128
TABLE = "context_embeddings"
_token_re = re.compile(r"[a-z0-9]+")

# retrieval knobs
TOP_K = int(os.getenv("ATLYS_RAG_TOP_K", "12"))
# kinds that are always included regardless of ranking — the governance-critical context a
# finding must never miss even if lexically distant from the focus string. `known_issue` is
# included because the interpret step's whole thesis is citing a documented issue to explain a
# number; dropping a lexically-distant known-issue would silently downgrade a finding that
# should have been corroborated. This guarantees ranked mode never surfaces LESS governance
# context than the full dump (only trims low-cardinality descriptive entries).
_ALWAYS_KINDS = ("contradiction", "gap", "metric", "known_issue", "relationship")


def enabled() -> bool:
    """Ranked retrieval is the default; `ATLYS_CONTEXT_RETRIEVAL=full` opts back out.

    Anything other than an explicit "full" enables it, so a typo fails toward the mode
    with the governance-kind floor and the full-dump fallback rather than silently
    disabling retrieval.
    """
    return os.getenv("ATLYS_CONTEXT_RETRIEVAL", "vector").strip().lower() != "full"


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    """Validate a SQL identifier (table/column). Rejects anything that isn't a plain
    identifier — a defence-in-depth guard so this public function can't be an injection
    vector even if a caller passes an untrusted name."""
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


def _lit(value: str) -> str:
    """Escape a string into a single-quoted ClickHouse literal, handling BOTH backslash and
    quote (a lone quote-strip lets a trailing backslash escape the closing quote). Returns
    '' (two quotes) for the empty string."""
    s = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


# ── deterministic local embedding (hashing bag-of-tokens, L2-normalized) ──────
def _tokens(text: str) -> list[str]:
    return _token_re.findall(text.lower())


def embed(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    toks = _tokens(text)
    if not toks:
        return vec
    for tok in toks:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


def salient_terms(text: str, top_n: int = 8) -> list[str]:
    seen, out = set(), []
    for t in _tokens(text):
        if len(t) > 2 and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= top_n:
            break
    return out


# ── index maintenance (in ClickHouse) ────────────────────────────────────────
def ensure_table(ch: CH) -> None:
    ch.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE}
        (
            entry_id  String,
            version   UInt32,
            kind      LowCardinality(String),
            key       String,
            body      String,
            embedding Array(Float32),
            INDEX idx_body body TYPE text(tokenizer = 'splitByNonAlpha') GRANULARITY 1,
            INDEX idx_vec  embedding TYPE vector_similarity('hnsw', 'cosineDistance', {DIM})
                                     GRANULARITY 1
        )
        ENGINE = ReplacingMergeTree(version)
        ORDER BY entry_id
        """
    )


def reindex(ch: CH, snapshot: ContextSnapshot) -> int:
    """(Re)embed every active entry in the snapshot. Idempotent via ReplacingMergeTree."""
    ensure_table(ch)
    rows = []
    for e in snapshot.entries:
        if e.status == "superseded":
            continue
        text = f"{e.key} {e.body}".strip()
        rows.append(
            {
                "entry_id": e.entry_id,
                "version": e.version,
                "kind": e.kind,
                "key": e.key,
                "body": e.body,
                "embedding": embed(text),
            }
        )
    if rows:
        ch.insert_rows(TABLE, rows)
    return len(rows)


# ── retrieval ─────────────────────────────────────────────────────────────────
def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def search(ch: CH, query: str, k: int = TOP_K) -> list[dict[str, Any]]:
    """Nearest active context entries to `query` by cosine distance, with a keyword
    fallback merged in. Runs entirely in ClickHouse."""
    if not ch.table_exists(TABLE):
        return []
    qv = _vec_literal(embed(query))
    sem = ch.run_select(
        f"""
        SELECT entry_id, kind, key, body,
               round(cosineDistance(embedding, {qv}), 4) AS dist
        FROM {TABLE} FINAL
        WHERE length(embedding) = {DIM}
        ORDER BY dist ASC
        LIMIT {int(k)}
        """
    )
    hits = {r["entry_id"]: r for r in sem}
    # keyword corroboration via the text index
    terms = [t for t in salient_terms(query) if t.isalnum()]
    if terms:
        conds = " OR ".join(f"hasToken(lower(body), '{t}')" for t in terms)
        for r in ch.run_select(
            f"SELECT entry_id, kind, key, body FROM {TABLE} FINAL WHERE {conds} LIMIT {int(k)}"
        ):
            hits.setdefault(r["entry_id"], {**r, "dist": None})
    return list(hits.values())


def hybrid_issue_funnel(
    ch: CH,
    table: str,
    query: str,
    *,
    event_col: str = "event",
    entity_col: str = "user_id",
    segment_col: str = "device_type",
    first_event: str | None = None,
    last_event: str | None = None,
    k_issues: int = 3,
) -> list[dict[str, Any]]:
    """The hybrid query — semantic retrieval JOINed with funnel analytics in ONE statement.

    In a single SQL round-trip, ClickHouse:
      (a) ranks the k nearest known-issues to `query` by `cosineDistance` over the HNSW-indexed
          embedding column (the "vector DB" job), and
      (b) computes a per-segment two-step conversion rate over the feature table via
          `windowFunnel` (the "analytics DB" job),
    and CROSS JOINs the two so every returned row pairs a real segment metric with the
    semantically-closest documented issue — the diagnosis and the evidence in one result set.

    This is the "one query no other database can run": semantic retrieval ⨝ funnel aggregation,
    one engine, one SQL dialect, raw rows never leaving ClickHouse. Requires the embedding index
    (build it with `reindex`). Returns [] if the index or table is absent.
    """
    if not ch.table_exists(TABLE) or not ch.table_exists(table):
        return []
    qv = _vec_literal(embed(query))
    # Injection-safety: validate every identifier against a strict pattern (reject anything
    # that isn't a plain SQL identifier) and escape string literals for BOTH backslash and
    # quote (a lone quote-strip lets `x\` escape the closing quote). Identifiers here are
    # normally derived from trusted semantics, but this function is a public entry point, so a
    # bad identifier returns [] gracefully (matching the "returns [] if unusable" contract).
    try:
        seg = _ident(segment_col)
        ent = _ident(entity_col)
        ev = _ident(event_col)
        tbl = _ident(table)
    except ValueError:
        return []
    fe = _lit(first_event or "")
    le = _lit(last_event or "")
    # funnel condition: if explicit first/last events given use them, else fall back to
    # "reached any event" vs "reached the last event". `fe`/`le` are already fully-quoted
    # SQL literals (or '' when unset), so they are dropped straight into the comparison.
    have_events = bool((first_event or "").strip()) and bool((last_event or "").strip())
    if have_events:
        funnel_expr = (
            f"windowFunnel(2592000000)("
            f"toUInt64(toUnixTimestamp64Milli(toDateTime64(timestamp,3))), "
            f"{ev} = {fe}, {ev} = {le})"
        )
    else:
        # degenerate-safe: treat presence as step 1, any later distinct event as step 2
        funnel_expr = (
            f"windowFunnel(2592000000)("
            f"toUInt64(toUnixTimestamp64Milli(toDateTime64(timestamp,3))), 1, {ev} != '')"
        )
    sql = f"""
    WITH
      nearest_issue AS (
        SELECT entry_id, key, body, round(cosineDistance(embedding, {qv}), 4) AS dist
        FROM {TABLE} FINAL
        WHERE length(embedding) = {DIM}
        ORDER BY dist ASC
        LIMIT {int(k_issues)}
      ),
      per_entity AS (
        SELECT {ent} AS entity,
               any({seg}) AS segment,
               {funnel_expr} AS level
        FROM {tbl}
        WHERE {ent} != ''
        GROUP BY entity
      ),
      segment_funnel AS (
        SELECT segment,
               count() AS entities,
               countIf(level >= 1) AS reached_first,
               countIf(level >= 2) AS reached_last,
               round(countIf(level >= 2) / nullIf(countIf(level >= 1), 0), 4) AS conversion
        FROM per_entity
        WHERE segment != ''
        GROUP BY segment
        ORDER BY entities DESC
        LIMIT 10
      )
    SELECT sf.segment, sf.entities, sf.reached_first, sf.reached_last, sf.conversion,
           ni.entry_id AS nearest_issue_id, ni.key AS nearest_issue, ni.dist AS issue_distance
    FROM segment_funnel sf
    CROSS JOIN (SELECT * FROM nearest_issue ORDER BY dist ASC LIMIT 1) ni
    ORDER BY sf.conversion ASC
    """
    return ch.run_select(sql)


def ranked_prompt(ch: CH, snapshot: ContextSnapshot, query: str, k: int = TOP_K) -> str:
    """Drop-in relevance-ranked alternative to `snapshot.as_prompt()`.

    Returns a prompt block containing (a) every always-include governance entry
    (contradictions, gaps, metrics) and (b) the top-k semantically nearest other entries.
    Falls back to the full dump if the index is empty, so it can never return *less*
    context than the default when retrieval isn't ready.
    """
    hits = search(ch, query, k)
    if not hits:
        return snapshot.as_prompt()
    keep_ids = {h["entry_id"] for h in hits}
    kept: list[ContextEntry] = []
    for e in snapshot.entries:
        if e.status == "superseded":
            continue
        if e.kind in _ALWAYS_KINDS or e.entry_id in keep_ids:
            kept.append(e)
    focused = ContextSnapshot(version=snapshot.version, entries=kept)
    header = (
        f"# Context layer (version {snapshot.version}) — "
        f"relevance-ranked to: {query[:120]!r} "
        f"({len(kept)}/{len(snapshot.entries)} entries; governance entries always included)\n"
    )
    return header + focused.as_prompt()
