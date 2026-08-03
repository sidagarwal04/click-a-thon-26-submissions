"""Azure OpenAI (Foundry) client — narration only; never invents metric numbers."""

from __future__ import annotations

from openai import OpenAI

from clickathon.config import Settings, get_settings


def make_client(settings: Settings | None = None) -> OpenAI:
    s = settings or get_settings()
    if not s.llm_base_url or not s.llm_api_key:
        raise RuntimeError(
            "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT / "
            "AZURE_OPENAI_API_KEY (or OPENAI_BASE_URL / OPENAI_API_KEY) in .env"
        )
    return OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key)


def complete(prompt: str, *, settings: Settings | None = None) -> str:
    """Run a single Responses API call; return assistant text only."""
    s = settings or get_settings()
    client = make_client(s)
    response = client.responses.create(model=s.llm_model, input=prompt)

    # Prefer convenience property when present
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    parts: list[str] = []
    for item in response.output or []:
        item_type = getattr(item, "type", None) or ""
        if item_type and item_type not in ("message", "output_text"):
            # skip reasoning / tool stubs
            if item_type == "reasoning":
                continue
        content = getattr(item, "content", None)
        if content:
            for block in content:
                block_type = getattr(block, "type", None)
                if block_type in (None, "output_text", "text"):
                    t = getattr(block, "text", None)
                    if t:
                        parts.append(t)
            continue
        t = getattr(item, "text", None)
        if t and item_type != "reasoning":
            parts.append(t)
    return "\n".join(parts).strip()
