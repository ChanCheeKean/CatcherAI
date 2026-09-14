API_PREFIX = "/api/v1"


def run_urls(run_id: str) -> tuple[str, str]:
    base = f"{API_PREFIX}/runs/{run_id}"
    return f"{base}/events", f"{base}/events/stream"
