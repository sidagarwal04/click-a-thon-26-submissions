"""
config.py
---------
Agent registry driven entirely by environment variables.

    AGENT_1_ID=liv-concurrency        # appears as the "model" in LibreChat
    AGENT_1_PROVIDER=anthropic        # anthropic | openrouter | google
    AGENT_1_MODEL=claude-sonnet-4-6
    AGENT_1_PROMPT=liv-concurrency-agent    # Langfuse prompt name (preferred)
    AGENT_1_PROMPT_LABEL=production
    AGENT_1_SYSTEM=...                # inline fallback if PROMPT is unset

When AGENT_N_PROMPT is set the system prompt is fetched live from Langfuse,
so publishing a new production version updates behaviour without a redeploy.
"""

import os
from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    id: str
    provider: str
    model: str
    system: str
    description: str = ""          # what this specialist is for (router reads it)
    prompt_name: str = ""
    prompt_label: str = "production"
    append_tool_hint: bool = True
    temperature: float = 0.2
    max_tokens: int = 1024


# ── Schema + query-semantics hint appended to every system prompt ─────────────
# This is the highest-value part of the integration. Concurrency has three
# non-obvious rules, and an LLM that does not know them will write SQL that
# looks correct and returns numbers that are wrong. Stating them explicitly
# is what makes the agent trustworthy.
CLICKHOUSE_TOOL_HINT = """

You have MCP tools (`run_select_query`, `list_databases`, `list_tables`) that
run read-only SELECT queries against the `liv` database. It holds foreground-
only viewing concurrency for a Sony LIV-style OTT platform.

PREFERRED TABLE — `concurrency_minute` (a view). Use this unless you need
something it does not expose. It has already collapsed the aggregate-function
rows for you.
  concurrency_minute(minute, platform, country, video_type, content_id,
                     sessions, users)
  One row per minute per dimension tuple. `sessions` is the count of sessions
  actively watching in the FOREGROUND during that minute.

UNDERLYING TABLES
  conc_minute(minute, platform, country, video_type, content_id,
              sessions SimpleAggregateFunction(max, UInt32),
              users AggregateFunction(uniqExact, UInt64))
      The serving table. If you query it directly you MUST collapse first:
      GROUP BY minute, platform, country, video_type, content_id with
      max(sessions), and read users with uniqExactMerge(users).
  session_minute(minute, platform, country, video_type, content_id,
                 video_session_id UInt64, user_id UInt64)
      Detail tier: one row per (session, minute) actively watching.
      IDs are cityHash64 of the originals — identity only, not traceable.
  content(content_id UInt32, title, video_type, category)
      Catalogue. For titles inside an aggregate, prefer
      joinGet('liv.content_join', 'title', content_id) over a JOIN.

THE THREE RULES — violating any of these produces wrong numbers:

1. COLLAPSE BEFORE AGGREGATING. `sessions` in conc_minute is a max-semantics
   column. Summing raw rows double-counts. `concurrency_minute` has done this
   already; if you query conc_minute yourself, do it explicitly.

2. SUM ACROSS DIMENSIONS, THEN MAX OVER MINUTES — never the reverse.
   Concurrency is additive across dimensions at a FIXED minute (a session has
   exactly one platform, one country, one title) but NOT across minutes. So:
     WITH per_minute AS (
       SELECT minute, sum(sessions) AS c FROM concurrency_minute
       WHERE <filters> GROUP BY minute)
     SELECT max(c) AS peak, argMax(minute, c) AS peak_minute FROM per_minute

3. PEAK IS NEVER STORED AND NEVER ROLLED UP. Different dimension combinations
   peak at different minutes: the Android peak and the Android+India peak are
   at different times. Always recompute from the minute series.

AVERAGE CONCURRENCY — divide by EVERY minute in the requested range, not by
minutes that happen to have rows. Minutes with zero viewing would otherwise
vanish and inflate the answer:
   sum(c) / dateDiff('minute', <from>, <to>)

USERS vs SESSIONS — sessions are additive, users are not. One person watching
on a phone and a TV is two sessions but one viewer. Use uniqExactMerge(users),
never sum.

FOREGROUND ONLY — backgrounded viewing is already excluded from these tables.
Heartbeats continue firing while an app is backgrounded, so those minutes were
subtracted explicitly during the rollup. You do not need to filter for it.

RULES OF ENGAGEMENT
  - SELECT statements only. Never modify data.
  - Query first, then answer from the results. Never estimate.
  - Always report the minute a peak occurred, not just its value.
  - If a filter returns nothing, say so plainly rather than reporting zero as
    if it were a measurement.
"""


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load_agents() -> dict[str, AgentConfig]:
    """Discover all AGENT_N_* blocks from the environment."""
    agents: dict[str, AgentConfig] = {}
    i = 1
    while True:
        prefix = f"AGENT_{i}_"
        agent_id = _get(prefix + "ID")
        if not agent_id:
            break

        agents[agent_id] = AgentConfig(
            id=agent_id,
            provider=_get(prefix + "PROVIDER", "anthropic").lower(),
            model=_get(prefix + "MODEL"),
            system=_get(prefix + "SYSTEM") or "You are a helpful concurrency analyst.",
            description=_get(prefix + "DESCRIPTION"),
            prompt_name=_get(prefix + "PROMPT"),
            prompt_label=_get(prefix + "PROMPT_LABEL", "production") or "production",
            append_tool_hint=_get(prefix + "APPEND_TOOL_HINT", "true").lower() != "false",
            temperature=float(_get(prefix + "TEMPERATURE", "0.2") or 0.2),
            max_tokens=int(_get(prefix + "MAX_TOKENS", "1024") or 1024),
        )
        i += 1

    if not agents:
        agents["liv-concurrency"] = AgentConfig(
            id="liv-concurrency",
            provider="anthropic",
            model="claude-sonnet-4-6",
            system="You are the SonyLIV concurrency analyst.",
        )
    return agents


PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_KEY",
    "google": "GOOGLE_KEY",
    "xai": "XAI_API_KEY",
}


# ── Supervisor ────────────────────────────────────────────────────────────────
@dataclass
class SupervisorConfig:
    id: str
    provider: str
    model: str
    system: str
    prompt_name: str = ""
    prompt_label: str = "production"
    delegates: list[str] = field(default_factory=list)
    temperature: float = 0.1
    max_tokens: int = 1500


SUPERVISOR_BASE_SYSTEM = """\
You are the lead analyst for SonyLIV concurrency. You do not query the database
yourself — you have a team of specialists who do, and each is a tool you can
call.

Route by what the question actually needs:
  - a number, a peak, a time range, a filtered slice  -> the concurrency analyst
  - a comparison across platforms, countries, content types, or titles
    -> the segment analyst
  - provisioning, headroom, "what should we size for" -> the capacity planner

Call more than one specialist when a question spans their areas, and synthesise
their answers into one reply rather than pasting them end to end. When
specialists disagree, say so and explain which reading you trust.

Never invent a number. If you have not called a specialist, you do not have
data. Pass the user's question through with enough context that the specialist
can act on it alone — they cannot see this conversation.

Answer in concise prose, no markdown headers or bullet symbols. Attribute
plainly when it helps ("the segment breakdown shows…"), but do not narrate
your routing decisions.
"""


def load_supervisor(agents: dict[str, AgentConfig]) -> SupervisorConfig | None:
    """Read SUPERVISOR_* env. Returns None when no supervisor is configured."""
    sup_id = _get("SUPERVISOR_ID")
    if not sup_id:
        return None

    raw = _get("SUPERVISOR_DELEGATES")
    delegates = [d.strip() for d in raw.split(",") if d.strip()] if raw else list(agents)

    return SupervisorConfig(
        id=sup_id,
        provider=_get("SUPERVISOR_PROVIDER", "xai").lower(),
        model=_get("SUPERVISOR_MODEL", "grok-4.5"),
        system=_get("SUPERVISOR_SYSTEM") or SUPERVISOR_BASE_SYSTEM,
        prompt_name=_get("SUPERVISOR_PROMPT"),
        prompt_label=_get("SUPERVISOR_PROMPT_LABEL", "production") or "production",
        delegates=[d for d in delegates if d in agents],
        temperature=float(_get("SUPERVISOR_TEMPERATURE", "0.1") or 0.1),
        max_tokens=int(_get("SUPERVISOR_MAX_TOKENS", "1500") or 1500),
    )
