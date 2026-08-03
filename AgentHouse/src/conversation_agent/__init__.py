"""Conversation / analytics agents."""

__all__ = ["get_analytics_tools"]


def get_analytics_tools():
    from conversation_agent.tools import get_analytics_tools as _factory

    return _factory()
