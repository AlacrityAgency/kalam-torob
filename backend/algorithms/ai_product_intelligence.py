"""
موتور هوش مصنوعی تحلیل کالا و تولید پویای اقلام مکمل و پرامپت
Universal AI-Driven Product Intelligence & Dynamic Companion Architecture (DCA)

این ماژول جایگزین جداول قواعد ایستا (مانند complementary_rules) است:
۱. تحلیل صفر-نمونه (Zero-Shot) مشخصات هر کالای دلخواه در کاتالوگ میلیونی ترب با هوش مصنوعی.
۲. استخراج ابعاد نیازمندی کارکردی (Consumable, Accessory, Protective, Synergy) و توکن‌های جستجو.
۳. نگاشت عینی و بدون توهم (Grounded Catalog Retrieval) به موجودی واقعی مغازه‌ها در همان پاساژ با الگوریتم PACO.
۴. کش‌گذاری پایدار در دیتابیس (SQLite Persistent Memoization) با پاسخ‌دهی زیر ۲ میلی‌ثانیه برای مراجعات مکرر.
۵. استخراج خودکار سوالات کلیدی خرید حضوری در فروشگاه بدون نیاز به قواعد شرطی دسته‌ای.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .paco import calculate_paco_score
from .prompt_generator import extract_model_and_brand
from .textutil import to_fa_digits

log = logging.getLogger("kalam.ai_product_intel")

# کش حافظه‌ای سطح یک (In-Memory L1 Cache)
_L1_MEMO_CACHE: Dict[str, Dict[str, Any]] = {}
_MAX_L1_SIZE = 5000


def init_product_intelligence_table(conn: sqlite3.Connection) -> None:
    """ایجاد جدول کش پایدار تحلیل هوش مصنوعی برای اجناس کاتالوگ"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_ai_intelligence (
            product_id TEXT PRIMARY KEY,
            category_name TEXT,
            brand_name TEXT,
            product_title TEXT,
            facets_json TEXT,
            prompts_json TEXT,
            product_role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_intel_cat ON product_ai_intelligence(category_name);
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Fallback Heuristic Generator (در صورت قطعی اینترنت یا نبود کلید AI)
# ---------------------------------------------------------------------------

def _heuristic_generate_intelligence(title: str, category: str, brand: Optional[str]) -> Dict[str, Any]:
    """
    تولید قانون‌مند و بدون کرش ابعاد مکمل در صورت عدم دسترسی به API هوش مصنوعی.
    با تحلیل کلمات کلیدی عنوان و دسته‌بندی، ابعاد کارکردی واقعی و سوالات داینامیک کوتاه را می‌سازد.
    """
    clean_cat = (category or "").strip()
    clean_title = (title or "").strip()
    meta = extract_model_and_brand(clean_title, brand)
    model_name = meta.get("display_name") or clean_title[:20]

    facets = []
    prompts = [
        "فاکتور رسمی و گارانتی اصلی شرکتی",
        "تخفیف نقدی پای پوز در خرید حضوری",
        "استعلام پلمپ و گارانتی شرکتی",
    ]

    # ابزارآلات برقی و شارژی
    if any(w in clean_cat for w in ("دریل", "فرز", "اره", "بتن", "پیچ گوشتی", "ابزار", "جوش")):
        facets.append({
            "role": "consumable",
            "facet_name": "لوازم مصرفی و ملحقات دستگاه",
            "search_tokens": ["مته", "تیغ"] if "اره" in clean_cat or "اره" in clean_title else ["مته", "صفحه"],
            "dep_score": 0.90,
            "reason": "ملحقات مصرفی کارگاهی برای راه‌اندازی فوری دستگاه",
        })
        facets.append({
            "role": "protective",
            "facet_name": "عینک و دستکش ایمنی کارگاهی",
            "search_tokens": ["عینک", "ایمنی"],
            "dep_score": 0.80,
            "reason": "سپر محافظت فردی در برابر براده و پرتاب ذرات",
        })
        prompts = [
            f"ست مته دریل {brand or 'رونیکس'}",
            "تست روشن شدن و صدای گیربکس",
            "تخفیف نقدی پای پوز روی متعلقات",
            "عینک ایمنی کارگاهی",
        ]

    # ساعت مچی، هوشمند، عقربه‌ای و دیجیتال
    elif any(w in clean_cat or w in clean_title for w in ("ساعت", "ساعت مچی", "ساعت هوشمند", "مچ بند")):
        facets.append({
            "role": "accessory",
            "facet_name": "بند ساعت سازگار",
            "search_tokens": ["بند", "ساعت"],
            "dep_score": 0.90,
            "reason": "تغییر استایل و تعویض بند متناسب با سلیقه خریدار",
        })
        facets.append({
            "role": "protective",
            "facet_name": "گلس و محافظ صفحه ساعت",
            "search_tokens": ["محافظ", "ساعت"],
            "dep_score": 0.85,
            "reason": "سپر محافظت از صفحه و شیشه ساعت در برابر خط و خش روزمره",
        })
        facets.append({
            "role": "consumable",
            "facet_name": "باتری یا شارژر ساعت",
            "search_tokens": ["شارژر", "ساعت"] if ("هوشمند" in clean_cat or "هوشمند" in clean_title) else ["باتری", "ساعت"],
            "dep_score": 0.85,
            "reason": "تامین انرژی و کارکرد مداوم دستگاه",
        })
        prompts = [
            "بند چرمی ساعت",
            "تست آب‌بندی و سلامت موتور در مغازه",
            "کارت گارانتی معتبر و جعبه اصلی",
            "تخفیف نقدی پای پوز در خرید حضوری",
        ]

    # گوشی، تبلت و لوازم دیجیتال
    elif any(w in clean_cat for w in ("گوشی", "موبایل", "تبلت")):
        facets.append({
            "role": "protective",
            "facet_name": "گلس و محافظ صفحه مقاوم",
            "search_tokens": ["گلس", "محافظ"],
            "dep_score": 0.95,
            "reason": "سپر محافظت از ال‌سی‌دی در برابر ضربه و شکستگی",
        })
        facets.append({
            "role": "protective",
            "facet_name": "قاب و کاور ضربه‌گیر",
            "search_tokens": ["کاور", "قاب"],
            "dep_score": 0.90,
            "reason": "محافظت از بدنه و شیشه دوربین",
        })
        facets.append({
            "role": "consumable",
            "facet_name": "شارژر دیواری فست و کابل اصلی",
            "search_tokens": ["شارژر", "دیواری"],
            "dep_score": 0.85,
            "reason": "راه‌اندازی فوری بدون آسیب به سلامت باتری",
        })
        if "آیفون" in clean_title or "iphone" in clean_title.lower():
            prompts = [
                f"گلس و کاور مناسب {model_name}",
                "شارژر ۲۰ وات اصلی اپل",
                "استعلام پلمپ و رجیستری در سامانه همتا",
                "قیمت فاکتور بدون هزینه اجباری فعال‌سازی",
            ]
        elif "سامسونگ" in clean_title or "شیائومی" in clean_title:
            prompts = [
                f"گلس و کاور مناسب {model_name}",
                "شارژر دیواری فست ۲۵ وات اصلی",
                "استعلام پلمپ و رجیستری در سامانه همتا",
                "قیمت فاکتور بدون هزینه اجباری فعال‌سازی",
            ]
        else:
            prompts = [
                f"گلس و کاور مناسب {model_name}",
                "شارژر دیواری فست و کابل اصلی",
                "استعلام پلمپ و رجیستری در سامانه همتا",
                "قیمت فاکتور بدون هزینه اجباری فعال‌سازی",
            ]

    # لپ‌تاپ و تجهیزات کامپیوتری
    elif any(w in clean_cat for w in ("لپ تاپ", "کامپیوتر", "نوت بوک", "مانیتور")):
        facets.append({
            "role": "accessory",
            "facet_name": "کوله پشتی یا کیف ضربه‌گیر",
            "search_tokens": ["کوله", "کیف"],
            "dep_score": 0.90,
            "reason": "حمل ایمن و محافظت در برابر تکان‌های فیزیکی",
        })
        facets.append({
            "role": "accessory",
            "facet_name": "ماوس بی‌سیم و پد ماوس",
            "search_tokens": ["ماوس"],
            "dep_score": 0.80,
            "reason": "افزایش سرعت و راحتی کاربری",
        })
        prompts = [
            "کوله پشتی لپ تاپ",
            "ماوس بی‌سیم",
            "فاکتور رسمی و گارانتی اصلی شرکتی",
            "تخفیف نقدی پای پوز در خرید حضوری",
        ]

    # وسایل خانه، آشپزخانه و پذیرایی
    elif any(w in clean_cat or w in clean_title for w in ("پذیرایی", "ظروف", "آشپزخانه", "لیوان", "سفره", "پخت", "یکبار مصرف")):
        facets.append({
            "role": "synergy",
            "facet_name": "سفره یکبار مصرف",
            "search_tokens": ["سفره یکبار مصرف"] if ("یکبار مصرف" in clean_cat or "یکبار مصرف" in clean_title or "لیوان" in clean_title) else ["پیش دستی", "بشقاب"],
            "dep_score": 0.85,
            "reason": "تکمیل چیدمان و هماهنگی ست پذیرایی",
        })
        facets.append({
            "role": "consumable",
            "facet_name": "دستکش یکبار مصرف",
            "search_tokens": ["دستکش یکبار مصرف"],
            "dep_score": 0.75,
            "reason": "بهداشت و نظافت در کنار وسایل پذیرایی",
        })
        prompts = [
            f"سفره و ملحقات مناسب {model_name}",
            "استعلام قیمت عمده و بسته‌ای",
            "تخفیف خرید تجمیعی از مغازه",
        ]

    # کفش، کتانی و پوشاک ورزشی
    elif any(w in clean_cat for w in ("کفش", "کتانی", "کتونی", "اسپرت", "رانینگ", "پوشاک")):
        facets.append({
            "role": "accessory",
            "facet_name": "جوراب ورزشی و کفی طبی",
            "search_tokens": ["جوراب"],
            "dep_score": 0.85,
            "reason": "راحتی و بهداشت پا در استفاده مداوم",
        })
        facets.append({
            "role": "accessory",
            "facet_name": "کفی طبی و ضدتعریق",
            "search_tokens": ["کفی", "طبی"],
            "dep_score": 0.75,
            "reason": "افزایش راحتی و کاهش خستگی پا",
        })
        prompts = [
            f"جوراب نانو و کفی طبی مناسب {model_name}",
            "امکان تست پاخور و سایزبندی در مغازه",
            "ضمانت اصالت و سلامت دوخت",
            "تخفیف خرید جوراب همراه کفش",
        ]

    # سایر کالاهای نامشخص: در صورت عدم دسترسی به AI آنلاین، هیچ فرض غلطی مثل کاور تحمیل نمی‌شود
    else:
        facets = []

    return {
        "product_role": f"کالای {clean_cat or 'فروشگاهی'} مدل {model_name}",
        "facets": facets,
        "in_store_prompts": prompts,
        "source": "heuristic",
    }


# ---------------------------------------------------------------------------
# AI Gateway Connector (Arvan AlaaS / OpenAI / Anthropic)
# ---------------------------------------------------------------------------

_AI_SYSTEM_PROMPT = """You are a senior Tehran bazaar commercial strategist, retail psychologist, and in-person shopping assistant for Torob (ترب).
Given a physical product sold in Tehran bazaars and malls (Chaharsoo, Alaeddin, Hasan Abad, Lalehzar, Shoush, Payetakht, etc.):
Analyze the product using the BAP-LLM (Behavioral & Analytical Purchasing) framework:
1. Cognitive Trio Facets:
   - "protective" (سپر محافظت از سرمایه / Loss Aversion Shield): cases, glass, surge protector, gloves, safety glasses, etc.
   - "consumable" (راه‌اندازی فوری در محل / Out-of-box Readiness): wall chargers, drill bits, blades, beans, cables, etc.
   - "synergy" (ارتقای کاربری و بسته تجمیعی / Ecosystem & Bundle): stylus, wireless mouse, headsets, specialized stands.
2. In-Store Bazaar Battle Prompts:
   - Anti-hidden-fee probe (سپر ضد هزینه پنهان فعال‌سازی و نرم‌افزار)
   - Same-store bundle discount lever (اهرم چانه‌زنی و تخفیف نقدی پای پوز در صورت تجمیع فاکتور)
   - Unboxing, seal & warranty verification (استعلام سلامت پلمپ و گارانتی شرکتی قبل از پرداخت)

You must output ONLY valid JSON matching this schema:
{
  "product_role": "brief description of product utility in Persian (max 10 words)",
  "facets": [
    {
      "role": "consumable" | "protective" | "synergy" | "accessory",
      "facet_name": "Clear Persian companion name (e.g. تیغ اره دیسکی, دانه قهوه, کابل رابط)",
      "search_tokens": ["token1", "token2"],  // 2-3 Persian catalog search tokens
      "dep_score": 0.85,                      // float between 0.60 and 1.00
      "reason": "One short Persian sentence explaining why a customer in this shop needs this"
    }
  ],
  "in_store_prompts": [
    "3 to 4 Persian battle-tested questions to ask the seller (covering warranty/seal, bundle discount, and anti-hidden fees)"
  ]
}

Rules:
1. Provide 2 to 4 high-value facets. Do not recommend identical items or competitors (e.g. for a phone do NOT recommend another phone).
2. For search_tokens, pick exact Persian catalog search words (e.g. ["شارژر", "دیواری"], ["تیغ", "اره"], ["کارت", "حافظه"]).
3. In-store prompts must empower the buyer with confidence and negotiation leverage in Iranian offline shops.
"""


def _call_ai_product_analyzer(product_title: str, category_name: str, brand_name: Optional[str],
                              price: Optional[int], mall_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """فراخوانی درگاه هوش مصنوعی با ساختار خروجی JSON"""
    api_key = os.environ.get("ARVAN_AI_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key or os.environ.get("KALAM_LLM", "on") == "off":
        return None

    base_url = (os.environ.get("ARVAN_AI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://arvancloudai.ir/gateway/models").rstrip("/")
    model = os.environ.get("ARVAN_AI_MODEL") or os.environ.get("OPENAI_MODEL") or "Gemini-2.5-Flash"
    endpoint = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url

    user_payload = {
        "title": product_title,
        "category": category_name,
        "brand": brand_name,
        "price_toman": price,
        "mall": mall_name or "بازار تهران",
    }

    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        req_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": _AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this product for Tehran in-person shopping:\n{json.dumps(user_payload, ensure_ascii=False)}"}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=httpx.Timeout(12.0, connect=3.0)) as client:
            resp = client.post(endpoint, json=req_body, headers=headers)
            if resp.status_code != 200:
                log.warning("AI Product Analyzer HTTP %d: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"].strip()
            if raw_content.startswith("```"):
                raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
                raw_content = re.sub(r"\s*```$", "", raw_content).strip()
            parsed = json.loads(raw_content)
            if isinstance(parsed, dict) and "facets" in parsed:
                parsed["source"] = "ai"
                return parsed
    except Exception as e:
        log.warning("AI Product Analyzer error: %s; falling back to heuristic", e)
    return None


# ---------------------------------------------------------------------------
# Public API: Product Intelligence with 2-Tier Memoization
# ---------------------------------------------------------------------------

def get_product_intelligence(
    conn: sqlite3.Connection,
    product: Dict[str, Any],
    mall_name: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    دریافت مشخصات تحلیلی هوش مصنوعی برای هر کالای دلخواه.
    اولین بار از طریق AI ساخته شده و در SQLite کش می‌شود؛ دفعات بعدی زیر ۲ میلی‌ثانیه تحویل داده می‌شود.
    """
    pid = product.get("product_id") or ""
    title = product.get("persian_title") or product.get("title") or ""
    category = product.get("category_name") or product.get("category") or ""
    brand = product.get("brand_name") or product.get("brand")
    price = product.get("price") or product.get("price_toman")

    # بررسی کش L1 حافظه
    if not force_refresh and pid and pid in _L1_MEMO_CACHE:
        return _L1_MEMO_CACHE[pid]

    # اطمینان از وجود جدول کش در SQLite
    init_product_intelligence_table(conn)

    # بررسی کش L2 پایگاه داده
    if not force_refresh and pid:
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT facets_json, prompts_json, product_role, source
            FROM (
                SELECT facets_json, prompts_json, product_role, 'db' as source
                FROM product_ai_intelligence WHERE product_id = ?
            )
        """, (pid,)).fetchone()

        if not row and category:
            # بررسی تطابق دسته اگر کالای دقیقی ثبت نشده باشد
            row = cursor.execute("""
                SELECT facets_json, prompts_json, product_role, 'db_cat' as source
                FROM product_ai_intelligence
                WHERE category_name = ? AND category_name != ''
                LIMIT 1
            """, (category,)).fetchone()

        if row:
            try:
                facets = json.loads(row[0]) if row[0] else []
                prompts = json.loads(row[1]) if row[1] else []
                # تنها در صورتی که ابعاد خالی نباشد از کش استفاده کن (جلوگیری از کش مسموم)
                if facets:
                    # اگر از کش دسته‌بندی آمده باشد یا سوالات با مدل فعلی ناهمخوان/طولانی باشند،
                    # سوالات به صورت کاملاً پویا و متناسب با همین مدل تولید می‌شوند
                    need_fresh_prompts = False
                    if row[3] == "db_cat":
                        need_fresh_prompts = True
                    elif not prompts or any("لوازم جانبی و متعلقات سازگار با «" in p or len(p) > 55 for p in prompts):
                        need_fresh_prompts = True
                    elif "آیفون" in title and any("سامسونگ" in p for p in prompts):
                        need_fresh_prompts = True
                    elif "سامسونگ" in title and any("آیفون" in p for p in prompts):
                        need_fresh_prompts = True

                    if need_fresh_prompts:
                        intel_dyn = _heuristic_generate_intelligence(title, category, brand)
                        prompts = intel_dyn.get("in_store_prompts") or []

                    res = {
                        "product_role": row[2] or f"کالای {category}",
                        "facets": facets,
                        "in_store_prompts": prompts,
                        "source": row[3],
                    }
                    if len(_L1_MEMO_CACHE) < _MAX_L1_SIZE:
                        _L1_MEMO_CACHE[pid] = res
                    return res
            except Exception as e:
                log.warning("Corrupt JSON in product_ai_intelligence for %s: %s", pid, e)

    # استنباط پویا با هوش مصنوعی (Zero-Shot AI)
    intel = _call_ai_product_analyzer(title, category, brand, price, mall_name)
    if not intel or not intel.get("facets"):
        intel = _heuristic_generate_intelligence(title, category, brand)

    # ذخیره دائمی در کش دیتابیس (Memoize) - فقط در صورت معتبر بودن ابعاد
    if pid and intel.get("facets"):
        try:
            conn.execute("""
                INSERT OR REPLACE INTO product_ai_intelligence
                (product_id, category_name, brand_name, product_title, facets_json, prompts_json, product_role)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                pid,
                category,
                brand,
                title,
                json.dumps(intel.get("facets", []), ensure_ascii=False),
                json.dumps(intel.get("in_store_prompts", []), ensure_ascii=False),
                intel.get("product_role", ""),
            ))
            conn.commit()
        except sqlite3.Error as e:
            log.warning("Failed to memoize AI product intelligence: %s", e)

    if pid and intel.get("facets") and len(_L1_MEMO_CACHE) < _MAX_L1_SIZE:
        _L1_MEMO_CACHE[pid] = intel

    return intel


# ---------------------------------------------------------------------------
# Grounded Catalog Retrieval: پیوند ابعاد انتزاعی به موجودی فیزیکی واقعی
# ---------------------------------------------------------------------------

def find_grounded_complementary_items(
    conn: sqlite3.Connection,
    base_product: Dict[str, Any],
    base_shop: Optional[Dict[str, Any]] = None,
    limit: int = 8,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    استخراج اقلام مکمل عینی و موجود در پایگاه داده بر اساس تحلیل هوش مصنوعی و امتیازدهی PACO.
    خروجی: (فهرست کالاهای مکمل وزن‌دهی شده، سوالات آماده مرتبط با کالا)
    """
    base_shop = base_shop or {}
    base_pid = base_product.get("product_id") or ""
    base_cat = base_product.get("category_name") or base_product.get("category") or ""
    shop_id = base_shop.get("shop_id") or ""
    mall_label = base_shop.get("location_label") or ""

    # ۱. دریافت ابعاد مکمل از هوش مصنوعی
    intel = get_product_intelligence(conn, base_product, mall_name=mall_label)
    facets = intel.get("facets") or []
    in_store_prompts = intel.get("in_store_prompts") or []

    if not facets:
        return [], in_store_prompts

    best_by_product: Dict[str, Dict[str, Any]] = {}
    cursor = conn.cursor()

    # ۲. برای هر بعد، جستجوی FTS در کاتالوگ واقعی فروشگاه‌ها
    for facet in facets:
        search_tokens = facet.get("search_tokens") or []
        if not search_tokens:
            continue

        dep_score = float(facet.get("dep_score") or 0.75)
        facet_name = facet.get("facet_name") or "قلم مکمل"
        facet_reason = facet.get("reason") or "سازگار با این کالا"
        facet_role = facet.get("role") or "accessory"

        # استخراج شناسه‌های منطبق از FTS برای عبارات و توکن‌های ابعاد
        matched_pids = []
        for token_item in search_tokens:
            words = [w for w in re.findall(r"\w+", token_item) if len(w) > 1]
            if not words:
                continue
            fts_query = " AND ".join(f'"{w}"*' for w in words)
            try:
                cursor.execute(
                    "SELECT product_id FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT 100;",
                    (fts_query,)
                )
                matched_pids.extend(r[0] for r in cursor.fetchall() if r[0] != base_pid)
            except sqlite3.Error:
                continue

        # ترکیب توکن‌های کلیدی بعد
        flat_words = list(dict.fromkeys(w for t in search_tokens for w in re.findall(r"\w+", t) if len(w) > 1))
        if len(flat_words) >= 2 and len(matched_pids) < 20:
            combo_query = " AND ".join(f'"{w}"*' for w in flat_words[:2])
            try:
                cursor.execute(
                    "SELECT product_id FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT 100;",
                    (combo_query,)
                )
                matched_pids.extend(r[0] for r in cursor.fetchall() if r[0] != base_pid)
            except sqlite3.Error:
                pass

        matched_pids = list(dict.fromkeys(matched_pids))
        if not matched_pids:
            continue

        placeholders = ",".join("?" * len(matched_pids))
        candidates = cursor.execute(f"""
            SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, o.price_toman,
                   o.last_price_changed_at, s.shop_id, s.name, s.address, s.location_label
            FROM products p
            JOIN offers o ON p.product_id = o.product_id
            JOIN shops s ON o.shop_id = s.shop_id
            WHERE p.product_id IN ({placeholders})
              AND o.price_toman IS NOT NULL AND o.is_copy = 0 AND o.price_suspect = 0
            ORDER BY (s.shop_id = ?) DESC, (s.location_label = ?) DESC, o.price_toman ASC
            LIMIT 60
        """, (*matched_pids, shop_id, mall_label)).fetchall()

        # دسته‌های کالای اصلی مستقل که نباید به عنوان قلم مکمل به کالا پیشنهاد شوند
        _MAIN_DEVICE_CATS = {
            "گوشی موبایل", "تبلت", "لپ تاپ", "کامپیوتر",
            "ساعت و مچ بند هوشمند", "ساعت مچی عقربه‌ ای و دیجیتالی",
            "دوربین عکاسی و فیلم برداری"
        }

        # تشخیص حوزه کالا برای جلوگیری از تلاقی دامنه‌های نامرتبط (مثلاً پیش‌بند جوشکاری برای ساعت)
        base_text = f"{base_product.get('title', '')} {base_cat}"
        is_watch_base = any(w in base_text for w in ("ساعت", "واچ", "مچ بند", "مچ‌بند"))
        is_tool_base = any(w in base_text for w in ("دریل", "فرز", "اره", "بتن", "جوش", "ابزار"))
        is_phone_base = any(w in base_text for w in ("گوشی", "موبایل", "آیفون", "سامسونگ"))
        is_tableware_base = any(w in base_text for w in ("ظروف", "یکبار مصرف", "لیوان", "سفره", "پذیرایی"))

        for c in candidates:
            cand_title = c[1] or ""
            cand_cat = c[2] or ""

            # ۱. جلوگیری از پیشنهاد کالای کاملاً هم‌دسته (رقیب/جانشین)
            if cand_cat and cand_cat == base_cat:
                continue

            # ۲. اگر کالا در دسته‌های مادر است، تنها در صورتی مجاز است که مشخصاً عنوان جانبی/متعلقات داشته باشد
            if cand_cat in _MAIN_DEVICE_CATS:
                first_word = cand_title.split()[0] if cand_title.split() else ""
                if not (first_word in ("بند", "کاور", "قاب", "گلس", "محافظ", "شارژر", "کابل", "باتری", "پایه", "هولدر") or "مناسب برای" in cand_title):
                    continue

            # ۳. هماهنگی دامنه کالا
            if is_watch_base:
                if not any(w in cand_cat or w in cand_title for w in ("ساعت", "واچ", "مچ بند", "مچ‌بند")):
                    continue
            elif is_tool_base:
                if any(w in cand_cat for w in ("لباس", "پوشاک", "اسباب بازی", "طلا", "زیورآلات")):
                    continue
            elif is_phone_base:
                if any(w in cand_cat for w in ("ابزار", "لباس", "کفش", "خودرو", "برق ساختمان", "سیم و کابل برق")):
                    continue
            elif is_tableware_base:
                if any(w in cand_cat for w in ("ایمنی", "ملحفه", "روتختی", "کلاه", "لباس", "پوشاک", "حوله", "صنعتی", "خودرو", "مکانیک", "واشر", "ابزار", "پزشکی", "جراحی", "درمانی", "بیمارستان", "بهداشتی")):
                    continue
                if "کاسه نمد" in cand_title:
                    continue

            cand = {
                "product_id": c[0],
                "title": c[1],
                "category_name": c[2],
                "brand_name": c[3],
                "price_toman": c[4],
                "last_price_changed_at": c[5],
                "shop_id": c[6],
                "shop_name": c[7],
                "address": c[8],
                "location_label": c[9],
                "dep_score": dep_score,
                "role": facet_role,
                "cognitive_role": facet_role,
                "complementary_role": facet_role,
                "facet_name": facet_name,
                "ai_reason": facet_reason,
            }

            score, details = calculate_paco_score(base_product, base_shop, cand)
            if score <= 0:
                continue

            current = best_by_product.get(cand["product_id"])
            if current and current["paco_score"] >= score:
                continue

            cand.update({
                "paco_score": round(score, 4),
                "location_type": details.get("location_type"),
                "location_desc": details.get("location_description") or details.get("loc_desc"),
                "freshness_badge": details.get("freshness_badge"),
                "omega_economic": details.get("omega_economic"),
                "bundle_bonus": details.get("bundle_bonus", 1.0),
                "bundle_eligible": details.get("bundle_eligible", False),
                "cognitive_role": details.get("cognitive_role", facet_role),
                "cognitive_category": details.get("cognitive_category", "لوازم جانبی مکمل"),
                "bargaining_tip": details.get("bargaining_tip"),
            })
            best_by_product[cand["product_id"]] = cand

    scored = sorted(best_by_product.values(), key=lambda x: x["paco_score"], reverse=True)
    return scored[:limit], in_store_prompts


# ---------------------------------------------------------------------------
# In-Store Shopping Consultation & Warranty Advisory Engine
# ---------------------------------------------------------------------------

def answer_consultation_inquiry(
    conn: sqlite3.Connection,
    query: str,
    active_product_id: Optional[str] = None,
    active_shop_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    پاسخ هوشمند، محافظت‌کننده از منافع خریدار و دقیق به سوالات استعلام کالا،
    شرایط گارانتی و ضمانت شرکتی، هزینه‌های پنهان، تست حضوری و تخفیف پای پوز.
    """
    from ..search import normalize_text

    product = None
    shop = None
    cursor = conn.cursor()

    if active_product_id:
        cursor.execute("""
            SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, p.image_urls,
                   o.price_toman, s.shop_id, s.name, s.location_label, s.address, o.warranty, s.weekly_hours
            FROM products p
            LEFT JOIN offers o ON p.product_id = o.product_id AND o.is_copy = 0 AND o.price_suspect = 0
            LEFT JOIN shops s ON o.shop_id = s.shop_id
            WHERE p.product_id = ?
            ORDER BY o.price_toman ASC LIMIT 1
        """, (active_product_id,))
        row = cursor.fetchone()
        if row:
            product = {
                "product_id": row[0],
                "title": row[1],
                "category": row[2],
                "brand": row[3],
                "image_url": row[4],
                "min_price": row[5],
                "offline_shops_count": 1,
                "best_shop": {
                    "shop_id": row[6],
                    "name": row[7],
                    "price": row[5],
                    "parsed_address": {"mall_name": row[8] or "تهران", "floor_label": "فروشگاه حضوری"},
                    "hours": "ساعت کاری ثبت‌شده",
                    "distance_km": None,
                }
            }
            shop = {
                "shop_id": row[6],
                "name": row[7],
                "location_label": row[8],
                "address": row[9],
                "warranty": row[10],
            }

    # ۱. تلاش برای دریافت پاسخ زنده و مقتدر از مدل هوش مصنوعی آنلاین (Arvan AlaaS / OpenAI)
    api_key = os.environ.get("ARVAN_AI_KEY") or os.environ.get("OPENAI_API_KEY")
    ai_response = None
    if api_key and os.environ.get("KALAM_LLM", "on") != "off":
        base_url = (os.environ.get("ARVAN_AI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://arvancloudai.ir/gateway/models").rstrip("/")
        model = os.environ.get("ARVAN_AI_MODEL") or os.environ.get("OPENAI_MODEL") or "Gemini-2.5-Flash"
        endpoint = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url

        prod_title = product["title"] if product else "کالای مدنظر"
        prod_cat = product["category"] if product else "بازار"
        shop_name = shop["name"] if shop else "فروشگاه"
        hub = shop.get("location_label") if shop else "تهران"
        price_val = product.get("min_price") if product else None
        price_str = f"{to_fa_digits(f'{int(price_val):,}')} تومان" if price_val else "استعلام روز"
        warranty_raw = shop.get("warranty") if shop else None

        sys_prompt = f"""شما «کَلَم» (دستیار تخصصی خرید حضوری ترب و مشاور امین خریدار در بازار تهران) هستید.
خریدار این سوال، استعلام یا چالش خرید حضوری را پرسیده است:
«{query}»

اطلاعات کالای در حال بررسی:
- کالا: {prod_title}
- دسته‌بندی: {prod_cat}
- فروشگاه: {shop_name} ({hub})
- قیمت: {price_str}
- گارانتی ثبت‌شده فروشگاه در ترب: {warranty_raw or 'ثبت نشده'}

پاسخی کاملاً کاربردی، محافظ منافع خریدار، دقیق و گرم به زبان فارسی (حداکثر ۱۶۰ کلمه) در ۲ تا ۳ بخش ارائه دهید:
۱. پاسخ مستقیم و شفاف به سوال خریدار درباره این کالا/گارانتی/تخفیف/تست.
۲. شرایط استاندارد بازار (چه مواردی تحت پوشش است و چه مواردی استثناست یا حق قانونی خریدار است).
۳. چک‌لیست استعلام پای پیشخوان قبل از کشیدن کارت (فاکتور، مهر، تست در حضور فروشنده).
از ایموجی‌های مناسب و قالب‌بندی خوانا (بولت‌پوینت و پررنگ) استفاده کنید."""

        try:
            import httpx
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.3,
            }
            with httpx.Client(timeout=httpx.Timeout(9.0, connect=2.5)) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    ai_response = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning("Consultation AI call failed: %s; falling back to heuristic", e)

    # ۲. موتور پشتیبان دانشی هیوریستیک در صورت آفلاین بودن یا قطعی شبکه
    if not ai_response:
        norm_q = normalize_text(query)
        prod_title = product["title"] if product else "این کالا"
        shop_name = shop["name"] if shop else "فروشگاه"

        # موضوع الف: گارانتی، ضمانت شرکتی و سلامت موتور ساعت
        if any(w in norm_q for w in ("گارانتی", "ضمانت", "وارانتی", "موتور")):
            warranty_text = "گارانتی فروشگاه"
            if shop and shop.get("warranty"):
                try:
                    w_obj = json.loads(shop["warranty"]) if isinstance(shop["warranty"], str) else shop["warranty"]
                    if w_obj.get("description"):
                        warranty_text = f"«{w_obj['description']}»"
                except Exception:
                    pass
            ai_response = f"""سلام! من **کَلَم**، مشاور خرید حضوری شما در ترب هستم. در خصوص شرایط ضمانت و گارانتی **{prod_title}**:\n\n"""
            if shop:
                ai_response += f"📋 **وضعیت گارانتی ثبت‌شده:** فروشگاه **{shop_name}** در ترب گارانتی {warranty_text} را برای این کالا قید کرده است.\n\n"
            ai_response += """✅ **موارد تحت پوشش گارانتی معتبر موتور ساعت:**
• کارکرد دقیق و روان موتور (عدم توقف ناگهانی، نخوابیدن ساعت، یا جلو/عقب افتادن خارج از استاندارد).
• عیوب ساختاری ناشی از خط مونتاژ یا نقص فنی کارخانه سازنده.
• تعویض باتری اولیه در بازه مشخص (در مدل‌های باتری‌خور/کوارتز).

❌ **موارد خارج از تعهد گارانتی:**
• آسیب‌های فیزیکی، ضربه شدید، خط‌وخش بدنه و شکستگی شیشه.
• استهلاک طبیعی، پارگی یا تغییر رنگ بند چرمی/فلزی بر اثر تعریق و استفاده روزمره.
• نفوذ آب در صورتی که دسته کوک باز مانده باشد یا ساعت فاقد استاندارد مقاومت در برابر آب باشد.

💡 **چک‌لیست پای پیشخوان قبل از پرداخت:**
۱. **کارت ضمانت رسمی:** برگه یا کارت گارانتی ممهور به مهر فروشگاه با درج تاریخ روز و شماره سریال را تحویل بگیرید.
۲. **تست عملکرد در حضور فروشنده:** سلامت کوک، گردش نرم عقربه‌ها و عملکرد تقویم را تست کنید.
۳. **درج در فاکتور:** حتماً بخواهید عبارت «ضمانت اصالت و سلامت موتور ساعت به مدت ... ماه» در فاکتور رسمی قید شود."""

        # موضوع ب: فعال‌سازی، هزینه‌های پنهان، ریجستری و همتا
        elif any(w in norm_q for w in ("فعال", "ریجستر", "رجیستر", "همتا", "نرم افزار", "نرم‌افزار", "هزینه")):
            ai_response = f"""⚠️ **سپر ضد هزینه پنهان (توصیه کَلَم پای پیشخوان):**\n\n"""
            ai_response += """• **فعال‌سازی و ریجستری کاملاً رایگان است:** استعلام شناسه IMEI و فعال‌سازی در سامانه همتا (`*7777#`) هیچ هزینه‌ای ندارد و حق قانونی شماست.
• **پکیج نرم‌افزاری اجباری ممنوع:** پرداخت هرگونه وجه اضافی بابت «نصب برنامه»، «آپدیت اجباری» یا «کارمزد فعال‌سازی» غیرقانونی است.
• **شرط قبل از پرداخت:** از فروشنده بخواهید پلمپ جعبه جلوی خودتان باز شود و فاکتور دقیقاً مطابق با قیمت اعلام‌شده کالا صادر گردد."""

        # موضوع ج: تخفیف نقدی پای پوز و چانه‌زنی تجمیع فاکتور
        elif any(w in norm_q for w in ("تخفیف", "پای پوز", "بردارم", "چانه")):
            ai_response = f"""🤝 **اهرم چانه‌زنی و تخفیف پای پوز در بازار:**\n\n"""
            ai_response += """• **حاشیه سود لوازم جانبی:** سود قاب، گلس، بند و شارژر در بازار ۴۰ تا ۶۰ درصد است، در حالی که سود دستگاه اصلی ناچیز است.
• **تاکتیک تجمیع:** به فروشنده بگویید «اگر لوازم جانبی را هم از خودتان بردارم، روی سرجمع فاکتور ۵ تا ۱۰ درصد تخفیف نقدی پای پوز می‌خواهم».
• **گزینه جایگزین:** اگر تخفیف نقدی نداد، یک قلم جانبی (مانند گلس یا محافظ) را به عنوان هدیه خرید نقدی دریافت کنید."""

        # موضوع د: تست فیزیکی و آب‌بندی در مغازه
        else:
            ai_response = f"""🛠️ **راهنمای بررسی فیزیکی پای پیشخوان برای {prod_title}:**\n\n"""
            ai_response += """۱. **تست ارگونومی روی دست:** وزن، قفل بند و هماهنگی سایز را بررسی کنید. تنظیم سایز بند در اکثر مغازه‌ها رایگان انجام می‌شود.
۲. **سلامت کلیدها و اهرم‌ها:** پیچ تنظیم را در حالت‌های مختلف بچرخانید؛ عملکرد باید کاملاً نرم و بدون گیرکردن باشد.
۳. **مهلت تست فنی:** از فروشنده بخواهید حداقل ۴۸ ساعت مهلت تست در فاکتور رسمی قید نماید."""

    follow_up_prompts = [
        "استعلام تلفنی با فروشگاه برای هماهنگی مراجعه",
        "چطور سلامت فیزیکی را در مغازه تست کنم؟",
        "کدوم پاساژهای بازار این کالا رو دارند؟",
    ]

    return {
        "message": ai_response,
        "active_product": product,
        "suggested_prompts": follow_up_prompts,
    }
