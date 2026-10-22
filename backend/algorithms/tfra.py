"""
الگوریتم ۷: معماری جایگزینی اضطراری سه‌لایه (TFRA / TUFA - Panic Button Fallback)
نجات خریدار هنگام مراجعه به مغازه بسته یا مواجهه با اتمام موجودی در کمتر از ۱٫۵ ثانیه.
"""

import math

from .imwp import parse_mall_address

# سقف کاندیداهای بررسی‌شده؛ لایه‌بندی پس از خواندن همه انجام می‌شود تا مغازه‌های نزدیک اما گران‌تر حذف نشوند
MAX_CANDIDATES = 500


def _distance_km(lat1, lon1, lat2, lon2):
    """فاصله هاورساین بین دو نقطه (کیلومتر)؛ اگر مختصات ناقص باشد None."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _in_same_mall(base_parsed, base_hub, cand_parsed, cand_hub):
    if base_parsed["mall_detected"] and cand_parsed["mall_detected"]:
        return base_parsed["mall_name"] == cand_parsed["mall_name"]
    # اگر نام پاساژ از آدرس درنیامد، فقط هم‌هاب بودن معتبر است (نه حضور کلمه «تهران» در آدرس)
    return bool(base_hub) and base_hub == cand_hub


def find_emergency_fallbacks(db_conn, product_id: str, failed_shop_id: str):
    """
    یافتن فوری مغازه‌های جایگزین در ۳ لایه:
    لایه ۱: همان طبقه همان پاساژ
    لایه ۲: طبقات دیگر همان مجتمع تجاری
    لایه ۳: سایر راسته‌ها، به ترتیب نزدیکی جغرافیایی
    """
    cursor = db_conn.cursor()

    # دریافت اطلاعات مغازه مبدأ
    cursor.execute("""
    SELECT shop_id, name, address, location_label, lat, lon
    FROM shops WHERE shop_id = ?
    """, (failed_shop_id,))
    base_shop = cursor.fetchone()
    if not base_shop:
        return {"error": "فروشگاه مبدأ یافت نشد."}

    sid, sname, saddr, sloc, slat, slon = base_shop
    base_parsed = parse_mall_address(saddr, sloc)
    base_floor = base_parsed["floor_level"]

    # جستجوی تمام مغازه‌های دیگر دارای این محصول با قیمت معتبر
    cursor.execute("""
    SELECT s.shop_id, s.name, s.address, s.location_label, s.payment_options, s.contacts,
           o.price_toman, o.warranty, o.last_price_changed_at, s.lat, s.lon
    FROM offers o
    JOIN shops s ON o.shop_id = s.shop_id
    WHERE o.product_id = ? AND s.shop_id != ? AND o.price_toman IS NOT NULL
    ORDER BY o.price_toman ASC
    LIMIT ?;
    """, (product_id, failed_shop_id, MAX_CANDIDATES))
    candidates = cursor.fetchall()

    layer1_same_floor = []
    layer2_same_mall = []
    layer3_same_hub = []
    seen_shops = set()

    for c in candidates:
        csid, cname, caddr, cloc, cpay, ccontacts, price, warranty, last_ch, clat, clon = c
        # هر مغازه یک بار (ارزان‌ترین پیشنهادش)
        if csid in seen_shops:
            continue
        seen_shops.add(csid)

        c_parsed = parse_mall_address(caddr, cloc)
        distance = _distance_km(slat, slon, clat, clon)

        candidate_obj = {
            "shop_id": csid,
            "name": cname,
            "address": caddr,
            "parsed_address": c_parsed,
            "price_toman": price,
            "warranty": warranty if warranty and warranty != "null" else None,
            "last_price_changed_at": last_ch,
            "payment_options": cpay,
            "distance_km": round(distance, 2) if distance is not None else None,
        }

        same_mall = _in_same_mall(base_parsed, sloc, c_parsed, cloc)
        same_floor = same_mall and base_parsed["floor_known"] and c_parsed["floor_known"] and c_parsed["floor_level"] == base_floor
        if same_floor:
            candidate_obj["tier"] = 1
            candidate_obj["tier_badge"] = "همین طبقه"
            layer1_same_floor.append(candidate_obj)
        elif same_mall:
            candidate_obj["tier"] = 2
            candidate_obj["tier_badge"] = f"همین پاساژ ({c_parsed['floor_label']})"
            layer2_same_mall.append(candidate_obj)
        else:
            candidate_obj["tier"] = 3
            candidate_obj["tier_badge"] = f"راسته {cloc}" if cloc else "راسته دیگر"
            layer3_same_hub.append(candidate_obj)

    # در لایه ۲ نزدیک‌ترین طبقه، در لایه ۳ نزدیک‌ترین مسافت اولویت دارد (قیمت معیار دوم)
    if base_parsed["floor_known"]:
        layer2_same_mall.sort(key=lambda x: (abs(x["parsed_address"]["floor_level"] - base_floor), x["price_toman"]))
    layer3_same_hub.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0, x["price_toman"]))

    # ترکیب نتایج با اولویت لایه‌ها
    recommended_fallbacks = (layer1_same_floor[:2] + layer2_same_mall[:2] + layer3_same_hub[:2])[:4]

    return {
        "failed_shop": {
            "shop_id": sid,
            "name": sname,
            "mall_name": base_parsed["mall_name"],
            "floor_label": base_parsed["floor_label"],
            "unit": base_parsed["unit_number"]
        },
        "layer1_count": len(layer1_same_floor),
        "layer2_count": len(layer2_same_mall),
        "layer3_count": len(layer3_same_hub),
        "recommended_fallbacks": recommended_fallbacks,
        "action_guide": (
            "نیازی به ترک مرکز خرید نیست! مغازه‌های هم‌طبقه و هم‌پاساژ این کالا را دارند."
            if (layer1_same_floor or layer2_same_mall) else
            "در این پاساژ جایگزینی نبود؛ نزدیک‌ترین فروشگاه‌ها در راسته‌های دیگر:"
            if layer3_same_hub else
            "فروشگاه دیگری این کالا را با قیمت ثبت‌شده ندارد."
        )
    }
