"""
تحلیل ساعت کاری فروشگاه‌ها (ستون weekly_hours) و وضعیت «الان باز/بسته» به وقت تهران.

قالب دقیق weekly_hours در دیتاست مستند نیست؛ پارسر چند قالب رایج را می‌پذیرد
و هر چیزی را که نشناسد «نامشخص» گزارش می‌کند، نه باز و نه بسته (حدس نمی‌زند).
- دیکشنری روز → بازه:  {"saturday": "10:00-20:00"} یا {"شنبه": ["10:00-14:00", "16:00-21:00"]}
- بازه به شکل آبجکت:  {"start": "10:00", "end": "20:00"} (یا from/to، open/close)
- لیست روزها:          [{"day": "saturday", "shifts": [...]}]
- خالی ({}، []، null):   نامشخص
- «00:00-00:00» برای یک روز نامشخص حساب می‌شود (ممکن است «۲۴ ساعته» یا «ثبت‌نشده» باشد).
- روزهای یک دیکشنری که اصلاً نیامده‌اند تعطیل حساب می‌شوند، به شرط اینکه حداقل یک روز بازه کاری واقعی داشته باشد.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from .textutil import is_null, to_fa_digits, to_latin_digits

# ایران از ۱۴۰۱ ساعت تابستانی ندارد؛ اختلاف ثابت +۳:۳۰ (بدون نیاز به tzdata در ویندوز)
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")

# اندیس روز مطابق datetime.weekday(): دوشنبه=0 ... شنبه=5، یکشنبه=6
DAY_NAMES = {
    "saturday": 5, "sat": 5, "شنبه": 5,
    "sunday": 6, "sun": 6, "یکشنبه": 6, "یک‌شنبه": 6, "یک شنبه": 6,
    "monday": 0, "mon": 0, "دوشنبه": 0, "دو‌شنبه": 0,
    "tuesday": 1, "tue": 1, "سه‌شنبه": 1, "سه شنبه": 1, "سهشنبه": 1,
    "wednesday": 2, "wed": 2, "چهارشنبه": 2, "چهار‌شنبه": 2,
    "thursday": 3, "thu": 3, "پنجشنبه": 3, "پنج‌شنبه": 3, "پنج شنبه": 3,
    "friday": 4, "fri": 4, "جمعه": 4,
}
FA_DAY = {5: "شنبه", 6: "یکشنبه", 0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه", 4: "جمعه"}
WEEK_ORDER = [5, 6, 0, 1, 2, 3, 4]  # شنبه تا جمعه
CLOSED_WORDS = {"closed", "close", "off", "تعطیل", "بسته", "false"}

_RANGE_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(?:-|–|تا|to)\s*(\d{1,2})(?::(\d{2}))?")

UNKNOWN = "unknown"


def now_tehran() -> datetime:
    return datetime.now(TEHRAN_TZ)


def _minutes(h, m):
    h, m = int(h), int(m or 0)
    if not (0 <= h <= 24 and 0 <= m < 60):
        return None
    return h * 60 + m


def _parse_range_text(text: str):
    ranges = []
    for m in _RANGE_RE.finditer(to_latin_digits(text)):
        start, end = _minutes(m.group(1), m.group(2)), _minutes(m.group(3), m.group(4))
        if start is None or end is None:
            return UNKNOWN
        if start == end:
            return UNKNOWN  # «00:00-00:00» و مشابه: نامشخص
        ranges.append((start, end))
    return ranges


def _parse_day_value(value):
    """یک روز → لیست بازه‌ها ([] یعنی تعطیل) یا UNKNOWN"""
    if value is None:
        return []
    if isinstance(value, bool):
        return [] if value is False else UNKNOWN
    if isinstance(value, str):
        text = value.strip().lower()
        if not text or text in CLOSED_WORDS:
            return []
        ranges = _parse_range_text(text)
        return ranges if ranges else UNKNOWN
    if isinstance(value, dict):
        if value.get("closed") is True or value.get("is_closed") is True:
            return []
        for key in ("shifts", "hours", "ranges", "times"):
            if key in value:
                return _parse_day_value(value[key])
        pairs = (("start", "end"), ("from", "to"), ("open", "close"), ("opens_at", "closes_at"), ("open_time", "close_time"))
        for a, b in pairs:
            if a in value and b in value:
                return _parse_day_value(f"{value[a]}-{value[b]}")
        return UNKNOWN
    if isinstance(value, list):
        ranges = []
        for item in value:
            parsed = _parse_day_value(item)
            if parsed == UNKNOWN:
                return UNKNOWN
            ranges.extend(parsed)
        return ranges
    return UNKNOWN


def _day_index(name):
    if not isinstance(name, str):
        return None
    return DAY_NAMES.get(name.strip().lower().replace("_", ""))


def parse_weekly_hours(raw):
    """
    خروجی: {"known": bool, "days": {weekday: [(start_min, end_min), ...] | "unknown"}}
    known=False یعنی هیچ روزی قابل تفسیر نبود.
    """
    if is_null(raw):
        return {"known": False, "days": {}}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return {"known": False, "days": {}}

    days = {}
    if isinstance(data, dict):
        for key, value in data.items():
            idx = _day_index(key)
            if idx is not None:
                days[idx] = _parse_day_value(value)
        if days:
            # روزهای نیامده در دیکشنری: تعطیل
            for idx in WEEK_ORDER:
                days.setdefault(idx, [])
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                idx = _day_index(item.get("day") or item.get("weekday") or item.get("name"))
                if idx is not None:
                    rest = {k: v for k, v in item.items() if k not in ("day", "weekday", "name")}
                    days[idx] = _parse_day_value(rest)

    # حداقل یک روز باید بازه کاری واقعی داشته باشد؛ «همه روزها تعطیل یا نامشخص» یعنی داده قابل اتکا نیست
    known = any(isinstance(v, list) and v for v in days.values())
    return {"known": known, "days": days if known else {}}


def _fmt(minutes: int) -> str:
    minutes %= 24 * 60
    return to_fa_digits(f"{minutes // 60:02d}:{minutes % 60:02d}")


def _fmt_ranges(ranges) -> str:
    if ranges == UNKNOWN:
        return "نامشخص"
    if not ranges:
        return "تعطیل"
    return "، ".join(f"{_fmt(s)} تا {_fmt(e)}" for s, e in ranges)


def _is_open(ranges, minute: int) -> bool:
    for start, end in ranges:
        if start < end and start <= minute < end:
            return True
        if start > end and (minute >= start or minute < end):  # شیفت شبانه
            return True
    return False


def hours_status(raw, at: datetime | None = None):
    """
    وضعیت فعلی + برنامه هفتگی برای نمایش.
    state: open | closed | unknown
    """
    parsed = raw if isinstance(raw, dict) and "known" in raw else parse_weekly_hours(raw)
    if not parsed["known"]:
        return {
            "known": False,
            "state": "unknown",
            "label": "ساعت کاری ثبت نشده (پیش از رفتن استعلام کنید)",
            "today": "نامشخص",
            "friday_closed": None,
            "week": [],
        }

    at = (at or now_tehran()).astimezone(TEHRAN_TZ)
    weekday = at.weekday()
    minute = at.hour * 60 + at.minute
    days = parsed["days"]
    today = days.get(weekday, UNKNOWN)

    if today == UNKNOWN:
        state, label = "unknown", "ساعت کاری امروز نامشخص است"
    elif _is_open(today, minute):
        end = next(e for s, e in today if (s <= minute < e) or (s > e))
        state, label = "open", f"الان باز است (تا {_fmt(end)})"
    else:
        state = "closed"
        later = [s for s, e in today if s > minute]
        if later:
            label = f"الان بسته است؛ امروز از {_fmt(min(later))} باز می‌شود"
        else:
            label = "الان بسته است"
            for offset in range(1, 8):
                nxt = (weekday + offset) % 7
                ranges = days.get(nxt)
                if ranges and ranges != UNKNOWN:
                    when = "فردا" if offset == 1 else FA_DAY[nxt]
                    label = f"الان بسته است؛ {when} از {_fmt(ranges[0][0])} باز می‌شود"
                    break

    friday = days.get(4, UNKNOWN)
    return {
        "known": True,
        "state": state,
        "label": label,
        "today": _fmt_ranges(today),
        "friday_closed": None if friday == UNKNOWN else (friday == []),
        "week": [{"day": FA_DAY[i], "hours": _fmt_ranges(days.get(i, UNKNOWN))} for i in WEEK_ORDER],
    }
