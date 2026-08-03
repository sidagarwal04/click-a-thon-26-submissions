"""The three deterministic agents + correlation + MV helpers.

Agents are event handlers (D4): each subscribes to event types on the bus and
emits downstream events. None of them call an LLM (D6).
"""
