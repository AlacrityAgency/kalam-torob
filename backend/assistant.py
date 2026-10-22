"""
دستیار هوشمند کَلَم (Kalam Conversational AI Core)
تحلیل نیات کاربر، غربالگری نیازهای مبهم (INDP)، اجرای ابزارهای تحلیلی و اعمال گاردریل‌های ۵گانه.

گاردریل اصلی: هر پاسخ فقط از داده‌های پایگاه داده ساخته می‌شود. اگر داده کافی نباشد
(مثلاً کالا یا مغازه مشخص نیست یا کالایی پیدا نشد) همین را صادقانه می‌گوید و چیزی نمی‌سازد.
"""

import re
import sqlite3
from typing import Dict, Any, List

from .algorithms.imwp import parse_mall_address
from .algorithms.ip_crp import InPersonCartRouter
from .algorithms.credipay import filter_and_rank_by_credit
from .algorithms.indp import detect_ambiguous_intent
from .algorithms.svdp import compute_stock_certainty, generate_inquiry_dossier
from .algorithms.tfra import find_emergency_fallbacks
from .algorithms.textutil import has_any_word

PANIC_WORDS = ["بسته بود", "بستس", "بسته است", "بسته‌ست", "موجود نداشت", "تموم کرده", "تمام کرده", "پنیک", "panic", "جایگزین"]
ROUTE_WORDS = ["سبد", "سبدم", "مسیر", "خرید حضوری", "چند کالا", "بچین", "پاساژگردی", "لیست"]
SPECIFIC_WORDS = ["مدل", "خرید", "مسیر", "فاکتور", "بچین"]
CREDIT_WORDS = ["اقساط", "اقساطی", "قسطی", "قسط", "اسنپ پی", "اسنپ‌پی", "ترب پی", "ترب‌پی", "تارا", "دیجی پی", "دیجی‌پی", "چک", "اعتباری"]
PROVIDER_WORDS = {
    "snapp_pay": ["اسنپ پی", "اسنپ‌پی", "اسنپپی"],
    "torob_pay": ["ترب پی", "ترب‌پی", "تربپی"],
    "tara": ["تارا"],
    "digi_pay": ["دیجی پی", "دیجی‌پی", "دیجیپی"],
}

# کلماتی که در جستجوی کالا نقشی ندارند
STOPWORDS = {
    "دنبال", "می‌گردم", "میگردم", "می گردم", "قیمت", "هستم", "یه", "یک", "برای", "خوب", "خوبی", "می‌خوام",
    "میخوام", "میخواهم", "می‌خواهم", "رو", "را", "با", "در", "از", "به", "که", "و", "کجا", "بخرم", "خرید",
    "ارزون", "ارزان", "بهترین", "لطفا", "لطفاً", "سلام", "چند", "چنده", "داره", "دارید", "دارین", "مدل",
}


def _query_tokens(text: str) -> List[str]:
    text = text.replace("ي", "ی").replace("ك", "ک")
    tokens = re.findall(r"[\w؀-ۿ‌]+", text)
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1][:5]


class KalamAssistant:
    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn
        self.router = InPersonCartRouter(db_conn)

    def process_message(self, user_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        پردازش پیام خریدار و هدایت به مناسب‌ترین ماژول الگوریتمی
        """
        text = (user_text or "").strip().lower()
        context = context or {}
        cart_ids = context.get("cart_product_ids") or []
        current_hub = context.get("current_hub") or None

        # ۱. درخواست جایگزین / بسته بودن مغازه (TFRA) — پیش از هر چیز، چون فوری است
        if has_any_word(text, PANIC_WORDS):
            return self._panic(context, cart_ids)

        # ۲. بررسی نیاز مبهم و کلیک غربالگر (INDP)
        ambiguous_check = detect_ambiguous_intent(text)
        if ambiguous_check["needs_decoupling"] and not has_any_word(text, SPECIFIC_WORDS):
            tree = ambiguous_check["tree"]
            return {
                "type": "diagnostic_tree",
                "message": "برای اینکه بهترین خرید حضوری رو داشته باشید و وقتتون در پاساژ تلف نشه، به دو سؤال کوتاه پاسخ بدید:",
                "category_key": ambiguous_check["category_key"],
                "diagnostic": tree,
                "suggestions": [opt["label"] for opt in tree["steps"][0]["options"]]
            }

        # ۳. سبد خرید چندقلمی و مسیریابی پاساژ (IP-CRP)
        if has_any_word(text, ROUTE_WORDS):
            return self._route(cart_ids, current_hub)

        # ۴. خرید اقساطی / اعتباری (CrediPay)
        if has_any_word(text, CREDIT_WORDS):
            return self._credit(text, current_hub)

        # ۵. جستجوی کالا در پایگاه داده
        return self._product_search(text, current_hub)

    # ------------------------------------------------------------------

    def _panic(self, context, cart_ids):
        product_id = context.get("active_product_id") or (cart_ids[0] if cart_ids else None)
        shop_id = context.get("active_shop_id")
        if not product_id or not shop_id:
            return {
                "type": "text",
                "message": "برای پیدا کردن جایگزین باید بدانم کدام کالا و کدام مغازه. در صفحه کالا یا برنامه حرکت سبد، کنار همان مغازه دکمه «بسته بود؟» را بزنید تا جایگزین‌های همان طبقه و همان پاساژ را نشان بدهم.",
            }
        fallbacks = find_emergency_fallbacks(self.conn, product_id, shop_id)
        if fallbacks.get("error"):
            return {"type": "text", "message": "این مغازه در پایگاه داده پیدا نشد؛ لطفاً از صفحه کالا دوباره امتحان کنید."}
        return {
            "type": "panic_fallback",
            "message": fallbacks["action_guide"],
            "fallback_data": fallbacks,
            "quick_actions": ["مسیریابی به اولین جایگزین", "تماس فوری با مغازه جایگزین"]
        }

    def _route(self, cart_ids, current_hub):
        if len(cart_ids) == 0:
            return {
                "type": "text",
                "message": "سبد خرید حضوری شما خالی است. کالاهایی را که می‌خواهید با «افزودن به سبد خرید حضوری» اضافه کنید تا مسیر خرید را بچینم.",
            }
        route_result = self.router.solve_cart(cart_ids, preferred_hub=current_hub)
        primary = route_result.get("primary_route")
        if not primary:
            return {
                "type": "text",
                "message": "برای همه اقلام سبد شما فروشگاه حضوری با قیمت ثبت‌شده پیدا نشد.",
            }
        savings = route_result.get("savings")
        savings_msg = f"\n**{savings['description']}**" if savings else ""
        hub_name = primary.get("hub") or "مراکز خرید تهران"
        note = ""
        if current_hub and primary.get("hub") != current_hub:
            note = f"\nدر {current_hub} همه اقلام موجود نبود؛ بهترین مسیر جایگزین را انتخاب کردم."
        return {
            "type": "cart_route",
            "message": f"مسیر خرید حضوری شما در {hub_name} با {primary.get('stops_count', 0)} توقف آماده شد. توقف‌ها از طبقه پایین به بالا و با تحویل کالای سنگین در آخر چیده شده‌اند.{note}{savings_msg}",
            "route": route_result,
            "quick_actions": ["مشاهده برنامه حرکت", "تغییر به استراتژی تک‌فروشگاه"]
        }

    def _credit(self, text, current_hub):
        provider = next((key for key, words in PROVIDER_WORDS.items() if has_any_word(text, words)), None)
        cursor = self.conn.cursor()
        sql = """
            SELECT shop_id, name, address, location_label, payment_options
            FROM shops
            WHERE payment_options IS NOT NULL AND payment_options NOT IN ('', 'null', '[]')
        """
        params = []
        if current_hub:
            sql += " AND location_label = ?"
            params.append(current_hub)
        cursor.execute(sql + " LIMIT 500;", params)
        shops = [
            {"shop_id": r[0], "name": r[1], "address": r[2], "location_label": r[3], "payment_options": r[4]}
            for r in cursor.fetchall()
        ]
        ranked = filter_and_rank_by_credit(shops, required_provider=provider, in_person_only=True)

        credit_shops = [{
            "shop_id": s["shop_id"],
            "name": s["name"],
            "hub": s["location_label"],
            "parsed_address": parse_mall_address(s["address"], s["location_label"]),
            "credit_analysis": s["credit_analysis"],
        } for s in ranked[:6]]

        where = f" در {current_hub}" if current_hub else ""
        if not credit_shops:
            return {"type": "text", "message": f"فروشگاهی با پایانه اقساطی حضوری{where} پیدا نشد."}
        return {
            "type": "credit_shops",
            "message": f"فروشگاه‌های دارای کارتخوان اقساطی حضوری{where}:",
            "shops": credit_shops,
            "quick_actions": ["فقط ترمینال‌های کارتخوان حضوری", "مشاهده کالاهای دارای گارانتی"]
        }

    def _product_search(self, text, current_hub):
        tokens = _query_tokens(text)
        if not tokens:
            return {
                "type": "text",
                "message": "نام کالایی که می‌خواهید را بنویسید؛ مثلاً «ایرپاد پرو» یا «دریل شارژی».",
            }

        cursor = self.conn.cursor()
        products = []
        # FTS5 روی توکن کامل (پیشوندی) جستجو می‌کند تا «بای» با «موبایل» تطبیق نخورد.
        # اول همه توکن‌ها (AND)، اگر نتیجه نداشت هر کدام (OR)
        for joiner in (" ", " OR "):
            fts_query = joiner.join(f'"{t}"*' for t in tokens)
            try:
                cursor.execute(
                    "SELECT product_id FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT 200;",
                    (fts_query,),
                )
                ranked_ids = [r[0] for r in cursor.fetchall()]
            except sqlite3.Error:
                ranked_ids = []
            if ranked_ids:
                placeholders = ",".join(["?"] * len(ranked_ids))
                params = list(ranked_ids)
                hub_cond = ""
                if current_hub:
                    hub_cond = " AND s.location_label = ?"
                    params.append(current_hub)
                cursor.execute(f"""
                SELECT p.product_id, p.persian_title, p.category_name, p.brand_name,
                       min(o.price_toman) as min_price, count(DISTINCT o.shop_id) as shop_count
                FROM products p
                JOIN offers o ON p.product_id = o.product_id AND o.price_toman IS NOT NULL
                JOIN shops s ON o.shop_id = s.shop_id
                WHERE p.product_id IN ({placeholders}){hub_cond}
                GROUP BY p.product_id;
                """, params)
                order = {pid: i for i, pid in enumerate(ranked_ids)}
                products = sorted(cursor.fetchall(), key=lambda r: order[r[0]])[:4]
            if products or len(tokens) == 1:
                break

        query_label = " ".join(tokens)
        where = f" در {current_hub}" if current_hub else ""
        if not products:
            return {
                "type": "product_search",
                "message": f"برای «{query_label}»{where} فروشگاه حضوری پیدا نشد. عبارت کوتاه‌تر یا نام برند را امتحان کنید.",
                "products": [],
            }

        prod_list = []
        for p in products:
            # واکشی ارزان‌ترین آفر حضوری با قیمت معتبر
            cursor.execute("""
            SELECT o.price_toman, o.last_price_changed_at, o.warranty, s.shop_id, s.name, s.address,
                   s.location_label, s.contacts, s.weekly_hours
            FROM offers o
            JOIN shops s ON o.shop_id = s.shop_id
            WHERE o.product_id = ? AND o.price_toman IS NOT NULL
            ORDER BY o.price_toman ASC
            LIMIT 1;
            """, (p[0],))
            best_off = cursor.fetchone()

            dossier = None
            stock_info = None
            if best_off:
                stock_info = compute_stock_certainty(
                    {"price_toman": best_off[0], "last_price_changed_at": best_off[1]},
                    {"weekly_hours": best_off[8]},
                )
                dossier = generate_inquiry_dossier(
                    product_title=p[1],
                    price_toman=best_off[0],
                    shop_name=best_off[4],
                    contacts_raw=best_off[7]
                )

            prod_list.append({
                "product_id": p[0],
                "title": p[1],
                "category": p[2],
                "brand": p[3],
                "min_price": p[4],
                "offline_shops_count": p[5],
                "best_shop": {
                    "shop_id": best_off[3],
                    "name": best_off[4],
                    "address": best_off[5],
                    "hub": best_off[6],
                    "price": best_off[0],
                    "warranty": best_off[2] if best_off[2] and best_off[2] != "null" else None,
                    "parsed_address": parse_mall_address(best_off[5], best_off[6])
                } if best_off else None,
                "stock_info": stock_info,
                "dossier": dossier
            })

        return {
            "type": "product_search",
            "message": f"نتایج خرید حضوری برای «{query_label}»{where}:",
            "products": prod_list,
            "quick_actions": ["افزودن به سبد خرید حضوری", "تنظیم فیلتر مجتمع تجاری", "استعلام تلفنی موجودی"]
        }
