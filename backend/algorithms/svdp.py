"""
الگوریتم ۶: استعلام تلفنی و اعتبارسنجی موجودی پیش از حرکت (SVDP Engine)
پاسخ به چالش منتور هکاتون برای استعلام قیمت‌های تاریخ‌گذشته با Click-to-Call و اسکریپت ۱۲ ثانیه‌ای تماس.
"""

import math
import json
import re

from .textutil import days_since, is_null, to_latin_digits

# اگر تاریخ قیمت معلوم نباشد، برای امتیاز اطمینان قیمتی یک‌ماهه فرض می‌شود
UNKNOWN_AGE_DAYS = 30


def _find_phone(text: str):
    """شماره ثابت یا همراه ایران؛ ارقام فارسی، فاصله/خط تیره و پیش‌شماره +98 پشتیبانی می‌شود."""
    compact = re.sub(r"[\s\-()]", "", to_latin_digits(str(text)))
    compact = re.sub(r"(?:\+|00)98(?=\d{10})", "0", compact)
    match = re.search(r"(?<!\d)(0\d{9,10})(?!\d)", compact)
    return match.group(1) if match else None


def parse_phone_number(contacts_raw: str):
    """
    استخراج شماره تلفن معتبر (ثابت یا همراه) از ستون contacts
    """
    if is_null(contacts_raw):
        return None
    try:
        data = json.loads(contacts_raw) if isinstance(contacts_raw, str) else contacts_raw
    except ValueError:
        return _find_phone(contacts_raw)
    values = data.values() if isinstance(data, dict) else data if isinstance(data, list) else [data]
    for item in values:
        phone = _find_phone(json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else item)
        if phone:
            return phone
    return None


def compute_stock_certainty(offer: dict, shop: dict):
    """
    محاسبه شاخص قطعیت موجودی بر پایه فرمول تنزیل زمانی
    P(InStock) = exp(-lambda * delta_days) * w_hours * w_verified
    """
    days_old = days_since(offer.get("last_price_changed_at"))

    # نرخ تنزیل روزانه: lambda = 0.015 (نیمه‌عمر حدود ۴۶ روز)
    decay_lambda = 0.015
    p_time = math.exp(-decay_lambda * (UNKNOWN_AGE_DAYS if days_old is None else days_old))

    # فاکتور ساعات کاری
    w_hours = 0.85 if is_null((shop or {}).get("weekly_hours")) else 0.95

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
    # اگر شماره‌ای ثبت نشده باشد None برمی‌گردد تا شماره ساختگی نمایش داده نشود
    phone = parse_phone_number(contacts_raw)
    formatted_price = f"{int(price_toman):,} تومان" if price_toman else "قیمت نیازمند استعلام"
    title = (product_title or "").strip()
    # عنوان طولانی برای تماس تلفنی در مرز کلمه کوتاه می‌شود
    short_title = title if len(title) <= 40 else title[:40].rsplit(" ", 1)[0]

    # اسکریپت ۱۲ ثانیه‌ای استاندارد بازار
    phone_script = (
        f"«سلام وقت بخیر، فروشگاهتون رو در ترب پیدا کردم. "
        f"آیا {short_title} رو موجود دارین و قیمت روزتون همون {formatted_price} هست؟ "
        f"برای خرید حضوری تا چه ساعتی تشریف دارید؟»"
    )

    # پیش‌نویس پیام ساختاریافته (بله / واتساپ)
    chat_draft = (
        f"سلام وقت بخیر، {shop_name or 'فروشگاه'}\n"
        f"من از طریق ترب در حال مراجعه حضوری هستم.\n"
        f"کالای مدنظر: {title}\n"
        f"قیمت ثبت‌شده: {formatted_price}\n"
        f"لطفاً در صورت موجود بودن، برای بنده رزرو بفرمایید تا ۳۰ دقیقه دیگر پای پیشخوان هستم. تشکر."
    )

    return {
        "phone_number": phone,
        "phone_script_12s": phone_script,
        "chat_draft_text": chat_draft
    }
