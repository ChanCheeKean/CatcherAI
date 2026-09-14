"""Precedent library: hand-written contrast precedents + templated precedents from closed background disputes."""
from __future__ import annotations

import background as bg
from common import Ctx, add_days, m, utc


def _doc(pid, case_id, title, decided, condition, ch_out, net_out, merchant_id, tags, policies, facts, decision, reasoning, notes):
    front = "\n".join([
        "---", f"precedent_id: {pid}", f"case_id: {case_id}", f"title: \"{title}\"", f"decided_at: {decided}",
        f"network_condition: \"{condition}\"", f"cardholder_outcome: {ch_out}", f"network_outcome: {net_out}",
        f"merchant_id: {merchant_id}", f"tags: [{', '.join(tags)}]", f"policy_versions_applied: [{', '.join(policies)}]", "---", ""])
    body = f"# {title}\n\n## Facts\n{facts.strip()}\n\n## Decision\n{decision.strip()}\n\n## Reasoning\n{reasoning.strip()}\n\n## Investigator notes\n{notes.strip()}\n"
    return front + body


def _closed_case(ctx: Ctx, case_id, rec, merchant, day, amount, family, condition, ch_out, net_out, opened, closed, summary, **txn_kw):
    acct, card = rec["accounts"][0], rec["cards"][0]
    t = bg.add_txn(ctx, acct, card, merchant, day, txn_kw.pop("time", "14:00:00"), amount,
                   channel=txn_kw.pop("channel", "ecommerce"), **txn_kw)
    bg.add_dispute(ctx, case_id, [t], acct["regime"], utc(opened, "10:00:00"), summary, family, status="closed", stage="closed",
                   network_condition=condition, dispute_processing_date=add_days(opened, 3) if net_out != "not_filed" else "",
                   cardholder_outcome=ch_out, network_outcome=net_out, closed_at=utc(closed, "16:00:00"),
                   assigned_queue="consumer_disputes" if not family.startswith("fraud") else "fraud_cnp")
    bg.add_devent(ctx, case_id, utc(closed, "16:00:00"), "case_closed", f"Closed: {ch_out}; {net_out}")
    return t


def build_hand_precedents(ctx: Ctx):
    rng = ctx.rng
    pick = [r for r in ctx.people if r["accounts"][0]["regime"] == "REG_Z"][60:75]
    debit = [r for r in ctx.people if r["accounts"][0]["regime"] == "REG_E"][:2]
    M = lambda mid: ctx.get("merchants", mid)
    byname = lambda n: next(r for r in ctx.t["merchants"] if r["dba_name"] == n)
    P = ctx.precedents

    # PRE-0004 true duplicate
    hm = byname("Hatchmark")
    t = _closed_case(ctx, "DSP-2026-08004", pick[0], hm, "2026-03-11", "212.40", "duplicate", "12.6", "credited", "issuer_won",
                     "2026-03-20", "2026-04-22", "Charged twice for one order.")
    dup = bg.add_txn(ctx, pick[0]["accounts"][0], pick[0]["cards"][0], hm, "2026-03-11", "14:00:00", "212.40", channel="ecommerce",
                     auth_code=t["auth_code"], auth_id=t["auth_id"], clearing_seq=1, clearing_count=1)
    ctx.add("dispute_transactions", dict(case_id="DSP-2026-08004", txn_id=dup["txn_id"], disputed_amount="212.40"))
    P["PRE-0004"] = _doc("PRE-0004", "DSP-2026-08004", "Same authorization cleared twice (true duplicate)", "2026-04-22", "12.6", "credited",
                         "issuer_won", hm["merchant_id"], ["duplicate", "clearing"], ["VISA-12.6@2025-10"], f"""
- Two clearing records for authorization {t['auth_code']}, both $212.40, both clearing sequence 1 of 1, different ARNs.
- Order had a single item; merchant confirmed a batch was resubmitted after a settlement error.""",
                         "Filed 12.6 for the second clearing ($212.40). Acquirer accepted.",
                         "Same authorization, same amount, same date, and **each** clearing marked 1/1 → processed more than once. Contrast: "
                         "multiple clearing sequence numbers (1/2, 2/2) from one authorization are a single transaction (split shipment), not a duplicate.",
                         "Check clearing_seq/clearing_count before assuming duplicate.")
    # PRE-0007 Larkspur upgrade without initials
    lk = M("MER-90005")
    _closed_case(ctx, "DSP-2026-08007", pick[1], lk, "2026-06-14", "916.20", "incorrect_amount", "", "partial_credit", "not_filed",
                 "2026-06-18", "2026-06-29", "Hotel upgrade charged; guest says complimentary.", channel="in_store", pos_entry_mode="07",
                 card_present=True, time="11:00:00")
    P["PRE-0007"] = _doc("PRE-0007", "DSP-2026-08007", "Larkspur Nashville: upgrade charged, no guest acknowledgment", "2026-06-29", "", "partial_credit",
                         "not_filed (merchant credited via Order Insight)", lk["merchant_id"], ["lodging", "T&E", "upgrade", "order_insight"],
                         ["VISA-12.5@2025-10", "VISA-13.3@2025-10"], """
- Guest disputed $207.00 upgrade (3 nights × $60 + tax) as "complimentary".
- Order Insight response included folio and registration card; **no initials or signature next to the upgrade line**.
- Destination fee was disclosed at booking; guest did not dispute it.""",
                         "Merchant issued a $207.00 credit after Order Insight inquiry. No network dispute filed. Case closed partial credit.",
                         "Without documented acknowledgment the hotel could not support the upgrade and credited it. 12.5 would have been invalid "
                         "(T&E quoted vs actual), so the pre-dispute channel was the correct path.",
                         "Larkspur responds to Order Insight within ~3 days with folio + registration card. Check the registration card for initials.")
    # PRE-0009 CE3.0 old rule
    sp = byname("Cinderbox Games")
    _closed_case(ctx, "DSP-2025-08009", pick[2], sp, "2025-10-30", "59.99", "fraud_cnp", "10.4", "denied", "merchant_won_pre_arb",
                 "2025-11-06", "2025-12-18", "Did not authorize game purchase.", eci="07", avs_result="Y")
    P["PRE-0009"] = _doc("PRE-0009", "DSP-2025-08009", "CE 3.0 met with two same-merchant prior purchases", "2025-12-18", "10.4", "denied",
                         "merchant_won_pre_arb", sp["merchant_id"], ["fraud_cnp", "CE3.0", "digital_goods"], ["VISA-10.4@2025-10"], """
- Two undisputed purchases at the **same merchant** 150 and 290 days before the dispute; IP and login ID matched on all three.
- Merchant pre-arbitration with CE 3.0 data; issuer reviewed evidence with the cardholder, who acknowledged the account was theirs.""",
                         "Accepted pre-arbitration; re-billed cardholder with explanation.",
                         "CE 3.0 (rule as in force in 2025): same payment credential, 2 prior undisputed transactions >120 and ≤365 days, "
                         "IP/device + one more element matching. Met.",
                         "Rule version: pre-October-2026 (same-merchant priors). Check the version in force on the dispute processing date.")
    # PRE-0010 household, card taken from wallet
    ph = M("MER-90011")
    _closed_case(ctx, "DSP-2026-08010", pick[3], ph, "2026-03-07", "149.95", "fraud_cnp", "10.4", "credited", "merchant_won_pre_arb",
                 "2026-03-09", "2026-04-20", "Teen used parent's card from wallet in game without permission.", eci="07", avs_result="Y")
    P["PRE-0010"] = _doc("PRE-0010", "DSP-2026-08010", "Teen used parent's card taken from wallet (no prior authority)", "2026-04-20", "10.4",
                         "credited", "merchant_won_pre_arb (issuer absorbed loss)", ph["merchant_id"], ["household", "minor", "reg_z_12b", "CE_item_11"],
                         ["REGZ-1026.12", "VISA-11.5.1-COMPELLING-EVIDENCE@2025-10"], """
- 6 purchases over one evening, card entered manually each time on the child's device; card had **never** been saved to the game account.
- Cardholder reported the same night after the first alert; no prior purchases at the merchant.""",
                         "Cardholder credited (unauthorized under Reg Z — no actual, implied or apparent authority; reported immediately). "
                         "Merchant defeated the 10.4 at pre-arbitration with household-member evidence; issuer wrote off $149.95.",
                         "Authority had never been given, so §1026.12(b) protected the cardholder even though the network outcome went to the merchant.",
                         "Contrast: if the cardholder had previously saved the card for the child, authority analysis changes (comment 12(b)(1)(ii)-3).")
    # PRE-0012 Lumafit old 13.2 rule
    lf = M("MER-90006")
    _closed_case(ctx, "DSP-2026-08012", pick[4], lf, "2026-02-19", "119.88", "cancelled_recurring", "13.2", "credited", "issuer_won",
                 "2026-03-02", "2026-04-09", "Trial converted to annual; cancelled after charge.", channel="recurring")
    P["PRE-0012"] = _doc("PRE-0012", "DSP-2026-08012", "Lumafit+: annual charge after trial, cancelled after billing (13.2 won)", "2026-04-09", "13.2",
                         "credited", "issuer_won", lf["merchant_id"], ["recurring", "free_trial", "13.2"], ["VISA-13.2@PRIOR"], """
- Trial converted to $119.88 annual plan on 2026-02-19; cardholder cancelled 2026-02-24 and disputed on 2026-03-02.""",
                         "Filed 13.2 on 2026-03-05 for $119.88; merchant did not respond; issuer won.",
                         "Cardholder withdrew permission; dispute filed under the 13.2 rule then in force.",
                         "Decided before the 18 April 2026 rule change that made 13.2 invalid when cancellation is after the transaction date.")
    # PRE-0015 FX pre-arb after dispute
    az = M("MER-90007")
    _closed_case(ctx, "DSP-2026-08015", pick[5], az, "2026-01-12", "329.51", "not_as_described", "13.3", "credited", "issuer_won",
                 "2026-01-28", "2026-03-30", "Tiles arrived broken.", txn_amount="300.00", txn_currency="EUR", fx_rate="1.0984")
    P["PRE-0015"] = _doc("PRE-0015", "DSP-2026-08015", "FX loss recovered via pre-arbitration (credit issued after dispute)", "2026-03-30", "13.3",
                         "credited", "issuer_won (pre-arb for FX difference)", az["merchant_id"], ["cross_border", "fx", "pre_arb"],
                         ["VISA-11.4-AMOUNTS-CREDITS-FX@2025-10", "VISA-11.2-LIFECYCLE@2025-10"], """
- Dispute filed 2026-01-31 (13.3). **After** the dispute, merchant refunded EUR 300.00, which converted to $318.31.
- Issuer's loss from rate change: $11.20.""",
                         "Issuer pursued pre-arbitration for $11.20 under the same condition; acquirer accepted.",
                         "Visa allows pre-arb for FX loss when the merchant credits the full amount in its local currency after the dispute was initiated.",
                         "Does not apply when the merchant's credit came before any dispute.")
    # PRE-0016 13.3 no return attempt
    rt = byname("Pixelwave Electronics")
    _closed_case(ctx, "DSP-2026-08016", pick[6], rt, "2026-06-20", "449.00", "not_as_described", "13.3", "denied", "merchant_won",
                 "2026-07-08", "2026-08-19", "Monitor has dead pixels.")
    P["PRE-0016"] = _doc("PRE-0016", "DSP-2026-08016", "Not as described: cardholder never attempted return", "2026-08-19", "13.3", "denied",
                         "merchant_won", rt["merchant_id"], ["not_as_described", "return"], ["VISA-13.3@2026-04-18"], """
- Cardholder kept the monitor and did not contact the merchant or request an RMA. Merchant's return policy offered free returns.""",
                         "Accepted Dispute Response; re-billed $449.00 with explanation.",
                         "13.3 requires the cardholder to return or attempt to return; an attempt only counts if the merchant refused, gave no "
                         "instructions, or disappeared.", "Contrast with refused-RMA cases.")
    # PRE-0017 12(c) honored
    tk = byname("Stagepass Tickets")
    _closed_case(ctx, "DSP-2026-08017", pick[7], tk, "2025-12-05", "248.00", "not_received", "", "credited", "not_filed",
                 "2026-06-10", "2026-06-24", "Festival cancelled; no refund; outside dispute window.")
    P["PRE-0017"] = _doc("PRE-0017", "DSP-2026-08017", "Claims and defenses honored outside dispute windows (balance outstanding)", "2026-06-24", "",
                         "credited", "not_filed", tk["merchant_id"], ["reg_z_12c", "expired_window", "revolving"], ["REGZ-1026.12"], """
- Network and billing-error windows had closed. Cardholder revolves a balance; after applying payments to non-disputed amounts first,
  **$248.00 of the purchase remained unpaid**. Same state; > $50; cardholder emailed merchant twice.""",
                         "Honored §1026.12(c) claim: cardholder may withhold $248.00; issuer credited and wrote off (no chargeback right).",
                         "Claims and defenses are limited to credit outstanding for the disputed purchase at the time of notice.",
                         "Contrast: a cardholder who pays in full each month has nothing outstanding to withhold.")
    # PRE-0019 Denver late cancellation
    hv = M("MER-90017")
    _closed_case(ctx, "DSP-2026-08019", pick[8], hv, "2026-07-20", "608.18", "cancelled_merch", "13.7", "partial_credit", "issuer_won",
                 "2026-07-22", "2026-09-01", "No-show billed after phone cancellation.", channel="card_not_present", pos_entry_mode="10",
                 cof_type="mit_unscheduled", time="11:00:00")
    P["PRE-0019"] = _doc("PRE-0019", "DSP-2026-08019", "Harbor & Vine no-show: cancellation call after hotel-local deadline", "2026-09-01", "13.7",
                         "partial_credit", "issuer_won (one night)", hv["merchant_id"], ["lodging", "no_show", "timezone"], ["VISA-13.7@2026-04-18"], """
- Cancel-by: 6:00 PM **hotel local time (ET)** two days before arrival.
- Cardholder in Denver called at 4:30 PM on their phone (**MT**) = 6:30 PM ET → after the deadline.
- Hotel billed two nights as no-show ($608.18).""",
                         "Filed 13.7 for $304.09 (the second night + tax) — billing a no-show for more than one night is improper regardless of timing. "
                         "First night stood.",
                         "Late cancellation made the first night valid; the more-than-one-night rule made the second night disputable.",
                         "Always convert the cardholder's call time into the hotel's time zone.")
    # PRE-0020 Reg E lost wallet tiers
    if debit:
        r = debit[0]
        pmer = byname("Circuitry Loft")
        _closed_case(ctx, "DSP-2026-08020", r, pmer, "2026-04-04", "420.00", "fraud_cnp", "10.4", "partial_credit", "issuer_won",
                     "2026-04-08", "2026-05-02", "Wallet stolen; card used before customer called.")
        P["PRE-0020"] = _doc("PRE-0020", "DSP-2026-08020", "Reg E: stolen debit card, notice after 2 business days", "2026-05-02", "10.4",
                             "partial_credit (liability $350)", "issuer_won", pmer["merchant_id"], ["reg_e", "lost_stolen", "liability_tiers"],
                             ["REGE-1005.6"], """
- Wallet stolen Friday 2026-04-03 (customer knew that evening). Customer notified bank Wednesday 2026-04-08.
- Unauthorized transfers: $120.00 on 04-04 (within 2 business days of learning) and $300.00 on 04-07 (after 2 business days).""",
                             "Liability $350.00 = $50 (lesser of $50 or transfers within 2 business days) + $300 (after 2 business days, before notice); capped at $500.",
                             "The 2-business-day tier applies because the **access device was lost/stolen**.",
                             "Does not apply when the card is still in the customer's possession (e.g., skimming / card-not-present compromise).")
    # PRE-0031 = the flawed ATO denial (C11 prior case) — written in the analyst's own words
    P["PRE-0031"] = _doc("PRE-0031", "DSP-2026-04471", "Kestrel Outdoor: merchant CE accepted, first-party misuse", "2026-06-02", "10.4", "denied",
                         "merchant_won_pre_arb", "MER-90013", ["fraud_cnp", "CE3.0", "first_party_misuse"], ["VISA-10.4@2026-04-18"], """
- Cardholder disputed $612.00 online purchase. Merchant pre-arbitration: order placed from the cardholder's merchant account login;
  IP "198.18.201.x" matched prior orders; AVS Y.
- Cardholder "could not explain" the order.""",
                         "Accepted pre-arbitration. Re-billed $612.00. Memory note added: heightened scrutiny for future CNP fraud claims.",
                         "Merchant CE indicates returning customer from matching IP; treated as first-party misuse.",
                         "Shipping address on the merchant packet was not reviewed. (Recorded as written by analyst.lpetrov.)")


def build_templated_precedents(ctx: Ctx, n=28):
    closed = [dd for dd in ctx.t["disputes"] if dd["status"] == "closed" and dd["case_id"].startswith(("DSP-2026-0", "DSP-2025-0"))
              and not dd["case_id"].startswith(("DSP-2026-08", "DSP-2025-08"))]
    notes = {}
    for ev in ctx.t["dispute_events"]:
        if ev["event_type"] == "case_closed" and ev["detail"]:
            notes[ev["case_id"]] = ev["detail"].get("note", "")
    fams_seen = {}
    k = 100
    for dsp in closed:
        fam = dsp["claim_family_initial"]
        if fams_seen.get(fam, 0) >= 4 or dsp["case_id"] not in notes:
            continue
        fams_seen[fam] = fams_seen.get(fam, 0) + 1
        k += 1
        pid = f"PRE-0{k}"
        txn_id = next(x["txn_id"] for x in ctx.t["dispute_transactions"] if x["case_id"] == dsp["case_id"])
        t = ctx.get("transactions", txn_id)
        ctx.precedents[pid] = _doc(pid, dsp["case_id"], f"{fam.replace('_', ' ').title()}: {t['descriptor']} ${dsp['dispute_amount']}",
                                   dsp["closed_at"][:10], dsp["network_condition"], dsp["cardholder_outcome"], dsp["network_outcome"],
                                   t["merchant_id"], [fam], [f"VISA-{dsp['network_condition']}@{'2026-04-18' if dsp['closed_at'] >= '2026-04-18' else '2025-10'}"]
                                   if dsp["network_condition"] else [], f"- {dsp['claim_summary']}\n- Transaction {txn_id}: {t['descriptor']} "
                                   f"${t['billing_amount']} on {t['txn_local_datetime'][:10]} ({t['channel']}).",
                                   f"Cardholder outcome: {dsp['cardholder_outcome']}. Network outcome: {dsp['network_outcome']}.",
                                   "Routine application of the condition's evidence requirements.", notes[dsp["case_id"]])
        if k - 100 >= n:
            break
