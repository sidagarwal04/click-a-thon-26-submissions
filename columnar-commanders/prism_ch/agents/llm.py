"""Minimal, traced LLM access.

Deliberately thin: one function, one provider abstraction, every call wrapped in
a Langfuse generation span so token cost and prompts land in the trace. Swapping
providers touches this file only.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from ..config import Settings
from ..tracing import llm_call

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of a completion.

    Models wrap JSON in prose or fences more often than they should; failing the
    whole run over a stray ``` would be an expensive way to be pedantic.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            log.warning(
                "unparseable JSON (%d chars), tail: %s", len(text), text[-200:]
            )
            raise LLMError(f"could not parse JSON from completion: {exc}") from exc

    log.warning("unparseable completion (%d chars), tail: %s", len(text), text[-200:])
    raise LLMError("completion contained no JSON object")


# Provider-agnostic markers of "busy, try again" rather than "you asked wrong".
_TRANSIENT = (
    "503",
    "429",
    "500",
    "502",
    "504",
    "unavailable",
    "overloaded",
    "high demand",
    "rate limit",
    "timeout",
    "timed out",
    "connection",
)


def _is_transient(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    # Unparseable or truncated output is stochastic: the same prompt often
    # returns clean JSON on the next attempt, so re-asking is worth a retry.
    if isinstance(exc, LLMError) and ("json" in text or "truncated" in text):
        return True
    return any(marker in text for marker in _TRANSIENT)


def _dispatch(
    settings: Settings, *, model: str, system: str, prompt: str, max_tokens: int
) -> tuple[str, dict[str, int]]:
    """Returns (completion text, token usage).

    Usage is a Langfuse baseline requirement - without input/output tokens it
    cannot compute cost, so every provider reports them in the same shape.
    """
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return _anthropic(
            settings, model=model, system=system, prompt=prompt, max_tokens=max_tokens
        )
    if provider == "openai":
        return _openai(settings, model=model, system=system, prompt=prompt, max_tokens=max_tokens)
    if provider in ("gemini", "google"):
        return _gemini(settings, model=model, system=system, prompt=prompt, max_tokens=max_tokens)
    raise LLMError(f"unknown LLM_PROVIDER {settings.llm_provider!r}")


def complete(
    settings: Settings,
    *,
    name: str,
    system: str,
    prompt: str,
    max_tokens: int | None = None,
    as_json: bool = False,
) -> str | dict[str, Any]:
    """Run one completion, retrying transient provider failures.

    A hosted model answering "503, high demand" is routine, and on the unseen
    spec there is no second attempt to fall back on - so retry with backoff, and
    optionally fail over to LLM_FALLBACK_MODEL. Errors that are *our* fault
    (bad model id, bad key, malformed request) are raised immediately; retrying
    those just burns the clock.
    """
    provider = settings.llm_provider.lower()
    max_tokens = max_tokens or settings.llm_max_tokens
    models = [settings.llm_model]
    if settings.llm_fallback_model and settings.llm_fallback_model != settings.llm_model:
        models.append(settings.llm_fallback_model)

    last: Exception | None = None

    for model in models:
        for attempt in range(1, settings.llm_max_retries + 1):
            try:
                with llm_call(name, model=model, prompt=prompt, provider=provider) as span:
                    result = _dispatch(
                        settings, model=model, system=system, prompt=prompt, max_tokens=max_tokens
                    )
                    text, usage = result if isinstance(result, tuple) else (result, {})
                    cost = settings.cost_details(usage, model)
                    span.update(
                        output=text,
                        usage_details=usage or None,
                        cost_details=cost or None,
                    )
                    if cost:
                        log.debug(
                            "%s: %d+%d tokens, $%.6f",
                            model,
                            usage.get("input", 0),
                            usage.get("output", 0),
                            cost.get("total", 0),
                        )
                return _extract_json(text) if as_json else text
            except Exception as exc:  # noqa: BLE001 - classified below
                last = exc
                if not _is_transient(exc):
                    raise
                if attempt < settings.llm_max_retries:
                    delay = min(2 ** (attempt - 1), 30)
                    log.warning(
                        "%s on %s (attempt %d/%d) - retrying in %ds: %s",
                        type(exc).__name__,
                        model,
                        attempt,
                        settings.llm_max_retries,
                        delay,
                        str(exc)[:160],
                    )
                    time.sleep(delay)
        if model != models[-1]:
            log.warning("%s exhausted - failing over to %s", model, models[-1])

    raise LLMError(f"all LLM attempts failed ({len(models)} model(s)): {last}") from last


def _anthropic(
    settings: Settings, *, model: str, system: str, prompt: str, max_tokens: int
) -> tuple[str, dict[str, int]]:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on install
        raise LLMError("anthropic SDK not installed - `pip install anthropic`") from exc

    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    usage = getattr(response, "usage", None)
    return text, {
        "input": getattr(usage, "input_tokens", 0) or 0,
        "output": getattr(usage, "output_tokens", 0) or 0,
    }


def _gemini(
    settings: Settings, *, model: str, system: str, prompt: str, max_tokens: int
) -> tuple[str, dict[str, int]]:
    """Google Gemini via the `google-genai` SDK.

    A wrong model id surfaces here as a 404 naming the id you passed - check it
    against the current model list rather than assuming, the names move often.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - depends on install
        raise LLMError("google-genai SDK not installed - `pip install google-genai`") from exc

    if not settings.google_api_key:
        raise LLMError("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set")

    client = genai.Client(api_key=settings.google_api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            # The schema prompt demands a JSON object; asking for it directly
            # beats parsing it back out of prose.
            response_mime_type="application/json",
        ),
    )

    # A truncated response is valid-looking text that fails to parse hundreds of
    # lines later. Name the real cause here rather than leaving a JSON decode
    # error to be misread as the model emitting garbage.
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        reason = str(getattr(candidates[0], "finish_reason", "") or "")
        if "MAX_TOKENS" in reason.upper():
            raise LLMError(
                f"response truncated at max_output_tokens={max_tokens} - "
                "raise LLM_MAX_TOKENS"
            )
    meta = getattr(response, "usage_metadata", None)
    return response.text or "", {
        "input": getattr(meta, "prompt_token_count", 0) or 0,
        "output": getattr(meta, "candidates_token_count", 0) or 0,
    }


EMBED_DIM = 768


def embed(settings: Settings, texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a batch of texts.

    Uses the provider's native embedding API. Falls back across providers
    if the primary one has no embedding support.
    """
    provider = settings.llm_provider.lower()

    def _run(fn: Any, mdl: str) -> list[list[float]]:
        with llm_call(
            "embed",
            model=mdl,
            prompt={"texts": len(texts)},
            observation_type="embedding",
            provider=provider,
        ) as span:
            result = fn(settings, texts)
            span.update(
                output={"vectors": len(result), "dimensions": len(result[0]) if result else 0}
            )
            return result

    try:
        if provider in ("gemini", "google") and settings.google_api_key:
            return _run(_embed_gemini, "gemini-embedding-001")
        if provider == "openai" and settings.openai_api_key:
            return _run(_embed_openai, "text-embedding-3-small")
    except Exception as exc:
        log.warning("embedding via %s failed: %s", provider, exc)

    if settings.google_api_key:
        return _run(_embed_gemini, "gemini-embedding-001")
    if settings.openai_api_key:
        return _run(_embed_openai, "text-embedding-3-small")
    raise LLMError("no embedding provider available — set GOOGLE_API_KEY or OPENAI_API_KEY")


def _embed_gemini(settings: Settings, texts: list[str]) -> list[list[float]]:
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts,
    )
    return [e.values for e in result.embeddings]


def _embed_openai(settings: Settings, texts: list[str]) -> list[list[float]]:
    import openai

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [d.embedding for d in response.data]


def _openai(
    settings: Settings, *, model: str, system: str, prompt: str, max_tokens: int
) -> tuple[str, dict[str, int]]:
    try:
        import openai
    except ImportError as exc:  # pragma: no cover - depends on install
        raise LLMError("openai SDK not installed - `pip install openai`") from exc

    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set")

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=model,
        max_completion_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    usage = getattr(response, "usage", None)
    return response.choices[0].message.content or "", {
        "input": getattr(usage, "prompt_tokens", 0) or 0,
        "output": getattr(usage, "completion_tokens", 0) or 0,
    }
