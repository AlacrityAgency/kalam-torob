"""
ایجنت پیگیری فروشنده (گام چهارم چالش).

برای یک آفر، مراحل پیگیری را به ترتیب اجرا می‌کند: ساعت کاری ← پاسخ‌گویی فروشنده ← قیمت و موجودی ←
گارانتی ← اقساط، و در پایان تصمیم می‌گیرد: «بروید»، «اول تماس بگیرید» یا «به جایگزین بروید».
اگر فروشنده پاسخ ندهد (طبق ساعت کاری بسته باشد) یا قیمت قابل اتکا نباشد، جایگزین‌ها را خودش پیدا می‌کند.

شماره‌های دیتاست ساختگی‌اند و تماس واقعی ممکن نیست؛ پاسخ‌های فروشنده شبیه‌سازی از داده‌های همان
آفر هستند و خروجی همیشه برچسب simulated دارد. برای فروشگاه‌های دارای هویت واقعی (اینستاگرام/وب‌سایت)
راه ارتباط واقعی هم برگردانده می‌شود.
"""

from __future__ import annotations

import re
import sqlite3

from .algorithms.hours import hours_status
from .algorithms.svdp import generate_inquiry_dossier, simulate_inquiry
from .algorithms.textutil import to_fa_digits
from .algorithms.tfra import find_emergency_fallbacks

LEVEL_STATUS = {"high": "ok", "medium": "warn", "low": "bad", "unknown": "warn"}


def _contact_channels(shop: dict, dossier: dict) -> list[dict]:
    channels = []
    insta = shop.get("instagram")
    if insta:
        handle = re.sub(r"^@|^https?://(www\.)?instagram\.com/|/.*$", "", str(insta))
        if re.fullmatch(r"[A-Za-z0-9._]{1,30}", handle):
            channels.append({"type": "instagram", "label": "پیام در اینستاگرام", "url": f"https://ig.me/m/{handle}", "real": True})
    site = shop.get("website_url")
    if site and str(site).startswith(("http://", "https://")):
        channels.append({"type": "website", "label": "وب‌سایت فروشگاه", "url": site, "real": True})
    if dossier.get("phone_number"):
        channels.append({"type": "phone", "label": f"تماس با {to_fa_digits(dossier['phone_number'])}", "url": f"tel:{dossier['phone_number']}",
                         "real": False, "note": "شماره در دیتاست آزمایشی ترب ساختگی است"})
    return channels


def follow_up(conn: sqlite3.Connection, offer_id: str) -> dict | None:
    row = conn.execute("""
        SELECT p.product_id, p.persian_title, o.price_toman, o.last_price_changed_at, o.warranty, o.seller_title,
               o.is_copy, o.price_suspect, s.shop_id, s.name, s.payment_options, s.weekly_hours, s.contacts,
               s.instagram, s.website_url
        FROM offers o JOIN shops s ON o.shop_id = s.shop_id JOIN products p ON p.product_id = o.product_id
        WHERE o.offer_id = ?
    """, (offer_id,)).fetchone()
    if not row:
        return None
    keys = ["product_id", "product_title", "price_toman", "last_price_changed_at", "warranty", "seller_title", "is_copy",
            "price_suspect", "shop_id", "shop_name", "payment_options", "weekly_hours", "contacts", "instagram", "website_url"]
    offer = dict(zip(keys, row))
    hours = hours_status(offer["weekly_hours"])
    dossier = generate_inquiry_dossier(offer["product_title"], offer["price_toman"], offer["shop_name"], offer["contacts"])

    steps = []
    # ۱. ساعت کاری
    status = {"open": "ok", "closed": "bad"}.get(hours["state"], "warn")
    steps.append({"key": "hours", "label": "ساعت کاری", "status": status,
                  "text": hours["label"] + (" — جمعه‌ها تعطیل" if hours.get("friday_closed") else "")})

    # ۲. پاسخ‌گویی فروشنده
    answered = hours["state"] != "closed"
    if not answered:
        steps.append({"key": "contact", "label": "تماس با فروشنده", "status": "bad",
                      "text": "پاسخی دریافت نشد: طبق ساعت کاری ثبت‌شده، مغازه الان بسته است."})
    elif hours["state"] == "unknown":
        steps.append({"key": "contact", "label": "تماس با فروشنده", "status": "warn",
                      "text": "ساعت کاری ثبت نشده؛ معلوم نیست الان پاسخ دهد. پاسخ‌های زیر از داده‌های ثبت‌شده است."})
    else:
        steps.append({"key": "contact", "label": "تماس با فروشنده", "status": "ok",
                      "text": "مغازه طبق ساعت کاری باز است؛ پاسخ‌های زیر از داده‌های ثبت‌شده همین آفر شبیه‌سازی شده‌اند."})

    # ۳ تا ۵. قیمت و موجودی، گارانتی، اقساط
    sims = {}
    if answered:
        for key, label in (("availability", "قیمت و موجودی"), ("warranty", "گارانتی و اصالت"), ("credit", "خرید اقساطی")):
            sim = simulate_inquiry(offer, key)
            sims[key] = sim
            steps.append({"key": key, "label": label, "status": LEVEL_STATUS.get(sim["level"], "warn"),
                          "question": sim["agent"], "text": sim["seller"]})

    # تصمیم
    availability = sims.get("availability", {}).get("level")
    alternatives = []
    if not answered or availability == "low" or offer["is_copy"]:
        decision = {"action": "alternative", "label": "به جایگزین بروید",
                    "text": "این فروشگاه الان پاسخ نمی‌دهد یا قیمتش قابل اتکا نیست؛ این فروشگاه‌ها همین کالا را دارند:"}
        fb = find_emergency_fallbacks(conn, offer["product_id"], offer["shop_id"])
        alternatives = [f for f in fb.get("recommended_fallbacks", []) if f["hours"]["state"] != "closed"][:3] \
            or fb.get("recommended_fallbacks", [])[:3]
        if not alternatives:
            decision["text"] = "فروشگاه دیگری این کالا را با قیمت ثبت‌شده ندارد؛ " + (
                hours["label"] if hours["state"] == "closed" else "پیش از رفتن حتماً تماس بگیرید.")
    # گارانتی و اقساط اطلاعات تکمیلی‌اند؛ تصمیم رفتن فقط به ساعت کاری، پاسخ‌گویی و قیمت/موجودی بستگی دارد
    elif any(st["status"] != "ok" for st in steps if st["key"] in ("hours", "contact", "availability")):
        decision = {"action": "call_first", "label": "اول تماس بگیرید",
                    "text": "بخشی از اطلاعات تأیید نشده است؛ پیش از رفتن تماس بگیرید یا پیام بدهید."}
    else:
        decision = {"action": "go", "label": "می‌توانید بروید",
                    "text": "مغازه باز است و قیمت تازه ثبت شده؛ با این حال موجودی تا تماس واقعی تأیید نشده است."}

    return {
        "simulated": True,
        "notice": "شبیه‌سازی بر اساس داده‌های ثبت‌شده در ترب؛ با فروشنده واقعی تماس گرفته نشده است.",
        "shop": {"shop_id": offer["shop_id"], "name": offer["shop_name"]},
        "steps": steps,
        "decision": decision,
        "alternatives": alternatives,
        "contact_channels": _contact_channels(offer, dossier),
        "chat_draft_text": dossier["chat_draft_text"],
    }
