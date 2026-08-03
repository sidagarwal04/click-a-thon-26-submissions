"""Structured LLM calls. The ONLY module that talks to a model.

AUTH: this runs on the user's **Claude subscription**, not an API key. Calls shell
out to the authenticated `claude` CLI in headless mode (`claude -p`), which uses
the existing Claude Code login. No ANTHROPIC_API_KEY is required.

Set ATLYS_LLM_BACKEND=api to use the Anthropic SDK with an API key instead; the
public interface is identical either way.

`complete_json` REQUIRES `context_version` as a keyword argument. That is
deliberate: you physically cannot make a traced LLM call in this codebase without
declaring which context snapshot fed it. The "based on what context" judging
criterion is satisfied mechanically rather than by discipline.

Retries feed the validation error back to the model, which fixes most schema
misses on the first retry.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

import tracing

load_dotenv()

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = os.getenv("ATLYS_LLM_MODEL", "claude-sonnet-5")
BACKEND = os.getenv("ATLYS_LLM_BACKEND", "cli")
# "cli" (Claude subscription) | "api" (Anthropic SDK) | "openai" (any
# OpenAI-compatible /v1 host, e.g. Ollama Cloud) | "mock" (deterministic, offline)
CLI_TIMEOUT_S = int(os.getenv("ATLYS_LLM_TIMEOUT_S", "600"))
# Every task in this file is bounded structured-JSON emission: the prompt already hands
# the model the full computed context (profile, house rules, query frames), so there is
# nothing open-ended to explore. Measured cost of leaving effort unset (the CLI default,
# empirically high/xhigh): 15-30K output tokens and 2.5-5 minutes PER CALL, almost all of
# it hidden reasoning, not the JSON payload -- a real DDLProposal is a few thousand tokens
# at most. "low" is the right default for this workload; escalate per-call if you have a
# specific task that genuinely benefits from deeper exploration.
DEFAULT_EFFORT = os.getenv("ATLYS_LLM_EFFORT", "low")

_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0}


def usage() -> dict[str, Any]:
    return dict(_usage)


def backend_info() -> str:
    if BACKEND == "mock":
        return "deterministic mock (offline, no credentials) — mockllm.py"
    if BACKEND == "cli":
        return f"claude CLI (subscription auth), model={DEFAULT_MODEL}"
    if BACKEND == "openai":
        return f"OpenAI-compatible {OPENAI_BASE_URL}, model={DEFAULT_MODEL}"
    return f"anthropic SDK (API key), model={DEFAULT_MODEL}"


# --------------------------------------------------------------------------
# CLI backend -- subscription auth
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> Any:
    """Pull a JSON value out of a model response that may carry fences or prose."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = _FENCE.search(text)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Fall back to the outermost {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON object found in model output: {text[:400]}")


def _cli_call(
    system: str, user: str, model: str, effort: str | None = None
) -> tuple[str, dict[str, Any]]:
    """One headless `claude -p` turn. Returns (result_text, usage_dict)."""
    if not shutil.which("claude"):
        raise RuntimeError(
            "the `claude` CLI is not on PATH. Install Claude Code and log in, "
            "or set ATLYS_LLM_BACKEND=api with ANTHROPIC_API_KEY."
        )
    cmd = [
        "claude",
        "-p",
        user,
        "--system-prompt",
        system,
        "--exclude-dynamic-system-prompt-sections",
        # No tools: a schema-design call must not be able to touch the filesystem.
        "--allowed-tools",
        "",
        # Do not inherit project/user settings -- keeps runs reproducible.
        "--setting-sources",
        "",
        "--model",
        model,
        "--output-format",
        "json",
        "--effort",
        effort or DEFAULT_EFFORT,
    ]
    # An API key in the environment SILENTLY OVERRIDES the subscription login and
    # the CLI then refuses to run. .env files and CI often set one, so strip every
    # competing auth source from the child environment rather than trusting it.
    child_env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE")
    }
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
        cwd="/tmp",
        env=child_env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed ({proc.returncode}): {proc.stderr[:800]}")

    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI returned an error: {envelope.get('result')}")

    u = envelope.get("usage", {}) or {}
    stats = {
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
        "cost_usd": envelope.get("total_cost_usd", 0.0) or 0.0,
        "duration_ms": envelope.get("duration_ms", 0),
        "session_id": envelope.get("session_id", ""),
    }
    return envelope.get("result", ""), stats


# --------------------------------------------------------------------------
# API backend -- API key (fallback)
# --------------------------------------------------------------------------


def _api_call(system: str, user: str, model: str, max_tokens: int) -> tuple[str, dict]:
    import anthropic

    client = anthropic.Anthropic()  # resolves key / OAuth profile from environment
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cost_usd": 0.0,
    }


# --------------------------------------------------------------------------
# OpenAI-compatible backend -- any /v1/chat/completions host (Ollama Cloud, vLLM, ...)
# --------------------------------------------------------------------------

#: Where an OpenAI-compatible backend points. Defaults to Ollama Cloud because that is
#: the one we have credentials for; any host exposing /v1/chat/completions works.
OPENAI_BASE_URL = os.getenv("ATLYS_LLM_BASE_URL", "https://ollama.com/v1").rstrip("/")


def _openai_key() -> str:
    return (os.getenv("ATLYS_LLM_API_KEY") or os.getenv("OLLAMA_API_KEY") or "").strip()


def _openai_call(system: str, user: str, model: str, max_tokens: int) -> tuple[str, dict]:
    """POST to an OpenAI-compatible /chat/completions endpoint.

    Deliberately urllib rather than the `openai` package: this adds a whole model family
    to the bake-off without adding a dependency, and the request shape is four keys.

    No `effort` knob here -- that is a Claude-CLI concept. Comparing models on their own
    default reasoning behaviour is the honest comparison anyway; forcing an equivalent
    would mean inventing one.
    """
    import urllib.error
    import urllib.request

    key = _openai_key()
    if not key:
        raise RuntimeError(
            "ATLYS_LLM_BACKEND=openai needs a key: set ATLYS_LLM_API_KEY (or "
            "OLLAMA_API_KEY) in .env."
        )
    body = json.dumps(
        {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        f"{OPENAI_BASE_URL}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        raw = json.loads(urllib.request.urlopen(req, timeout=CLI_TIMEOUT_S).read())
    except urllib.error.HTTPError as exc:
        # 403 here is a plan/tier restriction, not a bad key -- measured: the same key
        # that serves gpt-oss:* is refused for the larger hosted models. Say which.
        raise RuntimeError(
            f"{OPENAI_BASE_URL} returned {exc.code} for model {model!r}: "
            f"{exc.read()[:200]!r}"
        ) from None
    text = raw["choices"][0]["message"]["content"]
    usage = raw.get("usage", {}) or {}
    return text, {
        "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "output_tokens": int(usage.get("completion_tokens", 0) or 0),
        "cost_usd": 0.0,  # self-hosted / flat-rate: no per-token price to claim
    }


def _call(
    system: str, user: str, model: str, max_tokens: int, effort: str | None = None
) -> tuple[str, dict]:
    if BACKEND == "openai":
        return _openai_call(system, user, model, max_tokens)
    if BACKEND == "mock":
        # Opt-in deterministic offline backend. Synthesizes schema-valid JSON from the
        # schema embedded in the system prompt; downstream deterministic gates (lint,
        # dry-run, grounding, metric policy) are unchanged, so a mock run degrades only
        # in prose quality, never in correctness. See mockllm.py.
        import mockllm
        return mockllm.mock_call(system, user)
    if BACKEND == "cli":
        return _cli_call(system, user, model, effort=effort)
    return _api_call(system, user, model, max_tokens)  # API backend: effort not wired (rare path)


def _record(stats: dict[str, Any]) -> None:
    _usage["calls"] += 1
    _usage["input_tokens"] += stats.get("input_tokens", 0)
    _usage["output_tokens"] += stats.get("output_tokens", 0)
    _usage["cost_usd"] += stats.get("cost_usd", 0.0)


# --------------------------------------------------------------------------
# Public interface -- unchanged across backends
# --------------------------------------------------------------------------

_JSON_RULES = (
    "\n\nRespond with a SINGLE JSON object conforming exactly to this JSON Schema.\n"
    "Output ONLY the JSON: no prose, no explanation, no markdown code fences.\n\n"
    "JSON Schema:\n{schema}\n"
)


def complete_json(
    *,
    name: str,
    system: str,
    user: str,
    schema: type[T],
    context_version: int,
    model: str | None = None,
    max_tokens: int = 8000,
    retries: int = 2,
    effort: str | None = None,
) -> T:
    """Call the model and return a validated pydantic object of type `schema`.

    `effort` defaults to `DEFAULT_EFFORT` ("low") -- these are all bounded structured-JSON
    tasks with the full context handed in, not open-ended exploration. On a validation
    failure, retries step up one level (low -> medium -> high) rather than repeating the
    same effort that already failed -- a schema miss is sometimes genuinely a reasoning
    gap, not just a formatting slip.
    """
    model = model or DEFAULT_MODEL
    json_schema = json.dumps(schema.model_json_schema(), indent=2)
    sys_prompt = system + _JSON_RULES.format(schema=json_schema)
    prompt = user
    last_error = ""
    effort_ladder = [effort or DEFAULT_EFFORT, "medium", "high"]

    with tracing.generation(
        name, model=model, context_version=context_version, schema=schema.__name__
    ) as gen:
        gen.update(input={"system": sys_prompt[:4000], "user": user[:20000]})
        for attempt in range(retries + 1):
            this_effort = effort_ladder[min(attempt, len(effort_ladder) - 1)]
            try:
                text, stats = _call(sys_prompt, prompt, model, max_tokens, effort=this_effort)
                _record(stats)
                obj = schema.model_validate(_extract_json(text))
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:3000]
            except Exception as exc:  # transport / CLI failure
                last_error = f"{type(exc).__name__}: {exc}"[:3000]
            else:
                gen.update(
                    output=obj.model_dump(mode="json"),
                    usage_details={
                        "input": stats.get("input_tokens", 0),
                        "output": stats.get("output_tokens", 0),
                    },
                    metadata={
                        "attempt": attempt,
                        "effort": this_effort,
                        "context_version": context_version,
                        "backend": BACKEND,
                        "cost_usd": stats.get("cost_usd", 0.0),
                    },
                )
                return obj

            if attempt < retries:
                prompt = (
                    f"{user}\n\n---\nYour previous response did not validate against "
                    f"{schema.__name__}:\n{last_error}\n\n"
                    "Emit a corrected JSON object. Output ONLY the JSON."
                )

        gen.update(output={"error": last_error}, level="ERROR")
    raise RuntimeError(f"{name}: failed to produce a valid {schema.__name__}: {last_error}")


def complete_text(
    *,
    name: str,
    system: str,
    user: str,
    context_version: int,
    model: str | None = None,
    max_tokens: int = 4000,
) -> str:
    model = model or DEFAULT_MODEL
    with tracing.generation(name, model=model, context_version=context_version) as gen:
        gen.update(input={"system": system[:4000], "user": user[:20000]})
        text, stats = _call(system, user, model, max_tokens)
        _record(stats)
        gen.update(
            output=text[:8000],
            usage_details={
                "input": stats.get("input_tokens", 0),
                "output": stats.get("output_tokens", 0),
            },
            metadata={"backend": BACKEND, "cost_usd": stats.get("cost_usd", 0.0)},
        )
        return text
