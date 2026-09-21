import json
from pathlib import Path
from typing import Annotated

import typer

from domain.events import event_json_schema
from replay import load_events, render_timeline
from runtime import RuntimePaths, run_case

app = typer.Typer(no_args_is_help=True, help="Replay card-dispute investigation trajectories.")


@app.command("run")
def run(
    case_id: str,
    graph: Annotated[Path, typer.Option(help="Pristine LadybugDB evidence graph")] = Path(
        "data/generated/evidence.lbug"
    ),
    knowledge: Annotated[Path, typer.Option(help="Knowledge SQLite database")] = Path(
        "data/generated/knowledge.sqlite"
    ),
    run_dir: Annotated[Path, typer.Option(help="Directory for isolated run graphs")] = Path(
        "data/generated/runs"
    ),
    events: Annotated[Path, typer.Option(help="SQLite trajectory store")] = Path(
        "trajectory.sqlite"
    ),
    checkpoints: Annotated[Path, typer.Option(help="LangGraph checkpoint store")] = Path(
        "checkpoints.sqlite"
    ),
) -> None:
    """Investigate one dispute and print its structured CaseReport."""

    report = run_case(
        case_id,
        paths=RuntimePaths(
            source_graph=graph,
            knowledge_db=knowledge,
            run_dir=run_dir,
            trajectory_db=events,
            checkpoint_db=checkpoints,
        ),
    )
    typer.echo(report.model_dump_json(indent=2))


@app.command("replay")
def replay(
    run_id: str,
    to_seq: Annotated[int | None, typer.Option(help="Replay through this sequence")] = None,
    event_type: Annotated[str | None, typer.Option("--type", help="Filter by event type")] = None,
    actor: Annotated[str | None, typer.Option(help="Filter by actor name")] = None,
    db: Annotated[Path, typer.Option("--db", help="SQLite trajectory store")] = Path(
        "trajectory.sqlite"
    ),
) -> None:
    """Print a readable, filterable trajectory timeline."""

    events = load_events(db.resolve(), run_id, to_seq)
    if event_type:
        events = [event for event in events if event.type == event_type]
    if actor:
        events = [event for event in events if event.actor.name == actor]
    if not events:
        raise typer.BadParameter(f"no matching events for {run_id}")
    typer.echo(render_timeline(events))


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
