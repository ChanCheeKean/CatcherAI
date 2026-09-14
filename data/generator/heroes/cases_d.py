"""Hero cases C13–C19."""
from __future__ import annotations

import background as bg
from common import Ctx, add_days, m, money, utc
from derived import add_business_days, reg_z_resolution_deadline
from heroes.kit import AS_OF_ISO, full_address, person, persona, research, truth


def _merchant_by_name(ctx: Ctx, name: str) -> dict:
    return next(r for r in ctx.t["merchants"] if r["dba_name"] == name)


# =====================================================================================================
def c13_agent_booked(ctx: Ctx):
    p = person(ctx, 90018, "Ezra Holloway", "Boston", "2018-01-08", cycle_day=4, employer="Tern & Finch Legal")
    tz = "America/New_York"
    ctx.add("tokens", dict(token_id="TKN-90018-TM", card_id=p.card["card_id"], token_requestor_type="agentic_payment_provider",
                           token_requestor_name="TravelMind", provisioned_at=utc("2026-09-14", "19:02:00"),
                           device_id=p.phone["device_id"], status="active"))
    bg.add_event(ctx, p.cust["customer_id"], p.acct["account_id"], "token_provisioned", utc("2026-09-14", "19:02:00"),
                 channel="network", device_id=p.phone["device_id"],
                 detail={"token_id": "TKN-90018-TM", "requestor": "TravelMind", "requestor_type": "agentic_payment_provider",
                         "cardholder_verification": "issuer_app_biometric"}, is_hero=True)
    sky = bg.make_merchant(ctx, "Skylark Air", "4511", "ecommerce", "Denver", merchant_id="MER-90016", descriptor="SKYLARK AIR 0192",
                           acquirer_id="ACQ-05", onboarded="2014-01-01", website="https://www.skylarkair.example", is_hero=True,
                           legal_suffix=" Holdings Inc")
    txn = bg.add_txn(ctx, p.acct, p.card, sky, "2026-10-02", "12:30:00", "412.60", channel="agentic_commerce", txn_id="TXN-9001501",
                     token_id="TKN-90018-TM", pos_entry_mode="10", card_present=False, cof_type="cit_subsequent", eci="07",
                     cavv_present=False, three_ds_status="", avs_result="Y", is_hero=True)
    case = "DSP-2026-90015"
    intake = utc("2026-10-16", "12:20:00", tz)
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake,
                   "AI travel agent (TravelMind) booked non-refundable fare despite 'refundable' instruction; cardholder cancelled trip.",
                   "fraud_cnp", intake_channel="secure_message", intake_authenticated_via="secure_online_banking",
                   assigned_queue="fraud_cnp", stage="investigating", is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Secure message: claims agent-made purchase was unauthorized")
    bg.add_devent(ctx, case, utc("2026-10-17", "09:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "secure_message", "cardholder",
                "I use TravelMind (the AI travel assistant) with my Lanternfield card. On Oct 1 I told it to book Boston–Denver for "
                "Nov 14–17 and specifically said REFUNDABLE fare, max $450. It booked a Skylark Air Basic Economy ticket for $412.60 "
                "that is non-refundable. My plans changed and Skylark won't refund or even give credit. I never authorized a "
                "non-refundable ticket. Please reverse this charge as unauthorized.", case_id=case, merchant_id=sky["merchant_id"],
                subject="Unauthorized non-refundable ticket",
                attachments=[{"name": "travelmind_chat_screenshot.png", "description":
                              "Screenshot of TravelMind chat 2026-10-01 10:12: user: 'Book me a round trip BOS to DEN, leave Nov 14 after "
                              "3pm, come back Nov 17 evening. Refundable fare preferred. Max $450 total.' TravelMind: 'Got it! I'll find "
                              "the best option within your budget and book it for you.'"},
                             {"name": "skylark_confirmation.eml", "description":
                              "Skylark Air confirmation QX7R2M, booked 2026-10-02 12:30 MT via TravelMind. BOS–DEN SK 1184 Nov 14 16:05, "
                              "DEN–BOS SK 1191 Nov 17 18:40. Fare: Basic Economy. 'Basic Economy fares are non-refundable and cannot be "
                              "changed. Free cancellation within 24 hours of booking.' Total $412.60."},
                             {"name": "skylark_cancellation.eml", "description":
                              "2026-10-09: 'Your trip QX7R2M has been cancelled. Basic Economy fares are not eligible for refund or travel credit.'"}])
    bg.add_packet(ctx, "MEP-90015-APP", case, txn["txn_id"], "", "agentic_provider_record_on_written_request", "",
                  utc("2026-10-23", "11:00:00"), dict(
                      provider=dict(name="TravelMind", role="Agentic Payment Provider", program="Visa Intelligent Commerce (enrolled)"),
                      cardholder_consent=dict(ts=utc("2026-09-14", "19:01:00"), identity_verification="issuer biometric via token provisioning",
                                              acknowledged_responsibility_text="I understand I am responsible for purchases TravelMind makes on my behalf within my instructions.",
                                              policy_acceptance_mode="pre-consented at instruction time",
                                              policy_acceptance_text="TravelMind may accept fare rules and merchant policies needed to complete bookings within your criteria."),
                      instruction=dict(created_at=utc("2026-10-01", "10:12:00"), expires_at=utc("2026-10-08", "23:59:00"),
                                       raw_text="Book me a round trip BOS to DEN, leave Nov 14 after 3pm, come back Nov 17 evening. Refundable fare preferred. Max $450 total.",
                                       parsed=dict(hard_constraints=["origin=BOS", "destination=DEN", "depart=2026-11-14 after 15:00",
                                                                     "return=2026-11-17 after 17:00", "max_total_usd=450"],
                                                   preferences=["fare_refundable=true"]),
                                       parsed_confirmation_shown_to_user=True),
                      options_evaluated=[dict(carrier="Skylark Air", fare="Basic Economy", total="412.60", refundable=False, within_hard_constraints=True),
                                         dict(carrier="Skylark Air", fare="Main Cabin Flex", total="489.20", refundable=True, within_hard_constraints=False),
                                         dict(carrier="Bluecrest Airways", fare="Standard", total="531.00", refundable=True, within_hard_constraints=False)],
                      decision_log="Selected lowest-cost option satisfying all hard constraints. Preference 'refundable' could not be met within max_total_usd=450.",
                      booking_notification=dict(ts=utc("2026-10-02", "14:31:00"), channel="push",
                                                text="Booked! Skylark Air QX7R2M $412.60 (Basic Economy — non-refundable; free cancellation for 24h). Tap to review."),
                      order_confirmation_retention="available to cardholder for 120 days"))
    research(ctx, "WEB-04177", "TravelMind Terms — Booking Guarantee", "https://www.travelmind.example/terms#guarantee", "TravelMind Inc (fictional)",
             "2026-08-01", "2026-10-16", "agentic_provider_terms", """
**Booking Guarantee.** If TravelMind completes a purchase that violates one of your **hard constraints** (for example
destination, dates, or maximum price), we will refund the difference or the full purchase at our option.
**Preferences** (such as seat type or refundability) are applied on a best-effort basis and are not covered by the
Booking Guarantee. TravelMind shows you how it interpreted your request before booking.

**Disputes.** Please contact TravelMind Support before disputing a charge with your bank.
""")
    research(ctx, "WEB-04184", "Skylark Air — Fare types", "https://www.skylarkair.example/fares", "Skylark Air", "2026-01-10", "2026-10-16",
             "merchant_policy", """
| Fare | Changes | Refund | 24-hour cancellation |
|---|---|---|---|
| Basic Economy | Not permitted | No refund, no travel credit | Yes, if cancelled within 24h of booking |
| Main Cabin Flex | Free | Full refund | Yes |
""", sky["merchant_id"])
    truth(ctx, case, code="C13", title="The Agent Booked It", depth="L4", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="Agentic Transaction by TravelMind within hard constraints but against a stated preference. Visa §4.1.24 imposes "
                  "duties on the Agentic Payment Provider (use only cardholder-defined criteria; obtain responsibility acknowledgment; "
                  "provide records on written request) but no dispute condition addresses agent-exceeded instructions. No clean route.",
          expected=dict(is_dispute=False, claim_family="agentic_transaction_instruction_dispute",
                        wait=dict(for_="MEP-90015-APP (agentic provider instruction record)", available_at="2026-10-23T15:00:00Z",
                                  latest_safe_decision_date=add_business_days(reg_z_resolution_deadline("2026-10-16", 4), -2),
                                  rule="determinative evidence arrives well before the regulatory deadline → suspend and resume"),
                        network_actions=[dict(txn_id=txn["txn_id"], action="no_dispute",
                                              reason="no Visa condition fits; cardholder authorized the agent within hard constraints")],
                        cardholder_resolution=dict(outcome="denied_with_explanation", credit_amount="0.00",
                                                   note="no billing error: purchase within cardholder-defined hard constraints; 'refundable' was a "
                                                        "preference shown back to the cardholder; non-refundable fare and 24h cancellation disclosed at booking"),
                        cardholder_guidance=["TravelMind Booking Guarantee covers hard constraints only (WEB-04177)", "TravelMind complaint process"],
                        adjudication=dict(review_panel_required=True, reason="no applicable rule / novel transaction type (SOP-DSP-003 §2.4)",
                                          min_confidence=0.75, conservative_default_applied=False,
                                          flip_fact="instruction record showing 'refundable' parsed as a hard constraint, or no booking disclosure"),
                        automated_actions=[dict(action="request_record", target="TravelMind", basis="VISA-4.1.24-AGENTIC@2026-04-18 written request"),
                                           dict(action="policy_gap_record", topic="agentic transaction outside cardholder preference",
                                                conditions_considered=["10.4", "13.1", "13.5", "13.7"])]),
          key_facts=[dict(id="F1", fact="Token provisioned to TravelMind 2026-09-14 with issuer biometric verification", evidence=["tokens TKN-90018-TM", "account_events token_provisioned"]),
                     dict(id="F2", fact="Instruction: max $450 hard; refundable 'preferred'", evidence=["COM attachment travelmind_chat_screenshot.png", "MEP-90015-APP"]),
                     dict(id="F3", fact="Refundable option cost $489.20 (> max)", evidence=["MEP-90015-APP.options_evaluated"]),
                     dict(id="F4", fact="Booking notification disclosed non-refundable and 24h free cancellation", evidence=["MEP-90015-APP.booking_notification", "WEB-04184"]),
                     dict(id="F5", fact="Cardholder acknowledged responsibility for agent purchases", evidence=["MEP-90015-APP.cardholder_consent"])],
          conditions_considered=[dict(condition="10.4", fails_because="cardholder authorized the agent and acknowledged responsibility; tokenized, verified"),
                                 dict(condition="13.1", fails_because="service was available; cardholder cancelled"),
                                 dict(condition="13.7", fails_because="merchant disclosed and applied its fare rules"),
                                 dict(condition="13.5", fails_because="misrepresentation by merchant not alleged; agentic provider is not a merchant")],
          must_cite=["VISA-4.1.24-AGENTIC@2026-04-18", "VISA-10.4@2026-04-18", "VISA-13.7@2026-04-18", "REGZ-1026.13", "LFB-SOP-DSP-003@v6"],
          must_not=["file 10.4", "invent a dispute condition", "decide before the instruction record arrives", "wait for a human"],
          components=["router (novel type)", "research (network rules + provider terms)", "semantic_retrieval (no precedent found)",
                      "loop suspend/resume on external event (APP record 2026-10-23)", "automated review panel", "policy gap record"],
          deterministic_checks=[dict(path="network_actions[0].action", op="eq", value="no_dispute"),
                                dict(path="cardholder_resolution.outcome", op="eq", value="denied_with_explanation"),
                                dict(path="adjudication.review_panel_used", op="eq", value=True),
                                dict(path="automated_actions[*].action", op="contains", value="policy_gap_record")],
          rubric=["Acknowledges absence of precedent explicitly rather than stretching a weak one"],
          budget=dict(expected_tool_calls="8-18"))


# =====================================================================================================
def c14_time_zones(ctx: Ctx):
    p = person(ctx, 90019, "Linden Crowe", "Los Angeles", "2010-03-03", cycle_day=27)
    tz_ny = "America/New_York"
    hotel = bg.make_merchant(ctx, "Harbor & Vine Hotel", "7011", "in_store", "New York", state="NY", tz=tz_ny,
                             merchant_id="MER-90017", descriptor="HARBOR AND VINE HOTEL NY", acquirer_id="ACQ-06",
                             onboarded="2012-05-01", website="https://www.harborandvine.example", phone="(212) 555-0161",
                             is_hero=True, legal_suffix=" Hospitality LLC")
    txn = bg.add_txn(ctx, p.acct, p.card, hotel, "2026-10-12", "11:00:00", "608.18", channel="card_not_present",
                     txn_id="TXN-9001601", pos_entry_mode="10", card_present=False, cof_type="mit_unscheduled", eci="07",
                     is_hero=True)
    case = "DSP-2026-90016"
    intake = utc("2026-10-14", "10:05:00", "America/Los_Angeles")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Billed 2-night no-show at Harbor & Vine after cancelling by phone before deadline.",
                   "cancelled_merch", intake_channel="phone", assigned_queue="consumer_disputes", stage="awaiting_merchant_evidence",
                   provisional_credit_amount="608.18", provisional_credit_at=utc("2026-10-16", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: no-show charge after cancellation")
    bg.add_devent(ctx, case, utc("2026-10-15", "09:00:00"), "order_insight_requested", "Order Insight request sent")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Cardholder booked Harbor & Vine NYC Oct 10-12 for a conference, $265/night, guaranteed with card. Conference was "
                "cancelled; cardholder called the hotel Wednesday Oct 8 around 2:40 in the afternoon and was told 'you're all set'. "
                "No cancellation number given. Hotel charged $608.18 on 10/12 as no-show for both nights. Emailed hotel 10/13, no answer.",
                case_id=case, merchant_id=hotel["merchant_id"], subject="No-show charge",
                attachments=[{"name": "harborvine_confirmation.eml", "description":
                              "Reservation HV-30917 made 2026-09-25: King room, Oct 10–12 (2 nights), $265.00/night + 14.75% tax, "
                              "guaranteed. 'Cancellations must be received by 6:00 PM hotel local time two days prior to arrival "
                              "to avoid a charge.'"},
                             {"name": "phone_call_log.png", "description":
                              "Phone recents screenshot (phone region: Los Angeles): 'Wed, Oct 8 · 2:41 PM · (212) 555-0161 · Outgoing · 4 min'"}])
    bg.add_packet(ctx, "MEP-90016-OI", case, txn["txn_id"], hotel["merchant_id"], "order_insight", utc("2026-10-15", "09:00:00"),
                  utc("2026-10-17", "16:10:00"), dict(
                      reservation=dict(confirmation="HV-30917", arrival="2026-10-10", departure="2026-10-12", nights=2, rate="265.00",
                                       guarantee="credit card", cancellation_policy="Cancel by 6:00 PM hotel local time 2 days prior to arrival."),
                      pms_log=[dict(ts_local="2026-09-25 13:20", tz="America/New_York", event="reservation_created", channel="web"),
                               dict(ts_local="2026-10-11 23:59", tz="America/New_York", event="no_show_posted", nights_charged=2)],
                      call_center_log="No cancellation record found for HV-30917. Calls to the front desk are not logged.",
                      charge=dict(nights=2, room="530.00", tax="78.18", total="608.18"),
                      merchant_statement="No cancellation was recorded; no-show billed per guaranteed reservation policy."))
    truth(ctx, case, code="C14", title="Three Time Zones", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="Cardholder's call at 2:41 PM PT on Oct 8 = 5:41 PM ET, before the 6:00 PM hotel-local deadline. Hotel also billed "
                  "more than one night for a no-show, independently improper. Precedent PRE-0019 looks the same but the call was late.",
          expected=dict(is_dispute=True, claim_family="cancelled_guaranteed_reservation",
                        network_actions=[dict(txn_id=txn["txn_id"], action="file_dispute", condition="13.7", amount="608.18",
                                              certification=["cardholder properly cancelled on 2026-10-08 17:41 ET",
                                                             "no-show billed for more than one night"])],
                        cardholder_resolution=dict(outcome="provisional_credit_pending_network", credit_amount="608.18"),
                        fallback=dict(minimum_valid_amount="304.09", basis="no-show billed for more than one day's accommodation"),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Deadline 2026-10-08 18:00 America/New_York", evidence=["COM attachment harborvine_confirmation.eml", "MEP-90016-OI"]),
                     dict(id="F2", fact="Call 2026-10-08 14:41 America/Los_Angeles = 17:41 America/New_York, 4 min to hotel number", evidence=["COM attachment phone_call_log.png", "merchants MER-90017.phone"]),
                     dict(id="F3", fact="Hotel does not log front-desk calls", evidence=["MEP-90016-OI.call_center_log"]),
                     dict(id="F4", fact="No-show charged for 2 nights", evidence=["MEP-90016-OI.charge"])],
          computations=[dict(name="call_time_hotel_local", value="2026-10-08T17:41:00-04:00"),
                        dict(name="cancelled_before_deadline", value=True),
                        dict(name="one_night_with_tax", value="304.09", rule="265*1.1475 half-up")],
          must_cite=["VISA-13.7@2026-04-18"],
          must_not=["conclude the call was late", "copy PRE-0019 partial outcome", "require a cancellation code as a condition"],
          precedents=dict(distinguish=["PRE-0019"]),
          components=["sandbox (timezones, tax)", "semantic_retrieval (precedent)", "verifier", "skills (T&E lodging)"],
          deterministic_checks=[dict(path="network_actions[0].condition", op="eq", value="13.7"),
                                dict(path="network_actions[0].amount", op="eq", value="608.18")],
          rubric=["States both the time-zone conversion and the more-than-one-night rule", "Explains why PRE-0019 differs"],
          budget=dict(expected_tool_calls="6-14"))


# =====================================================================================================
def c15_membership(ctx: Ctx):
    p = person(ctx, 90020, "Freya Janowski", "Austin", "2018-09-09", cycle_day=5, behavior="partial", exclude_cats=("gym",))
    tz = "America/Chicago"
    gym = bg.make_merchant(ctx, "Ironwood Athletic Club", "7997", "recurring", "Austin", merchant_id="MER-90018",
                           descriptor="IRONWOOD ATHLETIC CLUB", acquirer_id="ACQ-06", onboarded="2011-01-01",
                           website="https://www.ironwoodathletic.example", phone="(512) 555-0122", is_hero=True)
    months = ["2025-10-01", "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01",
              "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"]
    txns = {}
    for day in months:
        txns[day] = bg.add_txn(ctx, p.acct, p.card, gym, day, "04:00:00", "64.00", channel="recurring", processing_lag=1,
                               txn_id={"2026-09-01": "TXN-9001701", "2026-10-01": "TXN-9001702"}.get(day),
                               is_hero=day in ("2026-09-01", "2026-10-01"))
    sep, octo = txns["2026-09-01"], txns["2026-10-01"]
    c1 = "DSP-2026-90017"
    o1 = utc("2026-09-18", "12:30:00", tz)
    bg.add_dispute(ctx, c1, [sep], "REG_Z", o1, "Cancelled Ironwood membership 8/28; charged 9/1.", "cancelled_recurring",
                   intake_channel="phone", assigned_queue="consumer_disputes", stage="pre_arb_decision_due",
                   network_condition="13.2", network_case_ref="VRL7719203385", dispute_processing_date="2026-09-21",
                   response_processing_date="2026-10-16", provisional_credit_amount="64.00",
                   provisional_credit_at=utc("2026-09-19", "10:00:00"), related_case_ids="DSP-2026-90018", is_hero=True)
    for ts, et, sm, actor in ((o1, "intake_created", "Phone intake: cancelled recurring", "system"),
                              (utc("2026-09-19", "09:00:00"), "ack_letter_sent", "Billing-rights acknowledgment sent", "system"),
                              (utc("2026-09-19", "10:00:00"), "provisional_credit_posted", "Temporary credit 64.00 posted", "system"),
                              (utc("2026-09-21", "15:10:00"), "dispute_filed", "Visa 13.2 dispute filed; cardholder certified withdrawal of permission 2026-08-28", "analyst.cwright"),
                              (utc("2026-10-16", "16:40:00"), "dispute_response_received", "Acquirer Dispute Response received with membership agreement and usage logs", "system")):
        bg.add_devent(ctx, c1, ts, et, sm, actor=actor)
    bg.add_comm(ctx, p.cust["customer_id"], o1, "inbound", "phone_summary", "cardholder",
                "Cardholder emailed Ironwood on Aug 28 to cancel because she's moving. Still charged $64 on Sept 1. "
                "'I haven't been since August.' Provided the email and the club's auto-reply.", case_id=c1, merchant_id=gym["merchant_id"],
                subject="Cancelled membership charged",
                attachments=[{"name": "cancel_email_and_autoreply.eml", "description":
                              "2026-08-28 21:10 CDT cardholder → members@ironwoodathletic.example: 'Please cancel my membership effective "
                              "immediately, I am moving.' 21:11 auto-reply: 'We received your cancellation request. Per your membership "
                              "agreement, 30 days' written notice is required. Your final billing date will be September 1, 2026.'"}])
    bg.add_packet(ctx, "MEP-90017-DR", c1, sep["txn_id"], gym["merchant_id"], "dispute_response", "2026-09-21T15:10:00Z",
                  utc("2026-10-16", "16:40:00"), dict(
                      membership_agreement=dict(signed_at=utc("2025-01-10", "17:05:00", tz), signature="electronic",
                                                clause_7="Either party may terminate this membership with thirty (30) days' written notice. "
                                                         "Monthly dues are billed on the 1st and are not prorated."),
                      cancellation=dict(received_at=utc("2026-08-28", "21:10:00", tz), auto_reply_final_billing_date="2026-09-01"),
                      badge_scans=[dict(ts=utc("2026-09-10", "18:32:00", tz), location="Main floor turnstile"),
                                   dict(ts=utc("2026-09-14", "09:05:00", tz), location="Pool entrance")],
                      merchant_statement="Member gave notice on 8/28; 30-day notice period covers the 9/1 dues as disclosed in the signed "
                                         "agreement and confirmed in our reply. Member used the club on 9/10 and 9/14."))
    c2 = "DSP-2026-90018"
    o2 = utc("2026-10-19", "17:45:00", tz)
    bg.add_dispute(ctx, c2, [octo], "REG_Z", o2, "Ironwood charged again 10/1 after cancellation.", "cancelled_recurring",
                   intake_channel="phone", assigned_queue="consumer_disputes", stage="intake", related_case_ids=c1, is_hero=True)
    bg.add_devent(ctx, c2, o2, "intake_created", "Phone intake: second post-cancellation charge")
    bg.add_comm(ctx, p.cust["customer_id"], o2, "inbound", "phone_summary", "cardholder",
                "Same issue as the September dispute — Ironwood charged $64 again on October 1. Cardholder has moved out of Austin.",
                case_id=c2, merchant_id=gym["merchant_id"])
    persona(ctx, c1, p.cust["customer_id"],
            profile="Moved from Austin in early October; thought membership ran until end of September.",
            knows=["Visited the gym twice in September (pool on the 14th)", "Moved out of Austin 2026-10-03"],
            disclosure_rules=["Admits visits when shown badge scan dates"],
            scripted_replies=[dict(trigger="agent shares badge scans and asks for explanation", delay_minutes=300,
                                   reply="Yes, I went twice in September — I thought my membership ran until the end of the month since I'd paid for September. I haven't been since I moved on Oct 3."),
                              dict(trigger="agent explains Sep charge will stand and Oct charge will be disputed", delay_minutes=120,
                                   reply="OK, that's fair about September. Thank you for fixing October.")])
    truth(ctx, c1, code="C15", title="Membership Mid-Flight", depth="L3", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[sep["txn_id"], octo["txn_id"]], related_case_ids=[c2],
          summary="Sep charge already disputed (13.2); merchant's late Dispute Response shows disclosed 30-day notice term and "
                  "post-cancellation use → accept response after certified cardholder review. Oct charge is after the merchant's own "
                  "stated final billing date → new 13.2 dispute.",
          expected=dict(
              is_dispute=True, claim_family="cancelled_recurring",
              network_actions=[dict(txn_id=sep["txn_id"], case_id=c1, action="accept_dispute_response", amount="64.00",
                                    prerequisite="cardholder contacted to review evidence"),
                               dict(txn_id=octo["txn_id"], case_id=c2, action="file_dispute", condition="13.2", amount="64.00")],
              cardholder_resolution=[dict(case_id=c1, outcome="denied_with_explanation", reversal_amount="64.00"),
                                     dict(case_id=c2, outcome="provisional_credit_pending_network", credit_amount="64.00")],
              deadlines={c1: dict(pre_arb_deadline="2026-11-15", reg_z_resolution_deadline="2026-12-05"),
                         c2: dict(reg_z_resolution_deadline="2027-01-05", visa_dispute_time_limit="2027-01-30")},
              adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Signed agreement clause 7: 30 days' written notice", evidence=["MEP-90017-DR"]),
                     dict(id="F2", fact="Merchant auto-reply stated final billing date 2026-09-01", evidence=["COM attachment cancel_email_and_autoreply.eml"]),
                     dict(id="F3", fact="Badge scans 2026-09-10 and 2026-09-14", evidence=["MEP-90017-DR.badge_scans"]),
                     dict(id="F4", fact="Oct charge 2026-10-01 after merchant's own final billing date", evidence=["TXN-9001702"])],
          contradictions=[dict(id="X1", between=["intake: haven't been since August", "badge scans in September"], resolution="cardholder confirms visits")],
          computations=[dict(name="pre_arb_deadline", value="2026-11-15", rule="30 days from Dispute Response processing date 2026-10-16"),
                        dict(name="reg_z_deadline_c1", value="2026-12-05", rule="2 complete billing cycles after 2026-09-18 with cycle_day 5; 90-day cap 2026-12-17"),
                        dict(name="reg_z_deadline_c2", value="2027-01-05")],
          must_cite=["VISA-13.2@2026-04-18", "VISA-11.2-LIFECYCLE@2026-04-18", "REGZ-1026.13"],
          must_not=["make a pre-arbitration attempt on the September charge", "decline response without cardholder contact/certification",
                    "combine both charges in one dispute"],
          components=["mid-lifecycle state loading", "wait_for_event/late evidence", "replan", "sandbox (billing cycles)",
                      "parallel case tracks", "user_simulation", "certification duty"],
          deterministic_checks=[dict(path="network_actions[?case_id=='DSP-2026-90017'].action", op="eq", value="accept_dispute_response"),
                                dict(path="network_actions[?case_id=='DSP-2026-90018'].condition", op="eq", value="13.2"),
                                dict(path="deadlines.DSP-2026-90017.pre_arb_deadline", op="eq", value="2026-11-15")],
          rubric=["Tracks two charges at different lifecycle stages without conflating them"],
          budget=dict(expected_tool_calls="10-22"))
    ctx.ground_truth[c2] = dict(case_id=c2, see=c1, code="C15")


# =====================================================================================================
def c16_listing_changed(ctx: Ctx):
    p = person(ctx, 90021, "Imani Kowalczyk", "Chicago", "2019-12-01", cycle_day=23)
    mer = bg.make_merchant(ctx, "RenewTek Outlet", "5732", "ecommerce", "Austin", merchant_id="MER-90019", descriptor="RENEWTEK OUTLET",
                           acquirer_id="ACQ-08", onboarded="2023-05-01", website="https://www.renewtek.example", is_hero=True)
    txn = bg.add_txn(ctx, p.acct, p.card, mer, "2026-09-19", "13:05:00", "899.00", channel="ecommerce", txn_id="TXN-9001801",
                     eci="05", cavv_present=True, three_ds_status="Y", avs_result="Y", three_ds_browser_ip=p.ip, is_hero=True)
    case = "DSP-2026-90019"
    intake = utc("2026-10-12", "20:40:00", "America/Chicago")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Refurbished laptop battery far below advertised; return refused.",
                   "not_as_described", intake_channel="secure_message", intake_authenticated_via="secure_online_banking",
                   assigned_queue="consumer_disputes", stage="investigating", provisional_credit_amount="899.00",
                   provisional_credit_at=utc("2026-10-14", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Secure message intake: not as described")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "secure_message", "cardholder",
                "I bought a refurbished UltraBook 14 from RenewTek for $899 on Sept 19. The listing said Grade A, battery health at "
                "least 85%, and 30-day returns. It arrived Sept 26 and the battery health is 61% (it dies in about 90 minutes). I "
                "asked to return it on Sept 29 and they said refurbished items are final sale and refused to give me a return label. "
                "I still have the laptop and all packaging.", case_id=case, merchant_id=mer["merchant_id"], subject="Laptop not as described",
                attachments=[{"name": "battery_report.txt", "description":
                              "Windows battery report generated 2026-09-27 09:14: DESIGN CAPACITY 57,000 mWh; FULL CHARGE CAPACITY "
                              "34,770 mWh (61%). Cycle count 912."},
                             {"name": "renewtek_chat_2026-09-29.txt", "description":
                              "Customer: 'The battery is at 61% but the listing said 85%+. I'd like to return it.' Agent 'Mia': 'I'm sorry, "
                              "refurbished items are final sale. We can't issue an RMA.' Customer: 'Your listing says 30-day returns.' "
                              "Agent: 'Our policy is all refurbished sales are final.'"},
                             {"name": "delivery_confirmation.png", "description": "ParcelPath delivered 2026-09-26 to cardholder's address"}])
    bg.add_packet(ctx, "MEP-90019-OI", case, txn["txn_id"], mer["merchant_id"], "order_insight", "", AS_OF_ISO,
                  dict(status="not_enrolled", message="Merchant does not participate in Order Insight. No data returned."))
    research(ctx, "WEB-04191", "RenewTek — Refurbished UltraBook 14 (archived 2026-09-19)",
             "https://archive.pagevault.example/2026-09-19/https://www.renewtek.example/p/ultrabook-14-refurb", "PageVault archive (fictional)",
             "2026-09-01", "2026-09-19", "merchant_listing_snapshot", """
**Refurbished UltraBook 14 — Grade A** — $899.00

- Condition: Grade A — like new, minimal signs of use
- **Battery health guaranteed ≥ 85%**
- 90-day RenewTek warranty
- **30-day hassle-free returns** — free return label
""", mer["merchant_id"])
    research(ctx, "WEB-04198", "RenewTek — Refurbished UltraBook 14 (current)", "https://www.renewtek.example/p/ultrabook-14-refurb",
             "RenewTek Outlet", "2026-10-03", "2026-10-15", "merchant_listing_snapshot", """
**Refurbished UltraBook 14 — Grade A** — $849.00

- Condition: Grade A
- Battery health: varies
- **All refurbished sales are final.** Warranty claims only.
""", mer["merchant_id"])
    truth(ctx, case, code="C16", title="The Listing Changed", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="Not as described (battery 61% vs guaranteed ≥85%); return attempt refused although the listing at time of sale "
                  "promised 30-day returns (changed later). Attempt to return valid; waiting period waived when merchant refuses return.",
          expected=dict(is_dispute=True, claim_family="not_as_described",
                        network_actions=[dict(txn_id=txn["txn_id"], action="file_dispute", condition="13.3", amount="899.00",
                                              certification=["return attempted 2026-09-29; merchant refused RMA",
                                                             "merchandise at cardholder address"])],
                        acceptable_alternatives=[dict(condition="13.7", rationale="attempted return refused contrary to disclosed return policy")],
                        cardholder_resolution=dict(outcome="provisional_credit_pending_network", credit_amount="899.00"),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Listing at purchase date: battery ≥85%, 30-day returns", evidence=["WEB-04191"]),
                     dict(id="F2", fact="Battery report 61% full-charge capacity", evidence=["COM attachment battery_report.txt"]),
                     dict(id="F3", fact="Merchant refused RMA on 2026-09-29", evidence=["COM attachment renewtek_chat_2026-09-29.txt"]),
                     dict(id="F4", fact="Current listing (2026-10-15) says final sale", evidence=["WEB-04198"])],
          contradictions=[dict(id="X1", between=["merchant: final sale", "listing at time of sale: 30-day returns"], resolution="policy as of purchase date governs")],
          must_cite=["VISA-13.3@2026-04-18", "VISA-13.7@2026-04-18"],
          must_not=["rely on current listing", "require completed return", "wait 15 days"],
          components=["research (as-of snapshot)", "semantic_retrieval", "skills (not as described)", "multiple-policy reasoning"],
          deterministic_checks=[dict(path="network_actions[0].condition", op="in", value=["13.3", "13.7"]),
                                dict(path="network_actions[0].amount", op="eq", value="899.00")],
          rubric=["Uses the snapshot dated on the purchase date, and says why"], budget=dict(expected_tool_calls="5-12"))


# =====================================================================================================
def c17_too_late(ctx: Ctx):
    p = person(ctx, 90022, "Zadie Ravensworth", "Denver", "2009-05-05", cycle_day=20, behavior="pay_in_full")
    mer = bg.make_merchant(ctx, "Gateway Tix", "7922", "ecommerce", "Austin", merchant_id="MER-90020", descriptor="GATEWAY TIX*AURORA VALE",
                           acquirer_id="ACQ-04", onboarded="2016-02-01", website="https://www.gatewaytix.example", is_hero=True)
    txn = bg.add_txn(ctx, p.acct, p.card, mer, "2026-02-02", "20:40:00", "329.40", channel="ecommerce", txn_id="TXN-9001901",
                     eci="05", cavv_present=True, three_ds_status="Y", avs_result="Y", is_hero=True)
    case = "DSP-2026-90020"
    intake = utc("2026-10-14", "11:10:00", "America/Denver")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Concert cancelled in April; never refunded.", "not_received",
                   intake_channel="phone", assigned_queue="consumer_disputes", stage="investigating", is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake: event cancelled, no refund")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Bought two tickets from Gateway Tix on Feb 2 ($329.40) for the Aurora Vale concert at Lantern Amphitheater on April 25. "
                "Show was cancelled. Gateway said refunds would be automatic. Never got it. Emailed them in May, no reply. Just noticed "
                "while doing taxes prep. Wants the bank to get the money back.", case_id=case, merchant_id=mer["merchant_id"],
                subject="Cancelled event refund",
                attachments=[{"name": "gateway_cancellation_email.eml", "description":
                              "2026-04-18 Gateway Tix: 'Aurora Vale — Lantern Amphitheater (Apr 25) has been cancelled. Refunds will be "
                              "issued automatically to the original payment method within 30 days.'"},
                             {"name": "cardholder_email_may.eml", "description":
                              "2026-05-03 cardholder → support@gatewaytix.example: 'I haven't received my refund for order GT-99812.' No reply."}])
    research(ctx, "WEB-04205", "Gateway Tix — Aurora Vale refunds update", "https://www.gatewaytix.example/news/aurora-vale-refunds",
             "Gateway Tix", "2026-05-30", "2026-10-14", "merchant_notice", """
**Update, May 30, 2026.** Some customers did not receive automatic refunds for the cancelled Aurora Vale (Lantern
Amphitheater, April 25) show because of a payment processor migration. If you have not received your refund, submit
a claim through our **Refund Portal** at gatewaytix.example/refunds with your order number. **Claims are accepted
until December 31, 2026.** Refunds are issued within 10 business days of an approved claim.
""", mer["merchant_id"])
    truth(ctx, case, code="C17", title="Too Late, Still Helpful", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="All formal remedies closed: Visa 13.1 time limit expired 2026-08-23; Reg Z billing-error notice window closed "
                  "2026-04-22; §1026.12(c) unavailable because the purchase has been paid in full (no credit outstanding). Merchant "
                  "refund portal is open until 2026-12-31.",
          expected=dict(is_dispute=False, claim_family="not_received_cancelled_event",
                        network_actions=[dict(txn_id=txn["txn_id"], action="no_dispute", reason="Visa time limit expired")],
                        cardholder_resolution=dict(outcome="declined_untimely_redirected", credit_amount="0.00",
                                                   redirect=dict(resource="WEB-04205", deadline="2026-12-31")),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Event date 2026-04-25; cancellation 2026-04-18", evidence=["COM attachment gateway_cancellation_email.eml"]),
                     dict(id="F2", fact="First statement with charge transmitted 2026-02-21", evidence=["statements ACC-CR-90022 cycle end 2026-02-20"]),
                     dict(id="F3", fact="Account paid in full every cycle", evidence=["statements", "payments"]),
                     dict(id="F4", fact="Refund portal open until 2026-12-31", evidence=["WEB-04205"])],
          computations=[dict(name="visa_13_1_time_limit", value="2026-08-23", rule="120 days after last expected service date 2026-04-25"),
                        dict(name="reg_z_notice_deadline", value="2026-04-22", rule="60 days after 2026-02-21"),
                        dict(name="credit_outstanding_on_purchase", value="0.00", rule="payments applied to non-disputed amounts first; balance paid in full")],
          must_cite=["VISA-13.1@2026-04-18", "REGZ-1026.13", "REGZ-1026.12"],
          must_not=["file 13.1", "post credit labelled billing error", "stop without giving the refund portal and deadline"],
          precedents=dict(distinguish=["PRE-0017"]),
          components=["sandbox (dates, balances)", "semantic_retrieval", "research", "value-of-information stopping"],
          deterministic_checks=[dict(path="is_dispute", op="eq", value=False),
                                dict(path="cardholder_resolution.redirect.deadline", op="eq", value="2026-12-31")],
          rubric=["Explains closed windows in plain language and gives an actionable next step"],
          budget=dict(expected_tool_calls="5-10", early_termination=True))


# =====================================================================================================
def c18_refund_crossed(ctx: Ctx):
    p = person(ctx, 90023, "Oakley Stirling", "Seattle", "2017-04-04", product="debit")
    tz = "America/Los_Angeles"
    mkt = bg.make_merchant(ctx, "Harborlane Market", "5399", "ecommerce", "Seattle", merchant_id="MER-90021",
                           descriptor="HARBORLANE MARKET", acquirer_id="ACQ-05", onboarded="2015-01-01", is_marketplace=True,
                           website="https://www.harborlane.example", is_hero=True, legal_suffix=" Inc",
                           extra_descriptors=[("HLM*<SELLER> <ITEM>", "2024-01-01", "", "marketplace sub-merchant pattern"),
                                              ("HLM*REFUND <ORDER4>", "2024-01-01", "", "refund descriptor; no seller name")])
    bg.make_merchant(ctx, "Velvet Loom Co", "5719", "ecommerce", "Chicago", merchant_id="MER-90022", descriptor="VELVET LOOM CO",
                     acquirer_id="ACQ-05", onboarded="2025-02-01", parent="MER-90021", is_hero=True)
    txn = bg.add_txn(ctx, p.acct, p.card, mkt, "2026-09-08", "20:10:00", "143.20", channel="ecommerce", txn_id="TXN-9002001",
                     descriptor="HLM*VELVETLOOM RUG", eci="05", cavv_present=True, three_ds_status="Y", avs_result="Y", is_hero=True)
    case = "DSP-2026-90021"
    intake = utc("2026-10-15", "09:40:00", tz)
    prov = bg.add_txn(ctx, p.acct, p.card, None, "2026-10-16", "10:00:00", "143.20", channel="adjustment", txn_type="provisional_credit",
                      txn_id="TXN-9002003", processing_lag=0, descriptor=f"PROVISIONAL CREDIT CLAIM {case}", pos_entry_mode="",
                      auth_code="", auth_id="", is_hero=True)
    ref = bg.add_txn(ctx, p.acct, p.card, mkt, "2026-10-19", "05:12:00", "143.20", channel="ecommerce", txn_type="credit",
                     txn_id="TXN-9002002", descriptor="HLM*REFUND 7781", processing_lag=0, related_txn_id="", eci="", avs_result="",
                     cvv2_presence="", cvv2_result="", cavv_present="", three_ds_status="", posting_date="2026-10-20",
                     available_at="2026-10-20T10:00:00Z", is_hero=True)
    bg.add_dispute(ctx, case, [txn], "REG_E", intake, "Rug from Harborlane Market seller Velvet Loom never delivered.", "not_received",
                   intake_channel="phone", assigned_queue="reg_e_disputes", stage="investigating", provisional_credit_amount="143.20",
                   provisional_credit_at=utc("2026-10-16", "10:00:00", tz), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Phone intake (debit): goods not received")
    bg.add_devent(ctx, case, utc("2026-10-16", "10:00:00", tz), "provisional_credit_posted", "Reg E provisional credit 143.20 posted (bank SOP: immediate)")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "phone_summary", "cardholder",
                "Customer ordered a rug on Harborlane Market (seller Velvet Loom Co) on 9/8 for $143.20; estimated delivery 9/20; never "
                "arrived. Says they 'opened a claim with Harborlane last week' but wants the bank to handle it too.",
                case_id=case, merchant_id=mkt["merchant_id"], subject="Rug not delivered")
    bg.add_comm(ctx, p.cust["customer_id"], utc("2026-10-20", "15:02:00", tz), "inbound", "email_forwarded", "cardholder",
                "Fwd from Harborlane Guarantee (sent 2026-10-18): 'Good news — your Harborlane Guarantee claim HG-40077 for order "
                "114-7781 (Velvet Loom Co, hand-tufted rug) was approved. A refund of $143.20 has been issued to your original payment "
                "method and should appear within 3–5 business days.' Customer note: 'FYI in case this helps.'",
                case_id=case, merchant_id=mkt["merchant_id"], subject="Fwd: Your Harborlane Guarantee claim",
                available_at=utc("2026-10-20", "15:02:00", tz))
    research(ctx, "WEB-04212", "Harborlane Guarantee", "https://www.harborlane.example/guarantee", "Harborlane Market", "2024-05-01",
             "2026-10-20", "marketplace_policy", """
If an item from a Harborlane seller doesn't arrive, file a Guarantee claim within 90 days of the estimated delivery date.
Approved refunds are issued to the original payment method. Refunds appear on card statements as **HLM\\*REFUND** followed
by the last four digits of your order number.
""", mkt["merchant_id"])
    truth(ctx, case, code="C18", title="Refund Crossed in the Mail", depth="L1/L2", regime="REG_E", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"], ref["txn_id"], prov["txn_id"]],
          summary="Merchant credit (HLM*REFUND 7781, no original ARN) posted 10-20 after provisional credit 10-16. Match via order "
                  "number suffix and forwarded email. No dispute; reverse provisional credit with Reg E notice (honor 5 business days).",
          expected=dict(is_dispute=False, claim_family="not_received",
                        network_actions=[dict(txn_id=txn["txn_id"], action="no_dispute", reason="merchant credit processed; apply credit")],
                        cardholder_resolution=dict(outcome="resolved_merchant_credit", reversal_amount="143.20",
                                                   reversal_of_txn_id=prov["txn_id"]),
                        letters=["reg_e_provisional_credit_reversal_notice"],
                        deadlines=dict(funds_honored_through="2026-10-28"),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Credit HLM*REFUND 7781 $143.20 posted 2026-10-20 without original transaction link", evidence=["TXN-9002002"]),
                     dict(id="F2", fact="Order number 114-7781 ends in 7781; Harborlane refund descriptor convention", evidence=["COM forwarded email", "WEB-04212"]),
                     dict(id="F3", fact="Provisional credit 143.20 posted 2026-10-16", evidence=["TXN-9002003"])],
          computations=[dict(name="net_position_if_no_action", value="+143.20 (double recovery)"),
                        dict(name="funds_honored_through", value="2026-10-28", rule="5 business days after notice on 2026-10-21")],
          must_cite=["REGE-1005.11", "VISA-11.2-LIFECYCLE@2026-04-18", "LFB-SOP-DSP-006@v4"],
          must_not=["file 13.1", "leave provisional credit in place", "reverse without Reg E notice"],
          components=["late/out-of-order data", "router (regime)", "sandbox (reconciliation)", "loop termination"],
          deterministic_checks=[dict(path="is_dispute", op="eq", value=False),
                                dict(path="cardholder_resolution.reversal_amount", op="eq", value="143.20")],
          rubric=["Explains the match between refund and order without an ARN"], budget=dict(expected_tool_calls="4-9", early_termination=True))


# =====================================================================================================
def c19_reputation(ctx: Ctx):
    p = person(ctx, 90024, "Arlo Greenhalgh", "Columbus", "2016-11-11", cycle_day=2)
    qm = bg.make_merchant(ctx, "Quillmark Print", "5969", "ecommerce", "Pittsburgh", merchant_id="MER-90023", descriptor="QUILLMARK PRINT",
                          acquirer_id="ACQ-02", onboarded="2021-03-01", website="https://www.quillmark.example", is_hero=True)
    qm_old = bg.make_merchant(ctx, "Quillmark Printing", "5969", "ecommerce", "Pittsburgh", merchant_id="MER-90024",
                              descriptor="QUILLMARK PRINTING LLC", acquirer_id="ACQ-02", onboarded="2019-06-01", is_hero=True)
    qm_old["status"] = "closed"
    ctx.get("merchants", "MER-90024")["status"] = "closed"
    rng = ctx.rng
    pool = [r for r in ctx.people if r["accounts"][0]["regime"] == "REG_Z"][40:57]
    hist_cases = []
    for i, r in enumerate(pool[:11]):
        mer = qm_old if i < 4 else qm
        day = "2026-%02d-%02d" % (1 + (i * 6) // 11, 3 + (i * 5) % 20)
        t = bg.add_txn(ctx, r["accounts"][0], r["cards"][0], mer, day, "11:30:00", m(rng.uniform(38, 165)), channel="ecommerce")
        opened = add_days(day, 26)
        dcid = f"DSP-2026-0{9401 + i}"
        hist_cases.append(dcid)
        bg.add_dispute(ctx, dcid, [t], "REG_Z", utc(opened, "10:00:00"), "Custom print order never arrived.", "not_received",
                       status="closed", stage="closed", network_condition="13.1", dispute_processing_date=add_days(opened, 4),
                       cardholder_outcome="credited", network_outcome="issuer_won", closed_at=utc(add_days(opened, 41), "16:00:00"),
                       assigned_queue="consumer_disputes")
        bg.add_devent(ctx, dcid, utc(add_days(opened, 41), "16:00:00"), "case_closed", "Closed: credited; 13.1 won",
                      detail={"note": "Tracking stuck at 'label created' for 3+ weeks; merchant response had no carrier scans. Won."})
        bg.add_packet(ctx, f"MEP-0{9401 + i}-OI", dcid, t["txn_id"], mer["merchant_id"], "order_insight", "", utc(add_days(opened, 3), "12:00:00"),
                      dict(shipments=[dict(carrier="ParcelPath", tracking_number=f"PP9401{i:02d}0", events=[
                          dict(ts=utc(add_days(day, 3), "10:00:00"), status="label_created")])],
                          merchant_statement="Order in production queue."))
        ctx.bg_labels.append(dict(case_id=dcid, family="not_received", true_nature="merchant_failure", expected_network_condition="13.1",
                                  expected_cardholder_outcome="credited", status="closed", historical_decision_correct=True))
    for r in pool[11:17]:
        bg.add_txn(ctx, r["accounts"][0], r["cards"][0], qm, "2026-%02d-%02d" % (rng.randint(8, 9), rng.randint(15, 28)), "14:00:00",
                   m(rng.uniform(40, 140)), channel="ecommerce")
    ctx.quillmark_cases = hist_cases
    txn = bg.add_txn(ctx, p.acct, p.card, qm, "2026-10-02", "12:15:00", "86.50", channel="ecommerce", txn_id="TXN-9002101",
                     eci="05", cavv_present=True, three_ds_status="Y", avs_result="Y", is_hero=True)
    case = "DSP-2026-90022"
    intake = utc("2026-10-16", "09:30:00")
    bg.add_dispute(ctx, case, [txn], "REG_Z", intake, "Custom poster from Quillmark Print not received by promised date.", "not_received",
                   intake_channel="app_chat", intake_authenticated_via="mobile_app_biometric", assigned_queue="consumer_disputes",
                   stage="investigating", provisional_credit_amount="86.50", provisional_credit_at=utc("2026-10-19", "10:00:00"), is_hero=True)
    bg.add_devent(ctx, case, intake, "intake_created", "Chat intake: goods not received (Quillmark)")
    bg.add_devent(ctx, case, utc("2026-10-16", "09:31:00"), "note_added",
                  "Auto-note from agent memory: 'Quillmark Print rarely ships; non-receipt claims almost always valid' (MEM-0209).",
                  actor="system")
    bg.add_comm(ctx, p.cust["customer_id"], intake, "inbound", "chat", "cardholder",
                "Ordered a custom 24x36 poster from Quillmark on Oct 2, they promised delivery by Oct 16. Nothing yet and tracking hasn't "
                "updated. I read online they have a history of not shipping. Please get my money back.",
                case_id=case, merchant_id=qm["merchant_id"])
    addr = full_address(p.addr)
    bg.add_packet(ctx, "MEP-90022-OI", case, txn["txn_id"], qm["merchant_id"], "order_insight", utc("2026-10-16", "10:00:00"),
                  utc("2026-10-18", "11:00:00"), dict(
                      order=dict(order_id="QM-208811", items=[dict(description="Custom poster 24x36 matte", price="86.50")],
                                 promised_delivery="2026-10-16"),
                      shipments=[dict(carrier="ShipCrest", tracking_number="SC7700218841", events=[
                          dict(ts=utc("2026-10-12", "08:00:00", "America/New_York"), status="label_created"),
                          dict(ts=utc("2026-10-14", "06:10:00"), status="in_transit"),
                          dict(ts=utc("2026-10-17", "14:02:00"), status="delivered", address=addr)],
                          proof_of_delivery=dict(address=addr, photo_description="Cardboard poster tube on doorstep beside planter."))],
                      merchant_statement="Delivered 1 day after promised date. We apologize for the delay."))
    research(ctx, "WEB-04219", "Quillmark moves fulfilment to ShipCrest, clears backlog", "https://www.quillmark.example/news/shipcrest",
             "Quillmark Print", "2026-08-12", "2026-10-16", "merchant_press_release", """
Pittsburgh, August 12, 2026 — Quillmark Print has moved all order fulfilment to ShipCrest Logistics after
production and shipping delays earlier this year. All backlogged orders have shipped. New orders now ship within
7–10 business days with live tracking. Customers affected by earlier delays can contact support for a refund.
""", qm["merchant_id"])
    research(ctx, "WEB-04226", "Forum: 'Quillmark never shipped my order' (April 2026)", "https://forum.buyerboard.example/t/quillmark-never-shipped/88120",
             "BuyerBoard forum (fictional)", "2026-04-09", "2026-10-16", "forum_post", """
**posted Apr 9, 2026** — Ordered a canvas print in February, tracking has said "label created" for 7 weeks. Support
won't answer. Anyone else? *(38 replies, most recent May 2026)*
""", qm["merchant_id"])
    persona(ctx, case, p.cust["customer_id"],
            profile="Reasonable customer who filed early after reading bad reviews.",
            knows=["Package arrived Saturday Oct 17 while away; found it Sunday"],
            disclosure_rules=["Confirms receipt if asked whether the package has arrived since Oct 16"],
            scripted_replies=[dict(trigger="agent asks whether package arrived / shares delivery scan", delay_minutes=45,
                                   reply="Oh — yes, it was on the step when I got back Sunday. Sorry, I jumped the gun. You can close this.")])
    truth(ctx, case, code="C19", title="Yesterday's Reputation", depth="L2", regime="REG_Z", customer_id=p.cust["customer_id"],
          txn_ids=[txn["txn_id"]],
          summary="Consolidated memory says Quillmark rarely ships; true only for Jan–Aug 2026 (11 disputes across two MIDs). "
                  "Fulfilment changed 2026-08-12; current order delivered 2026-10-17. Cardholder withdraws. Memory must be "
                  "time-bounded, not deleted.",
          expected=dict(is_dispute=False, claim_family="not_received",
                        network_actions=[dict(txn_id=txn["txn_id"], action="no_dispute", reason="delivered; cardholder withdrew")],
                        cardholder_resolution=dict(outcome="withdrawn_after_clarification", reversal_amount="86.50"),
                        adjudication=dict(review_panel_required=False)),
          key_facts=[dict(id="F1", fact="Delivered 2026-10-17 with full address and photo", evidence=["MEP-90022-OI"]),
                     dict(id="F2", fact="11 historical non-receipt disputes Jan–Jul 2026 across MER-90023 and legacy MID MER-90024", evidence=[", ".join(hist_cases)]),
                     dict(id="F3", fact="Fulfilment moved to ShipCrest 2026-08-12; 6 later orders, 0 disputes", evidence=["WEB-04219", "transactions MER-90023"])],
          contradictions=[dict(id="X1", between=["MEM-0209", "MEP-90022-OI + WEB-04219"], resolution="memory stale after 2026-08-12")],
          must_not=["approve based on merchant reputation", "delete historical notes", "treat MER-90023 and MER-90024 as unrelated when consolidating"],
          memory_ops=dict(read=["MEM-0209", "MEM-0201..MEM-0208"],
                          consolidate=[dict(from_notes=[f"MEM-020{i}" for i in range(1, 9)], into_scope="merchant",
                                            subject_ids=["MER-90023", "MER-90024"], valid_from="2026-01-01", valid_to="2026-08-12")],
                          supersede=[dict(note_id="MEM-0209", reason="pattern ended 2026-08-12")]),
          components=["memory consolidation", "memory forgetting (time-bounding)", "research", "verify-before-trust",
                      "entity resolution (near-duplicate merchants)", "user_simulation"],
          deterministic_checks=[dict(path="is_dispute", op="eq", value=False),
                                dict(path="memory_ops[?note_id=='MEM-0209'].op", op="eq", value="supersede")],
          rubric=["Consolidated note states its validity window and source cases"], budget=dict(expected_tool_calls="6-14"))


def build(ctx: Ctx):
    c13_agent_booked(ctx)
    c14_time_zones(ctx)
    c15_membership(ctx)
    c16_listing_changed(ctx)
    c17_too_late(ctx)
    c18_refund_crossed(ctx)
    c19_reputation(ctx)
