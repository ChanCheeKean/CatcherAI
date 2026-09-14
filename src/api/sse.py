"""Ordered, reconnectable SSE tail over a run's committed SQLite event log.

Polls the store rather than subscribing to the in-process `EventEmitter`: this is the design's
chosen Stage 2 approach (§5.3) because it works uniformly for a live run, a run resumed in a
different API process, and a purely historical replay, whereas an in-process subscription only
covers the first case. `sse_starlette.EventSourceResponse`'s own `ping` keyword supplies the
15-second heartbeat comment (§5.3); this module only has to decide when to stop.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Request

from api.read_models import derive_status, list_events
from api.run_manager import RunManager
from storage import connect_readonly

POLL_INTERVAL_SECONDS = 0.15
BATCH_LIMIT = 500


async def stream_run_events(
    manager: RunManager, store: Path, run_id: str, after_seq: int, request: Request
) -> AsyncIterator[dict[str, Any]]:
    last_seq = after_seq
    connection = connect_readonly(store)
    try:
        while True:
            if await request.is_disconnected():
                return
            events, _ = list_events(
                connection,
                run_id,
                after_seq=last_seq,
                event_type=None,
                actor=None,
                ref=None,
                limit=BATCH_LIMIT,
            )
            for event in events:
                yield {"id": str(event.seq), "event": event.type, "data": event.model_dump_json()}
                last_seq = event.seq
            if events:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            status = derive_status(connection, run_id)
            done = manager.is_task_done(run_id)
            if done is True or (done is None and status != "running"):
                # The driving task can commit its final event(s) and finish in the window
                # between the query above and this check; poll once more before stopping so a
                # run that ends between two ticks never drops its terminal event(s).
                final_events, _ = list_events(
                    connection,
                    run_id,
                    after_seq=last_seq,
                    event_type=None,
                    actor=None,
                    ref=None,
                    limit=BATCH_LIMIT,
                )
                for event in final_events:
                    yield {
                        "id": str(event.seq),
                        "event": event.type,
                        "data": event.model_dump_json(),
                    }
                return
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        connection.close()
