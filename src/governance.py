"""SOP-DSP-003 v6 and SOP-DSP-004 v2 governance as deterministic, testable code.

The review panel's advocates and adjudicator run as isolated subagents, but the gate itself
(when a panel is required, how confidence is scored, when the conservative default applies,
which automated actions are allowed) never depends on prompt compliance.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord

THRESHOLD = 0.75
GOVERNING_SOP = "LFB-SOP-DSP-003@v6"
FAIRNESS_SOP = "LFB-SOP-DSP-004@v2"

PROHIBITED_BASES = re.compile(
    r"\b(race|color|religion|national origin|sex|marital status|age|public assistance|"
    r"zip code|neighborhood|accent|demeanou?r|elderly|senior citizen|"
    r"sounds (?:old|young|elderly|confused|nervous|evasive))\b",
    re.IGNORECASE,
)
CHARACTER_LABELS = re.compile(r"\b(fraudster|abuser|liar|scammer|fraudulent customer)\b", re.I)
REOPEN_ACTIONS = frozenset({"reopen_case", "credit_reopened_case"})
ADVERSE_NETWORK_ACTIONS = frozenset({"file_dispute", "pre_arbitration"})


def panel_triggers(
    case: dict[str, Any], proposal: DecisionRecord, facts: dict[str, bool]
) -> list[str]:
    """SOP-DSP-003 §2 trigger codes; a non-empty list makes the panel mandatory."""

    denied = proposal.cardholder_resolution.outcome.startswith("denied")
    amount = Decimal(str(case.get("dispute_amount") or "0"))
    triggers = []
    if denied and case.get("claim_family_initial", "").startswith("fraud") and amount >= 500:
        triggers.append("unauthorized_use_denial_500_or_more")
    if denied and facts.get("cardholder_contests_issuer_evidence"):
        triggers.append("cardholder_contests_issuer_evidence")
    if REOPEN_ACTIONS & {str(action.get("action")) for action in proposal.automated_actions}:
        triggers.append("reopen_or_amend_closed_case")
    if facts.get("authority_determination"):
        triggers.append("authority_household_determination")
    if facts.get("no_applicable_rule") or facts.get("novel_transaction_type"):
        triggers.append("no_applicable_rule_or_novel_type")
    if facts.get("cross_customer_finding"):
        triggers.append("cross_customer_abuse_finding")
    return triggers


def score(hypothesis: dict[str, Any]) -> dict[str, float]:
    """Evidence-weighted support. Memory leads carry no weight: they are never evidence."""

    support = sum(float(item["weight"]) for item in hypothesis["evidence_for"])
    opposition = sum(float(item["weight"]) for item in hypothesis["evidence_against"])
    total = support + opposition
    return {
        "support": support,
        "opposition": opposition,
        "net": support - opposition,
        "confidence": round(support / total, 3) if total else 0.0,
    }


def advocate_position(board: list[dict[str, Any]], side: str) -> dict[str, str]:
    """The strongest hypothesis available to one advocate."""

    candidates = [item for item in board if item["favors"] == side]
    if not candidates:
        return {
            "role": f"{side}_advocate",
            "hypothesis": "none",
            "summary": f"No source-linked hypothesis favors the {side}.",
            "confidence": "0.0",
            "flip_fact": "Any source-linked fact supporting this side.",
        }
    best = max(candidates, key=lambda item: score(item)["net"])
    return {
        "role": f"{side}_advocate",
        "hypothesis": best["id"],
        "summary": f"{best['label']}: {best['outcome']}",
        "confidence": str(score(best)["confidence"]),
        "flip_fact": best["flip_fact"],
    }


def adjudicate(board: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the hypothesis with the greatest net evidence and score its confidence."""

    best = max(board, key=lambda item: (score(item)["net"], item["id"]))
    return {
        "hypothesis": best["id"],
        "label": best["label"],
        "favors": best["favors"],
        "flip_fact": best["flip_fact"],
        **score(best),
    }


def favors_cardholder(record: DecisionRecord) -> bool:
    resolution = record.cardholder_resolution
    return resolution.credit_amount > 0 and not resolution.outcome.startswith("denied")


def fairness_violations(record: DecisionRecord) -> list[str]:
    """SOP-DSP-004 prohibited bases and character labels in cardholder-facing or memory text."""

    text = " ".join(
        [
            record.explanation_for_cardholder,
            *[str(op.get("content", "")) for op in record.memory_ops],
            *[str(position.get("summary", "")) for position in record.adjudication.positions],
        ]
    )
    return sorted(
        {
            match.group(0).casefold()
            for pattern in (PROHIBITED_BASES, CHARACTER_LABELS)
            for match in pattern.finditer(text)
        }
    )


def apply_conservative_default(
    record: DecisionRecord, *, disputed_amount: Decimal, reason: str
) -> DecisionRecord:
    """SOP-DSP-003 §3: favor the cardholder, file nothing uncertain, and absorb the loss."""

    network_actions = [
        action.model_copy(
            update={
                "action": "no_dispute",
                "condition": None,
                "reason": "eligibility not certain; conservative default",
            }
        )
        if action.action in ADVERSE_NETWORK_ACTIONS
        else action
        for action in record.network_actions
    ]
    return record.model_copy(
        update={
            "network_actions": network_actions,
            "cardholder_resolution": CardholderResolution(
                outcome="credited_conservative_default",
                credit_amount=disputed_amount,
                reversal_amount=Decimal("0"),
                liability_amount=Decimal("0"),
            ),
            "automated_actions": [
                *record.automated_actions,
                {"action": "issuer_absorbs_loss", "amount": str(disputed_amount), "reason": reason},
            ],
            "adjudication": record.adjudication.model_copy(
                update={"conservative_default_applied": True}
            ),
            "letters": ["reg_z_credit_final_conservative_default"],
            "explanation_for_cardholder": (
                "We reviewed the available evidence and could not confirm the charge with "
                "enough certainty, so we resolved it in your favor and credited "
                f"${disputed_amount}. No further action is needed from you."
            ),
        }
    )


def panel_adjudication(
    record: DecisionRecord, positions: list[dict[str, str]], ruling: dict[str, Any]
) -> DecisionRecord:
    return record.model_copy(
        update={
            "adjudication": Adjudication(
                review_panel_used=True,
                positions=[
                    *positions,
                    {
                        "role": "adjudicator",
                        "hypothesis": ruling["hypothesis"],
                        "summary": ruling["label"],
                        "confidence": str(ruling["confidence"]),
                        "flip_fact": ruling["flip_fact"],
                    },
                ],
                confidence=ruling["confidence"],
                threshold=THRESHOLD,
                conservative_default_applied=False,
                flip_fact=ruling["flip_fact"],
            )
        }
    )
