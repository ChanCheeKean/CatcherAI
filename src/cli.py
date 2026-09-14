from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from bootstrap import build_runtime, isolated_workspace
from domain.events import event_json_schema
from evaluation.evaluator import GroundTruthEvaluator
from evaluation.reliability import (
    RunObservation,
    aggregate_reliability,
    capability_matrix,
    observe_run,
)
from memory.curator import curate_offline
from replay import load_events, render_timeline, verify_hash_chain
from runtime.langgraph_runtime import RunSuspended
from runtime.portfolio import QUEUE_SCENARIO_ID, rank_portfolio

app = typer.Typer(no_args_is_help=True, help="Run and replay card-dispute investigations.")

AdapterOption = Annotated[str, typer.Option(help="fake or openai")]
DbOption = Annotated[Path | None, typer.Option("--db", help="Scenario SQLite store to use")]


def _root() -> Path:
    return Path.cwd().resolve()


def _db(db: Path | None) -> Path:
    return (db or _root() / "data/generated/catcher.sqlite").resolve()


def _adapter(value: str) -> str:
    if value not in {"fake", "openai"}:
        raise typer.BadParameter("adapter must be fake or openai")
    return value


@app.command("run")
def run_case(
    case_id: str,
    adapter: AdapterOption = "fake",
    db: DbOption = None,
    auto_resume: Annotated[
        bool, typer.Option(help="Let the harness deliver external events and resume automatically")
    ] = True,
) -> None:
    """Run one case; without auto-resume the run stops at its first external wait."""

    runtime = build_runtime(_root(), adapter=_adapter(adapter), sqlite_path=db)  # type: ignore[arg-type]

    async def execute() -> dict[str, object]:
        run_id = await runtime.start(case_id, auto_resume=auto_resume)
        try:
            decision = await runtime.result(run_id)
        except RunSuspended as suspended:
            return {"run_id": run_id, "status": "suspended", "wait": suspended.wait}
        return {"run_id": run_id, "status": "decided", "decision": decision.model_dump(mode="json")}

    typer.echo(json.dumps(asyncio.run(execute()), indent=2))


@app.command("resume")
def resume_run(run_id: str, adapter: AdapterOption = "fake", db: DbOption = None) -> None:
    """Resume a suspended run from its checkpoint; the harness delivers the awaited event."""

    runtime = build_runtime(_root(), adapter=_adapter(adapter), sqlite_path=db)  # type: ignore[arg-type]
    decision = asyncio.run(runtime.resume(run_id))
    typer.echo(
        json.dumps({"run_id": run_id, "decision": decision.model_dump(mode="json")}, indent=2)
    )


@app.command("replay")
def replay(
    run_id: str,
    to_seq: Annotated[int | None, typer.Option(help="Replay through this sequence")] = None,
    event_type: Annotated[str | None, typer.Option("--type", help="Filter by event type")] = None,
    actor: Annotated[str | None, typer.Option(help="Filter by actor name")] = None,
    db: DbOption = None,
) -> None:
    """Print a readable, filterable trajectory timeline."""

    db_path = _db(db)
    events = load_events(db_path, run_id, to_seq)
    if event_type:
        events = [event for event in events if event.type == event_type]
    if actor:
        events = [event for event in events if event.actor.name == actor]
    if not events:
        raise typer.BadParameter(f"no matching events for {run_id}")
    typer.echo(render_timeline(events))
    typer.echo(f"\nhash_chain_valid={verify_hash_chain(db_path, run_id)}")


@app.command("eval")
def evaluate_cases(
    case_ids: list[str],
    adapter: AdapterOption = "fake",
    workspace: Annotated[
        Path | None, typer.Option(help="Directory for isolated per-case stores")
    ] = None,
    runs: Annotated[int, typer.Option(min=1, help="Fresh attempts per case for pass^k")] = 1,
    report: Annotated[Path | None, typer.Option(help="Write the full JSON report here")] = None,
) -> None:
    """Run isolated case attempts and report correctness, pass^k and trajectory metrics."""

    root = _root()
    directory = workspace or root / "data/generated/eval" / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%S"
    )
    evaluator = GroundTruthEvaluator(root / "data/generated/ground_truth")

    async def evaluate_all() -> tuple[list[dict[str, object]], list[RunObservation]]:
        reports: list[dict[str, object]] = []
        observations: list[RunObservation] = []
        for case_id in case_ids:
            for run_index in range(1, runs + 1):
                name = case_id if runs == 1 else f"{case_id}-run-{run_index}"
                db_path = isolated_workspace(root, directory, name)
                runtime = build_runtime(root, adapter=_adapter(adapter), sqlite_path=db_path)  # type: ignore[arg-type]
                if case_id == QUEUE_SCENARIO_ID:
                    run_id, ranking = await rank_portfolio(runtime)
                    emitter = runtime.emitter(run_id)
                    events = emitter.events()
                    result = evaluator.evaluate_queue(ranking, events, emitter)
                    output: dict[str, object] | list[dict[str, object]] = ranking
                else:
                    decision = await runtime.run(case_id)
                    assert runtime.last_run_id
                    run_id = runtime.last_run_id
                    emitter = runtime.emitter(run_id)
                    events = emitter.events()
                    result = evaluator.evaluate(decision, events, emitter)
                    output = decision.model_dump(mode="json")
                observation = observe_run(
                    case_id=case_id,
                    run_index=run_index,
                    passed=result.passed,
                    trajectory_complete=result.trajectory_complete,
                    hash_chain_valid=verify_hash_chain(db_path, run_id),
                    output=output,
                    events=events,
                    capabilities={check.name: check.passed for check in result.capabilities},
                )
                observations.append(observation)
                reports.append(
                    {
                        "run_index": run_index,
                        "run_id": run_id,
                        "db": str(db_path),
                        **result.model_dump(mode="json"),
                        "metrics": observation.model_dump(mode="json"),
                    }
                )
        return reports, observations

    reports, observations = asyncio.run(evaluate_all())
    rendered = {
        "attempts": reports,
        "reliability": [row.model_dump(mode="json") for row in aggregate_reliability(observations)],
        "capability_matrix": capability_matrix(observations),
    }
    output_json = json.dumps(rendered, indent=2)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(f"{output_json}\n", encoding="utf-8")
    typer.echo(output_json)
    typer.echo(
        f"\n{sum(1 for item in reports if item['passed'])}/{len(reports)} attempts passed",
        err=True,
    )
    if not all(report["passed"] for report in reports):
        raise typer.Exit(1)


@app.command("queue")
def queue(adapter: AdapterOption = "fake", db: DbOption = None, top: int = 15) -> None:
    """Rank every open case by the hard clock that expires first (Q01)."""

    runtime = build_runtime(_root(), adapter=_adapter(adapter), sqlite_path=db)  # type: ignore[arg-type]
    run_id, ranking = asyncio.run(rank_portfolio(runtime))
    fields = ("rank", "case_id", "next_clock", "next_deadline", "overdue_clocks", "expired_rights")
    typer.echo(
        json.dumps(
            {"run_id": run_id, "top": [{key: row[key] for key in fields} for row in ranking[:top]]},
            indent=2,
        )
    )


@app.command("curate")
def curate(
    db: DbOption = None,
    as_of: Annotated[str | None, typer.Option(help="Curation date (YYYY-MM-DD)")] = None,
) -> None:
    """Run the offline SOP-DSP-005 memory curator as an evented, replayable job."""

    day = date.fromisoformat(as_of) if as_of else datetime.now(UTC).date()
    typer.echo(json.dumps(curate_offline(_db(db), as_of=day), indent=2))


@app.command("export-event-schema")
def export_event_schema(
    output: Annotated[Path | None, typer.Option(help="Write to a file instead of stdout")] = None,
) -> None:
    """Export the versioned frontend trajectory-event JSON Schema."""

    rendered = json.dumps(event_json_schema(), indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(rendered)
