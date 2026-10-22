"""
الگوریتم ۴: موتور تطبیق خرید اعتباری و اقساطی (CrediPay Matcher)
پشتیبانی از درگاه‌های BNPL ایرانی (اسنپ‌پی، ترب‌پی، تارا، دیجی‌پی) و تفکیک پایانه حضوری.
"""

from __future__ import annotations

import json

from .textutil import is_null

PROVIDER_LABELS = {
    "snapp_pay": "اسنپ‌پی",
    "torob_pay": "ترب‌پی",
    "tara": "تارا",
    "digi_pay": "دیجی‌پی",
    "azki_vam": "ازکی‌وام",
}

# در دیتاست واقعی provider_name فارسی است («اسنپ‌پی»)؛ همه املاها به یک کلید یکتا نگاشت می‌شوند
_PROVIDER_ALIASES = {
    "snapp_pay": ["snapp_pay", "snapppay", "snapp pay", "snap pay", "اسنپ‌پی", "اسنپ پی", "اسنپپی", "اسنپ"],
    "torob_pay": ["torob_pay", "torobpay", "torob pay", "ترب‌پی", "ترب پی", "تربپی"],
    "tara": ["tara", "تارا"],
    "digi_pay": ["digi_pay", "digipay", "digi pay", "دیجی‌پی", "دیجی پی", "دیجیپی"],
    "azki_vam": ["azki_vam", "azki", "ازکی‌وام", "ازکی وام", "ازکیوام", "ازکی"],
}
_ALIAS_TO_KEY = {
    alias.replace("\u200c", "").replace(" ", "").replace("_", "").lower(): key
    for key, aliases in _PROVIDER_ALIASES.items() for alias in aliases
}

CHANNEL_LABELS = {"in_person": "حضوری", "online": "آنلاین", "unknown": "کانال نامشخص"}


def canonical_provider(name) -> str | None:
    """«اسنپ‌پی»، «اسنپ پی» و «snapp_pay» → snapp_pay؛ ناشناخته → None"""
    if not name:
        return None
    key = str(name).replace("\u200c", "").replace(" ", "").replace("_", "").lower()
    return _ALIAS_TO_KEY.get(key)

EMPTY_ANALYSIS = {"has_credit": False, "credit_score": 0.0, "supported_providers": [], "badges": []}


def _normalize_options(raw):
    """payment_options ممکن است لیست، یک آبجکت تکی یا آبجکتی از لیست‌ها باشد؛ همه به لیست آبجکت تبدیل می‌شوند."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        if "provider_name" in raw or "provider" in raw:
            raw = [raw]
        else:
            raw = [v for value in raw.values() for v in (value if isinstance(value, list) else [value])]
    if not isinstance(raw, list):
        return []
    return [opt for opt in raw if isinstance(opt, dict)]


def analyze_payment_options(payment_options_raw):
    """
    تجزیه فیلد payment_options در دیتابیس و محاسبه شاخص پشتیبانی اعتباری
    """
    if is_null(payment_options_raw):
        return dict(EMPTY_ANALYSIS)
    try:
        options = _normalize_options(payment_options_raw)
    except ValueError:
        return dict(EMPTY_ANALYSIS)

    credit_score = 0.0
    supported_providers = []
    badges = []

    for opt in options:
        raw_name = opt.get("provider_name") or opt.get("provider") or ""
        if not raw_name:
            continue
        key = canonical_provider(raw_name) or str(raw_name)
        channel = opt.get("channel") or "unknown"
        if channel not in CHANNEL_LABELS:
            channel = "unknown"

        # وزن‌دهی به پایانه فیزیکی حضوری در مغازه
        is_in_person = (channel == "in_person")
        weight = 1.0 if is_in_person else 0.65
        credit_score += weight

        display = PROVIDER_LABELS.get(key, str(raw_name))
        badges.append({
            "provider": key,
            "provider_label": display,
            "channel": channel,
            "channel_label": CHANNEL_LABELS[channel],
            "label": f"{display} ({CHANNEL_LABELS[channel]})",
            "is_in_person": is_in_person
        })
        if key not in supported_providers:
            supported_providers.append(key)

    return {
        "has_credit": len(supported_providers) > 0,
        "credit_score": round(credit_score, 2),
        "supported_providers": supported_providers,
        "badges": badges
    }


def filter_and_rank_by_credit(shops: list, required_provider: str = None, in_person_only: bool = False):
    """
    فیلتر و مرتب‌سازی مغازه‌ها بر اساس معیارهای اعتباری و درگاه‌های اقساطی.
    in_person_only فقط وقتی کاربر صریحاً «کارتخوان حضوری» بخواهد استفاده شود؛
    در دیتاست واقعی بیشتر درگاه‌ها کانال unknown یا online دارند و این فیلتر اکثر آن‌ها را حذف می‌کند.
    """
    required_provider = canonical_provider(required_provider) or required_provider
    scored = []
    for s in shops:
        analysis = analyze_payment_options(s.get("payment_options"))
        if not analysis["has_credit"]:
            continue

        if required_provider and required_provider not in analysis["supported_providers"]:
            continue

        if in_person_only:
            # اگر درگاه خاصی خواسته شده، همان درگاه باید حضوری باشد
            has_in_person = any(
                b["is_in_person"] and (not required_provider or b["provider"] == required_provider)
                for b in analysis["badges"]
            )
            if not has_in_person:
                continue

        s_copy = dict(s)
        s_copy["credit_analysis"] = analysis
        scored.append(s_copy)

    # مرتب‌سازی نزولی بر اساس امتیاز اعتباری
    return sorted(scored, key=lambda x: x["credit_analysis"]["credit_score"], reverse=True)
