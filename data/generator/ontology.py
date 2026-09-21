"""The evidence-graph ontology: one plain dict per node label and per edge type.

Node: label -> {"prefix": id prefix, "props": {name: type}}; every node also has `id STRING`.
Edge: type -> {"pairs": [(src_label, dst_label), ...], "props": {name: type}}; every edge also has
`id STRING` ("E-..."). Relationships that change over time carry `valid_from`/`valid_to`
(ISO strings, empty = open); point-in-time ones carry `ts`.
"""

S, N, F, B = "STRING", "INT64", "DOUBLE", "BOOLEAN"

NODES: dict[str, dict] = {
    # Identity
    "Customer": {"prefix": "CUS", "props": {"name": S, "segment": S, "opened_at": S}},
    "Account": {
        "prefix": "ACC",
        "props": {"kind": S, "status": S, "opened_at": S, "credit_limit": F},
    },
    "Card": {"prefix": "CRD", "props": {"last4": S, "network": S, "status": S, "issued_at": S}},
    "Token": {"prefix": "TOK", "props": {"wallet": S, "created_at": S}},
    "Device": {"prefix": "DEV", "props": {"kind": S, "fingerprint": S}},
    "IP": {"prefix": "IP", "props": {"address": S, "kind": S}},
    "Phone": {"prefix": "PHN", "props": {"number": S}},
    "Email": {"prefix": "EML", "props": {"address": S}},
    "Address": {"prefix": "ADR", "props": {"street": S, "unit": S, "city": S, "postcode": S}},
    "MerchantAccount": {"prefix": "MAC", "props": {"handle": S, "created_at": S}},
    # Commerce
    "Merchant": {"prefix": "MER", "props": {"name": S, "mcc": S, "kind": S, "country": S}},
    "Terminal": {"prefix": "TRM", "props": {"kind": S, "location": S}},
    "Descriptor": {"prefix": "DSC", "props": {"text": S}},
    "Authorization": {"prefix": "AUT", "props": {"ts": S, "amount": F, "currency": S, "status": S}},
    "Transaction": {
        "prefix": "TXN",
        "props": {"ts": S, "amount": F, "currency": S, "kind": S, "channel": S, "status": S},
    },
    "PurchaseOrder": {"prefix": "ORD", "props": {"ts": S, "total": F, "currency": S, "items": S}},
    "Shipment": {"prefix": "SHP", "props": {"carrier": S, "tracking": S, "shipped_at": S}},
    "AgentProvider": {"prefix": "AGP", "props": {"name": S, "kind": S}},
    "Mandate": {
        "prefix": "MDT",
        "props": {"scope": S, "max_amount": F, "valid_from": S, "valid_to": S},
    },
    # Case
    "Dispute": {
        "prefix": "DSP",
        "props": {"filed_at": S, "claim_type": S, "amount": F, "intake": S, "status": S},
    },
    "EvidenceItem": {"prefix": "EVI", "props": {"kind": S, "source": S, "text": S, "ts": S}},
    "EvidenceRequest": {
        "prefix": "ERQ",
        "props": {"party": S, "status": S, "deadline": S, "deadline_passed": B, "responded_at": S},
    },
    "Communication": {"prefix": "COM", "props": {"channel": S, "ts": S, "sender": S, "text": S}},
    "AccountEvent": {"prefix": "AEV", "props": {"kind": S, "ts": S, "detail": S}},
    "MemoryNote": {
        "prefix": "MEM",
        "props": {"text": S, "status": S, "created_at": S, "run_id": S, "confidence": F},
    },
    "Finding": {
        "prefix": "FND",
        "props": {"text": S, "kind": S, "run_id": S, "confidence": F, "evidence_path": S},
    },
}

VALID = {"valid_from": S, "valid_to": S}
# Provenance carried by everything an agent may infer and write back to the graph.
INFERRED = {"run_id": S, "confidence": F, "evidence_path": S}

_NOTE_TARGETS = ["Merchant", "Customer", "Dispute", "Device", "Address", "Terminal", "Account"]
_ASSERT_TARGETS = ["Device", "IP", "Address", "PurchaseOrder", "Transaction", "Phone", "Shipment"]


def _pairs(srcs: list[str], dsts: list[str]) -> list[tuple[str, str]]:
    return [(s, d) for s in srcs for d in dsts]


EDGES: dict[str, dict] = {
    # Identity
    "HOLDS": {
        "pairs": [("Customer", "Account"), ("Customer", "MerchantAccount")],
        "props": {"role": S, **VALID},
    },
    "ISSUED_ON": {"pairs": [("Card", "Account")], "props": {}},
    "CARRIES": {"pairs": [("Customer", "Device")], "props": {}},
    "TOKENIZED_AS": {"pairs": [("Card", "Token")], "props": {}},
    "BOUND_TO_DEVICE": {"pairs": [("Token", "Device")], "props": {}},
    "LIVES_AT": {"pairs": [("Customer", "Address")], "props": VALID},
    "WORKS_AT": {"pairs": [("Customer", "Address")], "props": {}},
    "HAS_PHONE": {"pairs": [("Customer", "Phone")], "props": VALID},
    "HAS_EMAIL": {"pairs": [("Customer", "Email")], "props": {}},
    "LOGGED_IN_FROM": {"pairs": [("Customer", "Device")], "props": {"ts": S, "ip": S}},
    "MERCHANT_LOGIN_FROM": {"pairs": [("MerchantAccount", "IP")], "props": {"ts": S}},
    # Commerce
    "PAID_WITH": {
        "pairs": [("Transaction", "Card"), ("Transaction", "Token"), ("Authorization", "Card")],
        "props": {},
    },
    "AT_MERCHANT": {
        "pairs": [
            ("Transaction", "Merchant"),
            ("MerchantAccount", "Merchant"),
            ("Terminal", "Merchant"),
        ],
        "props": {},
    },
    "VIA_TERMINAL": {"pairs": [("Transaction", "Terminal")], "props": {}},
    "CLEARS": {"pairs": [("Transaction", "Authorization")], "props": {"seq": N}},
    "FOR_ORDER": {"pairs": [("Transaction", "PurchaseOrder")], "props": {}},
    "SHIPPED_AS": {"pairs": [("PurchaseOrder", "Shipment")], "props": {}},
    "DELIVERED_TO": {"pairs": [("Shipment", "Address")], "props": {"pod": S, "signer": S}},
    "REFUNDS": {"pairs": [("Transaction", "Transaction")], "props": {}},
    "FROM_DEVICE": {"pairs": [("Transaction", "Device"), ("PurchaseOrder", "Device")], "props": {}},
    "FROM_IP": {"pairs": [("Transaction", "IP"), ("PurchaseOrder", "IP")], "props": {}},
    "DESCRIBES": {
        "pairs": [("Descriptor", "Merchant"), ("Descriptor", "Transaction")],
        "props": VALID,
    },
    "SUB_MERCHANT_OF": {
        "pairs": [("Merchant", "Merchant"), ("Descriptor", "Merchant")],
        "props": {},
    },
    "ACTING_FOR": {
        "pairs": [("Token", "AgentProvider"), ("AgentProvider", "Customer")],
        "props": {},
    },
    "AUTHORIZED_BY_MANDATE": {
        "pairs": [("Transaction", "Mandate"), ("Mandate", "AgentProvider")],
        "props": {},
    },
    # Case
    "FILED_BY": {"pairs": [("Dispute", "Customer")], "props": {}},
    "DISPUTES": {"pairs": [("Dispute", "Transaction")], "props": {"amount": F}},
    "RELATED_TO": {"pairs": [("Dispute", "Dispute"), ("Dispute", "PurchaseOrder")], "props": {}},
    "HAS_EVIDENCE": {
        "pairs": [("Dispute", "EvidenceItem"), ("Dispute", "Communication")],
        "props": {},
    },
    "ASSERTS": {"pairs": _pairs(["EvidenceItem"], _ASSERT_TARGETS), "props": {}},
    "REQUESTED": {"pairs": [("Dispute", "EvidenceRequest")], "props": {"requested_at": S}},
    "TRIGGERED_BY": {"pairs": [("AccountEvent", "Device"), ("AccountEvent", "IP")], "props": {}},
    "CHANGED_PHONE_TO": {"pairs": [("AccountEvent", "Phone")], "props": {}},
    # Written by agents (or the generator for pre-existing notes), so they carry provenance.
    "ABOUT": {
        "pairs": [("AccountEvent", "Account")]
        + _pairs(["MemoryNote", "Finding"], _NOTE_TARGETS + ["Transaction"]),
        "props": INFERRED,
    },
    "SUPPORTS": {
        "pairs": _pairs(["Finding"], ["Finding", "MemoryNote", "Dispute", "Transaction"]),
        "props": INFERRED,
    },
    "CONTRADICTS": {
        "pairs": _pairs(["Finding"], ["Finding", "MemoryNote", "Dispute", "Transaction"]),
        "props": INFERRED,
    },
    "SAME_ACTOR": {
        "pairs": [("Customer", "Customer"), ("Account", "Account"), ("Device", "Customer")],
        "props": INFERRED,
    },
    "COMPROMISED_AT": {"pairs": [("Card", "Terminal"), ("Card", "Merchant")], "props": INFERRED},
}
