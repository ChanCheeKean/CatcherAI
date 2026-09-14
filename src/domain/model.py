from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Capability(StrEnum):
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    VISION = "vision"
    REASONING_CONTROLS = "reasoning_controls"
    USAGE_REPORTING = "usage_reporting"
    PROMPT_CACHING = "prompt_caching"


class NeutralMessage(BaseModel):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class NeutralTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    actor: str
    rationale: str
    messages: list[NeutralMessage]
    tools: list[NeutralTool] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    reasoning_effort: str | None = None
    max_output_tokens: int | None = None
    timeout_seconds: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0


class NeutralToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ModelResponse(BaseModel):
    text: str = ""
    tool_calls: list[NeutralToolCall] = Field(default_factory=list)
    structured: dict[str, Any] | None = None
    finish_category: str = "success"
    usage: Usage = Field(default_factory=Usage)
    provider_request_id: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ModelStreamEvent(BaseModel):
    type: Literal["text_delta", "tool_call", "usage", "completed", "error"]
    delta: str | None = None
    response: ModelResponse | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
