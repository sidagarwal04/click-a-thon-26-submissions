"""What an Agent may call, and what comes back when it does.

Agents made a fixed sequence of model calls before this: plan, then interpret.
That is enough to answer a question whose shape is known in advance, and it is
not enough to explore a tenant's own catalog — where the right query is not
knowable until you have looked at what the tenant actually has.

A Tool is the unit of that exploration. `ToolScope` and
`AgentDescriptor.tool_permissions` already existed and are the enforcement
point: a tool outside a descriptor's permissions is never offered to the model
*and* is refused if named anyway. That is what keeps ADR-0003's guarantee
structural once agents can act — the Cube Analyst gains iteration, not reach.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import JsonValue

from .contracts import ToolScope


class ToolDefinition(BaseModel):
    """What a model is told about a tool it may call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    #: JSON Schema for the arguments. Providers validate against this, so it
    #: must be the same object shape every provider's strict mode accepts.
    input_schema: dict[str, JsonValue]


class ToolCall(BaseModel):
    """A model asking for a tool to run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The provider's own id for this call. Echoed back on the result so a
    #: model that issued several calls in one turn can tell the answers apart.
    call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """What a tool returned, on its way back into the conversation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Empty until the runtime pairs this result to the call it answers. A
    #: tool does not know which call it is serving — and one that guessed
    #: would be guessing — so it is left blank here and filled in by the only
    #: code that does know.
    call_id: str = ""
    #: Rendered as text rather than typed, because it is going into a prompt.
    #: The tool decides how to say what it found.
    content: str
    #: A failed tool is reported to the model, never raised past it: an agent
    #: that asked for a member the catalog does not have should get told so and
    #: pick another, which is the whole point of a loop.
    is_error: bool = False


class ToolPort(Protocol):
    """One capability an Agent can be granted."""

    @property
    def definition(self) -> ToolDefinition: ...

    @property
    def scope(self) -> ToolScope: ...

    def invoke(self, arguments: dict[str, JsonValue]) -> Awaitable[ToolResult]: ...


class UnauthorizedToolError(PermissionError):
    """An Agent named a tool its descriptor does not permit."""
