"""Pre-existing agent memory: long-term notes (some valid, some stale, wrong, duplicated, noisy or prohibited)
and two episodic run traces. These exist so that consolidation, forgetting, and correction are testable."""
from __future__ import annotations

from common import Ctx


def _note(note_id, scope, subject_ids, content, created_at, created_by, source_refs, confidence=0.8, status="active",
          valid_from=None, valid_to=None, tags=(), sensitivity="normal", last_accessed_at=None, access_count=0, kind="semantic"):
    return dict(note_id=note_id, kind=kind, scope=scope, subject_ids=list(subject_ids), content=content, created_at=created_at,
                created_by=created_by, source_refs=list(source_refs), confidence=confidence, status=status,
                valid_from=valid_from or created_at[:10], valid_to=valid_to, superseded_by=None, tags=list(tags),
                sensitivity=sensitivity, last_accessed_at=last_accessed_at or created_at, access_count=access_count)


def build(ctx: Ctx):
    N = ctx.memory_notes
    q = ctx.quillmark_cases
    N += [
        _note("MEM-0142", "customer", ["CUS-90012"],
              "Prior CNP fraud claim DSP-2026-04471 denied: merchant compelling evidence matched (login ID, IP). Possible first-party "
              "misuse — apply heightened scrutiny to future card-not-present fraud claims from this customer.",
              "2026-06-02T21:05:00Z", "agent:dispute-assistant@0.3", ["DSP-2026-04471", "PRE-0031"], confidence=0.6,
              tags=["risk", "first_party_misuse"], access_count=3, last_accessed_at="2026-10-15T13:30:00Z"),
        _note("MEM-0150", "procedure", ["LFB-SOP-DSP-002"],
              "Non-fraud consumer disputes of $25.00 or less may be written off as goodwill without a chargeback if the customer has "
              "had no other dispute in the past 12 months.", "2025-03-02T15:00:00Z", "agent:dispute-assistant@0.1",
              ["LFB-SOP-DSP-002@v3"], confidence=0.95, tags=["write_off", "threshold"], access_count=41,
              last_accessed_at="2026-10-01T14:00:00Z"),
        _note("MEM-0151", "policy", ["VISA-10.4"],
              "CE 3.0 blocks a 10.4 dispute when the same card was used for 2 prior undisputed purchases at the SAME merchant 120–365 "
              "days earlier with IP/device plus one more matching element.", "2025-12-18T18:00:00Z", "agent:dispute-assistant@0.2",
              ["PRE-0009", "VISA-10.4@2025-10"], confidence=0.9, tags=["CE3.0"], access_count=17),
        _note("MEM-0152", "procedure", ["REGE-1005.11"],
              "Reg E: provisional credit must be posted within 10 calendar days of the customer's notice if the investigation is not "
              "finished.", "2025-04-10T12:00:00Z", "agent:dispute-assistant@0.1", ["LFB-CB-2025-03"], confidence=0.85,
              tags=["reg_e", "deadline"], access_count=22),
        _note("MEM-0160", "merchant", ["MER-90006"],
              "Lumafit+ annual-renewal disputes where the customer cancelled after billing are won under 13.2; merchant rarely responds.",
              "2026-04-09T17:00:00Z", "agent:dispute-assistant@0.3", ["PRE-0012"], confidence=0.7, tags=["recurring"]),
        _note("MEM-0170", "merchant", ["MER-90005"],
              "The Larkspur Hotel Nashville answers Order Insight within about 3 days and includes the folio and the signed registration card.",
              "2026-06-29T16:00:00Z", "agent:dispute-assistant@0.3", ["PRE-0007"], confidence=0.8, tags=["lodging", "order_insight"]),
        _note("MEM-0175", "merchant", ["MER-90004"],
              "Parcelwick Home charges per shipment; multi-item orders often appear as several same-day charges.",
              "2025-12-03T11:00:00Z", "analyst:tkhan", ["DSP-2025-00000 (not retained)"], confidence=0.75, tags=["split_shipment"]),
        _note("MEM-0180", "customer", ["CUS-90020"], "Customer prefers email over phone calls.", "2026-09-19T15:00:00Z",
              "agent:dispute-assistant@0.3", ["DSP-2026-90017"], confidence=0.9, tags=["contact_preference"]),
        _note("MEM-0181", "customer", ["CUS-90020"], "Prefers to be contacted by email, not phone.", "2026-09-21T15:20:00Z",
              "analyst:cwright", ["DSP-2026-90017"], confidence=0.9, tags=["contact_preference"]),
        _note("MEM-0185", "operational", [], "Tool get_statements timed out at 2026-05-02T14:03Z; retried successfully.",
              "2026-05-02T14:04:00Z", "agent:dispute-assistant@0.3", [], confidence=1.0, tags=["tooling"], kind="episodic"),
        _note("MEM-0190", "merchant", ["MER-90011"],
              "Pixelhollow Studios offers parents a one-time refund for a minor's purchases made in the last 30 days.",
              "2025-09-14T10:00:00Z", "agent:dispute-assistant@0.2", ["support.pixelhollow.example/minor-purchases (2025 capture)"],
              confidence=0.8, tags=["minor", "merchant_refund"]),
        _note("MEM-0191", "customer", ["CUS-90009"],
              "Two digital-goods fraud disputes in 2026 (DSP-2026-90901 Jan, DSP-2026-90902 Jun); both credited because merchants did not respond.",
              "2026-06-15T12:00:00Z", "system", ["DSP-2026-90901", "DSP-2026-90902"], confidence=1.0, tags=["history"]),
        _note("MEM-0195", "merchant", ["MER-90014"],
              "Stridevault proof-of-delivery packets include full address, photo, and GPS distance; generally reliable.",
              "2026-09-15T12:00:00Z", "agent:dispute-assistant@0.3", ["DSP-2026-91303"], confidence=0.8, tags=["pod"]),
        _note("MEM-0196", "customer", ["CUS-00031"],
              "Customer sounds elderly and easily confused on calls; their claims are probably mistakes.",
              "2026-02-11T16:00:00Z", "rep:unknown", [], confidence=0.4, tags=["demeanor"], sensitivity="prohibited_basis"),
    ]
    raw = [
        ("MEM-0201", q[0], "2026-02-10", "Quillmark Printing (legacy MID) order never shipped; tracking only 'label created' 3 weeks."),
        ("MEM-0202", q[1], "2026-02-24", "Quillmark Printing: no carrier scans; merchant response 'in production queue'. Won 13.1."),
        ("MEM-0203", q[3], "2026-03-30", "QUILLMARK PRINTING LLC again: label created, no movement. Customer credited."),
        ("MEM-0204", q[4], "2026-04-14", "Quillmark Print (new MID) — same pattern as the old Quillmark Printing merchant: no scans after label."),
        ("MEM-0205", q[5], "2026-05-06", "Quillmark Print non-receipt; merchant unresponsive to Order Insight for 9 days."),
        ("MEM-0206", q[7], "2026-06-01", "Quillmark Print: order from March never shipped. 13.1 won."),
        ("MEM-0207", q[8], "2026-06-22", "Quillmark: tracking stuck again. Recommend fast approval for this merchant."),
        ("MEM-0208", q[10], "2026-07-19", "Quillmark Print non-receipt #11 this year."),
    ]
    for nid, case, day, text in raw:
        N.append(_note(nid, "merchant", ["MER-90023"] if "legacy" not in text and "LLC" not in text and "Printing" not in text else ["MER-90024"],
                       text, f"{day}T18:00:00Z", "agent:dispute-assistant@0.3", [case], confidence=0.85, tags=["non_receipt", "raw_observation"],
                       kind="episodic"))
    N.append(_note("MEM-0209", "merchant", ["MER-90023"],
                   "Quillmark Print rarely ships orders; non-receipt claims against it are almost always valid. Fast-track approval.",
                   "2026-07-30T09:00:00Z", "agent:dispute-assistant@0.3", ["MEM-0201", "MEM-0205", "MEM-0208"], confidence=0.85,
                   tags=["non_receipt", "pattern", "consolidated"], access_count=5, last_accessed_at="2026-10-16T13:31:00Z"))
    N += [
        _note("MEM-0220", "procedure", [], "Before filing any consumer dispute, check for merchant credits posted after intake — they can "
              "arrive days later with a different descriptor and no link to the original transaction.", "2026-08-05T10:00:00Z",
              "agent:dispute-assistant@0.3", ["DSP-2026-00000 (QA finding)"], confidence=0.9, tags=["lesson", "credits"], kind="procedural"),
        _note("MEM-0221", "procedure", [], "Hotel cancellation deadlines are stated in the hotel's local time; convert cardholder-reported times.",
              "2026-09-01T17:00:00Z", "agent:dispute-assistant@0.3", ["PRE-0019"], confidence=0.95, tags=["lesson", "lodging", "timezone"],
              kind="procedural"),
    ]
    # ---- episodic run traces (abridged)
    ctx.run_traces["TRACE-2026-06-02-DSP-2026-04471"] = [
        dict(step=1, ts="2026-06-02T20:40:00Z", agent="dispute-assistant@0.3", type="plan", content="Pre-arb received for 10.4. Evaluate compelling evidence."),
        dict(step=2, ts="2026-06-02T20:41:10Z", type="tool_call", tool="get_evidence_packet", args={"packet_id": "MEP-04471-PA"},
             result_summary="login matches; ip 198.18.201.x; AVS Y"),
        dict(step=3, ts="2026-06-02T20:42:00Z", type="reasoning", content="Login and IP match prior orders → CE satisfied → likely first-party misuse."),
        dict(step=4, ts="2026-06-02T20:43:30Z", type="decision", content="Recommend accept pre-arb; re-bill cardholder.", confidence=0.72),
        dict(step=5, ts="2026-06-02T21:05:00Z", type="memory_write", note_id="MEM-0142"),
        dict(step=6, ts="2026-06-02T21:06:00Z", type="human_approval", approver="analyst.lpetrov", decision="approved"),
        dict(step=7, ts="2026-09-12T10:00:00Z", type="qa_review", reviewer="qa.mnguyen", sampled=False, note="not sampled"),
    ]
    ctx.run_traces["TRACE-2026-09-01-DSP-2026-08019"] = [
        dict(step=1, ts="2026-09-01T15:00:00Z", agent="dispute-assistant@0.3", type="plan", content="No-show dispute; check cancellation timing and nights billed."),
        dict(step=2, ts="2026-09-01T15:01:00Z", type="tool_call", tool="sandbox.run", args={"code": "convert 16:30 America/Denver -> America/New_York"},
             result_summary="18:30 ET"),
        dict(step=3, ts="2026-09-01T15:02:00Z", type="reasoning", content="Call after 18:00 ET deadline → first night valid; 2 nights billed → second night disputable."),
        dict(step=4, ts="2026-09-01T15:03:00Z", type="decision", content="File 13.7 for 304.09.", confidence=0.9),
        dict(step=5, ts="2026-09-01T15:04:00Z", type="memory_write", note_id="MEM-0221"),
        dict(step=6, ts="2026-09-01T15:30:00Z", type="human_approval", approver="analyst.abanerjee", decision="approved"),
    ]
