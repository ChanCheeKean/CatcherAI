"""An optional Merchant disputes desk over that Merchant's own records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from extensions.merchant_agent.contract import MerchantEvidenceRequest, MerchantSubmission
from models import invoke_structured, provider_strategy

_MAX_RECORD_CHARS = 12_000
_PROMPT = (
    "You are the Merchant's disputes desk. Answer each ask only from your own records; "
    "cite the ids the records mention; say plainly when you have no record. "
    "Use list_records and read_record to inspect the Merchant's files."
)


def record_tools(records_dir: Path) -> list[BaseTool]:
    """Expose only file names and bounded text reads inside one Merchant folder."""
    directory = records_dir.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError(f"Merchant records directory is not a directory: {records_dir}")

    @tool
    def list_records() -> str:
        """List available file names in this Merchant's records folder."""
        return "\n".join(sorted(path.name for path in directory.iterdir() if path.is_file()))

    @tool
    def read_record(name: str) -> str:
        """Read a named Merchant record as text, up to 12000 characters."""
        if Path(name).name != name or name in {"", ".", ".."}:
            return "Error: invalid record name"
        try:
            path = (directory / name).resolve(strict=True)
            if path.parent != directory or not path.is_file():
                return "Error: record is outside the Merchant folder or is not a file"
            with path.open(encoding="utf-8", errors="replace") as record:
                return record.read(_MAX_RECORD_CHARS)
        except (OSError, ValueError):
            return "Error: record could not be read"

    return [list_records, read_record]


def respond(
    request: MerchantEvidenceRequest,
    records_root: Path,
    model: Any,
    agent_builder=create_deep_agent,
) -> MerchantSubmission:
    """Answer a typed evidence request using only the named Merchant's records."""
    merchant_id = request.merchant_id
    if Path(merchant_id).name != merchant_id or merchant_id in {"", ".", ".."}:
        raise ValueError("Invalid Merchant id")
    root = records_root.resolve(strict=True)
    merchant_dir = (root / merchant_id).resolve(strict=True)
    if merchant_dir.parent != root:
        raise ValueError("Merchant records are outside the records root")
    agent = agent_builder(
        model=model,
        tools=record_tools(merchant_dir),
        system_prompt=_PROMPT,
        response_format=provider_strategy(MerchantSubmission),
    )
    return invoke_structured(agent, MerchantSubmission, [HumanMessage(request.model_dump_json())])
