from __future__ import annotations

import ast
from pathlib import Path

import pytest

from data.access import AccessDenied, PathGuard


@pytest.mark.parametrize(
    "path",
    [
        "ground_truth/cases/C02.json",
        "simulation/cardholder_personas.json",
        "../generated/ground_truth/cases/C02.json",
        "/tmp/ground_truth.json",
    ],
)
def test_agent_filesystem_denies_evaluator_and_simulation_paths(tmp_path: Path, path: str) -> None:
    guard = PathGuard(tmp_path)
    with pytest.raises(AccessDenied):
        guard.resolve(path)


def test_provider_sdk_imports_are_confined_to_adapter_modules(project_root: Path) -> None:
    source_root = project_root / "src"
    violations: list[str] = []
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(source_root)
        if relative.parts[:1] == ("adapters",):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "openai" or name.startswith("openai.") for name in names):
                violations.append(str(relative))
    assert violations == []
