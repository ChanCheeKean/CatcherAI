"""Background population: merchants, customers, accounts, devices, IPs, transaction history,
statements/payments, issuer account events, and historical + open background disputes.

Hero modules reuse the helpers here (make_customer, make_account, make_card, add_txn, gen_history, ...)
so hero records look exactly like background records.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from common import AS_OF, HISTORY_START, UTC, Ctx, add_days, d, iso_utc, local_dt, m, money, stable_hex, utc
from world import (ACQUIRERS, BACKGROUND_CITY_WEIGHTS, CITIES, EMPLOYERS, FIRST_NAMES, LAST_NAMES, MCC,
                   MERCHANT_CATALOG, STREET_SUFFIX, STREETS)

AS_OF_DATE = AS_OF.astimezone(ZoneInfo("America/New_York")).date()
CREDIT_BIN, DEBIT_BIN = "400012", "400034"
_ACQ = {a[0]: a for a in ACQUIRERS}
_phone_slots: dict = {}


# ============================================================ basic entity helpers
def make_address(ctx: Ctx, city: str, line1=None, line2="", postal=None, address_type="residential",
                 address_id=None) -> dict:
    c = CITIES[city]
    rng = ctx.rng
    if line1 is None:
        line1 = f"{rng.randint(12, 4980)} {rng.choice(STREETS)} {rng.choice(STREET_SUFFIX)}"
        if address_type == "residential" and rng.random() < 0.3:
            line2 = f"Apt {rng.randint(1, 24)}{rng.choice('ABCDEF')}"
    return ctx.add("addresses", dict(
        address_id=address_id or ctx.next_id("ADR", 6), line1=line1, line2=line2, city=city, state=c["state"],
        postal_code=postal or f"{c['zip3']}{rng.randint(1, 99):02d}", country="US",
        lat=round(c["lat"] + rng.uniform(-0.06, 0.06), 5), lon=round(c["lon"] + rng.uniform(-0.06, 0.06), 5),
        address_type=address_type))


def phone_for(ctx: Ctx, city: str, hero_slot=None) -> str:
    area = CITIES[city]["area"]
    if hero_slot is not None:
        return f"({area}) 555-01{hero_slot:02d}"
    n = _phone_slots.get(area, 0)
    _phone_slots[area] = n + 1
    return f"({area}) 555-01{n % 80:02d}"


def make_customer(ctx: Ctx, city: str, customer_id=None, full_name=None, since=None, birth_year=None,
                  address=None, employer=None, is_hero=False, preferred_contact=None, segment=None,
                  phone=None, email=None, alt_phone="") -> dict:
    rng = ctx.rng
    if full_name is None:
        full_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    first, last = full_name.split(" ", 1)
    cid = customer_id or ctx.next_id("CUS", 5)
    addr = address or make_address(ctx, city)
    work = ""
    if employer is None and rng.random() < 0.6:
        employer = rng.choice(EMPLOYERS)
    if employer:
        work = make_address(ctx, city, address_type="commercial")["address_id"]
    if since is None:
        yr = rng.choices(range(2008, 2027), weights=[3] * 10 + [4, 4, 5, 5, 6, 6, 6, 5, 3])[0]
        since = dt.date(yr, rng.randint(1, 12), rng.randint(1, 28))
        if since > dt.date(2026, 6, 30):
            since = dt.date(2026, 6, rng.randint(1, 28))
        since = since.isoformat()
    handle = f"{first.lower()}.{last.lower().replace('-', '')}"
    return ctx.add("customers", dict(
        customer_id=cid, full_name=full_name, preferred_name=first, birth_year=birth_year or rng.randint(1948, 2004),
        email=email or f"{handle}{rng.randint(1, 99)}@example.{rng.choice(['com', 'net', 'org'])}",
        phone=phone or phone_for(ctx, city), alt_phone=alt_phone, home_address_id=addr["address_id"],
        employer_name=employer or "", work_address_id=work, customer_since=since,
        segment=segment or rng.choices(["mass", "premium", "private"], [70, 25, 5])[0],
        preferred_contact=preferred_contact or rng.choice(["app", "email", "phone"]), is_hero=is_hero))


def make_account(ctx: Ctx, customer: dict, product="credit", opened_at=None, cycle_day=None, behavior=None,
                 account_id=None, credit_limit=None, first_deposit=None, is_hero=False) -> dict:
    rng = ctx.rng
    opened_at = opened_at or customer["customer_since"]
    if product == "credit":
        acc = ctx.add("accounts", dict(
            account_id=account_id or ctx.next_id("ACC-CR", 5), primary_customer_id=customer["customer_id"],
            product="lanternfield_visa_signature_credit", regime="REG_Z", opened_at=opened_at, status="open",
            credit_limit=credit_limit or rng.choice([1500, 3000, 5000, 7500, 10000, 15000, 25000]),
            apr=rng.choice(["19.99", "22.49", "24.99", "27.24", "29.49"]),
            statement_cycle_day=cycle_day or rng.randint(1, 28),
            payment_behavior=behavior or rng.choices(["pay_in_full", "partial", "minimum"], [55, 35, 10])[0],
            autopay=rng.random() < 0.45, first_deposit_date="", is_hero=is_hero))
    else:
        fd = first_deposit or add_days(opened_at, rng.randint(1, 5))
        acc = ctx.add("accounts", dict(
            account_id=account_id or ctx.next_id("ACC-DDA", 5), primary_customer_id=customer["customer_id"],
            product="lanternfield_visa_debit_checking", regime="REG_E", opened_at=opened_at, status="open",
            credit_limit="", apr="", statement_cycle_day=cycle_day or 28, payment_behavior="", autopay="",
            first_deposit_date=fd, is_hero=is_hero))
    ctx.add("account_holders", dict(account_id=acc["account_id"], customer_id=customer["customer_id"],
                                    role="primary", added_at=opened_at))
    return acc


def make_card(ctx: Ctx, account: dict, customer: dict, role="primary", card_id=None, last4=None,
              issued_at=None) -> dict:
    rng = ctx.rng
    bin_ = CREDIT_BIN if account["regime"] == "REG_Z" else DEBIT_BIN
    last4 = last4 or f"{rng.randint(0, 9999):04d}"
    return ctx.add("cards", dict(
        card_id=card_id or ctx.next_id("CRD", 6), account_id=account["account_id"],
        customer_id=customer["customer_id"], role=role, network="VISA", bin=bin_,
        pan_masked=f"{bin_}******{last4}", last4=last4,
        expiry=f"{rng.randint(1, 12):02d}/{rng.randint(27, 30)}", status="active",
        issued_at=issued_at or account["opened_at"]))


def make_device(ctx: Ctx, device_type: str, owner_id: str, first_seen: str, device_id=None,
                hardware=True) -> dict:
    rng = ctx.rng
    os_ = {"phone": rng.choice(["iOS 19.4", "Android 16"]), "laptop": rng.choice(["macOS 16.2", "Windows 11 24H2"]),
           "tablet": rng.choice(["iPadOS 19.4", "Android 16"]), "desktop": "Windows 11 24H2"}[device_type]
    did = device_id or ctx.next_id("DEV", 6)
    return ctx.add("devices", dict(
        device_id=did, device_type=device_type, os=os_,
        hardware_id=(f"35{rng.randint(10**12, 10**13 - 1)}" if device_type == "phone" and hardware else ""),
        device_fingerprint="fp_" + stable_hex("fp", did, n=40), first_seen=first_seen,
        observed_primary_customer_id=owner_id))


_ip_used: set = set()


def add_ip(ctx: Ctx, ip: str, ip_type: str, isp: str, city: str, note=""):
    if ip in ctx.index["ip_intel"]:
        return ip
    c = CITIES.get(city, {"state": ""})
    ctx.add("ip_intel", dict(ip=ip, ip_type=ip_type, isp=isp, city=city, state=c["state"], country="US", note=note))
    return ip


def new_home_ip(ctx: Ctx, city: str) -> str:
    rng = ctx.rng
    while True:
        ip = f"198.18.{rng.randint(1, 250)}.{rng.randint(2, 254)}"
        if ip not in _ip_used:
            _ip_used.add(ip)
            return add_ip(ctx, ip, "residential", rng.choice(["Metrolink Fiber", "Brightwave Cable", "Crestline DSL"]), city)


def mobile_ip(ctx: Ctx, city: str) -> str:
    ip = f"198.19.250.{ctx.rng.randint(1, 60)}"
    return add_ip(ctx, ip, "mobile_cgnat", "Relaywave Mobile", city, "carrier-grade NAT; shared by many subscribers")


# ============================================================ merchants
def make_merchant(ctx: Ctx, name: str, mcc: str, channel: str, city: str, merchant_id=None, descriptor=None,
                  acquirer_id=None, is_marketplace=False, parent=None, onboarded="2019-05-01", website=None,
                  phone=None, extra_descriptors=(), is_hero=False, country="US", tz=None, legal_suffix=" LLC",
                  state=None) -> dict:
    rng = ctx.rng
    acq = _ACQ[acquirer_id or rng.choice(ACQUIRERS)[0]]
    cinfo = CITIES.get(city)
    mer = ctx.add("merchants", dict(
        merchant_id=merchant_id or ctx.next_id("MER", 5), legal_name=name + legal_suffix, dba_name=name, mcc=mcc,
        mcc_description=MCC.get(mcc, ""), country=country, city=city, state=state or (cinfo["state"] if cinfo else ""),
        timezone=tz or (cinfo["tz"] if cinfo else "UTC"), channel=channel,
        website=website or f"https://www.{name.lower().replace(' ', '').replace('&', 'and').replace('+', 'plus').replace('#', '')}.example",
        phone=phone or f"(888) 555-01{rng.randint(0, 99):02d}", acquirer_id=acq[0], acquirer_name=acq[1],
        card_acceptor_id=f"{rng.randint(10**14, 10**15 - 1)}", is_marketplace=is_marketplace,
        parent_merchant_id=parent or "", onboarded_at=onboarded, status="active", is_hero=is_hero))
    desc = descriptor or name.upper()[:22]
    ctx.add("merchant_descriptors", dict(merchant_id=mer["merchant_id"], descriptor=desc, first_seen=onboarded,
                                         last_seen="", note="primary"))
    for ds, first, last, note in extra_descriptors:
        ctx.add("merchant_descriptors", dict(merchant_id=mer["merchant_id"], descriptor=ds, first_seen=first,
                                             last_seen=last, note=note))
    return mer


def primary_descriptor(ctx: Ctx, merchant_id: str, on_date: str) -> str:
    best = None
    for r in ctx.t["merchant_descriptors"]:
        if r["merchant_id"] != merchant_id:
            continue
        if r["first_seen"] <= on_date and (not r["last_seen"] or on_date <= r["last_seen"]):
            if best is None or r["first_seen"] > best["first_seen"]:
                best = r
    return best["descriptor"] if best else ctx.get("merchants", merchant_id)["dba_name"].upper()[:22]


def build_merchants(ctx: Ctx):
    rng = ctx.rng
    pools = {"city": {}, "national": {}}
    for cat, mcc, channel, scope, names in MERCHANT_CATALOG:
        if scope == "city":
            for city in CITIES:
                for i, nm in enumerate(names):
                    label = f"{nm} #{rng.randint(2, 48)}" if cat in ("fuel", "grocery", "pharmacy") else nm
                    mer = make_merchant(ctx, label, mcc, channel, city,
                                        descriptor=f"{label.upper()[:18]} {CITIES[city]['state']}")
                    if cat == "grocery" and rng.random() < 0.5:  # messy: POS vendor change mid-year
                        ctx.add("merchant_descriptors", dict(merchant_id=mer["merchant_id"],
                                descriptor=f"{nm.upper()[:10]}*{city.upper()[:6]}", first_seen="2026-03-01",
                                last_seen="", note="new POS vendor descriptor"))
                    pools["city"].setdefault((cat, city), []).append(mer["merchant_id"])
        else:
            for nm in names:
                city = rng.choice(list(CITIES))
                mer = make_merchant(ctx, nm, mcc, channel, city)
                pools["national"].setdefault(cat, []).append(mer["merchant_id"])
    ctx.pools = pools


# ============================================================ transactions
_ARN_SEQ = [0]


def _arn(acquirer_bin: str, date_s: str) -> str:
    _ARN_SEQ[0] += 1
    dd = d(date_s)
    body = f"7{acquirer_bin}{str(dd.year)[-1]}{dd.timetuple().tm_yday:03d}{_ARN_SEQ[0]:011d}"
    digits = [int(x) for x in body][::-1]
    total = sum((x * 2 - 9 if x * 2 > 9 else x * 2) if i % 2 == 0 else x for i, x in enumerate(digits))
    return body + str((10 - total % 10) % 10)


def _auth_code(ctx: Ctx) -> str:
    return "".join(ctx.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(6))


def add_txn(ctx: Ctx, account: dict, card: dict, merchant: dict, date_s: str, time_s: str, amount,
            channel="in_store", txn_type="purchase", txn_id=None, processing_lag=None, **kw) -> dict:
    """Create a transaction row with realistic defaults. kw overrides any column."""
    rng = ctx.rng
    tz = merchant["timezone"] if merchant else "America/New_York"
    local = local_dt(date_s, time_s, tz)
    if processing_lag is None:
        processing_lag = 1 if local.weekday() < 4 else rng.choice([1, 2, 3])
    proc = add_days(date_s, processing_lag)
    row = dict(
        txn_id=txn_id or ctx.next_id("TXN", 7), account_id=account["account_id"], card_id=card["card_id"],
        customer_id=card["customer_id"], merchant_id=merchant["merchant_id"] if merchant else "",
        descriptor=primary_descriptor(ctx, merchant["merchant_id"], date_s) if merchant else "",
        mcc=merchant["mcc"] if merchant else "", txn_type=txn_type, billing_amount=m(amount), billing_currency="USD",
        txn_amount=m(amount), txn_currency="USD", fx_rate="", auth_amount=m(amount), auth_id=ctx.next_id("AUT", 8),
        auth_code=_auth_code(ctx), auth_response_code="00", auth_timestamp_utc=iso_utc(local),
        txn_local_datetime=local.strftime("%Y-%m-%d %H:%M:%S"), merchant_timezone=tz,
        processing_date=proc, posting_date=proc, channel=channel, cof_type="none", clearing_seq=1, clearing_count=1,
        arn=_arn(merchant["acquirer_id"] and _ACQ[merchant["acquirer_id"]][2], proc) if merchant else "",
        available_at=iso_utc(dt.datetime.fromisoformat(proc + "T06:00:00").replace(tzinfo=UTC)), is_hero=False)
    if channel == "in_store":
        row.update(pos_entry_mode=rng.choices(["05", "07", "90", "01"], [48, 47, 3, 2])[0], card_present=True)
    elif channel == "ecommerce":
        three = rng.random() < 0.45
        row.update(pos_entry_mode="01", card_present=False, cvv2_presence="1", cvv2_result="M",
                   avs_result=rng.choices(["Y", "Z", "A", "N", "U"], [80, 8, 4, 3, 5])[0],
                   eci="05" if three else "07", cavv_present=three, three_ds_status="Y" if three else "")
    elif channel == "recurring":
        row.update(pos_entry_mode="10", card_present=False, cof_type="mit_recurring", eci="07")
    row.update(kw)
    if row["auth_response_code"] != "00":
        row.update(processing_date="", posting_date="", arn="")
    return ctx.add("transactions", row)


def _amount(rng, lo, hi):
    return money(rng.uniform(lo, hi))


RATE_MULT = 0.6
PROFILE_RATES = {  # expected transactions per month (before RATE_MULT)
    "grocery": 1.6, "restaurant": 0.9, "fast_food": 0.6, "fuel": 0.6, "pharmacy": 0.2, "department": 0.12,
    "ecom_general": 0.45, "electronics": 0.07, "apparel": 0.18, "shoes": 0.05, "home": 0.05,
    "digital_media": 0.12, "games": 0.12, "software": 0.05, "rideshare": 0.3, "hotel": 0.03, "airline": 0.025,
    "tickets": 0.03, "gift_cards": 0.02,
}
AMOUNTS = {
    "grocery": (14, 165), "restaurant": (19, 138), "fast_food": (6.5, 24), "fuel": (24, 78), "pharmacy": (6, 64),
    "department": (25, 240), "ecom_general": (12, 180), "electronics": (35, 780), "apparel": (22, 210),
    "shoes": (48, 190), "home": (30, 260), "digital_media": (1.99, 24.99), "games": (4.99, 69.99),
    "software": (2.99, 49.99), "rideshare": (8.5, 46), "hotel": (160, 880), "airline": (140, 690),
    "tickets": (38, 320), "gift_cards": (25, 150),
}
RECURRING_PRICES = {"streaming": ["9.99", "15.99", "17.99", "22.99"], "subscription_box": ["29.00", "59.95"],
                    "telecom": ["65.00", "85.00"], "gym": ["39.00", "54.00"]}


def gen_history(ctx: Ctx, customer: dict, account: dict, card: dict, start: str, end: str, scale=1.0,
                recurring=True, drives=None, exclude_cats=()):
    """Normal spending for one card between start and end (inclusive)."""
    rng = ctx.rng
    city = ctx.get("addresses", customer["home_address_id"])["city"]
    drives = rng.random() < 0.7 if drives is None else drives
    favorites = {}
    s, e = d(start), d(end)
    if e < s:
        return
    months = []
    cur = dt.date(s.year, s.month, 1)
    while cur <= e:
        months.append(cur)
        cur = dt.date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
    for cat, rate in PROFILE_RATES.items():
        if cat in exclude_cats or (cat == "fuel" and not drives):
            continue
        pool = ctx.pools["city"].get((cat, city)) or ctx.pools["national"].get(cat)
        if not pool:
            continue
        favorites[cat] = rng.sample(pool, k=min(len(pool), 2))
        for mo in months:
            r = rate * scale * RATE_MULT
            n = int(r) + (1 if rng.random() < r % 1 else 0)
            for _ in range(n):
                day = dt.date(mo.year, mo.month, rng.randint(1, 28))
                if day < s or day > e:
                    continue
                mer = ctx.get("merchants", rng.choice(favorites[cat]) if rng.random() < 0.8 else rng.choice(pool))
                channel = "ecommerce" if mer["channel"] == "ecommerce" else "in_store"
                if cat == "rideshare":
                    channel = "in_store"
                hh = rng.randint(7, 21)
                add_txn(ctx, account, card, mer, day.isoformat(), f"{hh:02d}:{rng.randint(0, 59):02d}:00",
                        _amount(rng, *AMOUNTS[cat]), channel=channel,
                        **({"pos_entry_mode": "10", "card_present": False} if cat == "rideshare" else {}))
    if recurring:
        subs = []
        for cat, p in (("streaming", 0.5), ("telecom", 0.3), ("subscription_box", 0.1), ("gym", 0.15),
                       ("utilities", 0.3)):
            if cat in exclude_cats or rng.random() > p:
                continue
            pool = ctx.pools["city"].get((cat, city)) or ctx.pools["national"].get(cat)
            price = rng.choice(RECURRING_PRICES[cat]) if cat in RECURRING_PRICES else None
            subs.append((ctx.get("merchants", rng.choice(pool)), price, rng.randint(1, 28)))
        for mer, price, dom in subs:
            for mo in months:
                day = dt.date(mo.year, mo.month, dom)
                if s <= day <= e:
                    amt = price or _amount(rng, 58, 185)
                    add_txn(ctx, account, card, mer, day.isoformat(), "03:15:00", amt, channel="recurring")


def add_refund(ctx: Ctx, orig: dict, date_s: str, amount=None, descriptor=None, link=True, **kw) -> dict:
    mer = ctx.get("merchants", orig["merchant_id"])
    acct = ctx.get("accounts", orig["account_id"])
    card = ctx.get("cards", orig["card_id"])
    return add_txn(ctx, acct, card, mer, date_s, "10:00:00", amount or orig["billing_amount"], channel=orig["channel"],
                   txn_type="credit", related_txn_id=orig["txn_id"] if link else "",
                   pos_entry_mode=orig["pos_entry_mode"], card_present=orig["card_present"], eci="", avs_result="",
                   cvv2_presence="", cvv2_result="", cavv_present="", three_ds_status="",
                   **({"descriptor": descriptor} if descriptor else {}), **kw)


# ============================================================ issuer account events
def add_event(ctx: Ctx, customer_id: str, account_id: str, event_type: str, ts: str, channel="mobile_app",
              device_id="", ip="", detail=None, is_hero=False, available_at=None) -> dict:
    return ctx.add("account_events", dict(
        event_id=ctx.next_id("EVT", 7), customer_id=customer_id, account_id=account_id, event_type=event_type,
        timestamp_utc=ts, channel=channel, device_id=device_id, ip=ip, detail=detail or {},
        available_at=available_at or ts, is_hero=is_hero))


def gen_login_events(ctx: Ctx, customer: dict, account: dict, devices: list, home_ip: str, start: str, end: str,
                     per_month=2.0):
    rng = ctx.rng
    city = ctx.get("addresses", customer["home_address_id"])["city"]
    tz = CITIES[city]["tz"]
    s, e = d(start), d(end)
    n_days = (e - s).days
    for _ in range(int(n_days / 30 * per_month)):
        day = s + dt.timedelta(days=rng.randint(0, max(n_days, 0)))
        dev = rng.choice(devices)
        ip = home_ip if (dev["device_type"] != "phone" or rng.random() < 0.55) else mobile_ip(ctx, city)
        ts = utc(day.isoformat(), f"{rng.randint(6, 23):02d}:{rng.randint(0, 59):02d}:00", tz)
        add_event(ctx, customer["customer_id"], account["account_id"], "login_success", ts,
                  channel="mobile_app" if dev["device_type"] in ("phone", "tablet") else "web",
                  device_id=dev["device_id"], ip=ip, detail={"auth_method": rng.choice(["biometric", "password", "passkey"])})


# ============================================================ background people
def build_background_people(ctx: Ctx, n_primary=330):
    rng = ctx.rng
    cities, weights = zip(*BACKGROUND_CITY_WEIGHTS.items())
    people = []
    for _ in range(n_primary):
        city = rng.choices(cities, weights)[0]
        cust = make_customer(ctx, city)
        prod = rng.choices(["credit", "debit", "both"], [75, 10, 15])[0]
        opened = cust["customer_since"]
        accounts, cards = [], []
        for p in (["credit", "debit"] if prod == "both" else [prod]):
            acct = make_account(ctx, cust, p, opened_at=opened)
            accounts.append(acct)
            cards.append(make_card(ctx, acct, cust))
        home_ip = new_home_ip(ctx, city)
        devs = [make_device(ctx, "phone", cust["customer_id"], opened)]
        if rng.random() < 0.7:
            devs.append(make_device(ctx, "laptop", cust["customer_id"], opened, hardware=False))
        rec = dict(customer=cust, accounts=accounts, cards=cards, devices=devs, home_ip=home_ip, city=city,
                   household=[])
        ctx.home_ip[cust["customer_id"]] = home_ip
        # authorized user / household member on credit account
        if accounts[0]["regime"] == "REG_Z" and rng.random() < 0.12:
            addr = ctx.get("addresses", cust["home_address_id"])
            member = make_customer(ctx, city, full_name=f"{rng.choice(FIRST_NAMES)} {cust['full_name'].split(' ', 1)[1]}",
                                   address=addr, since=add_days(opened, rng.randint(30, 900)) if opened < "2025-01-01" else opened)
            ctx.add("account_holders", dict(account_id=accounts[0]["account_id"], customer_id=member["customer_id"],
                                            role="authorized_user", added_at=member["customer_since"]))
            au_card = make_card(ctx, accounts[0], member, role="authorized_user", issued_at=member["customer_since"])
            tablet = make_device(ctx, "tablet", cust["customer_id"], opened, hardware=False)
            devs.append(tablet)
            mdevs = [make_device(ctx, "phone", member["customer_id"], member["customer_since"]), tablet]
            rec["household"].append(dict(customer=member, card=au_card, devices=mdevs))
        people.append(rec)
    ctx.people = people
    return people


def build_background_activity(ctx: Ctx):
    rng = ctx.rng
    for rec in ctx.people:
        cust = rec["customer"]
        start = max(HISTORY_START.isoformat(), cust["customer_since"])
        end = add_days(AS_OF_DATE.isoformat(), -1)
        if len(rec["accounts"]) == 2:
            gen_history(ctx, cust, rec["accounts"][0], rec["cards"][0], start, end, scale=0.75)
            gen_history(ctx, cust, rec["accounts"][1], rec["cards"][1], start, end, scale=0.35, recurring=False)
        else:
            gen_history(ctx, cust, rec["accounts"][0], rec["cards"][0], start, end)
        for hh in rec["household"]:
            gen_history(ctx, hh["customer"], rec["accounts"][0], hh["card"], max(start, hh["customer"]["customer_since"]),
                        end, scale=0.3, recurring=False)
            gen_login_events(ctx, hh["customer"], rec["accounts"][0], hh["devices"], rec["home_ip"],
                             max(start, hh["customer"]["customer_since"]), end, per_month=0.6)
        gen_login_events(ctx, cust, rec["accounts"][0], rec["devices"], rec["home_ip"], start, end)
    # sprinkle refunds on e-commerce purchases
    for t in list(ctx.t["transactions"]):
        rate = {"ecommerce": 0.03, "in_store": 0.004}.get(t["channel"], 0)
        if t["txn_type"] == "purchase" and not t["is_hero"] and rng.random() < rate:
            rd = add_days(t["posting_date"] or t["txn_local_datetime"][:10], rng.randint(4, 21))
            if rd < AS_OF_DATE.isoformat():
                add_refund(ctx, t, rd, link=rng.random() < 0.7)


# ============================================================ statements & payments
def _cycle_ends(cycle_day: int, start: dt.date, end: dt.date):
    cur = dt.date(start.year, start.month, min(cycle_day, 28))
    if cur < start:
        cur = dt.date(cur.year + (cur.month // 12), cur.month % 12 + 1, min(cycle_day, 28))
    while cur <= end:
        yield cur
        cur = dt.date(cur.year + (cur.month // 12), cur.month % 12 + 1, min(cycle_day, 28))


def build_statements_and_payments(ctx: Ctx):
    """Monthly statements for every account; payments for credit accounts per payment_behavior."""
    by_acct: dict = {}
    for t in ctx.t["transactions"]:
        if t["posting_date"]:
            by_acct.setdefault(t["account_id"], []).append(t)
    primary_card = {c["account_id"]: c for c in ctx.t["cards"] if c["role"] == "primary"}
    for acct in list(ctx.t["accounts"]):
        txns = by_acct.setdefault(acct["account_id"], [])
        opened = max(d(acct["opened_at"]), HISTORY_START - dt.timedelta(days=31))
        cycle_day = int(acct["statement_cycle_day"])
        prev_end = None
        prev_bal = money(0)
        card = primary_card[acct["account_id"]]
        pending_payment = None
        for ce in _cycle_ends(cycle_day, opened, AS_OF_DATE - dt.timedelta(days=1)):
            cs = (prev_end + dt.timedelta(days=1)) if prev_end else max(opened, ce - dt.timedelta(days=30))
            # payment for previous statement posts inside this cycle
            if pending_payment and acct["regime"] == "REG_Z":
                pay_date, pay_amt = pending_payment
                if pay_amt > 0 and cs <= pay_date <= ce:
                    txns.append(add_txn(ctx, acct, card, None, pay_date.isoformat(), "08:00:00", pay_amt,
                                        channel="payment", txn_type="payment", processing_lag=0, pos_entry_mode="",
                                        auth_code="", auth_id="", descriptor="PAYMENT - THANK YOU"))
            lo, hi = cs.isoformat(), ce.isoformat()
            in_cycle = [t for t in txns if lo <= t["posting_date"] <= hi]
            pur = sum((money(t["billing_amount"]) for t in in_cycle if t["txn_type"] == "purchase"), money(0))
            cred = sum((money(t["billing_amount"]) for t in in_cycle if t["txn_type"] in ("credit", "provisional_credit")), money(0))
            pay = sum((money(t["billing_amount"]) for t in in_cycle if t["txn_type"] == "payment"), money(0))
            fees = sum((money(t["billing_amount"]) for t in in_cycle if t["txn_type"] == "fee"), money(0))
            close = prev_bal + pur + fees - cred - pay
            if acct["regime"] == "REG_Z":
                due = ce + dt.timedelta(days=25)
                mind = money(0) if close <= 0 else max(money(35), money(close * money("0.02")))
                beh = acct["payment_behavior"]
                amt = close if beh == "pay_in_full" else (money(close * money("0.4")) if beh == "partial" else mind)
                pending_payment = (due - dt.timedelta(days=ctx.rng.randint(1, 6)), max(money(0), amt))
            else:
                due, mind = None, money(0)
            ctx.add("statements", dict(
                statement_id=f"STM-{acct['account_id'][4:]}-{ce.strftime('%Y%m')}", account_id=acct["account_id"],
                cycle_start=cs.isoformat(), cycle_end=ce.isoformat(),
                transmitted_at=utc((ce + dt.timedelta(days=1)).isoformat(), "09:00:00"),
                due_date=due.isoformat() if due else "", previous_balance=m(prev_bal), purchases=m(pur),
                credits=m(cred), payments=m(pay), fees=m(fees), closing_balance=m(close), minimum_due=m(mind)))
            prev_bal, prev_end = close, ce


# ============================================================ disputes
def add_dispute(ctx: Ctx, case_id: str, txns: list, regime: str, opened_at: str, claim_summary: str,
                claim_family: str, amounts=None, is_hero=False, **kw) -> dict:
    t0 = txns[0]
    row = dict(case_id=case_id, account_id=t0["account_id"], customer_id=ctx.get("cards", t0["card_id"])["customer_id"],
               card_id=t0["card_id"], regime=regime, status="open", stage="intake", opened_at=opened_at,
               intake_channel="phone", intake_authenticated_via="ivr_otp", claim_summary=claim_summary,
               claim_family_initial=claim_family, network="VISA",
               dispute_amount=m(sum(money(a) for a in (amounts or [t["billing_amount"] for t in txns]))),
               is_hero=is_hero)
    row.update(kw)
    dsp = ctx.add("disputes", row)
    for i, t in enumerate(txns):
        ctx.add("dispute_transactions", dict(case_id=case_id, txn_id=t["txn_id"],
                                             disputed_amount=m((amounts or [x["billing_amount"] for x in txns])[i])))
    return dsp


def add_devent(ctx: Ctx, case_id: str, ts: str, event_type: str, summary: str, actor="system", detail=None,
               available_at=None):
    return ctx.add("dispute_events", dict(event_id=ctx.next_id("DEV-EVT", 7), case_id=case_id, timestamp_utc=ts,
                                          event_type=event_type, actor=actor, summary=summary, detail=detail or {},
                                          available_at=available_at or ts))


def add_comm(ctx: Ctx, customer_id: str, ts: str, direction: str, channel: str, party: str, body: str, case_id="",
             merchant_id="", subject="", attachments=None, available_at=None):
    return ctx.add("communications", dict(comm_id=ctx.next_id("COM", 7), case_id=case_id, customer_id=customer_id,
                                          merchant_id=merchant_id, direction=direction, channel=channel, party=party,
                                          timestamp_utc=ts, available_at=available_at or ts, subject=subject,
                                          body=body, attachments=attachments or []))


def add_packet(ctx: Ctx, packet_id: str, case_id: str, txn_id: str, merchant_id: str, source: str, requested_at: str,
               available_at: str, content: dict):
    path = f"evidence_packets/{packet_id}.json"
    ctx.add("evidence_packets", dict(packet_id=packet_id, case_id=case_id, txn_id=txn_id, merchant_id=merchant_id,
                                     source=source, requested_at=requested_at, available_at=available_at, path=path))
    ctx.packets[packet_id] = dict(packet_id=packet_id, case_id=case_id, txn_id=txn_id, merchant_id=merchant_id,
                                  source=source, requested_at=requested_at, available_at=available_at, **content)


ANALYSTS = ["analyst.jmorales", "analyst.tkhan", "analyst.lpetrov", "analyst.abanerjee", "analyst.cwright"]

# family -> (claim text, condition, weight, natures[(nature, weight, cardholder_outcome, network_outcome)])
BG_FAMILIES = {
    "fraud_cnp": ("Cardholder does not recognize and did not authorize an online purchase.", "10.4", 88, [
        ("third_party_fraud", 70, "credited", "issuer_won"), ("first_party_misuse", 18, "denied", "merchant_won_pre_arb"),
        ("household_member", 5, "denied", "merchant_won_pre_arb"), ("account_takeover", 7, "credited", "issuer_won")]),
    "fraud_card_present": ("Card lost; cardholder did not make in-store purchases.", "10.3", 10, [
        ("third_party_fraud", 100, "credited", "issuer_won")]),
    "not_received": ("Paid for an order that never arrived.", "13.1", 38, [
        ("merchant_failure", 55, "credited", "issuer_won"), ("delivered_first_party", 25, "denied", "merchant_won"),
        ("late_delivery_received", 20, "withdrawn", "not_filed")]),
    "not_as_described": ("Item received is defective / not as described.", "13.3", 22, [
        ("valid_defect_return_attempted", 64, "credited", "issuer_won"), ("no_return_attempt", 36, "denied", "merchant_won")]),
    "cancelled_recurring": ("Subscription was cancelled but charges continued.", "13.2", 25, [
        ("cancelled_before_charge", 68, "credited", "issuer_won"), ("used_after_cancel", 32, "denied", "merchant_won")]),
    "credit_not_processed": ("Returned item; merchant promised refund that never posted.", "13.6", 15, [
        ("credit_missing", 80, "credited", "issuer_won"), ("credit_already_posted", 20, "withdrawn", "not_filed")]),
    "duplicate": ("Charged twice for the same purchase.", "12.6", 10, [
        ("true_duplicate", 60, "credited", "issuer_won"), ("separate_purchases", 40, "denied", "not_filed")]),
    "incorrect_amount": ("Charged more than the receipt amount.", "12.5", 6, [
        ("keying_error", 100, "partial_credit", "issuer_won")]),
    "cancelled_merch": ("Cancelled order within policy; no refund.", "13.7", 12, [
        ("cancelled_per_policy", 75, "credited", "issuer_won"), ("outside_policy", 25, "denied", "merchant_won")]),
    "descriptor_confusion": ("Does not recognize merchant name on statement.", "", 12, [
        ("recognized_after_clarification", 100, "withdrawn", "not_filed")]),
}


def _pick(rng, pairs):
    return rng.choices(pairs, [p[1] for p in pairs])[0]


def build_background_disputes(ctx: Ctx, n=238, exclude_customers=frozenset()):
    """Background disputes with lifecycle events, intake comms, some evidence packets, and labels."""
    rng = ctx.rng
    ctx.bg_labels = []
    fams = list(BG_FAMILIES)
    weights = [BG_FAMILIES[f][2] for f in fams]
    purchases = [t for t in ctx.t["transactions"] if t["txn_type"] == "purchase" and t["posting_date"]
                 and t["posting_date"] >= "2025-11-15" and t["customer_id"] not in exclude_customers
                 and not t["is_hero"] and t["auth_response_code"] == "00" and not t["merchant_id"].startswith("MER-9")]
    used = set()
    ecom = [t for t in purchases if t["channel"] == "ecommerce"]
    recur = [t for t in purchases if t["channel"] == "recurring"]
    instore = [t for t in purchases if t["channel"] == "in_store"]
    made = 0
    while made < n:
        fam = rng.choices(fams, weights)[0]
        claim, cond, _, natures = BG_FAMILIES[fam]
        nature, _, ch_out, net_out = _pick(rng, natures)
        pool = {"cancelled_recurring": recur, "fraud_card_present": instore, "descriptor_confusion": instore + ecom,
                "incorrect_amount": instore}.get(fam, ecom)
        recent = [x for x in pool[-400:] if x["posting_date"] >= "2026-08-20"] if rng.random() < 0.3 else None
        t = rng.choice(recent or pool)
        if t["txn_id"] in used:
            continue
        used.add(t["txn_id"])
        if fam in ("fraud_cnp", "fraud_card_present") and nature in ("third_party_fraud", "account_takeover"):
            t = _make_fraud_txn(ctx, t, card_present=(fam == "fraud_card_present"))
        opened = add_days(t["posting_date"], rng.randint(3, 55))
        if opened >= AS_OF_DATE.isoformat():
            continue
        acct = ctx.get("accounts", t["account_id"])
        cid = f"DSP-2026-{ctx.next_id('BG', 5)[3:]}" if opened >= "2026-01-01" else f"DSP-2025-{ctx.next_id('BG', 5)[3:]}"
        closed = opened < "2026-09-08"
        amount = t["billing_amount"]
        if fam == "incorrect_amount":
            amount = m(money(t["billing_amount"]) * money("0.1"))
        dsp = add_dispute(ctx, cid, [t], acct["regime"], utc(opened, f"{rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}:00"),
                          claim, fam, amounts=[amount], intake_channel=rng.choice(["phone", "app_chat", "secure_message"]),
                          assigned_queue="fraud_cnp" if fam.startswith("fraud") else "consumer_disputes")
        correct = _lifecycle(ctx, dsp, t, fam, cond, nature, ch_out, net_out, closed)
        ctx.bg_labels.append(dict(case_id=cid, family=fam, true_nature=nature,
                                  expected_network_condition=cond if net_out != "not_filed" else "",
                                  expected_cardholder_outcome=ch_out, status=dsp["status"],
                                  historical_decision_correct=correct))
        made += 1


def _make_fraud_txn(ctx: Ctx, legit: dict, card_present=False) -> dict:
    """Replace a background dispute's target with a genuinely foreign transaction."""
    rng = ctx.rng
    acct = ctx.get("accounts", legit["account_id"])
    card = ctx.get("cards", legit["card_id"])
    cat = rng.choice(["electronics", "gift_cards", "ecom_general", "shoes"]) if not card_present else "department"
    if card_present:
        other_city = rng.choice([c for c in CITIES if c != ctx.get("merchants", legit["merchant_id"])["city"]])
        mer = ctx.get("merchants", rng.choice(ctx.pools["city"][("department", other_city)]))
        return add_txn(ctx, acct, card, mer, legit["txn_local_datetime"][:10], "15:22:00", _amount(rng, 180, 900),
                       channel="in_store", pos_entry_mode="90", card_present=True)
    mer = ctx.get("merchants", rng.choice(ctx.pools["national"][cat]))
    return add_txn(ctx, acct, card, mer, legit["txn_local_datetime"][:10], f"0{rng.randint(1, 5)}:{rng.randint(10, 59)}:00",
                   _amount(rng, 150, 1200), channel="ecommerce", avs_result=rng.choice(["N", "U", "Z"]), eci="07",
                   cavv_present=False, three_ds_status="", cvv2_presence=rng.choice(["1", "0"]), cvv2_result="M")


def _lifecycle(ctx: Ctx, dsp: dict, t: dict, fam: str, cond: str, nature: str, ch_out: str, net_out: str, closed: bool):
    rng = ctx.rng
    cid = dsp["case_id"]
    cust = dsp["customer_id"]
    opened = dsp["opened_at"][:10]
    analyst = rng.choice(ANALYSTS)
    mer = ctx.get("merchants", t["merchant_id"])
    add_devent(ctx, cid, dsp["opened_at"], "intake_created", f"Claim opened via {dsp['intake_channel']}: {dsp['claim_summary']}")
    add_comm(ctx, cust, dsp["opened_at"], "inbound", {"phone": "phone_summary", "app_chat": "chat",
             "secure_message": "secure_message"}[dsp["intake_channel"]], "cardholder",
             _intake_text(rng, fam, nature, t, mer), case_id=cid, merchant_id=mer["merchant_id"], subject="Dispute intake")
    ack = utc(add_days(opened, rng.randint(1, 4)), "10:00:00")
    add_devent(ctx, cid, ack, "ack_letter_sent", "Billing-rights acknowledgment sent" if dsp["regime"] == "REG_Z"
               else "Reg E error notice acknowledgment sent")
    if fam.startswith("fraud"):
        add_devent(ctx, cid, ack, "fraud_reported", "Fraud activity reported to network (TC40)", actor=analyst)
        t["fraud_reported_at"] = ack
    pc_date = add_days(opened, rng.randint(1, 5))
    if ch_out != "withdrawn" and money(dsp["dispute_amount"]) > 0:
        dsp.update(provisional_credit_amount=dsp["dispute_amount"], provisional_credit_at=utc(pc_date, "11:00:00"))
        add_devent(ctx, cid, dsp["provisional_credit_at"], "provisional_credit_posted",
                   f"Temporary credit {dsp['dispute_amount']} posted")
    labels_correct = True
    if not closed:
        age = (AS_OF_DATE - d(opened)).days
        if ch_out == "withdrawn" or age < 6:
            dsp.update(stage="investigating")
        elif age < 12:
            dsp.update(stage="awaiting_merchant_evidence")
            _bg_packet(ctx, dsp, t, fam, nature, available=utc(add_days(opened, rng.randint(3, 9)), "14:00:00"))
        else:
            filed = add_days(opened, rng.randint(4, 9))
            dsp.update(stage="dispute_filed", network_condition=cond, dispute_processing_date=filed,
                       network_case_ref=f"VRL{rng.randint(10**9, 10**10 - 1)}")
            add_devent(ctx, cid, utc(filed, "15:00:00"), "dispute_filed", f"Visa {cond} dispute filed", actor=analyst)
            if age > 34 and net_out.startswith("merchant_won"):
                resp = add_days(filed, rng.randint(20, 29))
                dsp.update(stage="pre_arb_decision_due", response_processing_date=resp)
                add_devent(ctx, cid, utc(resp, "16:00:00"), "dispute_response_received",
                           "Acquirer response with compelling evidence received")
                _bg_packet(ctx, dsp, t, fam, nature, available=utc(resp, "16:00:00"), source="dispute_response")
        return True
    # ---------------- closed lifecycle
    if net_out == "not_filed":
        end = add_days(opened, rng.randint(2, 12))
        dsp.update(status="closed", stage="closed", cardholder_outcome=ch_out, network_outcome=net_out,
                   closed_at=utc(end, "17:00:00"))
        add_devent(ctx, cid, dsp["closed_at"], "case_closed", f"Closed: {ch_out}", actor=analyst,
                   detail={"note": _note(rng, fam, nature, ch_out)})
        return True
    filed = add_days(opened, rng.randint(3, 10))
    dsp.update(network_condition=cond, dispute_processing_date=filed, network_case_ref=f"VRL{rng.randint(10**9, 10**10 - 1)}")
    add_devent(ctx, cid, utc(filed, "15:00:00"), "dispute_filed", f"Visa {cond} dispute filed", actor=analyst)
    end = add_days(filed, rng.randint(10, 60))
    if net_out.startswith("merchant_won"):
        resp = add_days(filed, rng.randint(15, 29))
        dsp.update(response_processing_date=resp)
        add_devent(ctx, cid, utc(resp, "16:00:00"), "dispute_response_received", "Acquirer response received")
        _bg_packet(ctx, dsp, t, fam, nature, available=utc(resp, "16:00:00"), source="dispute_response")
        end = add_days(resp, rng.randint(3, 25))
        add_devent(ctx, cid, utc(end, "12:00:00"), "provisional_credit_reversed", "Temporary credit reversed; cardholder re-billed with explanation")
    # QA realism: ~7% of closed decisions judged wrong in hindsight
    if rng.random() < 0.07:
        labels_correct = False
    dsp.update(status="closed", stage="closed", cardholder_outcome=ch_out, network_outcome=net_out, closed_at=utc(end, "17:00:00"))
    add_devent(ctx, cid, dsp["closed_at"], "case_closed", f"Closed: cardholder {ch_out}; network {net_out}", actor=analyst,
               detail={"note": _note(rng, fam, nature, ch_out)})
    return labels_correct


def _intake_text(rng, fam, nature, t, mer) -> str:
    amt, desc, day = t["billing_amount"], t["descriptor"], t["txn_local_datetime"][:10]
    base = {
        "fraud_cnp": f"Cardholder states they did not make the {desc} purchase of ${amt} on {day}. Card still in possession.",
        "fraud_card_present": f"Cardholder reports wallet lost; did not make the ${amt} purchase at {desc} on {day}.",
        "not_received": f"Ordered from {desc} on {day} (${amt}). Nothing arrived. Says they emailed the merchant.",
        "not_as_described": f"Item from {desc} (${amt}) arrived damaged / not as pictured.",
        "cancelled_recurring": f"Cancelled {desc} membership but was still charged ${amt} on {day}.",
        "credit_not_processed": f"Returned purchase to {desc}; refund of ${amt} promised but not received.",
        "duplicate": f"Says {desc} charged ${amt} twice.",
        "incorrect_amount": f"Receipt from {desc} shows a lower total than the ${amt} charged.",
        "cancelled_merch": f"Cancelled order with {desc} within their cancellation window; charge of ${amt} not refunded.",
        "descriptor_confusion": f"Does not recognize '{desc}' ${amt} on {day}.",
    }[fam]
    if nature == "first_party_misuse" and rng.random() < 0.5:
        base += " Cardholder was hesitant when asked whether anyone else uses their devices."
    if nature == "household_member":
        base += " Mentions teenagers at home but says nobody has access to the card."
    return base


def _note(rng, fam, nature, outcome) -> str:
    notes = {
        "third_party_fraud": "AVS mismatch, no 3DS, ship-to not on file. Consistent with third-party fraud. Credited.",
        "account_takeover": "Merchant account email changed shortly before order. Treated as ATO. Credited.",
        "first_party_misuse": "Merchant CE: prior undisputed orders from same device/IP, item delivered to billing address. Cardholder shown evidence; no rebuttal. Re-billed.",
        "household_member": "Merchant showed purchase from household device; cardholder acknowledged child made purchase. Re-billed.",
        "merchant_failure": "No tracking provided; merchant unresponsive. Chargeback successful.",
        "delivered_first_party": "POD with full address and photo. Cardholder did not rebut. Re-billed.",
        "late_delivery_received": "Package arrived after intake; cardholder withdrew.",
        "valid_defect_return_attempted": "Return attempted; merchant refused RMA. 13.3 won.",
        "no_return_attempt": "Cardholder never attempted return; acquirer response valid. Re-billed.",
        "cancelled_before_charge": "Cancellation confirmation predates charge. 13.2 won.",
        "used_after_cancel": "Merchant usage logs after cancellation date. Accepted response.",
        "credit_missing": "Credit receipt provided; merchant never processed. 13.6 won.",
        "credit_already_posted": "Refund found posted 3 days after intake. Closed.",
        "true_duplicate": "Same auth cleared twice with identical amount and date. 12.6 won.",
        "separate_purchases": "Two distinct orders with different items. No error.",
        "keying_error": "Receipt vs clearing amount differ by transposition. Partial 12.5.",
        "cancelled_per_policy": "Cancelled within disclosed window. 13.7 won.",
        "outside_policy": "Cancellation after disclosed deadline. Merchant response valid.",
        "recognized_after_clarification": "Explained descriptor; cardholder recognized merchant.",
    }
    return notes[nature]


def _bg_packet(ctx: Ctx, dsp: dict, t: dict, fam: str, nature: str, available: str, source="order_insight"):
    rng = ctx.rng
    mer = ctx.get("merchants", t["merchant_id"])
    cust = ctx.get("customers", dsp["customer_id"])
    addr = ctx.get("addresses", cust["home_address_id"])
    full = f"{addr['line1']}{', ' + addr['line2'] if addr['line2'] else ''}, {addr['city']}, {addr['state']} {addr['postal_code']}"
    content = {"merchant_statement": "", "order": {"order_id": f"ORD-{stable_hex(t['txn_id'], n=8).upper()}",
                                                    "order_date": t["txn_local_datetime"][:10], "total": t["billing_amount"]}}
    if fam.startswith("fraud"):
        prior_match = nature in ("first_party_misuse", "household_member")
        content.update(
            customer_account={"login_id": cust["email"].split("@")[0] if prior_match else f"user{rng.randint(1000, 9999)}",
                              "email_on_file": cust["email"] if prior_match else f"shopper{rng.randint(100, 999)}@example.net"},
            session={"ip": ctx.home_ip.get(cust["customer_id"], "198.18.3.3") if prior_match
                     else f"203.0.113.{rng.randint(2, 250)}",
                     "device_fingerprint": "fp_" + stable_hex(t["txn_id"], n=40)},
            shipping_address=full if prior_match else f"{rng.randint(10, 999)} Industrial Pkwy Unit {rng.randint(1, 30)}, Toledo, OH 43604",
            merchant_statement="Order placed from a returning customer account with prior undisputed orders." if prior_match
            else "No prior relationship with this customer account.")
    elif fam == "not_received":
        delivered = nature != "merchant_failure"
        content.update(shipments=[{"carrier": rng.choice(["ParcelPath", "Swiftline Freight", "USPostal Ground"]),
                                   "tracking_number": f"PP{rng.randint(10**10, 10**11 - 1)}",
                                   "events": [{"status": "label_created", "ts": utc(add_days(t["txn_local_datetime"][:10], 1))}] +
                                             ([{"status": "delivered", "ts": utc(add_days(t["txn_local_datetime"][:10], 5), "14:10:00"),
                                                "address": full}] if delivered else []),
                                   "proof_of_delivery": ({"address": full, "photo_description": "Parcel on doormat beside door."}
                                                         if delivered else None)}],
                       merchant_statement="Delivered per carrier." if delivered else "")
    else:
        content.update(merchant_statement="Merchant disputes the claim; see attached policy and records.",
                       policies_accepted=[{"document": "Terms of Sale", "accepted_at": t["auth_timestamp_utc"]}])
    add_packet(ctx, f"MEP-{dsp['case_id'][4:]}-{source[:2].upper()}", dsp["case_id"], t["txn_id"], mer["merchant_id"],
               source, dsp["opened_at"], available, content)
