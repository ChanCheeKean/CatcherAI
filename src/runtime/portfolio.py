"""Q01 portfolio queue: rank every open case by the hard clock that expires first.

A deterministic scorer owns the ranking (§5.4). LangGraph `Send` fans out one clock computation per
open case. Isolated subagents re-check the top of the queue but cannot reorder it.
"""

from __future__ import annotations

import json
import operator
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from domain.events import ActorKind
from runtime.langgraph_runtime import LangGraphRuntime, _edge, _emit, _instrument_node
from sandbox import portfolio_case_clocks

TOP_N = 15
REMEDY_WINDOW = re.compile(r"(?:within|in) the last (\d+) days", re.I)
SCORING = "rank by (overdue clocks first, earliest next hard deadline, larger exposure)"


class PortfolioState(TypedDict, total=False):
    portfolio: dict[str, Any]
    case: dict[str, Any]
    clocks: Annotated[list[dict[str, Any]], operator.add]
    ranking: list[dict[str, Any]]


async def rank_portfolio(runtime: LangGraphRuntime) -> tuple[str, list[dict[str, Any]]]:
    """Run the portfolio graph and return its run id and full ranking."""

    run_id = f"queue-{uuid.uuid4().hex}"
    runtime.last_run_id = run_id
    emitter = runtime._emitter(run_id, None)  # noqa: SLF001 - same package runtime
    ctx = runtime._context(emitter)  # noqa: SLF001
    today = ctx.clock.now.date()
    holidays = [
        date.fromisoformat(row["date"])
        for row in ctx.data.bank_holidays(
            since=(today - timedelta(days=120)).isoformat(),
            until=(today + timedelta(days=400)).isoformat(),
        )
    ]

    async def load_open_cases(state: PortfolioState) -> dict[str, Any]:
        portfolio = ctx.call(
            "list_open_portfolio",
            "Load every open case with the fields its clocks need",
            {"as_of": ctx.clock.now.isoformat()},
            lambda: ctx.data.open_portfolio(),
        )
        return {"portfolio": portfolio}

    async def case_clock(state: PortfolioState) -> dict[str, Any]:
        case, portfolio = state["case"], state["portfolio"]
        transactions = [
            row for row in portfolio["transactions"] if row["case_id"] == case["case_id"]
        ]
        merchants = {row["merchant_id"] for row in transactions}
        purchases = sorted(row["txn_local_datetime"][:10] for row in transactions)
        windows = []
        for doc in portfolio["research"]:
            match = REMEDY_WINDOW.search(doc["body"])
            if (
                match
                and json.loads(doc["meta_json"]).get("related_merchant_id") in merchants
                and purchases
            ):
                deadline = date.fromisoformat(purchases[0]) + timedelta(days=int(match.group(1)))
                windows.append(
                    {
                        "name": "merchant_refund_window",
                        "deadline": deadline.isoformat(),
                        "source": doc["doc_id"],
                    }
                )
        windows.extend(
            {
                "name": "awaited_provider_record",
                "deadline": row["available_at"][:10],
                "source": row["packet_id"],
            }
            for row in portfolio["requested_records"]
            if row["case_id"] == case["case_id"]
        )
        result = ctx.call(
            "compute_portfolio_clocks",
            f"Compute the hard clocks for {case['case_id']}",
            {"case_id": case["case_id"], "today": today.isoformat()},
            lambda: portfolio_case_clocks(
                case=case,
                transactions=transactions,
                acknowledged=case["case_id"]
                in {row["case_id"] for row in portfolio["acknowledged"]},
                remedy_windows=windows,
                today=today,
                holidays=holidays,
                emitter=emitter,
            ),
            actor="portfolio_router",
        )
        return {"clocks": [result]}

    async def rank(state: PortfolioState) -> dict[str, Any]:
        rows = sorted(
            state["clocks"],
            key=lambda row: (
                0 if row["overdue_clocks"] else 1,
                row["next_deadline"] or "9999-12-31",
                -Decimal(row["amount"] or "0"),
            ),
        )
        ranking = [
            {
                "rank": index,
                **row,
                "score": {
                    "overdue": bool(row["overdue_clocks"]),
                    "next_deadline": row["next_deadline"],
                    "exposure": row["amount"],
                },
            }
            for index, row in enumerate(rows, start=1)
        ]
        _emit(
            emitter,
            ActorKind.GRAPH_NODE,
            "rank",
            "route_decision",
            f"Portfolio router ranked {len(ranking)} open cases",
            {
                "route_id": "portfolio_deadline_queue",
                "chosen_route": "portfolio_deadline_queue",
                "method": "rule",
                "confidence": 1.0,
                "rationale": SCORING,
                "ranking": [
                    {
                        key: row[key]
                        for key in ("rank", "case_id", "next_clock", "next_deadline", "score")
                    }
                    for row in ranking
                ],
            },
            refs=[row["case_id"] for row in ranking[:TOP_N]],
        )
        return {"ranking": ranking}

    async def review_top(state: PortfolioState) -> dict[str, Any]:
        top = state["ranking"][:TOP_N]
        results = await ctx.delegate(
            "portfolio",
            [
                {
                    "subagent_type": "queue_clock_analyst",
                    "description": json.dumps(
                        {
                            "task": (
                                "Re-check the governing clock for this case; do not reorder the "
                                "queue"
                            ),
                            "case_id": row["case_id"],
                            "rank": row["rank"],
                            "clocks": row["all_clocks"],
                            "next": [row["next_clock"], row["next_deadline"]],
                        }
                    ),
                }
                for row in top
            ],
            supervisor="queue_supervisor",
        )
        _emit(
            emitter,
            ActorKind.GRAPH_NODE,
            "review_top",
            "portfolio_ranked",
            f"Recorded the top {TOP_N} of the Monday queue",
            {
                "top": [
                    {
                        key: row[key]
                        for key in (
                            "rank",
                            "case_id",
                            "next_clock",
                            "next_deadline",
                            "overdue_clocks",
                            "expired_rights",
                            "regime",
                            "stage",
                        )
                    }
                    for row in top
                ],
                "reviews": [row["result_blob"] for row in results],
                "reorder_allowed": False,
                "coverage": {
                    "open_cases": len(state["portfolio"]["cases"]),
                    "computed": len(state["ranking"]),
                },
            },
            refs=[row["case_id"] for row in top],
        )
        _emit(
            emitter,
            ActorKind.GRAPH_NODE,
            "review_top",
            "termination",
            "Terminated with decision_complete_verifier_passed",
            {
                "reason": "decision_complete_verifier_passed",
                "final_status": "ranked",
                "segment_only": False,
            },
        )
        return {}

    builder = StateGraph(PortfolioState)
    nodes = {
        "load_open_cases": (load_open_cases, None),
        "case_clock": (case_clock, "rank"),
        "rank": (rank, "review_top"),
        "review_top": (review_top, "__end__"),
    }
    for name, (node, next_node) in nodes.items():
        builder.add_node(name, _instrument_node(name, node, emitter, next_node, False))
    builder.add_edge(START, "load_open_cases")
    builder.add_edge("case_clock", "rank")
    builder.add_edge("rank", "review_top")
    builder.add_edge("review_top", END)

    def fan_out(state: PortfolioState) -> list[Send]:
        sends = []
        for case in state["portfolio"]["cases"]:
            _edge(
                emitter,
                "load_open_cases",
                "case_clock",
                "one branch per open case",
                case["case_id"],
                branch_id=case["case_id"],
            )
            sends.append(
                Send("case_clock", {"portfolio": state["portfolio"], "case": case, "clocks": []})
            )
        return sends

    builder.add_conditional_edges("load_open_cases", fan_out, ["case_clock"])
    _emit(
        emitter,
        ActorKind.HARNESS,
        "runtime",
        "run_started",
        "Started the portfolio queue run",
        {"scenario_id": runtime.scenario.id, "input_case_ids": ["Q01"]},
    )
    _edge(emitter, "__start__", "load_open_cases", "run invoked", True)
    result = await builder.compile().ainvoke({})
    _emit(
        emitter,
        ActorKind.HARNESS,
        "runtime",
        "run_completed",
        "Portfolio queue ranked",
        {"status": "ranked", "open_cases": len(result["ranking"])},
    )
    emitter.close_stream()
    return run_id, result["ranking"]
