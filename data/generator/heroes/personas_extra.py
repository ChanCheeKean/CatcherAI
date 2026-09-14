"""Simulated-cardholder personas for hero cases whose builders don't define one inline.
Each lists what the cardholder knows, when they disclose it, and replies to likely questions."""
from __future__ import annotations

from common import Ctx
from heroes.kit import persona

EXTRA = {
    "DSP-2026-90001": ("CUS-90001", "Frustrated but organized; has all emails saved.",
                       ["Never received a shipping notice", "Heard from a neighbor that Oakhollow closed"],
                       ["Volunteers the neighbor rumor only if asked whether they know anything about the merchant's status"],
                       [("agent asks whether cardholder contacted merchant", 60, "Yes — three emails, Sept 24, Oct 1 and Oct 8, and I called twice. The phone just rings now.")]),
    "DSP-2026-90003": ("CUS-90003", "Designer; bought fonts for a client project; mildly annoyed.",
                       ["Both downloads showed an error page", "Never received new links"],
                       [], [("agent asks whether merchant re-issued links", 90, "No, nothing. I checked spam too. I bought something else from another foundry instead.")]),
    "DSP-2026-90006": ("CUS-90005", "Business traveler; initials are D.O.; remembers the desk clerk saying 'we can upgrade you'.",
                       ["Signed the registration card at check-in without reading closely", "Flew in and used rideshare; no car"],
                       ["Admits signing/initialing the card if shown the registration card text", "Maintains the clerk implied the upgrade was free"],
                       [("agent shares registration card initials", 180, "I did initial things at the desk, but she said 'we'll upgrade you' — I didn't realize it was $60 a night. I definitely didn't have a car."),
                        ("agent explains partial outcome", 120, "OK. I'm glad the parking is being fixed. I still think the upgrade was misleading but I understand.")]),
    "DSP-2026-90007": ("CUS-90006", "Signed up on a phone ad; didn't read terms.",
                       ["Used the app once after the charge (Sept 30)", "Never got a reminder email"],
                       [], [("agent asks about reminder emails", 60, "No reminder at all. Just the welcome email and then the charge.")]),
    "DSP-2026-90008": ("CUS-90007", "Assumes the merchant kept part of the refund.",
                       ["Bought in euros", "Merchant said full refund of EUR 420"],
                       ["Accepts exchange-rate explanation if shown both conversion rates"],
                       [("agent explains FX difference and fee reversal", 120, "Oh, I didn't realize the rate changed that much. Thanks for refunding the foreign fee.")]),
    "DSP-2026-90009": ("CUS-90008", "New customer; works night shifts; uses card mainly at gas stations and grocery.",
                       ["Card never left wallet", "Saw a declined-transaction push on Saturday but assumed a glitch", "Filled up at Pinegrove on Sept 30"],
                       ["Mentions the gas station only if asked where the card was recently used"],
                       [("agent asks where card was used recently", 45, "Mostly Pinegrove on W 25th and the grocery store. That's about it."),
                        ("agent asks for written confirmation", 1440, "Sent the signed form through the app.")]),
    "DSP-2026-90012": ("CUS-90012", "Long-time customer; phone showed 'No Service' since Monday evening; worried.",
                       ["Did not request a phone number change", "Never shipped anything to Jersey City", "Had a similar unexplained charge in May"],
                       ["Mentions the May charge and that they 'gave up' only if asked about prior unauthorized activity"],
                       [("agent asks about phone service / number change", 60, "My phone has had no service since Monday night. I haven't changed my number — I've been meaning to go to the carrier store."),
                        ("agent asks about prior disputes", 90, "Yes! In May there was a $612 outdoor gear order I never made. The bank said I must have done it. I didn't have the energy to fight it.")]),
    "DSP-2026-90013": ("CUS-90013", "Insists on porch theft; evasive about other claims.",
                       ["Coordinates non-receipt claims with three acquaintances (conceals this)", "Package was received"],
                       ["Does not volunteer other claims; answers 'I don't know those people' if asked about shared devices"],
                       [("agent shares POD photo and GPS", 240, "That photo could be from any day. Someone took it off the porch."),
                        ("agent asks about shared devices/phone numbers", 300, "I don't know what you're talking about. Lots of people use that staffing agency's tablets.")]),
    "DSP-2026-90014": ("CUS-90017", "Teacher; careful; lives at 1240 Maple Ridge Dr.",
                       ["House number is 1240", "Neighbors at 1204 are on vacation"],
                       [], [("agent shares POD photo description", 90, "That's not my door — we're 1240, ours is a red door. 1204 is three houses down and they're away until November.")]),
    "DSP-2026-90015": ("CUS-90018", "Lawyer; articulate; believes 'preferred' meant required.",
                       ["Saw a 'Booked!' push but didn't open it for two days", "Did not use the 24-hour free cancellation"],
                       ["Admits seeing the booking notification if asked when they first learned the fare type"],
                       [("agent asks when they learned it was non-refundable", 120, "I got a push that it was booked but didn't open it until Oct 4. I assumed it followed my instructions."),
                        ("agent explains decision and TravelMind guarantee", 180, "I still think 'preferred' should have meant something. Fine — I'll take it up with TravelMind directly.")]),
    "DSP-2026-90016": ("CUS-90019", "Busy consultant based in LA; phone set to Pacific time.",
                       ["Called the hotel front desk; spoke to 'Marcus'", "Was told 'you're all set'; no number given"],
                       [], [("agent asks what time zone the call log shows", 45, "My phone is on Pacific time — I was at my desk in LA.")]),
    "DSP-2026-90019": ("CUS-90021", "Methodical; kept packaging and all screenshots.",
                       ["Listing said 30-day returns when purchased", "Laptop is unused in original box"],
                       [], [("agent asks where the merchandise is", 60, "It's in the original box at my apartment, ready to ship back if they'll give me a label.")]),
    "DSP-2026-90020": ("CUS-90022", "Embarrassed about waiting so long; pays card in full every month.",
                       ["Never saw the refund portal update", "Pays statement balance in full automatically"],
                       [], [("agent explains windows closed and refund portal", 120, "I had no idea there was a portal. I'll file today. Thank you for finding that.")]),
    "DSP-2026-90021": ("CUS-90023", "Didn't realize the marketplace claim would refund the card directly.",
                       ["Got an approval email from Harborlane on Oct 18"],
                       [], [("agent explains refund posted and provisional credit reversal", 90, "Makes sense — I don't want to be paid twice. Go ahead.")]),
}


def build(ctx: Ctx):
    for case_id, (cust, profile, knows, rules, replies) in EXTRA.items():
        if case_id in ctx.personas:
            continue
        persona(ctx, case_id, cust, profile=profile, knows=knows, disclosure_rules=rules,
                scripted_replies=[dict(trigger=t, delay_minutes=dm, reply=r) for t, dm, r in replies])
