"""Typed contract between the Dispute AI and a Merchant (see README: Merchant agent, not wired)."""

from __future__ import annotations

from schemas import SchemaModel


class EvidenceAsk(SchemaModel):
    topic: str  # e.g. "return policy accepted at purchase"
    detail: str


class MerchantEvidenceRequest(SchemaModel):
    dispute_id: str
    merchant_id: str
    charge_ids: list[str]
    asks: list[EvidenceAsk]


class SubmittedItem(SchemaModel):
    kind: str  # acceptance_log, folio, invoice_ledger, usage_log, …
    text: str
    asserts: list[str]  # graph ids the item is about (orders, charges, subscriptions, …)


class SubmittedMessage(SchemaModel):
    channel: str
    sender: str
    date: str
    text: str
    asserts: list[str]


class MerchantSubmission(SchemaModel):
    submission_id: str  # MSB-…
    dispute_id: str
    merchant_id: str
    statement: str
    items: list[SubmittedItem]
    messages: list[SubmittedMessage]
    cited_ids: list[str]  # clause (CLS-…) or policy document (POL-…) ids
