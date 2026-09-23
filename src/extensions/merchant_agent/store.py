"""Save Merchant Submissions for ingestion on the next static graph build."""

from __future__ import annotations

from pathlib import Path

from extensions.merchant_agent.contract import MerchantSubmission


def save_submission(
    submission: MerchantSubmission, out_dir: Path = Path("data/corpus/submissions")
) -> Path:
    dispute_id = submission.dispute_id
    if Path(dispute_id).name != dispute_id or dispute_id in {"", ".", ".."}:
        raise ValueError("Invalid Dispute id")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{dispute_id}.json"
    path.write_text(submission.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
