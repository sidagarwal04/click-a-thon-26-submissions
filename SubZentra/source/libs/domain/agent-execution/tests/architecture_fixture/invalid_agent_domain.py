"""Known-bad fixture proving the guard detects the agent stack leaking inward.

ADR-001 keeps the orchestration framework and model SDK as adapters. If either
ever reaches domain code, this is what CI must catch.
"""

import anthropic
import openai
from langgraph.graph import StateGraph

client = anthropic.Anthropic()
routed = openai.OpenAI()
graph = StateGraph(dict)
