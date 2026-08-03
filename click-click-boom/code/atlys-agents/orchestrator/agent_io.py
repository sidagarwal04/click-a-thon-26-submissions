"""Shared agent I/O helpers — imported by both pipeline.py and analytics_agent.py.

Extracted into a neutral module so neither file creates a circular import by
depending on the other. pipeline.py lazily imports analytics_agent; analytics_agent
must not import pipeline at module load time.
"""
from __future__ import annotations

import json

from librechat_client import call_agent


class AgentOutputError(Exception):
    """Raised when an agent's final message isn't valid JSON."""

    def __init__(self, raw_text: str, parse_error: Exception):
        self.raw_text = raw_text
        self.parse_error = parse_error
        super().__init__(f"Agent output was not valid JSON: {parse_error}")


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        raise AgentOutputError(text, e) from e


def _check_required_keys(parsed: dict, required_keys: list[str] | None, raw_text: str) -> None:
    """Valid JSON that's missing a key the caller unconditionally accesses (e.g.
    pipeline.py's draft["ordering_key_candidates"]) used to crash with a raw
    KeyError instead of going through the same bounded retry/rework path as any
    other agent-output problem. Found on a real run: the proposer, given more
    tool-exploration latitude, sometimes writes a prose "measurement plan" with
    SQL instead of the required schema -- valid-ish output, wrong shape. Treated
    identically to invalid JSON: raises AgentOutputError so _call_json_agent's
    existing retry-once path handles it the same way."""
    if not required_keys:
        return
    missing = [k for k in required_keys if k not in parsed]
    if missing:
        raise AgentOutputError(raw_text, ValueError(f"missing required key(s): {missing}"))


def _call_json_agent(
    agent_id: str, payload: dict, run, step: str,
    required_keys: list[str] | None = None, reasoning_fn=None,
    resume_from: str | None = None, **span_metadata,
) -> tuple[dict, object]:
    """Calls an agent expecting JSON back, with full LIVE tracing -- opens
    `run.span(step)` and logs each reasoning chunk / tool call the moment it
    happens during the call, not batched until the whole multi-turn loop
    finishes. That batching used to mean nothing was visible for the entire
    duration of a 10-20-tool-call loop (confirmed: indistinguishable from a hang
    on a run that hit a 120s single-turn timeout with zero intermediate signal).

    Retries ONCE if JSON parsing fails OR the parsed JSON is missing any of
    `required_keys` (valid JSON, wrong shape -- same failure class, same retry
    path). `reasoning_fn(parsed_result) -> str`, if given, derives a human-legible
    summary from the parsed JSON (e.g. the proposer's own `rationale` field, or
    the reviewer's verdict + finding descriptions) for the dashboard's primary
    "thinking" display -- kept separate from the model's own raw reasoning
    tokens (`model_reasoning`), which are always logged too, live, per turn.

    `resume_from`: continue a PRIOR call's conversation (its AgentResult's
    response_id) instead of starting fresh -- see agent_runner.runner.run_agent's
    docstring. Used across rework revisions so e.g. the proposer's revision-2
    call has real memory of its own revision-1 turn. The retry-on-bad-JSON
    call (below) also resumes from the SAME `resume_from`, not from the failed
    attempt's own response -- that failure is an orthogonal parse-shape issue,
    not part of the cross-revision conversation being continued."""
    with run.span(step, **span_metadata):
        tool_idx = [0]

        def on_event(kind: str, name: str, input_, output_):
            if kind == "reasoning":
                run.log(step=f"{step}_reasoning[{name}]", input=None, output=output_)
            elif kind == "tool_call":
                run.log(step=f"{step}_tool[{tool_idx[0]}]_{name}", input=input_, output=output_)
                tool_idx[0] += 1

        r = call_agent(agent_id, json.dumps(payload), on_event=on_event, resume_from=resume_from)
        try:
            parsed = _extract_json(r.output_text)
            _check_required_keys(parsed, required_keys, r.output_text)
        except AgentOutputError as e:
            retry_payload = dict(payload)
            retry_payload["_previous_output_was_invalid_json"] = {
                "your_previous_output": e.raw_text[:2000],
                "parse_error": str(e.parse_error),
                "instruction": (
                    "Output ONLY the JSON object this time — no markdown fences, no "
                    "prose before or after it, no plan/explanation, every key from "
                    "your instructions' schema present." + (
                        f" Required keys: {required_keys}." if required_keys else ""
                    )
                ),
            }
            r = call_agent(agent_id, json.dumps(retry_payload), on_event=on_event, resume_from=resume_from)
            # Not wrapped in its own try/except: if the retry ALSO fails, this
            # raises AgentOutputError again and propagates out of this function
            # uncaught -- the caller's own except AgentOutputError (in
            # ingest_spec's main loop) handles that, same as before this rewrite.
            parsed = _extract_json(r.output_text)
            _check_required_keys(parsed, required_keys, r.output_text)

        # `reasoning` = the caller-derived summary (rationale / verdict+findings /
        # section diffs) shown as the dashboard's primary "thinking" callout;
        # `model_reasoning` = the real reasoning-model output, logged alongside.
        run.log(
            step=f"{step}_generation",
            input=payload,
            output=r.output_text,
            usage=r.usage if r.usage else None,
            reasoning=reasoning_fn(parsed) if reasoning_fn else None,
            model_reasoning=getattr(r, "reasoning", "") or None,
            n_tool_calls=len(r.tool_calls),
        )
    return parsed, r
