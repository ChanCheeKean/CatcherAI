"""Small state and data helpers for the agent runtime."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from schemas import (
    CaseReport,
    Findings,
    InvestigationSummary,
    PlanEdit,
    PlanItem,
    PlanStatus,
    Task,
    Triage,
)


class AgentState(TypedDict, total=False):
    case: dict[str, Any]
    triage: Triage
    plan: list[PlanItem]
    summary: InvestigationSummary
    findings: Annotated[list[Findings], operator.add]
    processed_findings: int
    progress_refs: list[str]
    no_progress_count: int
    turn: int
    route: str
    tasks: list[dict[str, Any]]
    task: Task
    delegation_id: str
    worker_visit: int
    termination_reason: str
    supervisor_feedback: str
    report: CaseReport


def apply_plan_edits(plan: list[PlanItem], edits: list[PlanEdit]) -> list[PlanItem]:
    items = {item.id: item.model_copy(deep=True) for item in plan}
    order = [item.id for item in plan]
    for edit in edits:
        if edit.operation == "add":
            item = edit.item or PlanItem(
                id=edit.plan_item_id or f"P{len(order) + 1}",
                question=edit.question or "Investigate the added question.",
                status=PlanStatus.OPEN,
                evidence_refs=edit.evidence_refs,
                waiver_reason=None,
            )
            items[item.id] = item
            if item.id not in order:
                order.append(item.id)
        elif edit.operation == "drop":
            if edit.plan_item_id in items:
                del items[edit.plan_item_id]
                order.remove(edit.plan_item_id)
        elif edit.plan_item_id in items:
            current = items[edit.plan_item_id]
            status = (
                PlanStatus.DONE if edit.operation in {"mark_done", "done"} else PlanStatus.WAIVED
            )
            items[edit.plan_item_id] = current.model_copy(
                update={
                    "status": status,
                    "evidence_refs": edit.evidence_refs or current.evidence_refs,
                    "waiver_reason": edit.waiver_reason if status == PlanStatus.WAIVED else None,
                }
            )
    return [items[item_id] for item_id in order if item_id in items]


def open_plan(plan: list[PlanItem]) -> list[str]:
    return [item.id for item in plan if item.status == PlanStatus.OPEN]


def plan_refs(plan: list[PlanItem]) -> list[str]:
    return unique(ref for item in plan for ref in item.evidence_refs)


def findings_refs(state: AgentState) -> list[str]:
    return unique(
        ref
        for finding in state.get("findings", [])
        for ref in [*finding.node_ids, *finding.edge_ids]
    )


def triage_refs(case: dict[str, Any]) -> list[str]:
    neighborhood = case["neighborhood"]
    return unique([case["dispute"]["id"], *neighborhood["node_ids"], *neighborhood["edge_ids"]])


def report_refs(report: CaseReport) -> list[str]:
    evidence = [link for charge in report.charges for link in charge.evidence]
    evidence += [link for item in report.system_improvements for link in item.evidence]
    evidence.extend(link for hypothesis in report.hypotheses for link in hypothesis.evidence)
    return unique(ref for link in evidence for ref in [*link.node_ids, *link.edge_ids])


def unique(values) -> list[str]:
    return list(dict.fromkeys(values))
