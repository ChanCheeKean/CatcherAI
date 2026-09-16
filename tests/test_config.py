from __future__ import annotations

from pathlib import Path

from config import load_models_config


def test_concurrency_config_has_no_dead_model_calls_field(project_root: Path) -> None:
    models = load_models_config(project_root / "config/models.yaml")
    assert models.concurrency.per_run == 4
    assert not hasattr(models.concurrency, "model_calls")


import yaml

from config import RoutesConfig


ROUTES_FIXTURE = """
schema_version: 1
route_confidence_threshold: 0.80
routes:
  - id: sample_route
    depth: L2
    description: A sample route for schema tests.
    required_skills: [eligibility-check]
depth_bounds:
  L1: {tool_calls: [3, 12], model_input_tokens: [10000, 100000], model_output_tokens: [2000, 14000], wall_seconds: [30, 240], replans: [0, 2], no_progress_iterations: [1, 2], max_agent_calls: [3, 6]}
  L2: {tool_calls: [5, 40], model_input_tokens: [30000, 150000], model_output_tokens: [4000, 20000], wall_seconds: [60, 320], replans: [0, 3], no_progress_iterations: [1, 3], max_agent_calls: [4, 8]}
  L3: {tool_calls: [8, 30], model_input_tokens: [50000, 100000], model_output_tokens: [6000, 14000], wall_seconds: [90, 260], replans: [1, 3], no_progress_iterations: [1, 3], max_agent_calls: [6, 10]}
  L4: {tool_calls: [15, 35], model_input_tokens: [100000, 140000], model_output_tokens: [12000, 20000], wall_seconds: [200, 320], replans: [1, 4], no_progress_iterations: [1, 3], max_agent_calls: [8, 16]}
"""


def test_routes_config_has_no_match_or_priority_fields() -> None:
    config = RoutesConfig.model_validate(yaml.safe_load(ROUTES_FIXTURE))
    route = config.routes[0]
    assert route.id == "sample_route"
    assert route.depth == "L2"
    assert route.required_skills == ["eligibility-check"]
    assert not hasattr(route, "match")
    assert not hasattr(route, "priority")
    assert not hasattr(route, "output")
    assert config.depth_bounds["L4"].max_agent_calls == (8, 16)


def test_routes_config_rejects_duplicate_ids() -> None:
    raw = yaml.safe_load(ROUTES_FIXTURE)
    raw["routes"].append(raw["routes"][0])
    try:
        RoutesConfig.model_validate(raw)
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("expected duplicate route ids to be rejected")
