import json
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from domain.events import event_json_schema
from evaluation import evaluate, load_truth, write_summary
from replay import load_events, render_timeline
from runtime import RuntimePaths, run_case
from showcase import export, install

load_dotenv()
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
    notebook: Annotated[Path, typer.Option(help="Case Notebook SQLite database")] = Path(
        "data/generated/notebook.sqlite"
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
            notebook_db=notebook,
            trajectory_db=events,
            checkpoint_db=checkpoints,
        ),
    )
    typer.echo(report.model_dump_json(indent=2))


@app.command("eval")
def eval_cases(
    cases: Annotated[list[str] | None, typer.Option("--cases", help="Case codes or ids")] = None,
    k: Annotated[int, typer.Option(help="Attempts per case (pass@k)")] = 1,
    parallel: Annotated[int, typer.Option(help="Concurrent runs")] = 3,
) -> None:
    """Run cases with the real model and score them against the ground truth."""

    truths = load_truth(cases)
    if not truths:
        raise typer.BadParameter("no matching cases")
    summary = evaluate(truths, k=k, parallel=parallel)
    out = write_summary(summary)
    typer.echo((out / "summary.md").read_text())
    typer.echo(f"written to {out}")


@app.command("showcase-export")
def showcase_export() -> None:
    """Snapshot the latest completed run of every case into data/showcase/ for committing."""

    for case_id, run_id in sorted(export().items()):
        typer.echo(f"{case_id}: {run_id}")


@app.command("showcase-install")
def showcase_install() -> None:
    """Restore data/generated/ and the stored runs from the committed data/showcase/."""

    install()
    typer.echo("showcase restored")


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
