from __future__ import annotations

from pathlib import Path

from config import load_models_config


def test_concurrency_config_has_no_dead_model_calls_field(project_root: Path) -> None:
    models = load_models_config(project_root / "config/models.yaml")
    assert models.concurrency.per_run == 4
    assert not hasattr(models.concurrency, "model_calls")
