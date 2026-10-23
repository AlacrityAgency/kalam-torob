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
from .algorithms.colloquial import clean_conversational_text, translate_colloquial
from .algorithms.textutil import has_word, to_latin_digits
from .search import normalize_text, tokenize

log = logging.getLogger("kalam.nlu")

INTENTS = ["search", "route", "visit", "panic", "credit", "hours", "greeting", "complementary", "consultation", "out_of_domain", "other"]

CONSULTATION_STRONG_PHRASES = [
    "پلمپ", "همتا", "ریجستر", "رجیستر", "رجیستری", "ریجستری",
    "فعال‌سازی", "فعالسازی", "هزینه اجباری", "نصب نرم‌افزار", "نصب برنامه", "هزینه فعال",
    "پای پوز", "چانه‌زنی", "چانه زنی", "تخفیف نقدی",
    "صدای گیربکس", "سلامت موتور", "آب‌بندی", "آب بندی", "مهلت تست", "تست روشن شدن",
    "فاکتور بدون هزینه", "هزینه فعال سازی", "استعلام پلمپ", "استعلام همتا",
    "کارت گارانتی", "برگه گارانتی", "اصالت شرکتی", "استعلام اصالت",
    "همین مغازه", "همین فروشگاه", "یکجا داره", "جنس بهتر", "کدوم مغازه", "کدام مغازه", "کدوم فروشگاه", "کدام فروشگاه", "کیفیت بهتر",
]
CONSULTATION_GENERAL_PHRASES = [
    "ضمانت", "گارانتی", "وارانتی", "شرایط گارانتی", "شرکت گارانتی",
    "تخفیف", "فاکتور", "فاکتور رسمی", "قیمت فاکتور", "اصالت", "تست فیزیکی", "مهلت تست",
]
CONSULTATION_MODIFIERS = [
    "استعلام", "شرایط", "قیمت", "رسمی", "چطور", "چگونه", "آیا", "تست", "در مغازه",
    "پای", "بدون", "حقوق", "اصلی", "معتبر", "قبل از", "پای پیشخوان", "حضوری",
    "نحوه", "راهنما", "چک کردن", "بررسی",
]
QUESTION_STARTERS = ["آیا", "چطور", "چگونه", "چرا", "امکان", "آیا امکان", "شرایط"]
QUESTION_ENDERS = ["؟", "میشود", "می‌شود", "میشه", "چطوره", "چقدره", "هست", "داره", "میدن", "میدید", "کنم"]


def is_consultation_query(text: str) -> bool:
    t_norm = normalize_text(text)
    w_set = set(t_norm.split())

    # استعلام ساعت کاری یا باز بودن فروشگاه‌ها باید به نیت hours برود نه consultation
    if any(h in t_norm for h in ("بازن", "بازند", "باز است", "باز هستند", "ساعت کار", "ساعت کاری", "ساعات کاری")):
        return False

    # عبارات قدرتمند و قطعی استعلام خرید حضوری (پلمپ، رجیستری، فعال‌سازی، هزینه اجباری، تخفیف پای پوز و تست سلامت)
    if any(p in t_norm for p in CONSULTATION_STRONG_PHRASES):
        return True

    # اگر کاربر به دنبال خرید کالای اصلی است و صرفاً قید «با گارانتی» دارد، این جستجو است نه مشاوره
    # مثلاً: «گوشی با گارانتی» یا «دریل با ضمانت»
    is_device_purchase = any(w in w_set for w in ("گوشی", "موبایل", "تبلت", "لپتاپ", "لپ تاپ", "دریل", "فرز", "ساعت")) and any(w in w_set for w in ("با", "دار", "دارای"))
    if is_device_purchase:
        return False

    has_cp = any(p in t_norm for p in CONSULTATION_GENERAL_PHRASES)
    has_mod = any(m in t_norm for m in CONSULTATION_MODIFIERS)
    has_qs = any(t_norm.startswith(s) or s in w_set for s in QUESTION_STARTERS)
    has_qe = any(t_norm.endswith(e) or e in w_set for e in QUESTION_ENDERS) or "؟" in text
    if has_cp and (has_mod or has_qs or has_qe or "این" in w_set or "خودتون" in w_set or "قبل" in w_set):
        return True
    if any(t_norm.startswith(s) for s in ("آیا", "چطور", "چگونه", "چرا")):
        return True
    return False

PANIC_WORDS = ["بسته بود", "بستس", "بسته است", "بسته‌ست", "موجود نداشت", "تموم کرده", "تمام کرده",
               "پنیک", "panic", "جایگزین"]
VISIT_WORDS = ["کی برم", "کی بریم", "چه ساعتی برم", "چه موقع برم", "بهترین زمان", "بهترین ساعت", "کی باز", "کی بازن"]
ROUTE_WORDS = ["سبد", "سبدم", "مسیر", "مسیرم", "بچین", "پاساژگردی", "برنامه حرکت",
               "یکجا", "همه اقلام", "همه این اقلام", "همه اینا", "کدوم پاساژ همه",
               "کدوم مرکز خرید همه", "همه اینا رو یکجا", "یکجا داره", "یک جا داره",
               "همه رو یکجا", "همه را یکجا", "کدوم پاساژ"]
COMPLEMENTARY_WORDS = ["مکمل", "اقلام مکمل", "لوازم جانبی", "جانبی", "وسایل جانبی", "متعلقات",
                       "تکمیل این خرید", "تکمیل خرید", "وسایل اضافه", "چی باهاش بخرم",
                       "چی همراهش بخرم", "چی لازم دارم", "لوازم مناسب", "ست با این", "متناسب با این"]
CREDIT_WORDS = ["اقساط", "اقساطی", "قسطی", "قسط", "اعتباری", "اعتبار", "bnpl"]
IN_PERSON_WORDS = ["کارتخوان", "حضوری", "پوز"]
HOURS_WORDS = ["ساعت کاری", "ساعت کار", "بازه", "بازن", "باز است", "باز هست", "تعطیل", "جمعه", "الان باز"]
GREETING_WORDS = ["سلام", "درود", "خسته نباشید", "ممنون", "مرسی"]
OUT_OF_DOMAIN_WORDS = ["میگرن", "درمان", "پزشک", "پزشکی", "دارو", "بیماری", "سردرد", "علائم", "تسکین",
                       "پایتون", "کد بنویس", "الگوریتم", "جاوااسکریپت", "برنامه‌نویسی", "برنامه نویسی", "تابع", "اسکریپت",
                       "انشا", "حل معادله"]
PREVIOUS_WORDS = ["ارزون‌ترش", "ارزونترش", "ارزان‌ترش", "ارزانترش", "همین", "همون", "اون", "کدومش", "قبلی",
                  "ارزون‌تر", "ارزان‌تر", "ارزونتر", "ارزانتر"]

# پاساژها و مراکز خرید شناخته‌شده که ممکن است در آدرس بیایند (نه در location_label)
KNOWN_MALLS = ["چارسو", "علاءالدین", "علاالدین", "پایتخت", "امجد", "کوروش", "قائم", "تندیس", "ارگ",
               "مرکز کامپیوتر ایران", "مرکز کامپیوتر نور", "مرکز کامپیوتر رضا", "لاله زار", "بازار بزرگ",
               "سپه سالار", "شوش"]

STOPWORDS = {
    # ضمایر شخصی و انتسابی
    "من", "ما", "تو", "شما", "او", "اونا", "اونها", "آنها", "ایشون",
    "واسم", "برام", "واسمون", "برامون", "بهش", "بهشون", "بهت", "بهتون",
    "میخوام", "می‌خوام", "میخواستم", "می‌خواستم", "میگشتم", "می‌گشتم", "میخوایم", "می‌خواهیم",
    "بی‌زحمت", "بیزحمت", "زحمت",
    # افعال و عبارات فروش، خرید و استعلام مکان
    "میفروشن", "می‌فروشن", "میفروشند", "می‌فروشند", "میفروشه", "می‌فروشه",
    "میخرن", "می‌خرن", "بفروشن", "بخرن", "کجاها", "کجا", "کجاست", "کجاهاست",
    "دنبال", "میگردم", "می", "گردم", "قیمت", "هستم", "یه", "یک", "برای", "خوب", "خوبی",
    "خواهم", "خوام", "رو", "را", "با", "در", "از", "به", "که", "و", "بخرم", "خرید", "ارزون", "ارزان",
    "بهترین", "لطفا", "لطفاً", "سلام", "چند", "چنده", "داره", "دارید", "دارین", "دارن", "مدل", "تا", "زیر",
    "بالای", "حدود", "حداکثر", "حداقل", "بین", "کمتر", "بیشتر", "تومن", "تومان", "میلیون", "هزار", "م",
    "مغازه", "مغازه‌ای", "فروشگاه", "فروشگاهی", "پاساژ", "مرکز", "خریدی", "کی", "چی", "یا", "هم", "هست",
    "است", "کنید", "کن", "بده", "بگو", "نشون", "نشان", "اینجا", "اونجا", "توی", "تو", "داخل", "نزدیک",
    "اقساط", "اقساطی", "قسطی", "قسط", "اعتباری", "اعتبار", "کارتخوان", "حضوری", "پوز",
    "باز", "بازن", "تعطیل", "جمعه", "الان", "ممنون", "مرسی", "مناسب", "متناسب",
    # پسوندها و کلمات کمکی که با جدا شدن نیم‌فاصله توکن مستقل می‌شوند
    "ها", "های", "هایی", "ای", "ی", "تر", "ترین", "ترش", "ولی", "فقط", "دارای", "کدوم", "کدومه", "کدام", "بود",
    "بوده", "هستن", "هستند", "دارند", "داشته", "باشه", "باشد", "کنم", "میشه", "شه", "چطور", "چه",
    "اینو", "اون", "این", "همین", "همون", "پیدا", "نیاز", "لازم", "دارم", "نزدیک", "نزدیکم",
    "نزدیکترین", "اطرافم", "نزدیکی", "دور", "بر", "کی", "برم", "بریم", "زمان",
    # صفات بازاریابی و عبارات عمومی استعلام
    "گارانتی", "باگارانتی", "تخفیف", "رایگان", "درصد", "آفر", "ویژه", "اصل", "اورجینال",
    "آیا", "آیاامکان",
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
            return lo, hi
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

    # ترجمه اصطلاحات عامیانه بازار و پاکسازی ضمایر و فیلرها
    colloquial = translate_colloquial(text)
    optional = None
    category = None
    colloquial_label = None
    colloquial_concept = None
    colloquial_note = None
    bazaar_hub_guide = colloquial.bazaar_hub_guide
    where_to_buy = colloquial.where_to_buy or any(has_word(t, w) for w in ("کجا", "کجاها", "کجا ها", "کجاست", "میفروشن", "می‌فروشن", "میفروشند", "گیر میاد", "کجا داره"))

    if colloquial.is_colloquial:
        tokens = list(colloquial.tokens)
        optional = list(colloquial.optional_tokens)
        category = colloquial.target_category
        colloquial_label = colloquial.display_label
        colloquial_concept = colloquial.concept_key
        colloquial_note = colloquial.friendly_note
        if not budget_max and colloquial.implied_budget_max:
            budget_max = colloquial.implied_budget_max
        if not budget_min and colloquial.implied_budget_min:
            budget_min = colloquial.implied_budget_min
    else:
        rest = clean_conversational_text(text)
        rest = _strip_budget(rest)
        # پاکسازی عبارات استعلام ساعت کاری (بدون حذف واژه ساعت برای محصولات مانند ساعت مچی یا بند ساعت)
        rest = re.sub(r"(?:\bساعت\s*کاری\b|\bساعت\s*کار\b|\bساعات\s*کاری\b|\bساعت\s*باز\s*(?:بودن|شدن)\b)", " ", rest)
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
    elif is_consultation_query(text):
        intent = "consultation"
    elif any(has_word(t, w) for w in COMPLEMENTARY_WORDS):
        intent = "complementary"
        # پاکسازی توکن‌های مکمل تا جستجوی لفظی نامرتبط مثل «مکمل باروری» یا «ماهیگیری تکمیل» اجرا نشود
        tokens = [tok for tok in tokens if tok not in ("مکمل", "تکمیل", "اقلام", "خرید", "این", "رو", "را", "برای", "چیه")]
    elif any(has_word(t, w) for w in OUT_OF_DOMAIN_WORDS) and not any(has_word(t, w) for w in ("کتاب", "کیف", "جعبه", "جلد")):
        intent = "out_of_domain"
        tokens = []
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
        "optional": optional,
        "category": category,
        "colloquial_label": colloquial_label,
        "colloquial_concept": colloquial_concept,
        "colloquial_note": colloquial_note,
        "bazaar_hub_guide": bazaar_hub_guide,
        "where_to_buy": where_to_buy,
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
    "intent: search (find a product), route (plan a multi-item shopping route or ask if a mall has all items), "
    "visit (best time to go for the cart route), complementary (asking for accessories, complement items, or what completes this purchase), "
    "panic (a shop was closed or out of stock), "
    "credit (shops with installment payment, no product named), hours (opening hours), greeting, "
    "consultation (in-store shopping advice, unboxing seal check, warranty/guarantee verification, Hamta/registry check, avoiding mandatory software/activation fees, bargaining/cash discounts at counter, in-store physical testing, invoice checking), "
    "out_of_domain (medical questions, medications, code writing, programming, essays, or non-shopping queries), other. "
    "place must be copied exactly from the provided list, otherwise empty."
)

_client = None


def llm_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ARVAN_AI_KEY") or os.environ.get("OPENAI_API_KEY")) and os.environ.get("KALAM_LLM", "on") != "off"


def openai_or_arvan_extract(text: str, places: list[str], previous: dict | None) -> tuple[dict | None, str]:
    api_key = os.environ.get("ARVAN_AI_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key or os.environ.get("KALAM_LLM", "on") == "off":
        return None, ""

    source = "arvan" if os.environ.get("ARVAN_AI_KEY") else "openai"
    base_url = (os.environ.get("ARVAN_AI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://arvancloudai.ir/gateway/models").rstrip("/")
    model = os.environ.get("ARVAN_AI_MODEL") or os.environ.get("OPENAI_MODEL") or "Gemini-2.5-Flash"

    endpoint = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    context = {
        "places": sorted(set(places) | set(KNOWN_MALLS))[:100],
        "previous_search": {k: previous.get(k) for k in ("tokens", "place", "budget_min", "budget_max", "provider")}
        if previous else None,
    }
    system_instruction = (
        _SYSTEM + "\n"
        "Return ONLY a JSON object matching this schema:\n"
        "{\n"
        '  "intent": "search" | "route" | "visit" | "panic" | "credit" | "hours" | "greeting" | "complementary" | "consultation" | "out_of_domain" | "other",\n'
        '  "product_query": "string (cleaned product name or empty)",\n'
        '  "place": "string (from places list or empty)",\n'
        '  "budget_min": integer,\n'
        '  "budget_max": integer,\n'
        '  "provider": "string",\n'
        '  "wants_credit": boolean,\n'
        '  "refers_to_previous": boolean\n'
        "}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Context:\n{json.dumps(context, ensure_ascii=False)}\n\nMessage:\n{text}"}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    try:
        import httpx
        with httpx.Client(timeout=httpx.Timeout(18.0, connect=3.5)) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                log.warning("AI Gateway (%s) error %s: %s", source, resp.status_code, resp.text[:200])
                return None, ""
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"].strip()
            # پاکسازی احتمالی بلوک کد مارک‌داون
            if raw_content.startswith("```"):
                raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
                raw_content = re.sub(r"\s*```$", "", raw_content).strip()
            parsed = json.loads(raw_content)
            valid_places = set(places) | set(KNOWN_MALLS)
            raw_intent = (parsed.get("intent") or "").lower()
            if raw_intent in ("purchase", "buy", "find"):
                raw_intent = "search"
            if any(w in text for w in ("همین مغازه", "همین فروشگاه", "همینجا", "جنس بهتر", "کدوم مغازه", "کدام مغازه")):
                if raw_intent in ("route", "search", "other"):
                    raw_intent = "consultation"
            return {
                "intent": raw_intent if raw_intent in INTENTS else "search",
                "tokens": tokenize(parsed.get("product_query", ""), STOPWORDS),
                "place": parsed.get("place") if parsed.get("place") in valid_places else None,
                "budget_min": parsed.get("budget_min") or None,
                "budget_max": parsed.get("budget_max") or None,
                "provider": parsed.get("provider") or None,
                "credit": bool(parsed.get("wants_credit") or parsed.get("provider")),
                "refers_previous": bool(parsed.get("refers_to_previous")),
            }, source
    except Exception as e:
        log.warning("AI Gateway call failed: %s; falling back to local NLU", e)
        return None, ""


def _get_client():
    global _client
    if _client is None:
        import anthropic

        # کوتاه نگه داشتن timeout: اگر API در دسترس نباشد، پارسر محلی بدون معطلی جایگزین می‌شود
        _client = anthropic.Anthropic(timeout=anthropic.Timeout(10.0, connect=3.0), max_retries=1)
    return _client


def llm_extract(text: str, places: list[str], previous: dict | None) -> dict | None:
    if not os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("KALAM_LLM", "on") == "off":
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
    """اسلات‌ها + منبع («arvan»، «openai»، «claude» یا «local»). پارسر محلی برای پرچم‌های جزئی همیشه اجرا می‌شود."""
    local = local_extract(text, places)
    # گاردریل حاکمیتی قطعی: سوالات پزشکی یا برنامه‌نویسی هرگز نباید جستجو شوند یا به AI بیرونی ارسال گردند
    if local.get("intent") == "out_of_domain":
        return local, "guardrail"
    # استعلام قطعی موجودی همان مغازه و رتبه‌بندی اصالت کالا
    if local.get("intent") == "consultation" and any(w in text for w in ("همین مغازه", "همین فروشگاه", "همینجا", "جنس بهتر", "کدوم مغازه", "کدام مغازه")):
        return local, "deterministic"
    llm, source = openai_or_arvan_extract(text, places, previous)
    if llm is None:
        llm = llm_extract(text, places, previous)
        if llm is not None:
            source = "claude"
    if llm is None:
        return local, "local"
    merged = dict(local)
    merged.update({k: v for k, v in llm.items() if v not in (None, [], "")})
    if not llm.get("tokens"):
        merged["tokens"] = local["tokens"] if llm["intent"] == "search" else []
    return merged, source
