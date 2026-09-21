"""C11: account-takeover activity across forty accounts converges on one drop address."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    drop, device, ip, phone = "ADR-C11-DROP", "DEV-C11-NEW", "IP-C11-VPN", "PHN-C11-NEW"
    merchant, memory = "MER-C11-AUDIO", "MEM-C11-FRIENDLY"
    hero_dispute, hero_txn = "DSP-2026-90011", "TXN-C11-ATO-01"
    g.node(
        "Address",
        drop,
        street="88 Wharfside Avenue",
        unit="2",
        city="Jersey City",
        postcode="07302",
    )
    g.node("Device", device, kind="browser", fingerprint="c11-new-device-cluster")
    g.node("IP", ip, address="203.0.113.58", kind="hosting_vpn")
    g.node("Phone", phone, number="+1-929-555-0197")
    g.node("Merchant", merchant, name="Orbital Audio", mcc="5732", kind="ecommerce", country="US")
    for i in range(40):
        n = i + 1
        customer, account, card = f"CUS-C11-{n:02d}", f"ACC-C11-{n:02d}", f"CRD-C11-{n:02d}"
        event, txn, order, shipment = (
            f"AEV-C11-{n:02d}",
            f"TXN-C11-ATO-{n:02d}",
            f"ORD-C11-{n:02d}",
            f"SHP-C11-{n:02d}",
        )
        dispute = hero_dispute if i == 0 else f"DSP-2026-911{n:02d}"
        amount = 1389.0 if i == 0 else float(420 + n * 19)
        g.node(
            "Customer",
            customer,
            name=f"ATO claimant {n}",
            segment="consumer",
            opened_at="2019-01-01",
        )
        g.node(
            "Account",
            account,
            kind="credit",
            status="open",
            opened_at="2019-01-01",
            credit_limit=10000.0,
        )
        g.node(
            "Card",
            card,
            last4=f"11{n:02d}",
            network="visa",
            status="active",
            issued_at="2025-01-01",
        )
        g.edge("HOLDS", customer, account, role="primary", valid_from="2019-01-01", valid_to="")
        g.edge("ISSUED_ON", card, account)
        g.node(
            "AccountEvent",
            event,
            kind="phone_change",
            ts=f"2026-10-{10 + i % 5:02d}T01:{i:02d}:00Z",
            detail="self-service change followed by password reset",
        )
        g.edge(
            "ABOUT",
            event,
            account,
            run_id="seed-c11",
            confidence=1.0,
            evidence_path=f"{event}>{account}",
        )
        g.edge("CHANGED_PHONE_TO", event, phone)
        g.edge("TRIGGERED_BY", event, device)
        g.node(
            "Transaction",
            txn,
            ts=f"2026-10-{14 + i % 5:02d}T02:{i:02d}:00Z",
            amount=amount,
            currency="USD",
            kind="purchase",
            channel="ecommerce",
            status="posted",
        )
        g.edge("PAID_WITH", txn, card)
        g.edge("AT_MERCHANT", txn, merchant)
        g.edge("FROM_DEVICE", txn, device)
        g.edge("FROM_IP", txn, ip)
        g.node(
            "PurchaseOrder",
            order,
            ts=f"2026-10-{14 + i % 5:02d}T02:{i:02d}:00Z",
            total=amount,
            currency="USD",
            items="high-value electronics",
        )
        g.edge("FOR_ORDER", txn, order)
        g.edge("FROM_DEVICE", order, device)
        g.edge("FROM_IP", order, ip)
        g.node(
            "Shipment",
            shipment,
            carrier="Swiftline",
            tracking=f"SW-C11-{n:04d}",
            shipped_at=f"2026-10-{15 + i % 5:02d}",
        )
        g.edge("SHIPPED_AS", order, shipment)
        g.edge("DELIVERED_TO", shipment, drop, pod="mailroom scan", signer="unknown")
        intake = (
            "I did not authorize this online purchase and I was locked out after my phone "
            "stopped receiving service."
        )
        g.node(
            "Dispute",
            dispute,
            filed_at=f"2026-10-{16 + i % 5:02d}",
            claim_type="fraud",
            amount=amount,
            intake=intake,
            status="open" if i < 8 else "closed",
        )
        g.edge("FILED_BY", dispute, customer)
        g.edge("DISPUTES", dispute, txn, amount=amount)
    g.node(
        "MemoryNote",
        memory,
        text="Prior review treated the customer's matching merchant login as friendly fraud.",
        status="active",
        created_at="2026-06-02",
        run_id="historical-c11",
        confidence=0.62,
    )
    g.edge(
        "ABOUT",
        memory,
        hero_dispute,
        run_id="historical-c11",
        confidence=0.62,
        evidence_path=f"{memory}>{hero_dispute}",
    )
    # A real prior purchase creates the merchant's persuasive returning-customer story.
    home, old_device, prior = "ADR-C11-HOME", "DEV-C11-OLD", "TXN-C11-PRIOR"
    g.node(
        "Address",
        home,
        street="311 Carroll Bend Street",
        unit="11C",
        city="Brooklyn",
        postcode="11231",
    )
    g.node("Device", old_device, kind="phone", fingerprint="c11-known-phone")
    g.edge("LIVES_AT", "CUS-C11-01", home, valid_from="2020-01-01", valid_to="")
    g.edge("CARRIES", "CUS-C11-01", old_device)
    g.node(
        "Transaction",
        prior,
        ts="2026-04-22T20:40:00Z",
        amount=149.0,
        currency="USD",
        kind="purchase",
        channel="ecommerce",
        status="posted",
    )
    g.edge("PAID_WITH", prior, "CRD-C11-01")
    g.edge("AT_MERCHANT", prior, merchant)
    g.edge("FROM_DEVICE", prior, old_device)
    return {
        "case_id": hero_dispute,
        "code": "C11",
        "title": "Takeover in a Friendly Mask",
        "intake": (
            "I did not authorize the $1,389 Orbital Audio purchase and I was locked out after my "
            "phone stopped receiving service."
        ),
        "misleading_surface": (
            "A prior legitimate merchant purchase and a stale friendly-fraud note conceal a "
            "forty-account takeover cluster."
        ),
        "expected": {
            "verdict": "accepted",
            "claim_family": "fraud_cnp_account_takeover",
            "transactions": [
                transaction_expected(
                    hero_txn, "accepted", 1389.0, 1389.0, "file_dispute", "Visa 10.4"
                )
            ],
            "account_actions": [
                "card_reissue",
                "secure_online_banking",
                "revert_phone_change",
                "retract_memory_note",
                "watchlist_drop_address",
            ],
        },
        "solution_node_ids": [
            hero_dispute,
            hero_txn,
            "CUS-C11-01",
            "ACC-C11-01",
            "AEV-C11-01",
            phone,
            device,
            ip,
            "ORD-C11-01",
            "SHP-C11-01",
            drop,
            memory,
            prior,
            old_device,
        ],
        "proof_patterns": [
            {
                "name": "phone change to shared takeover infrastructure",
                "cypher": (
                    "MATCH (d:Dispute)-[:FILED_BY]->(c:Customer)-[:HOLDS]->(a:Account)"
                    "<-[:ABOUT]-(e:AccountEvent)-[:CHANGED_PHONE_TO]->(p:Phone), "
                    "(e)-[:TRIGGERED_BY]->(dev:Device), "
                    "(d)-[:DISPUTES]->(t:Transaction)-[:FROM_DEVICE]->(dev), "
                    "(t)-[:FROM_IP]->(ip:IP) WHERE p.id = 'PHN-C11-NEW' "
                    "RETURN d, c, a, e, p, dev, t, ip"
                ),
                "min_rows": 40,
            },
            {
                "name": "forty orders reach one drop address",
                "cypher": (
                    "MATCH (d:Dispute)-[:DISPUTES]->(t:Transaction)-[:FOR_ORDER]->"
                    "(o:PurchaseOrder)-[:SHIPPED_AS]->(s:Shipment)-[:DELIVERED_TO]->"
                    "(a:Address {id: 'ADR-C11-DROP'}) RETURN d, t, o, s, a"
                ),
                "min_rows": 40,
            },
        ],
        "decoy_patterns": [
            {
                "name": "stale friendly-fraud note",
                "cypher": (
                    "MATCH (m:MemoryNote {id: 'MEM-C11-FRIENDLY'})-[:ABOUT]->"
                    "(d:Dispute {id: 'DSP-2026-90011'}) RETURN m, d"
                ),
                "why_irrelevant": (
                    "The historical inference predates and is contradicted by the phone-change, "
                    "new-device, VPN, and shared drop-address cluster."
                ),
            },
            {
                "name": "prior legitimate merchant purchase",
                "cypher": (
                    "MATCH (t:Transaction {id: 'TXN-C11-PRIOR'})-[:FROM_DEVICE]->(dev:Device), "
                    "(t)-[:AT_MERCHANT]->(m:Merchant {id: 'MER-C11-AUDIO'}) RETURN t, dev, m"
                ),
                "why_irrelevant": (
                    "It used the known device months earlier and does not connect to the new "
                    "takeover device or drop shipment."
                ),
            },
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 8,
            "entities": 168,
            "note": (
                "Correlate forty account changes with a new device and VPN, then traverse each "
                "order and shipment to the common drop while distinguishing the customer's older "
                "known device."
            ),
        },
    }
