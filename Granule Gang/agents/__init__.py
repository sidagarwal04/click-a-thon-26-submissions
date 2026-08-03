"""
Atlys Click-a-thon 2026 - Agent System

A system of three agents on ClickHouse:
- Instrumentation Agent: feature spec -> production-ready ClickHouse schemas
- Analytics Agent: queries data, applies context, writes insight summaries
- Context Agent: maintains living context layer, feeds it to other agents

Plus:
- Tracing: Langfuse integration for full pipeline tracing
- Visualization: Visualization layer for the entire pipeline
"""

from .instrumentation.agent import InstrumentationAgent
from .analytics.agent import AnalyticsAgent
from .context.agent import ContextAgent
from .tracing.agent import TracingAgent
from .config import (
    ClickHouseConfig,
    LangfuseConfig,
    OpenRouterConfig,
    load_dotenv,
    get_config,
    make_llm_call_fn,
)

__all__ = [
    "InstrumentationAgent",
    "AnalyticsAgent",
    "ContextAgent",
    "TracingAgent",
    "ClickHouseConfig",
    "LangfuseConfig",
    "OpenRouterConfig",
    "load_dotenv",
    "get_config",
    "make_llm_call_fn",
]