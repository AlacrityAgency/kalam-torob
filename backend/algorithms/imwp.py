"""
الگوریتم ۳: ناوبری خرد درون پاساژ و استخراج واحد متنی (Indoor Mall Wayfinding Parser - IMWP)
تجزیه آدرس خام مغازه‌ها در دیتابیس به پاساژ، طبقه، پلاک و تولید راهنمای کلامی گام‌به‌گام.
"""

from __future__ import annotations

import re

from .textutil import has_word, to_fa_digits, to_latin_digits

# اعداد ترتیبی و اصلی که بعد از «طبقه» می‌آیند؛ تطبیق فقط روی توکن کامل انجام می‌شود
FLOOR_WORDS = {
    "همکف": 0, "هم‌کف": 0,
    "زیرهمکف": -1, "زیرزمین": -1, "پارکینگ": -1,
    "اول": 1, "یکم": 1, "یک": 1,
    "دوم": 2, "دو": 2,
    "سوم": 3, "سه": 3,
    "چهارم": 4, "چهار": 4,
    "پنجم": 5, "پنج": 5,
    "ششم": 6, "شش": 6,
    "هفتم": 7, "هفت": 7,
    "هشتم": 8, "هشت": 8,
    "نهم": 9, "نه": 9,
    "دهم": 10, "ده": 10,
}

FLOOR_LABELS = {
    -3: "طبقه منفی سه", -2: "طبقه منفی دو", -1: "طبقه منفی یک",
    0: "طبقه همکف", 1: "طبقه اول", 2: "طبقه دوم", 3: "طبقه سوم", 4: "طبقه چهارم",
    5: "طبقه پنجم", 6: "طبقه ششم", 7: "طبقه هفتم", 8: "طبقه هشتم", 9: "طبقه نهم", 10: "طبقه دهم",
}

MALL_PREFIXES = ("پاساژ", "مجتمع تجاری", "مرکز خرید", "برج تجاری", "بازار", "مجتمع")
KNOWN_MALLS = ["چارسو", "علاءالدین", "علاالدین", "پایتخت", "امجد", "تجارت جهانی فردوسی", "کوروش", "ارگ"]

# توکن‌هایی که نشان می‌دهند نام پاساژ تمام شده است
_NAME_STOPWORDS = ("طبقه", "واحد", "پلاک", "شماره", "غرفه", "خیابان", "کوچه", "بلوار", "میدان", "نبش", "روبروی", "جنب")
_SEPARATORS = r"[،,؛;\-–\n()]"


def _floor_label(level: int) -> str:
    return FLOOR_LABELS.get(level, f"طبقه {to_fa_digits(level)}")


def _parse_floor_token(tokens: list[str]):
    """تبدیل توکن‌های بعد از «طبقه» به عدد طبقه؛ مثل «دوم»، «۲»، «-1»، «منفی یک»، «10»."""
    if not tokens:
        return None
    first = tokens[0]
    negative = False
    if first in ("منفی", "-") and len(tokens) > 1:
        negative = True
        first = tokens[1]
    elif first.startswith("-") and len(first) > 1:
        negative = True
        first = first[1:]

    if first.isdigit():
        value = int(first)
    elif first in FLOOR_WORDS:
        value = FLOOR_WORDS[first]
    else:
        return None
    return -abs(value) if negative else value


def _extract_floor(addr: str):
    match = re.search(r"طبقه\s*([^،,؛;\n]+)", addr)
    if match:
        # «طبقه - 1» و «طبقه -1» هر دو به توکن «-1» تبدیل می‌شوند
        tokens = re.sub(r"^\s*-\s*", "-", match.group(1)).split()
        level = _parse_floor_token(tokens[:2])
        if level is not None:
            return level, True
    # بدون کلمه «طبقه»: فقط کلمات کامل و بدون ابهام پذیرفته می‌شوند
    for word in ("زیرهمکف", "زیر همکف", "زیرزمین"):
        if has_word(addr, word):
            return -1, True
    if has_word(addr, "همکف"):
        return 0, True
    return 0, False


def _extract_mall(addr: str):
    for prefix in MALL_PREFIXES:
        match = re.search(r"(?<!\w)" + prefix + r"\s+(.+)", addr)
        if not match:
            continue
        segment = re.split(_SEPARATORS, match.group(1))[0]
        name_tokens = []
        for tok in segment.split():
            if tok in _NAME_STOPWORDS or len(name_tokens) == 4:
                break
            name_tokens.append(tok)
        if name_tokens:
            return f"{prefix} {' '.join(name_tokens)}"
    for kw in KNOWN_MALLS:
        if has_word(addr, kw):
            return f"مجتمع {kw}"
    return None


def _extract_unit(addr: str):
    match = re.search(r"(واحد|پلاک|شماره|غرفه)\s*(\d+(?:\s*[-/]\s*\d+)?)", addr)
    if match:
        number = re.sub(r"\s+", "", match.group(2))
        return f"{match.group(1)} {to_fa_digits(number)}"
    # «طبقه دوم، 214» → شماره خالص بعد از طبقه
    match = re.search(r"طبقه\s*\S+\s*[،,]\s*(\d+)(?!\S)", addr)
    if match:
        return f"واحد {to_fa_digits(match.group(1))}"
    return None


def parse_mall_address(raw_address: str, fallback_location: str = "تهران"):
    """
    تحلیل آدرس متنی و استخراج اجزای فیزیکی مغازه
    """
    fallback = fallback_location or "راسته بازار"
    if not raw_address or str(raw_address).strip() in ("", "null"):
        return {
            "raw_address": None,
            "mall_name": fallback,
            "mall_detected": False,
            "floor_level": 0,
            "floor_known": False,
            "floor_label": "طبقه نامشخص",
            "unit_number": None,
            "verbal_guide": [
                f"مراجعه به محدوده {fallback}",
                "آدرس دقیق ثبت نشده؛ پیش از رفتن با فروشگاه تماس بگیرید",
            ],
        }

    addr = to_latin_digits(str(raw_address).strip())

    mall_name = _extract_mall(addr)
    mall_detected = mall_name is not None
    if mall_name:
        mall_name = to_fa_digits(mall_name)
    else:
        mall_name = fallback

    floor_level, floor_known = _extract_floor(addr)
    floor_label = _floor_label(floor_level) if floor_known else "طبقه نامشخص"
    unit_number = _extract_unit(addr)

    verbal_steps = [f"ورود به لابی اصلی {mall_name}" if mall_detected else f"مراجعه به {mall_name}"]
    if not floor_known:
        verbal_steps.append("طبقه در آدرس ثبت نشده؛ از نگهبانی یا تابلوی راهنمای پاساژ بپرسید")
    elif floor_level == 0:
        verbal_steps.append("مستقر در طبقه همکف (بدون نیاز به آسانسور/پله‌برقی)")
    elif floor_level > 0:
        verbal_steps.append(f"صعود با پله‌برقی یا آسانسور به سمت {floor_label}")
    else:
        verbal_steps.append(f"نزول با پله‌برقی یا آسانسور به سمت {floor_label}")
    verbal_steps.append(f"پیدا کردن تابلوی فروشگاه: {unit_number}" if unit_number else "پیدا کردن تابلوی فروشگاه با نام مغازه")

    return {
        "raw_address": raw_address,
        "mall_name": mall_name,
        "mall_detected": mall_detected,
        "floor_level": floor_level,
        "floor_known": floor_known,
        "floor_label": floor_label,
        "unit_number": unit_number,
        "verbal_guide": verbal_steps,
    }
