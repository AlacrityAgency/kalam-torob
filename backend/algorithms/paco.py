"""
الگوریتم ۲: موتور مکمل نامتقارن و فضایی در پاساژ (PACO Engine)
محاسبه امتیاز پیوند کالاهای مکمل بر اساس ۴ فاکتور: وابستگی کارکردی، اصطکاک فیزیکی پاساژ، قطعیت قیمت و تناسب اقتصادی.
"""

import re

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


def _infer_cognitive_role(cand_title: str, cand_cat: str, explicit_role: str = None) -> tuple[str, str, float]:
    """
    تشخیص نقش شناختی قلم مکمل طبق سه‌گانه BAP-LLM:
    (role_key, category_name_fa, price_ratio_threshold)
    """
    if explicit_role in ("protective", "shield"):
        return "protective", "سپر محافظت از سرمایه", 0.30
    if explicit_role in ("consumable", "starter"):
        return "consumable", "راه‌اندازی فوری در محل", 0.20
    if explicit_role in ("synergy", "ecosystem"):
        return "synergy", "ارتقای کاربری و سینرژی", 0.60

    text = f"{cand_title} {cand_cat}".lower()
    # ۱. سپر محافظت از سرمایه (Loss Aversion Shield)
    if any(w in text for w in ("گلس", "محافظ", "کاور", "قاب", "کیف", "کوله", "ضربه", "فیوز", "ایمنی", "عینک", "دستکش")):
        return "protective", "سپر محافظت از سرمایه", 0.30
    # ۲. راه‌اندازی فوری در محل (Out-of-Box Readiness / Consumables)
    if any(w in text for w in ("مته", "شارژر", "آداپتور", "کابل", "تیغ", "باتری", "دانه", "نوار", "صفحه برش", "ذغال")):
        return "consumable", "راه‌اندازی فوری در محل", 0.20
    # ۳. ارتقای کاربری و سینرژی (Ecosystem & Synergy)
    if any(w in text for w in ("هدفون", "هندزفری", "ایرپاد", "ماوس", "پد", "هولدر", "پایه", "کیبورد", "قلم")):
        return "synergy", "ارتقای کاربری و سینرژی", 0.60

    return "accessory", "لوازم جانبی تکمیلی", 0.25


def calculate_paco_score(base_product: dict, base_shop: dict, candidate_offer: dict):
    """
    محاسبه فرمول PACO 2.0 بر مبنای معماری BAP-LLM:
    S = [w_dep * F_dep + w_spatial * Psi_retail + w_conf * Phi_confidence + w_econ * Omega_mental] * Mu_model * Theta_bundle
    """
    base_shop = base_shop or {}

    # ۱. ضریب وابستگی کارکردی F_dep (از جدول یا تحلیل AI)
    dep_score = candidate_offer.get("dep_score") or DEFAULT_DEP_SCORE
    # کالای هم‌دسته مکمل نیست بلکه جانشین است (چه هم‌برند چه رقیب)
    if candidate_offer.get("category_name") and candidate_offer.get("category_name") == base_product.get("category_name"):
        return 0.0, {"filtered": "substitute"}

    # ۲. تابع اصطکاک فیزیکی در پاساژ با شیب افت تصاعدی Psi_retail
    cand_parsed = parse_mall_address(candidate_offer.get("address"), candidate_offer.get("location_label"))
    if base_shop.get("shop_id") and base_shop.get("shop_id") == candidate_offer.get("shop_id"):
        psi_spatial = 1.00
        location_type = "same_shop"
        loc_desc = "موجود در همین مغازه (یک فاکتور بدون جابه‌جایی)"
        bundle_bonus = 1.40
        bundle_eligible = True
        bargaining_tip = "موجود در همین مغازه؛ امکان گرفتن ۱۰ تا ۱۵ درصد تخفیف نقدی روی فاکتور کل"
    elif not base_shop:
        # مغازه مبدأ مشخص نیست؛ فاصله قابل محاسبه نیست
        psi_spatial = 0.50
        location_type = "unknown_origin"
        loc_desc = f"{cand_parsed['mall_name']}، {cand_parsed['floor_label']}"
        bundle_bonus = 1.00
        bundle_eligible = False
        bargaining_tip = "موجود در پاساژ؛ نیازمند استعلام مستقیم در محل"
    else:
        base_parsed = parse_mall_address(base_shop.get("address"), base_shop.get("location_label"))
        bundle_bonus = 1.00
        bundle_eligible = False
        if _same_mall(base_shop, base_parsed, candidate_offer, cand_parsed):
            both_known = base_parsed["floor_known"] and cand_parsed["floor_known"]
            floor_diff = abs(base_parsed["floor_level"] - cand_parsed["floor_level"]) if both_known else 1
            if both_known and floor_diff == 0:
                psi_spatial = 0.55
                location_type = "same_floor"
                loc_desc = f"مغازه همکار در همین طبقه ({base_parsed['floor_label']})"
                bargaining_tip = "مغازه همکار در همین طبقه؛ پیاده‌روی کمتر از ۱ دقیقه"
            else:
                # افت شدید برای جابه‌جایی عمودی بین طبقات پاساژ
                psi_spatial = max(0.15, 0.30 - (0.05 * floor_diff))
                location_type = "diff_floor"
                loc_desc = f"در همین پاساژ، {cand_parsed['floor_label']}"
                bargaining_tip = f"طبقه دیگر پاساژ ({cand_parsed['floor_label']})؛ در صورت عدم موجودی در مغازه مبدأ"
        elif base_shop.get("location_label") and base_shop.get("location_label") == candidate_offer.get("location_label"):
            psi_spatial = 0.20
            location_type = "same_hub"
            loc_desc = f"در همین راسته، {cand_parsed['mall_name']}"
            bargaining_tip = "مغازه دیگر در همین راسته بازار"
        else:
            psi_spatial = 0.15
            location_type = "other_hub"
            loc_desc = f"در راسته {candidate_offer.get('location_label') or 'دیگر'}"
            bargaining_tip = "راسته دیگر بازار"

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

    # ۴. فاکتور حسابداری ذهنی و نقش رفتاری Omega_mental
    cand_title = candidate_offer.get("title") or candidate_offer.get("persian_title") or ""
    cand_cat = candidate_offer.get("category_name") or ""
    role, cog_cat, ratio_threshold = _infer_cognitive_role(
        cand_title,
        cand_cat,
        candidate_offer.get("role") or candidate_offer.get("cognitive_role"),
    )

    base_price = base_product.get("price_toman") or base_product.get("price")
    if price and base_price:
        ratio = price / base_price
        if ratio <= ratio_threshold:
            omega_economic = 1.00
        else:
            # افت ملایم متناسب با انحراف از آستانه نقشی
            omega_economic = max(0.40, round(1.00 - 1.2 * (ratio - ratio_threshold), 2))
    else:
        omega_economic = 0.70

    # ۵. ضریب تطابق مدل و برند Mu_model (Model Alignment Multiplier)
    core_model = base_product.get("core_model")
    mu_model = 1.00
    if core_model:
        if re.search(r"\b" + re.escape(core_model) + r"\b", cand_title, re.IGNORECASE):
            mu_model = 2.50
        elif core_model.lower() in cand_title.lower():
            mu_model = 2.00
        else:
            base_cat = (base_product.get("category_name") or "").lower()
            if any(w in base_cat for w in ("موبایل", "گوشی", "تبلت", "لپ تاپ")):
                mu_model = 0.40

    # فرمول خطی-وزنی BAP-LLM با توان تطابق و پاداش سبدی
    w_dep = 0.30
    w_spatial = 0.35
    w_conf = 0.15
    w_econ = 0.20
    base_sum = (w_dep * dep_score) + (w_spatial * psi_spatial) + (w_conf * phi_confidence) + (w_econ * omega_economic)
    final_score = base_sum * mu_model * bundle_bonus

    return round(final_score, 4), {
        "final_score": round(final_score, 4),
        "location_type": location_type,
        "location_description": loc_desc,
        "freshness_badge": freshness_badge,
        "psi_spatial": round(psi_spatial, 2),
        "phi_confidence": round(phi_confidence, 2),
        "dep_score": round(dep_score, 2),
        "omega_economic": round(omega_economic, 2),
        "mu_model": round(mu_model, 2),
        "bundle_bonus": round(bundle_bonus, 2),
        "bundle_eligible": bundle_eligible,
        "cognitive_role": role,
        "cognitive_category": cog_cat,
        "bargaining_tip": bargaining_tip,
    }
