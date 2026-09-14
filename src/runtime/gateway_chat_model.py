from __future__ import annotations

import asyncio
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, Field

from domain.model import ModelRequest, NeutralMessage, NeutralTool


class GatewayChatModel(BaseChatModel):
    """The only LangChain-facing bridge around the neutral model gateway."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    gateway: Any = Field(exclude=True)
    model_name: str
    actor: str = "lead_investigator"
    case_id: str = ""
    reasoning_effort: str = "medium"
    max_output_tokens: int = 4000
    timeout_seconds: float = 60
    bound_tools: list[Any] = Field(default_factory=list, exclude=True)

    @property
    def _llm_type(self) -> str:
        return "catcher-model-gateway"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_name": self.model_name, "adapter": "catcher-model-gateway"}

    def bind_tools(
        self,
        tools: list[dict[str, Any] | type | Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> GatewayChatModel:
        del tool_choice, kwargs
        return self.model_copy(update={"bound_tools": list(tools)})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        return asyncio.run(self._generate_async(messages))

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        return await self._generate_async(messages)

    async def _generate_async(self, messages: list[BaseMessage]) -> ChatResult:
        neutral_messages = [
            NeutralMessage(
                role=_role(message),
                content=_content(message.content),
                name=getattr(message, "name", None),
                tool_call_id=getattr(message, "tool_call_id", None),
            )
            for message in messages
        ]
        request = ModelRequest(
            call_id=f"model-{uuid.uuid4().hex}",
            actor=self.actor,
            rationale="Create or revise the investigation plan",
            messages=neutral_messages,
            tools=[_normalize_tool(tool) for tool in self.bound_tools],
            reasoning_effort=self.reasoning_effort,
            max_output_tokens=self.max_output_tokens,
            timeout_seconds=self.timeout_seconds,
            metadata={"case_id": self.case_id, "role": self.actor},
        )
        response = None
        async for event in self.gateway.stream(request):
            if event.type == "completed":
                response = event.response
        if response is None:
            raise RuntimeError("model gateway did not return a completed response")
        tool_calls = [
            {"id": call.id, "name": call.name, "args": call.arguments}
            for call in response.tool_calls
        ]
        message = AIMessage(
            content=response.text,
            tool_calls=tool_calls,
            usage_metadata={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                "input_token_details": {"cache_read": response.usage.cached_tokens},
                "output_token_details": {"reasoning": response.usage.reasoning_tokens},
            },
            response_metadata={
                "provider_request_id": response.provider_request_id,
                "finish_category": response.finish_category,
            },
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def _role(message: BaseMessage) -> str:
    mapping = {
        "human": "user",
        "ai": "assistant",
        "system": "system",
        "tool": "tool",
    }
    return mapping.get(message.type, "user")


def _content(content: str | list[Any]) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(item) for item in content)


def _normalize_tool(tool: Any) -> NeutralTool:
    if isinstance(tool, dict):
        function = tool.get("function", tool)
        return NeutralTool(
            name=function.get("name", "unknown"),
            description=function.get("description", ""),
            input_schema=function.get("parameters", {"type": "object", "properties": {}}),
        )
    name = getattr(tool, "name", getattr(tool, "__name__", "unknown"))
    description = getattr(tool, "description", getattr(tool, "__doc__", "")) or ""
    schema = getattr(tool, "args_schema", None)
    input_schema = (
        schema.model_json_schema()
        if schema and hasattr(schema, "model_json_schema")
        else {"type": "object", "properties": {}}
    )
    return NeutralTool(name=name, description=description, input_schema=input_schema)
