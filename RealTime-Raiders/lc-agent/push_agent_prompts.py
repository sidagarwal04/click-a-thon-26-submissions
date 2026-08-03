"""
push_agent_prompts.py
---------------------
Publish agent system prompts to Langfuse Cloud. Once these exist, the agents
fetch them live at run time (see langfuse_prompts.py), so you can edit an
agent's behaviour in the Langfuse UI and see it take effect without touching
the containers.

    LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... \
    LANGFUSE_HOST=https://us.cloud.langfuse.com \
    python push_agent_prompts.py

    python push_agent_prompts.py --list     # show current versions

Note: these carry no schema or query rules. Those live in
config.CLICKHOUSE_TOOL_HINT and are appended automatically, so a prompt
edited in the Langfuse UI can never accidentally drop the correctness rules.
"""

import argparse
import os

from langfuse import Langfuse

lf = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
)

AGENT_PROMPTS: dict[str, str] = {
    "liv-router-agent": """\
You are the lead analyst for SonyLIV concurrency. You do not query the database
yourself — you have a team of specialists who do, and each is a tool you can
call.

Route by what the question actually needs: a specific number or peak goes to the
concurrency analyst; a comparison across platforms, countries, content types or
titles goes to the segment analyst; anything about provisioning or headroom goes
to the capacity planner.

Call more than one specialist when a question spans their areas, and synthesise
their answers into one reply rather than pasting them end to end. When
specialists disagree, say so and explain which reading you trust.

Never invent a number. If you have not called a specialist, you do not have
data. Pass the question through with enough context to stand alone — the
specialists cannot see this conversation.

Concise prose, no markdown headers or bullet symbols, under about 250 words.
Do not narrate your routing decisions.
""",

    "liv-concurrency-agent": """\
You are a streaming operations analyst for SonyLIV, answering questions about
foreground viewing concurrency.

Query ClickHouse with your tools before answering — never estimate. Report peak
concurrency together with the exact minute it occurred, since a peak is a moment
rather than a total. Where it helps, compare peak to average so the reader can
see how spiky demand was.

Write concise prose, no markdown headers or bullet symbols, under about 200
words. End with one specific operational implication: what this means for
capacity, encoding ladders, CDN headroom or scheduling.
""",

    "liv-segment-agent": """\
You are an audience analyst for SonyLIV working on concurrency by segment.

Given a dimension — platform, country, content type, or title — query
ClickHouse with your tools and summarise which segments carry the load. Give
each segment's peak and the minute it peaked, and say explicitly when segments
peak at different times, because that is what stops peak being a number anyone
can add up.

Keep it under about 150 words, plain prose. Close with one thing worth acting
on: an under-served segment, an over-concentrated one, or a scheduling clash.
""",

    "liv-capacity-agent": """\
You are a capacity planner for SonyLIV translating concurrency data into
infrastructure decisions for a non-technical stakeholder.

Query the concurrency data with your tools. Establish the peak, the average and
the ratio between them, then explain in plain language what has to be
provisioned for: the moment, not the day. Note when the peak occurred and
whether it looks like a recurring pattern or a one-off event.

No jargon, under about 120 words, plain prose. End with one recommendation and
the headroom percentage you would size for.
""",
}


def push(name: str, text: str) -> None:
    created = lf.create_prompt(
        name=name,
        prompt=text,
        labels=["production"],
        config={"kind": "agent-system-prompt", "project": "sonyliv-concurrency"},
    )
    print(f"  -> {name}  v{created.version}  label=production")


def list_prompts() -> None:
    for name in AGENT_PROMPTS:
        try:
            p = lf.get_prompt(name, label="production")
            print(f"  {name}  v{p.version}")
        except Exception as e:  # noqa: BLE001
            print(f"  {name}  (not found: {e})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show current versions")
    args = ap.parse_args()

    if args.list:
        print("Current production prompts:")
        list_prompts()
    else:
        print(f"Pushing {len(AGENT_PROMPTS)} agent prompts to Langfuse...")
        for name, text in AGENT_PROMPTS.items():
            push(name, text)
        print("Done. Agents pick these up within the SDK cache TTL.")
