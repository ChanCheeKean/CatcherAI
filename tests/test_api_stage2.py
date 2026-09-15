"""Stage 2: execution manager and live SSE stream.

Every test drives the API through `httpx.AsyncClient` over an in-process ASGI transport so the
SSE stream can be consumed concurrently with the background run it is following, exactly as a
browser's `EventSource` would. `scenario_db` (from `conftest.py`) is a per-test tmp_path copy of
the pristine store; `ui_dir` additionally isolates each test's UI run workspaces from the real
`data/generated/ui/` directory.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest

from api.app import create_app


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _client(project_root: Path, scenario_db: Path, tmp_path: Path) -> httpx.AsyncClient:
    app = create_app(project_root, db_path=scenario_db, ui_dir=tmp_path / "ui")
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0
    )


async def _drain_stream(
    client: httpx.AsyncClient,
    run_id: str,
    *,
    after_seq: int = 0,
    last_event_id: int | None = None,
) -> tuple[list[int], list[str]]:
    """Consume an SSE stream to its natural close and return parallel (seq, type) lists."""

    seqs: list[int] = []
    types: list[str] = []
    headers = {"last-event-id": str(last_event_id)} if last_event_id is not None else {}
    params = {} if last_event_id is not None else {"after_seq": after_seq}
    async with client.stream(
        "GET", f"/api/v1/runs/{run_id}/events/stream", params=params, headers=headers
    ) as response:
        assert response.status_code == 200
        # An SSE frame's `id`/`event`/`data` lines may arrive in any order; a blank line ends it.
        seq: int | None = None
        event_type: str | None = None
        async for line in response.aiter_lines():
            if line.startswith("id:"):
                seq = int(line.removeprefix("id:").strip())
            elif line.startswith("event:"):
                event_type = line.removeprefix("event:").strip()
            elif line == "":
                if seq is not None and event_type is not None:
                    seqs.append(seq)
                    types.append(event_type)
                seq, event_type = None, None
    return seqs, types


async def test_start_run_returns_202_and_streams_gap_free_to_decision(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    async with _client(project_root, scenario_db, tmp_path) as client:
        response = await client.post(
            "/api/v1/runs", json={"case_id": "DSP-2026-90002", "adapter": "fake"}
        )
        assert response.status_code == 202
        body = response.json()
        run_id = body["run_id"]
        assert body["case_id"] == "DSP-2026-90002"
        assert body["status"] == "running"
        assert body["stream_url"] == f"/api/v1/runs/{run_id}/events/stream"

        seqs, types = await _drain_stream(client, run_id)
        assert seqs, "expected at least one streamed event"
        assert seqs == list(range(1, len(seqs) + 1)), "sequence must be gap-free and dup-free"
        assert "termination" in types
        assert "route_decision" in types

        summary = (await client.get(f"/api/v1/runs/{run_id}")).json()
        assert summary["status"] == "decided"
        assert summary["decision_available"] is True

        page = (await client.get(f"/api/v1/runs/{run_id}/events", params={"limit": 500})).json()
        assert len(page["items"]) == len(seqs)
        assert page["items"][-1]["seq"] == seqs[-1]

        decision = await client.get(f"/api/v1/runs/{run_id}/decision")
        assert decision.status_code == 200
        assert decision.json()["case_id"] == "DSP-2026-90002"


async def test_reconnect_yields_exact_missing_suffix(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    async with _client(project_root, scenario_db, tmp_path) as client:
        started = await client.post("/api/v1/runs", json={"case_id": "DSP-2026-90002"})
        run_id = started.json()["run_id"]

        full_seqs, full_types = await _drain_stream(client, run_id)
        midpoint = full_seqs[len(full_seqs) // 2]
        split_index = full_seqs.index(midpoint) + 1

        suffix_seqs, suffix_types = await _drain_stream(client, run_id, after_seq=midpoint)
        assert suffix_seqs == full_seqs[split_index:]
        assert suffix_types == full_types[split_index:]
        assert midpoint not in suffix_seqs

        # `Last-Event-ID` (the browser EventSource reconnect header) must take precedence.
        header_seqs, header_types = await _drain_stream(client, run_id, last_event_id=midpoint)
        assert header_seqs == suffix_seqs
        assert header_types == suffix_types


async def test_two_simultaneous_runs_are_isolated_and_preserve_the_pristine_store(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    pristine = project_root / "data/generated/disputes.sqlite"
    before = _sha256(pristine)
    async with _client(project_root, scenario_db, tmp_path) as client:
        first, second = await asyncio.gather(
            client.post("/api/v1/runs", json={"case_id": "DSP-2026-90002"}),
            client.post("/api/v1/runs", json={"case_id": "DSP-2026-90003"}),
        )
        assert first.status_code == 202
        assert second.status_code == 202
        run_ids = {first.json()["run_id"], second.json()["run_id"]}
        assert len(run_ids) == 2

        await asyncio.gather(*(_drain_stream(client, run_id) for run_id in run_ids))

        for run_id in run_ids:
            summary = (await client.get(f"/api/v1/runs/{run_id}")).json()
            assert summary["status"] == "decided"

        listing = (await client.get("/api/v1/runs")).json()
        assert run_ids <= {row["run_id"] for row in listing["items"]}

    assert _sha256(pristine) == before, "UI-started runs must never mutate the pristine store"


async def test_cancel_is_idempotent_and_rerun_starts_a_fresh_isolated_run(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    async with _client(project_root, scenario_db, tmp_path) as client:
        started = await client.post("/api/v1/runs", json={"case_id": "DSP-2026-90002"})
        run_id = started.json()["run_id"]

        # The fake adapter is fast enough that this run may already be decided by the time
        # cancel lands; either outcome is a legitimate terminal state and neither is an error.
        cancelled = await client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] in {"cancelled", "decided"}

        # A second cancel of an already-finished run is a documented no-op, not an error.
        again = await client.post(f"/api/v1/runs/{run_id}/cancel")
        assert again.status_code in {200, 409}

        rerun = await client.post(f"/api/v1/runs/{run_id}/rerun")
        assert rerun.status_code == 202
        new_run_id = rerun.json()["run_id"]
        assert new_run_id != run_id
        assert rerun.json()["case_id"] == "DSP-2026-90002"

        await _drain_stream(client, new_run_id)
        summary = (await client.get(f"/api/v1/runs/{new_run_id}")).json()
        assert summary["status"] == "decided"


async def test_rerun_of_an_unmanaged_run_id_is_rejected(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    async with _client(project_root, scenario_db, tmp_path) as client:
        response = await client.post("/api/v1/runs/run-does-not-exist/rerun")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "run_not_rerunnable"


async def test_queue_run_ranks_open_cases(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    async with _client(project_root, scenario_db, tmp_path) as client:
        started = await client.post("/api/v1/queue/runs", json={"adapter": "fake"})
        assert started.status_code == 202
        run_id = started.json()["run_id"]

        seqs, types = await _drain_stream(client, run_id)
        assert seqs == list(range(1, len(seqs) + 1))
        assert "portfolio_ranked" in types

        result = (await client.get(f"/api/v1/queue/runs/{run_id}")).json()
        assert result["status"] == "ranked"
        assert result["ranking"]
        assert result["ranking"][0]["rank"] == 1


async def test_starting_a_run_never_mutates_the_pristine_store_even_on_a_bad_case_id(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    pristine = project_root / "data/generated/disputes.sqlite"
    before = _sha256(pristine)
    async with _client(project_root, scenario_db, tmp_path) as client:
        started = await client.post("/api/v1/runs", json={"case_id": "DSP-2026-NOPE"})
        assert started.status_code == 202
        run_id = started.json()["run_id"]

        seqs, types = await _drain_stream(client, run_id)
        assert "error" in types
        summary = (await client.get(f"/api/v1/runs/{run_id}")).json()
        assert summary["status"] == "failed"

    assert _sha256(pristine) == before


@pytest.mark.parametrize("case_id", ["DSP-2026-90002"])
async def test_get_runs_merges_across_isolated_stores_and_the_default_store(
    project_root: Path, scenario_db: Path, tmp_path: Path, runtime, case_id: str
) -> None:
    """A run created directly against the app's configured store (Stage 1 style, bypassing
    `RunManager`) must still show up in `GET /runs` alongside API-started runs."""

    await runtime.run(case_id)
    direct_run_id = runtime.last_run_id
    assert direct_run_id

    async with _client(project_root, scenario_db, tmp_path) as client:
        started = await client.post("/api/v1/runs", json={"case_id": case_id})
        api_run_id = started.json()["run_id"]
        await _drain_stream(client, api_run_id)

        listing = (await client.get("/api/v1/runs")).json()
        run_ids = {row["run_id"] for row in listing["items"]}
        assert {direct_run_id, api_run_id} <= run_ids
