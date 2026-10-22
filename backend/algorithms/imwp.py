"""
الگوریتم ۳: ناوبری خرد درون پاساژ و استخراج واحد متنی (Indoor Mall Wayfinding Parser - IMWP)
تجزیه آدرس خام مغازه‌ها در دیتابیس به پاساژ، طبقه، پلاک و تولید راهنمای کلامی گام‌به‌گام.
"""

import re

# نگاشت متنی طبقات به عدد صحیح
FLOOR_WORDS_MAP = {
    "منفی سه": -3, "منفی 3": -3, "-3": -3,
    "منفی دو": -2, "منفی 2": -2, "-2": -2,
    "منفی یک": -1, "منفی 1": -1, "-1": -1, "زیر همکف": -1, "زیرهمکف": -1, "زیرزمین": -1,
    "همکف": 0, "طبقه همکف": 0,
    "اول": 1, "یکم": 1, "1": 1, "یک": 1,
    "دوم": 2, "2": 2, "دو": 2,
    "سوم": 3, "3": 3, "سه": 3,
    "چهارم": 4, "4": 4, "چهار": 4,
    "پنجم": 5, "5": 5, "پنج": 5,
    "ششم": 6, "6": 6, "شش": 6,
    "هفتم": 7, "7": 7, "هفت": 7,
    "هشتم": 8, "8": 8, "هشت": 8
}

MALL_KEYWORDS = [
    "پاساژ", "مجتمع تجاری", "مرکز خرید", "بازار", "برج تجاری",
    "مجتمع", "پاساژ علاءالدین", "علاءالدین", "چارسو", "پایتخت",
    "امجد", "تجارت جهانی فردوسی", "کوروش", "ارگ", "قائم"
]

def parse_mall_address(raw_address: str, fallback_location: str = "تهران"):
    """
    تحلیل آدرس متنی و استخراج اجزای فیزیکی مغازه
    """
    if not raw_address:
        return {
            "mall_name": fallback_location,
            "floor_level": 0,
            "floor_label": "همکف",
            "unit_number": "مشخص‌نشده",
            "verbal_guide": [
                f"مراجعه به محدوده {fallback_location}",
                "جستجوی تابلوی مغازه در راسته اصلی"
            ]
        }

    addr = raw_address.strip()
    
    # ۱. استخراج نام مجتمع / پاساژ
    mall_name = None
    mall_match = re.search(r'(پاساژ|مجتمع تجاری|مرکز خرید|برج تجاری|بازار)\s+([^\s،,]+(?:\s+[^\s،,]+){0,3})', addr)
    if mall_match:
        mall_name = mall_match.group(0).strip()
    else:
        for kw in ["چارسو", "علاءالدین", "علاالدین", "پایتخت", "امجد", "تجارت جهانی فردوسی", "کوروش", "ارگ"]:
            if kw in addr:
                mall_name = f"مجتمع {kw}"
                break
    if not mall_name:
        mall_name = fallback_location if fallback_location else "راسته بازار"

    # ۲. استخراج طبقه
    floor_level = 0
    floor_label = "همکف"
    
    # جستجوی عبارات طبقه
    floor_match = re.search(r'طبقه\s*([^\s،,]+)', addr)
    if floor_match:
        f_word = floor_match.group(1).strip()
        for k, v in FLOOR_WORDS_MAP.items():
            if k in f_word:
                floor_level = v
                floor_label = f"طبقه {k}"
                break
    else:
        for k, v in FLOOR_WORDS_MAP.items():
            if k in addr:
                floor_level = v
                floor_label = f"طبقه {k}"
                break

    # ۳. استخراج واحد یا پلاک
    unit_number = None
    unit_match = re.search(r'(واحد|پلاک|شماره)\s*([۰-۹0-9]+(?:\s*[-/]\s*[۰-۹0-9]+)?)', addr)
    if unit_match:
        unit_number = unit_match.group(0).strip()
    else:
        # جستجوی شماره خالص پس از طبقه
        num_match = re.search(r'طبقه\s*\d+\s*[،,]\s*(\d+)', addr)
        if num_match:
            unit_number = f"واحد {num_match.group(1)}"
        else:
            unit_number = "پلاک پای پیشخوان"

    # ۴. تولید راهنمای کلامی سه‌مرحله‌ای پاساژگردی
    verbal_steps = []
    verbal_steps.append(f"ورود به لابی اصلی {mall_name}")
    if floor_level == 0:
        verbal_steps.append("مستقر در طبقه همکف (بدون نیاز به آسانسور/پله‌برقی)")
    elif floor_level > 0:
        verbal_steps.append(f"صعود با پله‌برقی یا آسانسور به سمت {floor_label}")
    else:
        verbal_steps.append(f"نزول با پله‌برقی به سمت {floor_label} (طبقات منفی)")

    verbal_steps.append(f"پیدا کردن تابلوی فروشگاه: {unit_number}")

    return {
        "raw_address": raw_address,
        "mall_name": mall_name,
        "floor_level": floor_level,
        "floor_label": floor_label,
        "unit_number": unit_number,
        "verbal_guide": verbal_steps
    }
