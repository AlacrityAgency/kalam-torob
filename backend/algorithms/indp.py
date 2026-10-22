"""
الگوریتم ۵: غربال تعاملی نیاز مبهم خریدار (INDP Engine)
پاسخ به چالش کاربر سردرگم (مثال کفش کتونی منتور هکاتون) با درخت تشخیصی ۲ مرحله‌ای بدون هدررفت توکن.
"""

from .textutil import has_word

DIAGNOSTIC_TREES = {
    "shoes": {
        "keywords": ["کتونی", "کفش", "اسنیکر", "پیاده روی", "رانینگ"],
        "title": "راهنمای انتخاب هوشمند کفش و کتونی",
        "steps": [
            {
                "step_id": 1,
                "question": "این کفش رو برای چه کاربرد اصلی می‌خواین؟",
                "options": [
                    {"label": "پیاده‌روی روزمره و اداری 👟", "query_tag": "طبی سبک پیاده روی"},
                    {"label": "دویدن، ورزش و تردمیل 🏃", "query_tag": "رانینگ ورزشی اسپرت"},
                    {"label": "طبی، خارپاشنه و راحتی کامل 🩺", "query_tag": "طبی راحتی ارتوپدی"}
                ]
            },
            {
                "step_id": 2,
                "question": "بازه بودجه مدنظرتون چقدره؟",
                "options": [
                    {"label": "زیر ۱ میلیون تومان (اقتصادی)", "max_price": 1000000},
                    {"label": "بین ۱ تا ۳ میلیون تومان (میان‌رده باکیفیت)", "min_price": 1000000, "max_price": 3000000},
                    {"label": "بالای ۳ میلیون تومان (برند اورجینال)", "min_price": 3000000}
                ]
            }
        ]
    },
    "mobile": {
        "keywords": ["گوشی", "موبایل", "تلفن همراه", "سامسونگ", "شیائومی", "آیفون"],
        "title": "راهنمای انتخاب هوشمند گوشی موبایل",
        "steps": [
            {
                "step_id": 1,
                "question": "مهم‌ترین اولویت شما در گوشی چیه؟",
                "options": [
                    {"label": "کیفیت عالی دوربین و عکاسی 📸", "query_tag": "دوربین عکاسی Pro"},
                    {"label": "باتری قوی و کارهای روزمره 🔋", "query_tag": "باتری ۵۰۰۰ فست شارژ"},
                    {"label": "گیمینگ و پردازش سنگین 🎮", "query_tag": "گیمینگ اسنپدراگون رم"}
                ]
            },
            {
                "step_id": 2,
                "question": "بازه بودجه مدنظر چقدر است؟",
                "options": [
                    {"label": "زیر ۱۰ میلیون تومان (اقتصادی)", "max_price": 10000000},
                    {"label": "بین ۱۰ تا ۲۵ میلیون تومان (ارزش خرید بالا)", "min_price": 10000000, "max_price": 25000000},
                    {"label": "بالای ۲۵ میلیون تومان (پرچمدار)", "min_price": 25000000}
                ]
            }
        ]
    },
    "cctv": {
        "keywords": ["دوربین", "مداربسته", "دوربین مداربسته", "دزدگیر", "امنیتی"],
        "title": "راهنمای تجهیزات امنیتی و دوربین مداربسته",
        "steps": [
            {
                "step_id": 1,
                "question": "محل نصب دوربین کجاست؟",
                "options": [
                    {"label": "فضای باز / پارکینگ (دید در شب ضدآب) 🌧️", "query_tag": "دید در شب ضد آب بولت"},
                    {"label": "داخل مغازه و آپارتمان (دید ۳۶۰ درجه) 🏢", "query_tag": "دام گردان سقفی بی سیم"},
                    {"label": "باغ و ویلا بدون اینترنت ثابت 📡", "query_tag": "سیمکارتی خورشیدی 4G"}
                ]
            }
        ]
    }
}

def detect_ambiguous_intent(user_query: str):
    """
    بررسی اینکه آیا کاربر نیاز کلی و بدون مدل مشخص دارد؟
    کلیدواژه‌ها به صورت کلمه کامل تطبیق داده می‌شوند و درختی که بیشترین کلیدواژه را دارد انتخاب می‌شود
    (مثلاً «دوربین گوشی» به گوشی می‌رود نه دوربین مداربسته).
    """
    query = (user_query or "").lower()
    best_key, best_hits = None, 0
    for cat_key, tree in DIAGNOSTIC_TREES.items():
        hits = sum(1 for kw in tree["keywords"] if has_word(query, kw))
        if hits > best_hits:
            best_key, best_hits = cat_key, hits
    if best_key is None:
        return {"needs_decoupling": False}
    return {
        "needs_decoupling": True,
        "category_key": best_key,
        "tree": DIAGNOSTIC_TREES[best_key]
    }
