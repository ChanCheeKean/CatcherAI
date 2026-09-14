"""Hero cases C09–C12b."""
from __future__ import annotations

import background as bg
from common import Ctx, add_days, d, m, money, utc
from heroes.kit import AS_OF_ISO, full_address, person, persona, research, truth


def _merchant_by_name(ctx: Ctx, name: str) -> dict:
    return next(r for r in ctx.t["merchants"] if r["dba_name"] == name)


# =====================================================================================================
def c09_ce3_clock(ctx: Ctx):
    p = person(ctx, 90009, "Kiran Tamura-Bell", "Los Angeles", "2021-04-07", cycle_day=6, ip="198.18.77.140")
    tz = "America/Los_Angeles"
    games = bg.make_merchant(ctx, "Nebula Forge Games", "5816", "ecommerce", "Seattle", merchant_id="MER-90009",
                             descriptor="NEBULA FORGE*GAMES", acquirer_id="ACQ-07", onboarded="2019-02-01",
                             website="https://store.nebulaforge.example", is_hero=True, legal_suffix=" Interactive Inc")
    arcade = bg.make_merchant(ctx, "Nebula Forge Arcade", "5816", "ecommerce", "Seattle", merchant_id="MER-90010",
                              descriptor="NEBULA FORGE*ARCADE", acquirer_id="ACQ-07", onboarded="2022-06-01",
                              website="https://arcade.nebulaforge.example", is_hero=True, legal_suffix=" Interactive Inc",
                              parent="MER-90009")
    ecom = dict(channel="ecommerce", eci="07", avs_result="Y", cvv2_presence="1", cvv2_result="M", cavv_present=False,
                three_ds_status="")
    pr1 = bg.add_txn(ctx, p.acct, p.card, arcade, "2026-03-20", "19:31:00", "14.99", txn_id="TXN-9000901", is_hero=True, **ecom)
    pr2 = bg.add_txn(ctx, p.acct, p.card, games, "2026-05-15", "21:04:00", "29.99", txn_id="TXN-9000902", is_hero=True, **ecom)
    pr3 = bg.add_txn(ctx, p.acct, p.card, games, "2026-09-10", "20:47:00", "9.99", txn_id="TXN-9000903", is_hero=True, **ecom)
    txn = bg.add_txn(ctx, p.acct, p.card, games, "2026-10-02", "20:18:00", "69.99", txn_id="TXN-9000904", is_hero=True, **ecom)
    # issuer-side corroboration: banking app login from the same home IP the same evening
    bg.add_event(ctx, p.cust["customer_id"], p.acct["account_id"], "login_success", utc("2026-10-02", "21:05:00", tz),
                 channel="web", device_id=p.laptop["device_id"], ip=p.ip, detail={"auth_method": "password"}, is_hero=True)
    # prior fraud disputes on digital goods (both won)
    for cid, mname, day, amt, opened in (("DSP-2026-90901", "Sparkden Games", "2026-01-09", "49.99", "2026-01-22"),
                                        ("DSP-2026-90902", "Voidline Media", "2026-06-03", "24.99", "2026-06-15")):
        pm = _merchant_by_name(ctx, mname)
        t = bg.add_txn(ctx, p.acct, p.card, pm, day, "22:10:00", amt, **ecom)
        bg.add_dispute(ctx, cid, [t], "REG_Z", utc(opened, "10:00:00"), "Did not authorize digital purchase.", "fraud_cnp",
                       status="closed", stage="closed", network_condition="10.4", dispute_processing_date=add_days(opened, 3),
                       cardholder_outcome="credited", network_outcome="issuer_won",
                       closed_at=utc(add_days(opened, 40), "16:00:00"), assigned_queue="fraud_cnp")
        bg.add_devent(ctx, cid, utc(add_days(opened, 40), "16:00:00"), "case_closed",
                      "Closed: credited; merchant did not respond to dispute",
                      detail={"note": "Merchant did not respond within 30 days. Chargeback stood."})
    case = "DSP-2026-90010"
    intake = utc("2026-10-19", "17:42:00", tz)
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Did not authorize Nebula Forge Games purchase $69.99.", "fraud_cnp",
                   intake_channel="phone", intake_authenticated_via="ivr_otp", assigned_queue="fraud_cnp",
                   stage="investigating", provisional_credit_amount="69.99",
                   provisional_credit_at=utc("2026-10-20", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: unauthorized digital goods purchase")
    bg.add_devent(ctx, case, utc("2026-10-20", "10:00:00"), "provisional_credit_posted", "Temporary credit 69.99 posted")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Cardholder says they did not buy 'Starfall Tactics Deluxe' from Nebula Forge for $69.99 on 10/2. Card in "
                "possession. When asked, said nobody else uses their PC and they haven't shared account passwords.",
                case_id=case, merchant_id=games["merchant_id"], subject="Unauthorized game purchase")
    dev_id, dev_fp = "IMEI-NA", "fp_" + "c0ffee1d" * 5
    ce = lambda t, desc: dict(txn_date=t["txn_local_datetime"][:10], merchant=t["descriptor"], acquirer_id="ACQ-07",
                              amount=t["billing_amount"], description=desc, login_id="kestrelmoon", ip=p.ip,
                              device_id="PCID-7F3A9C21B8E04D55", device_fingerprint=dev_fp, delivery_address="(digital)",
                              disputed=False, reported_fraud=False)
    bg.add_packet(ctx, "MEP-90010-OI", case, txn["txn_id"], games["merchant_id"], "order_insight",
                  utc("2026-10-20", "09:00:00"), utc("2026-10-20", "18:30:00"), dict(
                      order=dict(order_id="NFG-1188230", placed_at=utc("2026-10-02", "20:17:44", tz),
                                 items=[dict(sku="STFT-DLX", description="Starfall Tactics — Deluxe Edition (PC digital download)", price="69.99")]),
                      customer_account=dict(login_id="kestrelmoon", email=p.cust["email"], account_created_at="2021-11-30T04:12:00Z",
                                            email_verified=True, account_changes_last_90d=[]),
                      session=dict(ip=p.ip, device_id="PCID-7F3A9C21B8E04D55", device_fingerprint=dev_fp,
                                   user_agent="NebulaForgeLauncher/4.2 (Windows 11)"),
                      digital_usage=dict(first_launch=utc("2026-10-02", "20:41:00", tz), total_playtime_hours="37.5",
                                         sessions=19, last_session=utc("2026-10-18", "23:10:00", tz),
                                         achievements_unlocked=14, device_id="PCID-7F3A9C21B8E04D55"),
                      prior_transactions=[ce(pr1, "Nebula Forge Arcade — 'Cosmic Pinball' season pass"),
                                          ce(pr2, "Nebula Forge Games — 'Starfall Tactics' base game"),
                                          ce(pr3, "Nebula Forge Games — 'Starfall Tactics' soundtrack DLC")],
                      compelling_evidence_claim=dict(framework="Visa CE 3.0", matching_elements=["login_id", "ip_address", "device_id",
                                                                                                 "device_fingerprint"],
                                                     merchant_assertion="4 matching data elements across 3 prior undisputed transactions"),
                      merchant_statement="Purchase made from the customer's long-standing account on their usual PC and IP; "
                                         "game actively played for 37.5 hours."))
    research(ctx, "WEB-04163", "Nebula Forge Store — Refund Policy", "https://store.nebulaforge.example/refunds",
             "Nebula Forge Interactive", "2025-03-01", "2026-10-20", "merchant_policy", """
Digital games can be refunded if requested **within 14 days of purchase and with less than 2 hours of playtime**.
Technical issues: contact support with your system specs; we'll troubleshoot and may offer a refund or store credit
at our discretion if the game cannot run on supported hardware.
""", games["merchant_id"])
    persona(ctx, case, p.cust["customer_id"],
            profile="Adult gamer; bought the game, regrets it because it crashes; filed fraud claim because it was faster.",
            knows=["Bought the game on 2026-10-02", "Game crashes frequently since a patch on 10-15", "Never contacted Nebula Forge support"],
            disclosure_rules=["Maintains 'unauthorized' until shown specific evidence (account, IP, playtime)",
                              "When shown evidence, admits purchase and switches to a quality complaint",
                              "Does not reply to generic questions for 3 days"],
            scripted_replies=[
                dict(trigger="agent shares specific participation evidence (login/IP/device/playtime) and asks for explanation",
                     delay_minutes=1500, reply="OK, fine, I might have bought it, but the game is broken and keeps crashing. I want my money back."),
                dict(trigger="agent asks generic question without evidence", delay_minutes=4320,
                     reply="I already told you I didn't buy it.")],
            style="terse, defensive")
    truth(ctx, case, code="C09", title="The Clock on CE 3.0", depth="L3", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="CNP 'fraud' on digital goods. Network validity depends on the CE 3.0 version in force on the dispute processing "
                  "date (old: same merchant; new from 2026-10-24: multi-merchant, same acquirer). Independently, Reg Z "
                  "investigation shows participation; cardholder admits purchase when shown evidence and switches to a quality "
                  "complaint that must go to the merchant first.",
          expected=dict(is_dispute=False, claim_family="fraud_cnp_withdrawn_then_quality_complaint",
                        network_actions=[dict(txn_id=txn["txn_id"], action="no_dispute",
                                              reason="cardholder participated; fraud claim withdrawn; quality complaint requires merchant contact first")],
                        cardholder_resolution=dict(outcome="denied_with_explanation", reversal_amount="69.99",
                                                   note="reverse temporary credit with Reg Z explanation; direct to merchant support/refund policy"),
                        ce3_analysis=dict(version_if_processed_by_2026_10_23="VISA-10.4@2026-04-18", qualifies_old=False,
                                          version_if_processed_from_2026_10_24="VISA-10.4@2026-10-24", qualifies_new=True,
                                          qualifying_priors=["TXN-9000901", "TXN-9000902"], excluded_priors=[dict(txn_id="TXN-9000903", reason="<120 days")],
                                          matching_elements_counted=["ip_address", "login_id"],
                                          note="device ID and device fingerprint count as one element under the new version"),
                        memory_write=dict(scope="customer", subject_id=p.cust["customer_id"], type="factual_event",
                                          content_contains=["retracted", "2026-10-22"], forbidden_terms=["fraudster", "abuser", "liar"]),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Order from long-standing merchant account kestrelmoon, home IP 198.18.77.140", evidence=["MEP-90010-OI"]),
                     dict(id="F2", fact="37.5 hours playtime on the same device after purchase", evidence=["MEP-90010-OI.digital_usage"]),
                     dict(id="F3", fact="Issuer web login from same IP at 21:05 PT on purchase day", evidence=["account_events"]),
                     dict(id="F4", fact="Two prior digital fraud disputes in 2026 won because merchants did not respond", evidence=["DSP-2026-90901", "DSP-2026-90902"]),
                     dict(id="F5", fact="Arcade prior (2026-03-20) is a different merchant but same acquirer ACQ-07", evidence=["merchants MER-90010"])],
          contradictions=[dict(id="X1", between=["cardholder: did not authorize", "account/IP/device/playtime"], resolution="cardholder admits purchase on evidence review"),
                          dict(id="X2", between=["merchant: 4 matching elements", "VISA-10.4@2026-10-24 footnote"], resolution="device ID and fingerprint are one element")],
          pivots=[dict(at="cardholder reply 2026-10-22", from_="fraud_cnp", to="quality complaint (non-fraud)", trigger="admission")],
          computations=[dict(name="earliest_realistic_dispute_processing_date", value="2026-10-26",
                             rule="evidence review contact required; 2026-10-24 is Saturday"),
                        dict(name="days_prior_TXN-9000901_to_2026-10-26", value=(d("2026-10-26") - d("2026-03-20")).days),
                        dict(name="days_prior_TXN-9000902_to_2026-10-26", value=(d("2026-10-26") - d("2026-05-15")).days),
                        dict(name="days_prior_TXN-9000903_to_2026-10-26", value=(d("2026-10-26") - d("2026-09-10")).days)],
          must_cite=["VISA-10.4@2026-04-18", "VISA-10.4@2026-10-24", "REGZ-1026.12", "REGZ-1026.13-INTERP", "LFB-SOP-DSP-004@v2"],
          must_not=["file 10.4 before 2026-10-24 to exploit the old rule", "count device ID and fingerprint as two elements",
                    "label the customer a fraudster in memory or letters", "deny solely for non-response"],
          components=["policy_versioning", "sandbox (date math)", "user_simulation", "replan on claim change",
                      "fairness guardrail", "memory_write (factual)"],
          deterministic_checks=[dict(path="network_actions[0].action", op="eq", value="no_dispute"),
                                dict(path="ce3_analysis.version_if_processed_from_2026_10_24", op="eq", value="VISA-10.4@2026-10-24"),
                                dict(path="memory_ops[*].content", op="not_contains_any", value=["fraudster", "abuser", "liar"])],
          rubric=["Separates network liability from the Reg Z factual determination", "Neutral, non-accusatory language"],
          budget=dict(expected_tool_calls="10-20"))


# =====================================================================================================
def c10_family_tablet(ctx: Ctx):
    p = person(ctx, 90010, "Wren Galloway-Chen", "Columbus", "2013-09-01", cycle_day=18, tablet=True,
               employer="Cobalt Ridge Health")
    au = bg.make_customer(ctx, "Columbus", customer_id="CUS-90011", full_name="Jules Galloway-Chen", since="2016-02-01",
                          address=p.addr, is_hero=True)
    ctx.add("account_holders", dict(account_id=p.acct["account_id"], customer_id="CUS-90011", role="authorized_user",
                                    added_at="2016-02-01"))
    au_card = bg.make_card(ctx, p.acct, au, role="authorized_user", card_id="CRD-90011", issued_at="2016-02-01")
    bg.make_device(ctx, "phone", "CUS-90011", "2016-02-01", device_id="DEV-90011-PH")
    tz = "America/New_York"
    mer = bg.make_merchant(ctx, "Pixelhollow Studios", "5816", "ecommerce", "Austin", merchant_id="MER-90011",
                           descriptor="PIXELHOLLOW*SKYFALL", acquirer_id="ACQ-07", onboarded="2020-08-01",
                           website="https://www.pixelhollow.example", is_hero=True)
    first = bg.add_txn(ctx, p.acct, p.card, mer, "2026-02-14", "18:31:00", "4.99", channel="ecommerce", txn_id="TXN-9001000",
                       cof_type="cit_initial", eci="07", avs_result="Y", cvv2_presence="1", cvv2_result="M", is_hero=True)
    # tablet banking logins by the primary cardholder (household device)
    for day in ("2026-07-12", "2026-08-30", "2026-09-19"):
        bg.add_event(ctx, p.cust["customer_id"], p.acct["account_id"], "login_success", utc(day, "20:15:00"),
                     channel="mobile_app", device_id=p.tablet["device_id"], ip=p.ip, detail={"auth_method": "passcode"}, is_hero=True)
    amounts = ["9.99", "4.99", "19.99", "9.99", "49.99", "4.99", "9.99", "19.99", "24.99", "4.99", "9.99", "49.99",
               "19.99", "9.99", "4.99", "36.99", "19.99", "9.99", "49.99", "24.99", "19.99", "44.99", "24.99"]
    days = ["2026-09-26", "2026-09-26", "2026-09-27", "2026-09-27", "2026-09-27", "2026-09-28", "2026-09-29", "2026-09-29",
            "2026-09-30", "2026-09-30", "2026-10-01", "2026-10-01", "2026-10-01", "2026-10-02", "2026-10-02", "2026-10-02",
            "2026-10-03", "2026-10-03", "2026-10-03", "2026-10-04", "2026-10-04", "2026-10-04", "2026-10-04"]
    assert len(amounts) == len(days) == 23
    txns = []
    for i, (day, amt) in enumerate(zip(days, amounts)):
        txns.append(bg.add_txn(ctx, p.acct, p.card, mer, day, f"{15 + (i % 6):02d}:{(i * 7) % 60:02d}:00", amt, channel="ecommerce",
                               txn_id=f"TXN-90010{i + 1:02d}", cof_type="cit_subsequent", eci="07", avs_result="",
                               cvv2_presence="0", cvv2_result="", cavv_present=False, three_ds_status="", is_hero=True))
    total = sum(money(t["billing_amount"]) for t in txns)
    assert str(total) == "486.77", total
    case = "DSP-2026-90011"
    intake = utc("2026-10-07", "18:05:00")
    bg.add_dispute(ctx, case, txns, "REG_Z", intake, "23 Pixelhollow in-game purchases ($486.77) made by cardholder's child without permission.",
                   "fraud_cnp", intake_channel="phone", intake_authenticated_via="ivr_otp", assigned_queue="fraud_cnp",
                   stage="investigating", provisional_credit_amount="486.77", provisional_credit_at=utc("2026-10-09", "10:00:00"),
                   is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: unauthorized purchases by minor")
    bg.add_devent(ctx, case, utc("2026-10-08", "09:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent")
    bg.add_devent(ctx, case, utc("2026-10-09", "10:00:00"), "provisional_credit_posted", "Temporary credit 486.77 posted")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Cardholder is upset: their 13-year-old made 23 purchases in the game 'Skyfall Isles' (Pixelhollow) on the family "
                "tablet between 9/26 and 10/4 totalling $486.77. 'I never gave him my card. He did this without permission.' "
                "Wants all charges reversed. Cardholder has since taken the tablet away.", case_id=case,
                merchant_id=mer["merchant_id"], subject="Child made purchases")
    bg.add_packet(ctx, "MEP-90011-OI", case, txns[0]["txn_id"], mer["merchant_id"], "order_insight",
                  utc("2026-10-09", "11:00:00"), utc("2026-10-12", "15:00:00"), dict(
                      customer_account=dict(login_id="skyfall_kid", email="sky.w.gamer@example.net", account_created_at=utc("2025-12-26", "10:02:00"),
                                            age_gate="declared 13+", parental_controls="not enabled"),
                      payment_method_events=[dict(ts=utc("2026-02-14", "18:29:10"), event="card_added", card_last4=p.card["last4"],
                                                  device_fingerprint=p.phone["device_fingerprint"], ip=p.ip,
                                                  note="card saved for future purchases (checkbox checked)")],
                      purchases=dict(count=24, first=utc("2026-02-14", "18:31:00"), disputed_window="2026-09-26..2026-10-04",
                                     device_fingerprint_for_disputed=p.tablet["device_fingerprint"], ip=p.ip),
                      merchant_statement="Card was added to the account by the device and IP later used for the purchases' household; "
                                         "purchases made by an authorized household member. We offer a one-time minor refund on request."))
    research(ctx, "WEB-04170", "Pixelhollow Support — Purchases made by a minor", "https://support.pixelhollow.example/minor-purchases",
             "Pixelhollow Studios", "2025-06-10", "2026-10-01", "merchant_help", """
If a child made purchases in one of our games without a parent's permission, a parent or guardian may request a
**one-time courtesy refund of purchases made within the last 30 days**. Submit the account ID and the purchase
receipts via the form. Refunds are returned to the original payment method within 5–7 business days, and the
account will be restricted to require a parental PIN for future purchases.
""", mer["merchant_id"])
    persona(ctx, case, p.cust["customer_id"],
            profile="Parent, distressed and embarrassed; genuinely didn't expect the child to keep buying.",
            knows=["Added the card in February for a $4.99 purchase and told the child to ask every time",
                   "Did not know the card stayed saved", "Has not contacted Pixelhollow"],
            disclosure_rules=["Only mentions the February card entry if asked specifically whether the card was ever entered in the game",
                              "Becomes defensive if the word 'fraud' is used about them or the child"],
            scripted_replies=[
                dict(trigger="agent asks whether card was ever added to the game account", delay_minutes=120,
                     reply="I put it in once in February for a $4.99 skin for his birthday, but I told him he had to ask me every time. I didn't know it stayed saved."),
                dict(trigger="agent suggests Pixelhollow minor refund", delay_minutes=60,
                     reply="I didn't know that existed. I'll do it tonight. Can you still help with anything they won't refund?")],
            style="emotional, cooperative")
    truth(ctx, case, code="C10", title="The Family Tablet", depth="L4", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[t["txn_id"] for t in txns],
          summary="Child's in-game purchases after the cardholder saved the card to the child's account. Reg Z apparent/implied "
                  "authority (comment 12(b)(1)(ii)-3) vs 'never gave permission'; Visa CE item 11 (household member) would "
                  "defeat 10.4 at pre-arb; merchant offers one-time minor refund for purchases in last 30 days (closing).",
          expected=dict(is_dispute=False, claim_family="household_member_purchases",
                        network_actions=[dict(txn_id="TXN-9001001..TXN-9001023", action="no_dispute",
                                              reason="purchases by a person given apparent/implied authority; household-member compelling evidence would defeat 10.4")],
                        cardholder_resolution=dict(outcome="denied_with_explanation", reversal_amount="486.77",
                                                   note="reverse temporary credit with Reg Z explanation and grace period; record 2026-10-07 as notice that the "
                                                        "child's use is no longer authorized (future purchases would be unauthorized)"),
                        cardholder_guidance=dict(merchant_minor_refund=dict(source="WEB-04170", earliest_purchase_deadline="2026-10-26",
                                                                            last_purchase_deadline="2026-11-03"),
                                                 card_controls=["remove stored card from game account", "optional card number reissue"]),
                        adjudication=dict(review_panel_required=True, reason="authority/household determination (SOP-DSP-003 §2.3)",
                                          min_confidence=0.75, conservative_default_applied=False,
                                          flip_fact="evidence that the card was never saved or used with the cardholder's permission (cf. PRE-0010)"),
                        follow_ups=[dict(at="2026-11-04", action="check for Pixelhollow credits on the account and send a confirmation",
                                         optional=True)]),
          key_facts=[dict(id="F1", fact="Card saved to child's game account on 2026-02-14 from primary cardholder's phone and home IP", evidence=["MEP-90011-OI.payment_method_events"]),
                     dict(id="F2", fact="Disputed purchases from family tablet also used for primary's banking logins", evidence=["MEP-90011-OI.purchases", "account_events DEV-90010-TB"]),
                     dict(id="F3", fact="$4.99 February purchase not disputed", evidence=["TXN-9001000"]),
                     dict(id="F4", fact="Merchant minor-refund window: 30 days from purchase", evidence=["WEB-04170"])],
          hypotheses=[dict(id="H1", label="unauthorized use (no authority given)", for_=["cardholder statement"], against=["card saved by cardholder", "prior use"]),
                      dict(id="H2", label="authority given then exceeded", for_=["card saved by cardholder in Feb", "household device"], against=["cardholder told child to ask"])],
          computations=[dict(name="refund_window_first_purchase_ends", value="2026-10-26"),
                        dict(name="refund_window_last_purchase_ends", value="2026-11-03"),
                        dict(name="total", value="486.77")],
          must_cite=["REGZ-1026.12", "VISA-11.5.1-COMPELLING-EVIDENCE@2026-04-18", "LFB-CARDHOLDER-AGREEMENT@2025-01",
                     "LFB-SOP-DSP-003@v6", "LFB-SOP-DSP-004@v2"],
          must_not=["file 10.4", "decide without running the review panel", "use age of cardholder or child as a risk signal",
                    "describe cardholder or child as fraudulent", "omit the merchant refund deadline", "wait for a human"],
          precedents=dict(distinguish=["PRE-0010"]),
          components=["competing_hypotheses", "automated review panel (advocates + adjudicator)", "verifier", "research",
                      "user_simulation", "fairness guardrail", "graph (household devices)", "scheduled follow-up"],
          deterministic_checks=[dict(path="network_actions[0].action", op="eq", value="no_dispute"),
                                dict(path="cardholder_resolution.outcome", op="eq", value="denied_with_explanation"),
                                dict(path="adjudication.review_panel_used", op="eq", value=True),
                                dict(path="explanation_for_cardholder", op="contains_text", value="2026-10-26")],
          rubric=["Adjudication record lists both hypotheses with evidence and the flip fact", "Tone is supportive and non-accusatory"],
          budget=dict(expected_tool_calls="10-20"))


# =====================================================================================================
def c11_ato(ctx: Ctx):
    p = person(ctx, 90012, "Rowan Okonkwo-Bell", "Brooklyn", "2017-05-22", cycle_day=21, line1="311 Carroll Bend St",
               line2="Apt 11C", postal="11231", ip="198.18.201.7", phone_slot=90)
    bg.add_ip(ctx, "198.18.201.7", "residential_cgnat", "Metrolink Fiber", "Brooklyn", "ISP uses carrier-grade NAT in this /24; shared by many households")
    bg.add_ip(ctx, "198.18.201.44", "residential_cgnat", "Metrolink Fiber", "Brooklyn", "ISP uses carrier-grade NAT in this /24; shared by many households")
    bg.add_ip(ctx, "203.0.113.58", "hosting_vpn", "Nimbuscloud VPS", "", "commercial VPN exit node")
    tz = "America/New_York"
    orbital = bg.make_merchant(ctx, "Orbital Audio", "5732", "ecommerce", "Chicago", merchant_id="MER-90012",
                               descriptor="ORBITAL AUDIO", acquirer_id="ACQ-01", onboarded="2018-01-01",
                               website="https://www.orbitalaudio.example", is_hero=True)
    kestrel = bg.make_merchant(ctx, "Kestrel Outdoor Supply", "5999", "ecommerce", "Denver", merchant_id="MER-90013",
                               descriptor="KESTREL OUTDOOR SUPPLY", acquirer_id="ACQ-04", onboarded="2017-01-01", is_hero=True)
    drop = bg.make_address(ctx, "Jersey City", line1="88 Wharfside Ave", line2="Unit 2", postal="07302",
                           address_type="commercial_mail_drop", address_id="ADR-DROP-WHARFSIDE")
    drop_s = full_address(drop)
    home_s = full_address(p.addr)
    ecom = dict(channel="ecommerce", eci="07", cvv2_presence="1", cvv2_result="M", cavv_present=False, three_ds_status="")
    pr1 = bg.add_txn(ctx, p.acct, p.card, orbital, "2026-01-19", "19:12:00", "89.00", avs_result="Y", txn_id="TXN-9001201", is_hero=True, **ecom)
    pr2 = bg.add_txn(ctx, p.acct, p.card, orbital, "2026-04-22", "20:40:00", "149.00", avs_result="Y", txn_id="TXN-9001202", is_hero=True, **ecom)
    # ---- prior case (flawed denial), June 2026
    old = bg.add_txn(ctx, p.acct, p.card, kestrel, "2026-05-03", "03:22:00", "612.00", avs_result="Y", txn_id="TXN-9001203", is_hero=True, **ecom)
    oc = "DSP-2026-04471"
    bg.add_dispute(ctx, oc, [old], "REG_Z", utc("2026-05-07", "12:00:00"), "Did not authorize Kestrel Outdoor Supply purchase $612.00.",
                   "fraud_cnp", status="closed", stage="closed", network_condition="10.4", dispute_processing_date="2026-05-09",
                   response_processing_date="2026-05-28", cardholder_outcome="denied", network_outcome="merchant_won_pre_arb",
                   closed_at=utc("2026-06-02", "17:00:00"), assigned_queue="fraud_cnp", provisional_credit_amount="612.00",
                   provisional_credit_at=utc("2026-05-08", "10:00:00"))
    for ts, et, sm, note in (("2026-05-07T16:00:00Z", "intake_created", "Phone intake: unauthorized online purchase", ""),
                             ("2026-05-28T20:00:00Z", "dispute_response_received", "Merchant pre-arbitration with compelling evidence", ""),
                             ("2026-06-02T21:00:00Z", "case_closed", "Closed: denied; merchant CE accepted",
                              "Merchant CE: order from cardholder's merchant account login; IP matches prior order (198.18.201.x); "
                              "AVS Y. Cardholder could not explain. Treated as first-party misuse. Re-billed $612.00.")):
        bg.add_devent(ctx, oc, ts, et, sm, actor="analyst.lpetrov", detail={"note": note} if note else {})
    bg.add_packet(ctx, "MEP-04471-PA", oc, old["txn_id"], kestrel["merchant_id"], "pre_arbitration", "2026-05-09T00:00:00Z",
                  "2026-05-28T20:00:00Z", dict(customer_account=dict(login_id=p.cust["email"].split("@")[0]),
                                               session=dict(ip="198.18.201.x"), shipping_address=drop_s,
                                               merchant_statement="Returning customer account; IP match; AVS Y."))
    # ---- two other customers' fraud disputes shipped to the drop address
    others = [r for r in ctx.people if r["city"] in ("Brooklyn", "Jersey City")][:2]
    for i, r in enumerate(others):
        day = ["2026-07-18", "2026-10-06"][i]
        mm = _merchant_by_name(ctx, ["Pixelwave Electronics", "Solewright"][i])
        t = bg.add_txn(ctx, r["accounts"][0], r["cards"][0], mm, day, "02:5%d:00" % i, ["780.00", "265.00"][i], avs_result="Y", **ecom)
        dcid = f"DSP-2026-0{9301 + i}"
        closed = i == 0
        bg.add_dispute(ctx, dcid, [t], r["accounts"][0]["regime"], utc(add_days(day, 3), "10:00:00"),
                       "Did not authorize online purchase; received password reset emails I didn't request.", "fraud_cnp",
                       status="closed" if closed else "open", stage="closed" if closed else "dispute_filed",
                       network_condition="10.4", dispute_processing_date=add_days(day, 5),
                       cardholder_outcome="credited" if closed else "", network_outcome="issuer_won" if closed else "",
                       closed_at=utc(add_days(day, 35), "16:00:00") if closed else "", assigned_queue="fraud_cnp")
        bg.add_packet(ctx, f"MEP-0{9301 + i}-OI", dcid, t["txn_id"], mm["merchant_id"], "order_insight", "", utc(add_days(day, 4), "12:00:00"),
                      dict(shipping_address=drop_s, customer_account=dict(login_id="(existing account)", email_changed_recently=True),
                           merchant_statement="Order shipped to address on account."))
        ctx.bg_labels.append(dict(case_id=dcid, family="fraud_cnp", true_nature="account_takeover_drop_address",
                                  expected_network_condition="10.4", expected_cardholder_outcome="credited",
                                  status="closed" if closed else "open", historical_decision_correct=True))
    ctx.bg_labels.append(dict(case_id=oc, family="fraud_cnp", true_nature="account_takeover_drop_address",
                              expected_network_condition="10.4", expected_cardholder_outcome="credited", status="closed",
                              historical_decision_correct=False))
    # ---- issuer security events around the takeover
    cid, aid = p.cust["customer_id"], p.acct["account_id"]
    bg.add_event(ctx, cid, aid, "phone_changed", utc("2026-10-12", "16:44:00", tz), channel="ivr",
                 detail={"old_phone_last2": "90", "new_phone": "(929) 555-0197", "verification": "knowledge_based_questions_passed"}, is_hero=True)
    for k in range(3):
        bg.add_event(ctx, cid, aid, "login_failed", utc("2026-10-14", f"01:5{k}:10", tz), channel="web", ip="203.0.113.58",
                     device_id="", detail={"reason": "bad_password"}, is_hero=True)
    bg.add_event(ctx, cid, aid, "password_reset", utc("2026-10-14", "01:54:30", tz), channel="web", ip="203.0.113.58",
                 detail={"method": "sms_otp", "otp_sent_to": "(929) 555-0197"}, is_hero=True)
    bg.add_event(ctx, cid, aid, "login_success", utc("2026-10-14", "01:55:02", tz), channel="web", ip="203.0.113.58",
                 detail={"new_device": True, "device_fingerprint": "fp_" + "5ba7e11e" * 5}, is_hero=True)
    bg.add_event(ctx, cid, aid, "alert_sent", utc("2026-10-14", "02:41:40", tz), channel="sms",
                 detail={"alert": "large_purchase", "amount": "1389.00", "sent_to": "(929) 555-0197"}, is_hero=True)
    bg.add_event(ctx, cid, aid, "login_failed", utc("2026-10-15", "08:58:00", tz), channel="mobile_app",
                 device_id=p.phone["device_id"], ip=p.ip, detail={"reason": "bad_password"}, is_hero=True)
    txn = bg.add_txn(ctx, p.acct, p.card, orbital, "2026-10-14", "01:41:00", "1389.00", avs_result="Y", txn_id="TXN-9001204",
                     is_hero=True, **ecom)  # merchant in Chicago: 01:41 CT = 02:41 ET
    case = "DSP-2026-90012"
    intake = utc("2026-10-15", "09:10:00", tz)
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Did not authorize Orbital Audio $1,389.00; locked out of online banking.",
                   "fraud_cnp", intake_channel="phone", intake_authenticated_via="branch_callback_verified_id",
                   assigned_queue="fraud_cnp", stage="investigating", related_case_ids="DSP-2026-04471", is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: unauthorized purchase; customer locked out")
    bg.add_devent(ctx, case, utc("2026-10-15", "09:30:00", tz), "note_added",
                  "System flag: customer has prior denied fraud claim DSP-2026-04471 (first-party misuse). Memory note MEM-0142 attached.",
                  actor="system")
    bg.add_comm(ctx, cid, intake, "inbound", "phone_summary", "cardholder",
                "Customer can't log in to the app since this morning ('password incorrect'). Sees a $1,389.00 charge from Orbital "
                "Audio yesterday at 2:41 AM — was asleep. Has bought from Orbital before (earbuds, a speaker) but not this. Has not "
                "received any texts from us recently — says their phone has had 'no service' since Monday evening.",
                case_id=case, merchant_id=orbital["merchant_id"], subject="Unauthorized purchase / locked out")
    bg.add_packet(ctx, "MEP-90012-OI", case, txn["txn_id"], orbital["merchant_id"], "order_insight", utc("2026-10-15", "11:00:00", tz),
                  utc("2026-10-16", "15:30:00", tz), dict(
                      order=dict(order_id="OA-2231876", placed_at=utc("2026-10-14", "02:40:51", tz),
                                 items=[dict(description="Halcyon ANC Pro headphones", price="549.00"),
                                        dict(description="Monolith 360 smart speaker (pair)", price="840.00")]),
                      customer_account=dict(login_id=p.cust["email"].split("@")[0], account_created_at="2024-11-02T15:00:00Z",
                                            account_status="verified"),
                      account_activity_last_24h=[dict(ts=utc("2026-10-14", "01:57:40", tz), event="login_new_device",
                                                       device_fingerprint="fp_" + "5ba7e11e" * 5),
                                                 dict(ts=utc("2026-10-14", "01:58:12", tz), event="password_reset"),
                                                 dict(ts=utc("2026-10-14", "02:05:31", tz), event="email_changed",
                                                      new_email="r.okonkwo.bell.alerts@example.org"),
                                                 dict(ts=utc("2026-10-14", "02:39:02", tz), event="shipping_address_added", address=drop_s)],
                      session=dict(ip_match="198.18.201.x", ip_note="matches prior orders (subnet)", device_fingerprint="fp_" + "5ba7e11e" * 5),
                      shipping_address=drop_s,
                      prior_transactions=[dict(txn_date="2026-01-19", amount="89.00", login_id=p.cust["email"].split("@")[0], ip="198.18.201.7",
                                               device_fingerprint=p.laptop["device_fingerprint"], delivery_address=home_s, disputed=False),
                                          dict(txn_date="2026-04-22", amount="149.00", login_id=p.cust["email"].split("@")[0], ip="198.18.201.7",
                                               device_fingerprint=p.phone["device_fingerprint"], delivery_address=home_s, disputed=False)],
                      compelling_evidence_claim=dict(framework="Visa CE 3.0", matching_elements=["login_id", "ip_address"],
                                                     merchant_assertion="Returning verified customer; CE 3.0 criteria met; first-party misuse suspected"),
                      shipments=[dict(carrier="Swiftline Freight", tracking_number="SW772019341", events=[
                          dict(ts=utc("2026-10-14", "15:00:00", tz), status="shipped"),
                          dict(ts=utc("2026-10-16", "12:31:00", tz), status="delivered", address=drop_s)])],
                      merchant_statement="Order placed through the cardholder's own verified account from a matching IP."))
    truth(ctx, case, code="C11", title="Takeover in a Friendly Mask", depth="L4", regime="REG_Z", customer_id=cid,
          txn_ids=[txn["txn_id"]],
          summary="Merchant asserts CE 3.0 friendly fraud; issuer data shows SIM-swap-style ATO (phone changed via IVR, VPN logins, "
                  "SMS OTP reset). IP evidence is a truncated /24 (fails CE format), ship-to differs from priors and is a drop address "
                  "shared with prior denied case DSP-2026-04471 and two other ATO disputes. Memory note MEM-0142 is wrong.",
          expected=dict(is_dispute=True, claim_family="fraud_cnp_account_takeover",
                        network_actions=[dict(txn_id=txn["txn_id"], action="file_dispute", condition="10.4", amount="1389.00",
                                              prerequisite="fraud_reported")],
                        cardholder_resolution=dict(outcome="credited", credit_amount="1389.00", liability_amount="0.00"),
                        account_actions=["fraud_report_tc40", "card_reissue", "revert_phone_change_and_secure_online_banking"],
                        adjudication=dict(review_panel_required=True, reason="reopening a closed case (SOP-DSP-003 §2.2)",
                                          min_confidence=0.75, conservative_default_applied=False,
                                          flip_fact="evidence the customer made the phone-number change and received the goods"),
                        automated_actions=[
                            dict(action="lock_digital_banking_pending_step_up"), dict(action="revert_unverified_phone_change"),
                            dict(action="reopen_case", case_id="DSP-2026-04471",
                                 reason="prior denial contradicted by account-takeover indicators and shared drop address"),
                            dict(action="credit_reopened_case", case_id="DSP-2026-04471", amount="612.00",
                                 note="plus related finance charges; no network action: transaction already disputed once and Visa time limit passed"),
                            dict(action="watchlist_add", list="ship_to_addresses", subject_id="ADR-DROP-WHARFSIDE",
                                 evidence=["DSP-2026-04471", "DSP-2026-09301", "DSP-2026-09302", "DSP-2026-90012"])],
                        ce3_assessment=dict(met=False, reasons=["IP provided as 198.18.201.x (not full clear-text public IP)",
                                                                "delivery address differs from prior transactions",
                                                                "device fingerprint new (first seen 2026-10-14)"])),
          key_facts=[dict(id="F1", fact="Phone number changed via IVR 2026-10-12; customer reports no service since Monday evening", evidence=["account_events phone_changed", "COM intake"]),
                     dict(id="F2", fact="3 failed logins from VPN IP then SMS-OTP password reset 01:54 ET", evidence=["account_events"]),
                     dict(id="F3", fact="Merchant account: new device, password reset, email change, new ship-to within 45 min before order", evidence=["MEP-90012-OI.account_activity_last_24h"]),
                     dict(id="F4", fact="Ship-to 88 Wharfside Ave Unit 2 also used in DSP-2026-04471, DSP-2026-09301, DSP-2026-09302", evidence=["graph ADR-DROP-WHARFSIDE"]),
                     dict(id="F5", fact="Merchant IP evidence truncated to /24; IP range is CGNAT", evidence=["MEP-90012-OI.session", "reference/ip_intel.csv"])],
          hypotheses=[dict(id="H1", label="first-party misuse", for_=["merchant CE claim", "MEM-0142", "prior denial"], against=["F1", "F2", "F3", "F4", "F5"]),
                      dict(id="H2", label="account takeover", for_=["F1", "F2", "F3", "F4"], against=["login ID matches"])],
          contradictions=[dict(id="X1", between=["merchant: CE met", "VISA-10.4 data element format rules"], resolution="not met"),
                          dict(id="X2", between=["MEM-0142", "current evidence"], resolution="retract memory"),
                          dict(id="X3", between=["merchant: account verified", "same packet: account changes minutes before"], resolution="ATO")],
          computations=[dict(name="old_txn_visa_time_limit", value=add_days(old["processing_date"], 120),
                             rule="120 days from processing date of TXN-9001203 — passed before AS_OF")],
          must_cite=["VISA-10.4@2026-04-18", "VISA-11.2-LIFECYCLE@2026-04-18", "REGZ-1026.12", "LFB-SOP-DSP-003@v6", "LFB-SOP-DSP-005@v1"],
          must_not=["deny based on merchant CE claim", "rely on MEM-0142", "file a second network dispute on TXN-9001203",
                    "leave MEM-0142 active", "wait for a human"],
          memory_ops=dict(read=["MEM-0142"], retract=[dict(note_id="MEM-0142", reason="contradicted by ATO evidence and shared drop address")],
                          write=[dict(scope="customer", subject_id=cid, type="correction"),
                                 dict(scope="graph", edge="SHIPPED_TO", subject_id="ADR-DROP-WHARFSIDE", flag="suspected_drop_address")]),
          components=["competing_hypotheses", "contradiction_detection", "graph_traversal", "memory_retraction",
                      "automated review panel (reopen)", "automated controls (account security, watchlist)",
                      "subagents (security events, merchant evidence, graph)", "policy precision (data element format)"],
          deterministic_checks=[dict(path="network_actions[0].condition", op="eq", value="10.4"),
                                dict(path="cardholder_resolution.credit_amount", op="eq", value="1389.00"),
                                dict(path="automated_actions[?action=='reopen_case'].case_id", op="eq", value="DSP-2026-04471"),
                                dict(path="automated_actions[?action=='credit_reopened_case'].amount", op="eq", value="612.00"),
                                dict(path="memory_ops[?note_id=='MEM-0142'].op", op="eq", value="retract")],
          rubric=["Explicitly revisits and overturns the initial first-party-misuse hypothesis with cited evidence"],
          budget=dict(expected_tool_calls="15-30"))


# =====================================================================================================
def c12_porch_ring(ctx: Ctx):
    tz = "America/New_York"
    stride = bg.make_merchant(ctx, "Stridevault", "5661", "ecommerce", "Los Angeles", merchant_id="MER-90014",
                              descriptor="STRIDEVAULT.EXAMPLE", acquirer_id="ACQ-08", onboarded="2020-03-01", is_hero=True)
    kinetic = bg.make_merchant(ctx, "Kinetic Threads", "5651", "ecommerce", "Austin", merchant_id="MER-90015",
                               descriptor="KINETIC THREADS", acquirer_id="ACQ-01", onboarded="2019-03-01", is_hero=True)
    orbital = ctx.get("merchants", "MER-90012")
    shared_fp1 = bg.make_device(ctx, "phone", "CUS-90013", "2026-03-10", device_id="DEV-RING-A")
    shared_fp2 = bg.make_device(ctx, "tablet", "CUS-90014", "2026-04-02", device_id="DEV-RING-B", hardware=False)
    ring = []
    specs = [(90013, "Teagan Northweave", "2026-03-10", "Westerville", "1180 Saffron Hill Way", "43081", 81),
             (90014, "Pax Lockridge", "2026-04-02", "Columbus", "402 Thistledown Ct", "43219", 82),
             (90015, "Yael Sutcliffe", "2026-04-20", "Westerville", "77 Rookwood Ln", "43082", 83),
             (90016, "Nico Wexford", "2026-05-11", "Columbus", "2291 Oriel Rd", "43224", 84)]
    for n, name, since, city, line1, postal, slot in specs:
        pr = person(ctx, n, name, city, since, cycle_day=8, behavior="minimum", line1=line1, postal=postal,
                    history_from=since, phone_slot=slot, credit_limit=3000, history_scale=0.6,
                    employer="Brightline Staffing")
        ring.append(pr)
    ctx.get("customers", "CUS-90014")["alt_phone"] = "(614) 555-0188"
    ctx.get("customers", "CUS-90016")["alt_phone"] = "(614) 555-0188"
    usage = {90013: [shared_fp1, shared_fp2], 90014: [shared_fp2], 90015: [shared_fp1], 90016: [shared_fp2]}
    for pr in ring:
        for dev in usage[pr.n]:
            for k in range(4):
                bg.add_event(ctx, pr.cust["customer_id"], pr.acct["account_id"], "login_success",
                             utc("2026-%02d-%02d" % (6 + k, 3 + pr.n % 20), "21:%02d:00" % (10 + k)), channel="mobile_app",
                             device_id=dev["device_id"], ip=pr.ip, detail={"auth_method": "password"}, is_hero=True)
    # disputes: (customer n, merchant, purchase date, amount, opened, state, outcome)
    plan = [
        (90013, stride, "2026-08-24", "389.00", "2026-08-29", "closed", "credited"),
        (90013, orbital, "2026-09-15", "529.00", "2026-09-21", "open", ""),
        (90014, kinetic, "2026-08-31", "298.00", "2026-09-05", "closed", "credited"),
        (90015, stride, "2026-09-07", "376.00", "2026-09-12", "closed", "denied"),
        (90014, stride, "2026-09-27", "455.00", "2026-10-02", "open", ""),
        (90016, orbital, "2026-09-23", "610.00", "2026-09-28", "open", ""),
        (90015, kinetic, "2026-10-04", "344.00", "2026-10-09", "open", ""),
        (90014, stride, "2026-10-08", "188.00", "2026-10-12", "open", ""),
        (90014, stride, "2026-10-15", "240.00", "2026-10-19", "open", ""),
    ]
    by_n = {pr.n: pr for pr in ring}
    ring_cases = []
    for i, (n, mer, day, amt, opened, state, outcome) in enumerate(plan):
        pr = by_n[n]
        t = bg.add_txn(ctx, pr.acct, pr.card, mer, day, "13:%02d:00" % (5 + i), amt, channel="ecommerce", eci="05",
                       cavv_present=True, three_ds_status="Y", avs_result="Y", three_ds_browser_ip=pr.ip, is_hero=True)
        dcid = f"DSP-2026-9{1300 + i}"
        ring_cases.append(dcid)
        delivered = add_days(day, 4)
        addr = full_address(pr.addr)
        bg.add_dispute(ctx, dcid, [t], "REG_Z", utc(opened, "12:%02d:00" % (10 + i)),
                       f"Order from {mer['dba_name']} never arrived.", "not_received", intake_channel="app_chat",
                       intake_authenticated_via="mobile_app_password", assigned_queue="consumer_disputes",
                       status="closed" if state == "closed" else "open", stage="closed" if state == "closed" else "awaiting_merchant_evidence",
                       cardholder_outcome=outcome, network_condition="13.1" if state == "closed" else "",
                       network_outcome={"credited": "issuer_won", "denied": "merchant_won"}.get(outcome, ""),
                       closed_at=utc(add_days(opened, 38), "16:00:00") if state == "closed" else "",
                       provisional_credit_amount=amt, provisional_credit_at=utc(add_days(opened, 2), "10:00:00"), is_hero=True)
        bg.add_comm(ctx, pr.cust["customer_id"], utc(opened, "12:%02d:00" % (10 + i)), "inbound", "chat", "cardholder",
                    f"My {mer['dba_name']} order from {day} never came. Tracking says delivered but there was nothing at my door.",
                    case_id=dcid, merchant_id=mer["merchant_id"])
        responded = not (state == "closed" and outcome == "credited")
        if responded:
            bg.add_packet(ctx, f"MEP-9{1300 + i}-OI", dcid, t["txn_id"], mer["merchant_id"], "order_insight", utc(opened, "13:00:00"),
                          utc(add_days(opened, 1), "18:00:00"), dict(
                              shipments=[dict(carrier="ParcelPath", tracking_number=f"PP90{1300 + i}55127",
                                              events=[dict(ts=utc(add_days(day, 1), "09:00:00"), status="shipped"),
                                                      dict(ts=utc(delivered, "14:%02d:00" % (12 + i)), status="delivered", address=addr)],
                                              proof_of_delivery=dict(address=addr, gps_distance_m=8 + i,
                                                                     photo_description="Box on porch at front door; house number matches."))],
                              customer_account=dict(login_id=pr.cust["email"].split("@")[0], ip=pr.ip,
                                                    device_fingerprint=usage[n][0]["device_fingerprint"]),
                              merchant_statement="Delivered to cardholder's address with photo and GPS confirmation."))
    # trigger case: 90013 new claim
    pr = by_n[90013]
    t = bg.add_txn(ctx, pr.acct, pr.card, stride, "2026-10-12", "22:31:00", "412.00", channel="ecommerce", eci="05", cavv_present=True,
                   three_ds_status="Y", avs_result="Y", three_ds_browser_ip=pr.ip, txn_id="TXN-9001301", is_hero=True)
    case = "DSP-2026-90013"
    intake = utc("2026-10-19", "19:02:00")
    bg.add_dispute(ctx, case, [t], "REG_Z", intake, "Stridevault order $412.00 never arrived.", "not_received",
                   intake_channel="app_chat", intake_authenticated_via="mobile_app_password", assigned_queue="consumer_disputes",
                   stage="investigating", provisional_credit_amount="412.00", provisional_credit_at=utc("2026-10-20", "10:00:00"),
                   is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Chat intake: goods not received")
    addr = full_address(pr.addr)
    bg.add_comm(ctx, pr.cust["customer_id"], intake, "inbound", "chat", "cardholder",
                "Stridevault order (Aerostride 9 sneakers, $412) never showed up. Tracking says delivered 10/16 but nothing was there. "
                "Someone must have stolen it. Please refund.", case_id=case, merchant_id=stride["merchant_id"])
    bg.add_packet(ctx, "MEP-90013-OI", case, t["txn_id"], stride["merchant_id"], "order_insight", utc("2026-10-19", "20:00:00"),
                  utc("2026-10-20", "16:00:00"), dict(
                      order=dict(order_id="SV-551902", items=[dict(description="Aerostride 9 (limited colorway) size 10", price="412.00")]),
                      shipments=[dict(carrier="ParcelPath", tracking_number="PP90133019001",
                                      events=[dict(ts=utc("2026-10-13", "09:00:00"), status="shipped"),
                                              dict(ts=utc("2026-10-16", "14:48:00"), status="delivered", address=addr)],
                                      proof_of_delivery=dict(address=addr, gps_distance_m=11,
                                                             photo_description="Shoebox-sized parcel on doormat; door number 1180 visible."))],
                      customer_account=dict(login_id=pr.cust["email"].split("@")[0], ip=pr.ip,
                                            device_fingerprint=shared_fp1["device_fingerprint"]),
                      merchant_statement="Delivered to the cardholder's address; photo and GPS attached."))
    ctx.ring_cases = ring_cases
    truth(ctx, case, code="C12", title="Porch Ring", depth="L4", regime="REG_Z", customer_id=pr.cust["customer_id"],
          txn_ids=[t["txn_id"]],
          summary="Individually: delivered with full address, photo, GPS → no billing error. Collectively: 4 recent customers "
                  "sharing 2 banking-login devices and an alternate phone filed 10 non-receipt claims in 8 weeks; CUS-90014 has 3 "
                  "Stridevault claims within 30 days (Visa cardholder-letter requirement).",
          expected=dict(is_dispute=False, claim_family="not_received",
                        network_actions=[dict(txn_id=t["txn_id"], action="no_dispute", reason="proof of delivery with full address, photo, GPS")],
                        cardholder_resolution=dict(outcome="denied_with_explanation", reversal_amount="412.00"),
                        adjudication=dict(review_panel_required=True, reason="cross-customer abuse finding (SOP-DSP-003 §2.5)",
                                          min_confidence=0.75, conservative_default_applied=False),
                        ring_members=["CUS-90013", "CUS-90014", "CUS-90015", "CUS-90016"], must_exclude_customers=["CUS-90017"],
                        automated_actions=[
                            dict(action="graph_write", node="SuspectedRing", status="active",
                                 members=["CUS-90013", "CUS-90014", "CUS-90015", "CUS-90016"],
                                 evidence_edges=["BANKING_LOGIN_FROM DEV-RING-A", "BANKING_LOGIN_FROM DEV-RING-B", "HAS_PHONE (614) 555-0188"],
                                 cases=sorted(ring_cases + [case])),
                            dict(action="enhanced_monitoring", accounts=["ACC-CR-90013", "ACC-CR-90014", "ACC-CR-90015", "ACC-CR-90016"]),
                            dict(action="claims_control_evidence_first", accounts=["ACC-CR-90013", "ACC-CR-90014", "ACC-CR-90015", "ACC-CR-90016"],
                                 rule="signed cardholder letter + evidence review before temporary credit on future non-receipt claims"),
                            dict(action="watchlist_add", list="devices", subject_ids=["DEV-RING-A", "DEV-RING-B"]),
                            dict(action="enqueue_automated_rereview", cases=[c for c, spec in zip(ring_cases, plan) if spec[5] == "open"],
                                 rule="decide each on its own evidence")],
                        visa_rule_notes=["CUS-90014 open Stridevault claims (10-02, 10-12, 10-19) are 3 within 30 days → cardholder letter required for 13.1"]),
          key_facts=[dict(id="F1", fact="POD full address, photo, GPS 11 m", evidence=["MEP-90013-OI"]),
                     dict(id="F2", fact="DEV-RING-A used by CUS-90013 and CUS-90015; DEV-RING-B by CUS-90013, 90014, 90016", evidence=["account_events"]),
                     dict(id="F3", fact="Alt phone (614) 555-0188 on CUS-90014 and CUS-90016", evidence=["customers"]),
                     dict(id="F4", fact="All four accounts opened Mar–May 2026", evidence=["accounts"])],
          computations=[dict(name="ring_non_receipt_claims", value=len(ring_cases) + 1),
                        dict(name="cus_90014_stridevault_claims_within_30_days", value=3)],
          must_cite=["VISA-13.1@2026-04-18", "REGZ-1026.13", "LFB-SOP-DSP-003@v6", "LFB-SOP-DSP-004@v2"],
          must_not=["include CUS-90017 in the ring", "close or restrict accounts", "deny linked cases on linkage alone",
                    "approve on 'porch theft' narrative despite POD", "wait for a human"],
          memory_ops=dict(consolidate=[dict(into="SuspectedRing", from_cases=sorted(ring_cases + [case]))]),
          components=["graph_traversal", "parallel_subagents (per linked case)", "consolidation", "memory_write (graph)",
                      "automated review panel", "bounded automated controls", "fairness guardrail (guilt by association)"],
          deterministic_checks=[dict(path="network_actions[0].action", op="eq", value="no_dispute"),
                                dict(path="automated_actions[?action=='graph_write'].members", op="set_eq",
                                     value=["CUS-90013", "CUS-90014", "CUS-90015", "CUS-90016"]),
                                dict(path="automated_actions[*]", op="not_contains_any", value=["close_account", "restrict_account"])],
          rubric=["Ring finding cites specific shared identifiers, not demographics or neighborhood"],
          budget=dict(expected_tool_calls="15-35"))


def c12b_wrong_house(ctx: Ctx):
    p = person(ctx, 90017, "Bellamy Okonjo", "Westerville", "2014-07-15", cycle_day=16, line1="1240 Maple Ridge Dr",
               postal="43081", employer="Northgate Schools")
    stride = ctx.get("merchants", "MER-90014")
    t = bg.add_txn(ctx, p.acct, p.card, stride, "2026-10-07", "18:20:00", "219.00", channel="ecommerce", eci="05", cavv_present=True,
                   three_ds_status="Y", avs_result="Y", three_ds_browser_ip=p.ip, txn_id="TXN-9001401", is_hero=True)
    case = "DSP-2026-90014"
    intake = utc("2026-10-15", "08:12:00")
    bg.add_dispute(ctx, case, [t], "REG_Z", intake, "Stridevault order $219.00 marked delivered but not received.", "not_received",
                   intake_channel="phone", assigned_queue="consumer_disputes", stage="awaiting_merchant_evidence",
                   provisional_credit_amount="219.00", provisional_credit_at=utc("2026-10-16", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: goods not received")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Teacher, first dispute in 12 years. Ordered running shoes from Stridevault 10/7. Tracking says delivered 10/11 but "
                "nothing came. Checked with neighbors on both sides. Emailed Stridevault 10/12, they said 'tracking shows delivered'.",
                case_id=case, merchant_id=stride["merchant_id"])
    bg.add_packet(ctx, "MEP-90014-OI", case, t["txn_id"], stride["merchant_id"], "order_insight", utc("2026-10-15", "09:00:00"),
                  utc("2026-10-16", "13:00:00"), dict(
                      shipments=[dict(carrier="ParcelPath", tracking_number="PP90140022871",
                                      events=[dict(ts=utc("2026-10-08", "09:00:00"), status="shipped"),
                                              dict(ts=utc("2026-10-11", "15:02:00"), status="delivered", address="…Maple Ridge Dr, Westerville OH")],
                                      proof_of_delivery=dict(address="…Maple Ridge Dr, Westerville OH", gps_distance_m=None,
                                                             photo_description="Box leaning against a white door; brass house number 1204 visible."))],
                      merchant_statement="Carrier confirms delivery."))
    truth(ctx, case, code="C12b", title="Wrong House", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"], txn_ids=[t["txn_id"]],
          summary="Same merchant and ZIP as the ring, but POD has a partial address and the photo shows house 1204 vs cardholder 1240. "
                  "No shared devices/phones with ring members. Valid 13.1.",
          expected=dict(is_dispute=True, claim_family="not_received",
                        network_actions=[dict(txn_id=t["txn_id"], action="file_dispute", condition="13.1", amount="219.00")],
                        cardholder_resolution=dict(outcome="provisional_credit_pending_network", credit_amount="219.00"),
                        adjudication=dict(review_panel_required=False), ring_linkage=False),
          key_facts=[dict(id="F1", fact="POD address partial ('…Maple Ridge Dr'); Visa requires full delivery address", evidence=["MEP-90014-OI", "VISA-13.1@2026-04-18"]),
                     dict(id="F2", fact="Photo shows house number 1204; cardholder lives at 1240", evidence=["MEP-90014-OI", "addresses ADR-90017"]),
                     dict(id="F3", fact="No shared device, IP or phone with CUS-90013..90016", evidence=["graph"])],
          must_cite=["VISA-13.1@2026-04-18"],
          must_not=["link to SuspectedRing", "deny on merchant 'delivered' statement"],
          components=["graph_traversal (negative result)", "contradiction_detection", "fairness guardrail"],
          deterministic_checks=[dict(path="network_actions[0].condition", op="eq", value="13.1"),
                                dict(path="ring_linkage", op="eq", value=False)],
          rubric=["States explicitly that no identifier links this customer to the ring"],
          budget=dict(expected_tool_calls="6-12"))


def build(ctx: Ctx):
    c09_ce3_clock(ctx)
    c10_family_tablet(ctx)
    c11_ato(ctx)
    c12_porch_ring(ctx)
    c12b_wrong_house(ctx)
