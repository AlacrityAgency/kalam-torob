"""
حالت ایجنت دستیار: یک «مأموریت خرید» را از اول تا آخر خودش انجام می‌دهد.

کاربر یک جمله می‌گوید («یه گوشی A55 قسطی نزدیک من پیدا کن و هماهنگ کن») و ایجنت مثل یک
خریدار باتجربه قدم‌به‌قدم کار می‌کند و هر قدم را با دلیلش گزارش می‌دهد:

۱. فهم درخواست (کالا، محدوده، بودجه، اقساط، نزدیکی)
۲. پیدا کردن کالا در کاتالوگ
۳. مقایسه فروشگاه‌ها با امتیاز قیمت، فاصله، باز بودن و تازگی قیمت
۴. پیگیری با فروشگاه‌ها به ترتیب امتیاز؛ اگر یکی بسته بود یا قیمتش قابل اتکا نبود، سراغ بعدی می‌رود
۵. برنامه مراجعه: زمان باز بودن، مسیر داخل پاساژ، راه ارتباط و پیام آماده
۶. اقلام مکمل موجود در همان مغازه برای خرید یکجا

هیچ داده‌ای ساخته نمی‌شود: پاسخ فروشنده‌ها شبیه‌سازی از داده‌های ثبت‌شده است و همین برچسب را دارد.
"""

from __future__ import annotations

import re
import sqlite3

from .agent import follow_up
from .algorithms.geo import distance_km
from .algorithms.hours import common_open_window, hours_status
from .algorithms.imwp import parse_mall_address
from .algorithms.recommend import rank_offers
from .algorithms.textutil import days_since, to_fa_digits
from .nlu import extract, local_extract
from .search import OFFER_COLUMNS, offer_matches, search_products

# عبارت‌های فرمان به ایجنت که جزو نام کالا نیستند
MISSION_PHRASES = (
    "برای همین کالا", "برای این کالا", "همین کالا", "این کالا", "همین محصول", "این محصول", "همینو", "اینو",
    "برام", "برای من", "واسم", "پیدا کن", "پیداش کن", "پیدا کنید", "هماهنگ کن", "هماهنگش کن", "هماهنگ کنید", "هماهنگ",
    "رزرو کن", "رزرو", "بخرم", "بخر", "بگیرم", "بگیر", "میخوام", "می‌خوام", "می‌خواهم", "میخواهم", "لطفا", "لطفاً",
    "بگرد", "دنبال", "ماموریت", "مأموریت", "ایجنت", "کن", "یه", "یک دونه", "و",
)
_PHRASE_RE = re.compile(r"(?:^|\s)(?:" + "|".join(sorted(map(re.escape, MISSION_PHRASES), key=len, reverse=True)) + r")(?=\s|$|[،,.!؟?])")
FLAG_KEYS = ("place", "budget_min", "budget_max", "provider", "credit", "open_now", "near", "cheapest")
MAX_FOLLOW_UPS = 3
NOTICE = "پاسخ فروشنده‌ها شبیه‌سازی از داده‌های ثبت‌شده در ترب است؛ با فروشنده واقعی تماس گرفته نشده."


def _fa_toman(n) -> str:
    return f"{to_fa_digits(f'{int(n):,}')} تومان"


def _fa_km(km) -> str:
    if km is None:
        return ""
    if km < 1:
        return f"{to_fa_digits(int(round(km * 1000, -1)))} متر"
    return f"{to_fa_digits(f'{km:.1f}').replace('.', '٫')} کیلومتر"


def clean_mission_text(text: str) -> str:
    cleaned = text
    for _ in range(3):  # عبارت‌های پشت‌سرهم («برام پیدا کن و هماهنگ کن»)
        cleaned = _PHRASE_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _describe(slots: dict, user_known: bool) -> str:
    parts = []
    if slots.get("place"):
        parts.append(f"محدوده: {slots['place']}")
    if slots.get("budget_max") and slots.get("budget_min"):
        parts.append(f"بودجه: {_fa_toman(slots['budget_min'])} تا {_fa_toman(slots['budget_max'])}")
    elif slots.get("budget_max"):
        parts.append(f"بودجه: تا {_fa_toman(slots['budget_max'])}")
    if slots.get("credit") or slots.get("provider"):
        parts.append("فقط فروشگاه‌های اقساطی")
    if slots.get("open_now"):
        parts.append("الان باز")
    if slots.get("near"):
        parts.append("نزدیک شما" if user_known else "نزدیک شما (موقعیت تعیین نشده)")
    return "؛ ".join(parts)


BRAND_WORDS = ("اپل", "آیفون", "سامسونگ", "شیائومی", "هواوی", "آنر", "نوکیا", "ریلمی", "وان پلاس", "موتورولا", "ال جی")


def _other_brand(candidate_title: str, base_title: str) -> bool:
    """لوازم جانبی برند دیگر (شارژر اپل برای گوشی سامسونگ) پیشنهاد نشود؛ لوازم بی‌برند مجازند."""
    named = [b for b in BRAND_WORDS if b in candidate_title]
    return bool(named) and not any(b in base_title for b in named)


def _step(key, title, status, detail, lines=None):
    return {"key": key, "title": title, "status": status, "detail": detail, "lines": lines or []}


def _offers_for(conn, product_id, filters, user_lat, user_lon):
    cols = OFFER_COLUMNS + ", s.name, s.payment_options, s.instagram, s.website_url"
    rows = conn.execute(f"""
        SELECT {cols} FROM offers o JOIN shops s ON o.shop_id = s.shop_id WHERE o.product_id = ?
    """, (product_id,)).fetchall()
    names = [c.strip().split(".")[-1] for c in cols.replace("\n", " ").split(",")]
    offers = []
    for r in rows:
        row = dict(zip(names, r))
        if not offer_matches(row, **filters):
            continue
        row["hours"] = hours_status(row["weekly_hours"])
        row["distance_km"] = distance_km(user_lat, user_lon, row["lat"], row["lon"])
        offers.append(row)
    return offers


def run_mission(conn: sqlite3.Connection, text: str, context: dict | None = None) -> dict:
    context = context or {}
    user_lat, user_lon = context.get("user_lat"), context.get("user_lon")
    user_known = user_lat is not None and user_lon is not None
    places = [r[0] for r in conn.execute("SELECT DISTINCT location_label FROM shops WHERE location_label IS NOT NULL")]
    steps = []

    # ۱. فهم درخواست
    cleaned = clean_mission_text(text)
    flags = local_extract(text, places)
    if cleaned:
        slots, source = extract(cleaned, places, None)
    else:
        # فقط فرمان («برام هماهنگ کن»): کالا از صفحه فعلی می‌آید
        slots, source = {**flags, "tokens": [], "optional": None, "category": None}, "local"
    for k in FLAG_KEYS:
        if not slots.get(k) and flags.get(k):
            slots[k] = flags[k]
    if not slots.get("place") and context.get("current_hub"):
        slots["place"] = context["current_hub"]
    tokens = slots.get("tokens") or []
    product_row = None
    if not tokens and context.get("active_product_id"):
        product_row = conn.execute(
            "SELECT product_id, persian_title, category_name FROM products WHERE product_id = ?",
            (context["active_product_id"],)).fetchone()
    if not tokens and not product_row:
        steps.append(_step("understand", "فهم درخواست", "bad", "نام کالا در درخواست پیدا نشد."))
        return {"type": "mission", "status": "failed", "goal": text, "steps": steps,
                "message": "بگویید چه کالایی لازم دارید؛ مثلاً «یه گوشی A55 قسطی نزدیک من پیدا کن و هماهنگ کن».",
                "suggested_prompts": ["یه گوشی A55 قسطی نزدیک من پیدا کن", "دریل شارژی تا ۵ میلیون در لاله زار", "ایرپاد پرو که الان باز باشه"]}

    query_label = slots.get("colloquial_label") or " ".join(tokens) or product_row[1]
    conditions = _describe(slots, user_known)
    steps.append(_step("understand", "فهم درخواست", "ok",
                       f"کالا: «{query_label}»" + (f"؛ {conditions}" if conditions else ""),
                       ["درک پیام: " + {"local": "الگوریتم محلی فارسی", "deterministic": "قواعد قطعی"}.get(source, "مدل زبانی")]))

    filters = {
        "place": slots.get("place"), "min_price": slots.get("budget_min"), "max_price": slots.get("budget_max"),
        "provider": slots.get("provider"), "credit": bool(slots.get("credit")), "open_now": bool(slots.get("open_now")),
    }

    # ۲. پیدا کردن کالا
    if product_row:
        product = {"product_id": product_row[0], "persian_title": product_row[1], "category_name": product_row[2]}
        steps.append(_step("search", "انتخاب کالا", "ok", f"همان کالای صفحه فعلی: «{product_row[1]}»"))
    else:
        found = search_products(conn, tokens, optional=slots.get("optional"), category=slots.get("category"), limit=5,
                                accessories="exclude", user_lat=user_lat, user_lon=user_lon, **filters)
        if not found and slots.get("category"):
            found = search_products(conn, tokens, optional=slots.get("optional"), limit=5, accessories="exclude",
                                    user_lat=user_lat, user_lon=user_lon, **filters)
        if not found:
            loose = search_products(conn, tokens, optional=slots.get("optional"), limit=1, accessories="exclude")
            reason = (f"«{query_label}» با این شرط‌ها ({conditions}) در هیچ فروشگاهی نیست، ولی بدون شرط‌ها هست."
                      if loose and conditions else f"«{query_label}» در فروشگاه‌های حضوری پیدا نشد.")
            steps.append(_step("search", "جستجوی کالا", "bad", reason))
            return {"type": "mission", "status": "failed", "goal": text, "steps": steps,
                    "message": reason + " شرط‌ها را کمتر کنید یا نام کوتاه‌تری بگویید.",
                    "suggested_prompts": [f"{query_label} بدون شرط اقساط", f"{query_label} در همه محدوده‌ها"] if conditions else []}
        if slots.get("cheapest"):
            found.sort(key=lambda p: p["min_price_toman"] or 0)
        product = found[0]
        others = [p["persian_title"] for p in found[1:3]]
        steps.append(_step("search", "جستجوی کالا", "ok",
                           f"{to_fa_digits(len(found))} کالای منطبق پیدا شد؛ «{product['persian_title']}» انتخاب شد "
                           f"({'ارزان‌ترین' if slots.get('cheapest') else 'مرتبط‌ترین'}، در {to_fa_digits(product['available_offline_shops_count'])} فروشگاه حضوری).",
                           [f"گزینه دیگر: {t}" for t in others]))

    # ۳. مقایسه فروشگاه‌ها
    offers = _offers_for(conn, product["product_id"], filters, user_lat, user_lon)
    if not offers:
        steps.append(_step("compare", "مقایسه فروشگاه‌ها", "bad", "فروشگاهی با قیمت معتبر و منطبق با شرط‌ها برای این کالا نیست."))
        return {"type": "mission", "status": "failed", "goal": text, "steps": steps,
                "message": "برای این کالا فروشگاه حضوری با قیمت معتبر پیدا نشد."}
    ranking = rank_offers([{
        "offer_id": o["offer_id"], "price_toman": o["price_toman"], "is_copy": o["is_copy"], "price_suspect": o["price_suspect"],
        "distance_km": o["distance_km"], "hours_state": o["hours"]["state"],
        "days_since_update": days_since(o["last_price_changed_at"]), "has_credit": bool(o.get("credit_providers")),
    } for o in offers])
    scores = (ranking or {}).get("scores", {})
    if slots.get("near") and user_known:
        offers.sort(key=lambda o: (o["distance_km"] is None, o["distance_km"] or 0))
    elif slots.get("cheapest"):
        offers.sort(key=lambda o: o["price_toman"])
    else:
        offers.sort(key=lambda o: -scores.get(o["offer_id"], 0))
    top = offers[:MAX_FOLLOW_UPS]
    steps.append(_step("compare", "مقایسه فروشگاه‌ها", "ok",
                       f"{to_fa_digits(len(offers))} فروشگاه با قیمت، " + ("فاصله از شما، " if user_known else "")
                       + "ساعت کاری و تازگی قیمت مقایسه شد"
                       + ("؛ مرتب بر اساس نزدیکی." if slots.get("near") and user_known else "؛ مرتب بر اساس قیمت." if slots.get("cheapest") else "."),
                       [f"{to_fa_digits(i + 1)}. {o['name']} — {_fa_toman(o['price_toman'])}"
                        + (f" · {_fa_km(o['distance_km'])}" if o["distance_km"] is not None else "")
                        + f" · {o['hours']['label']}" for i, o in enumerate(top)]))

    # ۴. پیگیری با فروشگاه‌ها به ترتیب؛ اولین فروشگاهی که می‌شود رفت انتخاب می‌شود
    # «بروید» بر «اول تماس بگیرید» مقدم است؛ پیگیری با اولین «بروید» تمام می‌شود
    attempts, chosen, chosen_fu = [], None, None
    for o in top:
        fu = follow_up(conn, o["offer_id"])
        if not fu:
            continue
        action = fu["decision"]["action"]
        mark = {"go": "✓", "call_first": "☎", "alternative": "✗"}[action]
        attempts.append(f"{mark} {o['name']}: {fu['decision']['label']} — {fu['steps'][0]['text']}")
        if action == "go":
            chosen, chosen_fu = o, fu
            break
        if action == "call_first" and chosen is None:
            chosen, chosen_fu = o, fu
    if chosen is None:
        chosen = top[0]
        chosen_fu = follow_up(conn, chosen["offer_id"])
        attempts.append("هیچ‌کدام الان پاسخ‌گو نیستند؛ بهترین گزینه برای زمان باز بودن برنامه‌ریزی شد.")
    status = "ok" if chosen_fu["decision"]["action"] == "go" else "warn"
    steps.append(_step("follow_up", "پیگیری با فروشگاه‌ها", status,
                       f"با {to_fa_digits(sum(1 for a in attempts if a[0] in '✓☎✗'))} فروشگاه پیگیری شد؛ "
                       f"«{chosen['name']}» انتخاب شد ({chosen_fu['decision']['label']}).", attempts))

    # ۵. برنامه مراجعه
    parsed = parse_mall_address(chosen["address"], chosen["location_label"])
    window = common_open_window([chosen["weekly_hours"]], subject="مغازه باز است")
    if not window["found"] and not window["known_count"]:
        window["label"] = "ساعت کاری این مغازه ثبت نشده؛ پیش از رفتن تماس بگیرید"
    plan_lines = [window["label"]]
    if chosen["distance_km"] is not None:
        plan_lines.append(f"فاصله از شما: {_fa_km(chosen['distance_km'])}")
    plan_lines += parsed.get("verbal_guide") or []
    steps.append(_step("plan", "برنامه مراجعه", "ok" if window["found"] else "warn",
                       f"{parsed['mall_name']}" + (f"، {parsed['floor_label']}" if parsed.get("floor_known") else "")
                       + (f"، {parsed['unit_number']}" if parsed.get("unit_number") else ""), plan_lines))

    # ۶. خرید یکجا: اقلام مکمل در همان مغازه
    extras = []
    try:
        from .algorithms.ai_product_intelligence import find_grounded_complementary_items
        base = {"product_id": product["product_id"], "title": product["persian_title"],
                "category_name": product.get("category_name"), "price": chosen["price_toman"]}
        shop = {"shop_id": chosen["shop_id"], "name": chosen["name"], "address": chosen["address"],
                "location_label": chosen["location_label"]}
        comps, _ = find_grounded_complementary_items(conn, base, shop, limit=12)
        extras = [{"product_id": c["product_id"], "title": c["title"], "price_toman": c["price_toman"]}
                  for c in comps if c.get("is_same_shop") and not _other_brand(c["title"], product["persian_title"])][:3]
    except Exception:
        extras = []
    if extras:
        steps.append(_step("extras", "خرید یکجا", "ok", f"همین مغازه {to_fa_digits(len(extras))} قلم مکمل هم دارد.",
                           [f"{e['title']} — {_fa_toman(e['price_toman'])}" for e in extras]))

    alternatives = [o for o in offers if o["offer_id"] != chosen["offer_id"]][:3]
    shop_public = {
        "shop_id": chosen["shop_id"], "name": chosen["name"], "address": chosen["address"],
        "location_label": chosen["location_label"], "parsed_address": parsed, "hours": chosen["hours"],
        "lat": chosen["lat"], "lon": chosen["lon"],
    }
    decision = chosen_fu["decision"]
    summary = (f"«{product['persian_title']}» را از **{chosen['name']}** ({parsed['mall_name']}) با "
               f"**{_fa_toman(chosen['price_toman'])}** بخرید. {decision['label']}؛ {window['label']}.")
    return {
        "type": "mission",
        "status": "done" if decision["action"] == "go" else "partial",
        "goal": text,
        "nlu": source,
        "steps": steps,
        "message": summary,
        "notice": NOTICE,
        "result": {
            "product": {"product_id": product["product_id"], "title": product["persian_title"]},
            "offer_id": chosen["offer_id"],
            "price_toman": chosen["price_toman"],
            "distance_km": chosen["distance_km"],
            "shop": shop_public,
            "decision": decision,
            "visit": window,
            "contact_channels": chosen_fu.get("contact_channels", []),
            "chat_draft_text": chosen_fu.get("chat_draft_text"),
            "extras": extras,
            "alternatives": [{
                "shop_id": o["shop_id"], "name": o["name"], "price_toman": o["price_toman"],
                "distance_km": o["distance_km"], "hours": o["hours"], "lat": o["lat"], "lon": o["lon"],
                "location_label": o["location_label"],
            } for o in alternatives],
        },
        "state": {"active_product_id": product["product_id"], "active_shop_id": chosen["shop_id"],
                  "active_product_title": product["persian_title"]},
        "suggested_prompts": ["کدوم مغازه جنس بهتر داره", "آیا همین مغازه این لوازم جانبی رو یکجا داره؟", "اقلام مکمل برای تکمیل این خرید چیه؟"],
    }
