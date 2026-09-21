"""Seeded background world with realistic identity sharing, commerce, and ordinary disputes."""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import date, datetime, timedelta

from graph_builder import Graph

_START = date(2026, 3, 1)
_FIRST = ("Avery", "Blake", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper")
_LAST = ("Chen", "Garcia", "Johnson", "Khan", "Lim", "Martin", "Ng", "Patel")
_STREETS = ("Amber", "Cedar", "Harbour", "Juniper", "Orchard", "Pine", "River", "Willow")
_CITIES = ("Austin", "Chicago", "Denver", "Miami", "Portland", "Seattle")
_MERCHANTS = ("Market", "Books", "Travel", "Cafe", "Supply", "Digital", "Pharmacy", "Home")
_CLAIMS = ("fraud", "duplicate", "not_received", "refund", "descriptor", "not_as_described")


def build_world(
    seed: int = 42,
    *,
    customer_count: int = 2_500,
    merchant_count: int = 250,
    transaction_count: int = 50_000,
    dispute_count: int = 300,
) -> Graph:
    """Build deterministic background data.

    Counts may be reduced for tests, but not below full ontology coverage.
    """
    if customer_count < 20 or merchant_count < 5 or transaction_count < 38 or dispute_count < 11:
        raise ValueError("world counts are too small to cover the ontology")

    rng = random.Random(seed)
    g = Graph()
    identities = _identities(g, rng, customer_count)
    commerce = _commerce(g, merchant_count, identities)
    transactions = _transactions(g, rng, transaction_count, identities, commerce)
    _disputes(g, dispute_count, identities, transactions)
    _historical_findings(g, identities, commerce, transactions)
    return g


def _identities(g: Graph, rng: random.Random, count: int) -> dict:
    address_count = max(20, count * 3 // 5)
    device_count = max(20, count * 4 // 5)
    ip_count = max(12, count // 3)
    phone_count = max(20, count * 9 // 10)

    addresses = []
    for i in range(address_count):
        household = i // 4
        address_id = _id("ADR", i)
        addresses.append(address_id)
        g.node(
            "Address",
            address_id,
            street=f"{100 + household} {_STREETS[household % len(_STREETS)]} Street",
            unit=f"{i % 4 + 1}{chr(65 + household % 4)}",
            city=_CITIES[household % len(_CITIES)],
            postcode=f"{10000 + household % 89999:05d}",
        )

    devices = []
    for i in range(device_count):
        device_id = _id("DEV", i)
        devices.append(device_id)
        g.node(
            "Device",
            device_id,
            kind=("phone", "laptop", "tablet")[i % 3],
            fingerprint=f"fp-{rng.getrandbits(64):016x}",
        )

    ips = []
    for i in range(ip_count):
        ip_id = _id("IP", i)
        ips.append(ip_id)
        kind = "office" if i % 11 == 0 else "cgnat" if i % 3 == 0 else "residential"
        g.node("IP", ip_id, address=f"10.{i // 65025}.{i // 255 % 255}.{i % 255}", kind=kind)

    phones = []
    for i in range(phone_count):
        phone_id = _id("PHN", i)
        phones.append(phone_id)
        g.node("Phone", phone_id, number=f"+1-555-{i // 10000:03d}-{i % 10000:04d}")

    customers, accounts, cards = [], [], []
    for i in range(count):
        customer_id, account_id, card_id, email_id = (
            _id("CUS", i),
            _id("ACC", i),
            _id("CRD", i),
            _id("EML", i),
        )
        customers.append(customer_id)
        accounts.append(account_id)
        cards.append(card_id)
        opened = (_START - timedelta(days=400 + i % 1_200)).isoformat()
        g.node(
            "Customer",
            customer_id,
            name=f"{_FIRST[i % len(_FIRST)]} {_LAST[(i // len(_FIRST)) % len(_LAST)]}",
            segment=("consumer", "student", "small_business")[i % 3],
            opened_at=opened,
        )
        g.node(
            "Account",
            account_id,
            kind="credit" if i % 4 else "debit",
            status="open",
            opened_at=opened,
            credit_limit=float(1_000 + i % 20 * 500),
        )
        g.node(
            "Card",
            card_id,
            last4=f"{i % 10000:04d}",
            network="visa",
            status="active",
            issued_at=(_START - timedelta(days=180 + i % 500)).isoformat(),
        )
        g.node("Email", email_id, address=f"customer{i}@example.test")
        address_id = addresses[(i // 2) % address_count]
        device_id = devices[(i // 2) % device_count]
        phone_id = phones[i % phone_count]
        ip_id = ips[(i // 6) % ip_count]
        g.edge("HOLDS", customer_id, account_id, role="primary", valid_from=opened, valid_to="")
        g.edge("ISSUED_ON", card_id, account_id)
        g.edge("CARRIES", customer_id, device_id)
        g.edge("LIVES_AT", customer_id, address_id, valid_from="2024-01-01", valid_to="")
        g.edge("HAS_PHONE", customer_id, phone_id, valid_from="2025-01-01", valid_to="")
        g.edge("HAS_EMAIL", customer_id, email_id)
        g.edge(
            "LOGGED_IN_FROM",
            customer_id,
            device_id,
            ts=_timestamp(i),
            ip=g.nodes[ip_id]["props"]["address"],
        )
        if i % 8 == 0:
            g.edge("WORKS_AT", customer_id, addresses[(i + 7) % address_count])

    for i in range(0, count - 1, 10):
        g.edge(
            "HOLDS",
            customers[i + 1],
            accounts[i],
            role="authorized",
            valid_from="2025-06-01",
            valid_to="",
        )

    # A recycled number whose ownership periods do not overlap.
    recycled = phones[-1]
    g.edge("HAS_PHONE", customers[0], recycled, valid_from="2024-01-01", valid_to="2025-05-31")
    g.edge("HAS_PHONE", customers[1], recycled, valid_from="2025-06-01", valid_to="")

    tokens = []
    for i in range(max(5, count // 4)):
        token_id = _id("TOK", i)
        tokens.append(token_id)
        g.node(
            "Token",
            token_id,
            wallet=("apple", "google", "merchant")[i % 3],
            created_at="2025-01-01",
        )
        g.edge("TOKENIZED_AS", cards[i % count], token_id)
        g.edge("BOUND_TO_DEVICE", token_id, devices[(i // 2) % device_count])

    return {
        "customers": customers,
        "accounts": accounts,
        "cards": cards,
        "tokens": tokens,
        "devices": devices,
        "ips": ips,
        "phones": phones,
        "addresses": addresses,
    }


def _commerce(g: Graph, count: int, identities: dict) -> dict:
    merchants, terminals, descriptors = [], [], []
    for i in range(count):
        merchant_id = _id("MER", i)
        merchants.append(merchant_id)
        g.node(
            "Merchant",
            merchant_id,
            name=f"{_LAST[i % len(_LAST)]} {_MERCHANTS[i % len(_MERCHANTS)]} {i:03d}",
            mcc=f"{5000 + i % 800:04d}",
            kind="marketplace" if i < 2 else "retail",
            country="US",
        )
        descriptor_id = _id("DSC", i)
        descriptors.append(descriptor_id)
        g.node(
            "Descriptor", descriptor_id, text=f"{_MERCHANTS[i % len(_MERCHANTS)].upper()}*{i:04d}"
        )
        g.edge("DESCRIBES", descriptor_id, merchant_id, valid_from="2025-01-01", valid_to="")
        account_id = _id("MAC", i)
        g.node("MerchantAccount", account_id, handle=f"merchant-{i}", created_at="2024-01-01")
        owner = identities["customers"][(i * 13) % len(identities["customers"])]
        g.edge("HOLDS", owner, account_id, role="owner", valid_from="2024-01-01", valid_to="")
        g.edge("AT_MERCHANT", account_id, merchant_id)
        g.edge(
            "MERCHANT_LOGIN_FROM",
            account_id,
            identities["ips"][i % len(identities["ips"])],
            ts=_timestamp(i),
        )
        for j in range(2):
            terminal_id = _id("TRM", i * 2 + j)
            terminals.append(terminal_id)
            g.node(
                "Terminal",
                terminal_id,
                kind="physical" if j == 0 else "online",
                location=f"site-{i}-{j}",
            )
            g.edge("AT_MERCHANT", terminal_id, merchant_id)
        if i >= 2 and i % 5 == 0:
            g.edge("SUB_MERCHANT_OF", merchant_id, merchants[i % 2])

    alias = _id("DSC", count)
    g.node("Descriptor", alias, text="MARKETPLACE*PARTNER")
    g.edge("DESCRIBES", alias, merchants[2], valid_from="2025-01-01", valid_to="")
    g.edge("SUB_MERCHANT_OF", alias, merchants[0])

    providers, mandates = [], []
    for i in range(3):
        provider_id = _id("AGP", i)
        providers.append(provider_id)
        g.node("AgentProvider", provider_id, name=f"Booking Agent {i}", kind="travel")
        g.edge("ACTING_FOR", provider_id, identities["customers"][i])
    for i in range(5):
        mandate_id = _id("MDT", i)
        mandates.append(mandate_id)
        g.node(
            "Mandate",
            mandate_id,
            scope="travel_booking",
            max_amount=float(500 + i * 250),
            valid_from="2025-01-01",
            valid_to="2027-01-01",
        )
        g.edge("AUTHORIZED_BY_MANDATE", mandate_id, providers[i % len(providers)])
        g.edge("ACTING_FOR", identities["tokens"][i], providers[i % len(providers)])

    return {
        "merchants": merchants,
        "terminals": terminals,
        "descriptors": descriptors,
        "mandates": mandates,
    }


def _transactions(
    g: Graph, rng: random.Random, count: int, identities: dict, commerce: dict
) -> list[dict]:
    transactions: list[dict] = []
    merchant_count = len(commerce["merchants"])
    for i in range(count):
        customer_index = rng.randrange(len(identities["customers"]))
        merchant_index = rng.randrange(merchant_count)
        txn_id, auth_id = _id("TXN", i), _id("AUT", i)
        ts = _timestamp(rng.randrange(184 * 24), hours=True)
        amount = round(4 + rng.random() * 496, 2)
        refund = i > 0 and i % 37 == 0
        channel = "ecommerce" if i % 3 == 0 else "card_present"
        card_id = identities["cards"][customer_index]
        device_id = identities["devices"][(customer_index // 2) % len(identities["devices"])]
        ip_id = identities["ips"][(customer_index // 6) % len(identities["ips"])]
        merchant_id = commerce["merchants"][merchant_index]
        terminal_id = commerce["terminals"][merchant_index * 2 + (channel == "ecommerce")]
        g.node(
            "Transaction",
            txn_id,
            ts=ts,
            amount=-amount if refund else amount,
            currency="USD",
            kind="refund" if refund else "purchase",
            channel=channel,
            status="posted",
        )
        g.node("Authorization", auth_id, ts=ts, amount=amount, currency="USD", status="approved")
        payment = (
            identities["tokens"][customer_index % len(identities["tokens"])]
            if i % 7 == 0
            else card_id
        )
        g.edge("PAID_WITH", txn_id, payment)
        g.edge("PAID_WITH", auth_id, card_id)
        g.edge("AT_MERCHANT", txn_id, merchant_id)
        g.edge("VIA_TERMINAL", txn_id, terminal_id)
        g.edge("CLEARS", txn_id, auth_id, seq=1)
        g.edge("FROM_DEVICE", txn_id, device_id)
        g.edge("FROM_IP", txn_id, ip_id)
        descriptor = commerce["descriptors"][merchant_index]
        g.edge("DESCRIBES", descriptor, txn_id, valid_from="2025-01-01", valid_to="")
        if refund:
            g.edge("REFUNDS", txn_id, transactions[-1]["id"])
        order_id = ""
        if channel == "ecommerce":
            order_id, shipment_id = _id("ORD", i), _id("SHP", i)
            g.node(
                "PurchaseOrder",
                order_id,
                ts=ts,
                total=amount,
                currency="USD",
                items=f"item-{i % 50}",
            )
            g.node(
                "Shipment",
                shipment_id,
                carrier=("DHL", "UPS", "USPS")[i % 3],
                tracking=f"TRACK{i:010d}",
                shipped_at=ts[:10],
            )
            g.edge("FOR_ORDER", txn_id, order_id)
            g.edge("FROM_DEVICE", order_id, device_id)
            g.edge("FROM_IP", order_id, ip_id)
            g.edge("SHIPPED_AS", order_id, shipment_id)
            g.edge(
                "DELIVERED_TO",
                shipment_id,
                identities["addresses"][(customer_index // 2) % len(identities["addresses"])],
                pod="photo" if i % 4 else "none",
                signer="resident" if i % 5 else "",
            )
        if i % 997 == 0:
            g.edge(
                "AUTHORIZED_BY_MANDATE", txn_id, commerce["mandates"][i % len(commerce["mandates"])]
            )
        transactions.append(
            {
                "id": txn_id,
                "customer": identities["customers"][customer_index],
                "account": identities["accounts"][customer_index],
                "device": device_id,
                "ip": ip_id,
                "merchant": merchant_id,
                "order": order_id,
                "amount": amount,
                "ts": ts,
            }
        )
    return transactions


def _disputes(
    g: Graph,
    count: int,
    identities: dict,
    transactions: list[dict],
) -> None:
    for i in range(count):
        txn = transactions[(i * 137 + 11) % len(transactions)]
        dispute_id, evidence_id = _id("DSP", i), _id("EVI", i)
        filed = (_START + timedelta(days=184 + i % 30)).isoformat()
        claim = _CLAIMS[i % len(_CLAIMS)]
        g.node(
            "Dispute",
            dispute_id,
            filed_at=filed,
            claim_type=claim,
            amount=txn["amount"],
            intake=f"Customer reports {claim.replace('_', ' ')} for a ${txn['amount']:.2f} charge.",
            status="closed" if i % 4 else "open",
        )
        g.edge("FILED_BY", dispute_id, txn["customer"])
        g.edge("DISPUTES", dispute_id, txn["id"], amount=txn["amount"])
        g.node(
            "EvidenceItem",
            evidence_id,
            kind="merchant_record",
            source="merchant",
            text=f"Merchant record for order {txn['order'] or 'not supplied'}",
            ts=txn["ts"],
        )
        g.edge("HAS_EVIDENCE", dispute_id, evidence_id)
        assert_target = (txn["device"], txn["ip"], txn["id"], txn["order"] or txn["id"])[i % 4]
        g.edge("ASSERTS", evidence_id, assert_target)
        if i % 2 == 0:
            communication_id = _id("COM", i)
            g.node(
                "Communication",
                communication_id,
                channel="secure_message",
                ts=txn["ts"],
                sender="cardholder",
                text="I do not recognize this transaction."
                if claim == "fraud"
                else "Please investigate this purchase.",
            )
            g.edge("HAS_EVIDENCE", dispute_id, communication_id)
        if i % 3 == 0:
            request_id = _id("ERQ", i)
            status = ("responded", "no_response", "pending")[(i // 3) % 3]
            deadline = (_START + timedelta(days=210 + i)).isoformat()
            g.node(
                "EvidenceRequest",
                request_id,
                party="merchant",
                status=status,
                deadline=deadline,
                deadline_passed=status != "pending",
                responded_at=deadline if status == "responded" else "",
            )
            g.edge("REQUESTED", dispute_id, request_id, requested_at=filed)
        if i and i % 10 == 0:
            g.edge("RELATED_TO", dispute_id, _id("DSP", i - 1))
        if i % 4 == 0:
            event_id = _id("AEV", i)
            g.node(
                "AccountEvent",
                event_id,
                kind="phone_change",
                ts=txn["ts"],
                detail="self-service profile update",
            )
            g.edge(
                "ABOUT",
                event_id,
                txn["account"],
                run_id="seed",
                confidence=1.0,
                evidence_path=event_id,
            )
            g.edge("TRIGGERED_BY", event_id, txn["device"] if i % 8 else txn["ip"])
            g.edge(
                "CHANGED_PHONE_TO",
                event_id,
                identities["phones"][(i + 3) % len(identities["phones"])],
            )


def _historical_findings(
    g: Graph, identities: dict, commerce: dict, transactions: list[dict]
) -> None:
    for i in range(3):
        note_id, finding_id = _id("MEM", i), _id("FND", i)
        run_id = f"historical-{i}"
        path = f"{transactions[i]['id']}>{transactions[i]['merchant']}"
        g.node(
            "MemoryNote",
            note_id,
            text="Historical merchant pattern; revalidate before use.",
            status="active",
            created_at="2026-01-01",
            run_id=run_id,
            confidence=0.6,
        )
        g.node(
            "Finding",
            finding_id,
            text="Shared identifier observed in historical review.",
            kind="pattern",
            run_id=run_id,
            confidence=0.7,
            evidence_path=path,
        )
        provenance = {"run_id": run_id, "confidence": 0.7, "evidence_path": path}
        g.edge("ABOUT", note_id, commerce["merchants"][i], **provenance)
        g.edge("ABOUT", finding_id, transactions[i]["id"], **provenance)
        g.edge("SUPPORTS", finding_id, _id("DSP", i), **provenance)
        g.edge("CONTRADICTS", finding_id, note_id, **provenance)
    provenance = {"run_id": "historical-link", "confidence": 0.55, "evidence_path": "shared-device"}
    g.edge("SAME_ACTOR", identities["customers"][0], identities["customers"][1], **provenance)
    g.edge("COMPROMISED_AT", identities["cards"][0], commerce["terminals"][0], **provenance)


def stats(graph: Graph) -> dict[str, dict[str, int]]:
    """Print and return counts by node label and edge type."""
    result = {
        "nodes": dict(sorted(Counter(n["label"] for n in graph.nodes.values()).items())),
        "edges": dict(sorted(Counter(e["type"] for e in graph.edges).items())),
    }
    print(f"nodes {json.dumps(result['nodes'], sort_keys=True)}")
    print(f"edges {json.dumps(result['edges'], sort_keys=True)}")
    return result


def _id(prefix: str, index: int) -> str:
    return f"{prefix}-{index + 1:07d}"


def _timestamp(offset: int, *, hours: bool = False) -> str:
    moment = datetime.combine(_START, datetime.min.time()) + (
        timedelta(hours=offset) if hours else timedelta(days=offset % 184, hours=offset % 24)
    )
    return moment.isoformat(timespec="seconds") + "Z"
