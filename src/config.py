from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class DefaultModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    reasoning_effort: str = "medium"
    timeout_seconds: float = 60
    max_attempts: int = 3
    max_output_tokens: int = 12000
    required_capabilities: frozenset[str] = frozenset()


class RetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_backoff_ms: int = 500
    max_backoff_ms: int = 8000


class ConcurrencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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


class CaseTypeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    description: str
    suggested_skills: list[str] = Field(default_factory=list)
    suggested_roles: list[str] = Field(default_factory=list)


class RoleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    description: str
    prompt: str
    default_skills: list[str] = Field(default_factory=list)


class AgentPrompts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    triage: str
    supervisor: str


class AgentRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_turns: int = Field(default=8, gt=0)
    no_progress_turns: int = Field(default=2, gt=0)
    max_parallel_tasks: int = Field(default=4, gt=0)


class AgentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_types: list[CaseTypeConfig]
    roles: list[RoleConfig]
    prompts: AgentPrompts
    runtime: AgentRuntimeConfig = Field(default_factory=AgentRuntimeConfig)

    @property
    def case_type_map(self) -> dict[str, CaseTypeConfig]:
        return {case_type.id: case_type for case_type in self.case_types}

    @property
    def role_map(self) -> dict[str, RoleConfig]:
        return {role.id: role for role in self.roles}


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


def load_agents_config(path: Path) -> AgentsConfig:
    return AgentsConfig.model_validate(_load_yaml(path))
