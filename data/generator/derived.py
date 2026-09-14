"""Derived artifacts: Q01 queue ground truth (deadline-ranked backlog) and graph node/edge export."""
from __future__ import annotations

import datetime as dt
import hashlib

from common import AS_OF, Ctx, add_days, d
from world import BANK_HOLIDAYS_2026

HOLIDAYS = {d(x) for x, _ in BANK_HOLIDAYS_2026}
AS_OF_DATE = dt.date(2026, 10, 21)


def add_business_days(start: str, n: int) -> str:
    """Move n business days (negative = backwards), skipping weekends and bank holidays."""
    cur, k, step = d(start), 0, (1 if n >= 0 else -1)
    while k < abs(n):
        cur += dt.timedelta(days=step)
        if cur.weekday() < 5 and cur not in HOLIDAYS:
            k += 1
    return cur.isoformat()


def _month_add(day: dt.date, months: int, dom: int) -> dt.date:
    y, mth = day.year + (day.month - 1 + months) // 12, (day.month - 1 + months) % 12 + 1
    return dt.date(y, mth, min(dom, 28))


def reg_z_resolution_deadline(notice: str, cycle_day: int) -> str:
    """End of the second complete billing cycle after notice, capped at 90 days."""
    n = d(notice)
    end = dt.date(n.year, n.month, min(cycle_day, 28))
    if end < n:
        end = _month_add(end, 1, cycle_day)
    # `end` closes the cycle containing the notice; two complete cycles follow
    second = _month_add(end, 2, cycle_day)
    return min(second, n + dt.timedelta(days=90)).isoformat()


def build_queue(ctx: Ctx):
    accounts = {a["account_id"]: a for a in ctx.t["accounts"]}
    txn_of = {}
    for x in ctx.t["dispute_transactions"]:
        txn_of.setdefault(x["case_id"], []).append(ctx.get("transactions", x["txn_id"]))
    acked = {e["case_id"] for e in ctx.t["dispute_events"] if e["event_type"] == "ack_letter_sent"}
    rows = []
    for dsp in ctx.t["disputes"]:
        if dsp["status"] != "open":
            continue
        acct = accounts[dsp["account_id"]]
        opened = dsp["opened_at"][:10]
        clocks = []
        if dsp["regime"] == "REG_Z":
            if dsp["case_id"] not in acked:
                clocks.append(("reg_z_acknowledgment", add_days(opened, 30)))
            clocks.append(("reg_z_resolution", reg_z_resolution_deadline(opened, int(acct["statement_cycle_day"]))))
        else:
            txns = txn_of[dsp["case_id"]]
            first_dep = acct["first_deposit_date"]
            new_acct = bool(first_dep) and any(0 <= (d(t["txn_local_datetime"][:10]) - d(first_dep)).days <= 30 for t in txns)
            if not dsp["provisional_credit_at"]:
                clocks.append(("reg_e_provisional_credit", add_business_days(opened, 20 if new_acct else 10)))
            pos = any(t["channel"] in ("in_store", "ecommerce") for t in txns)
            clocks.append(("reg_e_investigation", add_days(opened, 90 if (new_acct or pos) else 45)))
        if dsp["response_processing_date"] and dsp["stage"] == "pre_arb_decision_due":
            clocks.append(("visa_pre_arbitration", add_days(dsp["response_processing_date"], 30)))
        if not dsp["dispute_processing_date"]:
            proc = min(t["processing_date"] for t in txn_of[dsp["case_id"]] if t["processing_date"])
            clocks.append(("visa_dispute_time_limit", add_days(proc, 120)))
        gt = ctx.ground_truth.get(dsp["case_id"], {})
        if gt.get("code") == "C10":
            clocks.append(("merchant_minor_refund_window", "2026-10-26"))
        if gt.get("code") == "C13":
            clocks.append(("await_agentic_provider_record", "2026-10-23"))
        today = AS_OF_DATE.isoformat()
        expired = [c for c in clocks if c[0] == "visa_dispute_time_limit" and c[1] < today]
        future = [c for c in clocks if c[1] >= today]
        overdue = [c for c in clocks if c[1] < today and c not in expired]
        nxt = min(future, key=lambda c: c[1]) if future else None
        rows.append(dict(case_id=dsp["case_id"], regime=dsp["regime"], stage=dsp["stage"], amount=dsp["dispute_amount"],
                         opened=opened, next_clock=nxt[0] if nxt else None, next_deadline=nxt[1] if nxt else None,
                         overdue_clocks=overdue, expired_rights=expired, all_clocks=clocks, hero_code=gt.get("code")))
    ranked = sorted(rows, key=lambda r: (0 if r["overdue_clocks"] else 1, r["next_deadline"] or "9999", -float(r["amount"])))
    ctx.queue_truth = dict(
        scenario="Q01", title="Monday Morning Queue", as_of=AS_OF.isoformat(),
        instructions="Rank open cases by the earliest hard deadline that requires issuer action. Overdue clocks first.",
        notes=["Reg Z acknowledgment/resolution deadlines assume notice date = opened_at date",
               "Reg Z resolution: end of second complete billing cycle after notice, capped at 90 days",
               "Reg E business days use reference/bank_holidays_2026.csv",
               "Hero-specific non-regulatory clocks included where they are hard (merchant refund window, awaited agentic-provider record)",
               "expired_rights lists network time limits already passed: not urgent work, but a finding the investigator must surface"],
        top_15=[dict(rank=i + 1, **{k: r[k] for k in ("case_id", "next_clock", "next_deadline", "overdue_clocks", "expired_rights", "regime", "stage", "hero_code")})
                for i, r in enumerate(ranked[:15])],
        all_open=ranked)


# ============================================================ graph export
def _nid(label, key):
    return f"{label}:{key}"


def build_graph(ctx: Ctx):
    nodes, edges = {}, []

    def node(label, key, **props):
        k = _nid(label, key)
        if k not in nodes:
            nodes[k] = dict(node_id=k, label=label, key=key, props=props)
        return k

    def edge(src, rel, dst, **props):
        edges.append(dict(src=src, rel=rel, dst=dst, props=props))

    addr_key = {}
    for a in ctx.t["addresses"]:
        full = f"{a['line1']}{', ' + a['line2'] if a['line2'] else ''}, {a['city']}, {a['state']} {a['postal_code']}"
        addr_key[full.lower()] = a["address_id"]
        node("Address", a["address_id"], full=full, type=a["address_type"], city=a["city"], state=a["state"])

    def address_node(s: str):
        k = addr_key.get(s.lower())
        if k:
            return _nid("Address", k)
        h = "ADR-OBS-" + hashlib.sha1(s.lower().encode()).hexdigest()[:10]
        return node("Address", h, full=s, type="observed_in_merchant_evidence")

    for c in ctx.t["customers"]:
        cn = node("Customer", c["customer_id"], name=c["full_name"], since=c["customer_since"])
        edge(cn, "LIVES_AT", _nid("Address", c["home_address_id"]))
        if c["work_address_id"]:
            edge(cn, "WORKS_AT", _nid("Address", c["work_address_id"]))
        edge(cn, "HAS_PHONE", node("Phone", c["phone"]), kind="primary")
        if c["alt_phone"]:
            edge(cn, "HAS_PHONE", node("Phone", c["alt_phone"]), kind="alternate")
        edge(cn, "HAS_EMAIL", node("Email", c["email"].lower()))
    for a in ctx.t["accounts"]:
        node("Account", a["account_id"], product=a["product"], regime=a["regime"], opened=a["opened_at"])
    for h in ctx.t["account_holders"]:
        edge(_nid("Customer", h["customer_id"]), "HOLDS", _nid("Account", h["account_id"]), role=h["role"], since=h["added_at"])
    for c in ctx.t["cards"]:
        cn = node("Card", c["card_id"], pan_masked=c["pan_masked"], role=c["role"])
        edge(_nid("Account", c["account_id"]), "HAS_CARD", cn)
        edge(_nid("Customer", c["customer_id"]), "CARRIES", cn)
    for t in ctx.t["tokens"]:
        tn = node("Token", t["token_id"], requestor_type=t["token_requestor_type"])
        edge(_nid("Card", t["card_id"]), "TOKENIZED_AS", tn)
        if t["token_requestor_type"] == "agentic_payment_provider":
            edge(tn, "REQUESTED_BY", node("AgenticProvider", t["token_requestor_name"]))
    for mrc in ctx.t["merchants"]:
        mn = node("Merchant", mrc["merchant_id"], name=mrc["dba_name"], mcc=mrc["mcc"], acquirer_id=mrc["acquirer_id"], status=mrc["status"])
        edge(mn, "ACQUIRED_BY", node("Acquirer", mrc["acquirer_id"], name=mrc["acquirer_name"]))
        if mrc["parent_merchant_id"]:
            edge(mn, "SUB_MERCHANT_OF", _nid("Merchant", mrc["parent_merchant_id"]))
    for ds in ctx.t["merchant_descriptors"]:
        edge(node("Descriptor", ds["descriptor"]), "DESCRIBES", _nid("Merchant", ds["merchant_id"]), first_seen=ds["first_seen"], last_seen=ds["last_seen"])
    for dv in ctx.t["devices"]:
        dn = node("Device", dv["device_id"], type=dv["device_type"])
        edge(dn, "HAS_FINGERPRINT", node("DeviceFingerprint", dv["device_fingerprint"]))
    for ip in ctx.t["ip_intel"]:
        node("IP", ip["ip"], ip_type=ip["ip_type"])
    for t in ctx.t["transactions"]:
        if t["txn_type"] in ("payment",):
            continue
        tn = node("Transaction", t["txn_id"], amount=t["billing_amount"], type=t["txn_type"], date=t["txn_local_datetime"][:10],
                  channel=t["channel"])
        edge(_nid("Card", t["card_id"]), "MADE", tn)
        if t["merchant_id"]:
            edge(tn, "AT", _nid("Merchant", t["merchant_id"]))
        if t["token_id"]:
            edge(tn, "USING_TOKEN", _nid("Token", t["token_id"]))
    # login aggregation: customer -> device / ip
    agg = {}
    for ev in ctx.t["account_events"]:
        if ev["event_type"] not in ("login_success", "login_failed", "password_reset"):
            continue
        for kind, val in (("Device", ev["device_id"]), ("IP", ev["ip"])):
            if val:
                key = (ev["customer_id"], kind, val, ev["event_type"])
                a = agg.setdefault(key, [0, ev["timestamp_utc"], ev["timestamp_utc"]])
                a[0] += 1
                a[1] = min(a[1], ev["timestamp_utc"])
                a[2] = max(a[2], ev["timestamp_utc"])
    for (cid, kind, val, et), (cnt, first, last) in sorted(agg.items()):
        tgt = _nid("Device", val) if kind == "Device" else node("IP", val)
        edge(_nid("Customer", cid), "BANKING_LOGIN_FROM", tgt, event=et, count=cnt, first=first, last=last)
    for dsp in ctx.t["disputes"]:
        dn = node("Dispute", dsp["case_id"], status=dsp["status"], condition=dsp["network_condition"], opened=dsp["opened_at"][:10],
                  family=dsp["claim_family_initial"])
        edge(_nid("Customer", dsp["customer_id"]), "FILED", dn)
        for rel in filter(None, dsp["related_case_ids"].split("|")):
            edge(dn, "RELATED_TO", _nid("Dispute", rel))
    for x in ctx.t["dispute_transactions"]:
        edge(_nid("Dispute", x["case_id"]), "DISPUTES", _nid("Transaction", x["txn_id"]), amount=x["disputed_amount"])
    for pk in ctx.packets.values():
        pn = node("EvidencePacket", pk["packet_id"], source=pk["source"], available_at=pk["available_at"])
        edge(_nid("Dispute", pk["case_id"]), "HAS_EVIDENCE", pn)
        tn = _nid("Transaction", pk["txn_id"])
        ship = pk.get("shipping_address")
        if ship:
            edge(tn, "SHIPPED_TO", address_node(ship), source=pk["packet_id"])
        for s in pk.get("shipments") or []:
            pod = (s.get("proof_of_delivery") or {}).get("address")
            if pod and not ship:
                edge(tn, "DELIVERED_TO", address_node(pod), source=pk["packet_id"])
        sess = pk.get("session") or {}
        for k in ("ip",):
            if sess.get(k):
                edge(tn, "MERCHANT_SAW_IP", node("IP", sess[k]), source=pk["packet_id"])
        if sess.get("device_fingerprint"):
            edge(tn, "MERCHANT_SAW_FINGERPRINT", node("DeviceFingerprint", sess["device_fingerprint"]), source=pk["packet_id"])
        acct = pk.get("customer_account") or {}
        if acct.get("login_id"):
            edge(tn, "MERCHANT_LOGIN", node("MerchantLogin", f"{pk['merchant_id']}|{acct['login_id']}"), source=pk["packet_id"])
        if acct.get("device_fingerprint"):
            edge(tn, "MERCHANT_SAW_FINGERPRINT", node("DeviceFingerprint", acct["device_fingerprint"]), source=pk["packet_id"])
    for pid, text in ctx.precedents.items():
        case = next(line.split(": ", 1)[1] for line in text.splitlines() if line.startswith("case_id:"))
        edge(node("Precedent", pid), "DECIDED", _nid("Dispute", case))
    # keep only edges whose endpoints exist
    edges = [e for e in edges if e["src"] in nodes and e["dst"] in nodes]
    ctx.graph = (list(nodes.values()), edges)
