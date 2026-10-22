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

from .algorithms.hours import hours_status
from .algorithms.textutil import days_since

# املاهای چندکلمه‌ای پیش از توکن‌سازی یکسان می‌شوند
PHRASE_NORMALIZE = {
    "لپتاپ": "لپ تاپ",
    "پاوربانک": "پاور بانک",
    "اسنپپی": "اسنپ پی",
    "تربپی": "ترب پی",
    "دیجیپی": "دیجی پی",
    "مداربسته": "مدار بسته",
}

# گروه‌های مترادف تک‌کلمه‌ای (هر عضو همه اعضا را پیدا می‌کند)
SYNONYM_GROUPS = [
    ["کتانی", "کتونی"],
    ["ایرپاد", "ایرپادز", "airpods", "airpod"],
    ["آیفون", "ایفون", "iphone"],
    ["سامسونگ", "samsung"],
    ["شیائومی", "شیامی", "xiaomi", "redmi", "ردمی"],
    ["هندزفری", "هنزفری", "هندسفری"],
    ["موبایل", "گوشی"],
]
_SYNONYMS = {w: group for group in SYNONYM_GROUPS for w in group}

FRESH_DAYS = 14

# لوازم جانبی معمولاً عنوانی مثل «کاور ... مناسب برای گوشی ...» دارند. وقتی کاربر خود کالا را
# می‌خواهد (کلمه لوازم جانبی در جستجو نیست)، این‌ها بعد از کالای اصلی می‌آیند یا حذف می‌شوند.
ACCESSORY_WORDS = {"کاور", "قاب", "محافظ", "گلس", "شارژر", "کابل", "هولدر", "کیف", "بند", "لوازم", "جانبی", "باتری",
                   "آداپتور", "اداپتور", "کفی", "جوراب", "مته"}


def is_accessory(title: str | None, category: str | None) -> bool:
    text = normalize_text(f"{title or ''} {category or ''}")
    return "مناسب برای" in text or any(w in text.split() for w in ("کاور", "قاب", "محافظ", "گلس", "لوازم"))


def wants_accessory(tokens: list[str]) -> bool:
    return any(t in ACCESSORY_WORDS for t in tokens)


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
    return "(" + " OR ".join(f'"{v}"*' for v in variants) + ")"


def fts_ranked_ids(conn: sqlite3.Connection, tokens: list[str], optional: list[str] | None = None,
                   limit: int = 400) -> list[str]:
    """
    شناسه کالاها به ترتیب ارتباط. اول همه توکن‌ها (+ حداقل یکی از توکن‌های اختیاری)،
    بعد فقط توکن‌های اصلی، و در آخر هر توکن (OR).
    """
    if not tokens:
        return []
    required = " AND ".join(_group(t) for t in tokens)
    attempts = []
    if optional:
        attempts.append(f"{required} AND (" + " OR ".join(_group(t) for t in optional) + ")")
    attempts.append(required)
    if len(tokens) > 1:
        attempts.append(" OR ".join(_group(t) for t in tokens))

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
    s.shop_id, s.location_label, s.address, s.credit_providers, s.hours_known, s.weekly_hours
"""


def search_products(conn: sqlite3.Connection, tokens: list[str], *, optional: list[str] | None = None,
                    category: str | None = None, limit: int = 25, accessories: str = "after", **filters) -> list[dict]:
    """
    جستجوی کالا با شرایط خرید. خروجی به ترتیب ارتباط است؛ min_price از آفرهای سالم
    (غیر کپی، قیمت غیرپرت) و منطبق با فیلترها محاسبه می‌شود.
    accessories: «after» لوازم جانبی را بعد از کالای اصلی می‌آورد، «exclude» حذفشان می‌کند
    (هر دو فقط وقتی کاربر خودش دنبال لوازم جانبی نیست).
    """
    ranked = fts_ranked_ids(conn, tokens, optional)
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
        a = agg.setdefault(row["product_id"], {"prices": [], "shops": set()})
        a["prices"].append(row["price_toman"])
        a["shops"].add(row["shop_id"])
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
        main = [pid for pid in ids if pid in info and not is_accessory(info[pid][1], info[pid][2])]
        extra = [] if accessories == "exclude" else [pid for pid in ids if pid in info and pid not in set(main)]
        ids = main + extra

    results = []
    for pid in ids:
        if pid not in info:
            continue
        p = info[pid]
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
        })
        if len(results) >= limit:
            break
    return results
