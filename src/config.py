from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.case import RouteBudget
from domain.model import Capability


class DefaultModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    reasoning_effort: str = "medium"
    timeout_seconds: float = 60
    max_attempts: int = 3
    max_output_tokens: int = 12000
    required_capabilities: frozenset[Capability]


class RetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_backoff_ms: int = 500
    max_backoff_ms: int = 8000


class ConcurrencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model_calls: int = 8
    per_run: int = 4


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    provider: str
    api: str
    default: DefaultModelConfig
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @property
    def snapshot_hash(self) -> str:
        raw = json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


class RouteOutputConfig(BaseModel):
    depth: str
    graph_path: str
    agents: list[str]
    skills: list[str]
    budget: RouteBudget


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: int
    description: str
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    max_iterations: int = 4


class RouteConfig(BaseModel):
    id: str
    priority: int
    match: dict[str, Any]
    output: RouteOutputConfig


class RoutesConfig(BaseModel):
    schema_version: int
    route_confidence_threshold: float
    routes: list[RouteConfig]

    @model_validator(mode="after")
    def unique_ordered_routes(self) -> RoutesConfig:
        ids = [route.id for route in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("route ids must be unique")
        self.routes.sort(key=lambda route: route.priority)
        return self


class ScenarioConfig(BaseModel):
    id: str
    manifest: Path
    agent_root: Path
    policy_root: Path
    skill_root: Path
    sqlite_path: Path
    virtual_clock: str
    deny: list[str]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def load_models_config(path: Path) -> ModelsConfig:
    raw = _load_yaml(path)
    prefix = "DISPUTE_AGENT_MODEL__"
    overrides = {
        key[len(prefix) :].lower(): value
        for key, value in os.environ.items()
        if key.startswith(prefix)
    }
    if "MODEL".lower() in overrides:
        raw["default"]["model"] = overrides["model"]
    if "REASONING_EFFORT".lower() in overrides:
        raw["default"]["reasoning_effort"] = overrides["reasoning_effort"]
    return ModelsConfig.model_validate(raw)


def load_routes_config(path: Path) -> RoutesConfig:
    return RoutesConfig.model_validate(_load_yaml(path))


def load_agent_configs(path: Path) -> dict[str, AgentConfig]:
    agents = {
        config.id: config
        for file_path in sorted(path.glob("*.yaml"))
        for config in [AgentConfig.model_validate(_load_yaml(file_path))]
    }
    if len(agents) != len(list(path.glob("*.yaml"))):
        raise ValueError("agent ids must be unique")
    return agents


def load_scenario(path: Path, root: Path) -> ScenarioConfig:
    raw = _load_yaml(path)
    for key in ("manifest", "agent_root", "policy_root", "skill_root", "sqlite_path"):
        raw[key] = (root / raw[key]).resolve()
    return ScenarioConfig.model_validate(raw)
