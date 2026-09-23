"""Merchant Submissions: the one path from a typed submission into the evidence graph."""

from __future__ import annotations

from pathlib import Path

from graph_builder import Graph

from extensions.merchant_agent.contract import MerchantSubmission


def insert_submission(g: Graph, s: MerchantSubmission) -> None:
    """Add the submission, its evidence items and messages (ids derived from the submission id),
    what each one asserts, and the policies it cites."""
    suffix = s.submission_id.removeprefix("MSB-")
    g.node("MerchantSubmission", s.submission_id, statement=s.statement)
    g.edge("HAS_SUBMISSION", s.dispute_id, s.submission_id)
    for n, item in enumerate(s.items, start=1):
        evidence = g.node(
            "EvidenceItem", f"EVI-{suffix}-{n}", kind=item.kind, source="merchant", text=item.text
        )
        _file(g, s.submission_id, evidence, item.asserts)
    for n, m in enumerate(s.messages, start=1):
        message = g.node(
            "Communication",
            f"COM-{suffix}-{n}",
            channel=m.channel,
            sender=m.sender,
            date=m.date,
            text=m.text,
        )
        _file(g, s.submission_id, message, m.asserts)
    for cited in s.cited_ids:
        g.edge("CITES", s.submission_id, cited)


def _file(g: Graph, submission: str, evidence: str, asserts: list[str]) -> None:
    g.edge("HAS_EVIDENCE", submission, evidence)
    for record in asserts:
        g.edge("ASSERTS", evidence, record)


def load_saved(directory: Path) -> list[MerchantSubmission]:
    """Every submission saved as `<dispute_id>.json`; none when the directory is absent."""
    return [
        MerchantSubmission.model_validate_json(path.read_text())
        for path in sorted(directory.glob("*.json"))
    ]
