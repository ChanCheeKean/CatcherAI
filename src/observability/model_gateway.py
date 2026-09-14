from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from domain.events import Actor, ActorKind, EventDraft, EventUsage
from domain.model import Capability, ModelRequest, ModelStreamEvent
from observability.emitter import EventEmitter
from ports import ModelGateway


class InstrumentedModelGateway:
    """One observable boundary for concurrency, retries, and normalized model events."""

    def __init__(
        self,
        inner: ModelGateway,
        emitter: EventEmitter,
        *,
        provider: str,
        model: str,
        max_attempts: int = 1,
        initial_backoff_ms: int = 500,
        max_backoff_ms: int = 8000,
        concurrency: int = 4,
    ) -> None:
        self.inner = inner
        self.emitter = emitter
        self.provider = provider
        self.model = model
        self.max_attempts = max_attempts
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self._semaphore = asyncio.Semaphore(concurrency)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self.inner.capabilities

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        request_blob = self.emitter.put_blob(request.model_dump(mode="json"))
        parent_span = self.emitter.current_span
        terminal: ModelStreamEvent | None = None
        response = None
        started = time.perf_counter()

        async with self._semaphore:
            with self.emitter.span(request.call_id):
                async for event in self._stream_attempts(
                    request, request_blob, parent_span, started
                ):
                    if event.type == "completed":
                        terminal = event
                        response = event.response
                    yield event

        if terminal is None or response is None:
            raise RuntimeError("model stream ended without a completed response")
        used_tokens = response.usage.input_tokens + response.usage.output_tokens
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="budget_manager"),
                type="budget_update",
                summary="Updated model-token budget",
                payload={
                    "dimension": "model_tokens",
                    "used": used_tokens,
                    "limit": None,
                    "delta": used_tokens,
                    "remaining": None,
                },
            )
        )

    async def _stream_attempts(
        self,
        request: ModelRequest,
        request_blob: str,
        parent_span: str,
        started: float,
    ) -> AsyncIterator[ModelStreamEvent]:
        terminal: ModelStreamEvent | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._emit_started(request, request_blob, parent_span, attempt)
            ordinal = 0
            emitted_content = False
            try:
                async for event in self.inner.stream(request):
                    ordinal += 1
                    if event.type != "completed":
                        emitted_content = True
                        self.emitter.emit(
                            EventDraft(
                                actor=Actor(kind=ActorKind.AGENT, name=request.actor),
                                type="llm_stream_event",
                                summary=f"Model stream {event.type}",
                                payload={
                                    "call_id": request.call_id,
                                    "attempt": attempt,
                                    "stream_type": event.type,
                                    "ordinal": ordinal,
                                    "data_blob": self.emitter.put_blob(
                                        event.model_dump(mode="json")
                                    ),
                                },
                                span_id=request.call_id,
                                parent_span_id=parent_span,
                            )
                        )
                    else:
                        terminal = event
                    yield event
            except asyncio.CancelledError:
                self._emit_failed(request, parent_span, attempt, RuntimeError("cancelled"), False)
                raise
            except Exception as exc:
                retryable = (
                    _is_retryable(exc) and not emitted_content and attempt < self.max_attempts
                )
                self._emit_failed(request, parent_span, attempt, exc, retryable)
                if not retryable:
                    raise
                backoff_ms = min(
                    self.initial_backoff_ms * (2 ** (attempt - 1)), self.max_backoff_ms
                )
                self.emitter.emit(
                    EventDraft(
                        actor=Actor(kind=ActorKind.AGENT, name=request.actor),
                        type="retry",
                        summary=f"Retrying model call after attempt {attempt}",
                        payload={
                            "call_id": request.call_id,
                            "failed_attempt": attempt,
                            "next_attempt": attempt + 1,
                            "backoff_ms": backoff_ms,
                            "category": type(exc).__name__,
                        },
                        span_id=request.call_id,
                        parent_span_id=parent_span,
                    )
                )
                await asyncio.sleep(backoff_ms / 1000)
                continue
            break

        if terminal is None or terminal.response is None:
            raise RuntimeError("model stream ended without a completed response")
        response = terminal.response
        latency_ms = int((time.perf_counter() - started) * 1000)
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name=request.actor),
                type="llm_call",
                summary="Model call completed",
                payload={
                    "call_id": request.call_id,
                    "attempt": attempt,
                    "response_blob": self.emitter.put_blob(response.model_dump(mode="json")),
                    "provider_request_id": response.provider_request_id,
                    "stop_reason": response.finish_category,
                },
                usage=EventUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    reasoning_tokens=response.usage.reasoning_tokens,
                    cached_tokens=response.usage.cached_tokens,
                    latency_ms=latency_ms,
                ),
                span_id=request.call_id,
                parent_span_id=parent_span,
            )
        )

    def _emit_started(
        self, request: ModelRequest, request_blob: str, parent_span: str, attempt: int
    ) -> None:
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name=request.actor),
                type="llm_call_started",
                summary=f"Started {request.rationale}",
                payload={
                    "call_id": request.call_id,
                    "provider": self.provider,
                    "requested_model": self.model,
                    "resolved_model": self.model,
                    "attempt": attempt,
                    "request_blob": request_blob,
                    "options": {
                        "reasoning_effort": request.reasoning_effort,
                        "max_output_tokens": request.max_output_tokens,
                        "timeout_seconds": request.timeout_seconds,
                    },
                    "tool_schema_hash": self.emitter.put_blob(
                        [tool.model_dump(mode="json") for tool in request.tools]
                    ),
                    "output_schema_hash": self.emitter.put_blob(request.output_schema or {}),
                    "rationale": request.rationale,
                },
                span_id=request.call_id,
                parent_span_id=parent_span,
            )
        )

    def _emit_failed(
        self,
        request: ModelRequest,
        parent_span: str,
        attempt: int,
        exc: Exception,
        retryable: bool,
    ) -> None:
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name=request.actor),
                type="llm_call_failed",
                summary="Model call attempt failed",
                payload={
                    "call_id": request.call_id,
                    "attempt": attempt,
                    "category": type(exc).__name__,
                    "retryable": retryable,
                    "sanitized_error": str(exc),
                },
                span_id=request.call_id,
                parent_span_id=parent_span,
            )
        )


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 429} or isinstance(status, int) and status >= 500:
        return True
    name = type(exc).__name__.casefold()
    if any(word in name for word in ("authentication", "permission", "validation")):
        return False
    return any(word in name for word in ("timeout", "ratelimit", "connection"))
