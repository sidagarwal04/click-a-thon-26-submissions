"""
langfuse_prompts.py
-------------------
Resolve an agent's system prompt, preferring Langfuse Cloud.

If cfg.prompt_name is set, fetch that prompt by label (default "production").
The SDK caches client-side with a short TTL, so publishing a new production
version propagates within the TTL with no redeploy. On any failure — Langfuse
unreachable, key missing, prompt not found — fall back to the inline text so
the agent always runs.

The returned version tag keys agent.py's graph cache, so a newly published
version rebuilds the agent with it.
"""

from config import AgentConfig, CLICKHOUSE_TOOL_HINT


def _append_hint(text: str, cfg: AgentConfig) -> str:
    return text + CLICKHOUSE_TOOL_HINT if cfg.append_tool_hint else text


def resolve_system_prompt(cfg: AgentConfig) -> tuple[str, str]:
    """
    Return (system_text, version_tag).

    version_tag examples:
        "liv-concurrency-agent:v3"  → fetched from Langfuse, version 3
        "inline"                    → no prompt_name configured
        "inline-fallback"           → fetch failed, used cfg.system
    """
    if not cfg.prompt_name:
        return _append_hint(cfg.system, cfg), "inline"

    try:
        from langfuse import get_client

        client = get_client()
        prompt = client.get_prompt(cfg.prompt_name, label=cfg.prompt_label)

        try:
            text = prompt.compile()
        except Exception:  # noqa: BLE001 — some SDKs require exact vars
            text = prompt.prompt

        return _append_hint(text, cfg), f"{cfg.prompt_name}:v{prompt.version}"

    except Exception as e:  # noqa: BLE001 — never let prompt fetch break the agent
        print(
            f"[langfuse] prompt fetch failed for '{cfg.prompt_name}' "
            f"(label={cfg.prompt_label}): {e}; using inline fallback"
        )
        return _append_hint(cfg.system, cfg), "inline-fallback"
