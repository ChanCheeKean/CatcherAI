from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


T = TypeVar("T", bound=type[ToolInput])
_SCHEMAS: dict[str, type[ToolInput]] = {}


def register_tool_schema(name: str) -> Callable[[T], T]:
    def register(schema: T) -> T:
        if name in _SCHEMAS:
            raise ValueError(f"duplicate tool schema: {name}")
        _SCHEMAS[name] = schema
        return schema

    return register


def validate_tool_input(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        schema = _SCHEMAS[name]
    except KeyError as exc:
        raise KeyError(f"unregistered tool: {name}") from exc
    return schema.model_validate(arguments).model_dump(mode="json", exclude_none=True)


@register_tool_schema("get_case")
class GetCaseInput(ToolInput):
    case_id: str
    as_of: datetime


@register_tool_schema("get_case_transactions")
class GetCaseTransactionsInput(ToolInput):
    case_id: str
    as_of: datetime


@register_tool_schema("descriptor_history")
class DescriptorHistoryInput(ToolInput):
    customer_id: str
    merchant_id: str
    as_of: datetime


@register_tool_schema("graph_descriptor_variants")
class GraphDescriptorVariantsInput(ToolInput):
    merchant_id: str


@register_tool_schema("search_research")
class SearchResearchInput(ToolInput):
    merchant_id: str
    as_of: datetime


@register_tool_schema("clearing_group")
class ClearingGroupInput(ToolInput):
    auth_id: str
    as_of: datetime


@register_tool_schema("compute_group_clearings")
class ComputeGroupClearingsInput(ToolInput):
    txn_ids: list[str]


@register_tool_schema("read_evidence_packet")
class ReadEvidencePacketInput(ToolInput):
    case_id: str
    as_of: datetime


@register_tool_schema("message_cardholder")
class MessageCardholderInput(ToolInput):
    case_id: str
    question: str
    channel: str = "secure_message"


@register_tool_schema("retrieve_knowledge")
class RetrieveKnowledgeInput(ToolInput):
    query: str
    as_of: date
    kinds: list[str]


@register_tool_schema("read_memory_notes")
class ReadMemoryNotesInput(ToolInput):
    subject_ids: list[str]
    as_of: date
    minimum_confidence: float


@register_tool_schema("get_case_communications")
class GetCaseCommunicationsInput(ToolInput):
    case_id: str
    as_of: datetime


@register_tool_schema("get_account")
class GetAccountInput(ToolInput):
    account_id: str


@register_tool_schema("get_prior_disputes")
class GetPriorDisputesInput(ToolInput):
    customer_id: str
    current_case_id: str
    since: date
    as_of: datetime


@register_tool_schema("compute_write_off_eligibility")
class ComputeWriteOffEligibilityInput(ToolInput):
    txn_id: str
    amount: float
    threshold: float
    prior_dispute_count: int
    delinquency_days: int
    merchant_cluster_open: bool


@register_tool_schema("compute_unused_portion")
class ComputeUnusedPortionInput(ToolInput):
    amount: float
    service_start: date
    service_end: date
    used_through: date


@register_tool_schema("get_account_events")
class GetAccountEventsInput(ToolInput):
    account_id: str
    since: datetime
    until: datetime


@register_tool_schema("get_bank_holidays")
class GetBankHolidaysInput(ToolInput):
    since: date
    until: date


@register_tool_schema("get_customer_with_address")
class GetCustomerWithAddressInput(ToolInput):
    customer_id: str


@register_tool_schema("get_disputes_by_ids")
class GetDisputesByIdsInput(ToolInput):
    case_ids: list[str]
    as_of: datetime


@register_tool_schema("get_transactions_for_cases")
class GetTransactionsForCasesInput(ToolInput):
    case_ids: list[str]
    as_of: datetime


@register_tool_schema("get_transactions_by_ids")
class GetTransactionsByIdsInput(ToolInput):
    txn_ids: list[str]
    as_of: datetime


@register_tool_schema("graph_common_compromise_points")
class GraphCommonCompromisePointsInput(ToolInput):
    customer_id: str
    fraud_date: date
    lookback_days: int = 30


@register_tool_schema("graph_shared_delivery")
class GraphSharedDeliveryInput(ToolInput):
    case_id: str


@register_tool_schema("graph_shared_identity")
class GraphSharedIdentityInput(ToolInput):
    customer_id: str


@register_tool_schema("graph_disputes_for_customers")
class GraphDisputesForCustomersInput(ToolInput):
    customer_ids: list[str]
    family: str
    since: date


@register_tool_schema("compute_reg_e_deadlines")
class ComputeRegEDeadlinesInput(ToolInput):
    notice_date: date
    first_deposit_date: date
    transaction_dates: list[date]
    holidays: list[date]
    card_lost_or_stolen: bool = False


@register_tool_schema("request_evidence")
class RequestEvidenceInput(ToolInput):
    case_id: str
    provider: str
    evidence_types: list[str]
    target_txn_ids: list[str]


@register_tool_schema("request_record")
class RequestRecordInput(ToolInput):
    case_id: str
    provider: str
    evidence_types: list[str]
    target_txn_ids: list[str]


@register_tool_schema("get_dispute_events")
class GetDisputeEventsInput(ToolInput):
    case_ids: list[str]
    as_of: datetime


@register_tool_schema("list_dispute_conditions")
class ListDisputeConditionsInput(ToolInput):
    network: str


@register_tool_schema("find_related_merchants")
class FindRelatedMerchantsInput(ToolInput):
    merchant_id: str


@register_tool_schema("get_merchant_activity")
class GetMerchantActivityInput(ToolInput):
    merchant_ids: list[str]
    since: date


@register_tool_schema("graph_device_fingerprint_owners")
class GraphDeviceFingerprintOwnersInput(ToolInput):
    fingerprints: list[str]


@register_tool_schema("compute_window_deadlines")
class ComputeWindowDeadlinesInput(ToolInput):
    events: dict[str, date]
    days: int
    rule: str


@register_tool_schema("compute_case_clocks")
class ComputeCaseClocksInput(ToolInput):
    case_id: str
    notice_date: date
    statement_cycle_day: int
    response_processing_date: date | None = None
    dispute_processing_date: date | None = None


@register_tool_schema("compute_pattern_validity")
class ComputePatternValidityInput(ToolInput):
    observation_dates: list[date]
    ended_on: date


@register_tool_schema("get_statements")
class GetStatementsInput(ToolInput):
    account_id: str


@register_tool_schema("get_account_transactions")
class GetAccountTransactionsInput(ToolInput):
    account_id: str
    since: date
    until: date


@register_tool_schema("get_linked_transactions")
class GetLinkedTransactionsInput(ToolInput):
    txn_ids: list[str]


@register_tool_schema("get_fx_rates")
class GetFxRatesInput(ToolInput):
    dates: list[date]


@register_tool_schema("get_merchant")
class GetMerchantInput(ToolInput):
    merchant_id: str


@register_tool_schema("compute_local_time")
class ComputeLocalTimeInput(ToolInput):
    local: datetime
    from_tz: str
    to_tz: str


@register_tool_schema("compute_amount_with_tax")
class ComputeAmountWithTaxInput(ToolInput):
    unit: float
    quantity: int
    tax_rate: float


@register_tool_schema("compute_folio_lines")
class ComputeFolioLinesInput(ToolInput):
    disputed_codes: list[str]
    claimed_amount: float


@register_tool_schema("compute_fx_refund")
class ComputeFxRefundInput(ToolInput):
    purchase_txn_id: str
    refund_txn_id: str
    fee_rate: float
    reversal_window_days: int


@register_tool_schema("compute_credit_outstanding")
class ComputeCreditOutstandingInput(ToolInput):
    account_id: str
    purchase_date: date
    amount: float


@register_tool_schema("compute_ce3_priors")
class ComputeCe3PriorsInput(ToolInput):
    disputed_txn_id: str
    processing_date: date
    version: str


@register_tool_schema("compute_business_days")
class ComputeBusinessDaysInput(ToolInput):
    start: date
    days: int


@register_tool_schema("list_open_portfolio")
class ListOpenPortfolioInput(ToolInput):
    as_of: datetime


@register_tool_schema("compute_portfolio_clocks")
class ComputePortfolioClocksInput(ToolInput):
    case_id: str
    today: date
