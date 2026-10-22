"""
الگوریتم ۶: استعلام تلفنی و اعتبارسنجی موجودی پیش از حرکت (SVDP Engine)
پاسخ به چالش منتور هکاتون برای استعلام قیمت‌های تاریخ‌گذشته با Click-to-Call و اسکریپت ۱۲ ثانیه‌ای تماس.
"""

import math
import json
import re
from datetime import datetime

def parse_phone_number(contacts_raw: str):
    """
    استخراج شماره تلفن معتبر (ثابت یا همراه) از ستون contacts
    """
    if not contacts_raw or contacts_raw in ("null", "[]"):
        return None
    try:
        data = json.loads(contacts_raw) if isinstance(contacts_raw, str) else contacts_raw
        if isinstance(data, list):
            for item in data:
                # جستجوی شماره در مقادیر
                val = str(item)
                match = re.search(r'(0\d{9,10})', val)
                if match:
                    return match.group(1)
        elif isinstance(data, dict):
            for k, v in data.items():
                match = re.search(r'(0\d{9,10})', str(v))
                if match:
                    return match.group(1)
    except Exception:
        match = re.search(r'(0\d{9,10})', str(contacts_raw))
        if match:
            return match.group(1)
    return None

def compute_stock_certainty(offer: dict, shop: dict):
    """
    محاسبه شاخص قطعیت موجودی بر پایه فرمول تنزیل زمانی
    P(InStock) = exp(-lambda * delta_days) * w_hours * w_verified
    """
    last_changed = offer.get("last_price_changed_at")
    days_old = 30
    if last_changed:
        try:
            dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
            days_old = max(0, (datetime.now().astimezone() - dt).days)
        except Exception:
            days_old = 30

    # نرخ تنزیل روزانه: lambda = 0.015 (نیمه‌عمر حدود ۴۶ روز)
    decay_lambda = 0.015
    p_time = math.exp(-decay_lambda * days_old)
    
    # فاکتور ساعات کاری
    w_hours = 0.95 if shop.get("weekly_hours") else 0.85
    
    # فاکتور قیمت معتبر
    w_verified = 1.00 if offer.get("price_toman") else 0.50

    p_stock = round(p_time * w_hours * w_verified, 2)
    confidence_pct = int(p_stock * 100)

    if confidence_pct >= 75:
        badge = {"label": "موجودی با قطعیت بالا (قیمت به‌روز)", "color": "emerald", "type": "high"}
    elif confidence_pct >= 45:
        badge = {"label": "احتمال تغییر جزئی قیمت (توصیه به تماس)", "color": "amber", "type": "medium"}
    else:
        badge = {"label": "قیمت قدیمی (الزام استعلام پیش از حرکت)", "color": "rose", "type": "low"}

    return {
        "confidence_percentage": confidence_pct,
        "days_since_update": days_old,
        "badge": badge
    }

def generate_inquiry_dossier(product_title: str, price_toman: int, shop_name: str, contacts_raw: str):
    """
    تولید اسکریپت صوتی ۱۲ ثانیه‌ای تماس و متن آماده پیام‌رسان
    """
    phone = parse_phone_number(contacts_raw) or "۰۲۱۵۵۰۰۰۰۰۰"
    formatted_price = f"{price_toman:,} تومان" if price_toman else "قیمت نیازمند استعلام"

    # اسکریپت ۱۲ ثانیه‌ای استاندارد بازار
    phone_script = (
        f"«سلام وقت بخیر، از سمت ترب تماس می‌گیرم. "
        f"آیا مدل {product_title[:35]} رو موجود دارین و قیمت روزتون همون {formatted_price} هست؟ "
        f"برای خرید حضوری تا چه ساعتی تشریف دارید؟»"
    )

    # پیش‌نویس پیام ساختاریافته (بله / واتساپ)
    chat_draft = (
        f"سلام وقت بخیر جناب {shop_name}\n"
        f"من از طریق ترب در حال مراجعه حضوری هستم.\n"
        f"کالای مدنظر: {product_title}\n"
        f"قیمت ثبت‌شده: {formatted_price}\n"
        f"لطفاً در صورت موجود بودن، برای بنده رزرو بفرمایید تا ۳۰ دقیقه دیگر پای پیشخوان هستم. تشکر."
    )

    return {
        "phone_number": phone,
        "phone_script_12s": phone_script,
        "chat_draft_text": chat_draft
    }
