from __future__ import annotations

import os
import sqlite3
from functools import cache
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends

from api.dependencies import (
    get_db_path,
    get_models_config,
    get_root,
    get_routes_config,
    get_scenario_config,
)
from api.models import (
    AgentSummary,
    HealthResponse,
    MetaResponse,
    RouteSummary,
    SkillSummary,
    WorkflowGraph,
)
from api.workflow_graph import build_workflow_graph
from config import ModelsConfig, RoutesConfig, ScenarioConfig, load_agent_configs
from domain.events import event_json_schema
from storage import connect_readonly

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(db_path: Annotated[Path, Depends(get_db_path)]) -> HealthResponse:
    scenario_db = db_path.exists()
    status = "ok"
    if scenario_db:
        try:
            with connect_readonly(db_path) as connection:
                connection.execute("SELECT 1 FROM disputes LIMIT 1")
        except sqlite3.OperationalError:
            status = "degraded"
    else:
        status = "degraded"
    return HealthResponse(
        status=status,  # type: ignore[arg-type]
        scenario_db=scenario_db,
        scenario_db_path=str(db_path),
    )


@router.get("/meta", response_model=MetaResponse)
def meta(
    models: Annotated[ModelsConfig, Depends(get_models_config)],
    scenario: Annotated[ScenarioConfig, Depends(get_scenario_config)],
) -> MetaResponse:
    return MetaResponse(
        adapters={"fake": True, "openai": bool(os.environ.get("OPENAI_API_KEY"))},
        model=models.default.model,
        virtual_clock=scenario.virtual_clock,
        feature_flags={"sse_stream": True, "execution_manager": True},
    )


@router.get("/meta/routes", response_model=list[RouteSummary])
def routes(
    routes_config: Annotated[RoutesConfig, Depends(get_routes_config)],
) -> list[RouteSummary]:
    return [
        RouteSummary(
            id=route.id,
            priority=route.priority,
            match=route.match,
            depth=route.output.depth,
            graph_path=route.output.graph_path,
            agents=route.output.agents,
            skills=route.output.skills,
            budget=route.output.budget.model_dump(mode="json"),
        )
        for route in routes_config.routes
    ]


@router.get("/meta/agents", response_model=list[AgentSummary])
def agents(root: Annotated[Path, Depends(get_root)]) -> list[AgentSummary]:
    return _load_agent_summaries(root)


@cache
def _load_agent_summaries(root: Path) -> list[AgentSummary]:
    configs = load_agent_configs(root / "config" / "agents")
    return [
        AgentSummary(
            id=agent.id,
            version=agent.version,
            description=agent.description,
            tools=agent.tools,
            skills=agent.skills,
        )
        for agent in sorted(configs.values(), key=lambda a: a.id)
    ]


@router.get("/meta/skills", response_model=list[SkillSummary])
def skills(root: Annotated[Path, Depends(get_root)]) -> list[SkillSummary]:
    return _load_skill_summaries(root)


@cache
def _load_skill_summaries(root: Path) -> list[SkillSummary]:
    skill_root = root / "skills"
    results: list[SkillSummary] = []
    for skill_file in sorted(skill_root.glob("*/SKILL.md")):
        front_matter = _parse_front_matter(skill_file.read_text(encoding="utf-8"))
        results.append(
            SkillSummary(
                name=front_matter.get("name", skill_file.parent.name),
                description=front_matter.get("description", ""),
                version=int(front_matter.get("version", 1)),
                path=str(skill_file.relative_to(root)),
            )
        )
    return results


@router.get("/meta/workflow", response_model=WorkflowGraph)
def workflow() -> WorkflowGraph:
    return build_workflow_graph()


@router.get("/schema/events")
def schema_events() -> dict[str, object]:
    return event_json_schema()


def _parse_front_matter(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("---")
    front, _, _ = rest.partition("---")
    value = yaml.safe_load(front)
    return value if isinstance(value, dict) else {}
