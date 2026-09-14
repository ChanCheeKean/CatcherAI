"""C14-style route: a guaranteed-reservation no-show after a phone cancellation.

The deadline is in hotel local time while the cardholder's evidence is in their phone's time zone,
so the decision turns on a sandboxed conversion. Billing more than one night is independently
improper.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from runtime.context import RunContext, check
from sandbox import amount_with_tax, convert_local_time

STEPS = ["gather_evidence"]
EVIDENCE_USE = "confirm the cancellation policy, nights charged and any cancellation record"
QUERY = (
    "VISA 13.7 cancelled guaranteed reservation no-show more than one night lodging PRE 0019 "
    "hotel local time"
)
CALL = re.compile(
    r"phone region: ([A-Za-z ]+)\)?: '\w{3}, (\w{3}) (\d{1,2}) · "
    r"(\d{1,2}:\d{2} [AP]M) · (\([0-9]{3}\) [0-9-]+)"
)
DEADLINE = re.compile(r"by (\d{1,2}:\d{2} [AP]M) hotel local time", re.I)
NIGHTLY = re.compile(r"\$(\d+\.\d{2})/night \+ (\d+\.\d+)% tax")


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, txn = state["case"], state["transactions"][0]
    communications = ctx.call(
        "get_case_communications",
        "Read the reservation terms and the cardholder's call log",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    merchant = ctx.call(
        "get_merchant",
        "Get the hotel's local time zone and phone number",
        {"merchant_id": txn["merchant_id"]},
        lambda: ctx.data.merchant(txn["merchant_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve no-show rules and comparable precedent",
        {"query": QUERY, "as_of": case["opened_at"][:10], "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(
            QUERY, as_of=datetime.fromisoformat(case["opened_at"][:10]).date(), limit=16
        ),
    )
    lessons = ctx.call(
        "read_memory_notes",
        "Read procedural lessons about hotel time zones as leads",
        {"subject_ids": [], "as_of": ctx.clock.now.date().isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(
            subject_ids=[], as_of=ctx.clock.now.date(), scope="procedure"
        ),
    )
    attachments = " ".join(
        item["description"]
        for row in communications
        for item in json.loads(row["attachments"] or "[]")
    )
    return {
        "knowledge": knowledge,
        "memory_notes": lessons,
        "findings": {
            "communications": communications,
            "merchant": merchant,
            "attachments": attachments,
        },
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    findings, merchant = state["findings"], state["findings"]["merchant"]
    packet = json.loads(packets[0]["json"])
    reservation = packet["reservation"]
    region, month, day, clock_time, number = CALL.search(findings["attachments"]).groups()
    arrival = datetime.fromisoformat(reservation["arrival"])
    call_local = datetime.strptime(
        f"{arrival.year} {month} {day} {clock_time}", "%Y %b %d %I:%M %p"
    )
    phone_tz = ctx.data.city_timezone(region.strip())
    converted = ctx.call(
        "compute_local_time",
        "Convert the call time from the phone's zone to hotel local time",
        {"local": call_local.isoformat(), "from_tz": phone_tz, "to_tz": merchant["timezone"]},
        lambda: convert_local_time(
            local=call_local.isoformat(),
            from_tz=phone_tz,
            to_tz=merchant["timezone"],
            refs=[packets[0]["packet_id"]],
            emitter=ctx.emitter,
        ),
    )
    deadline_time = datetime.strptime(
        DEADLINE.search(findings["attachments"]).group(1), "%I:%M %p"
    ).time()
    deadline_day = arrival.date().fromordinal(arrival.date().toordinal() - 2)
    deadline = datetime.combine(deadline_day, deadline_time).isoformat()
    rate, tax_percent = NIGHTLY.search(findings["attachments"]).groups()
    one_night = ctx.call(
        "compute_amount_with_tax",
        "Compute the most a no-show may bill: one night plus tax",
        {"unit": float(rate), "quantity": 1, "tax_rate": float(Decimal(tax_percent) / 100)},
        lambda: amount_with_tax(
            unit=Decimal(rate),
            quantity=1,
            tax_rate=Decimal(tax_percent) / 100,
            refs=["VISA-13.7@2026-04-18"],
            emitter=ctx.emitter,
        ),
    )
    lesson = next((note for note in state["memory_notes"] if "local time" in note["content"]), None)
    if lesson:
        ctx.notes.verify(
            lesson,
            reason="Deadline stated in hotel local time; call log recorded in the phone's zone",
            evidence_refs=[packets[0]["packet_id"]],
        )
    return {
        "findings": {
            **findings,
            "call_hotel_local": converted["converted"],
            "deadline_hotel_local": deadline,
            "call_number": number,
            "nights_charged": packet["charge"]["nights"],
            "one_night": one_night,
            "cancellation_record": packet["call_center_log"],
        }
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    packet_id = state["evidence"][0]["packet_id"]
    call_local = findings["call_hotel_local"][:19]
    precedent = next((row for row in state["knowledge"] if row["doc_id"] == "PRE-0019"), None)
    if precedent:
        ctx.knowledge.reject(
            precedent,
            reason="PRE-0019's call was after the hotel-local deadline; this call was before it",
            evidence_refs=[packet_id],
        )
    return [
        check(
            "13_7_retrieved",
            "VISA-13.7@2026-04-18" in {row["doc_id"] for row in state["knowledge"]},
            {},
            ["VISA-13.7@2026-04-18"],
        ),
        check(
            "call_placed_to_hotel",
            findings["call_number"] == findings["merchant"]["phone"],
            {"called": findings["call_number"], "hotel": findings["merchant"]["phone"]},
            [findings["merchant"]["merchant_id"]],
        ),
        check(
            "cancelled_before_hotel_local_deadline",
            call_local < findings["deadline_hotel_local"],
            {"call": findings["call_hotel_local"], "deadline": findings["deadline_hotel_local"]},
            [packet_id],
        ),
        check(
            "no_show_billed_more_than_one_night",
            findings["nights_charged"] > 1,
            {"nights": findings["nights_charged"], "maximum_valid": findings["one_night"]["total"]},
            [packet_id],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, txn, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(txn["billing_amount"])
    call = datetime.fromisoformat(findings["call_hotel_local"])
    tz_abbreviation = call.tzname() and (
        "ET" if findings["merchant"]["timezone"] == "America/New_York" else call.tzname()
    )
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="cancelled_guaranteed_reservation",
        network_actions=[
            NetworkAction(
                txn_id=txn["txn_id"],
                case_id=case["case_id"],
                action="file_dispute",
                condition="13.7",
                amount=amount,
                reason="guaranteed reservation cancelled before the hotel-local deadline",
                certification=[
                    f"cardholder properly cancelled on {call:%Y-%m-%d %H:%M} {tz_abbreviation}",
                    "no-show billed for more than one night",
                ],
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="provisional_credit_pending_network",
            credit_amount=amount,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        fallback={
            "minimum_valid_amount": findings["one_night"]["total"],
            "basis": "no-show billed for more than one day's accommodation",
        },
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.95,
            flip_fact="Evidence the call reached the hotel after the 6:00 PM hotel-local deadline.",
        ),
        citations=[
            {
                "doc_id": "VISA-13.7@2026-04-18",
                "why": "Cancelled guaranteed reservation billed as a no-show",
            },
            {
                "doc_id": "PRE-0019",
                "why": "Distinguished: that call came after the hotel-local deadline",
            },
        ],
        confidence=0.95,
        explanation_for_cardholder=(
            f"Your phone logged the call at {findings['attachments'].split('·')[1].strip()} "
            "Pacific time, which was "
            f"{call:%-I:%M %p} at the hotel, before its 6:00 PM local deadline. We credited "
            f"${amount} and filed a "
            "dispute. Even if the cancellation were contested, a no-show can be billed for at "
            "most one night "
            f"(${findings['one_night']['total']})."
        ),
    )
