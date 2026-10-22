"""
الگوریتم ۶: استعلام تلفنی و اعتبارسنجی موجودی پیش از حرکت (SVDP Engine)
پاسخ به چالش منتور هکاتون برای استعلام قیمت‌های تاریخ‌گذشته با Click-to-Call و اسکریپت ۱۲ ثانیه‌ای تماس.
"""

import math
import json
import re

from .credipay import analyze_payment_options
from .hours import hours_status, parse_weekly_hours
from .textutil import days_since, is_null, to_fa_digits, to_latin_digits

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

    # فاکتور ساعات کاری: فقط ساعت کاری قابل تفسیر امتیاز می‌گیرد، نه صرفاً پر بودن ستون
    w_hours = 0.95 if parse_weekly_hours((shop or {}).get("weekly_hours"))["known"] else 0.85

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


# ---------------------------------------------------------------------------
# شبیه‌ساز استعلام (Sandbox)
# شماره‌های دیتاست آزمایشی ساختگی‌اند، پس تماس واقعی ممکن نیست. این شبیه‌ساز گفت‌وگوی
# ایجنت با فروشنده را فقط از روی داده‌های ثبت‌شده همان آفر بازسازی می‌کند و همیشه
# برچسب «شبیه‌سازی» دارد؛ هیچ پاسخی از خودش (مثل موجودی قطعی) نمی‌سازد.
# ---------------------------------------------------------------------------

INQUIRY_QUESTIONS = {
    "availability": "موجودی و قیمت",
    "warranty": "گارانتی و اصالت",
    "credit": "خرید اقساطی",
    "hours": "ساعت کاری",
    "reserve": "رزرو تا رسیدن",
}


def _price_text(price):
    return f"{to_fa_digits(f'{int(price):,}')} تومان" if price else "قیمت ثبت‌نشده"


def simulate_inquiry(offer: dict, question: str) -> dict:
    """
    offer: product_title, price_toman, last_price_changed_at, warranty, shop_name,
           payment_options, weekly_hours, is_copy, price_suspect, seller_title
    خروجی: پیام ایجنت، پاسخ شبیه‌سازی‌شده فروشنده و نتیجه برای تصمیم کاربر.
    """
    title = (offer.get("product_title") or "این کالا")[:60]
    price = offer.get("price_toman")
    age = days_since(offer.get("last_price_changed_at"))
    hours = hours_status(offer.get("weekly_hours"))
    agent, seller, verdict, level = "", "", "", "unknown"

    if question == "availability":
        agent = f"سلام، {title} را با قیمت {_price_text(price)} موجود دارید؟"
        if offer.get("is_copy"):
            seller = f"این آفر در ترب با توضیح «{offer.get('seller_title') or 'غیراصل'}» ثبت شده؛ اصل نیست."
            verdict, level = "کالای این آفر غیراصل اعلام شده است.", "low"
        elif not price:
            seller = "قیمتی در ترب ثبت نکرده‌ایم؛ باید تلفنی بپرسید."
            verdict, level = "قیمت نامشخص؛ پیش از رفتن تماس بگیرید.", "low"
        elif offer.get("price_suspect"):
            seller = "قیمت ثبت‌شده با بقیه فروشگاه‌ها خیلی فرق دارد؛ احتمالاً اشتباه ثبت شده."
            verdict, level = "قیمت غیرعادی؛ قابل اتکا نیست.", "low"
        elif age is None:
            seller = "تاریخ به‌روزرسانی قیمت معلوم نیست؛ موجودی را باید بپرسید."
            verdict, level = "تازگی قیمت نامشخص است.", "medium"
        elif age <= 14:
            seller = f"قیمت {to_fa_digits(age)} روز پیش به‌روز شده؛ به احتمال زیاد همان قیمت است."
            verdict, level = "قیمت تازه؛ احتمال موجود بودن بالاست (تأیید نشده).", "high"
        elif age <= 60:
            seller = f"قیمت {to_fa_digits(age)} روز پیش ثبت شده؛ ممکن است تغییر کرده باشد."
            verdict, level = "قیمت ممکن است تغییر کرده باشد.", "medium"
        else:
            seller = f"این قیمت مال {to_fa_digits(age)} روز پیش است؛ احتمالاً به‌روز نیست."
            verdict, level = "قیمت قدیمی؛ حتماً استعلام کنید.", "low"
    elif question == "warranty":
        agent = "گارانتی و اصالت کالا چطور است؟"
        warranty = offer.get("warranty")
        if offer.get("is_copy"):
            seller, verdict, level = "طبق توضیح آفر، کالا اصل نیست.", "غیراصل اعلام شده.", "low"
        elif warranty and warranty != "null":
            seller, verdict, level = f"در آفر ثبت شده: «{warranty}».", "گارانتی ثبت شده است.", "high"
        else:
            seller, verdict, level = "گارانتی در آفر ثبت نشده است.", "گارانتی نامشخص؛ هنگام خرید بپرسید.", "unknown"
    elif question == "credit":
        agent = "امکان خرید اقساطی دارید؟"
        credit = analyze_payment_options(offer.get("payment_options"))
        if credit["has_credit"]:
            labels = "، ".join(b["label"] for b in credit["badges"])
            seller = f"در ترب این درگاه‌ها ثبت شده: {labels}."
            in_person = any(b["is_in_person"] for b in credit["badges"])
            verdict = "پرداخت اقساطی حضوری ثبت شده." if in_person else "درگاه اقساطی هست ولی حضوری بودن آن مشخص نیست."
            level = "high" if in_person else "medium"
        else:
            seller, verdict, level = "روش پرداخت اقساطی ثبت نکرده‌ایم.", "اقساط ثبت نشده است.", "unknown"
    elif question == "hours":
        agent = "امروز تا چه ساعتی باز هستید؟"
        seller = f"{hours['label']}. امروز: {hours['today']}." if hours["known"] else "ساعت کاری در ترب ثبت نشده است."
        verdict = hours["label"]
        level = {"open": "high", "closed": "low"}.get(hours["state"], "unknown")
        if hours.get("friday_closed"):
            verdict += " — جمعه‌ها تعطیل."
    elif question == "reserve":
        agent = "اگر موجود است، تا ۳۰ دقیقه دیگر برایم نگه دارید؟"
        seller = "رزرو فقط با تماس واقعی با فروشنده ممکن است؛ این شبیه‌ساز نمی‌تواند رزرو کند."
        verdict, level = "برای رزرو با فروشگاه تماس بگیرید.", "unknown"
    else:
        raise ValueError("unknown question")

    return {
        "simulated": True,
        "question": question,
        "question_label": INQUIRY_QUESTIONS[question],
        "agent": agent,
        "seller": seller,
        "verdict": verdict,
        "level": level,
        "notice": "شبیه‌سازی بر اساس داده‌های ثبت‌شده در ترب؛ با فروشنده واقعی تماس گرفته نشده است.",
    }
