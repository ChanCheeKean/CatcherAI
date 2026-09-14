"""Helpers shared by hero case builders."""
from __future__ import annotations

from types import SimpleNamespace

import background as bg
from common import AS_OF, Ctx, add_days, iso_utc, utc

AS_OF_DATE = bg.AS_OF_DATE.isoformat()
AS_OF_ISO = iso_utc(AS_OF)


def person(ctx: Ctx, n: int, name: str, city: str, since: str, product="credit", cycle_day=None,
           behavior="pay_in_full", line1=None, line2="", postal=None, employer=None, opened=None,
           first_deposit=None, history_from="2025-10-01", history=True, phone_slot=None, email=None,
           credit_limit=None, drives=None, exclude_cats=(), tablet=False, segment=None, birth_year=None,
           ip=None, address=None, history_scale=1.0) -> SimpleNamespace:
    addr = address or bg.make_address(ctx, city, line1=line1, line2=line2, postal=postal,
                                      address_id=f"ADR-{n}")
    cust = bg.make_customer(ctx, city, customer_id=f"CUS-{n}", full_name=name, since=since, address=addr,
                            employer=employer, is_hero=True, segment=segment, birth_year=birth_year,
                            phone=bg.phone_for(ctx, city, phone_slot) if phone_slot is not None else None,
                            email=email)
    acct = bg.make_account(ctx, cust, product, opened_at=opened or since, cycle_day=cycle_day, behavior=behavior,
                           account_id=f"ACC-{'CR' if product == 'credit' else 'DDA'}-{n}", credit_limit=credit_limit,
                           first_deposit=first_deposit, is_hero=True)
    card = bg.make_card(ctx, acct, cust, card_id=f"CRD-{n}", issued_at=opened or since)
    phone = bg.make_device(ctx, "phone", cust["customer_id"], opened or since, device_id=f"DEV-{n}-PH")
    laptop = bg.make_device(ctx, "laptop", cust["customer_id"], opened or since, device_id=f"DEV-{n}-LT", hardware=False)
    devices = [phone, laptop]
    tab = None
    if tablet:
        tab = bg.make_device(ctx, "tablet", cust["customer_id"], opened or since, device_id=f"DEV-{n}-TB", hardware=False)
        devices.append(tab)
    home_ip = bg.add_ip(ctx, ip, "residential", "Metrolink Fiber", city) if ip else bg.new_home_ip(ctx, city)
    ctx.home_ip[cust["customer_id"]] = home_ip
    start = max(history_from, opened or since)
    if history:
        bg.gen_history(ctx, cust, acct, card, start, add_days(AS_OF_DATE, -1), drives=drives,
                       exclude_cats=exclude_cats, scale=history_scale)
        bg.gen_login_events(ctx, cust, acct, devices, home_ip, start, add_days(AS_OF_DATE, -1))
    return SimpleNamespace(cust=cust, acct=acct, card=card, phone=phone, laptop=laptop, tablet=tab, ip=home_ip,
                           addr=addr, devices=devices, city=city, n=n)


def full_address(addr: dict) -> str:
    unit = f", {addr['line2']}" if addr["line2"] else ""
    return f"{addr['line1']}{unit}, {addr['city']}, {addr['state']} {addr['postal_code']}"


def research(ctx: Ctx, doc_id: str, title: str, url: str, publisher: str, published_at: str, captured_at: str,
             doc_type: str, body: str, related_merchant_id=""):
    ctx.research[doc_id] = dict(doc_id=doc_id, title=title, url=url, publisher=publisher, published_at=published_at,
                                captured_at=captured_at, doc_type=doc_type, related_merchant_id=related_merchant_id,
                                body=body.strip() + "\n")


def persona(ctx: Ctx, case_id: str, customer_id: str, profile: str, knows: list, disclosure_rules: list,
            scripted_replies: list, style: str = "plain, cooperative"):
    ctx.personas[case_id] = dict(case_id=case_id, customer_id=customer_id, profile=profile, style=style,
                                 facts_known_to_cardholder=knows, disclosure_rules=disclosure_rules,
                                 scripted_replies=scripted_replies)


def truth(ctx: Ctx, case_id: str, **kw):
    base = dict(case_id=case_id, as_of=AS_OF_ISO, schema_version="1.0")
    base.update(kw)
    ctx.ground_truth[case_id] = base
