"""LangGraph runtime for one graph-backed dispute investigation."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

import notebook
from config import AgentsConfig
from domain.events import Actor, ActorKind, EventDraft, event_context
from graph_store import GraphStore
from models import invoke_structured, provider_strategy
from observability.emitter import EventEmitter
from runtime_entry import RuntimePaths, run_case
from runtime_support import (
    AgentState,
    apply_plan_edits,
    findings_refs,
    open_plan,
    plan_refs,
    report_refs,
    triage_refs,
    unique,
)
from schemas import (
    CaseReport,
    Decide,
    Findings,
    InvestigationSummary,
    PlanStatus,
    SupervisorTurn,
    Task,
    Triage,
)
from tools import READ_ONLY_TOOLS, Run, make_tools

AgentBuilder = Callable[..., Any]
__all__ = ["RuntimePaths", "run_case"]


class _Runtime:
    def __init__(
        self,
        *,
        store: GraphStore,
        emitter: EventEmitter,
        run_id: str,
        knowledge_db: Path,
        notebook_db: Path,
        skills_dir: Path,
        config: AgentsConfig,
        model: Any,
        agent_builder: AgentBuilder,
    ) -> None:
        self.store = store
        self.emitter = emitter
        self.run_id = run_id
        self.knowledge_db = knowledge_db
        self.notebook_db = notebook_db
        self.skills_dir = skills_dir
        self.config = config
        self.model = model
        self.agent_builder = agent_builder
        self._visits: dict[str, int] = {}
        self._visit_lock = threading.Lock()

    def build(self, checkpointer: SqliteSaver):
        builder = StateGraph(AgentState)
        builder.add_node("triage", self.triage)
        builder.add_node("supervisor", self.supervisor)
        builder.add_node("worker", self.worker)
        builder.add_node("adjudicator", self.adjudicator)
        builder.add_node("consolidate_memory", self.consolidate_memory)
        builder.add_edge(START, "triage")
        builder.add_edge("triage", "supervisor")
        builder.add_conditional_edges("supervisor", self.route_supervisor)
        builder.add_edge("worker", "supervisor")
        builder.add_edge("adjudicator", "consolidate_memory")
        builder.add_edge("consolidate_memory", END)
        return builder.compile(checkpointer=checkpointer)

    def case_context(self, case_id: str) -> dict[str, Any]:
        return {
            "dispute": self.store.node(case_id),
            "neighborhood": self.store.neighbors(case_id, limit=50),
            "schema": self.store.schema(),
        }

    def triage(self, state: AgentState) -> dict[str, Any]:
        actor, visit, turn = "triage", self._next_visit("triage"), 0
        with event_context(actor=actor, visit=visit, turn=turn):
            self._node_event("node_entered", actor, visit, turn, {"case": state["case"]})
            prompt = {
                "instructions": self.config.prompts.triage,
                "case": state["case"],
            }
            output = invoke_structured(
                self.model,
                Triage,
                [HumanMessage(content=json.dumps(prompt, default=str))],
            )
            summary = InvestigationSummary(
                hypotheses=output.hypotheses,
                key_facts=[],
                open_questions=[item.question for item in output.plan if item.status == "open"],
                contradictions=[],
            )
            refs = triage_refs(state["case"])
            self._emit("triage", actor, visit, turn, output.model_dump(mode="json"), refs)
            self._emit(
                "plan_updated",
                actor,
                visit,
                turn,
                {"plan": [p.model_dump(mode="json") for p in output.plan]},
                refs,
            )
            self._node_event(
                "node_exited",
                actor,
                visit,
                turn,
                output.model_dump(mode="json"),
                refs=refs,
            )
            self._edge(actor, "supervisor", visit, turn, "triage complete")
        return {
            "triage": output,
            "plan": output.plan,
            "summary": summary,
            "processed_findings": 0,
            "progress_refs": [],
            "no_progress_count": 0,
            "route": "supervisor",
            "supervisor_feedback": "",
        }

    def supervisor(self, state: AgentState) -> dict[str, Any]:
        actor = "supervisor"
        visit = self._next_visit(actor)
        turn = state.get("turn", 0) + 1
        with event_context(actor=actor, visit=visit, turn=turn):
            self._node_event("node_entered", actor, visit, turn, self._supervisor_input(state))
            progress = self._progress(state)
            if state.get("turn", 0) >= self.config.runtime.max_turns:
                return self._force_decision(state, visit, turn, "max_turns", progress)
            if progress["no_progress_count"] >= self.config.runtime.no_progress_turns:
                return self._force_decision(state, visit, turn, "no_progress", progress)

            output = invoke_structured(
                self.model,
                SupervisorTurn,
                [
                    HumanMessage(
                        content=json.dumps(
                            {
                                "instructions": self.config.prompts.supervisor,
                                **self._supervisor_input(state),
                            },
                            default=str,
                        )
                    )
                ],
            )
            plan = apply_plan_edits(state["plan"], output.plan_edits)
            payload = output.model_dump(mode="json")
            self._emit("supervisor_turn", actor, visit, turn, payload, findings_refs(state))
            if output.plan_edits:
                self._emit(
                    "plan_updated",
                    actor,
                    visit,
                    turn,
                    {"plan": [p.model_dump(mode="json") for p in plan]},
                    plan_refs(plan),
                )

            common = {
                "plan": plan,
                "summary": output.summary,
                "turn": turn,
                "processed_findings": progress["processed_findings"],
                "progress_refs": progress["progress_refs"],
                "no_progress_count": progress["no_progress_count"],
            }
            if isinstance(output.action, Decide):
                open_items = [p.id for p in plan if p.status == PlanStatus.OPEN]
                if open_items:
                    feedback = "Decide rejected: close or waive open plan items: " + ", ".join(
                        open_items
                    )
                    self._node_event("node_exited", actor, visit, turn, payload)
                    self._edge(actor, actor, visit, turn, feedback)
                    return {**common, "route": "supervisor", "supervisor_feedback": feedback}
                self._node_event("node_exited", actor, visit, turn, payload)
                self._edge(actor, "adjudicator", visit, turn, output.action.reason or "Decide")
                return {
                    **common,
                    "route": "adjudicator",
                    "termination_reason": "decided",
                    "supervisor_feedback": "",
                }

            tasks = output.action.tasks[: self.config.runtime.max_parallel_tasks]
            if not tasks:
                feedback = "Delegate rejected: provide at least one task or choose Decide."
                self._node_event("node_exited", actor, visit, turn, payload)
                self._edge(actor, actor, visit, turn, feedback)
                return {**common, "route": "supervisor", "supervisor_feedback": feedback}
            delegations = [
                {
                    "task": task,
                    "delegation_id": f"dlg-{uuid.uuid4().hex}",
                    "visit": self._next_visit(task.role),
                }
                for task in tasks
            ]
            for delegation in delegations:
                task = delegation["task"]
                parent_id = delegation["delegation_id"]
                self._emit(
                    "delegation_started",
                    task.role,
                    delegation["visit"],
                    turn,
                    {"task": task.model_dump(mode="json")},
                    parent_id=parent_id,
                )
                self._edge(actor, task.role, visit, turn, "decided by supervisor", parent_id)
            self._node_event("node_exited", actor, visit, turn, payload)
            return {
                **common,
                "route": "workers",
                "tasks": delegations,
                "supervisor_feedback": "",
            }

    def route_supervisor(self, state: AgentState):
        if state["route"] == "workers":
            return [
                Send(
                    "worker",
                    {
                        **state,
                        "task": item["task"],
                        "delegation_id": item["delegation_id"],
                        "worker_visit": item["visit"],
                    },
                )
                for item in state["tasks"]
            ]
        return state["route"]

    def worker(self, state: AgentState) -> dict[str, Any]:
        task, parent_id, turn = state["task"], state["delegation_id"], state["turn"]
        actor, visit = task.role, state["worker_visit"]
        with event_context(actor=actor, visit=visit, turn=turn, parent_id=parent_id):
            self._node_event(
                "node_entered",
                actor,
                visit,
                turn,
                {"task": task.model_dump(mode="json")},
                parent_id,
            )
            skills = unique([*self._role_skills(task.role), *task.skills])
            agent, tool_store = self._agent(
                task.role, task.instructions, skills, Findings, state, task=task
            )
            try:
                output = invoke_structured(
                    agent,
                    Findings,
                    [HumanMessage(content=json.dumps({"task": task.model_dump()}, default=str))],
                )
            finally:
                tool_store.close()
            refs = [*output.node_ids, *output.edge_ids]
            payload = output.model_dump(mode="json")
            self._node_event("node_exited", actor, visit, turn, payload, parent_id, refs)
            self._emit(
                "delegation_finished",
                actor,
                visit,
                turn,
                {"findings": payload},
                refs,
                parent_id,
            )
            self._edge(actor, "supervisor", visit, turn, "findings returned", parent_id)
        return {"findings": [output]}

    def adjudicator(self, state: AgentState) -> dict[str, Any]:
        actor, visit, turn = "adjudicator", self._next_visit("adjudicator"), state["turn"]
        with event_context(actor=actor, visit=visit, turn=turn):
            adjudication_input = {
                "case": state["case"]["dispute"],
                "plan": [p.model_dump(mode="json") for p in state["plan"]],
                "summary": state["summary"].model_dump(mode="json"),
                "findings": [f.model_dump(mode="json") for f in state.get("findings", [])],
                "notebook": notebook.read_entries(self.notebook_db, self.run_id),
                "termination_note": state.get("termination_reason", "decided"),
            }
            self._node_event("node_entered", actor, visit, turn, adjudication_input)
            skills = self._role_skills(actor)
            agent, tool_store = self._agent(actor, None, skills, CaseReport, state, read_only=True)
            try:
                report = invoke_structured(
                    agent,
                    CaseReport,
                    [HumanMessage(content=json.dumps(adjudication_input, default=str))],
                )
            finally:
                tool_store.close()
            payload = report.model_dump(mode="json")
            refs = report_refs(report)
            self._node_event("node_exited", actor, visit, turn, payload, refs=refs)
            self._emit(
                "decision",
                actor,
                visit,
                turn,
                {"report": payload, "reason": state.get("termination_reason", "decided")},
                refs,
            )
            self._edge(actor, "consolidate_memory", visit, turn, "decision complete")
        return {"report": report}

    def consolidate_memory(self, state: AgentState) -> dict[str, Any]:
        actor = "consolidate_memory"
        visit, turn = self._next_visit(actor), state["turn"]
        with event_context(actor=actor, visit=visit, turn=turn):
            memory_input = {
                "objective": "Consolidate durable memory from this completed investigation.",
                "case_id": state["case"]["dispute"]["id"],
                "findings": [f.model_dump(mode="json") for f in state.get("findings", [])],
                "report": state["report"].model_dump(mode="json"),
            }
            self._node_event("node_entered", actor, visit, turn, memory_input)
            skills = self._role_skills("memory_keeper")
            agent, tool_store = self._agent("memory_keeper", None, skills, Findings, state)
            try:
                output = invoke_structured(
                    agent,
                    Findings,
                    [HumanMessage(content=json.dumps(memory_input, default=str))],
                )
            finally:
                tool_store.close()
            payload = output.model_dump(mode="json")
            refs = [*output.node_ids, *output.edge_ids]
            self._node_event("node_exited", actor, visit, turn, payload, refs=refs)
            reason = state.get("termination_reason", "decided")
            self._edge(actor, "end", visit, turn, reason)
            self._emit("termination", actor, visit, turn, {"reason": reason}, refs)
        return {}

    def _agent(
        self,
        role: str,
        instructions: str | None,
        skills: list[str],
        schema: type[Findings] | type[CaseReport],
        state: AgentState,
        *,
        task: Task | None = None,
        read_only: bool = False,
    ) -> tuple[Any, GraphStore]:
        role_config = self.config.role_map.get(role)
        role_prompt = instructions or (role_config.prompt if role_config else "")
        loaded_skills: list[str] = []
        visit = state.get("worker_visit", self._visits.get(role, 1))
        for skill in skills:
            path = self.skills_dir / skill / "SKILL.md"
            if not path.is_file():
                continue
            loaded_skills.append(path.read_text(encoding="utf-8"))
            self._emit(
                "skill_loaded",
                role,
                visit,
                state["turn"],
                {"skill": skill},
                parent_id=state.get("delegation_id"),
            )
        system_prompt = "\n\n".join(
            part
            for part in (
                role_prompt,
                f"Objective: {task.objective}" if task else "",
                "Requested skills: " + ", ".join(skills) if skills else "",
                "Attached skill instructions:\n" + "\n\n".join(loaded_skills)
                if loaded_skills
                else "",
                "Evidence graph schema:\n" + json.dumps(state["case"]["schema"], default=str),
            )
            if part
        )
        tool_store = GraphStore(self.store.db_path)
        run = Run(
            tool_store,
            self.emitter,
            self.run_id,
            self.knowledge_db,
            self.notebook_db,
            actor=role,
            visit=visit,
            turn=state["turn"],
            parent_id=state.get("delegation_id"),
        )
        tools = make_tools(run)
        if read_only:
            tools = [tool for tool in tools if tool.name in READ_ONLY_TOOLS]
        try:
            agent = self.agent_builder(
                model=self.model,
                tools=tools,
                system_prompt=system_prompt,
                skills=["/skills"],
                backend=FilesystemBackend(self.skills_dir.parent, virtual_mode=True),
                response_format=provider_strategy(schema),
                name=role,
            )
        except Exception:
            tool_store.close()
            raise
        return agent, tool_store

    def _progress(self, state: AgentState) -> dict[str, Any]:
        findings = state.get("findings", [])
        processed = state.get("processed_findings", 0)
        seen = set(state.get("progress_refs", []))
        new_tokens: set[str] = set()
        for finding in findings[processed:]:
            new_tokens.update(finding.node_ids)
            new_tokens.update(finding.edge_ids)
            new_tokens.update(f.statement for f in finding.facts)
        made_progress = bool(new_tokens - seen)
        no_progress = state.get("no_progress_count", 0)
        if processed < len(findings) or state.get("turn", 0) > 0:
            no_progress = 0 if made_progress else no_progress + 1
        return {
            "processed_findings": len(findings),
            "progress_refs": sorted(seen | new_tokens),
            "no_progress_count": no_progress,
        }

    def _force_decision(
        self,
        state: AgentState,
        visit: int,
        turn: int,
        reason: str,
        progress: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {"forced": True, "reason": reason, "open_plan_items": open_plan(state["plan"])}
        self._emit("supervisor_turn", "supervisor", visit, turn, payload)
        self._node_event("node_exited", "supervisor", visit, turn, payload)
        self._edge("supervisor", "adjudicator", visit, turn, f"forced: {reason}")
        return {
            **progress,
            "turn": turn,
            "route": "adjudicator",
            "termination_reason": reason,
            "supervisor_feedback": f"Forced adjudication because {reason} was reached.",
        }

    def _supervisor_input(self, state: AgentState) -> dict[str, Any]:
        processed = state.get("processed_findings", 0)
        return {
            "plan": [p.model_dump(mode="json") for p in state["plan"]],
            "summary": state["summary"].model_dump(mode="json"),
            "latest_findings": [
                f.model_dump(mode="json") for f in state.get("findings", [])[processed:]
            ],
            "feedback": state.get("supervisor_feedback", ""),
            "notebook": notebook.read_entries(self.notebook_db, self.run_id),
        }

    def _role_skills(self, role: str) -> list[str]:
        config = self.config.role_map.get(role)
        return list(config.default_skills) if config else []

    def _next_visit(self, actor: str) -> int:
        with self._visit_lock:
            self._visits[actor] = self._visits.get(actor, 0) + 1
            return self._visits[actor]

    def _node_event(
        self,
        type_: str,
        actor: str,
        visit: int,
        turn: int,
        data: dict[str, Any],
        parent_id: str | None = None,
        refs: list[str] | None = None,
    ) -> None:
        field = "input" if type_ == "node_entered" else "output"
        self._emit(type_, actor, visit, turn, {field: data}, refs or [], parent_id)

    def _edge(
        self,
        source: str,
        target: str,
        visit: int,
        turn: int,
        reason: str,
        parent_id: str | None = None,
    ) -> None:
        self._emit(
            "edge_taken",
            source,
            visit,
            turn,
            {"source": source, "target": target, "reason": reason},
            parent_id=parent_id,
        )

    def _emit(
        self,
        type_: str,
        actor: str,
        visit: int,
        turn: int,
        payload: dict[str, Any],
        refs: list[str] | None = None,
        parent_id: str | None = None,
    ) -> None:
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.GRAPH_NODE, name=actor),
                visit=visit,
                turn=turn,
                parent_id=parent_id,
                type=type_,
                summary=f"{actor} {type_.replace('_', ' ')}",
                payload=payload,
                refs=refs or [],
            )
        )
