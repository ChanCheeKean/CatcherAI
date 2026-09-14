from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


class ClearingResult(BaseModel):
    clearing_count: int
    observed_sequences: list[int]
    total_cleared: Decimal
    authorized_amount: Decimal
    is_split_clearing: bool
    exceeds_authorization: bool


class WriteOffResult(BaseModel):
    txn_id: str
    eligible: bool
    amount: Decimal
    threshold: Decimal
    checks: dict[str, bool]


class UnusedPortionResult(BaseModel):
    days_in_period: int
    days_used: int
    days_unused: int
    amount: Decimal
    unused_portion: Decimal
    used_portion: Decimal


class RegEDeadlineResult(BaseModel):
    new_account: bool
    provisional_credit_business_days: int
    provisional_credit_deadline: date
    written_confirmation_due_if_bank_requires: date
    investigation_deadline: date
    liability_amount: Decimal


def _add_business_days(start: date, days: int, holidays: set[date]) -> date:
    current = start
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            remaining -= 1
    return current


def reg_e_deadlines(
    *,
    notice_date: date,
    first_deposit_date: date,
    transaction_dates: list[date],
    holidays: list[date],
    card_lost_or_stolen: bool,
    emitter: EventEmitter,
) -> RegEDeadlineResult:
    """Apply tested Reg E new-account and business-day calendar rules."""

    holiday_set = set(holidays)
    new_account = any(
        0 <= (transaction_date - first_deposit_date).days <= 30
        for transaction_date in transaction_dates
    )
    provisional_days = 20 if new_account else 10
    result = RegEDeadlineResult(
        new_account=new_account,
        provisional_credit_business_days=provisional_days,
        provisional_credit_deadline=_add_business_days(notice_date, provisional_days, holiday_set),
        written_confirmation_due_if_bank_requires=_add_business_days(notice_date, 10, holiday_set),
        investigation_deadline=notice_date + timedelta(days=90),
        liability_amount=Decimal("0") if not card_lost_or_stolen else Decimal("50"),
    )
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.SANDBOX, name="reg_e_deadlines"),
            type="computation",
            summary="Computed Reg E new-account, liability and business-day deadlines",
            payload={
                "helper": "reg_e_deadlines",
                "code": (
                    "new_account=any(0 <= txn-first_deposit <= 30); "
                    "provisional=add_business_days(notice, 20 if new_account else 10, "
                    "holidays); investigation=notice+90 calendar days; "
                    "liability=0 when access device was not lost or stolen"
                ),
                "inputs": {
                    "notice_date": notice_date.isoformat(),
                    "first_deposit_date": first_deposit_date.isoformat(),
                    "transaction_dates": [value.isoformat() for value in transaction_dates],
                    "holidays": [value.isoformat() for value in holidays],
                    "card_lost_or_stolen": card_lost_or_stolen,
                },
                "stdout": "",
                "stderr": "",
                "output": result.model_dump(mode="json"),
                "runtime_ms": 0,
                "status": "success",
            },
            refs=["REGE-1005.6", "REGE-1005.11", "LFB-CB-2025-09"],
        )
    )
    return result


def group_clearings(rows: list[dict[str, Any]], emitter: EventEmitter) -> ClearingResult:
    code = (
        "total_cleared = sum(Decimal(row['billing_amount']) for row in rows); "
        "is_split = one auth_id and sequences cover clearing_count"
    )
    sequences = sorted(int(row["clearing_seq"]) for row in rows)
    total = sum((Decimal(row["billing_amount"]) for row in rows), Decimal("0"))
    auth_amount = Decimal(rows[0]["auth_amount"]) if rows else Decimal("0")
    expected_count = int(rows[0]["clearing_count"]) if rows else 0
    one_auth = len({row["auth_id"] for row in rows}) == 1
    result = ClearingResult(
        clearing_count=len(rows),
        observed_sequences=sequences,
        total_cleared=total,
        authorized_amount=auth_amount,
        is_split_clearing=one_auth and sequences == list(range(1, expected_count + 1)),
        exceeds_authorization=total > auth_amount,
    )
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.SANDBOX, name="group_clearings"),
            type="computation",
            summary="Computed clearing aggregation in the sandbox helper",
            payload={
                "helper": "group_clearings",
                "code": code,
                "inputs": {"rows": rows},
                "stdout": "",
                "stderr": "",
                "output": result.model_dump(mode="json"),
                "runtime_ms": 0,
                "status": "success",
            },
            refs=[str(row["txn_id"]) for row in rows],
        )
    )
    return result


def write_off_eligibility(
    *,
    txn_id: str,
    amount: Decimal,
    threshold: Decimal,
    prior_dispute_count: int,
    delinquency_days: int,
    merchant_cluster_open: bool,
    emitter: EventEmitter,
) -> WriteOffResult:
    checks = {
        "amount_lte_threshold": amount <= threshold,
        "no_prior_disputes_12m": prior_dispute_count == 0,
        "delinquency_lte_30_days": delinquency_days <= 30,
        "merchant_cluster_absent": not merchant_cluster_open,
    }
    result = WriteOffResult(
        txn_id=txn_id,
        eligible=all(checks.values()),
        amount=amount,
        threshold=threshold,
        checks=checks,
    )
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.SANDBOX, name="write_off_eligibility"),
            type="computation",
            summary=f"Computed write-off eligibility for {txn_id}",
            payload={
                "helper": "write_off_eligibility",
                "code": "eligible = all(SOP_DSP_002_v4_checks)",
                "inputs": {
                    "txn_id": txn_id,
                    "amount": str(amount),
                    "threshold": str(threshold),
                    "prior_dispute_count": prior_dispute_count,
                    "delinquency_days": delinquency_days,
                    "merchant_cluster_open": merchant_cluster_open,
                },
                "stdout": "",
                "stderr": "",
                "output": result.model_dump(mode="json"),
                "runtime_ms": 0,
                "status": "success",
            },
            refs=[txn_id, "LFB-SOP-DSP-002@v4"],
        )
    )
    return result


def unused_portion(
    *,
    amount: Decimal,
    service_start: date,
    service_end: date,
    used_through: date,
    emitter: EventEmitter,
) -> UnusedPortionResult:
    days_in_period = (service_end - service_start).days + 1
    days_used = (used_through - service_start).days + 1
    days_unused = days_in_period - days_used
    value = (amount * Decimal(days_unused) / Decimal(days_in_period)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    result = UnusedPortionResult(
        days_in_period=days_in_period,
        days_used=days_used,
        days_unused=days_unused,
        amount=amount,
        unused_portion=value,
        used_portion=amount - value,
    )
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.SANDBOX, name="unused_portion"),
            type="computation",
            summary="Computed the validity-bounded unused subscription portion",
            payload={
                "helper": "unused_portion",
                "code": (
                    "days=(end-start)+1; used=(used_through-start)+1; "
                    "unused=amount*(days-used)/days; round_half_up(0.01); used=amount-unused"
                ),
                "inputs": {
                    "amount": str(amount),
                    "service_start": service_start.isoformat(),
                    "service_end": service_end.isoformat(),
                    "used_through": used_through.isoformat(),
                },
                "stdout": "",
                "stderr": "",
                "output": result.model_dump(mode="json"),
                "runtime_ms": 0,
                "status": "success",
            },
            refs=["VISA-13.5@2026-04-18"],
        )
    )
    return result


def _record_computation(
    emitter: EventEmitter,
    helper: str,
    summary: str,
    *,
    code: str,
    inputs: dict[str, Any],
    output: dict[str, Any],
    refs: list[str],
) -> None:
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.SANDBOX, name=helper),
            type="computation",
            summary=summary,
            payload={
                "helper": helper,
                "code": code,
                "inputs": inputs,
                "stdout": "",
                "stderr": "",
                "output": output,
                "runtime_ms": 0,
                "status": "success",
            },
            refs=refs,
        )
    )


def add_business_days(start: date, days: int, holidays: set[date]) -> date:
    """Move a signed number of business days, skipping weekends and bank holidays."""

    current, step = start, 1 if days >= 0 else -1
    for _ in range(abs(days)):
        current += timedelta(days=step)
        while current.weekday() >= 5 or current in holidays:
            current += timedelta(days=step)
    return current


def reg_z_resolution_deadline(notice: date, cycle_day: int) -> date:
    """End of the second complete billing cycle after notice, capped at 90 days."""

    def month_add(day: date, months: int) -> date:
        index = day.month - 1 + months
        return date(day.year + index // 12, index % 12 + 1, min(cycle_day, 28))

    cycle_end = date(notice.year, notice.month, min(cycle_day, 28))
    if cycle_end < notice:
        cycle_end = month_add(cycle_end, 1)
    return min(month_add(cycle_end, 2), notice + timedelta(days=90))


class ClockResult(BaseModel):
    deadlines: dict[str, date]
    governing_clock: str
    latest_safe_decision_date: date


def case_clocks(
    *,
    case: dict[str, Any],
    account: dict[str, Any],
    transactions: list[dict[str, Any]],
    holidays: list[date],
    emitter: EventEmitter,
) -> ClockResult:
    """Regulatory and network clocks for one case, and the SOP-DSP-003 latest safe time."""

    notice = date.fromisoformat(case["opened_at"][:10])
    holiday_set = set(holidays)
    deadlines: dict[str, date] = {}
    if case["regime"] == "REG_Z":
        deadlines["reg_z_resolution_deadline"] = reg_z_resolution_deadline(
            notice, int(account["statement_cycle_day"])
        )
    else:
        first_deposit = account.get("first_deposit_date")
        new_account = bool(first_deposit) and any(
            0
            <= (date.fromisoformat(row["processing_date"]) - date.fromisoformat(first_deposit)).days
            <= 30
            for row in transactions
        )
        if not case.get("provisional_credit_at"):
            deadlines["reg_e_provisional_credit_deadline"] = add_business_days(
                notice, 20 if new_account else 10, holiday_set
            )
        deadlines["reg_e_investigation_deadline"] = notice + timedelta(
            days=90 if new_account else 45
        )
    if case.get("response_processing_date"):
        deadlines["pre_arb_deadline"] = date.fromisoformat(
            case["response_processing_date"]
        ) + timedelta(days=30)
    elif not case.get("dispute_processing_date") and transactions:
        earliest = min(date.fromisoformat(row["processing_date"]) for row in transactions)
        deadlines["visa_dispute_time_limit"] = earliest + timedelta(days=120)
    governing = min(deadlines, key=lambda name: deadlines[name])
    result = ClockResult(
        deadlines=deadlines,
        governing_clock=governing,
        latest_safe_decision_date=add_business_days(deadlines[governing], -2, holiday_set),
    )
    _record_computation(
        emitter,
        "case_clocks",
        f"Computed case clocks; {governing} governs the latest safe decision time",
        code=(
            "reg_z=min(end_of_second_complete_cycle(notice, cycle_day), notice+90d); "
            "reg_e=notice+10|20 business days, investigation 45|90 days; "
            "pre_arb=response_processing+30d; visa_limit=earliest_processing+120d; "
            "latest_safe=add_business_days(min(deadlines), -2, holidays)"
        ),
        inputs={
            "case_id": case["case_id"],
            "regime": case["regime"],
            "notice_date": notice.isoformat(),
            "statement_cycle_day": account.get("statement_cycle_day"),
            "dispute_processing_date": case.get("dispute_processing_date"),
            "response_processing_date": case.get("response_processing_date"),
            "transaction_processing_dates": [row["processing_date"] for row in transactions],
            "holidays": sorted(value.isoformat() for value in holiday_set),
        },
        output=result.model_dump(mode="json"),
        refs=[case["case_id"], "LFB-SOP-DSP-003@v6"],
    )
    return result


def window_deadlines(
    *,
    events: dict[str, date],
    days: int,
    rule: str,
    refs: list[str],
    emitter: EventEmitter,
) -> dict[str, date]:
    """Calendar-day windows such as merchant refund periods, keyed by the source event."""

    result = {key: value + timedelta(days=days) for key, value in events.items()}
    _record_computation(
        emitter,
        "window_deadlines",
        f"Computed {days}-day windows: {rule}",
        code=f"deadline = event_date + {days} calendar days",
        inputs={"events": {key: value.isoformat() for key, value in events.items()}, "rule": rule},
        output={key: value.isoformat() for key, value in result.items()},
        refs=refs,
    )
    return result


def pattern_validity_window(
    *, observation_dates: list[date], ended_on: date, refs: list[str], emitter: EventEmitter
) -> dict[str, str]:
    """Validity of a consolidated pattern: the month it was first observed until it stopped."""

    first = min(observation_dates)
    result = {
        "valid_from": date(first.year, first.month, 1).isoformat(),
        "valid_to": ended_on.isoformat(),
        "observations": str(len(observation_dates)),
        "all_before_end": str(all(value < ended_on for value in observation_dates)),
    }
    _record_computation(
        emitter,
        "pattern_validity_window",
        "Bounded the merchant pattern to the period it was observed",
        code="valid_from = first_day_of_month(min(observations)); valid_to = change date",
        inputs={
            "observation_dates": sorted(value.isoformat() for value in observation_dates),
            "ended_on": ended_on.isoformat(),
        },
        output=result,
        refs=refs,
    )
    return result


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def convert_local_time(
    *, local: str, from_tz: str, to_tz: str, refs: list[str], emitter: EventEmitter
) -> dict[str, str]:
    """Re-express a wall-clock time recorded in one time zone in another zone."""

    from datetime import datetime
    from zoneinfo import ZoneInfo

    source = datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(from_tz))
    target = source.astimezone(ZoneInfo(to_tz))
    result = {
        "source": source.isoformat(),
        "converted": target.isoformat(),
        "utc": source.astimezone(ZoneInfo("UTC")).isoformat(),
    }
    _record_computation(
        emitter,
        "convert_local_time",
        f"Converted {local} {from_tz} to {to_tz}",
        code="datetime(local, tz=from_tz).astimezone(to_tz)",
        inputs={"local": local, "from_tz": from_tz, "to_tz": to_tz},
        output=result,
        refs=refs,
    )
    return result


def amount_with_tax(
    *, unit: Decimal, quantity: int, tax_rate: Decimal, refs: list[str], emitter: EventEmitter
) -> dict[str, str]:
    base = unit * quantity
    tax = (base * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result = {"base": _money(base), "tax": _money(tax), "total": _money(base + tax)}
    _record_computation(
        emitter,
        "amount_with_tax",
        f"Computed {quantity} x {unit} plus {tax_rate} tax",
        code="base=unit*quantity; tax=round_half_up(base*tax_rate, 0.01); total=base+tax",
        inputs={"unit": str(unit), "quantity": quantity, "tax_rate": str(tax_rate)},
        output=result,
        refs=refs,
    )
    return result


def folio_line_amounts(
    *,
    lines: list[dict[str, Any]],
    disputed_codes: list[str],
    claimed_amount: Decimal,
    refs: list[str],
    emitter: EventEmitter,
) -> dict[str, Any]:
    """Split a folio into supported and disputed lines, each with its own tax rate."""

    taxed = [line for line in lines if line.get("taxable_rate")]
    by_rate: dict[str, Decimal] = {}
    for line in taxed:
        by_rate[line["taxable_rate"]] = by_rate.get(line["taxable_rate"], Decimal("0")) + Decimal(
            line["amount"]
        )
    taxes = {
        rate: (base * Decimal(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for rate, base in by_rate.items()
    }
    disputed = Decimal("0")
    for line in taxed:
        if line["code"] in disputed_codes:
            amount = Decimal(line["amount"])
            disputed += amount + (amount * Decimal(line["taxable_rate"])).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
    total = sum(by_rate.values(), Decimal("0")) + sum(taxes.values(), Decimal("0"))
    result = {
        "tax_by_rate": {rate: _money(value) for rate, value in taxes.items()},
        "folio_total": _money(total),
        "disputed_with_tax": _money(disputed),
        "claimed_amount": _money(claimed_amount),
        "denied_portion": _money(claimed_amount - disputed),
    }
    _record_computation(
        emitter,
        "folio_line_amounts",
        "Recomputed folio taxes and split disputed from supported lines",
        code=(
            "tax[rate]=round(sum(lines at rate)*rate); disputed=sum(line+round(line*rate)) for "
            "disputed codes; denied=claimed-disputed"
        ),
        inputs={
            "lines": lines,
            "disputed_codes": disputed_codes,
            "claimed_amount": str(claimed_amount),
        },
        output=result,
        refs=refs,
    )
    return result


def fx_refund_breakdown(
    *,
    purchase: dict[str, Any],
    refund: dict[str, Any],
    fee: dict[str, Any] | None,
    fee_rate: Decimal,
    reversal_window_days: int,
    refs: list[str],
    emitter: EventEmitter,
) -> dict[str, Any]:
    """Explain a USD refund shortfall and test the issuer fee-reversal rule."""

    def converted(row: dict[str, Any]) -> Decimal:
        return (Decimal(row["txn_amount"]) * Decimal(row["fx_rate"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    purchase_usd, refund_usd = converted(purchase), converted(refund)
    expected_fee = (purchase_usd * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    days = (
        date.fromisoformat(refund["processing_date"])
        - date.fromisoformat(purchase["processing_date"])
    ).days
    full_refund = Decimal(refund["txn_amount"]) == Decimal(purchase["txn_amount"])
    result = {
        "purchase_usd": _money(purchase_usd),
        "refund_usd": _money(refund_usd),
        "fx_difference": _money(purchase_usd - refund_usd),
        "transaction_currency_refund_complete": full_refund,
        "fee_expected": _money(expected_fee),
        "fee_charged": fee["billing_amount"] if fee else "0.00",
        "days_purchase_to_refund": days,
        "fee_reversal_amount": _money(Decimal(fee["billing_amount"]))
        if fee and full_refund and days <= reversal_window_days
        else "0.00",
    }
    _record_computation(
        emitter,
        "fx_refund_breakdown",
        "Recomputed FX conversions and foreign-fee reversal eligibility",
        code=(
            "usd=round(txn_amount*fx_rate); difference=purchase_usd-refund_usd; "
            "fee=round(purchase_usd*3%); "
            "reverse fee if refund equals purchase in transaction currency within window"
        ),
        inputs={
            "purchase": purchase,
            "refund": refund,
            "fee": fee,
            "fee_rate": str(fee_rate),
            "reversal_window_days": reversal_window_days,
        },
        output=result,
        refs=refs,
    )
    return result


def credit_outstanding(
    *,
    statements: list[dict[str, Any]],
    purchase_date: date,
    amount: Decimal,
    refs: list[str],
    emitter: EventEmitter,
) -> dict[str, Any]:
    """Compute the amount outstanding for a Reg Z claims-and-defenses analysis."""

    ordered = sorted(statements, key=lambda row: row["cycle_end"])
    first = next(
        row
        for row in ordered
        if row["cycle_start"] <= purchase_date.isoformat() <= row["cycle_end"]
    )
    later = [row for row in ordered if row["cycle_end"] > first["cycle_end"]]
    paid_in_full = [
        Decimal(row["payments"]) >= Decimal(previous["closing_balance"])
        for previous, row in zip([first, *later], later, strict=False)
    ]
    unpaid = Decimal("0") if later and all(paid_in_full) else amount
    result = {
        "first_statement_id": first["statement_id"],
        "first_statement_transmitted": first["transmitted_at"][:10],
        "cycles_after_purchase": len(later),
        "every_later_cycle_paid_prior_balance": bool(later) and all(paid_in_full),
        "credit_outstanding": _money(unpaid),
    }
    _record_computation(
        emitter,
        "credit_outstanding",
        "Tested whether any credit for the purchase remains outstanding",
        code="outstanding = 0 if every later payment >= prior closing balance else purchase amount",
        inputs={
            "statement_ids": [row["statement_id"] for row in ordered],
            "purchase_date": purchase_date.isoformat(),
            "amount": str(amount),
        },
        output=result,
        refs=refs,
    )
    return result


def ce3_prior_transactions(
    *,
    disputed: dict[str, Any],
    priors: list[dict[str, Any]],
    processing_date: date,
    same_acquirer_counts: bool,
    min_age_days: int,
    max_age_days: int,
    refs: list[str],
    emitter: EventEmitter,
) -> dict[str, Any]:
    """Which prior undisputed transactions qualify under one CE 3.0 version on a processing date."""

    qualifying, excluded = [], []
    for row in priors:
        age = (processing_date - date.fromisoformat(row["txn_local_datetime"][:10])).days
        same_merchant = row["merchant_id"] == disputed["merchant_id"]
        eligible_party = same_merchant or (
            same_acquirer_counts and row["acquirer_id"] == disputed["acquirer_id"]
        )
        if not eligible_party:
            excluded.append(
                {"txn_id": row["txn_id"], "age_days": age, "reason": "different merchant"}
            )
        elif not min_age_days < age <= max_age_days:
            excluded.append(
                {
                    "txn_id": row["txn_id"],
                    "age_days": age,
                    "reason": f"<{min_age_days} days"
                    if age <= min_age_days
                    else f">{max_age_days} days",
                }
            )
        else:
            qualifying.append({"txn_id": row["txn_id"], "age_days": age})
    result = {
        "processing_date": processing_date.isoformat(),
        "qualifying": qualifying,
        "excluded": excluded,
        "two_priors_met": len(qualifying) >= 2,
    }
    _record_computation(
        emitter,
        "ce3_prior_transactions",
        f"Aged prior transactions against processing date {processing_date}",
        code=(
            f"age=processing_date-txn_date; qualifies if {min_age_days}<age<={max_age_days} and "
            f"{'same acquirer' if same_acquirer_counts else 'same merchant'}"
        ),
        inputs={
            "disputed_txn_id": disputed["txn_id"],
            "prior_txn_ids": [row["txn_id"] for row in priors],
            "same_acquirer_counts": same_acquirer_counts,
        },
        output=result,
        refs=refs,
    )
    return result


def business_day_offset(
    *,
    start: date,
    days: int,
    holidays: list[date],
    rule: str,
    refs: list[str],
    emitter: EventEmitter,
) -> date:
    result = add_business_days(start, days, set(holidays))
    _record_computation(
        emitter,
        "business_day_offset",
        f"Computed {days} business days from {start}: {rule}",
        code="add_business_days(start, days, weekends and bank holidays skipped)",
        inputs={
            "start": start.isoformat(),
            "days": days,
            "rule": rule,
            "holidays": sorted(value.isoformat() for value in holidays),
        },
        output={"date": result.isoformat()},
        refs=refs,
    )
    return result


def portfolio_case_clocks(
    *,
    case: dict[str, Any],
    transactions: list[dict[str, Any]],
    acknowledged: bool,
    remedy_windows: list[dict[str, Any]],
    today: date,
    holidays: list[date],
    emitter: EventEmitter,
) -> dict[str, Any]:
    """Every hard clock on one open case, and which one expires first."""

    opened = date.fromisoformat(case["opened_at"][:10])
    holiday_set = set(holidays)
    clocks: list[tuple[str, date]] = []
    if case["regime"] == "REG_Z":
        if not acknowledged:
            clocks.append(("reg_z_acknowledgment", opened + timedelta(days=30)))
        clocks.append(
            (
                "reg_z_resolution",
                reg_z_resolution_deadline(opened, int(case["statement_cycle_day"])),
            )
        )
    else:
        first_deposit = case.get("first_deposit_date")
        new_account = bool(first_deposit) and any(
            0
            <= (
                date.fromisoformat(row["txn_local_datetime"][:10])
                - date.fromisoformat(first_deposit)
            ).days
            <= 30
            for row in transactions
        )
        if not case.get("provisional_credit_at"):
            clocks.append(
                (
                    "reg_e_provisional_credit",
                    add_business_days(opened, 20 if new_account else 10, holiday_set),
                )
            )
        point_of_sale = any(row["channel"] in {"in_store", "ecommerce"} for row in transactions)
        clocks.append(
            (
                "reg_e_investigation",
                opened + timedelta(days=90 if new_account or point_of_sale else 45),
            )
        )
    if case.get("response_processing_date") and case["stage"] == "pre_arb_decision_due":
        clocks.append(
            (
                "visa_pre_arbitration",
                date.fromisoformat(case["response_processing_date"]) + timedelta(days=30),
            )
        )
    processing = [row["processing_date"] for row in transactions if row["processing_date"]]
    if not case.get("dispute_processing_date") and processing:
        clocks.append(
            ("visa_dispute_time_limit", date.fromisoformat(min(processing)) + timedelta(days=120))
        )
    clocks.extend(
        (window["name"], date.fromisoformat(window["deadline"])) for window in remedy_windows
    )
    expired = [
        (name, value)
        for name, value in clocks
        if name == "visa_dispute_time_limit" and value < today
    ]
    future = [(name, value) for name, value in clocks if value >= today]
    overdue = [
        (name, value) for name, value in clocks if value < today and (name, value) not in expired
    ]
    next_clock = min(future, key=lambda item: item[1]) if future else None
    result = {
        "case_id": case["case_id"],
        "regime": case["regime"],
        "stage": case["stage"],
        "amount": case["dispute_amount"],
        "all_clocks": [[name, value.isoformat()] for name, value in clocks],
        "next_clock": next_clock[0] if next_clock else None,
        "next_deadline": next_clock[1].isoformat() if next_clock else None,
        "overdue_clocks": [[name, value.isoformat()] for name, value in overdue],
        "expired_rights": [[name, value.isoformat()] for name, value in expired],
    }
    _record_computation(
        emitter,
        "portfolio_case_clocks",
        f"Computed hard clocks for {case['case_id']}",
        code=(
            "Reg Z: ack=opened+30d unless sent; resolution=two complete cycles capped at 90d. "
            "Reg E: provisional="
            "opened+10|20 business days unless posted; investigation=45|90d. "
            "pre_arb=response+30d; visa_limit="
            "earliest processing+120d if not filed (expired rights when past); merchant remedy "
            "windows from research"
        ),
        inputs={
            "case": case,
            "transaction_ids": [row["txn_id"] for row in transactions],
            "acknowledged": acknowledged,
            "remedy_windows": remedy_windows,
            "today": today.isoformat(),
        },
        output=result,
        refs=[case["case_id"]],
    )
    return result
