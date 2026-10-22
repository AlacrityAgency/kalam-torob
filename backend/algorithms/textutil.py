"""
ابزارهای مشترک متنی و زمانی الگوریتم‌های کَلَم:
نرمال‌سازی ارقام فارسی/عربی، تطبیق کلمه کامل (نه زیررشته) و محاسبه سن تاریخ‌ها.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

_TO_LATIN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_TO_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_latin_digits(text: str) -> str:
    return text.translate(_TO_LATIN) if text else text


def to_fa_digits(text) -> str:
    return str(text).translate(_TO_FA)


def is_null(value) -> bool:
    """دیتاست ترب مقادیر خالی را با رشته null ذخیره می‌کند."""
    return value is None or (isinstance(value, str) and value.strip() in ("", "null", "[]", "{}"))


def has_word(text: str, phrase: str) -> bool:
    """آیا phrase به صورت کلمه/عبارت کامل در text آمده است؟ («یک» در «نزدیک» تطبیق نمی‌خورد)"""
    if not text or not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def has_any_word(text: str, phrases) -> bool:
    return any(has_word(text, p) for p in phrases)


def days_since(timestamp) -> int | None:
    """
    تعداد روزهای گذشته از یک تاریخ ISO. تاریخ بدون منطقه زمانی UTC فرض می‌شود.
    برای تاریخ نامعتبر یا خالی None برمی‌گرداند.
    """
    if is_null(timestamp):
        return None
    try:
        dt = datetime.fromisoformat(str(timestamp).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt).days)
