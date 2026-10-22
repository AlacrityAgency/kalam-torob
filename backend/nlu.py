"""
درک پیام خریدار (NLU): استخراج هم‌زمان «کالا + محدوده/پاساژ + بودجه + شرایط اقساطی + نیت» از یک جمله.

دو مسیر:
1. Claude (اختیاری): اگر ANTHROPIC_API_KEY تنظیم شده باشد، پیام با خروجی ساختاریافته (JSON Schema)
   به اسلات‌ها تبدیل می‌شود. مدل فقط «درک» می‌کند؛ هیچ پاسخی از مدل به کاربر نشان داده نمی‌شود
   و همه نتایج از پایگاه داده می‌آیند (ضد توهم).
2. پارسر محلی فارسی: همیشه در دسترس است و هر وقت مسیر ۱ خاموش، کند یا ناموفق باشد استفاده می‌شود.
"""

from __future__ import annotations

import json
import logging
import os
import re

from .algorithms.credipay import _PROVIDER_ALIASES
from .algorithms.textutil import has_word, to_latin_digits
from .search import normalize_text, tokenize

log = logging.getLogger("kalam.nlu")

INTENTS = ["search", "route", "visit", "panic", "credit", "hours", "greeting", "other"]

PANIC_WORDS = ["بسته بود", "بستس", "بسته است", "بسته‌ست", "موجود نداشت", "تموم کرده", "تمام کرده",
               "پنیک", "panic", "جایگزین"]
VISIT_WORDS = ["کی برم", "کی بریم", "چه ساعتی برم", "چه موقع برم", "بهترین زمان", "بهترین ساعت", "کی باز", "کی بازن"]
ROUTE_WORDS = ["سبد", "سبدم", "مسیر", "مسیرم", "بچین", "پاساژگردی", "برنامه حرکت"]
CREDIT_WORDS = ["اقساط", "اقساطی", "قسطی", "قسط", "اعتباری", "اعتبار", "bnpl"]
IN_PERSON_WORDS = ["کارتخوان", "حضوری", "پوز"]
HOURS_WORDS = ["ساعت کاری", "ساعت کار", "بازه", "بازن", "باز است", "باز هست", "تعطیل", "جمعه", "الان باز"]
GREETING_WORDS = ["سلام", "درود", "خسته نباشید", "ممنون", "مرسی"]
PREVIOUS_WORDS = ["ارزون‌ترش", "ارزونترش", "ارزان‌ترش", "ارزانترش", "همین", "همون", "اون", "کدومش", "قبلی",
                  "ارزون‌تر", "ارزان‌تر", "ارزونتر", "ارزانتر"]

# پاساژها و مراکز خرید شناخته‌شده که ممکن است در آدرس بیایند (نه در location_label)
KNOWN_MALLS = ["چارسو", "علاءالدین", "علاالدین", "پایتخت", "امجد", "کوروش", "قائم", "تندیس", "ارگ",
               "مرکز کامپیوتر ایران", "مرکز کامپیوتر نور", "مرکز کامپیوتر رضا", "لاله زار", "بازار بزرگ",
               "سپه سالار", "شوش"]

STOPWORDS = {
    "دنبال", "میگردم", "می", "گردم", "قیمت", "هستم", "یه", "یک", "برای", "خوب", "خوبی", "میخوام", "میخواهم",
    "خواهم", "خوام", "رو", "را", "با", "در", "از", "به", "که", "و", "کجا", "بخرم", "خرید", "ارزون", "ارزان",
    "بهترین", "لطفا", "لطفاً", "سلام", "چند", "چنده", "داره", "دارید", "دارین", "دارن", "مدل", "تا", "زیر",
    "بالای", "حدود", "حداکثر", "حداقل", "بین", "کمتر", "بیشتر", "تومن", "تومان", "میلیون", "هزار", "م",
    "مغازه", "مغازه‌ای", "فروشگاه", "فروشگاهی", "پاساژ", "مرکز", "خریدی", "کی", "چی", "یا", "هم", "هست",
    "است", "کنید", "کن", "بده", "بگو", "نشون", "نشان", "اینجا", "اونجا", "توی", "تو", "داخل", "نزدیک",
    "اقساط", "اقساطی", "قسطی", "قسط", "اعتباری", "اعتبار", "کارتخوان", "حضوری", "پوز", "ساعت", "کاری",
    "باز", "بازن", "تعطیل", "جمعه", "الان", "ممنون", "مرسی",
    # پسوندها و کلمات کمکی که با جدا شدن نیم‌فاصله توکن مستقل می‌شوند
    "ها", "های", "هایی", "ای", "ی", "تر", "ترین", "ترش", "ولی", "فقط", "دارای", "کدوم", "کدومه", "کدام", "بود",
    "بوده", "هستن", "هستند", "دارند", "داشته", "باشه", "باشد", "کنم", "میشه", "شه", "چطور", "چه",
    "اینو", "اون", "این", "همین", "همون", "پیدا", "کجاست", "نیاز", "لازم", "دارم", "نزدیک", "نزدیکم",
    "نزدیکترین", "اطرافم", "نزدیکی", "دور", "بر", "کی", "برم", "بریم", "ساعتی", "زمان",
} | set(PREVIOUS_WORDS)

_NUM_WORDS = {"نیم": 0.5, "یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "شیش": 6, "هفت": 7,
              "هشت": 8, "نه": 9, "ده": 10, "یازده": 11, "دوازده": 12, "پانزده": 15, "بیست": 20, "سی": 30,
              "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90, "صد": 100}
_NUM = r"(\d+(?:[.,/]\d+)?|" + "|".join(sorted(_NUM_WORDS, key=len, reverse=True)) + r")"
_UNIT = r"\s*(میلیارد|میلیون|ملیون|م|هزار|تومن|تومان)?"
_AMOUNT = _NUM + _UNIT


def _amount(num: str, unit: str | None) -> int | None:
    num = num.replace(",", "").replace("/", ".")
    value = _NUM_WORDS.get(num)
    if value is None:
        try:
            value = float(num)
        except ValueError:
            return None
    if unit == "میلیارد":
        value *= 1_000_000_000
    elif unit in ("میلیون", "ملیون", "م"):
        value *= 1_000_000
    elif unit == "هزار":
        value *= 1_000
    elif value < 1000:
        # در محاوره «تا ۳ تومن» یعنی ۳ میلیون تومان
        value *= 1_000_000
    return int(value)


def parse_budget(text: str) -> tuple[int | None, int | None]:
    t = to_latin_digits(normalize_text(text))
    m = re.search(r"(?:بین|از)\s*" + _AMOUNT + r"\s*(?:و|تا)\s*" + _AMOUNT, t)
    if m:
        unit2 = m.group(4)
        lo = _amount(m.group(1), m.group(2) or unit2)
        hi = _amount(m.group(3), unit2)
        if lo and hi:
            return min(lo, hi), max(lo, hi)
    m = re.search(r"(?:زیر|تا|کمتر از|حداکثر|نهایتا|نهایتاً|سقف|ماکزیمم)\s*" + _AMOUNT, t)
    if m:
        return None, _amount(m.group(1), m.group(2))
    m = re.search(r"(?:بالای|بیشتر از|حداقل|از)\s*" + _AMOUNT + r"(?:\s*به بالا)?", t)
    if m and (m.group(2) or "به بالا" in t or "بالای" in t or "بیشتر" in t or "حداقل" in t):
        return _amount(m.group(1), m.group(2)), None
    m = re.search(r"(?:حدود|حدودا|حدوداً|در حد)\s*" + _AMOUNT, t)
    if m:
        v = _amount(m.group(1), m.group(2))
        return (int(v * 0.85), int(v * 1.15)) if v else (None, None)
    return None, None


def _strip_budget(text: str) -> str:
    t = to_latin_digits(normalize_text(text))
    t = re.sub(r"(?:بین|از)\s*" + _AMOUNT + r"\s*(?:و|تا)\s*" + _AMOUNT, " ", t)
    t = re.sub(r"(?:زیر|تا|کمتر از|حداکثر|نهایتا|سقف|بالای|بیشتر از|حداقل|حدود|حدودا|در حد)\s*" + _AMOUNT, " ", t)
    return re.sub(r"\d+\s*(?:میلیون|ملیون|هزار|تومن|تومان|میلیارد)", " ", t)


def find_provider(text: str) -> str | None:
    t = normalize_text(text)
    for key, aliases in _PROVIDER_ALIASES.items():
        for alias in aliases:
            if has_word(t, normalize_text(alias)):
                return key
    return None


def find_place(text: str, places: list[str]) -> str | None:
    t = normalize_text(text)
    candidates = sorted(set(places) | set(KNOWN_MALLS), key=len, reverse=True)
    for place in candidates:
        if place and has_word(t, normalize_text(place)):
            return place
    return None


def local_extract(text: str, places: list[str]) -> dict:
    t = normalize_text(text)
    place = find_place(text, places)
    provider = find_provider(text)
    budget_min, budget_max = parse_budget(text)
    credit = provider is not None or any(has_word(t, w) for w in CREDIT_WORDS)

    rest = _strip_budget(text)
    if place:
        rest = rest.replace(normalize_text(place), " ")
    for aliases in _PROVIDER_ALIASES.values():
        for alias in aliases:
            rest = re.sub(r"(?<!\w)" + re.escape(normalize_text(alias)) + r"(?!\w)", " ", rest)
    tokens = tokenize(rest, STOPWORDS)

    if any(has_word(t, w) for w in PANIC_WORDS):
        intent = "panic"
    elif any(has_word(t, w) for w in VISIT_WORDS):
        intent = "visit"
    elif any(has_word(t, w) for w in ROUTE_WORDS):
        intent = "route"
    elif not tokens and credit:
        intent = "credit"
    elif not tokens and any(has_word(t, w) for w in HOURS_WORDS):
        intent = "hours"
    elif not tokens and any(has_word(t, w) for w in GREETING_WORDS):
        intent = "greeting"
    else:
        intent = "search"

    return {
        "intent": intent,
        "tokens": tokens,
        "place": place,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "provider": provider,
        "credit": credit,
        "in_person": any(has_word(t, w) for w in IN_PERSON_WORDS),
        "open_now": has_word(t, "الان باز") or has_word(t, "باز باشه") or has_word(t, "باز باشد"),
        "friday": has_word(t, "جمعه") or has_word(t, "جمعه ها"),
        "near": any(has_word(t, w) for w in ("نزدیک", "نزدیکم", "نزدیک ترین", "نزدیکترین", "دور و بر", "اطرافم", "نزدیکی")),
        # «فروشگاه‌های اقساطی» فهرست فروشگاه می‌خواهد، نه ادامه جستجوی کالای قبلی
        "shop_oriented": any(has_word(t, w) for w in ("فروشگاه", "فروشگاه های", "فروشگاهها", "مغازه", "مغازه ها", "مغازه های", "مغازه‌ها")),
        "refers_previous": any(has_word(t, normalize_text(w)) for w in PREVIOUS_WORDS),
        "cheapest": any(has_word(t, normalize_text(w)) for w in ("ارزون‌ترش", "ارزان‌ترش", "ارزونترش", "ارزانترین", "ارزون‌ترین", "ارزونترین")),
    }


# ---------------------------------------------------------------------------
# Claude (اختیاری)
# ---------------------------------------------------------------------------

LLM_MODEL = os.environ.get("KALAM_LLM_MODEL", "claude-opus-5-5")

_SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "product_query": {"type": "string", "description": "نام یا نوع کالا به فارسی، بدون محدوده و بودجه؛ خالی اگر کالایی نگفته"},
        "place": {"type": "string", "description": "یکی از محدوده‌های فهرست‌شده یا خالی"},
        "budget_min": {"type": "integer", "description": "حداقل بودجه به تومان؛ 0 یعنی نامشخص"},
        "budget_max": {"type": "integer", "description": "حداکثر بودجه به تومان؛ 0 یعنی نامشخص"},
        "provider": {"type": "string", "enum": ["", *_PROVIDER_ALIASES.keys()]},
        "wants_credit": {"type": "boolean"},
        "refers_to_previous": {"type": "boolean", "description": "آیا به کالا یا جستجوی پیام قبلی اشاره دارد"},
    },
    "required": ["intent", "product_query", "place", "budget_min", "budget_max", "provider", "wants_credit",
                 "refers_to_previous"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You convert a Persian shopping message for an in-person shopping assistant in Tehran into structured slots. "
    "Only extract what the user said; never invent products, places or numbers. "
    "Budgets are in toman; colloquial «۳ تومن» means 3,000,000 toman. "
    "intent: search (find a product), route (plan a multi-item shopping route), visit (best time to go for the cart route), "
    "panic (a shop was closed or out of stock), "
    "credit (shops with installment payment, no product named), hours (opening hours), greeting, other. "
    "place must be copied exactly from the provided list, otherwise empty."
)

_client = None


def llm_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("KALAM_LLM", "on") != "off"


def _get_client():
    global _client
    if _client is None:
        import anthropic

        # کوتاه نگه داشتن timeout: اگر API در دسترس نباشد، پارسر محلی بدون معطلی جایگزین می‌شود
        _client = anthropic.Anthropic(timeout=anthropic.Timeout(10.0, connect=3.0), max_retries=1)
    return _client


def llm_extract(text: str, places: list[str], previous: dict | None) -> dict | None:
    if not llm_enabled():
        return None
    try:
        import anthropic
    except ImportError:
        return None

    context = {
        "places": sorted(set(places) | set(KNOWN_MALLS))[:300],
        "previous_search": {k: previous.get(k) for k in ("tokens", "place", "budget_min", "budget_max", "provider")}
        if previous else None,
    }
    try:
        response = _get_client().beta.messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SLOT_SCHEMA}},
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nMessage:\n{text}",
            }],
        )
    except anthropic.APIConnectionError:
        log.info("Claude API unreachable; using local NLU")
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s; using local NLU", e.status_code)
        return None

    if response.stop_reason == "refusal":
        return None
    raw = next((b.text for b in response.content if b.type == "text"), None)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None

    valid_places = set(places) | set(KNOWN_MALLS)
    return {
        "intent": data["intent"] if data.get("intent") in INTENTS else "search",
        "tokens": tokenize(data.get("product_query", ""), STOPWORDS),
        "place": data.get("place") if data.get("place") in valid_places else None,
        "budget_min": data.get("budget_min") or None,
        "budget_max": data.get("budget_max") or None,
        "provider": data.get("provider") or None,
        "credit": bool(data.get("wants_credit") or data.get("provider")),
        "refers_previous": bool(data.get("refers_to_previous")),
    }


def extract(text: str, places: list[str], previous: dict | None = None) -> tuple[dict, str]:
    """اسلات‌ها + منبع («claude» یا «local»). پارسر محلی برای پرچم‌های جزئی همیشه اجرا می‌شود."""
    local = local_extract(text, places)
    llm = llm_extract(text, places, previous)
    if llm is None:
        return local, "local"
    merged = dict(local)
    merged.update({k: v for k, v in llm.items() if v not in (None, [], "")})
    if not llm.get("tokens"):
        merged["tokens"] = local["tokens"] if llm["intent"] == "search" else []
    return merged, "claude"
