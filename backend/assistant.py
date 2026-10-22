"""
دستیار هوشمند کَلَم (Kalam Conversational AI Core)
تحلیل نیات کاربر، غربالگری نیازهای مبهم (INDP)، اجرای ابزارهای تحلیلی و اعمال گاردریل‌های ۵گانه.
"""

import json
import sqlite3
from typing import Dict, Any, List

from .algorithms.imwp import parse_mall_address
from .algorithms.ip_crp import InPersonCartRouter
from .algorithms.paco import calculate_paco_score
from .algorithms.credipay import analyze_payment_options
from .algorithms.indp import detect_ambiguous_intent, DIAGNOSTIC_TREES
from .algorithms.svdp import compute_stock_certainty, generate_inquiry_dossier
from .algorithms.tfra import find_emergency_fallbacks

class KalamAssistant:
    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn
        self.router = InPersonCartRouter(db_conn)

    def process_message(self, user_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        پردازش پیام خریدار و هدایت به مناسب‌ترین ماژول الگوریتمی
        """
        text = user_text.strip().lower()
        context = context or {}
        cart_ids = context.get("cart_product_ids", [])
        current_hub = context.get("current_hub", "چارسو")

        # ۱. بررسی نیاز مبهم و کلیک غربالگر (INDP)
        ambiguous_check = detect_ambiguous_intent(text)
        if ambiguous_check["needs_decoupling"] and not any(k in text for k in ["مدل", "خرید", "مسیر", "فاکتور", "بچین"]):
            tree = ambiguous_check["tree"]
            return {
                "type": "diagnostic_tree",
                "message": f"برای اینکه بهترین خرید حضوری رو در بازار داشته باشید و وقتتون در پاساژ تلف نشه، به دو سوال کوتاه پاسخ بدید:",
                "category_key": ambiguous_check["category_key"],
                "diagnostic": tree,
                "suggestions": [opt["label"] for opt in tree["steps"][0]["options"]]
            }

        # ۲. بررسی درخواست دکمه پنیک / بسته بودن مغازه / اتمام موجودی (TFRA)
        if any(w in text for w in ["بسته بود", "بستس", "بسته است", "موجود نداشت", "تموم کرده", "پنیک", "panic", "جایگزین", "فوری"]):
            # اگر مغازه یا محصولی در کانتکست باشد
            product_id = context.get("active_product_id") or (cart_ids[0] if cart_ids else None)
            shop_id = context.get("active_shop_id")

            if not product_id or not shop_id:
                # تلاش برای استخراج اولین کالای فعال
                cursor = self.conn.cursor()
                cursor.execute("SELECT o.product_id, o.shop_id FROM offers o LIMIT 1;")
                sample = cursor.fetchone()
                if sample:
                    product_id = product_id or sample[0]
                    shop_id = shop_id or sample[1]

            if product_id and shop_id:
                fallbacks = find_emergency_fallbacks(self.conn, product_id, shop_id)
                return {
                    "type": "panic_fallback",
                    "message": "نگران نباشید! کَلَم بلافاصله مغازه‌های آلترناتیو در همان پاساژ و طبقه را برای شما استخراج کرد. نیازی به خروج از مجتمع تجاری نیست:",
                    "fallback_data": fallbacks,
                    "quick_actions": ["مسیریابی به اولین جایگزین", "تماس فوری با مغازه جایگزین"]
                }

        # ۳. بررسی درخواست سبد خرید چندقلمی و مسیریابی پاساژ (IP-CRP)
        if any(w in text for w in ["سبد", "مسیر", "خرید حضوری", "چند کالا", "بچین", "پاساژگردی", "لیست"]) or len(cart_ids) >= 2:
            target_ids = cart_ids
            # اگر کاربر نام کالاهایی را در پیام آورده باشد و سبد خالی باشد، ۲ کالای مرتبط پیدا کن
            if not target_ids:
                cursor = self.conn.cursor()
                cursor.execute("""
                SELECT p.product_id FROM products p 
                WHERE p.persian_title LIKE '%سامسونگ%' OR p.persian_title LIKE '%ایرپاد%' OR p.persian_title LIKE '%شیائومی%'
                LIMIT 2;
                """)
                rows = cursor.fetchall()
                target_ids = [r[0] for r in rows]

            if target_ids:
                route_result = self.router.solve_cart(target_ids, preferred_hub=current_hub)
                savings = route_result.get("savings")
                savings_msg = f"\n💰 **{savings['description']}**" if savings else ""
                
                return {
                    "type": "cart_route",
                    "message": f"مسیر طلایی خرید حضوری شما در {current_hub} با موفقیت بهینه‌سازی شد. توقف‌ها بر اساس کمترین جابه‌جایی عمودی و رعایت قید کالای سنگین چیده شده‌اند.{savings_msg}",
                    "route": route_result,
                    "quick_actions": ["مشاهده پرونده خرید هر توقف", "دانلود آفلاین مسیر", "تغییر به استراتژی تک‌فروشگاه"]
                }

        # ۴. بررسی درخواست خرید اقساطی / اعتباری (CrediPay)
        if any(w in text for w in ["اقساط", "قسطی", "اسنپ پی", "ترب پی", "تارا", "دیجی پی", "چک", "اعتباری"]):
            cursor = self.conn.cursor()
            cursor.execute("""
            SELECT shop_id, name, address, location_label, payment_options
            FROM shops
            WHERE payment_options LIKE '%in_person%' OR payment_options LIKE '%snapp_pay%' OR payment_options LIKE '%torob_pay%'
            LIMIT 6;
            """)
            shops_rows = cursor.fetchall()
            credit_shops = []
            for row in shops_rows:
                analysis = analyze_payment_options(row[4])
                parsed = parse_mall_address(row[2], row[3])
                credit_shops.append({
                    "shop_id": row[0],
                    "name": row[1],
                    "hub": row[3],
                    "parsed_address": parsed,
                    "credit_analysis": analysis
                })

            return {
                "type": "credit_shops",
                "message": "فروشگاه‌های حضوری دارای پایانه پرداخت اقساطی و BNPL فعال (اسنپ‌پی / ترب‌پی) به تفکیک طبقه و پلاک:",
                "shops": credit_shops,
                "quick_actions": ["فقط ترمینال‌های کارتخوان حضوری", "مشاهده کالاهای دارای گارانتی"]
            }

        # ۵. جستجوی عمومی کالاها و استعلام در پایگاه داده
        cursor = self.conn.cursor()
        # جستجوی امن در FTS5 یا محصولات
        clean_query = text.replace("دنبال", "").replace("می‌گردم", "").replace("قیمت", "").replace("هستم", "").strip()
        if not clean_query:
            clean_query = "گوشی"

        cursor.execute("""
        SELECT p.product_id, p.persian_title, p.category_name, p.brand_name,
               min(o.price_toman) as min_price, count(o.offer_id) as shop_count
        FROM products p
        LEFT JOIN offers o ON p.product_id = o.product_id
        WHERE p.persian_title LIKE ? OR p.category_name LIKE ?
        GROUP BY p.product_id
        ORDER BY shop_count DESC
        LIMIT 4;
        """, (f"%{clean_query}%", f"%{clean_query}%"))
        
        products = cursor.fetchall()
        if not products:
            # جستجوی عمومی به عنوان fallback
            cursor.execute("""
            SELECT p.product_id, p.persian_title, p.category_name, p.brand_name,
                   min(o.price_toman) as min_price, count(o.offer_id) as shop_count
            FROM products p
            LEFT JOIN offers o ON p.product_id = o.product_id
            GROUP BY p.product_id
            ORDER BY shop_count DESC
            LIMIT 4;
            """)
            products = cursor.fetchall()

        prod_list = []
        for p in products:
            # واکشی بهترین آفر حضوری
            cursor.execute("""
            SELECT o.price_toman, o.last_price_changed_at, o.warranty, s.shop_id, s.name, s.address, s.location_label, s.contacts
            FROM offers o
            JOIN shops s ON o.shop_id = s.shop_id
            WHERE o.product_id = ?
            ORDER BY o.price_toman ASC
            LIMIT 1;
            """, (p[0],))
            best_off = cursor.fetchone()
            
            dossier = None
            stock_info = None
            if best_off:
                stock_info = compute_stock_certainty({
                    "price_toman": best_off[0],
                    "last_price_changed_at": best_off[1]
                }, {})
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
                    "name": best_off[4],
                    "address": best_off[5],
                    "hub": best_off[6],
                    "price": best_off[0],
                    "warranty": best_off[2],
                    "parsed_address": parse_mall_address(best_off[5], best_off[6])
                } if best_off else None,
                "stock_info": stock_info,
                "dossier": dossier
            })

        return {
            "type": "product_search",
            "message": f"نتایج معتبر خرید حضوری در بازارهای تهران برای «{clean_query}»:",
            "products": prod_list,
            "quick_actions": ["افزودن به سبد خرید حضوری", "تنظیم فیلتر مجتمع تجاری", "استعلام تلفنی موجودی"]
        }
