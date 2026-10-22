"""
الگوریتم ۵: غربال تعاملی نیاز مبهم خریدار (INDP Engine)
پاسخ به خریدار مردد (مثال کفش کتونی منتور هکاتون) با درخت تشخیصی ۲ مرحله‌ای: کاربرد، سپس بودجه.

جلوگیری از حلقه: درخت فقط وقتی نشان داده می‌شود که پیام «کلی» باشد (فقط کلمات عمومی همان دسته،
بدون مدل، برند یا بودجه). پاسخ‌های درخت به صورت اسلات ساختاریافته (نه متن آزاد) برگردانده
می‌شوند و مستقیم به جستجو می‌روند، پس دوباره وارد درخت نمی‌شوند.
"""

from __future__ import annotations

from .textutil import has_word

BUDGET_STEP_ID = 2

DIAGNOSTIC_TREES = {
    "shoes": {
        "keywords": ["کتونی", "کتانی", "کفش", "اسنیکر", "پیاده روی", "رانینگ"],
        "generic_words": ["کتونی", "کتانی", "کفش", "اسنیکر", "پیاده", "روی", "رانینگ", "ورزشی", "اسپرت", "راحت", "راحتی", "مردانه", "زنانه"],
        "base_tokens": ["کفش"],
        "title": "راهنمای انتخاب کفش و کتانی",
        "steps": [
            {
                "step_id": 1,
                "question": "این کفش را بیشتر برای چه کاری می‌خواهید؟",
                "options": [
                    {"label": "پیاده‌روی روزمره و اداری 👟", "tokens": ["پیاده", "طبی", "راحتی"]},
                    {"label": "دویدن، ورزش و تردمیل 🏃", "tokens": ["رانینگ", "ورزشی", "اسپرت"]},
                    {"label": "طبی، خارپاشنه و راحتی کامل 🩺", "tokens": ["طبی", "ارتوپدی"]},
                ],
            },
            {
                "step_id": BUDGET_STEP_ID,
                "question": "بودجه‌تان حدوداً چقدر است؟",
                "options": [
                    {"label": "زیر ۱ میلیون تومان", "max_price": 1_000_000},
                    {"label": "۱ تا ۳ میلیون تومان", "min_price": 1_000_000, "max_price": 3_000_000},
                    {"label": "بالای ۳ میلیون تومان", "min_price": 3_000_000},
                ],
            },
        ],
    },
    "mobile": {
        "keywords": ["گوشی", "موبایل", "تلفن همراه"],
        "generic_words": ["گوشی", "موبایل", "تلفن", "همراه", "هوشمند", "جدید"],
        "base_tokens": ["گوشی"],
        "title": "راهنمای انتخاب گوشی موبایل",
        "steps": [
            {
                "step_id": 1,
                "question": "مهم‌ترین اولویت شما در گوشی چیست؟",
                "options": [
                    {"label": "دوربین و عکاسی 📸", "tokens": ["دوربین", "pro", "ultra"]},
                    {"label": "باتری قوی و کارهای روزمره 🔋", "tokens": ["باتری", "5000", "6000"]},
                    {"label": "بازی و پردازش سنگین 🎮", "tokens": ["گیمینگ", "پوکو", "poco", "snapdragon"]},
                ],
            },
            {
                "step_id": BUDGET_STEP_ID,
                "question": "بودجه‌تان چقدر است؟",
                "options": [
                    {"label": "زیر ۱۰ میلیون تومان", "max_price": 10_000_000},
                    {"label": "۱۰ تا ۲۵ میلیون تومان", "min_price": 10_000_000, "max_price": 25_000_000},
                    {"label": "بالای ۲۵ میلیون تومان", "min_price": 25_000_000},
                ],
            },
        ],
    },
    "cctv": {
        "keywords": ["مداربسته", "دوربین مداربسته", "دوربین مدار بسته", "دزدگیر"],
        "generic_words": ["دوربین", "مداربسته", "مدار", "بسته", "دزدگیر", "امنیتی", "نظارتی"],
        "base_tokens": ["دوربین"],
        "title": "راهنمای انتخاب دوربین مداربسته",
        "steps": [
            {
                "step_id": 1,
                "question": "دوربین کجا نصب می‌شود؟",
                "options": [
                    {"label": "فضای باز و پارکینگ (دید در شب، ضدآب) 🌧️", "tokens": ["بولت", "دید", "شب"]},
                    {"label": "داخل مغازه یا آپارتمان 🏢", "tokens": ["دام", "سقفی", "بیسیم"]},
                    {"label": "باغ و ویلا بدون اینترنت ثابت 📡", "tokens": ["سیمکارتی", "4g", "خورشیدی"]},
                ],
            },
            {
                "step_id": BUDGET_STEP_ID,
                "question": "بودجه هر دوربین چقدر است؟",
                "options": [
                    {"label": "زیر ۲ میلیون تومان", "max_price": 2_000_000},
                    {"label": "بالای ۲ میلیون تومان", "min_price": 2_000_000},
                ],
            },
        ],
    },
}

# کلماتی که در پیام کلی هم مجازند و پیام را «مشخص» نمی‌کنند
_GENERIC_FILLERS = {"خوب", "خوبی", "مناسب", "برای", "یه", "یک", "بهترین", "ارزون", "ارزان", "قشنگ", "باکیفیت", "کیفیت"}


def detect_ambiguous_intent(user_query: str, tokens: list[str] | None = None, has_budget: bool = False):
    """
    بررسی اینکه آیا کاربر نیاز کلی و بدون مدل مشخص دارد؟
    tokens: توکن‌های کالای پیام (پس از حذف کلمات کمکی). اگر توکنی خارج از کلمات عمومی همان دسته
    باشد (برند، مدل، ویژگی) یا بودجه گفته شده باشد، پیام مبهم نیست.
    """
    query = (user_query or "").lower()
    best_key, best_hits = None, 0
    for cat_key, tree in DIAGNOSTIC_TREES.items():
        hits = sum(1 for kw in tree["keywords"] if has_word(query, kw))
        if hits > best_hits:
            best_key, best_hits = cat_key, hits
    if best_key is None or has_budget:
        return {"needs_decoupling": False}

    tree = DIAGNOSTIC_TREES[best_key]
    if tokens is not None:
        allowed = set(tree["generic_words"]) | _GENERIC_FILLERS
        if any(t not in allowed for t in tokens):
            return {"needs_decoupling": False}
    return {
        "needs_decoupling": True,
        "category_key": best_key,
        "tree": tree,
    }


def resolve_tree_answers(category_key: str, option_index: int, budget_index: int | None):
    """پاسخ‌های درخت → اسلات جستجو (توکن‌های پایه، توکن‌های ترجیحی، بازه قیمت)"""
    tree = DIAGNOSTIC_TREES[category_key]
    usage = tree["steps"][0]["options"][option_index]
    slots = {"tokens": list(tree["base_tokens"]), "optional": list(usage.get("tokens", [])),
             "budget_min": None, "budget_max": None, "label": usage["label"]}
    if budget_index is not None:
        budget = tree["steps"][1]["options"][budget_index]
        slots["budget_min"] = budget.get("min_price")
        slots["budget_max"] = budget.get("max_price")
        slots["label"] += f"، {budget['label']}"
    return slots
