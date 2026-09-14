from __future__ import annotations

import json
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from config import AgentConfig
from domain.events import Actor, ActorKind, EventDraft, EventUsage
from observability.emitter import EventEmitter
from tools.executor import ToolExecutor


class SubagentTrajectoryMiddleware(AgentMiddleware):
    """Central instrumentation around Deep Agents' built-in `task` delegation tool."""

    def __init__(
        self,
        emitter: EventEmitter,
        agents: dict[str, AgentConfig],
        results: list[dict[str, Any]],
        model: str,
        tool_executor: ToolExecutor,
    ) -> None:
        self.emitter = emitter
        self.agents = agents
        self.results = results
        self.model = model
        self.tool_executor = tool_executor

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        call = request.tool_call
        if call.get("name") != "task":
            return await handler(request)
        call_id = str(call["id"])
        arguments = dict(call.get("args", {}))
        name = str(arguments["subagent_type"])
        config = self.agents[name]
        self.tool_executor.account_external_call("task")
        parent_span = self.emitter.current_span
        child_span = f"span-subagent-{call_id}"
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.TOOL, name="task"),
                type="tool_call",
                summary=f"Delegated to {name}: {arguments['description']}",
                payload={
                    "call_id": call_id,
                    "tool": "task",
                    "version": 1,
                    "rationale": "Isolate an independent specialist investigation",
                    "arguments": arguments,
                    "calling_actor": "specialist_supervisor",
                },
                span_id=call_id,
                parent_span_id=parent_span,
            )
        )
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.SUBAGENT, name=name),
                type="subagent_started",
                summary=f"Started specialist {name}",
                payload={
                    "parent": "specialist_supervisor",
                    "child": name,
                    "task_brief": arguments["description"],
                    "context_handoff": "source-linked task brief",
                    "tools": config.tools,
                    "skills": config.skills,
                    "model": self.model,
                },
                span_id=child_span,
                parent_span_id=call_id,
            )
        )
        started = time.perf_counter()
        try:
            with self.emitter.span(child_span):
                result = await handler(request)
        except Exception as exc:
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.SUBAGENT, name=name),
                    type="subagent_finished",
                    summary=f"Specialist {name} failed",
                    payload={
                        "status": "error",
                        "category": type(exc).__name__,
                        "sanitized_error": str(exc),
                    },
                    span_id=child_span,
                    parent_span_id=call_id,
                )
            )
            raise
        content = getattr(result, "content", str(result))
        record = {
            "name": name,
            "status": "complete",
            "result": content,
            "result_blob": self.emitter.put_blob(content),
        }
        self.results.append(record)
        duration_ms = int((time.perf_counter() - started) * 1000)
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.SUBAGENT, name=name),
                type="subagent_finished",
                summary=f"Finished specialist {name}",
                payload={**record, "duration_ms": duration_ms},
                span_id=child_span,
                parent_span_id=call_id,
                usage=EventUsage(latency_ms=duration_ms),
            )
        )
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.TOOL, name="task"),
                type="tool_result",
                summary=f"Task returned from {name}",
                payload={
                    "call_id": call_id,
                    "status": "success",
                    "result_blob": record["result_blob"],
                    "source_ids": [],
                    "duration_ms": duration_ms,
                    "retry_count": 0,
                },
                span_id=call_id,
                parent_span_id=parent_span,
            )
        )
        return result


def delegation_message(delegations: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "instruction": (
                "Call the task tool once for every delegation in one parallel tool-call turn. "
                "After all tasks finish, return a concise synthesis."
            ),
            "delegations": delegations,
        }
    )
