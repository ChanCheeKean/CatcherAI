"""Seeded, dispute-only background: Card Members, Merchants and their policies, commerce, and
resolved past Disputes."""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import count
from pathlib import Path
from typing import NamedTuple

from graph_builder import Graph
from policies import Clause, PolicyDoc, add_to_graph, load_policies
from submissions import insert_submission

from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem

AMEX_MR = "POL-AMX-MR"
AMEX_CMA = "POL-AMX-CMA"
AMEX_OFFER = "POL-AMX-OFFER"
AMEX_PLAT_BEN = "POL-AMX-PLAT-BEN"
AMEX_PS_PART = "POL-AMX-PS-PART"
PLATINUM_STAYS = "PRG-PLAT"

_CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "policies"
_YEAR = date(2026, 1, 1)
_SECOND_VERSION = date(2026, 5, 1)  # background retailers' second returns policy applies from here

# (id, name, category, channel). The first six publish the corpus Merchant Policies.
_MERCHANTS = (
    ("MER-HGF", "Hearth & Grain Furniture", "furniture", "online"),
    ("MER-NWO", "Northwind Outfitters", "apparel", "online"),
    ("MER-HPH", "Harbor Point Hotel", "lodging", "in_person"),
    ("MER-STC", "StreamCo", "streaming", "online"),
    ("MER-WBV", "Willow Barn Venue", "events", "in_person"),
    ("MER-WBC", "Willow Barn Catering", "catering", "in_person"),
    ("MER-BG-0001", "Oakline Home", "furniture", "online"),
    ("MER-BG-0002", "Brightwater Sofa Co.", "furniture", "both"),
    ("MER-BG-0003", "Kestrel Design Studio", "furniture", "both"),
    ("MER-BG-0004", "Northwind Outdoor Supply", "apparel", "in_person"),
    ("MER-BG-0005", "Linen & Loom", "apparel", "online"),
    ("MER-BG-0006", "Cobalt Running", "apparel", "both"),
    ("MER-BG-0007", "Fernhill Tailors", "apparel", "in_person"),
    ("MER-BG-0008", "Harbor Point Inn", "lodging", "in_person"),
    ("MER-BG-0009", "The Aldergate Hotel", "lodging", "in_person"),
    ("MER-BG-0010", "Saltmarsh Resort", "lodging", "in_person"),
    ("MER-BG-0011", "Meridian Grand", "lodging", "in_person"),
    ("MER-BG-0012", "Copperleaf Suites", "lodging", "in_person"),
    ("MER-BG-0013", "Lakehouse Lodge", "lodging", "in_person"),
    ("MER-BG-0014", "Tunewell Music", "streaming", "online"),
    ("MER-BG-0015", "Lumen Fitness", "streaming", "online"),
    ("MER-BG-0016", "Pagecraft Books+", "streaming", "online"),
    ("MER-BG-0017", "Granary Hall", "events", "in_person"),
    ("MER-BG-0018", "Granary Kitchen", "catering", "in_person"),
    ("MER-BG-0019", "Riverside Pavilion", "events", "in_person"),
    ("MER-BG-0020", "Harbor Point Marina Grill", "dining", "in_person"),
    ("MER-BG-0021", "Saffron Table", "dining", "in_person"),
    ("MER-BG-0022", "Juniper & Rye", "dining", "in_person"),
    ("MER-BG-0023", "Osteria Lume", "dining", "in_person"),
    ("MER-BG-0024", "Blue Heron Cafe", "dining", "in_person"),
)
_NAMES = {m: name for m, name, _, _ in _MERCHANTS}
_CATEGORIES = {m: category for m, _, category, _ in _MERCHANTS}


def _merchants_in(*categories: str) -> list[str]:
    return [m for m, category in _CATEGORIES.items() if category in categories]


_AFFILIATES = (("MER-WBC", "MER-WBV"), ("MER-BG-0018", "MER-BG-0017"))
_PLATINUM_STAYS_HOTELS = (
    "MER-HPH",
    "MER-BG-0009",
    "MER-BG-0010",
    "MER-BG-0011",
    "MER-BG-0012",
    "MER-BG-0013",
)
# Lumen Fitness and Pagecraft Books+ both bill under their parent brand's descriptor.
_DESCRIPTORS = {
    "MER-STC": ("DSC-STC", "SC*DIGITAL SVCS"),
    "MER-BG-0014": ("DSC-BG-0001", "TUNEWELL*MUSIC"),
    "MER-BG-0015": ("DSC-BG-0002", "NVP*NOVAPLAY"),
    "MER-BG-0016": ("DSC-BG-0003", "NVP*NOVAPLAY"),
}
_PLANS = {
    "MER-STC": (("Individual", 12.99), ("Family", 22.99)),
    "MER-BG-0014": (("Solo", 10.99), ("Duo", 14.99)),
    "MER-BG-0015": (("Monthly", 19.99),),
    "MER-BG-0016": (("Reader", 8.99), ("Reader Plus", 13.99)),
}
# The corpus policy version each case Merchant's customers accept.
_CORPUS_TERMS = {
    "MER-HGF": "POL-HGF-CO-V4",
    "MER-NWO": "POL-NWO-SALE-V1",
    "MER-HPH": "POL-HPH-RES-V2",
    "MER-STC": "POL-STC-SUB-V3",
    "MER-WBV": "POL-WBV-CONTRACT-V2",
    "MER-WBC": "POL-WBC-CATERING-V1",
}
_RETURNS = (
    (
        "Returns window",
        "Items may be returned within {days} days of delivery for a refund to the original card.",
    ),
)
# category: (kind, title, clauses). Background Merchant Policies are generated from these.
_TEMPLATES = {
    "furniture": (
        "returns",
        "Returns Policy",
        _RETURNS
        + (
            (
                "Final sale",
                "Custom pieces, including Customer's Own Material (COM) and made-to-measure "
                "items, are final sale and cannot be returned.",
            ),
            ("Return shipping", "Return shipping is {shipping}."),
        ),
    ),
    "apparel": (
        "returns",
        "Returns Policy",
        _RETURNS
        + (
            ("Final sale", "Monogrammed and tailored-to-measure items are final sale."),
            ("Exchanges", "Unworn items may be exchanged for another size at no charge."),
        ),
    ),
    "lodging": (
        "reservation_terms",
        "Reservation Terms",
        (
            (
                "Confirmed rate",
                "The rate on your booking confirmation is the rate charged for the stay.",
            ),
            (
                "Cancellation",
                "Bookings may be cancelled free of charge up to {hours} hours before "
                "arrival; later cancellations are charged one night.",
            ),
        ),
    ),
    "streaming": (
        "subscription_terms",
        "Subscription Terms",
        (
            (
                "Recurring billing",
                "Plans renew monthly until cancelled, at the price shown at sign-up.",
            ),
            (
                "Cancelling",
                "Cancel any time in your account settings; billing stops at the end of the "
                "current period.",
            ),
        ),
    ),
    "events": (
        "event_contract",
        "Event Hire Contract",
        (
            (
                "Payment schedule",
                "A deposit is due on signing; the balance is due before the event.",
            ),
            ("Payment methods", "Each installment may be paid by card, bank transfer or cheque."),
            ("Cancellation", "The deposit is non-refundable once the date is confirmed."),
        ),
    ),
    "catering": (
        "event_contract",
        "Catering Terms",
        (
            ("Payment", "Catering is invoiced separately from any venue hire."),
            ("Payment methods", "Each installment may be paid by card, bank transfer or cheque."),
        ),
    ),
    "dining": (
        "reservation_terms",
        "Booking Terms",
        (
            ("Large parties", "Parties of eight or more are charged a {service}% service charge."),
            (
                "No-shows",
                "Reservations not cancelled by the day before may be charged $25 per guest.",
            ),
        ),
    ),
}
# category: (name, price, standard options, custom options)
_CATALOG = {
    "furniture": (
        (
            "Harlow sectional",
            2800.0,
            "Sage linen; Oat linen; Charcoal velvet",
            "Customer's Own Material (COM); made to measure",
        ),
        ("Birch armchair", 950.0, "Oat linen; Rust boucle", "Customer's Own Material (COM)"),
        ("Mira dining table", 1600.0, "Natural oak; Smoked oak", "made to measure"),
        ("Tallis bookcase", 700.0, "Natural oak; White", ""),
        ("Wren bed frame", 1200.0, "Queen; King", ""),
        ("Oona ottoman", 380.0, "Oat linen; Sage linen", "Customer's Own Material (COM)"),
    ),
    "apparel": (
        ("Storm shell jacket", 260.0, "S; M; L; XL", ""),
        ("Merino crew", 95.0, "S; M; L", "Monogramming"),
        ("Trail runner", 140.0, "Size 8; Size 9; Size 10; Size 11", ""),
        ("Wool overcoat", 420.0, "38; 40; 42", "Tailored to measure"),
        ("Canvas tote", 45.0, "Natural; Navy", "Monogramming"),
    ),
}
_INVOICES = {
    "events": ("Wedding venue hire", "Corporate dinner venue hire", "Birthday party venue hire"),
    "catering": ("Wedding catering, 80 guests", "Corporate lunch catering, 40 guests"),
}
_FIRST = (
    "Avery",
    "Blake",
    "Camila",
    "Darius",
    "Elif",
    "Farah",
    "Gideon",
    "Hana",
    "Ines",
    "Jamal",
    "Keiko",
    "Liam",
    "Mateo",
    "Nadia",
    "Owen",
    "Priyanka",
    "Quinn",
    "Rosa",
    "Samir",
    "Tessa",
    "Umar",
    "Vera",
    "Wes",
    "Yara",
)
_LAST = (
    "Abbott",
    "Brennan",
    "Castillo",
    "Dimitriou",
    "Eriksen",
    "Fontaine",
    "Gallagher",
    "Haddad",
    "Iwasaki",
    "Jovanovic",
    "Kowalski",
    "Lindgren",
    "Mbeki",
    "Novak",
    "Oyelaran",
    "Pereira",
    "Rahman",
    "Sandoval",
    "Takahashi",
    "Whitfield",
)
_PRODUCTS = ("Platinum", "Gold", "Green", "Blue Cash")
_PRODUCT_PAIRS = (
    ("Platinum", "Gold"),
    ("Gold", "Blue Cash"),
    ("Platinum", "Blue Cash"),
    ("Green", "Gold"),
)
_RETURN_METHODS = ("carrier pickup", "customer freight", "prepaid label", "in-store drop-off")

# Resolved past Disputes, one row per Dispute Category (as a comment): how many, which sales they
# challenge, the Card Member's words, the Merchant's evidence, and the possible (verdict,
# Merchant statement) outcomes; an empty statement means no Merchant Submission.
_PAST = (
    {  # RET
        "count": 6,
        "pool": "refused",
        "intake": "I sent {subject} back to {shown} and they refused to refund ${amount}.",
        "evidence": ("return_log", "Return of {subject} refused: made to order, final sale."),
        "outcomes": (
            (
                "rejected",
                "The item was a custom order, final sale under the terms accepted at purchase.",
            ),
            ("accepted", ""),
        ),
    },
    {  # NRC
        "count": 6,
        "pool": "retail",
        "intake": "I paid {shown} ${amount} for {subject} and it never arrived.",
        "evidence": ("delivery_proof", "Carrier scan: {subject} delivered and signed for."),
        "outcomes": (
            ("accepted", ""),
            ("rejected", "Carrier proof of delivery shows the order was delivered."),
        ),
    },
    {  # DMG
        "count": 5,
        "pool": "furniture",
        "intake": "{shown} delivered {subject} damaged.",
        "evidence": ("photo_report", "Delivery photos of {subject}: minor scuff on one side."),
        "outcomes": (
            ("partially_accepted", "The damage is cosmetic; we offered part of the price back."),
            ("accepted", ""),
        ),
    },
    {  # OVR
        "count": 7,
        "pool": "lodging",
        "share": 0.2,
        "intake": "{shown} charged me ${amount} more than the rate I booked for {subject}.",
        "evidence": ("folio", "Folio for {subject}: charged at the rate on the confirmation."),
        "outcomes": (
            ("accepted", ""),
            ("rejected", "The amount charged matches the rate on the booking confirmation."),
        ),
    },
    {  # CNC
        "count": 5,
        "pool": "lodging",
        "intake": "I cancelled {subject} with {shown} but was still charged ${amount}.",
        "evidence": (
            "reservation_record",
            "Reservation for {subject} cancelled after the free-cancellation cut-off.",
        ),
        "outcomes": (
            (
                "rejected",
                "The booking was cancelled after the free-cancellation cut-off in the "
                "reservation terms.",
            ),
            ("accepted", ""),
        ),
    },
    {  # DSS
        "count": 8,
        "pool": "service",
        "intake": "I paid {shown} ${amount} for {subject} and it was not as described.",
        "evidence": ("itemised_receipt", "Itemised record for {subject}: provided as ordered."),
        "outcomes": (
            ("rejected", "The service was provided as ordered."),
            ("goodwill_credit", "The service was provided as ordered."),
        ),
    },
    {  # DUP
        "count": 5,
        "pool": "dining",
        "duplicate": True,
        "intake": "{shown} charged me twice, ${amount} each, for {subject}.",
        "outcomes": (("accepted", ""),),
    },
    {  # CNR
        "count": 7,
        "pool": "subscription",
        "intake": "I cancelled {subject} but {shown} charged me ${amount} again.",
        "evidence": ("usage_log", "Usage log for {subject}: active and used in the billed period."),
        "outcomes": (
            ("accepted", ""),
            ("rejected", "No cancellation was received; the plan remained in use."),
            ("not_a_dispute", "This charge is for another plan on the account, never cancelled."),
        ),
    },
    {  # NKN
        "count": 7,
        "pool": "subscription",
        "intake": "I don't recognise a ${amount} charge from {shown}.",
        "evidence": (
            "usage_log",
            "Usage log for {subject}: opened with the Card on file and used in the billed period.",
        ),
        "outcomes": (
            (
                "not_a_dispute",
                "This is the Card Member's own subscription, billed under our "
                "statement descriptor.",
            ),
            ("fraud_referral", ""),
        ),
    },
    {  # PDD
        "count": 4,
        "pool": "installment",
        "intake": "I already paid {subject} by bank transfer, so the ${amount} card charge is a "
        "second payment.",
        "evidence": (
            "invoice_ledger",
            "Ledger for {subject}: the transfer paid another "
            "installment; the card charge paid this one.",
        ),
        "outcomes": (
            ("rejected", "The transfer paid a different installment than the card charge."),
            ("partially_accepted", "The card charge exceeded the installment it paid."),
        ),
    },
)


class _Card(NamedTuple):
    id: str
    account: str
    product: str
    holder: str  # the Card Member the Card was issued to
    basic: str  # the Basic Card Member responsible for its account


class _Sale(NamedTuple):
    """A background charge a past Dispute can challenge, and what it paid for."""

    charge: str
    card: _Card
    merchant: str
    day: date
    amount: float
    subject: str  # what was bought, as the Card Member would name it
    shown: str  # the name on the statement
    record: str  # the order, return, subscription, installment or charge evidence speaks about
    terms: str  # the policy version the Card Member accepted, or ""


def build_world(seed: int = 7, corpus: Path = _CORPUS) -> tuple[Graph, list[PolicyDoc]]:
    """Build the background graph, including every corpus policy, and return it with every
    PolicyDoc (corpus and generated) for the knowledge build."""
    rng = random.Random(seed)
    counters: defaultdict[str, count] = defaultdict(lambda: count(1))

    def new_id(prefix: str) -> str:
        return f"{prefix}-BG-{next(counters[prefix]):04d}"

    g = Graph()
    docs = load_policies(corpus)
    _merchants(g)
    for doc in docs:
        add_to_graph(g, doc)
    _amex_terms(g)
    generated, terms = _merchant_policies(g, rng, new_id)
    cards = _card_members(g, rng, new_id)
    retail, refused = _retail(g, rng, new_id, cards, terms)
    lodging = _lodging(g, rng, new_id, cards, terms)
    dining = _dining(g, rng, new_id, cards)
    subscriptions = _subscriptions(g, rng, new_id, cards, terms)
    installments = _invoices(g, rng, new_id, cards, terms)
    _offers(g, rng, new_id, cards)
    pools = {
        "refused": refused,
        "retail": retail,
        "furniture": [s for s in retail if _CATEGORIES[s.merchant] == "furniture"],
        "lodging": lodging,
        "dining": dining,
        "service": lodging + dining,
        "subscription": subscriptions,
        "installment": installments,
    }
    _past_disputes(g, rng, new_id, pools)
    return g, docs + generated


def stats(graph: Graph) -> None:
    """Print node and edge counts."""
    for name, counts in (
        ("nodes", Counter(n["label"] for n in graph.nodes.values())),
        ("edges", Counter(e["type"] for e in graph.edges)),
    ):
        print(f"{name} {json.dumps(dict(sorted(counts.items())))}")


def _merchants(g: Graph) -> None:
    for merchant, name, category, channel in _MERCHANTS:
        g.node("Merchant", merchant, name=name, category=category, channel=channel)
    for merchant, (descriptor, text) in _DESCRIPTORS.items():
        g.node("Descriptor", descriptor, text=text)
        g.edge("DESCRIBES", descriptor, merchant)
    for affiliate, parent in _AFFILIATES:
        g.edge("AFFILIATE_OF", affiliate, parent)


def _amex_terms(g: Graph) -> None:
    """Every Merchant is bound by the Merchant Regulations; the Platinum Stays hotels also by the
    program's participation terms."""
    for merchant in _NAMES:
        g.edge("BOUND_BY", merchant, AMEX_MR)
    g.node("Program", PLATINUM_STAYS, name="Platinum Stays", eligible_product="Platinum")
    g.edge("GOVERNS", AMEX_PLAT_BEN, PLATINUM_STAYS)
    g.edge("GOVERNS", AMEX_PS_PART, PLATINUM_STAYS)
    for hotel in _PLATINUM_STAYS_HOTELS:
        g.edge("PARTICIPATES_IN", hotel, PLATINUM_STAYS)
        g.edge("BOUND_BY", hotel, AMEX_PS_PART)


def _merchant_policies(g: Graph, rng, new_id) -> tuple[list[PolicyDoc], dict[str, list[str]]]:
    """Template policies for background Merchants; retailers get a second, stricter version.
    Returns the new documents and each Merchant's policy versions, oldest first."""
    docs = []
    terms = {merchant: [doc] for merchant, doc in _CORPUS_TERMS.items()}
    for merchant, name, category, _ in _MERCHANTS:
        if merchant in terms:
            continue
        kind, title, clauses = _TEMPLATES[category]
        params = {
            "hours": rng.choice((24, 48, 72)),
            "service": rng.choice((18, 20)),
            "shipping": rng.choice(("free", "paid by the customer")),
        }
        windows = (30, rng.choice((14, 21))) if category in _CATALOG else (30,)
        terms[merchant] = []
        for version, days in enumerate(windows, start=1):
            doc_id = new_id("POL")
            suffix = doc_id.removeprefix("POL-")
            doc = PolicyDoc(
                id=doc_id,
                title=f"{name} {title}",
                owner="merchant",
                kind=kind,
                version=str(version),
                audience="card_member",
                source_url="",
                publisher=merchant,
                clauses=tuple(
                    Clause(f"CLS-{suffix}-{n}", str(n), heading, text.format(days=days, **params))
                    for n, (heading, text) in enumerate(clauses, start=1)
                ),
            )
            add_to_graph(g, doc)
            docs.append(doc)
            terms[merchant].append(doc_id)
    return docs, terms


def _accepted(terms: dict[str, list[str]], merchant: str, day: date) -> str:
    versions = terms[merchant]
    return versions[-1] if day >= _SECOND_VERSION else versions[0]


def _card_members(g: Graph, rng, new_id) -> list[_Card]:
    """135 Basic Card Members (a third with two Card Products, three namesakes of others) and
    15 Additional Card Members on their accounts."""
    names = rng.sample([f"{f} {last}" for f in _FIRST for last in _LAST], 132)
    names += rng.sample(names, 3)
    cards = []
    for name in names:
        member = _person(g, rng, new_id, name)
        pair = rng.random() < 1 / 3
        products = rng.choice(_PRODUCT_PAIRS) if pair else rng.choices(_PRODUCTS, (2, 4, 2, 3))
        for product in products:
            account = open_account(g, member, new_id("ACC"), product)
            cards.append(_issue(g, rng, new_id, account, member, member, product))
    for basic in rng.sample(cards, 15):
        surname = g.nodes[basic.holder]["props"]["name"].split()[-1]
        member = _person(g, rng, new_id, f"{rng.choice(_FIRST)} {surname}")
        g.edge("HOLDS", member, basic.account, role="additional")
        cards.append(_issue(g, rng, new_id, basic.account, member, basic.holder, basic.product))
    return cards


def _person(g: Graph, rng, new_id, name: str) -> str:
    member = new_id("CMB")
    since = date(2005, 1, 1) + timedelta(days=rng.randrange(7300))
    g.node("CardMember", member, name=name, member_since=since.isoformat())
    return member


def _issue(g: Graph, rng, new_id, account, holder, basic, product) -> _Card:
    """A Card on `account` carried by `holder`; `basic` is the account's Basic Card Member."""
    role = "basic" if holder == basic else "additional"
    last4 = f"{rng.randrange(10000):04d}"
    card = issue_card(g, new_id("CRD"), account, holder, product, last4, role)
    return _Card(card, account, product, holder, basic)


def open_account(g: Graph, member: str, account: str, product: str) -> str:
    """An open account held by its Basic Card Member, bound by the Card Member Agreement and,
    for Platinum, the Platinum benefit terms."""
    g.node("CardAccount", account, product=product, status="open")
    g.edge("HOLDS", member, account, role="basic")
    g.edge("BOUND_BY", account, AMEX_CMA)
    if product == "Platinum":
        g.edge("BOUND_BY", account, AMEX_PLAT_BEN)
    return account


def issue_card(g: Graph, card: str, account: str, holder: str, product, last4, role) -> str:
    g.node("Card", card, last4=last4, product=product, role=role, status="active")
    g.edge("ISSUED_ON", card, account)
    g.edge("CARRIED_BY", card, holder)
    return card


def _day(rng) -> date:
    return _YEAR + timedelta(days=rng.randrange(230))


def _charge(g: Graph, new_id, card: str, merchant: str, day: date, amount: float, kind: str) -> str:
    return post_charge(g, new_id("CHG"), card, merchant, day.isoformat(), amount, kind)


def post_charge(g: Graph, charge: str, card: str, merchant: str, day: str, amount, kind) -> str:
    g.node(
        "Charge",
        charge,
        date=day,
        amount=round(amount, 2),
        currency="USD",
        kind=kind,
        status="posted",
    )
    g.edge("CHARGED_TO", charge, card)
    g.edge("AT_MERCHANT", charge, merchant)
    return charge


def file_dispute(
    g: Graph,
    dispute: str,
    member: str,
    disputed: dict[str, float],
    filed: str,
    intake,
    status: str,
    outcome: str,
) -> str:
    """A Dispute filed by `member` challenging the given amount of each charge."""
    g.node(
        "Dispute",
        dispute,
        filed_at=filed,
        amount=round(sum(disputed.values()), 2),
        intake=intake,
        status=status,
        outcome=outcome,
    )
    g.edge("FILED_BY", dispute, member)
    for charge, amount in disputed.items():
        g.edge("DISPUTES", dispute, charge, amount=amount)
    return dispute


def add_offer(g: Graph, offer: str, merchant: str, title: str, spend, credit, funded_by) -> str:
    """An Offer at `merchant`; an Amex-funded one is governed by the Amex Offer terms."""
    g.node(
        "Offer",
        offer,
        title=title,
        spend_threshold=float(spend),
        credit_amount=float(credit),
        funded_by=funded_by,
    )
    g.edge("OFFER_AT", offer, merchant)
    if funded_by == "amex":
        g.edge("GOVERNS", AMEX_OFFER, offer)
    return offer


def add_subscription(g: Graph, sub: str, merchant, card, terms, plan, amount, status) -> str:
    """A monthly plan billed to `card` under the terms version accepted at sign-up."""
    g.node(
        "Subscription",
        sub,
        plan=plan,
        amount=amount,
        frequency="monthly",
        status=status,
    )
    g.edge("AT_MERCHANT", sub, merchant)
    g.edge("SUBSCRIBED_WITH", sub, card)
    g.edge("ACCEPTED", sub, terms, method="checkbox at sign-up")
    return sub


def bill_subscription(g: Graph, charge: str, sub, card, merchant, day: str, amount) -> str:
    """One recurring charge for `sub`, shown under the Merchant's statement descriptor."""
    post_charge(g, charge, card, merchant, day, amount, "recurring")
    g.edge("FOR_SUBSCRIPTION", charge, sub)
    g.edge("DESCRIBED_AS", charge, _DESCRIPTORS[merchant][0])
    return charge


def add_invoice(g: Graph, invoice: str, merchant, member, terms, day: str, total, description):
    """An invoice to `member` under the signed terms version."""
    g.node(
        "Invoice",
        invoice,
        date=day,
        total=total,
        currency="USD",
        description=description,
    )
    g.edge("AT_MERCHANT", invoice, merchant)
    g.edge("BILLED_TO", invoice, member)
    g.edge("ACCEPTED", invoice, terms, method="signature")
    return invoice


def add_installment(g: Graph, invoice: str, installment: str, label: str, amount) -> str:
    g.node("Installment", installment, label=label, amount=amount)
    g.edge("HAS_INSTALLMENT", invoice, installment)
    return installment


def pay_other_means(
    g: Graph, payment: str, member, merchant, day: str, method, amount, reference, installment: str
) -> str:
    """A non-Card payment by `member` settling one installment."""
    g.node(
        "Payment",
        payment,
        date=day,
        method=method,
        amount=amount,
        reference=reference,
    )
    g.edge("PAID_BY", payment, member)
    g.edge("AT_MERCHANT", payment, merchant)
    g.edge("SETTLES", payment, installment)
    return payment


def _credit(g: Graph, rng, new_id, sale: _Sale, amount: float) -> None:
    day = sale.day + timedelta(days=rng.randint(10, 30))
    credit = _charge(g, new_id, sale.card.id, sale.merchant, day, -amount, "credit")
    g.edge("REFUNDS", credit, sale.charge)


def _retail(g: Graph, rng, new_id, cards, terms) -> tuple[list[_Sale], list[_Sale]]:
    """Furniture and apparel orders with line items; some returned (refused when an option is
    custom), some partly credited. Returns every order's sale and those whose return was refused."""
    catalog = {}
    for merchant in _merchants_in(*_CATALOG):
        catalog[merchant] = []
        for name, price, standard, custom in rng.sample(_CATALOG[_CATEGORIES[merchant]], 4):
            product = new_id("PRD")
            g.node("Product", product, name=name, standard_options=standard, custom_options=custom)
            g.edge("SOLD_BY", product, merchant)
            catalog[merchant].append((product, name, price, standard, custom))
    sales, refused = [], []
    for _ in range(850):
        merchant, card, day = rng.choice(list(catalog)), rng.choice(cards), _day(rng)
        order, doc = new_id("ORD"), _accepted(terms, merchant, day)
        chosen, is_custom = [], False
        for product, name, price, standard, custom in rng.sample(
            catalog[merchant], rng.randint(1, 2)
        ):
            custom_option = bool(custom) and rng.random() < 0.15
            is_custom |= custom_option
            option = rng.choice((custom if custom_option else standard).split("; "))
            chosen.append((product, name, price, option))
        total = sum(price for _, _, price, _ in chosen)
        g.node(
            "Order",
            order,
            date=day.isoformat(),
            kind="retail",
            total=total,
            currency="USD",
            summary="; ".join(f"{name} ({option})" for _, name, _, option in chosen),
        )
        g.edge("AT_MERCHANT", order, merchant)
        g.edge("ACCEPTED", order, doc, method="checkbox at checkout")
        for product, name, price, option in chosen:
            line = new_id("LIN")
            g.node("LineItem", line, description=name, quantity=1, unit_price=price, option=option)
            g.edge("HAS_LINE", order, line)
            g.edge("OF_PRODUCT", line, product)
        charge = _charge(g, new_id, card.id, merchant, day, total, "purchase")
        g.edge("FOR_ORDER", charge, order)
        sale = _Sale(
            charge, card, merchant, day, total, f"the {chosen[0][1]}", _NAMES[merchant], order, doc
        )
        sales.append(sale)
        roll = rng.random()
        if is_custom and roll < 0.15:
            ret = _return(
                g, rng, new_id, order, "refused", "Return refused: custom item, final sale."
            )
            refused.append(sale._replace(record=ret))
        elif not is_custom and roll < 0.03:
            _return(
                g,
                rng,
                new_id,
                order,
                "received and refunded",
                "Received in original condition; refunded to the original Card.",
            )
            _credit(g, rng, new_id, sale, total)
        elif roll > 0.92:
            _credit(g, rng, new_id, sale, round(total * rng.choice((0.1, 0.15, 0.25)), 2))
    return sales, refused


def _return(g: Graph, rng, new_id, order: str, status: str, note: str) -> str:
    ret = new_id("RTN")
    g.node("Return", ret, method=rng.choice(_RETURN_METHODS), status=status, note=note)
    g.edge("RETURNED_AS", order, ret)
    return ret


def _lodging(g: Graph, rng, new_id, cards, terms) -> list[_Sale]:
    """Hotel bookings guaranteed with the Card that pays; Platinum Stays bookings only with a
    Platinum Card at a participating hotel."""
    hotels = _merchants_in("lodging")
    rates = {hotel: rng.randrange(180, 520, 10) for hotel in hotels}
    platinum = [c for c in cards if c.product == "Platinum"]
    sales = []
    for _ in range(350):
        hotel = rng.choice(hotels)
        program = hotel in _PLATINUM_STAYS_HOTELS and rng.random() < 0.5
        card = rng.choice(platinum if program else cards)
        rate = round(rates[hotel] * 0.8) if program else rates[hotel]
        booked = _day(rng)
        arrival = booked + timedelta(days=rng.randint(7, 60))
        nights = rng.randint(1, 4)
        plan = "Platinum Stays rate" if program else "Best Available Rate"
        stay = f"{nights} night" + ("s" if nights > 1 else "")
        total = float(nights * rate)
        order, doc = new_id("ORD"), _accepted(terms, hotel, booked)
        g.node(
            "Order",
            order,
            date=booked.isoformat(),
            kind="lodging",
            total=total,
            currency="USD",
            summary=f"{stay}, {plan} ${rate}/night, arriving {arrival}",
        )
        g.edge("AT_MERCHANT", order, hotel)
        g.edge("GUARANTEED_WITH", order, card.id)
        g.edge("ACCEPTED", order, doc, method="booking confirmation")
        if program:
            g.edge("UNDER_PROGRAM", order, PLATINUM_STAYS)
        day = arrival + timedelta(days=nights)
        charge = _charge(g, new_id, card.id, hotel, day, total, "purchase")
        g.edge("FOR_ORDER", charge, order)
        sale = _Sale(charge, card, hotel, day, total, "my stay", _NAMES[hotel], order, doc)
        sales.append(sale)
        if rng.random() < 0.08:
            _credit(g, rng, new_id, sale, float(rng.choice((25, 40, 60))))
    return sales


def _dining(g: Graph, rng, new_id, cards) -> list[_Sale]:
    restaurants = _merchants_in("dining")
    sales = []
    for _ in range(1500):
        merchant, card, day = rng.choice(restaurants), rng.choice(cards), _day(rng)
        amount = rng.randrange(1800, 24000) / 100
        charge = _charge(g, new_id, card.id, merchant, day, amount, "purchase")
        sales.append(
            _Sale(charge, card, merchant, day, amount, "a meal", _NAMES[merchant], charge, "")
        )
    return sales


def _subscriptions(g: Graph, rng, new_id, cards, terms) -> list[_Sale]:
    """Monthly plans billed under each streaming Merchant's descriptor; some cancelled."""
    sales = []
    for _ in range(20):
        merchant = rng.choice(list(_PLANS))
        plan, price = rng.choice(_PLANS[merchant])
        card = rng.choice(cards)
        first = rng.randint(1, 5)
        cancelled = rng.random() < 0.3
        last = rng.randint(first + 1, 7) if cancelled else 8
        shown = _DESCRIPTORS[merchant][1]
        start = date(2026, first, rng.randint(1, 28))
        doc = _accepted(terms, merchant, start)
        status = "cancelled" if cancelled else "active"
        subscription = add_subscription(
            g, new_id("SUB"), merchant, card.id, doc, plan, price, status
        )
        for month in range(first, last + 1):
            day = start.replace(month=month)
            charge = bill_subscription(
                g, new_id("CHG"), subscription, card.id, merchant, day.isoformat(), price
            )
            sales.append(
                _Sale(
                    charge, card, merchant, day, price, f"the {plan} plan", shown, subscription, doc
                )
            )
    return sales


def _invoices(g: Graph, rng, new_id, cards, terms) -> list[_Sale]:
    """Venue and catering invoices split into installments, each paid by Card or by other means.
    Returns the installments paid by Card."""
    venues = _merchants_in(*_INVOICES)
    sales = []
    for _ in range(10):
        merchant, card = rng.choice(venues), rng.choice(cards)
        description = rng.choice(_INVOICES[_CATEGORIES[merchant]])
        total = float(rng.randrange(2000, 9001, 500))
        shares = rng.choice(((0.25,), (0.2, 0.4)))
        amounts = [round(total * s, -1) for s in shares]
        amounts.append(total - sum(amounts))
        labels = ("Deposit", "Second payment")[: len(shares)] + ("Balance",)
        issued = _YEAR + timedelta(days=rng.randrange(120))
        doc = _accepted(terms, merchant, issued)
        invoice = add_invoice(
            g, new_id("INV"), merchant, card.holder, doc, issued.isoformat(), total, description
        )
        day = issued
        for label, amount in zip(labels, amounts, strict=True):
            installment = add_installment(g, invoice, new_id("INS"), label, amount)
            day += timedelta(days=rng.randint(20, 60))
            if rng.random() < 0.6:
                charge = _charge(g, new_id, card.id, merchant, day, amount, "purchase")
                g.edge("SETTLES", charge, installment)
                subject = description.lower()
                sales.append(
                    _Sale(
                        charge,
                        card,
                        merchant,
                        day,
                        amount,
                        subject,
                        _NAMES[merchant],
                        installment,
                        doc,
                    )
                )
            else:
                surname = g.nodes[card.holder]["props"]["name"].split()[-1].upper()
                pay_other_means(
                    g,
                    new_id("PAY"),
                    card.holder,
                    merchant,
                    day.isoformat(),
                    rng.choice(("bank_transfer", "bank_transfer", "cheque")),
                    amount,
                    f"{_NAMES[merchant].upper()} {label.upper()} {surname}",
                    installment,
                )
    return sales


def _offers(g: Graph, rng, new_id, cards) -> None:
    """Twelve Offers at background Merchants: ten Amex Offers enrolled on specific Cards, two
    merchant-funded promotions."""
    eligible = [
        m
        for m in _merchants_in("furniture", "apparel", "lodging", "dining")
        if m not in _CORPUS_TERMS
    ]
    for n, merchant in enumerate(rng.sample(eligible, 12)):
        spend, credit = rng.choice(((100, 20), (150, 25), (200, 30), (250, 50), (500, 100)))
        amex = n < 10
        name = _NAMES[merchant]
        title = (
            f"Spend ${spend} or more at {name}, get ${credit} back"
            if amex
            else f"{name}: ${credit} off orders of ${spend} or more"
        )
        offer = add_offer(
            g, new_id("OFR"), merchant, title, spend, credit, "amex" if amex else "merchant"
        )
        if amex:
            for card in rng.sample(cards, rng.randint(3, 8)):
                g.edge("ENROLLED_ON", offer, card.id)


def _past_disputes(g: Graph, rng, new_id, pools: dict[str, list[_Sale]]) -> None:
    """Resolved Disputes over distinct background charges, about half with a Merchant Submission."""
    used: set[str] = set()
    for spec in _PAST:
        candidates = [s for s in pools[spec["pool"]] if s.charge not in used]
        for sale in rng.sample(candidates, spec["count"]):
            used.add(sale.charge)
            if spec.get("duplicate"):
                again = _charge(
                    g, new_id, sale.card.id, sale.merchant, sale.day, sale.amount, "purchase"
                )
                sale = sale._replace(charge=again, record=again)
            verdict, statement = rng.choice(spec["outcomes"])
            disputed = round(sale.amount * spec.get("share", 1.0), 2)
            words = {"subject": sale.subject, "shown": sale.shown, "amount": f"{disputed:,.2f}"}
            filed = sale.day + timedelta(days=rng.randint(5, 40))
            dispute = file_dispute(
                g,
                new_id("DSP"),
                sale.card.basic,
                {sale.charge: disputed},
                filed.isoformat(),
                spec["intake"].format(**words),
                "resolved",
                verdict,
            )
            if verdict in ("accepted", "partially_accepted"):
                share = 1 if verdict == "accepted" else 0.5
                _credit(g, rng, new_id, sale, round(disputed * share, 2))
            if statement:
                kind, text = spec["evidence"]
                item = SubmittedItem(kind=kind, text=text.format(**words), asserts=[sale.record])
                submission = MerchantSubmission(
                    submission_id=new_id("MSB"),
                    dispute_id=dispute,
                    merchant_id=sale.merchant,
                    statement=statement,
                    items=[item],
                    messages=[],
                    cited_ids=[sale.terms] if sale.terms else [],
                )
                insert_submission(g, submission)
