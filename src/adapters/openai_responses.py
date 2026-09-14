from __future__ import annotations

import json
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

from config import ModelsConfig
from domain.model import (
    Capability,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    NeutralToolCall,
    Usage,
)


class OpenAIResponsesGateway:
    """Provider adapter; OpenAI SDK types never cross this module."""

    def __init__(self, config: ModelsConfig) -> None:
        from openai import AsyncOpenAI

        self.config = config
        self.client = AsyncOpenAI(timeout=config.default.timeout_seconds, max_retries=0)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.STRUCTURED_OUTPUT,
                Capability.TOOL_CALLING,
                Capability.STREAMING,
                Capability.VISION,
                Capability.REASONING_CONTROLS,
                Capability.USAGE_REPORTING,
                Capability.PROMPT_CACHING,
            }
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        params: dict[str, Any] = {
            "model": self.config.default.model,
            "input": [message.model_dump(exclude_none=True) for message in request.messages],
            "stream": True,
            "store": False,
            "max_output_tokens": request.max_output_tokens or self.config.default.max_output_tokens,
            "metadata": request.metadata,
        }
        if request.reasoning_effort:
            params["reasoning"] = {"effort": request.reasoning_effort, "summary": "auto"}
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": strict_function_schema(tool.input_schema),
                    "strict": True,
                }
                for tool in request.tools
            ]
        if request.output_schema:
            params["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "catcher_output",
                    "schema": request.output_schema,
                    "strict": True,
                }
            }

        stream = await self.client.responses.create(**params)
        text_parts: list[str] = []
        completed: Any = None
        async for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                text_parts.append(delta)
                yield ModelStreamEvent(type="text_delta", delta=delta)
            elif event_type == "response.completed":
                completed = getattr(event, "response", None)
            elif event_type == "error":
                yield ModelStreamEvent(type="error", payload={"message": str(event)})

        if completed is None:
            raise RuntimeError("OpenAI stream ended without response.completed")
        text = getattr(completed, "output_text", None) or "".join(text_parts)
        tool_calls: list[NeutralToolCall] = []
        for item in getattr(completed, "output", []):
            if getattr(item, "type", None) == "function_call":
                arguments = getattr(item, "arguments", "{}")
                tool_calls.append(
                    NeutralToolCall(
                        id=getattr(item, "call_id", getattr(item, "id", "")),
                        name=getattr(item, "name", ""),
                        arguments=json.loads(arguments),
                    )
                )
        raw_usage = getattr(completed, "usage", None)
        input_details = getattr(raw_usage, "input_tokens_details", None)
        output_details = getattr(raw_usage, "output_tokens_details", None)
        usage = Usage(
            input_tokens=getattr(raw_usage, "input_tokens", 0) or 0,
            output_tokens=getattr(raw_usage, "output_tokens", 0) or 0,
            cached_tokens=getattr(input_details, "cached_tokens", 0) or 0,
            reasoning_tokens=getattr(output_details, "reasoning_tokens", 0) or 0,
        )
        structured = json.loads(text) if request.output_schema and text else None
        response = ModelResponse(
            text=text,
            tool_calls=tool_calls,
            structured=structured,
            finish_category=str(getattr(completed, "status", "completed")),
            usage=usage,
            provider_request_id=getattr(completed, "id", None),
            provider_metadata={"service_tier": getattr(completed, "service_tier", None)},
        )
        yield ModelStreamEvent(type="completed", response=response)


def strict_function_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Close every JSON-Schema object as required by strict Responses tools.

    LangChain and Deep Agents emit ordinary JSON Schema, where ``additionalProperties`` is omitted
    and fields with defaults may be absent. OpenAI strict function tools require closed objects and
    every property in ``required``; formerly optional fields remain optional in meaning by accepting
    JSON null.
    """

    normalized = deepcopy(schema)

    def visit(node: Any) -> Any:
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        for key in ("$defs", "definitions"):
            if isinstance(node.get(key), dict):
                node[key] = {name: visit(value) for name, value in node[key].items()}
        for key in ("anyOf", "oneOf", "allOf"):
            if key in node:
                node[key] = visit(node[key])
        if "items" in node:
            node["items"] = visit(node["items"])
        properties = node.get("properties")
        if node.get("type") == "object" or isinstance(properties, dict):
            properties = properties or {}
            originally_required = set(node.get("required", []))
            closed: dict[str, Any] = {}
            for name, value in properties.items():
                value = visit(value)
                if name not in originally_required and not _accepts_null(value):
                    value = {"anyOf": [value, {"type": "null"}]}
                closed[name] = value
            node["properties"] = closed
            node["required"] = list(properties)
            node["additionalProperties"] = False
        return node

    return visit(normalized)


def _accepts_null(schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null" or (isinstance(schema_type, list) and "null" in schema_type):
        return True
    return any(option.get("type") == "null" for option in schema.get("anyOf", []))
