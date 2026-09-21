"""Model construction and the single structured-output invocation boundary."""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

from langchain.agents.structured_output import ProviderStrategy
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError

from config import ModelsConfig, load_models_config
from domain.events import Actor, ActorKind, EventDraft, EventUsage, current_event_context
from observability.emitter import EventEmitter

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ModelCallCallbackHandler(BaseCallbackHandler):
    """Emit one compact trajectory event for each completed chat-model call."""

    def __init__(
        self,
        emitter: EventEmitter,
        *,
        actor: str = "model",
        schema_name: str | None = None,
    ) -> None:
        self.emitter = emitter
        self.actor = actor
        self.schema_name = schema_name
        self._started: dict[str, tuple[float, str | None, str | None]] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        run_key = str(run_id)
        metadata = metadata or {}
        self._started[run_key] = (
            time.perf_counter(),
            _model_name(serialized),
            metadata.get("schema_name") or self.schema_name,
        )

    def on_llm_end(self, response: Any, *, run_id: Any, **_: Any) -> None:
        run_key = str(run_id)
        started_at, model, schema_name = self._started.pop(
            run_key, (time.perf_counter(), None, self.schema_name)
        )
        usage = _usage_from_response(response)
        usage.latency_ms = round((time.perf_counter() - started_at) * 1000)
        context = current_event_context()
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name=context.actor or self.actor),
                type="model_call",
                summary=f"structured model call: {schema_name or 'unknown schema'}",
                payload={
                    "model": model or "unknown",
                    "schema": schema_name or "unknown",
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "reasoning_tokens": usage.reasoning_tokens,
                    "cached_tokens": usage.cached_tokens,
                    "latency_ms": usage.latency_ms,
                },
                usage=usage,
            )
        )

    def on_llm_error(self, error: BaseException, *, run_id: Any, **_: Any) -> None:
        self._started.pop(str(run_id), None)


def chat_model(
    config: ModelsConfig | Path | None = None,
    *,
    emitter: EventEmitter | None = None,
    actor: str = "model",
) -> Any:
    """Build the configured LangChain chat model without making a network call."""

    if config is None:
        config = load_models_config(Path("config/models.yaml"))
    elif isinstance(config, Path):
        config = load_models_config(config)

    callbacks = [ModelCallCallbackHandler(emitter, actor=actor)] if emitter is not None else None
    kwargs: dict[str, Any] = {
        "timeout": config.default.timeout_seconds,
        "max_completion_tokens": config.default.max_output_tokens,
        "reasoning_effort": config.default.reasoning_effort,
        "use_responses_api": config.api == "responses",
    }
    if config.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        # LangChain validates the OpenAI client at construction time. A sentinel keeps
        # construction side-effect free for local schema/plumbing tests; an actual call
        # still fails clearly until the user supplies the real key.
        kwargs["api_key"] = "not-configured"
    if callbacks is not None:
        kwargs["callbacks"] = callbacks
    return init_chat_model(
        config.default.model,
        model_provider=config.provider,
        **kwargs,
    )


def provider_strategy(schema: type[SchemaT]) -> ProviderStrategy[SchemaT]:
    """Return the strict provider-native strategy used when creating a Deep Agent."""

    return ProviderStrategy(schema, strict=True)


def invoke_structured(
    agent_or_model: Any,
    schema: type[SchemaT],
    messages: Sequence[Any],
) -> SchemaT:
    """Invoke a model or preconfigured Deep Agent and return a validated Pydantic object.

    Plain chat models are wrapped with provider-native strict JSON schema output. Deep Agents
    are created by their caller with ``ProviderStrategy`` and expose their result under
    ``structured_response``. A validation failure is returned to the model once as a retry
    message; a second failure is raised to the runtime.
    """

    current_messages = list(messages)
    for attempt in range(2):
        try:
            raw = _invoke_once(agent_or_model, schema, current_messages)
            return _coerce_output(raw, schema)
        except ValidationError as error:
            if attempt == 1:
                raise
            current_messages = [
                *current_messages,
                HumanMessage(
                    content=(
                        "Your previous structured response failed validation. "
                        "Return only a corrected response matching the schema. "
                        f"Validation error: {error}"
                    )
                ),
            ]
    raise AssertionError("unreachable")


def _invoke_once(agent_or_model: Any, schema: type[SchemaT], messages: list[Any]) -> Any:
    if hasattr(agent_or_model, "with_structured_output"):
        structured = agent_or_model.with_structured_output(schema, strict=True)
        return _runnable_invoke(structured, messages, schema)
    agent_input: Any = {"messages": messages} if _is_compiled_graph(agent_or_model) else messages
    return _runnable_invoke(agent_or_model, agent_input, schema)


def _runnable_invoke(runnable: Any, input_: Any, schema: type[SchemaT]) -> Any:
    if isinstance(runnable, Runnable):
        return runnable.invoke(
            input_,
            config={"metadata": {"schema_name": schema.__name__}},
        )
    return runnable.invoke(input_)


def _is_compiled_graph(value: Any) -> bool:
    return value.__class__.__module__.startswith("langgraph.graph.state")


def _coerce_output(raw: Any, schema: type[SchemaT]) -> SchemaT:
    if isinstance(raw, dict) and "structured_response" in raw:
        raw = raw["structured_response"]
    elif isinstance(raw, dict) and "parsed" in raw and raw.get("parsing_error") is None:
        raw = raw["parsed"]
    if isinstance(raw, schema):
        return raw
    if isinstance(raw, BaseModel):
        raw = raw.model_dump(mode="python")
    return schema.model_validate(raw)


def _model_name(serialized: dict[str, Any]) -> str | None:
    kwargs = serialized.get("kwargs", {})
    identifier = serialized.get("id")
    if isinstance(identifier, list):
        identifier = identifier[-1] if identifier else None
    return kwargs.get("model") or serialized.get("name") or identifier


def _usage_from_response(response: Any) -> EventUsage:
    usage: dict[str, Any] = {}
    llm_output = getattr(response, "llm_output", None) or {}
    usage.update(llm_output.get("token_usage", {}))
    generations = getattr(response, "generations", []) or []
    if generations and generations[0]:
        message = getattr(generations[0][0], "message", None)
        usage.update(getattr(message, "usage_metadata", None) or {})
        usage.update((getattr(message, "response_metadata", None) or {}).get("token_usage", {}))
    return EventUsage(
        input_tokens=int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0),
        output_tokens=int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0),
        reasoning_tokens=int(usage.get("reasoning_tokens", 0) or 0),
        cached_tokens=int(usage.get("cached_tokens", 0) or 0),
    )
