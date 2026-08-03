"""The actual agentic loop, run directly against OpenAI's Responses API.

Replaces LibreChat's Agents API as the thing that executes our 4 agents.
Confirmed via direct testing (not assumed) that going straight to OpenAI gets
us three things LibreChat's beta proxy never returned:
  1. Real function_call arguments (LibreChat: always "").
  2. Real reasoning summaries, with reasoning.effort="medium"+ and
     summary="detailed" (LibreChat: no reasoning item in the output at all,
     confirmed in streaming, non-streaming, and with an explicit param).
  3. Working previous_response_id chaining (LibreChat: conversationId never
     surfaced anywhere, confirmed 404 on every attempt) -- so a multi-turn tool
     loop here only sends the NEW function_call_output items each turn, not the
     whole conversation over again.

Tool execution is fully local: agent_runner.mcp_tools talks to our own MCP
servers directly, agent_runner.skills serves skill file reads. Nothing routes
through LibreChat anymore.
"""
from __future__ import annotations

import json
import os
import sys
import pathlib
from dataclasses import dataclass, field

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agents.prompts import AGENTS  # noqa: E402
from agent_runner import mcp_tools, schemas, skills  # noqa: E402

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MODEL = "gpt-5.6-luna"
# "low" effort suppresses reasoning summaries entirely (confirmed: reasoning_tokens
# spent but summary=[] every time) -- "medium" reliably produces real summary text
# at a reasonable cost step up from "low". Not "high": real cost/latency jump for
# marginal quality gain on tasks that are mostly tool-orchestration, not deep
# reasoning.
REASONING = {"effort": "medium", "summary": "detailed"}
MAX_TURNS = 20  # safety cap on the tool-calling loop, not a normal-case limit


@dataclass
class AgentResult:
    output_text: str
    tool_calls: list[dict] = field(default_factory=list)
    reasoning: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    response_id: str | None = None  # last response's id -- pass as resume_from to continue this exact conversation later


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }


def _build_system_prompt(agent_key: str) -> str:
    instructions = AGENTS[agent_key]["instructions"]
    skill_content = skills.inline_skill_content(agent_key)
    if skill_content:
        return f"{instructions}\n\n{skill_content}"
    return instructions


def _build_tools(agent_key: str) -> list[dict]:
    tool_names = AGENTS[agent_key].get("tools", [])
    defs = mcp_tools.openai_tool_defs(tool_names) if tool_names else []
    if agent_key in skills.SKILLS_BY_AGENT:
        defs.append(skills.LIST_SKILL_FILES_TOOL)
        defs.append(skills.READ_SKILL_FILE_TOOL)
    return defs


def _text_format(agent_key: str) -> dict:
    """Strict json_schema when this agent has one defined (guarantees every
    required key/type in the final message, not just "valid JSON" -- see
    agent_runner/schemas.py's module docstring for why json_object mode alone
    proved insufficient on real runs). Falls back to plain json_object for any
    agent without a defined schema, rather than no constraint at all."""
    schema = schemas.SCHEMAS.get(agent_key)
    if schema:
        return {"format": {"type": "json_schema", "name": f"{agent_key}_output", "strict": True, "schema": schema}}
    return {"format": {"type": "json_object"}}


def _execute_function_call(name: str, arguments_json: str) -> str:
    if name in ("read_skill_file", "list_skill_files"):
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as e:
            return f"ERROR: could not parse arguments: {e}"
        if name == "list_skill_files":
            return skills.list_skill_files(args.get("skill_name", ""))
        return skills.read_skill_file(args.get("path", ""))
    return mcp_tools.execute_tool(name, arguments_json)


def run_agent(
    agent_key: str, input_text: str, timeout: int = 180, on_event=None,
    resume_from: str | None = None,
) -> AgentResult:
    """Runs one agent to completion: sends the initial turn, then loops on any
    function_call items (executing each for real, against our own MCP servers or
    the skill-file reader) until the model produces a final message with no more
    pending calls. Uses previous_response_id chaining between turns -- confirmed
    working against OpenAI directly (unlike LibreChat's proxy).

    `resume_from`: continue a PRIOR run_agent() call's conversation (pass its
    AgentResult.response_id) instead of starting fresh. Used across rework
    revisions -- e.g. the proposer's revision-2 call resumes revision-1's own
    conversation instead of re-explaining the whole prior draft/findings in
    text every time, giving it real memory of what it already said rather
    than a re-summarized context dump. Costs nothing extra to wire: it's
    exactly the same previous_response_id chaining already used for the
    in-loop tool-calling turns below, just seeded from a PRIOR call's final
    response instead of always starting from None.

    `on_event(kind, name, input, output)`, if given, fires LIVE as each reasoning
    chunk or tool call happens -- not batched until the whole loop finishes. That
    batching was a real gap: a multi-turn loop can run 10-20 tool calls, and
    nothing was visible until it fully completed, indistinguishable from a hang
    (confirmed: a run once hit a 120s single-turn timeout with zero intermediate
    signal). `kind` is "reasoning" or "tool_call"; decoupled from tracing.Run so
    this module has no dependency on it -- the caller (orchestrator/agent_io.py)
    wires this to real run.log() calls."""
    tools = _build_tools(agent_key)

    # OpenAI's json_object mode requires the literal word "json" somewhere in the
    # INPUT messages specifically -- having it in `instructions` does NOT satisfy
    # this (confirmed via a real 400: "Response input messages must contain the
    # word 'json'..."). Confirmed separately: this only needs to be satisfied
    # ONCE on the first turn of a previous_response_id-chained conversation --
    # true whether that's this call's own first turn, or (via resume_from) the
    # first turn of the ORIGINAL conversation being resumed. Cheap to always
    # include rather than track whether it's already been said once.
    input_text = f"{input_text}\n\n(Respond with a single valid JSON object as your final message, per your system instructions.)"

    # Strict json_schema (agent_runner/schemas.py) when defined -- guarantees
    # every required key/type in the final message at the API level, not just
    # "valid JSON" (json_object mode alone let real runs drift on a DIFFERENT
    # malformed field almost every revision -- column_mapping, then
    # ordering_key_candidates, then columns_ddl twice -- burning an entire
    # revision budget on JSON formatting instead of substance).
    text_format = _text_format(agent_key)

    all_tool_calls: list[dict] = []
    reasoning_chunks: list[str] = []
    usage_totals = {"input": 0, "output": 0, "total": 0}
    last_response: dict = {}
    previous_response_id: str | None = resume_from
    pending_input: str | list = input_text

    for _turn in range(MAX_TURNS):
        turn_payload: dict = {
            "model": MODEL,
            "input": pending_input,
            "store": True,
            "reasoning": REASONING,
            "text": text_format,
        }
        if previous_response_id:
            # Continuing a conversation (either an in-loop tool-calling turn,
            # or turn 0 via resume_from) -- system prompt is already
            # established, only the new items get sent.
            turn_payload["previous_response_id"] = previous_response_id
        else:
            turn_payload["instructions"] = _build_system_prompt(agent_key)
        if tools:
            turn_payload["tools"] = tools

        resp = requests.post(OPENAI_RESPONSES_URL, headers=_headers(), json=turn_payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        last_response = data
        previous_response_id = data.get("id")

        usage = data.get("usage", {})
        usage_totals["input"] += usage.get("input_tokens", 0)
        usage_totals["output"] += usage.get("output_tokens", 0)
        usage_totals["total"] += usage.get("total_tokens", 0)

        function_calls = []
        output_text_parts = []
        for item in data.get("output", []):
            item_type = item.get("type")
            if item_type == "reasoning":
                for s in item.get("summary", []):
                    if s.get("type") == "summary_text":
                        text = s.get("text", "")
                        reasoning_chunks.append(text)
                        if on_event:
                            on_event("reasoning", f"turn{_turn}", None, text)
            elif item_type == "message":
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text"):
                        output_text_parts.append(c.get("text", ""))
            elif item_type == "function_call":
                function_calls.append(item)

        if not function_calls:
            return AgentResult(
                output_text="\n".join(output_text_parts).strip(),
                tool_calls=all_tool_calls,
                reasoning="\n\n".join(reasoning_chunks),
                usage=usage_totals,
                raw=last_response,
                response_id=previous_response_id,
            )

        # Execute every function call for real, build the output items the next
        # turn needs, and keep a record with the REAL arguments/output for our
        # own tracing (this is the entire point -- LibreChat never gave us this).
        next_input = []
        for fc in function_calls:
            name = fc.get("name", "")
            arguments = fc.get("arguments", "")
            call_id = fc.get("call_id")
            output = _execute_function_call(name, arguments)
            all_tool_calls.append({"name": name, "arguments": arguments, "output": output})
            if on_event:
                on_event("tool_call", name, arguments, output)
            next_input.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            })
        pending_input = next_input

    # Exhausted MAX_TURNS without a final message -- surface what we have rather
    # than silently returning nothing.
    return AgentResult(
        output_text="",
        tool_calls=all_tool_calls,
        reasoning="\n\n".join(reasoning_chunks),
        usage=usage_totals,
        raw=last_response,
        response_id=previous_response_id,
    )
