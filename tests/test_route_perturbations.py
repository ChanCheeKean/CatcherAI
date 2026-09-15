from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap import build_runtime
from evaluation.perturbations import create_perturbed_store, decision_semantics

CASES = [
    "DSP-2026-90001",
    "DSP-2026-90002",
    "DSP-2026-90003",
    "DSP-2026-90005",
    "DSP-2026-90006",
    "DSP-2026-90007",
    "DSP-2026-90008",
    "DSP-2026-90009",
    "DSP-2026-90010",
    "DSP-2026-90011",
    "DSP-2026-90012",
    "DSP-2026-90013",
    "DSP-2026-90014",
    "DSP-2026-90015",
    "DSP-2026-90016",
    "DSP-2026-90017",
    "DSP-2026-90019",
    "DSP-2026-90020",
    "DSP-2026-90021",
    "DSP-2026-90022",
]


@pytest.mark.parametrize("case_id", CASES)
async def test_route_semantics_survive_three_unseen_presentation_variants(
    project_root: Path, tmp_path: Path, case_id: str
) -> None:
    source = project_root / "data/generated/disputes.sqlite"
    baseline_db = tmp_path / f"{case_id}-baseline.sqlite"
    create_perturbed_store(source, baseline_db, seed=0)
    baseline = (await build_runtime(project_root, sqlite_path=baseline_db).run(case_id)).model_dump(
        mode="json"
    )
    expected = decision_semantics(baseline)

    for seed in (1, 2, 3):
        variant_db = tmp_path / f"{case_id}-variant-{seed}.sqlite"
        renamed = create_perturbed_store(source, variant_db, seed=seed)
        runtime = build_runtime(project_root, sqlite_path=variant_db)
        decision = (await runtime.run(case_id)).model_dump(mode="json")
        assert decision_semantics(decision) == expected
        assert runtime.last_run_id
        assert runtime.emitter(runtime.last_run_id).verify_chain()
        original_names = set(renamed)
        rendered = json_text(decision)
        assert not any(name in rendered for name in original_names if len(name) >= 5)


def json_text(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True)
