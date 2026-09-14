from __future__ import annotations

import shutil
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from domain.events import RuntimeSnapshot
from memory.graph import GraphMemory
from observability.emitter import EventEmitter
from runtime.langgraph_runtime import LangGraphRuntime


def _events(runtime: LangGraphRuntime):  # type: ignore[no-untyped-def]
    assert runtime.last_run_id
    return runtime.emitter(runtime.last_run_id).events()


def _assert_nested_delegations(events, minimum: int) -> None:  # type: ignore[no-untyped-def]
    started = [event for event in events if event.type == "subagent_started"]
    finished = [event for event in events if event.type == "subagent_finished"]
    task_calls = [
        event for event in events if event.type == "tool_call" and event.payload["tool"] == "task"
    ]
    task_results = [
        event for event in events if event.type == "tool_result" and event.actor.name == "task"
    ]
    assert len(started) == len(finished) == len(task_calls) == len(task_results)
    assert len(started) >= minimum
    span_ids = {event.span_id for event in events}
    assert all(event.parent_span_id in span_ids for event in started)


def test_graph_memory_uses_explicit_networkx_fallback(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fallback.sqlite"
    shutil.copy2(project_root / "data/generated/catcher.sqlite", db_path)
    emitter = EventEmitter(
        db_path,
        run_id="run-graph-fallback",
        case_id="DSP-2026-90014",
        runtime=RuntimeSnapshot(
            config_hash="unit",
            agent_runtime="unit",
            model_gateway="fake",
            provider="fake",
            model="fake",
        ),
        virtual_now=datetime(2026, 10, 21, 13, tzinfo=UTC),
    )
    monkeypatch.setitem(__import__("sys").modules, "ladybug", None)
    memory = GraphMemory(project_root / "data/generated/graph", db_path, emitter)

    assert memory.backend_name == "networkx"
    assert memory.shared_identity_component("CUS-90017") == {
        "customer_ids": ["CUS-90017"],
        "shared_identifiers": {},
        "linked": False,
    }
    events = emitter.events()
    assert any(
        event.type == "fallback"
        and event.payload["from"] == "ladybug"
        and event.payload["to"] == "networkx"
        for event in events
    )
    assert any(
        event.type == "graph_query" and event.payload["backend"] == "networkx" for event in events
    )


@pytest.mark.asyncio
async def test_c08_reg_e_graph_cpp_and_specialists(runtime: LangGraphRuntime) -> None:
    decision = await runtime.run("DSP-2026-90009")
    assert decision.regime == "REG_E"
    assert decision.cardholder_resolution.credit_amount == Decimal("1299.00")
    assert decision.cardholder_resolution.liability_amount == Decimal("0")
    assert decision.deadlines["provisional_credit_deadline"] == "2026-11-10"
    assert [action.action for action in decision.network_actions] == [
        "file_dispute",
        "write_off_no_chargeback",
    ]

    events = _events(runtime)
    _assert_nested_delegations(events, 5)
    types = Counter(event.type for event in events)
    assert types["graph_query"] >= 1
    assert types["computation"] >= 1
    assert types["review_panel_started"] == 1
    assert types["panel_position"] == 2
    assert types["adjudication"] == 1
    assert types["memory_supersede"] == 1
    assert types["graph_write"] == 1
    graph = next(
        event
        for event in events
        if event.type == "graph_query"
        and event.payload["template_id"] == "common_compromise_points"
    )
    assert "Customer:CUS-90008" in graph.payload["parameters"].values()


@pytest.mark.asyncio
async def test_c11_ato_overturns_memory_and_reopens_case(runtime: LangGraphRuntime) -> None:
    decision = await runtime.run("DSP-2026-90012")
    assert decision.claim_family == "fraud_cnp_account_takeover"
    assert decision.ce3_assessment["met"] is False
    assert decision.network_actions[0].condition == "10.4"
    assert any(
        action["action"] == "reopen_case" and action["case_id"] == "DSP-2026-04471"
        for action in decision.automated_actions
    )
    assert all(action.txn_id != "TXN-9001203" for action in decision.network_actions)

    events = _events(runtime)
    _assert_nested_delegations(events, 6)
    assert any(event.type == "contradiction_detected" for event in events)
    assert any(
        event.type == "memory_retract" and event.payload["target_id"] == "MEM-0142"
        for event in events
    )
    assert any(
        event.type == "automated_action" and event.payload["action"] == "credit_reopened_case"
        for event in events
    )
    with sqlite3.connect(runtime.scenario.sqlite_path) as connection:
        reopened = connection.execute(
            """SELECT status, stage, cardholder_outcome FROM disputes
               WHERE case_id='DSP-2026-04471'"""
        ).fetchone()
    assert reopened == ("open", "reopened_automated", "credited")


@pytest.mark.asyncio
async def test_c12_dynamic_case_fanout_and_bounded_ring_controls(
    runtime: LangGraphRuntime,
) -> None:
    decision = await runtime.run("DSP-2026-90013")
    assert decision.is_dispute is False
    assert decision.ring_members == [
        "CUS-90013",
        "CUS-90014",
        "CUS-90015",
        "CUS-90016",
    ]
    assert decision.ring_linkage is True
    rereview = next(
        action
        for action in decision.automated_actions
        if action["action"] == "enqueue_automated_rereview"
    )
    assert len(rereview["cases"]) == 6
    assert "CUS-90017" not in str(decision.model_dump(mode="json"))

    events = _events(runtime)
    _assert_nested_delegations(events, 13)
    linked_starts = [
        event
        for event in events
        if event.type == "subagent_started" and event.actor.name == "linked_case_analyst"
    ]
    assert len(linked_starts) == 9
    assert any(event.type == "memory_consolidate" for event in events)
    assert any(event.type == "graph_write" for event in events)
    assert not any(
        event.type == "automated_action"
        and event.payload["action"] in {"close_account", "restrict_account"}
        for event in events
    )
    escalated = [
        event
        for event in events
        if event.type == "route_decision" and event.payload["depth"] == "L4"
    ]
    assert len(escalated) == 1


@pytest.mark.asyncio
async def test_c12b_negative_graph_result_blocks_ring_write(
    runtime: LangGraphRuntime,
) -> None:
    decision = await runtime.run("DSP-2026-90014")
    assert decision.ring_linkage is False
    assert decision.network_actions[0].condition == "13.1"
    assert decision.cardholder_resolution.credit_amount == Decimal("219.00")

    events = _events(runtime)
    _assert_nested_delegations(events, 1)
    assert not any(event.type == "review_panel_started" for event in events)
    assert not any(event.type == "graph_write" for event in events)
    assert any(
        event.type == "memory_write_skipped" and "guilt by association" in event.payload["reason"]
        for event in events
    )
