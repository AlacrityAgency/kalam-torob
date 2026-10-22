"""
کیفیت آفرها: تشخیص کالای کپی/غیراصل از متن فروشنده و قیمت‌های پرت.
این برچسب‌ها هنگام ساخت پایگاه داده محاسبه می‌شوند تا «کمترین قیمت» با آفر کپی یا قیمت
اشتباه (مثلاً ۱ تومان یا ایرپاد ۶۰۰ هزاری کنار اورجینال ۱۵ میلیونی) گمراه‌کننده نشود.
"""

from __future__ import annotations

import re
from statistics import median

from .textutil import has_word

# عبارت‌هایی که فروشنده با آن‌ها غیراصل بودن کالا را اعلام می‌کند
COPY_PHRASES = [
    "کپی", "های کپی", "هایکپی", "مستر کپی", "مسترکپی", "فرست کپی", "فرستکپی", "غیر اصل", "غیراصل", "غیر اورجینال",
    "طرح اصلی", "طرح اورجینال", "فیک", "ریپلیکا", "replica", "copy", "high copy", "master copy", "fake",
]

MIN_VALID_PRICE = 1_000            # تومان؛ کمتر از این تقریباً همیشه داده تستی است
MAX_VALID_PRICE = 100_000_000_000  # ارقام نجومی ناشی از خطای ورود داده
LOW_RATIO = 0.35                   # کمتر از ۳۵٪ میانه آفرهای همان کالا
HIGH_RATIO = 3.0                   # بیشتر از ۳ برابر میانه


def is_copy_text(*texts) -> bool:
    joined = " ".join(t for t in texts if t and t != "null").lower()
    if not joined:
        return False
    # نیم‌فاصله جزء کلمه است: «کپی‌برداری» کپی نیست و «های‌کپی» به «هایکپی» تبدیل می‌شود
    joined = joined.replace("\u200c", "")
    return any(has_word(joined, phrase) for phrase in COPY_PHRASES)


def suspicious_prices(prices: list[int]) -> set[int]:
    """
    اندیس آفرهایی که قیمتشان پرت است.
    مرز مطلق برای همه؛ مقایسه با میانه فقط وقتی حداقل ۳ آفر قیمت‌دار وجود دارد.
    """
    flagged = set()
    valid = [(i, p) for i, p in enumerate(prices) if p is not None]
    for i, p in valid:
        if p < MIN_VALID_PRICE or p > MAX_VALID_PRICE:
            flagged.add(i)
    rest = [(i, p) for i, p in valid if i not in flagged]
    if len(rest) >= 3:
        m = median(p for _, p in rest)
        for i, p in rest:
            if p < m * LOW_RATIO or p > m * HIGH_RATIO:
                flagged.add(i)
    return flagged


_SPEC_SKIP = re.compile(r"^(id|_id|url|image|images)$", re.I)


def flatten_specs(raw, limit: int = 24):
    """specs (JSON) → لیست [{"name","value"}] برای جدول مشخصات فنی؛ قالب ناشناخته → []"""
    import json

    if not raw or raw == "null":
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return []
    rows = []

    def add(name, value):
        if len(rows) >= limit or value in (None, "", [], {}):
            return
        if isinstance(value, (list, tuple)):
            value = "، ".join(str(v) for v in value if v not in (None, ""))
        elif isinstance(value, dict):
            for k, v in value.items():
                add(f"{name} / {k}" if name else k, v)
            return
        name = str(name).strip()
        if name and not _SPEC_SKIP.match(name):
            rows.append({"name": name, "value": str(value).strip()})

    if isinstance(data, dict):
        for k, v in data.items():
            add(k, v)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                name = item.get("name") or item.get("key") or item.get("title")
                value = item.get("value") if "value" in item else item.get("values")
                if name is not None:
                    add(name, value)
                else:
                    for k, v in item.items():
                        add(k, v)
    return rows
