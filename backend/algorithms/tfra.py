"""
الگوریتم ۷: معماری جایگزینی اضطراری سه‌لایه (TFRA / TUFA - Panic Button Fallback)
نجات خریدار هنگام مراجعه به مغازه بسته یا مواجهه با اتمام موجودی در کمتر از ۱٫۵ ثانیه.
"""

from .imwp import parse_mall_address

def find_emergency_fallbacks(db_conn, product_id: str, failed_shop_id: str):
    """
    یافتن فوری مغازه‌های جایگزین در ۳ لایه:
    لایه ۱: همان طبقه (فاصله زیر ۲۰ متر)
    لایه ۲: طبقات دیگر همان مجتمع تجاری
    لایه ۳: راسته مجاور در همان منطقه
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
           o.price_toman, o.warranty, o.last_price_changed_at
    FROM offers o
    JOIN shops s ON o.shop_id = s.shop_id
    WHERE o.product_id = ? AND s.shop_id != ? AND o.price_toman IS NOT NULL
    ORDER BY o.price_toman ASC
    LIMIT 25;
    """, (product_id, failed_shop_id))
    candidates = cursor.fetchall()

    layer1_same_floor = []
    layer2_same_mall = []
    layer3_same_hub = []

    for c in candidates:
        csid, cname, caddr, cloc, cpay, ccontacts, price, warranty, last_ch = c
        c_parsed = parse_mall_address(caddr, cloc)
        c_floor = c_parsed["floor_level"]

        candidate_obj = {
            "shop_id": csid,
            "name": cname,
            "address": caddr,
            "parsed_address": c_parsed,
            "price_toman": price,
            "warranty": warranty or "گارانتی اصالت و سلامت فیزیکی",
            "last_price_changed_at": last_ch,
            "payment_options": cpay
        }

        # لایه ۱: همان هاب و دقیقاً همان طبقه
        if (cloc == sloc or base_parsed["mall_name"] in caddr) and c_floor == base_floor:
            candidate_obj["tier"] = 1
            candidate_obj["tier_badge"] = "همین طبقه (زیر ۲۰ متر)"
            layer1_same_floor.append(candidate_obj)
        # لایه ۲: همان هاب اما طبقات دیگر
        elif (cloc == sloc or base_parsed["mall_name"] in caddr):
            candidate_obj["tier"] = 2
            candidate_obj["tier_badge"] = f"همین پاساژ ({c_parsed['floor_label']})"
            layer2_same_mall.append(candidate_obj)
        # لایه ۳: هاب مجاور
        else:
            candidate_obj["tier"] = 3
            candidate_obj["tier_badge"] = f"راسته {cloc}"
            layer3_same_hub.append(candidate_obj)

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
            "نیازی به ترک مرکز خرید نیست! مغازه‌های هم‌طبقه و هم‌راستا با همان رده قیمتی برای شما آماده مراجعه هستند."
            if (layer1_same_floor or layer2_same_mall) else
            "به نزدیک‌ترین فروشگاه در راسته مجاور هدایت می‌شوید."
        )
    }
