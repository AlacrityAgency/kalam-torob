"""
الگوریتم ۲: موتور مکمل نامتقارن و فضایی در پاساژ (PACO Engine)
محاسبه امتیاز پیوند کالاهای مکمل بر اساس ۴ فاکتور: وابستگی کارکردی، اصطکاک فیزیکی پاساژ، قطعیت قیمت و تناسب اقتصادی.
"""

from .imwp import parse_mall_address
from .textutil import days_since

DEFAULT_DEP_SCORE = 0.65


def _same_mall(base_shop: dict, base_parsed: dict, cand: dict, cand_parsed: dict) -> bool:
    """دو مغازه در یک پاساژند اگر نام پاساژ هر دو از آدرس شناسایی شده و یکسان باشد؛
    اگر پاساژ هیچ‌کدام شناسایی نشده، هم‌هاب بودن (location_label) ملاک است."""
    if base_parsed["mall_detected"] and cand_parsed["mall_detected"]:
        return base_parsed["mall_name"] == cand_parsed["mall_name"]
    base_hub = base_shop.get("location_label")
    return bool(base_hub) and base_hub == cand.get("location_label")


def calculate_paco_score(base_product: dict, base_shop: dict, candidate_offer: dict):
    """
    محاسبه فرمول ضربی PACO:
    S = F_dep * Psi_spatial * Phi_confidence * Omega_economic
    """
    base_shop = base_shop or {}

    # ۱. ضریب وابستگی کارکردی F_dep (از جدول complementary_rules)
    dep_score = candidate_offer.get("dep_score") or DEFAULT_DEP_SCORE
    # کالای هم‌دسته مکمل نیست بلکه جانشین است (چه هم‌برند چه رقیب)
    if candidate_offer.get("category_name") and candidate_offer.get("category_name") == base_product.get("category_name"):
        return 0.0, {"filtered": "substitute"}

    # ۲. تابع اصطکاک فیزیکی در پاساژ Psi_spatial
    cand_parsed = parse_mall_address(candidate_offer.get("address"), candidate_offer.get("location_label"))
    if base_shop.get("shop_id") and base_shop.get("shop_id") == candidate_offer.get("shop_id"):
        psi_spatial = 1.00
        location_type = "same_shop"
        loc_desc = "موجود در همین مغازه (یک فاکتور بدون جابه‌جایی)"
    elif not base_shop:
        # مغازه مبدأ مشخص نیست؛ فاصله قابل محاسبه نیست
        psi_spatial = 0.70
        location_type = "unknown_origin"
        loc_desc = f"{cand_parsed['mall_name']}، {cand_parsed['floor_label']}"
    else:
        base_parsed = parse_mall_address(base_shop.get("address"), base_shop.get("location_label"))
        if _same_mall(base_shop, base_parsed, candidate_offer, cand_parsed):
            both_known = base_parsed["floor_known"] and cand_parsed["floor_known"]
            floor_diff = abs(base_parsed["floor_level"] - cand_parsed["floor_level"]) if both_known else 1
            if both_known and floor_diff == 0:
                psi_spatial = 0.88
                location_type = "same_floor"
                loc_desc = f"مغازه همکار در همین طبقه ({base_parsed['floor_label']})"
            else:
                psi_spatial = max(0.40, 0.88 - (0.07 * floor_diff))
                location_type = "diff_floor"
                loc_desc = f"در همین پاساژ، {cand_parsed['floor_label']}"
        elif base_shop.get("location_label") and base_shop.get("location_label") == candidate_offer.get("location_label"):
            psi_spatial = 0.60
            location_type = "same_hub"
            loc_desc = f"در همین راسته، {cand_parsed['mall_name']}"
        else:
            psi_spatial = 0.50
            location_type = "other_hub"
            loc_desc = f"در راسته {candidate_offer.get('location_label') or 'دیگر'}"

    # ۳. ضریب اطمینان و تازگی قیمت Phi_confidence
    price = candidate_offer.get("price_toman")
    days_old = days_since(candidate_offer.get("last_price_changed_at"))
    if not price or price <= 0:
        phi_confidence = 0.40
        freshness_badge = "استعلام در محل (قیمت نامشخص)"
    elif days_old is None:
        phi_confidence = 0.70
        freshness_badge = "تاریخ قیمت نامشخص (توصیه به استعلام)"
    elif days_old < 14:
        phi_confidence = 1.00
        freshness_badge = "قیمت تازه و قطعی (زیر ۱۴ روز)"
    elif days_old < 60:
        phi_confidence = 0.80
        freshness_badge = "قیمت معتبر (دو ماه اخیر)"
    else:
        phi_confidence = 0.55
        freshness_badge = "قیمت قدیمی (توصیه به استعلام)"

    # ۴. فاکتور تناسب روانشناسی قیمت سبد Omega_economic
    base_price = base_product.get("price_toman") or base_product.get("price")
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

    final_score = dep_score * psi_spatial * phi_confidence * omega_economic

    return round(final_score, 4), {
        "final_score": round(final_score, 4),
        "location_type": location_type,
        "location_description": loc_desc,
        "freshness_badge": freshness_badge,
        "psi_spatial": round(psi_spatial, 2),
        "phi_confidence": round(phi_confidence, 2),
        "dep_score": round(dep_score, 2),
        "omega_economic": round(omega_economic, 2),
    }
