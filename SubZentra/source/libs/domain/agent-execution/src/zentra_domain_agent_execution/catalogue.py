from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .contracts import AgentRole


class AgentCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=280)


class PublicAgent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(min_length=1, max_length=128)
    role: AgentRole
    version: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=280)
    enabled: bool
    evaluation_status: str = Field(min_length=1, max_length=16)
    capabilities: tuple[AgentCapability, ...]
