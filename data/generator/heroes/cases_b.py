"""Hero cases C05–C08."""
from __future__ import annotations

import background as bg
from common import Ctx, add_days, m, money, utc
from heroes.kit import AS_OF_ISO, full_address, person, persona, research, truth


def _merchant_by_name(ctx: Ctx, name: str) -> dict:
    return next(r for r in ctx.t["merchants"] if r["dba_name"] == name)


# =====================================================================================================
def c05_folio(ctx: Ctx):
    p = person(ctx, 90005, "Delphine Osei-Grant", "Chicago", "2015-10-01", cycle_day=12, drives=False)
    mer = bg.make_merchant(ctx, "The Larkspur Hotel Nashville", "7011", "in_store", "Nashville", state="TN",
                           tz="America/Chicago", merchant_id="MER-90005", descriptor="LARKSPUR HOTEL NASHVILLE",
                           acquirer_id="ACQ-06", onboarded="2016-03-01", website="https://www.larkspurhotels.example",
                           phone="(615) 555-0120", is_hero=True, legal_suffix=" Operating Co")
    ride = _merchant_by_name(ctx, "Ridehop")
    for day, tm, amt in (("2026-10-02", "12:40:00", "38.20"), ("2026-10-05", "10:15:00", "41.75")):
        bg.add_txn(ctx, p.acct, p.card, ride, day, tm, amt, channel="in_store", pos_entry_mode="10", card_present=False,
                   merchant_timezone="America/Chicago", txn_local_datetime=f"{day} {tm}",
                   auth_timestamp_utc=utc(day, tm, "America/Chicago"))
    air = _merchant_by_name(ctx, "Bluecrest Airways")
    bg.add_txn(ctx, p.acct, p.card, air, "2026-09-01", "21:02:00", "287.40", channel="ecommerce", eci="05",
               cavv_present=True, three_ds_status="Y")
    txn = bg.add_txn(ctx, p.acct, p.card, mer, "2026-10-05", "11:02:00", "1087.53", channel="in_store",
                     txn_id="TXN-9000501", pos_entry_mode="07", card_present=True, is_hero=True)
    case = "DSP-2026-90006"
    intake = utc("2026-10-12", "15:30:00", "America/Chicago")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake,
                   "Hotel charged $1,087.53 vs quoted $189/night; disputes $434.06 (upgrade said to be complimentary; parking not used).",
                   "incorrect_amount", amounts=["434.06"], intake_channel="phone", assigned_queue="consumer_disputes",
                   stage="awaiting_merchant_evidence", provisional_credit_amount="434.06",
                   provisional_credit_at=utc("2026-10-14", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: hotel overcharge. Rep coded 'incorrect amount'.")
    bg.add_devent(ctx, case, utc("2026-10-13", "09:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent")
    bg.add_devent(ctx, case, utc("2026-10-13", "11:00:00"), "order_insight_requested", "Order Insight request sent to merchant")
    bg.add_devent(ctx, case, utc("2026-10-14", "10:00:00"), "provisional_credit_posted", "Temporary credit 434.06 posted")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Cardholder stayed at The Larkspur Hotel Nashville Oct 2-5 (3 nights) on a work trip, booked direct at $189/night. "
                "Expected about $653 with tax. Charged $1,087.53. Says the front desk offered a 'complimentary upgrade' to a "
                "king suite at check-in, and says there should be no parking because they flew in and used rideshare. "
                "Does not dispute the room nights or tax. Emailed hotel 10/7; hotel replied charges are final. "
                "Disputing $434.06.", case_id=case, merchant_id=mer["merchant_id"], subject="Hotel overcharge",
                attachments=[
                    {"name": "larkspur_confirmation_LK-88213.eml", "description":
                     "Booking confirmation LK-88213, booked 2026-08-30: Deluxe Queen, 3 nights Oct 2-5, $189.00/night. "
                     "'Rate excludes applicable taxes (15.25%) and a daily destination fee of $35.00 plus tax, charged at the "
                     "property. Valet parking $32.00/night (plus 10% parking tax) if applicable.'"},
                    {"name": "larkspur_folio_oct5.pdf", "description":
                     "Folio room 814: Room 3 x 189.00; Suite upgrade 3 x 60.00; Destination fee 3 x 35.00; Valet parking "
                     "3 x 32.00; Room/occupancy tax 129.93; Parking tax 9.60; Total 1,087.53."}])
    bg.add_comm(ctx, p.cust["customer_id"], utc("2026-10-12", "15:45:00", "America/Chicago"), "inbound", "email_forwarded",
                "cardholder", "Fwd thread — 10/07 cardholder to reservations@larkspurhotels.example: 'I was told the upgrade "
                "was complimentary and I did not have a car. Please remove the upgrade and parking.' — 10/09 Larkspur "
                "Guest Services: 'Our records show the upgrade was accepted at check-in. All charges on your folio are final.'",
                case_id=case, merchant_id=mer["merchant_id"], subject="Fwd: Folio question")
    bg.add_packet(ctx, "MEP-90005-OI", case, txn["txn_id"], mer["merchant_id"], "order_insight",
                  utc("2026-10-13", "11:00:00"), utc("2026-10-16", "14:20:00"), dict(
                      reservation=dict(confirmation="LK-88213", booked_at=utc("2026-08-30", "20:11:00", "America/Chicago"),
                                       channel="hotel_website", room_type_booked="Deluxe Queen", rate="189.00",
                                       nights=3, arrival="2026-10-02", departure="2026-10-05",
                                       disclosed_fees=["Destination fee $35.00/night plus tax, charged at property",
                                                       "Valet parking $32.00/night plus 10% tax, if applicable"]),
                      folio=dict(room="814", lines=[
                          dict(code="ROOM", description="Room charge", qty=3, unit="189.00", amount="567.00", taxable_rate="0.1525"),
                          dict(code="UPG", description="Suite upgrade King Suite", qty=3, unit="60.00", amount="180.00", taxable_rate="0.1525"),
                          dict(code="DEST", description="Destination fee", qty=3, unit="35.00", amount="105.00", taxable_rate="0.1525"),
                          dict(code="VALET", description="Valet parking", qty=3, unit="32.00", amount="96.00", taxable_rate="0.10"),
                          dict(code="TAX-OCC", description="Room/occupancy tax 15.25%", amount="129.93"),
                          dict(code="TAX-PKG", description="Parking tax 10%", amount="9.60")], total="1087.53"),
                      registration_card=dict(signed_at=utc("2026-10-02", "15:48:00", "America/Chicago"), guest_signature="present",
                                             text="Room 814. Rate 189.00. UPG KING STE +$60/NT [initials: D.O.]. Destination fee acknowledged [initials: D.O.]. Vehicle: ______ Plate: ______"),
                      valet_log=dict(room="814", entries=[], note="No vehicle ticket issued to room 814 during stay"),
                      merchant_statement="Guest accepted and initialed a paid suite upgrade and acknowledged the destination fee at "
                                         "check-in. All folio charges posted per hotel policy."))
    research(ctx, "WEB-04135", "The Larkspur Hotel Nashville — Fees & Policies",
             "https://www.larkspurhotels.example/nashville/policies", "The Larkspur Hotels", "2026-01-15", "2026-10-13",
             "merchant_policy", """
- **Destination fee:** $35.00 per night plus tax. Includes Wi-Fi, fitness center, two welcome drinks.
- **Parking:** Valet only, $32.00 per night plus 10% parking tax. Charged only for registered vehicles.
- **Room upgrades:** Upgrades offered at check-in may be complimentary or paid; paid upgrades require guest
  acknowledgment on the registration card.
""", mer["merchant_id"])
    truth(ctx, case, code="C05", title="The Folio", depth="L3", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="Hotel folio above quote. 12.5 invalid (T&E quoted vs actual) and 13.3 invalid (price discrepancy). "
                  "Destination fee disclosed; upgrade initialed; parking billed with no vehicle (hotel's own valet log + "
                  "cardholder's rideshare trips) → partial 13.1 for parking + parking tax.",
          expected=dict(is_dispute=True, claim_family="services_not_received_partial",
                        network_actions=[dict(txn_id=txn["txn_id"], action="file_dispute", condition="13.1", amount="105.60")],
                        cardholder_resolution=dict(outcome="partial", credit_amount="105.60", reversal_amount="328.46",
                                                   note="reverse 328.46 of temporary credit with Reg Z explanation"),
                        letters=["reg_z_partial_denial_explanation"], adjudication=dict(review_panel_required=False)),
          line_decisions=[dict(line="DEST", decision="valid_charge", reason="disclosed in confirmation and initialed"),
                          dict(line="UPG", decision="valid_charge", reason="initialed on registration card despite cardholder testimony"),
                          dict(line="VALET+TAX-PKG", decision="dispute", reason="no vehicle; hotel valet log empty; rideshare trips at arrival/departure")],
          key_facts=[dict(id="F1", fact="Confirmation disclosed $35 destination fee and conditional parking", evidence=["COM attachment larkspur_confirmation_LK-88213.eml", "WEB-04135"]),
                     dict(id="F2", fact="Registration card initialed 'D.O.' beside paid upgrade", evidence=["MEP-90005-OI.registration_card"]),
                     dict(id="F3", fact="Valet log shows no vehicle for room 814", evidence=["MEP-90005-OI.valet_log"]),
                     dict(id="F4", fact="Rideshare trips on card at arrival (10-02) and departure (10-05)", evidence=["transactions Ridehop"])],
          contradictions=[dict(id="X1", between=["cardholder: upgrade complimentary", "registration card initials"], resolution="documented acknowledgment prevails; note residual uncertainty"),
                          dict(id="X2", between=["folio: valet 3 nights", "valet log: no vehicle"], resolution="merchant's own evidence contradicts charge")],
          computations=[dict(name="expected_by_cardholder", value="653.47"), dict(name="disputed", value="434.06"),
                        dict(name="parking_with_tax", value="105.60"), dict(name="denied_portion", value="328.46"),
                        dict(name="occupancy_tax", value="129.93", rule="(567+180+105)*0.1525")],
          must_cite=["VISA-12.5@2026-04-18", "VISA-13.3@2026-04-18", "VISA-13.1@2026-04-18", "REGZ-1026.13"],
          must_not=["file 12.5", "file 13.3 for price discrepancy", "dispute the full 434.06", "copy PRE-0007 outcome for the upgrade"],
          precedents=dict(distinguish=["PRE-0007"]),
          components=["router", "agent_graph", "parallel_subagents (per folio line)", "adversarial_review", "sandbox",
                      "semantic_retrieval (policy + precedent)", "contradiction_detection", "skills (T&E lodging)"],
          deterministic_checks=[dict(path="network_actions[0].condition", op="eq", value="13.1"),
                                dict(path="network_actions[0].amount", op="eq", value="105.60"),
                                dict(path="cardholder_resolution.reversal_amount", op="eq", value="328.46")],
          rubric=["Explains why 12.5 and 13.3 are invalid", "Distinguishes PRE-0007 (no initials) from this case",
                  "Acknowledges cardholder's testimony respectfully while explaining the documented acknowledgment"],
          budget=dict(expected_tool_calls="12-25"))


# =====================================================================================================
def c06_trial(ctx: Ctx):
    p = person(ctx, 90006, "Soren Valdivia", "Denver", "2020-02-14", cycle_day=12)
    mer = bg.make_merchant(ctx, "Lumafit Plus", "5968", "recurring", "Los Angeles", merchant_id="MER-90006",
                           descriptor="LUMAFIT+ 855-555-0171", acquirer_id="ACQ-07", onboarded="2023-02-01",
                           website="https://www.lumafit.example", phone="(855) 555-0171", is_hero=True, legal_suffix=" Inc")
    ver = bg.add_txn(ctx, p.acct, p.card, mer, "2026-09-22", "15:05:00", "0.00", channel="ecommerce",
                     txn_type="account_verification", txn_id="TXN-9000600", cof_type="cit_initial", eci="05",
                     cavv_present=True, three_ds_status="Y", avs_result="Y", is_hero=True)
    ver.update(processing_date="", posting_date="", arn="")
    txn = bg.add_txn(ctx, p.acct, p.card, mer, "2026-09-29", "03:10:00", "119.88", channel="recurring",
                     txn_id="TXN-9000601", processing_lag=1, related_txn_id="TXN-9000600", is_hero=True)
    case = "DSP-2026-90007"
    intake = utc("2026-10-06", "20:02:00", "America/Denver")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Free trial converted to $119.88 annual charge; cancelled; refund refused.",
                   "cancelled_recurring", intake_channel="app_chat", intake_authenticated_via="mobile_app_biometric",
                   assigned_queue="consumer_disputes", stage="awaiting_merchant_evidence",
                   provisional_credit_amount="119.88", provisional_credit_at=utc("2026-10-08", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Chat intake: cancelled recurring. Rep coded Visa 13.2 candidate.")
    bg.add_devent(ctx, case, utc("2026-10-07", "09:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent")
    bg.add_devent(ctx, case, utc("2026-10-08", "10:00:00"), "provisional_credit_posted", "Temporary credit 119.88 posted")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "chat", "cardholder",
                "Signed up for a Lumafit free trial on Sept 22. I thought it was monthly if I kept it, but they charged me "
                "$119.88 for a whole YEAR on Sept 29. Nobody told me the price or that trial was ending. I cancelled in the "
                "app on Oct 3 and emailed for a refund and they said annual plans are non-refundable. I used it a few times "
                "during the trial and once after.", case_id=case, merchant_id=mer["merchant_id"], subject="Trial charge",
                attachments=[{"name": "lumafit_welcome_email.eml", "description":
                              "Subject 'Welcome to Lumafit+!' sent 2026-09-22 15:06 PT. Body: 'Your 7-day free trial has started. "
                              "Enjoy unlimited classes. After your trial, your membership renews at the then-current annual rate. "
                              "Manage membership in the app.' No amount, no renewal date, no cancellation link."},
                             {"name": "lumafit_support_reply.eml", "description":
                              "2026-10-04 Lumafit Support: 'Per our Terms, annual memberships are non-refundable once billed. "
                              "Your membership remains active until 2027-09-28.'"}])
    tz = "America/Denver"
    bg.add_packet(ctx, "MEP-90006-OI", case, txn["txn_id"], mer["merchant_id"], "order_insight",
                  utc("2026-10-08", "12:00:00"), utc("2026-10-14", "17:00:00"), dict(
                      subscription=dict(plan="Lumafit+ Annual", price="119.88", trial_days=7,
                                        trial_start=utc("2026-09-22", "16:05:00", tz), trial_end=utc("2026-09-29", "16:05:00", tz),
                                        first_billing=utc("2026-09-29", "04:10:00", tz), service_period="2026-09-29 to 2027-09-28",
                                        cancelled_at=utc("2026-10-03", "18:22:00", tz), cancellation_effective="end of paid term (2027-09-28)"),
                      checkout_disclosure=dict(captured_text="Start your FREE 7-day trial. Cancel anytime. By continuing you agree to the Terms.",
                                               terms_link="https://www.lumafit.example/terms", checkbox="none"),
                      emails_sent=[dict(ts=utc("2026-09-22", "16:06:00", tz), template="welcome_trial", included_price=False,
                                        included_renewal_date=False, included_cancel_link=False)],
                      app_sessions=[dict(ts=utc(dd, "07:10:00", tz), device="iOS app") for dd in
                                    ("2026-09-23", "2026-09-25", "2026-09-27", "2026-09-30")],
                      customer_account=dict(login_id="soren.v", email=p.cust["email"]),
                      merchant_statement="Customer agreed to the Terms at checkout, used the service after billing, and "
                                         "cancelled after the transaction date. Annual plans are non-refundable."))
    research(ctx, "WEB-04142", "Lumafit+ Terms of Service (archived 2026-09-20)",
             "https://archive.pagevault.example/2026-09-20/https://www.lumafit.example/terms", "PageVault archive (fictional)",
             "2026-06-01", "2026-09-20", "merchant_terms_snapshot", """
**4. Trials and Renewals.** Free trials convert automatically to the plan selected at checkout at the end of the
trial period. The Annual plan is billed at $119.88 per year. Membership renews automatically until cancelled.

**5. Refunds.** Annual memberships are non-refundable once billed.

*(No trial-end reminder commitment appears in this version.)*
""", mer["merchant_id"])
    research(ctx, "WEB-04149", "Lumafit+ Terms of Service (current)", "https://www.lumafit.example/terms", "Lumafit Plus Inc",
             "2026-10-05", "2026-10-10", "merchant_terms_snapshot", """
**4. Trials and Renewals.** Free trials convert automatically at the end of the trial period. **We will email you at
least 7 days before your trial ends with the renewal amount, date and a one-click cancellation link.**

**5. Refunds.** Annual memberships are non-refundable once billed.
""", mer["merchant_id"])
    truth(ctx, case, code="C06", title="Trial Trap", depth="L3", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="13.2 invalid (cancellation after transaction date; rule effective 18 Apr 2026). Merchant failed the "
                  "trial-end notice duty (amount, date, cancel link ≥7 days before) → 13.5 Misrepresentation; amount "
                  "limited to unused portion (360/365).",
          expected=dict(is_dispute=True, claim_family="misrepresentation_trial",
                        network_actions=[dict(txn_id=txn["txn_id"], action="file_dispute", condition="13.5", amount="118.24",
                                              amount_tolerance="0.35")],
                        cardholder_resolution=dict(outcome="partial", credit_amount="118.24", reversal_amount="1.64"),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Charge 2026-09-29; cancellation 2026-10-03 (after transaction)", evidence=["TXN-9000601", "MEP-90006-OI.subscription"]),
                     dict(id="F2", fact="No trial-end notice with amount/date/cancel link was sent", evidence=["MEP-90006-OI.emails_sent", "COM attachment lumafit_welcome_email.eml"]),
                     dict(id="F3", fact="Checkout disclosure did not state price or renewal", evidence=["MEP-90006-OI.checkout_disclosure", "WEB-04142"]),
                     dict(id="F4", fact="Service used once after billing (2026-09-30)", evidence=["MEP-90006-OI.app_sessions"]),
                     dict(id="F5", fact="Cardholder attempted to resolve (support email 10-04)", evidence=["COM attachment lumafit_support_reply.eml"])],
          pivots=[dict(at="route selection", from_="13.2", to="13.5", trigger="VISA-13.2@2026-04-18 invalid-dispute clause")],
          computations=[dict(name="days_in_period", value=365), dict(name="days_used", value=5, rule="2026-09-29..2026-10-03 inclusive"),
                        dict(name="unused_portion", value="118.24", rule="119.88*360/365")],
          must_cite=["VISA-13.2@2026-04-18", "VISA-13.5@2026-04-18", "VISA-5-RECURRING-MERCHANT-DUTIES@2026-04-18"],
          must_not=["file 13.2", "dispute the full 119.88", "rely on PRE-0012 or MEM-0160 as current"],
          precedents=dict(outdated=["PRE-0012"]),
          memory_ops=dict(read=["MEM-0160"], supersede=[dict(note_id="MEM-0160", reason="VISA-13.2 changed 2026-04-18")]),
          components=["plan_execute_replan", "verifier", "policy_versioning (as-of retrieval)", "sandbox",
                      "semantic_retrieval", "memory_forgetting", "research (dated snapshot)"],
          deterministic_checks=[dict(path="network_actions[0].condition", op="eq", value="13.5"),
                                dict(path="network_actions[0].amount", op="approx", value="118.24", tolerance="0.35")],
          rubric=["Shows the 13.2 invalidation explicitly before re-routing", "Identifies PRE-0012 as decided under the prior rule"],
          budget=dict(expected_tool_calls="10-20"))


# =====================================================================================================
def c07_fx(ctx: Ctx):
    p = person(ctx, 90007, "Anouk Brightwater", "Seattle", "2011-06-30", cycle_day=20)
    mer = bg.make_merchant(ctx, "Azulejo Atelier Lisboa", "5719", "ecommerce", "Lisbon", country="PT", state="",
                           tz="Europe/Lisbon", merchant_id="MER-90007", descriptor="AZULEJO ATELIER LISBOA PT",
                           acquirer_id="ACQ-05", onboarded="2019-11-11", website="https://www.azulejoatelier.example",
                           phone="+351 21 555 0143", is_hero=True, legal_suffix=" Lda")
    buy = bg.add_txn(ctx, p.acct, p.card, mer, "2026-08-11", "16:40:00", "462.84", channel="ecommerce",
                     txn_id="TXN-9000701", txn_amount="420.00", txn_currency="EUR", fx_rate="1.1020", auth_amount="462.84",
                     processing_lag=1, eci="05", cavv_present=True, three_ds_status="Y", avs_result="U", is_hero=True)
    fee = bg.add_txn(ctx, p.acct, p.card, None, "2026-08-12", "00:00:00", "13.89", channel="fee", txn_type="fee",
                     txn_id="TXN-9000702", processing_lag=0, related_txn_id="TXN-9000701", descriptor="FOREIGN TRANSACTION FEE",
                     pos_entry_mode="", auth_code="", auth_id="", is_hero=True)
    ref = bg.add_refund(ctx, buy, "2026-10-01", amount="447.09", txn_id="TXN-9000703", txn_amount="420.00",
                        txn_currency="EUR", fx_rate="1.0645", processing_lag=1, is_hero=True)
    case = "DSP-2026-90008"
    intake = utc("2026-10-08", "13:15:00", "America/Los_Angeles")
    bg.add_dispute(ctx, case, [ref], "REG_Z", intake,
                   "Merchant refund $15.75 less than purchase; foreign transaction fee not refunded.", "credit_not_processed",
                   amounts=["29.64"], intake_channel="phone", assigned_queue="consumer_disputes", is_hero=True,
                   stage="investigating")
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: partial refund / credit shortfall. Disputed 29.64 (15.75 + 13.89).")
    bg.add_devent(ctx, case, utc("2026-10-09", "09:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Cardholder bought hand-painted tiles from Azulejo Atelier in Lisbon on 8/11 for $462.84 plus a $13.89 foreign fee. "
                "Returned them (arrived back in Lisbon 9/14). Merchant emailed that a FULL refund was issued. Only $447.09 came "
                "back. Cardholder believes merchant short-changed them $15.75 and wants the foreign fee back too.",
                case_id=case, merchant_id=mer["merchant_id"], subject="Refund short",
                attachments=[{"name": "azulejo_refund_email.eml", "description":
                              "2026-09-30 Azulejo Atelier: 'We received your return on 14 September. A full refund of EUR 420.00 "
                              "has been issued to your card.'"},
                             {"name": "return_tracking.pdf", "description": "CTT Expresso tracking RR884120993PT delivered Lisbon 2026-09-14"}])
    truth(ctx, case, code="C07", title="Lost in Conversion", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[buy["txn_id"], fee["txn_id"], ref["txn_id"]],
          summary="Merchant refunded 100% in EUR; USD shortfall is FX movement (1.1020 → 1.0645). Credit preceded any dispute, "
                  "so no 13.6 and no FX pre-arb right. Reg Z: no billing error (FX terms disclosed). SOP-007 reverses the "
                  "issuer's own 3% fee on full refunds.",
          expected=dict(is_dispute=False, claim_family="credit_shortfall_fx",
                        network_actions=[dict(txn_id=ref["txn_id"], action="no_dispute", reason="merchant credit issued in full in transaction currency before any dispute")],
                        cardholder_resolution=dict(outcome="no_error_fx_explained_fee_reversed", credit_amount="13.89",
                                                   credit_type="foreign_transaction_fee_reversal"),
                        letters=["reg_z_no_error_explanation_with_fx_breakdown"], adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Purchase EUR 420.00 @1.1020 = USD 462.84", evidence=["TXN-9000701", "reference/fx_rates.csv"]),
                     dict(id="F2", fact="Refund EUR 420.00 @1.0645 = USD 447.09", evidence=["TXN-9000703"]),
                     dict(id="F3", fact="Refund posted 2026-10-02, before intake 2026-10-08", evidence=["TXN-9000703", "DSP-2026-90008"]),
                     dict(id="F4", fact="Foreign fee 13.89 charged on purchase", evidence=["TXN-9000702"])],
          contradictions=[dict(id="X1", between=["cardholder: merchant short-changed", "EUR amounts equal"], resolution="exchange-rate movement")],
          computations=[dict(name="fx_difference", value="15.75"), dict(name="fee", value="13.89", rule="round(462.84*0.03,2)")],
          must_cite=["VISA-11.4-AMOUNTS-CREDITS-FX@2026-04-18", "VISA-13.6@2026-04-18", "LFB-SOP-DSP-007@v2", "LFB-CARDHOLDER-AGREEMENT@2025-01"],
          must_not=["file 13.6", "credit 15.75 as billing error", "blame merchant"],
          components=["sandbox (FX)", "router", "semantic_retrieval", "internal SOP skill", "contradiction_detection"],
          deterministic_checks=[dict(path="is_dispute", op="eq", value=False),
                                dict(path="cardholder_resolution.credit_amount", op="eq", value="13.89")],
          rubric=["Shows the FX arithmetic in the explanation"], budget=dict(expected_tool_calls="5-10"))


# =====================================================================================================
def c08_pump_six(ctx: Ctx):
    p = person(ctx, 90008, "Cyrus Northcott", "Cleveland", "2026-09-24", product="debit", opened="2026-09-24",
               first_deposit="2026-09-28", history=False)
    bg.gen_history(ctx, p.cust, p.acct, p.card, "2026-09-28", "2026-10-12", drives=True, recurring=False, scale=2.0,
                   exclude_cats=("fuel",))
    bg.gen_login_events(ctx, p.cust, p.acct, p.devices, p.ip, "2026-09-24", "2026-10-20", per_month=6)
    pine = bg.make_merchant(ctx, "Pinegrove Fuel #22", "5542", "in_store", "Cleveland", merchant_id="MER-90008",
                            descriptor="PINEGROVE FUEL #22 CLEVELAND OH", acquirer_id="ACQ-02", onboarded="2015-07-01",
                            is_hero=True)
    volt = _merchant_by_name(ctx, "Voltcart Online")
    gift = _merchant_by_name(ctx, "Giftlane Cards")
    bg.add_event(ctx, p.cust["customer_id"], p.acct["account_id"], "deposit_received", utc("2026-09-28", "06:00:00"),
                 channel="ach", detail={"amount": "2140.55", "type": "payroll_direct_deposit", "first_deposit": True})
    bg.add_event(ctx, p.cust["customer_id"], p.acct["account_id"], "deposit_received", utc("2026-10-09", "06:00:00"),
                 channel="ach", detail={"amount": "2140.55", "type": "payroll_direct_deposit"})
    bg.add_txn(ctx, p.acct, p.card, pine, "2026-09-30", "18:42:00", "46.12", channel="in_store", pos_entry_mode="90",
               card_present=True, is_hero=True)
    t_gift = bg.add_txn(ctx, p.acct, p.card, gift, "2026-10-09", "02:05:00", "59.00", channel="ecommerce", txn_id="TXN-9000802",
                        avs_result="U", eci="07", cavv_present=False, three_ds_status="", cvv2_presence="0", cvv2_result="",
                        merchant_timezone="America/New_York", txn_local_datetime="2026-10-09 02:05:00",
                        auth_timestamp_utc=utc("2026-10-09", "02:05:00"), is_hero=True)
    t_volt = bg.add_txn(ctx, p.acct, p.card, volt, "2026-10-09", "02:17:00", "1240.00", channel="ecommerce", txn_id="TXN-9000801",
                        avs_result="N", eci="07", cavv_present=False, three_ds_status="", cvv2_presence="0", cvv2_result="",
                        merchant_timezone="America/New_York", txn_local_datetime="2026-10-09 02:17:00",
                        auth_timestamp_utc=utc("2026-10-09", "02:17:00"), is_hero=True)
    bg.add_txn(ctx, p.acct, p.card, volt, "2026-10-10", "01:55:00", "412.33", channel="ecommerce", txn_id="TXN-9000803",
               avs_result="N", eci="07", cvv2_presence="0", cvv2_result="", auth_response_code="59", is_hero=True,
               merchant_timezone="America/New_York", txn_local_datetime="2026-10-10 01:55:00",
               auth_timestamp_utc=utc("2026-10-10", "01:55:00"))
    cid, aid = p.cust["customer_id"], p.acct["account_id"]
    bg.add_event(ctx, cid, aid, "alert_sent", utc("2026-10-10", "01:55:30"), channel="push",
                 detail={"alert": "declined_transaction", "merchant": "VOLTCART ONLINE", "amount": "412.33"})
    bg.add_event(ctx, cid, aid, "alert_opened", utc("2026-10-10", "07:31:00"), channel="mobile_app", device_id=p.phone["device_id"],
                 ip=p.ip, detail={"alert": "declined_transaction"})
    bg.add_event(ctx, cid, aid, "ivr_call", utc("2026-10-13", "09:14:00"), channel="ivr", detail={"authenticated": "otp_sms"})
    bg.add_event(ctx, cid, aid, "card_locked", utc("2026-10-13", "09:19:00"), channel="agent", detail={"card_id": p.card["card_id"]})
    bg.add_event(ctx, cid, aid, "card_reissue_requested", utc("2026-10-13", "09:21:00"), channel="agent",
                 detail={"card_id": p.card["card_id"], "reason": "suspected_compromise"})
    case = "DSP-2026-90009"
    intake = utc("2026-10-13", "09:20:00")
    bg.add_dispute(ctx, case, [t_volt, t_gift], "REG_E", intake,
                   "Unauthorized online purchases VoltCart $1,240.00 and Giftlane $59.00; card in possession.",
                   "fraud_cnp", intake_channel="phone", intake_authenticated_via="ivr_otp", assigned_queue="fraud_cnp",
                   stage="investigating", is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: unauthorized debit card transactions (oral notice)")
    bg.add_devent(ctx, case, utc("2026-10-13", "09:25:00"), "note_added",
                  "Rep note: customer saw declined alert Sat 10/10 AM but did not call until Tue 10/13. Card not lost. "
                  "Consider $50/$500 liability? Legacy bulletin says provisional credit within 10 calendar days.",
                  actor="rep.dfarrow")
    bg.add_comm(ctx, cid, intake, "inbound", "phone_summary", "cardholder",
                "Customer opened checking 3 weeks ago. Sees $1,240 VoltCart Online and $59 Giftlane Cards on 10/9 he did not make. "
                "Got a 'declined transaction' push on Saturday morning, thought it was a glitch, called today. Card is in his "
                "wallet; has only used it for gas and groceries.", case_id=case, subject="Unauthorized transactions")
    bg.add_packet(ctx, "MEP-90009-OI", case, t_volt["txn_id"], volt["merchant_id"], "order_insight", "", AS_OF_ISO, dict(
        order=dict(order_id="VC-3389172", placed_at=utc("2026-10-09", "02:16:40"),
                   items=[dict(description="Aerion 16in gaming laptop RTX", qty=1, price="1240.00")]),
        customer_account=dict(login_id="guest_checkout", email="cn.orders88@example.net", account_created_at=utc("2026-10-09", "02:11:02")),
        session=dict(ip="203.0.113.77", device_fingerprint="fp_" + "9f3c1e7a" * 5, user_agent="Mozilla/5.0 (X11; Linux x86_64)"),
        shipping_address="4410 Industrial Pkwy Unit 7, Toledo, OH 43604", billing_address_entered="1 Main St, Cleveland, OH 44101",
        shipments=[dict(carrier="ParcelPath", tracking_number="PP44100772913", events=[
            dict(ts=utc("2026-10-09", "16:00:00"), status="shipped"), dict(ts=utc("2026-10-11", "11:20:00"), status="delivered",
                                                                           address="4410 Industrial Pkwy Unit 7, Toledo, OH 43604")])],
        prior_transactions=[], merchant_statement="Guest checkout; no prior relationship; AVS mismatch accepted by merchant rules."))
    bg.add_ip(ctx, "203.0.113.77", "hosting", "Nimbuscloud VPS", "", "datacenter / VPS range")
    # ---- planted common point of compromise among Cleveland background customers
    cle = [r for r in ctx.people if r["city"] == "Cleveland"]
    victims, noise = cle[:9], cle[9:34]
    fraud_merchants = [_merchant_by_name(ctx, n) for n in ("Circuitry Loft", "Pixelwave Electronics", "Giftlane Cards",
                                                            "Solewright", "Hatchmark")]
    for i, r in enumerate(victims):
        acct, card = r["accounts"][-1], r["cards"][-1]
        vday = "2026-09-%02d" % (20 + i)
        if i >= 8:
            vday = "2026-10-02"
        bg.add_txn(ctx, acct, card, pine, vday, "17:%02d:00" % (10 + i), m(ctx.rng.uniform(31, 72)), channel="in_store",
                   pos_entry_mode=ctx.rng.choice(["90", "05", "90"]), card_present=True)
        fday = add_days(vday, ctx.rng.randint(9, 14))
        fm = fraud_merchants[i % len(fraud_merchants)]
        ft = bg.add_txn(ctx, acct, card, fm, fday, "03:%02d:00" % (5 + i), m(ctx.rng.uniform(220, 1400)), channel="ecommerce",
                        avs_result="N", eci="07", cavv_present=False, three_ds_status="", cvv2_presence="0", cvv2_result="",
                        merchant_timezone="America/New_York", txn_local_datetime=f"{fday} 03:{5 + i:02d}:00",
                        auth_timestamp_utc=utc(fday, f"03:{5 + i:02d}:00"))
        opened = add_days(fday, ctx.rng.randint(1, 4))
        dcid = f"DSP-2026-0{9201 + i}"
        closed = opened < "2026-10-08"
        dsp = bg.add_dispute(ctx, dcid, [ft], acct["regime"], utc(opened, "11:00:00"),
                             "Did not authorize online purchase; card in possession.", "fraud_cnp", assigned_queue="fraud_cnp",
                             stage="closed" if closed else "dispute_filed", status="closed" if closed else "open",
                             network_condition="10.4", dispute_processing_date=add_days(opened, 2),
                             cardholder_outcome="credited" if closed else "", network_outcome="issuer_won" if closed else "",
                             closed_at=utc(add_days(opened, 12), "16:00:00") if closed else "",
                             provisional_credit_amount=ft["billing_amount"], provisional_credit_at=utc(add_days(opened, 1), "10:00:00"))
        ft["fraud_reported_at"] = utc(add_days(opened, 1), "09:00:00")
        bg.add_devent(ctx, dcid, dsp["opened_at"], "intake_created", "Unauthorized CNP transaction claim")
        bg.add_devent(ctx, dcid, ft["fraud_reported_at"], "fraud_reported", "Fraud activity reported (TC40)")
        bg.add_comm(ctx, r["customer"]["customer_id"], dsp["opened_at"], "inbound", "phone_summary", "cardholder",
                    f"Did not make ${ft['billing_amount']} purchase at {ft['descriptor']} on {fday}. Card in wallet.", case_id=dcid)
        ctx.bg_labels.append(dict(case_id=dcid, family="fraud_cnp", true_nature="third_party_fraud_skimming_cpp",
                                  expected_network_condition="10.4", expected_cardholder_outcome="credited",
                                  status=dsp["status"], historical_decision_correct=True))
    for r in noise:
        acct, card = r["accounts"][-1], r["cards"][-1]
        bg.add_txn(ctx, acct, card, pine, "2026-%02d-%02d" % (ctx.rng.randint(5, 8), ctx.rng.randint(1, 28)), "12:30:00",
                   m(ctx.rng.uniform(25, 70)), channel="in_store", pos_entry_mode=ctx.rng.choice(["05", "07"]), card_present=True)
    research(ctx, "WEB-04156", "Police: card skimmer found inside pump at Cleveland gas station",
             "https://www.lakeshorenews.example/2026/10/15/skimmer-found-pinegrove-fuel", "Lakeshore News (fictional)",
             "2026-10-15", "2026-10-16", "news", """
Cleveland police say a technician found a Bluetooth card skimmer inside **pump 6 at Pinegrove Fuel #22** on
West 25th Street during maintenance on Tuesday. Investigators believe the device may have been installed in
mid-September. Customers who used a card at that pump between September 15 and October 13 are urged to review
their statements.
""", pine["merchant_id"])
    truth(ctx, case, code="C08", title="Pump Six", depth="L3", regime="REG_E", customer_id=cid, txn_ids=[t_volt["txn_id"], t_gift["txn_id"]],
          summary="Debit CNP fraud after skimming at Pinegrove Fuel #22. Reg E: card not lost → $0 liability (60-day rule only). "
                  "New account (transfers within 30 days of first deposit) → 20 business days for provisional credit, 90 days to "
                  "investigate; bank holiday calendar. CPP discoverable via graph across 9 other victims. Chargeback $1,240 (10.4); "
                  "$59 below fraud recovery threshold → write off (cardholder still credited).",
          expected=dict(is_dispute=True, claim_family="fraud_cnp",
                        network_actions=[dict(txn_id=t_volt["txn_id"], action="file_dispute", condition="10.4", amount="1240.00",
                                              prerequisite="fraud_reported"),
                                         dict(txn_id=t_gift["txn_id"], action="write_off_no_chargeback", amount="59.00",
                                              prerequisite="fraud_reported")],
                        cardholder_resolution=dict(outcome="credited", credit_amount="1299.00", liability_amount="0.00"),
                        deadlines=dict(provisional_credit_deadline="2026-11-10", investigation_deadline="2027-01-11",
                                       written_confirmation_due_if_bank_requires="2026-10-27"),
                        account_actions=["fraud_report_tc40", "card_reissue"],
                        adjudication=dict(review_panel_required=True, reason="cross-customer finding (compromise point)"),
                        automated_actions=[
                            dict(action="graph_write", edge="SUSPECTED_COMPROMISE_POINT", subject_id="MER-90008", status="active",
                                 evidence=["DSP-2026-09201..09209", "WEB-04156"]),
                            dict(action="watchlist_add", list="merchant_compromise_points", subject_id="MER-90008",
                                 window="2026-09-15..2026-10-13"),
                            dict(action="enhanced_monitoring", scope="cards with card-present use at MER-90008 in window and no fraud claim yet",
                                 optional=True)]),
          key_facts=[dict(id="F1", fact="Account opened 2026-09-24; first deposit 2026-09-28; transfers 2026-10-09 (within 30 days)", evidence=["ACC-DDA-90008", "account_events deposit_received"]),
                     dict(id="F2", fact="Card not lost or stolen; compromise via skimming", evidence=["COM intake", "WEB-04156"]),
                     dict(id="F3", fact="Notice 2026-10-13; bank closed 2026-10-12 and 2026-11-11", evidence=["reference/bank_holidays_2026.csv"]),
                     dict(id="F4", fact="AVS N, no 3DS, guest checkout from hosting IP, ship to Toledo industrial unit", evidence=["TXN-9000801", "MEP-90009-OI"]),
                     dict(id="F5", fact="9 other cardholders used MER-90008 between 2026-09-20 and 2026-10-02 then reported CNP fraud", evidence=["graph/sql: DSP-2026-09201..09209"])],
          contradictions=[dict(id="X1", between=["rep note: consider $50/$500 tier", "REGE-1005.6"], resolution="tiers for lost/stolen access device only; card not lost"),
                          dict(id="X2", between=["MEM-0152 / LFB-CB-2025-03: 10 calendar days", "LFB-CB-2025-09 + REGE-1005.11"], resolution="business days; new-account 20 business days")],
          computations=[dict(name="new_account", value=True, rule="transfer within 30 days after first deposit"),
                        dict(name="provisional_credit_deadline", value="2026-11-10", rule="20 business days after 2026-10-13 excl. weekends/holidays"),
                        dict(name="investigation_deadline", value="2027-01-11", rule="90 calendar days"),
                        dict(name="liability", value="0.00")],
          must_cite=["REGE-1005.11", "REGE-1005.6", "LFB-SOP-DSP-006@v4", "LFB-CB-2025-09", "LFB-SOP-DSP-008@v3", "VISA-10.4@2026-04-18"],
          must_not=["assess $50 or $500 liability", "use calendar days", "use 10-business-day deadline 2026-10-27 as provisional credit deadline",
                    "charge back the $59", "close without fraud report"],
          memory_ops=dict(read=["MEM-0152"], supersede=[dict(note_id="MEM-0152", replaced_by="LFB-CB-2025-09")],
                          write=[dict(scope="graph", edge="SUSPECTED_COMPROMISE_POINT", subject_id="MER-90008", status="active")]),
          components=["router (regime)", "sandbox (business days)", "graph_traversal (CPP)", "subagents (graph analyst, reg E)",
                      "research", "memory_forgetting", "memory_write (graph)", "automated_controls (watchlist)"],
          deterministic_checks=[dict(path="regime", op="eq", value="REG_E"),
                                dict(path="cardholder_resolution.liability_amount", op="eq", value="0.00"),
                                dict(path="deadlines.provisional_credit_deadline", op="eq", value="2026-11-10"),
                                dict(path="network_actions[?txn_id=='TXN-9000801'].condition", op="eq", value="10.4"),
                                dict(path="network_actions[?txn_id=='TXN-9000802'].action", op="eq", value="write_off_no_chargeback")],
          rubric=["Explains why the 2-business-day tier does not apply", "Surfaces Pinegrove #22 with supporting counts"],
          budget=dict(expected_tool_calls="12-25"))


def build(ctx: Ctx):
    c05_folio(ctx)
    c06_trial(ctx)
    c07_fx(ctx)
    c08_pump_six(ctx)
