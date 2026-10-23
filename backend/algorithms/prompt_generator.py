"""
الگوریتم تولید پویای سوالات آماده و راهنمای مکالمه خریدار (DCPG - Dynamic Contextual Prompt Generator)

این ماژول بر اساس مشخصات کالای فعال، فروشگاه، پاساژ و سبد خرید حضوری،
سوالات آماده (Prompt Chips) بالای باکس چت را به‌صورت کاملاً پویا و متناسب با مدل دقیق کالا تولید می‌کند.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# الگوهای استخراج شناسه مدل کالا
_MODEL_PATTERNS = [
    # مدل‌های سری گلکسی سامسونگ (A54, A55, S23 Ultra, S24 FE, Note 20)
    r"\b([A-Z]\d{2,3}(?:\s*(?:5G|4G|Ultra|Plus|FE|fe))?)\b",
    r"\b(Galaxy\s+[A-Za-z0-9\s]+?)(?:\s*(?:5G|4G|حافظه|رم|ظرفیت|مدل|$|\|))",
    # آیفون (iPhone 13, 14, 15, 16 Pro Max)
    r"\b(iPhone\s+\d{1,2}(?:\s*(?:Pro\s*Max|Pro|Plus|Mini))?)\b",
    r"\b(آیفون\s+(?:۱[۱-۶]|\d{1,2})(?:\s*(?:پرو\s*مکس|پرو|پلاس|مینی))?)\b",
    # شیائومی (Redmi Note 13, Poco X6)
    r"\b(Redmi\s+Note\s+\d{1,2}(?:\s*(?:Pro\s*5G|Pro|5G|4G))?)\b",
    r"\b(Poco\s+[A-Z]\d{1,2}(?:\s*(?:Pro|GT))?)\b",
    r"\b(ردمی\s+نوت\s+\d{1,2})\b",
    # نوکیا (105, 110, 150, 106)
    r"\b(?:نوکیا|Nokia)\s*(?:مدل)?\s*(\d{3,4})\b",
    # کدهای مدل عددی ابزار و الکترونیک (0810, 2210, P65W3PD)
    r"\bمدل\s+([A-Za-z0-9\-]+)\b",
    r"\b([A-Z0-9]{3,8}(?:-[A-Z0-9]+)?)\b",
]


def extract_core_model(model_str: Optional[str]) -> Optional[str]:
    """استخراج کد هسته مدل، مانند A54 از A54 5G یا 15 از iPhone 15 Pro"""
    if not model_str:
        return None
    cleaned = re.sub(r"(?i)\b(?:5G|4G|Ultra|Plus|Pro\s*Max|Pro|Max|Mini|FE|Lite|مدل)\b", "", model_str).strip()
    return cleaned if cleaned else model_str


def extract_model_and_brand(title: str, brand: Optional[str] = None) -> Dict[str, Optional[str]]:
    """استخراج تمیز برند و شناسه مدل کالا از عنوان"""
    if not title:
        return {"brand": brand, "model": None, "core_model": None, "display_name": None}

    clean_title = title.replace("(", " ").replace(")", " ").replace("|", " ")

    # تشخیص برندهای معروف در صورت نبود برند صریح
    if not brand:
        for b in ("سامسونگ", "شیائومی", "اپل", "نوکیا", "هواوی", "رونیکس", "توسن", "ماکیتا", "بوش", "البرز"):
            if b in clean_title:
                brand = b
                break

    detected_model = None
    for pat in _MODEL_PATTERNS:
        match = re.search(pat, clean_title, re.IGNORECASE)
        if match:
            cand = match.group(1).strip()
            # فیلتر واژه‌های عمومی که نباید مدل تلقی شوند
            if cand.lower() not in ("ram", "rom", "sim", "dual", "4g", "5g", "org", "gb"):
                detected_model = cand
                break

    core_model = extract_core_model(detected_model)

    # ساخت برچسب نمایشی مختصر
    parts = []
    if brand:
        parts.append(brand)
    if detected_model:
        if detected_model not in parts:
            parts.append(detected_model)

    display_name = " ".join(parts) if parts else (brand or detected_model or None)

    return {
        "brand": brand,
        "model": detected_model,
        "core_model": core_model,
        "display_name": display_name,
    }


def generate_dynamic_prompts(
    product: Optional[Dict[str, Any]] = None,
    shop: Optional[Dict[str, Any]] = None,
    cart_items: Optional[List[Dict[str, Any]]] = None,
    mall_name: Optional[str] = None,
) -> List[str]:
    """
    تولید داینامیک سوالات آماده متناسب با کالا، فروشگاه، پاساژ و وضعیت سبد خرید.
    """
    cart_items = cart_items or []
    has_cart = len(cart_items) > 0

    mall_label = mall_name
    if not mall_label and shop:
        mall_label = shop.get("hub") or shop.get("location_label")
        parsed = shop.get("parsed_address") or {}
        if parsed.get("mall_name"):
            mall_label = parsed.get("mall_name")

    prompts: List[str] = []

    # سناریوی ۱: کالای مشخص در صفحه یا مکالمه وجود دارد
    if product:
        if product.get("in_store_prompts"):
            return list(product["in_store_prompts"])

        title = product.get("title") or product.get("persian_title") or ""
        cat = (product.get("category") or product.get("category_name") or "").lower()
        brand = product.get("brand") or product.get("brand_name")
        meta = extract_model_and_brand(title, brand)
        model_str = meta.get("display_name") or title[:25]

        # دسته‌بندی موبایل و تبلت
        if any(w in cat for w in ("موبایل", "گوشی", "تبلت")):
            prompts.append(f"کاور یا گلس ضد ضربه مناسب {model_str}")
            if "سامسونگ" in model_str or "شیائومی" in model_str:
                prompts.append("شارژر دیواری فست ۲۵ وات اصلی")
            elif "آیفون" in model_str or "iphone" in model_str.lower():
                prompts.append("شارژر ۲۰ وات اصلی اپل")
            else:
                prompts.append("شارژر دیواری فست و کابل اصلی")

            prompts.append("آیا همین مغازه این لوازم جانبی رو یکجا داره؟")
            if mall_label:
                prompts.append(f"کدوم مغازه در {mall_label} جنس بهتر و اورجینال داره؟")
            else:
                prompts.append("کدوم مغازه جنس بهتر و اورجینال (گارانتی شرکتی) داره؟")
            prompts.append("استعلام پلمپ و رجیستری در سامانه همتا")

        # دسته‌بندی لوازم خانگی، سماور، چای‌ساز و آشپزخانه
        elif any(w in cat for w in ("سماور", "چای ساز", "چای‌ساز", "کتری", "قهوه", "اسپرسو", "جارو", "آشپزخانه", "خانگی")):
            prompts.append("جرم‌گیر و رسوب‌زدای مخصوص سماور")
            prompts.append("محافظ برق استاندارد لوازم خانگی")
            prompts.append("آیا همین مغازه این اقلام جانبی رو یکجا داره؟")
            prompts.append("کدوم مغازه جنس بهتر و گارانتی معتبرتر داره؟")
            prompts.append("خرید المنت یا قطعات مصرفی یدکی")

        # دسته‌بندی ابزارآلات و دریل
        elif any(w in cat for w in ("دریل", "فرز", "آچار", "چکش", "ابزار", "بتن", "جوش")):
            prompts.append(f"ست مته دریل {meta.get('brand') or 'رونیکس'}")
            prompts.append("عینک ایمنی و دستکش کارگاهی")
            prompts.append("آیا همین مغازه ست مته رو هم داره؟")
            prompts.append("کدوم مغازه جنس بهتر و گارانتی اصلی داره؟")
            prompts.append("تخفیف نقدی پای پوز روی متعلقات")

        # دسته‌بندی ساعت مچی
        elif any(w in cat for w in ("ساعت", "واچ", "مچ بند")):
            prompts.append("بند چرمی ساعت")
            prompts.append("بند فلزی ساعت")
            prompts.append("آیا همین مغازه این بندها رو داره؟")
            prompts.append("کدوم مغازه جنس اورجینال و باکیفیت‌تر داره؟")

        # دسته‌بندی سیم، کابل و روشنایی
        elif any(w in cat for w in ("سیم", "کابل", "روشنایی", "کلید", "پریز", "فیوز")):
            prompts.append("لوله فلکسی برق")
            prompts.append("کلید و پریز برق")
            prompts.append("آیا همین مغازه این اقلام رو یکجا داره؟")
            prompts.append("کدوم مغازه جنس بهتر و باکیفیت‌تر داره؟")

        # دسته‌بندی لپ‌تاپ و قطعات کامپیوتر
        elif any(w in cat for w in ("لپ تاپ", "کامپیوتر", "نوت بوک", "هارد", "رم")):
            prompts.append("کوله پشتی لپ تاپ")
            prompts.append("ماوس بی‌سیم")
            prompts.append("آیا همین مغازه این اقلام رو یکجا داره؟")
            prompts.append("کدوم مغازه جنس بهتر و گارانتی اصلی داره؟")

        # دسته‌بندی پمپ و تجهیزات آبرسانی
        elif any(w in cat for w in ("پمپ", "ابرسانی", "کف کش")):
            prompts.append("پنج‌راهی برنجی و نوار تفلون")
            prompts.append("آیا همین مغازه این اقلام رو یکجا داره؟")
            prompts.append("کدوم مغازه جنس باکیفیت‌تر و گارانتی شرکتی داره؟")

        # دسته‌بندی ظروف و وسایل یکبار مصرف
        elif any(w in cat for w in ("یکبار مصرف", "یکبارمصرف", "پلاستیکی")):
            prompts.append("سفره یکبار مصرف")
            prompts.append("دستکش یکبار مصرف")
            prompts.append("آیا همین مغازه این اقلام رو یکجا داره؟")
            prompts.append("تخفیف خرید تجمیعی از مغازه")

        # دسته‌بندی پارچ و لیوان، بلور و کریستال
        elif any(w in cat for w in ("لیوان", "پارچ", "استکان", "بلور", "کریستال", "پذیرایی")):
            prompts.append("زیر لیوانی و استند لیوان")
            prompts.append("پارچ یا بطری ست با این لیوان")
            prompts.append("آیا همین مغازه این اقلام رو یکجا داره؟")
            prompts.append("تخفیف خرید تجمیعی از مغازه")

        # کالاهای عمومی متفرقه
        else:
            prompts.append("اقلام مکمل برای تکمیل این خرید چیه؟")
            prompts.append("آیا همین مغازه این لوازم جانبی رو یکجا داره؟")
            prompts.append("کدوم مغازه جنس بهتر و اورجینال داره؟")

    # سناریوی ۲: سبد خرید بدون صفحه کالای فعال
    elif has_cart:
        prompts.append("کدوم پاساژ همه اقلام سبد خریدم رو یکجا داره؟")
        prompts.append("مسیر خرید سبدم رو تو پاساژ بچین")
        prompts.append("کی برم که همه مغازه‌ها باز باشن؟")
        prompts.append("اقلام مکمل برای تکمیل این خرید چیه؟")

    # سناریوی ۳: پیش‌فرض راهنمای پاساژگردی
    else:
        if mall_label:
            prompts.append(f"مغازه‌های باز در {mall_label}")
            prompts.append(f"کدوم فروشگاه‌ها در {mall_label} قسطی میدن؟")
            prompts.append(f"ساعت کاری مغازه‌های {mall_label}")
        else:
            prompts.append("گوشی سامسونگ A55 قسطی در چارسو تا ۲۵ میلیون")
            prompts.append("دریل شارژی رونیکس در بازار حسن‌آباد")
            prompts.append("کدوم پاساژها جمعه‌ها باز هستن؟")

    # حذف تکراری‌ها و بازگرداندن حداکثر ۵ سوال طلایی
    seen = set()
    result = []
    for p in prompts:
        if p and p not in seen:
            seen.add(p)
            result.append(p)
            if len(result) == 5:
                break
    return result
