"""
الگوریتم ۲: موتور مکمل نامتقارن و فضایی در پاساژ (PACO Engine)
محاسبه امتیاز پیوند کالاهای مکمل بر اساس ۴ فاکتور: وابستگی کارکردی، اصطکاک فیزیکی پاساژ، قطعیت قیمت و تناسب اقتصادی.
"""

import math
from datetime import datetime
from .imwp import parse_mall_address

def calculate_paco_score(base_product: dict, base_shop: dict, candidate_offer: dict):
    """
    محاسبه فرمول ضربی PACO:
    S = F_dep * Psi_spatial * Phi_confidence * Omega_economic
    """
    # ۱. ضریب وابستگی کارکردی F_dep
    dep_score = candidate_offer.get("dep_score", 0.65)
    # اگر برند رقیب هم‌عرض باشد، مکمل نیست بلکه جانشین است
    if candidate_offer.get("brand_name") and base_product.get("brand_name"):
        if candidate_offer["category_name"] == base_product["category_name"] and candidate_offer["brand_name"] != base_product["brand_name"]:
            return 0.0, "Substitute Brand Filtered"

    # ۲. تابع اصطکاک فیزیکی در پاساژ Psi_spatial
    same_shop = (base_shop.get("shop_id") == candidate_offer.get("shop_id"))
    if same_shop:
        psi_spatial = 1.00
        location_type = "same_shop"
        loc_desc = "موجود در همین مغازه (یک فاکتور بدون جابه‌جایی)"
    else:
        # بررسی تطابق پاساژ و طبقات با IMWP
        base_parsed = parse_mall_address(base_shop.get("address", ""))
        cand_parsed = parse_mall_address(candidate_offer.get("address", ""))
        
        same_mall = (base_shop.get("location_label") == candidate_offer.get("location_label"))
        if same_mall:
            floor_diff = abs(base_parsed["floor_level"] - cand_parsed["floor_level"])
            if floor_diff == 0:
                psi_spatial = 0.88
                location_type = "same_floor"
                loc_desc = f"مغازه همکار در همین طبقه ({base_parsed['floor_label']})"
            else:
                psi_spatial = max(0.40, 0.88 - (0.07 * floor_diff))
                location_type = "diff_floor"
                loc_desc = f"در همین پاساژ، {cand_parsed['floor_label']}"
        else:
            psi_spatial = 0.50
            location_type = "same_hub"
            loc_desc = f"در راسته {candidate_offer.get('location_label', 'مجاور')}"

    # ۳. ضریب اطمینان و تازگی قیمت Phi_confidence
    price = candidate_offer.get("price_toman")
    last_changed = candidate_offer.get("last_price_changed_at")
    
    if price is None or price <= 0:
        phi_confidence = 0.40
        freshness_badge = "استعلام در محل (قیمت نامشخص)"
    else:
        # محاسبه سن قیمت به روز
        days_old = 30
        if last_changed:
            try:
                dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                days_old = (datetime.now().astimezone() - dt).days
            except Exception:
                days_old = 30
                
        if days_old < 14:
            phi_confidence = 1.00
            freshness_badge = "قیمت تازه و قطعی (زیر ۱۴ روز)"
        elif days_old < 60:
            phi_confidence = 0.80
            freshness_badge = "قیمت معتبر (ماه اخیر)"
        else:
            phi_confidence = 0.55
            freshness_badge = "قیمت قدیمی (توصیه به استعلام)"

    # ۴. فاکتور تناسب روانشناسی قیمت سبد Omega_economic
    base_price = base_product.get("price_toman") or base_product.get("price") or 1000000
    if price and base_price:
        ratio = price / base_price
        if ratio <= 0.15:
            omega_economic = 1.00
        elif ratio <= 0.35:
            omega_economic = 0.85
        elif ratio <= 0.70:
            omega_economic = 0.65
        else:
            omega_economic = 0.45
    else:
        omega_economic = 0.70

    # ضرب نهایی
    final_score = dep_score * psi_spatial * phi_confidence * omega_economic
    
    return round(final_score, 4), {
        "final_score": round(final_score, 4),
        "location_type": location_type,
        "location_description": loc_desc,
        "freshness_badge": freshness_badge,
        "psi_spatial": round(psi_spatial, 2),
        "phi_confidence": round(phi_confidence, 2),
        "dep_score": round(dep_score, 2),
        "omega_economic": round(omega_economic, 2)
    }
