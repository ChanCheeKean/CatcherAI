from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from api.app import create_app


@pytest.fixture
async def stage4_client(project_root: Path, scenario_db: Path, tmp_path: Path):
    app = create_app(project_root, db_path=scenario_db, ui_dir=tmp_path / "ui")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_memory_filters_and_allowlisted_sources(stage4_client: httpx.AsyncClient) -> None:
    notes = await stage4_client.get(
        "/api/v1/memory/notes", params={"subject": "CUS-90012", "status": "active"}
    )
    assert notes.status_code == 200
    assert [item["note_id"] for item in notes.json()["items"]] == ["MEM-0142"]

    source = await stage4_client.get("/api/v1/sources/WEB-04114")
    assert source.status_code == 200
    assert source.json()["kind"] == "document"
    assert "ground_truth" not in source.text

    denied = await stage4_client.get("/api/v1/sources/../../ground_truth/cases/C02.json")
    assert denied.status_code in {404, 422}


@pytest.mark.anyio
async def test_bounded_case_graph_has_only_persisted_entities(
    stage4_client: httpx.AsyncClient,
) -> None:
    response = await stage4_client.get(
        "/api/v1/graph/cases/DSP-2026-90011", params={"depth": 1, "limit": 40}
    )
    assert response.status_code == 200
    graph = response.json()
    assert any(node["id"] == "Dispute:DSP-2026-90011" for node in graph["nodes"])
    assert len(graph["nodes"]) <= 40
    node_ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])


@pytest.mark.anyio
async def test_run_memory_graph_and_redacted_blob_endpoints(
    stage4_client: httpx.AsyncClient,
) -> None:
    started = await stage4_client.post(
        "/api/v1/runs",
        json={"case_id": "DSP-2026-90002", "adapter": "fake", "auto_resume": True},
    )
    run_id = started.json()["run_id"]
    for _ in range(200):
        summary = (await stage4_client.get(f"/api/v1/runs/{run_id}")).json()
        if summary["status"] == "decided":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("fake run did not decide")

    memory = await stage4_client.get(f"/api/v1/runs/{run_id}/memory")
    graph = await stage4_client.get(f"/api/v1/runs/{run_id}/graph")
    assert memory.status_code == graph.status_code == 200
    assert memory.json()["operations"]
    assert graph.json()["operations"]

    events = (
        await stage4_client.get(f"/api/v1/runs/{run_id}/events", params={"limit": 500})
    ).json()["items"]
    blob_ref = next(
        value
        for event in events
        for value in event["payload"].values()
        if isinstance(value, str) and value.startswith("sha256:")
    )
    blob = await stage4_client.get(f"/api/v1/runs/{run_id}/blobs/{blob_ref[7:]}")
    assert blob.status_code == 200
    assert "OPENAI_API_KEY" not in blob.text
