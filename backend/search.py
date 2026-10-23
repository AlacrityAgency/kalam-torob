"""
موتور جستجوی مشترک کَلَم (API جستجو و دستیار گفتگو از همین ماژول استفاده می‌کنند).

- FTS5 روی توکن کامل (پیشوندی) تا «بای» با «موبایل» تطبیق نخورد.
- مترادف‌ها دوطرفه‌اند: «کتانی» و «کتونی» هر دو هر دو املا را پیدا می‌کنند.
- فیلترهای شرایط خرید روی آفرها اعمال می‌شوند: محدوده/پاساژ، بودجه، اقساط، تازگی قیمت،
  ساعت کاری مشخص، الان باز، و حذف آفرهای کپی/قیمت پرت از «کمترین قیمت».
"""

from __future__ import annotations

import re
import sqlite3
from typing import Iterable

from .algorithms.geo import distance_km
from .algorithms.hours import hours_status
from .algorithms.textutil import days_since

# املاهای چندکلمه‌ای و اصطلاحات منطقه‌ای/محاوره‌ای پیش از توکن‌سازی یکسان می‌شوند
PHRASE_NORMALIZE = {
    "لپتاپ": "لپ تاپ",
    "پاوربانک": "پاور بانک",
    "اسنپپی": "اسنپ پی",
    "تربپی": "ترب پی",
    "دیجیپی": "دیجی پی",
    "مداربسته": "مدار بسته",
    # اصطلاحات منطقه‌ای، شهرستانی و خطاهای آوایی ابزار و ساختمان
    "سنگ جت": "مینی فرز",
    "مینی سنگ": "مینی فرز",
    "سنگ فرث": "سنگ فرز",
    "پیکور": "چکش تخریب",
    "هیلتی": "بتن کن",
    "موتور جوش": "اینورتر جوشکاری",
    "ترانس جوش": "اینورتر جوشکاری",
    "سیم راویز": "سیم مفتول",
    "سیم رابیتس": "سیم مفتول",
    "آچار رنگی": "آچار رینگی",
    "آچار جقجقه": "آچار جغجغه",
    "آچار تق تقی": "آچار جغجغه",
    "آچار شلاغی": "آچار شلاقی",
    "گازنبر": "گاز انبر",
    "گازانبر": "گاز انبر",
    # اصطلاحات عامیانه دیجیتال، موبایل و صدا
    "گوشی گوشکوبی": "گوشی نوکیا",
    "گوشکوبی": "گوشی نوکیا",
    "دگمه ای": "دکمه ای",
    "دوکمه ای": "دکمه ای",
    "کله شارژر": "شارژر دیواری",
    "سر شارژر": "شارژر دیواری",
    "سری شارژر": "شارژر دیواری",
    "کول دیسک": "فلش مموری",
    "کولدیسک": "فلش مموری",
    "هنزفری": "هندزفری",
    "هنزفیری": "هندزفری",
    "هندزفیری": "هندزفری",
}

# گروه‌های مترادف تک‌کلمه‌ای (هر عضو همه اعضا را پیدا می‌کند)
SYNONYM_GROUPS = [
    ["کتانی", "کتونی"],
    ["ایرپاد", "ایرپادز", "airpods", "airpod"],
    ["آیفون", "ایفون", "iphone"],
    ["سامسونگ", "samsung"],
    ["شیائومی", "شیامی", "xiaomi", "redmi", "ردمی"],
    ["هندزفری", "هنزفری", "هندسفری", "هنزفیری", "هندزفیری"],
    ["موبایل", "گوشی"],
    ["رینگی", "رنگی"],
    ["جغجغه", "جقجقه"],
    ["شلاقی", "شلاغی"],
]
_SYNONYMS = {w: group for group in SYNONYM_GROUPS for w in group}

FRESH_DAYS = 14

# لوازم جانبی معمولاً عنوانی مثل «کاور ... مناسب برای گوشی ...» دارند. وقتی کاربر خود کالا را
# می‌خواهد (کلمه لوازم جانبی در جستجو نیست)، این‌ها بعد از کالای اصلی می‌آیند یا حذف می‌شوند.
ACCESSORY_WORDS = {
    "کاور", "قاب", "محافظ", "گلس", "شارژر", "کابل", "هولدر", "کیف", "بند", "لوازم", "جانبی", "باتری",
    "آداپتور", "اداپتور", "کفی", "جوراب", "مته", "پایه", "نگهدارنده", "شاسی", "فلت", "برد", "تاچ",
    "ال‌سی‌دی", "السی‌دی", "لنز", "استیکر", "برچسب", "سرسیم", "کابلشو", "هولدر",
    "زیرلیوانی", "زیر لیوانی", "زیر استکانی", "نعلبکی", "استند",
}

ACCESSORY_CATEGORIES = {
    "کیف و کاور گوشی", "محافظ صفحه نمایش گوشی", "باتری گوشی موبایل", "پایه نگهدارنده گوشی و تبلت",
    "شارژر گوشی", "کابل و اتصالات گوشی و تبلت", "قاب، شاسی و درب گوشی", "محافظ لنز دوربین گوشی",
    "تاچ و ال سی دی گوشی و تبلت", "فلت و برد گوشی", "آنتن گوشی و تبلت", "آی سی گوشی و تبلت",
    "بازر و بلندگو گوشی و تبلت", "جک و سوکت گوشی و تبلت", "دوربین گوشی و تبلت", "دکمه پاور گوشی و تبلت",
    "سایر قطعات گوشی و تبلت", "سنسور اثر انگشت گوشی", "شیشه دوربین گوشی و تبلت", "میکروفون گوشی و تبلت",
    "ویبره گوشی", "گلس تعمیراتی گوشی و تبلت", "سایر لوازم جانبی موبایل و تبلت",
    "باتری لپ تاپ", "شارژر لپ تاپ", "کیف و کاور لپ تاپ", "محافظ صفحه نمایش لپ تاپ",
    "پایه نگهدارنده مانیتور و لپ تاپ", "کابل شارژ لپ تاپ", "سایر لوازم جانبی کامپیوتر و لپ تاپ",
    "شارژر ساعت هوشمند", "لوازم جانبی ساعت معمولی و هوشمند", "گلس و محافظ ساعت",
    "نعلبکی و زیر لیوانی", "استند و جای لیوان", "جا لیوانی و لیوان خودرو",
}


MAIN_DEVICE_WORDS = {
    "ساعت", "واچ", "watch", "مچبند", "مچ بند", "گوشی", "موبایل", "موبايل", "تبلت",
    "لپتاپ", "لپ تاپ", "کامپیوتر", "دریل", "فرز", "مینی فرز", "بتن کن",
    "اینورتر", "پمپ", "دوربین"
}

PRIMARY_DEVICE_CATEGORIES = {
    "ساعت مچی عقربه‌ ای و دیجیتالی", "ساعت و مچ بند هوشمند",
    "ساعت دیواری٬ رومیزی و تزئینی", "ساعت و تقویم دیجیتال",
    "ساعت آموزشی", "ساعت انگشتری", "ساعت جیبی و گردنبندی",
    "گوشی موبایل", "تبلت", "لپ تاپ", "دوربین دیجیتال",
    "دریل و پیچ گوشتی برقی", "فرز و مینی فرز", "اینورتر جوشکاری",
}

SEARCH_STOPWORDS = {
    "با", "برای", "واسه", "در", "از", "به", "رو", "را", "که", "و", "یا", "تا", "توی", "تو", "داخل", "همراه"
}


def is_accessory(title: str | None, category: str | None) -> bool:
    norm_cat = normalize_text(category or "")
    if category in ACCESSORY_CATEGORIES or any(sub in norm_cat for sub in (
        "کیف و کاور", "محافظ صفحه", "محافظ لنز", "باتری", "پایه نگهدارنده",
        "شارژر", "کابل و اتصالات", "قاب، شاسی", "تاچ و ال سی دی", "لوازم جانبی", "قطعات",
        "نعلبکی و زیر لیوانی", "استند و جای لیوان", "چسب", "خشاب", "فلت", "برد", "ویبره",
        "سوکت", "بلندگو", "اسپیکر", "تعمیرات", "دوربین گوشی", "ابزار تعمیر ساعت", "جعبه ساعت"
    )):
        return True

    norm_title = normalize_text(title or "")
    title_words = norm_title.split()

    # در دسته‌های اصلی کالا، محصول جانبی نیست مگر صریحاً عنوان با کلمه جانبی شروع شود یا «مناسب برای» داشته باشد
    if category in PRIMARY_DEVICE_CATEGORIES:
        if title_words and title_words[0] in (
            "بند", "قاب", "کاور", "گلس", "شارژر", "باتری", "کابل", "هولدر", "محافظ", "برچسب", "استیکر"
        ):
            return True
        if "مناسب برای" in norm_title or "مناسب " in norm_title:
            return True
        return False

    title_word_set = set(title_words)
    if any(w in title_word_set for w in (
        "کاور", "قاب", "محافظ", "گلس", "لوازم", "باتری", "هولدر", "شارژر", "کابل",
        "آداپتور", "اداپتور", "شاسی", "فلت", "برچسب", "استیکر",
        "زیرلیوانی", "نعلبکی", "چسب", "خشاب", "ویبره", "سوکت", "اسپیکر"
    )):
        return True

    if "بند" in title_word_set:
        idx_band = title_words.index("بند")
        has_device_before = any(w in ("ساعت", "واچ", "مچبند", "smart") for w in title_words[:idx_band])
        if not has_device_before:
            return True

    if any(sub in norm_title for sub in ("زیر لیوانی", "زیرلیوانی", "زیر استکانی", "جا لیوانی", "استند لیوان")):
        return True

    if "مناسب " in norm_title or "مناسب برای" in norm_title:
        return True
    if "پایه نگهدارنده" in norm_title:
        return True

    return False


RAW_MATERIALS = {"مفتول", "سیم", "لوله", "ورق", "میلگرد", "پروفیل", "پیچ", "مهره"}
TOOL_ACTION_WORDS = {
    "انبر", "قیچی", "خم کن", "خم‌کن", "مفتول بر", "مفتول‌بر", "لوله‌بر", "لوله بر",
    "ورق بر", "ورق‌بر", "سیم چین", "سیم‌چین", "سیم لخت کن", "سیم‌لخت‌کن",
    "پیچ گوشتی", "پیچ‌گوشتی", "آچار"
}
JEWELRY_CATEGORIES = {
    "گوشواره", "دستبند و بنگل", "گردنبند", "انگشتر", "پلاک و زنجیر", "سنجاق سینه", "پابند"
}
TOOL_CATEGORIES = {
    "انبر دست و دم باریک", "قیچی ورق و مفتول بر", "سیم چین و کف چین", "سیم لخت‌کن و پرس کابل", "انبر قفلی", "انبر کلاغی"
}
BABY_CATEGORIES = {"دندان گیر کودک و نوزاد", "جغجغه نوزاد", "اسباب بازی", "عروسک", "جوراب نوزاد", "لباس نوزادی"}
TOOL_INTENT_WORDS = {"آچار", "بکس", "ابزار", "جغجغه", "فرز", "دریل", "انبر", "پیچ گوشتی", "اینورتر", "پیکور", "جوشکاری", "سنگ جت"}


def is_material_tool_conflict(tokens: list[str], title: str | None, category: str | None) -> bool:
    """
    جلوگیری از خطاهای معنایی و جابجایی دسته‌ها:
    ۱. نمایش ابزارهای برش/خم‌کاری یا زیورآلات به جای ماده اولیه (مفتول/سیم/لوله)
    ۲. نمایش جغجغه و دندان‌گیر نوزاد به جای آچار و ابزار جغجغه‌ای مکانیکی
    """
    token_set = set(tokens)
    cat = category or ""
    cat_norm = normalize_text(cat)
    title_norm = normalize_text(title or "")

    # تفکیک ابزار جغجغه از جغجغه نوزاد و اسباب‌بازی
    if (token_set & TOOL_INTENT_WORDS) and not (token_set & {"کودک", "نوزاد", "بچه", "اسباب بازی", "عروسک", "دندانگیر"}):
        if cat in BABY_CATEGORIES or any(b in cat_norm for b in ("نوزاد", "کودک", "اسباب بازی", "عروسک", "دندان گیر")):
            return True

    has_mat = any(m in token_set for m in RAW_MATERIALS)
    if not has_mat:
        return False

    # زیورآلات طرح مفتول یا سیم
    if (cat in JEWELRY_CATEGORIES or any(j in cat_norm for j in ("گوشواره", "دستبند", "گردنبند", "انگشتر", "پلاک"))) and not (token_set & {"گوشواره", "دستبند", "گردنبند", "انگشتر", "پلاک", "طلا", "نقره"}):
        return True

    # ابزارهای برش و شکل‌دهی ماده
    if cat in TOOL_CATEGORIES or any(tw in cat_norm for tw in ("انبر", "قیچی", "سیم چین", "پرس")):
        if not (token_set & {"انبر", "قیچی", "سیم چین", "پرس", "ابزار"}):
            return True

    for tw in TOOL_ACTION_WORDS:
        if tw in title_norm and tw not in token_set:
            return True

    return False


def wants_accessory(tokens: list[str]) -> bool:
    """
    بررسی اینکه آیا کاربر واقعاً قطعه یا لوازم جانبی می‌خواهد یا کالای اصلی با یک مشخصه/متعلقات:
    - «بند ساعت» یا «بند اپل واچ» یا «قاب گوشی»: کلمه جانبی قبل از کالا آمده => لوازم جانبی (True)
    - «بند چرمی» یا «کاور ژله ای»: فقط کلمه جانبی آمده => لوازم جانبی (True)
    - «ساعت بند چرمی» یا «گوشی با قاب»: کالای اصلی قبل از کلمه جانبی آمده => کالای اصلی (False)
    """
    acc_indices = [i for i, t in enumerate(tokens) if t in ACCESSORY_WORDS]
    if not acc_indices:
        return False
    dev_indices = [i for i, t in enumerate(tokens) if t in MAIN_DEVICE_WORDS]
    if not dev_indices:
        return True
    return min(acc_indices) < min(dev_indices)


def normalize_text(text: str) -> str:
    text = (text or "").replace("\u064a", "\u06cc").replace("\u0643", "\u06a9").replace("\u200c", " ").lower()
    for k, v in PHRASE_NORMALIZE.items():
        text = text.replace(k, v)
    return text


def tokenize(text: str, stopwords: Iterable[str] = (), max_tokens: int = 6) -> list[str]:
    stop = set(stopwords)
    # \w حروف فارسی را هم می‌گیرد و برخلاف بازه یونیکد عربی، «؟» و «،» را جزو کلمه نمی‌کند
    tokens = re.findall(r"\w+", normalize_text(text))
    return [t for t in tokens if t not in stop and len(t) > 1][:max_tokens]


def _group(token: str) -> str:
    variants = _SYNONYMS.get(token, [token])
    # کوتیشن هر توکن را از نحو FTS5 ایمن می‌کند
    # برای اعداد (مثل ۲۵ یا ۱۸) و شناسه‌های عددی از * استفاده نمی‌شود تا با ۲۵۶ یا ۲۵۰۰ تطابق کاذب ندهد
    parts = []
    for v in variants:
        if v.isdigit():
            parts.append(f'"{v}"')
        else:
            parts.append(f'"{v}"*')
    return "(" + " OR ".join(parts) + ")"


DESCRIPTIVE_MODIFIERS = {"فلزی", "پلاستیکی", "شیشه", "شیشه‌ای", "چوبی", "روغنی", "خشک", "خوب", "اصل", "نو", "رنگی"}


def fts_ranked_ids(conn: sqlite3.Connection, tokens: list[str], optional: list[str] | None = None,
                   category: str | None = None, limit: int = 400) -> list[str]:
    """
    شناسه کالاها به ترتیب ارتباط. اول همه توکن‌ها (+ حداقل یکی از توکن‌های اختیاری)،
    بعد فقط توکن‌های اصلی، و در آخر هر توکن (OR).
    اگر category مشخص شده باشد، ابتدا کوئری محدود به دسته‌بندی اولویت داده می‌شود.
    """
    if not tokens:
        return []
    required = " AND ".join(_group(t) for t in tokens)
    attempts = []
    
    # در صورت وجود دسته‌بندی مشخص، ابتدا جستجوی محدود به آن دسته‌بندی
    if category:
        cat_esc = category.replace('"', '')
        cat_filter = f' AND (category_name : "{cat_esc}")'
        if optional:
            attempts.append(f"{required} AND (" + " OR ".join(_group(t) for t in optional) + f"){cat_filter}")
        attempts.append(f"{required}{cat_filter}")

    # سپس جستجوی عمومی بدون محدودیت FTS دسته
    if optional:
        attempts.append(f"{required} AND (" + " OR ".join(_group(t) for t in optional) + ")")
    attempts.append(required)

    # اگر صفات توصیفی عمومی در کوئری است (مثل «مفتول فلزی»)، جستجو بدون صفت را امتحان کن
    core_tokens = [t for t in tokens if t not in DESCRIPTIVE_MODIFIERS]
    if core_tokens and len(core_tokens) < len(tokens):
        attempts.append(" AND ".join(_group(t) for t in core_tokens))

    # برای کوئری‌های ۳ کلمه‌ای یا بیشتر، اگر همه تطابق نداشتند، تطابق حداقل (N-1) کلمه را بسنج
    # در صورت وجود توکن مدل/عدد (مثل ۲۵ یا ۱۱ یا a54)، آن توکن حتماً باید در ترکیب باشد
    model_tokens = [t for t in tokens if re.search(r"\d", t)]
    if len(tokens) >= 3:
        for i in range(len(tokens)):
            sub = [t for j, t in enumerate(tokens) if j != i]
            if model_tokens and not all(mt in sub for mt in model_tokens):
                continue
            sub_q = " AND ".join(_group(t) for t in sub)
            if sub_q not in attempts:
                attempts.append(sub_q)

    cursor = conn.cursor()
    for query in attempts:
        try:
            cursor.execute(
                "SELECT product_id FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT ?;",
                (query, limit),
            )
        except sqlite3.Error:
            continue
        ids = [r[0] for r in cursor.fetchall()]
        if ids:
            return ids
    return []


_HOURS_CACHE: dict = {}


def shop_hours(shop_id: str, raw) -> dict:
    """وضعیت ساعت کاری با کش کوتاه‌مدت (وضعیت «الان باز» هر دقیقه عوض می‌شود)"""
    from time import monotonic

    hit = _HOURS_CACHE.get(shop_id)
    if hit and monotonic() - hit[0] < 60:
        return hit[1]
    status = hours_status(raw)
    if len(_HOURS_CACHE) > 20000:
        _HOURS_CACHE.clear()
    _HOURS_CACHE[shop_id] = (monotonic(), status)
    return status


def offer_matches(row: dict, *, place=None, min_price=None, max_price=None, provider=None, credit=False,
                  fresh=False, hours_known=False, open_now=False, include_copies=False) -> bool:
    """آیا یک آفر (ردیف offers+shops) با شرایط خرید کاربر جور است؟"""
    price = row.get("price_toman")
    if price is None:
        return False
    if not include_copies and (row.get("is_copy") or row.get("price_suspect")):
        return False
    if min_price and price < min_price:
        return False
    if max_price and price > max_price:
        return False
    if place and not place_matches(place, row.get("location_label"), row.get("address")):
        return False
    providers = (row.get("credit_providers") or "").split(",") if row.get("credit_providers") else []
    if provider and provider not in providers:
        return False
    if credit and not providers:
        return False
    if fresh:
        age = days_since(row.get("last_price_changed_at"))
        if age is None or age > FRESH_DAYS:
            return False
    if hours_known and not row.get("hours_known"):
        return False
    if open_now and shop_hours(row["shop_id"], row.get("weekly_hours"))["state"] != "open":
        return False
    return True


def place_matches(place: str, location_label, address) -> bool:
    """محدوده می‌تواند نام هاب (location_label) یا نام پاساژ داخل آدرس باشد («چارسو»)"""
    if not place:
        return True
    if location_label and location_label == place:
        return True
    return bool(address) and normalize_text(place) in normalize_text(address)


OFFER_COLUMNS = """
    o.product_id, o.offer_id, o.price_toman, o.last_price_changed_at, o.is_copy, o.price_suspect,
    s.shop_id, s.location_label, s.address, s.credit_providers, s.hours_known, s.weekly_hours, s.lat, s.lon
"""


def search_products(conn: sqlite3.Connection, tokens: list[str], *, optional: list[str] | None = None,
                    category: str | None = None, limit: int = 25, accessories: str = "after",
                    user_lat: float | None = None, user_lon: float | None = None, max_km: float | None = None,
                    **filters) -> list[dict]:
    """
    جستجوی کالا با شرایط خرید. خروجی به ترتیب ارتباط است؛ min_price از آفرهای سالم
    (غیر کپی، قیمت غیرپرت) و منطبق با فیلترها محاسبه می‌شود.
    accessories: «after» لوازم جانبی را بعد از کالای اصلی می‌آورد، «exclude» حذفشان می‌کند
    (هر دو فقط وقتی کاربر خودش دنبال لوازم جانبی نیست).
    """
    ranked = fts_ranked_ids(conn, tokens, optional, category=category)
    if not ranked:
        return []
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(ranked))
    cursor.execute(f"""
        SELECT {OFFER_COLUMNS}
        FROM offers o JOIN shops s ON o.shop_id = s.shop_id
        WHERE o.product_id IN ({placeholders}) AND o.price_toman IS NOT NULL
    """, ranked)
    cols = [d[0] for d in cursor.description]

    agg: dict[str, dict] = {}
    for values in cursor.fetchall():
        row = dict(zip(cols, values))
        if not offer_matches(row, **filters):
            continue
        dist = distance_km(user_lat, user_lon, row["lat"], row["lon"])
        if max_km and (dist is None or dist > max_km):
            continue
        a = agg.setdefault(row["product_id"], {"prices": [], "shops": set(), "nearest": None})
        a["prices"].append(row["price_toman"])
        a["shops"].add(row["shop_id"])
        if dist is not None and (a["nearest"] is None or dist < a["nearest"]):
            a["nearest"] = dist
    if not agg:
        return []

    ids = [pid for pid in ranked if pid in agg]
    ph = ",".join("?" * len(ids))
    params = list(ids)
    cat_cond = ""
    if category:
        cat_cond = " AND category_name = ?"
        params.append(category)
    cursor.execute(f"""
        SELECT product_id, persian_title, category_name, brand_name, image_urls
        FROM products WHERE product_id IN ({ph}){cat_cond}
    """, params)
    info = {r[0]: r for r in cursor.fetchall()}

    if not wants_accessory(tokens):
        main = [
            pid for pid in ids
            if pid in info
            and not is_accessory(info[pid][1], info[pid][2])
            and not is_material_tool_conflict(tokens, info[pid][1], info[pid][2])
        ]
        extra = [] if accessories == "exclude" else [pid for pid in ids if pid in info and pid not in set(main)]
        ids = main + extra
    else:
        acc = [
            pid for pid in ids
            if pid in info
            and is_accessory(info[pid][1], info[pid][2])
        ]
        extra = [pid for pid in ids if pid in info and pid not in set(acc)]
        ids = acc + extra

    results = []
    seen_titles = set()
    for pid in ids:
        if pid not in info:
            continue
        p = info[pid]
        clean_title = normalize_text(p[1])
        if clean_title in seen_titles:
            continue
        seen_titles.add(clean_title)
        a = agg[pid]
        results.append({
            "product_id": pid,
            "persian_title": p[1],
            "category_name": p[2],
            "brand_name": p[3],
            "image_url": p[4],
            "min_price_toman": min(a["prices"]),
            "max_price_toman": max(a["prices"]),
            "available_offline_shops_count": len(a["shops"]),
            "nearest_km": round(a["nearest"], 2) if a["nearest"] is not None else None,
        })
        if len(results) >= limit:
            break
    return results
