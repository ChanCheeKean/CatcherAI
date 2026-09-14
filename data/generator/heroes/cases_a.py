"""Hero cases C01–C04."""
from __future__ import annotations

import background as bg
from common import Ctx, add_days, m, money, utc
from heroes.kit import AS_OF_ISO, full_address, person, persona, research, truth


# =====================================================================================================
def c01_went_dark(ctx: Ctx):
    p = person(ctx, 90001, "Marlo Eversole", "Columbus", "2019-03-11", cycle_day=25, employer="Meridian Freight Co")
    mer = bg.make_merchant(ctx, "Oakhollow Furniture Co", "5712", "ecommerce", "Columbus", merchant_id="MER-90001",
                           descriptor="OAKHOLLOW FURNITURE CO", acquirer_id="ACQ-02", onboarded="2021-04-02",
                           website="https://www.oakhollowfurniture.example", phone="(614) 555-0133", is_hero=True)
    tz = mer["timezone"]
    txn = bg.add_txn(ctx, p.acct, p.card, mer, "2026-08-18", "14:22:00", "1284.00", channel="ecommerce",
                     txn_id="TXN-9000101", processing_lag=1, avs_result="Y", eci="05", cavv_present=True,
                     three_ds_status="Y", three_ds_browser_ip=p.ip, is_hero=True)
    # earlier legit Oakhollow orders by other customers (merchant used to deliver)
    cols = [r for r in ctx.people if r["city"] == "Columbus" and r["accounts"][0]["regime"] == "REG_Z"]
    for r in cols[8:10]:
        bg.add_txn(ctx, r["accounts"][0], r["cards"][0], mer, "2026-05-%02d" % ctx.rng.randint(3, 25), "12:10:00",
                   m(ctx.rng.uniform(420, 980)), channel="ecommerce")
    # four background cardholders with open non-receipt disputes -> merchant-level cluster
    for i, (r, day, opened, amt) in enumerate(zip(cols[:4], ["2026-08-05", "2026-08-12", "2026-08-21", "2026-08-29"],
                                                  ["2026-09-30", "2026-10-06", "2026-10-12", "2026-10-16"],
                                                  ["2150.00", "640.00", "1875.50", "912.00"])):
        t = bg.add_txn(ctx, r["accounts"][0], r["cards"][0], mer, day, "19:05:00", amt, channel="ecommerce")
        cid = f"DSP-2026-0{9101 + i}"
        dsp = bg.add_dispute(ctx, cid, [t], "REG_Z", utc(opened, "10:30:00"),
                             "Paid Oakhollow Furniture for custom furniture; never delivered; merchant not responding.",
                             "not_received", intake_channel="phone", assigned_queue="consumer_disputes",
                             stage="dispute_filed" if i == 0 else "investigating",
                             network_condition="13.1" if i == 0 else "",
                             dispute_processing_date="2026-10-08" if i == 0 else "")
        bg.add_devent(ctx, cid, dsp["opened_at"], "intake_created", "Claim opened: goods not received (Oakhollow)")
        bg.add_comm(ctx, r["customer"]["customer_id"], dsp["opened_at"], "inbound", "phone_summary", "cardholder",
                    f"Ordered furniture from Oakhollow on {day} for ${amt}. Promised delivery within 5 weeks. "
                    "Phone disconnected, emails bounce.", case_id=cid, merchant_id=mer["merchant_id"])
        ctx.bg_labels.append(dict(case_id=cid, family="not_received", true_nature="merchant_failure",
                                  expected_network_condition="13.1", expected_cardholder_outcome="credited",
                                  status="open", historical_decision_correct=True))

    case = "DSP-2026-90001"
    intake = utc("2026-10-20", "19:12:00")
    dsp = bg.add_dispute(ctx, case, [txn], "REG_Z", intake,
                         "Custom dining table from Oakhollow Furniture never delivered; merchant stopped responding.",
                         "not_received", intake_channel="secure_message",
                         intake_authenticated_via="secure_online_banking", assigned_queue="consumer_disputes",
                         is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Secure message converted to dispute claim")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "secure_message", "cardholder",
                "Hi, I ordered a custom walnut dining table (Harwick 7ft) from Oakhollow Furniture on Aug 18 and paid "
                "$1,284.00. They said 3-4 weeks and delivery by Sept 22. Nothing ever shipped. I've emailed them three "
                "times (Sept 24, Oct 1, Oct 8) and gotten no reply, and their phone just rings. I want my money back. "
                "I've attached their order confirmation and my emails.",
                case_id=case, merchant_id=mer["merchant_id"], subject="Never received my furniture",
                attachments=[{"name": "oakhollow_order_confirmation.eml", "description":
                              "Order OH-22871, Harwick 7ft walnut dining table, $1,284.00 paid in full, "
                              "'Made to order. Ships in 3-4 weeks. Estimated delivery: by September 22, 2026.'"},
                             {"name": "emails_to_oakhollow.pdf", "description":
                              "Three emails from cardholder to orders@oakhollowfurniture.example dated 2026-09-24, "
                              "2026-10-01, 2026-10-08 asking for delivery status or refund. No replies included."}])
    bg.add_packet(ctx, "MEP-90001-OI", case, txn["txn_id"], mer["merchant_id"], "order_insight", "", AS_OF_ISO,
                  dict(status="no_data", message="Merchant not reachable via Order Insight; no enrolment response "
                       "since 2026-10-02. No order, shipment, or refund data returned."))
    research(ctx, "WEB-04100", "Columbus furniture maker Oakhollow abruptly closes; owner files for bankruptcy",
             "https://news.columbusledger.example/business/2026/10/05/oakhollow-furniture-closes",
             "Columbus Ledger (fictional)", "2026-10-05", "2026-10-06", "news", """
Oakhollow Furniture Co, the Short North custom furniture workshop, closed its doors last week. A Chapter 7
petition was filed on behalf of the company in the U.S. Bankruptcy Court for the Southern District of Ohio on
October 2, 2026, according to court records reviewed by the Ledger.

Several customers told the Ledger they had paid in full for made-to-order pieces this summer that were never
delivered. The company's phone line has been disconnected. A bankruptcy trustee is expected to be appointed;
customers with unfulfilled orders may file a proof of claim with the court.
""", mer["merchant_id"])
    research(ctx, "WEB-04107", "Oakhollow Furniture — Notice", "https://www.oakhollowfurniture.example/",
             "Oakhollow Furniture Co", "2026-10-09", "2026-10-10", "merchant_site_snapshot", """
**Oakhollow Furniture has closed.**

We are no longer taking orders or fulfilling existing orders. Inquiries regarding the bankruptcy estate should be
directed to the appointed trustee. Thank you to our customers for eleven years.
""", mer["merchant_id"])
    truth(ctx, case, code="C01", title="Went Dark", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="Non-receipt of made-to-order furniture; merchant bankrupt; Visa 13.1 waiting period waived; "
                  "Reg Z notice timely with 5 days to spare; merchant-level cluster of 4 other open disputes.",
          expected=dict(
              is_dispute=True, claim_family="not_received",
              network_actions=[dict(txn_id=txn["txn_id"], action="file_dispute", condition="13.1", amount="1284.00",
                                    earliest_filing_date="2026-10-21")],
              cardholder_resolution=dict(outcome="provisional_credit_pending_network", credit_amount="1284.00",
                                         liability_amount="0.00"),
              letters=["reg_z_billing_error_acknowledgment"],
              adjudication=dict(review_panel_required=False)),
          key_facts=[
              dict(id="F1", fact="Expected delivery date 2026-09-22 has passed with no shipment", evidence=["COM attachment oakhollow_order_confirmation.eml", "MEP-90001-OI"]),
              dict(id="F2", fact="Cardholder attempted to resolve with merchant three times", evidence=["COM attachment emails_to_oakhollow.pdf"]),
              dict(id="F3", fact="Merchant filed Chapter 7 on 2026-10-02 (insolvent)", evidence=["WEB-04100", "WEB-04107"]),
              dict(id="F4", fact="Four other open non-receipt disputes against MER-90001", evidence=["disputes DSP-2026-09101..09104"]),
              dict(id="F5", fact="First statement reflecting the charge transmitted 2026-08-26", evidence=["statements ACC-CR-90001 cycle ending 2026-08-25"])],
          computations=[
              dict(name="reg_z_notice_deadline", value="2026-10-25", rule="60 days after first statement transmitted (2026-08-26)"),
              dict(name="reg_z_notice_timely", value=True),
              dict(name="visa_13_1_time_limit", value="2027-01-20", rule="120 days from expected receipt date 2026-09-22"),
              dict(name="visa_13_1_waiting_period_applies", value=False, rule="waived: merchant insolvent/bankrupt")],
          must_cite=["VISA-13.1@2026-04-18", "REGZ-1026.13"],
          must_not=["wait 15 days before filing", "require police report or affidavit",
                    "deny for lack of merchant response", "request merchant evidence repeatedly"],
          memory_ops=dict(write=[dict(scope="merchant", subject_id="MER-90001", must_mention=["bankrupt", "2026-10-02"],
                                      optional=True)]),
          components=["router", "tool_calling", "skills", "research", "sandbox", "semantic_retrieval",
                      "persistent_memory", "graph_or_sql_cluster", "memory_write"],
          deterministic_checks=[
              dict(path="network_actions[0].condition", op="eq", value="13.1"),
              dict(path="network_actions[0].amount", op="eq", value="1284.00"),
              dict(path="adjudication.conservative_default_applied", op="eq", value=False),
              dict(path="deadlines.reg_z_notice_deadline", op="eq", value="2026-10-25")],
          rubric=["Explains why the 15-day wait does not apply and cites the bankruptcy source",
                  "Notes the merchant-level cluster", "Stops without requesting further merchant evidence"],
          budget=dict(expected_tool_calls="6-12", early_termination=True))


# =====================================================================================================
def c02_coffee(ctx: Ctx):
    p = person(ctx, 90002, "Hollis Marchetti", "Boston", "2016-05-02", cycle_day=9, employer="Helix Analytics")
    work = ctx.get("addresses", p.cust["work_address_id"])
    mer = bg.make_merchant(ctx, "Bluefern Coffee Roasters", "5814", "in_store", "Boston", merchant_id="MER-90002",
                           descriptor="BLUEFERN COFFEE ROASTERS", acquirer_id="ACQ-03", onboarded="2018-09-10",
                           phone="(617) 555-0112", is_hero=True,
                           extra_descriptors=[("TAPR* BLUEFERN CAFE BOSTON", "2026-09-03", "",
                                               "payment facilitator migration (Tapr) — new descriptor")])
    for r in ctx.t["merchant_descriptors"]:
        if r["merchant_id"] == "MER-90002" and r["note"] == "primary":
            r["last_seen"] = "2026-09-02"
    days = ["2026-03-03", "2026-03-17", "2026-04-02", "2026-04-14", "2026-04-29", "2026-05-12", "2026-05-27",
            "2026-06-09", "2026-06-23", "2026-07-08", "2026-07-21", "2026-08-04", "2026-08-18", "2026-08-27",
            "2026-09-09", "2026-09-23"]
    for dday in days:
        bg.add_txn(ctx, p.acct, p.card, mer, dday, f"08:{ctx.rng.randint(2, 40):02d}:00",
                   m(ctx.rng.choice(["4.85", "6.40", "9.75", "11.20", "12.60", "7.95"])), channel="in_store",
                   pos_entry_mode="07", card_present=True)
    txn = bg.add_txn(ctx, p.acct, p.card, mer, "2026-10-14", "08:12:00", "11.40", channel="in_store",
                     pos_entry_mode="07", card_present=True, txn_id="TXN-9000201", is_hero=True)
    case = "DSP-2026-90002"
    intake = utc("2026-10-19", "12:40:00")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Does not recognize TAPR* BLUEFERN CAFE BOSTON $11.40.",
                   "fraud_card_present", intake_channel="app_chat", intake_authenticated_via="mobile_app_biometric",
                   assigned_queue="fraud_card_present", is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Chat: unrecognized card-present transaction")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "chat", "cardholder",
                "There's a charge TAPR* BLUEFERN CAFE BOSTON for $11.40 on Oct 14 that I don't recognize. I've never "
                "been to a place called Bluefern Cafe. Is my card compromised?? My card is in my wallet.",
                case_id=case, merchant_id=mer["merchant_id"], subject="Unrecognized charge")
    research(ctx, "WEB-04114", "Tapr merchant directory — Bluefern Cafe (Boston)",
             "https://directory.tapr.example/merchants/bluefern-cafe-boston", "Tapr Payment Facilitation (fictional)",
             "2026-09-03", "2026-10-19", "descriptor_directory", f"""
**TAPR\\* BLUEFERN CAFE BOSTON**

- Business: Bluefern Coffee Roasters (dba Bluefern Cafe)
- Address: {work['line1'].split(' ', 1)[0]} Harrowgate St, Boston, MA (0.3 mi from Helix Analytics offices)
- Category: Coffee shop (MCC 5814)
- Processing with Tapr since: 2026-09-03
- Note: *Previously billed as "BLUEFERN COFFEE ROASTERS". Card statements after Sept 3, 2026 show the new name.*
""", mer["merchant_id"])
    persona(ctx, case, p.cust["customer_id"],
            profile="Office worker who buys coffee near work most mornings; anxious about fraud.",
            knows=["Buys coffee at 'Bluefern' near the office 2-3 times a week", "Card never left their possession"],
            disclosure_rules=["Recognizes the merchant immediately if told it is Bluefern Coffee Roasters / the café near Helix Analytics",
                              "Otherwise insists they don't know 'Bluefern Cafe'"],
            scripted_replies=[
                dict(trigger="agent explains descriptor is Bluefern Coffee Roasters near work", delay_minutes=240,
                     reply="Oh! That's my coffee place by the office — they must have changed the name. Sorry about that. Please cancel the dispute, no need for a new card."),
                dict(trigger="agent asks generic yes/no whether they visited a coffee shop", delay_minutes=180,
                     reply="I get coffee most mornings, but not at anything called Bluefern Cafe.")])
    truth(ctx, case, code="C02", title="Coffee by Another Name", depth="L1", regime="REG_Z",
          customer_id=p.cust["customer_id"], txn_ids=[txn["txn_id"]],
          summary="Unrecognized card-present charge is the cardholder's regular café under a new facilitator descriptor.",
          expected=dict(is_dispute=False, claim_family="descriptor_confusion", network_actions=[],
                        cardholder_resolution=dict(outcome="withdrawn_after_clarification", credit_amount="0.00"),
                        account_actions_forbidden=["card_reissue", "fraud_report"], adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="16 prior card-present purchases at MER-90002 (14 under old descriptor)", evidence=["transactions MER-90002"]),
                     dict(id="F2", fact="Descriptor changed 2026-09-03 with Tapr migration", evidence=["merchant_descriptors MER-90002", "WEB-04114"]),
                     dict(id="F3", fact="Contactless chip read, card present; no fraud pattern", evidence=["TXN-9000201"])],
          must_not=["file 10.3 dispute", "report fraud / TC40", "reissue card", "continue investigating after withdrawal"],
          components=["router", "tool_calling", "persistent_memory", "graph_traversal (merchant descriptors)", "research",
                      "user_simulation", "loop_termination"],
          deterministic_checks=[dict(path="is_dispute", op="eq", value=False),
                                dict(path="cardholder_resolution.outcome", op="eq", value="withdrawn_after_clarification"),
                                dict(path="account_actions", op="not_contains", value="card_reissue")],
          rubric=["Asks a specific clarifying question naming the merchant's old name/location", "Closes promptly"],
          budget=dict(expected_tool_calls="3-6", early_termination=True))


# =====================================================================================================
def c03_stale_threshold(ctx: Ctx):
    p = person(ctx, 90003, "Idris Coldiron", "Austin", "2014-08-19", cycle_day=3)
    mer = bg.make_merchant(ctx, "Glyphstack Fonts", "5817", "ecommerce", "Austin", merchant_id="MER-90003",
                           descriptor="GLYPHSTACK FONTS", acquirer_id="ACQ-07", onboarded="2020-01-15",
                           website="https://www.glyphstack.example", is_hero=True)
    # prior dispute 14 months ago (outside 12-month lookback)
    old_mer = ctx.get("merchants", ctx.pools["national"]["streaming"][0])
    old = bg.add_txn(ctx, p.acct, p.card, old_mer, "2025-07-28", "03:15:00", "22.99", channel="recurring")
    bg.add_dispute(ctx, "DSP-2025-90003", [old], "REG_Z", utc("2025-08-12", "09:40:00"),
                   "Cancelled streaming but charged again.", "cancelled_recurring", status="closed", stage="closed",
                   network_condition="13.2", dispute_processing_date="2025-08-15", cardholder_outcome="credited",
                   network_outcome="issuer_won", closed_at=utc("2025-09-19", "16:00:00"),
                   assigned_queue="consumer_disputes")
    bg.add_devent(ctx, "DSP-2025-90003", utc("2025-09-19", "16:00:00"), "case_closed", "Closed: credited; 13.2 won")
    t1 = bg.add_txn(ctx, p.acct, p.card, mer, "2026-10-11", "10:02:00", "12.49", channel="ecommerce",
                    txn_id="TXN-9000301", eci="05", cavv_present=True, three_ds_status="Y", avs_result="Y",
                    three_ds_browser_ip=p.ip, is_hero=True)
    t2 = bg.add_txn(ctx, p.acct, p.card, mer, "2026-10-11", "10:09:00", "19.99", channel="ecommerce",
                    txn_id="TXN-9000302", eci="05", cavv_present=True, three_ds_status="Y", avs_result="Y",
                    three_ds_browser_ip=p.ip, is_hero=True)
    case = "DSP-2026-90003"
    intake = utc("2026-10-20", "16:25:00", "America/Chicago")
    bg.add_dispute(ctx, case, [t1, t2], "REG_Z", intake,
                   "Two Glyphstack font licenses purchased; downloads never worked; merchant not replying.",
                   "not_received", intake_channel="app_chat", intake_authenticated_via="mobile_app_biometric",
                   assigned_queue="consumer_disputes", is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created",
                  "Chat intake created ONE case for two transactions (TXN-9000301, TXN-9000302)")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "chat", "cardholder",
                "I bought two font licenses from Glyphstack on Oct 11 ($12.49 Morrow Serif Standard and $19.99 Morrow "
                "Serif Pro webfont bundle). Both download links gave an error page, and the license page says "
                "'activation failed'. I emailed support on the 12th and 15th, no answer. I just want refunds.",
                case_id=case, merchant_id=mer["merchant_id"], subject="Font downloads never worked",
                attachments=[{"name": "glyphstack_receipt.eml", "description":
                              "Receipt for order GS-40112: Morrow Serif Standard License $12.49; Morrow Serif Pro "
                              "Webfont Bundle $19.99. 'Your download links are available immediately in your account.'"}])
    bg.add_packet(ctx, "MEP-90003-OI", case, t2["txn_id"], mer["merchant_id"], "order_insight", "",
                  utc("2026-10-21", "11:00:00"), dict(
                      order=dict(order_id="GS-40112", placed_at=utc("2026-10-11", "10:01:40", "America/Chicago"),
                                 items=[dict(sku="MS-STD-LIC", description="Morrow Serif Standard Desktop License", price="12.49"),
                                        dict(sku="MS-PRO-WEB", description="Morrow Serif Pro Webfont Bundle", price="19.99")]),
                      customer_account=dict(login_id="icoldiron", email="idris.coldiron@example.com"),
                      digital_delivery=[
                          dict(ts=utc("2026-10-11", "10:03:12", "America/Chicago"), sku="MS-STD-LIC", event="download_attempt", result="HTTP 503"),
                          dict(ts=utc("2026-10-11", "10:10:05", "America/Chicago"), sku="MS-PRO-WEB", event="download_attempt", result="HTTP 503"),
                          dict(ts=utc("2026-10-13", "19:44:51", "America/Chicago"), sku="MS-PRO-WEB", event="download_attempt", result="HTTP 503"),
                          dict(ts="", sku="both", event="license_activation", result="status=pending_activation_error")],
                      successful_downloads=0,
                      merchant_statement="Customers can re-download purchases from their account at any time."))
    research(ctx, "WEB-04121", "Glyphstack status — Download service degraded",
             "https://status.glyphstack.example/incidents/2026-10-11", "Glyphstack Fonts", "2026-10-11", "2026-10-20",
             "status_page", """
**Resolved** — Oct 14, 2026 22:10 CDT: Download and license activation services have been restored.

**Monitoring** — Oct 13, 2026: A fix is being deployed. Some customers may still see HTTP 503 errors.

**Investigating** — Oct 11, 2026 09:55 CDT: We are investigating errors affecting file downloads and license
activation for orders placed today. Affected orders may require manual re-issue by support.
""", mer["merchant_id"])
    truth(ctx, case, code="C03", title="The Stale Threshold", depth="L1/L2", regime="REG_Z",
          customer_id=p.cust["customer_id"], txn_ids=[t1["txn_id"], t2["txn_id"]],
          summary="Intake bundled two transactions into one case. SOP v4 write-off (≤$15) covers only the $12.49 claim; "
                  "memory note MEM-0150 still reflects superseded v3 (≤$25). $19.99 needs a 13.1 digital non-receipt dispute.",
          expected=dict(
              is_dispute=True, claim_family="not_received", split_case_required=True,
              network_actions=[dict(txn_id=t1["txn_id"], action="write_off_no_chargeback", amount="12.49"),
                               dict(txn_id=t2["txn_id"], action="file_dispute", condition="13.1", amount="19.99")],
              cardholder_resolution=dict(outcome="credited", credit_amount="32.48"),
              adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="SOP-DSP-002 v4 effective 2026-07-01 threshold $15.00", evidence=["LFB-SOP-DSP-002@v4"]),
                     dict(id="F2", fact="Previous dispute opened 2025-08-12 (>12 months before 2026-10-20)", evidence=["DSP-2025-90003"]),
                     dict(id="F3", fact="Zero successful downloads; activation errors; merchant outage 11–14 Oct", evidence=["MEP-90003-OI", "WEB-04121"]),
                     dict(id="F4", fact="Receipt states downloads available immediately (expected delivery date specified)", evidence=["COM attachment glyphstack_receipt.eml"])],
          contradictions=[dict(id="X1", between=["MEM-0150", "LFB-SOP-DSP-002@v4"], resolution="SOP v4 governs; memory superseded")],
          computations=[dict(name="write_off_eligible_TXN-9000301", value=True), dict(name="write_off_eligible_TXN-9000302", value=False)],
          must_cite=["LFB-SOP-DSP-002@v4", "VISA-13.1@2026-04-18", "VISA-11.2-LIFECYCLE@2026-04-18"],
          must_not=["write off $19.99", "file a single dispute covering both transactions", "investigate the $12.49 claim"],
          memory_ops=dict(read=["MEM-0150"], supersede=[dict(note_id="MEM-0150", replaced_by="LFB-SOP-DSP-002@v4")]),
          components=["router (case split)", "policy_versioning", "memory_forgetting", "verifier", "tool_calling",
                      "wait_for_event (packet available 11:00 ET)"],
          deterministic_checks=[
              dict(path="network_actions[?txn_id=='TXN-9000301'].action", op="eq", value="write_off_no_chargeback"),
              dict(path="network_actions[?txn_id=='TXN-9000302'].condition", op="eq", value="13.1"),
              dict(path="memory_ops[?note_id=='MEM-0150'].op", op="eq", value="supersede")],
          rubric=["Explicitly identifies that memory conflicts with current SOP and prefers the SOP"],
          budget=dict(expected_tool_calls="6-12"))


# =====================================================================================================
def c04_split_not_double(ctx: Ctx):
    p = person(ctx, 90004, "Remy Achebe-Lowe", "Pittsburgh", "2012-02-10", cycle_day=15)
    mer = bg.make_merchant(ctx, "Parcelwick Home", "5719", "ecommerce", "Chicago", merchant_id="MER-90004",
                           descriptor="PARCELWICK HOME 888-555-0142", acquirer_id="ACQ-04", onboarded="2017-06-01",
                           website="https://www.parcelwick.example", phone="(888) 555-0142", is_hero=True)
    common = dict(channel="ecommerce", auth_id="AUT-90004-01", auth_code="A7K2Q9", auth_amount="128.36",
                  eci="07", avs_result="Y", cvv2_presence="1", cvv2_result="M", clearing_count=2, is_hero=True)
    t1 = bg.add_txn(ctx, p.acct, p.card, mer, "2026-10-03", "20:14:00", "64.18", txn_id="TXN-9000401",
                    processing_lag=2, clearing_seq=1, **common)
    t2 = bg.add_txn(ctx, p.acct, p.card, mer, "2026-10-03", "20:14:00", "64.18", txn_id="TXN-9000402",
                    processing_lag=6, clearing_seq=2, **common)
    addr = full_address(p.addr)
    case = "DSP-2026-90005"
    intake = utc("2026-10-13", "11:05:00")
    bg.add_dispute(ctx, case, [t2], "REG_Z", intake, "Charged twice ($64.18 x2) by Parcelwick for one lamp.",
                   "duplicate", intake_channel="phone", assigned_queue="consumer_disputes", is_hero=True,
                   provisional_credit_amount="64.18", provisional_credit_at=utc("2026-10-15", "10:00:00"),
                   stage="investigating")
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: duplicate charge claim")
    bg.add_devent(ctx, case, utc("2026-10-14", "10:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent")
    bg.add_devent(ctx, case, utc("2026-10-15", "10:00:00"), "provisional_credit_posted", "Temporary credit 64.18 posted")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Caller says Parcelwick Home charged $64.18 twice on 10/3 for a single floor lamp. Both charges show "
                "10/03 on the statement. Caller says they only ordered one lamp and received it last week. Rep "
                "selected 'duplicate processing'.", case_id=case, merchant_id=mer["merchant_id"],
                subject="Duplicate charge")
    ship = lambda sid, wh, shipped, delivered, dtime: dict(
        shipment_id=sid, carrier="ParcelPath", tracking_number=f"PP{sid[-1]}8841207{sid[-1]}3", items=[dict(sku="HL-BRS-FL", qty=1)],
        ship_from=wh, charged_at_shipment=True,
        events=[dict(ts=utc(shipped, "09:30:00", "America/Chicago"), status="shipped"),
                dict(ts=utc(delivered, dtime), status="delivered", address=addr)],
        proof_of_delivery=dict(address=addr, photo_description="Large brown carton marked 'PARCELWICK' on front porch next to door; house number visible.",
                               gps_distance_m=9))
    bg.add_packet(ctx, "MEP-90004-OI", case, t2["txn_id"], mer["merchant_id"], "order_insight", "",
                  utc("2026-10-21", "12:00:00"), dict(
                      order=dict(order_id="PW-7Q2-55810", placed_at=utc("2026-10-03", "20:12:31", "America/Chicago"),
                                 authorization=dict(auth_code="A7K2Q9", amount="128.36"),
                                 items=[dict(sku="HL-BRS-FL", description="Harlow brass floor lamp, 64in", qty=2, unit_price="60.55")],
                                 sales_tax_rate="0.06", total="128.36"),
                      customer_account=dict(login_id="remy.al", email=p.cust["email"]),
                      shipments=[ship("SHP1", "Columbus OH DC", "2026-10-05", "2026-10-08", "15:40:00"),
                                 ship("SHP2", "Reno NV DC", "2026-10-09", "2026-10-16", "13:05:00")],
                      refunds=[], return_policy="Returns accepted within 30 days of delivery for a full refund (customer pays return shipping).",
                      merchant_statement="Single order for quantity 2 shipped from two warehouses; each shipment is charged when it ships. Both delivered."))
    research(ctx, "WEB-04128", "Parcelwick Help — Why do I see more than one charge?",
             "https://help.parcelwick.example/articles/multiple-charges", "Parcelwick Home", "2025-11-04", "2026-10-21",
             "merchant_help", """
If your order ships in more than one package, we charge your card **as each package ships**. Your bank may show
separate charges with the same order date. Your total will never exceed the amount authorized at checkout.
""", mer["merchant_id"])
    persona(ctx, case, p.cust["customer_id"],
            profile="Busy parent; ordered on phone late at night; didn't notice quantity selector.",
            knows=["Received one lamp Oct 8", "A second large box arrived Oct 16 and hasn't been opened"],
            disclosure_rules=["Mentions the second box only if asked whether any other package from Parcelwick arrived"],
            scripted_replies=[
                dict(trigger="agent asks if another package arrived / explains quantity 2", delay_minutes=90,
                     reply="Oh — actually a second big box came last Friday, I haven't opened it. I only meant to order one lamp. Can I just send it back?"),
                dict(trigger="agent explains return path and no billing error", delay_minutes=60,
                     reply="OK, that makes sense. I'll return it through Parcelwick. You can close this.")])
    truth(ctx, case, code="C04", title="Split, Not Double", depth="L2", regime="REG_Z",
          customer_id=p.cust["customer_id"], txn_ids=[t1["txn_id"], t2["txn_id"]],
          summary="Apparent duplicate is one authorization cleared in two shipments (qty 2, both delivered).",
          expected=dict(is_dispute=False, claim_family="duplicate", network_actions=[
              dict(txn_id=t2["txn_id"], action="no_dispute", reason="not duplicate: multiple clearing sequence of one authorization")],
              cardholder_resolution=dict(outcome="no_error_split_shipment", reversal_amount="64.18",
                                         note="reverse temporary credit with Reg Z explanation; advise merchant return"),
              letters=["reg_z_no_error_explanation"], adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Same auth code A7K2Q9, clearing seq 1/2 and 2/2, sum 128.36 = auth amount", evidence=["TXN-9000401", "TXN-9000402"]),
                     dict(id="F2", fact="Order quantity 2; two shipments; both delivered (second on 2026-10-16, after intake)", evidence=["MEP-90004-OI"]),
                     dict(id="F3", fact="Posting dates differ (10-05 vs 10-09) although txn date is 10-03", evidence=["transactions"])],
          contradictions=[dict(id="X1", between=["intake: ordered one lamp", "order: qty 2"], resolution="order record; cardholder later confirms second delivery")],
          computations=[dict(name="clearing_sum", value="128.36"), dict(name="unit_total_with_tax", value="64.18", rule="round(60.55*1.06,2)")],
          must_cite=["VISA-12.6@2026-04-18", "REGZ-1026.13"],
          must_not=["file 12.6", "leave temporary credit in place as final"],
          components=["sandbox", "tool_calling", "contradiction_detection", "user_simulation", "wait_for_event"],
          deterministic_checks=[dict(path="is_dispute", op="eq", value=False),
                                dict(path="cardholder_resolution.reversal_amount", op="eq", value="64.18")],
          rubric=["Explains multiple clearing sequence numbers in plain language", "Offers merchant return path"],
          budget=dict(expected_tool_calls="6-12"))


def build(ctx: Ctx):
    c01_went_dark(ctx)
    c02_coffee(ctx)
    c03_stale_threshold(ctx)
    c04_split_not_double(ctx)
