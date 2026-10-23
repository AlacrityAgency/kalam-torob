"""
مجموعه آزمون‌های سیستم پیشنهادهای فروش‌محور (Cross-Sell)، تطابق موجودی همان مغازه (SSIM) و رتبه‌بندی اصالت کالا (SQAS)
Sales-Centric Cross-Sell Prompts, Same-Shop Inventory Matching & Shop Quality Scoring Tests
"""

import sqlite3
import unittest

from backend.algorithms.ai_product_intelligence import (
    find_grounded_complementary_items,
    get_product_intelligence,
    score_offer_quality,
)
from backend.algorithms.prompt_generator import generate_dynamic_prompts
from backend.assistant import KalamAssistant


class TestCrossSellAndQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect("torob.db")
        cls.assistant = KalamAssistant(cls.conn)

    def test_01_phone_sales_prompts(self):
        """آزمون تولید سوالات فروش‌محور و مکمل برای گوشی‌های هوشمند (آیفون ۱۸ پرو و ...)"""
        product = {
            "product_id": "test_iphone_18",
            "persian_title": "گوشی موبایل اپل مدل iPhone 18 Pro ظرفیت 256 گیگابایت",
            "category_name": "گوشی موبایل",
            "brand_name": "اپل",
            "min_price_toman": 95000000,
        }
        shop = {"name": "فروشگاه اپل سنتر پایتخت", "location_label": "مجتمع کامپیوتر پایتخت"}
        prompts = generate_dynamic_prompts(product, shop, mall_name="پایتخت")

        self.assertGreaterEqual(len(prompts), 3)
        joined = " ".join(prompts)

        # باید شامل پیشنهاد کاور یا گلس سازگار با مدل دقیق باشد
        self.assertTrue(any(w in joined for w in ("کاور", "گلس", "قاب", "ضد ضربه")))
        # باید شامل شارژر ۲۰ وات اصلی باشد
        self.assertTrue(any(w in joined for w in ("شارژر", "کلگی", "آداپتور")))
        # باید شامل استعلام موجودی یکجای همان مغازه باشد
        self.assertIn("همین مغازه", joined)
        # باید شامل استعلام جنس بهتر و گارانتی معتبرتر باشد
        self.assertIn("جنس بهتر", joined)

        # نباید هیچ سوال بازجویی یا تست دفاعی وجود داشته باشد
        self.assertNotIn("به برق بزنید", joined)
        self.assertNotIn("جعبه را پلمپ", joined)
        self.assertNotIn("هزینه اجباری", joined)

    def test_02_samovar_sales_prompts(self):
        """آزمون تولید سوالات فروش‌محور برای لوازم خانگی و سماور برقی"""
        product = {
            "product_id": "test_samovar_15l",
            "persian_title": "سماور برقی 15 لیتری صنعتی استیل",
            "category_name": "سماور",
            "brand_name": "پارس استیل",
            "min_price_toman": 4200000,
        }
        intel = get_product_intelligence(self.conn, product, mall_name="میدان شوش")
        prompts = intel.get("in_store_prompts", [])

        self.assertGreaterEqual(len(prompts), 3)
        joined = " ".join(prompts)

        # باید اقلام فروش و نگهداری کالا پیشنهاد شود
        self.assertTrue(any(w in joined for w in ("جرم‌گیر", "رسوب‌زدا", "محافظ برق", "قوری")))
        # باید موجودی همان مغازه و رتبه‌بندی جنس بهتر پرسیده شود
        self.assertIn("همین مغازه", joined)
        self.assertIn("جنس بهتر", joined)

        # عبارات غلط قدیمی نباید باشند
        self.assertNotIn("چشم من به برق بزنید", joined)
        self.assertNotIn("المنت و ترموستات", joined)

    def test_03_quality_scoring_formula(self):
        """آزمون فرمول SQAS برای ارزیابی اصالت و گارانتی رسمی شرکتی"""
        # مغازه معتبر با گارانتی رسمی ۱۸ ماهه
        official_offer = {
            "price_toman": 15000000,
            "warranty": '{"provider": "شرکتی", "period_months": 18, "description": "گارانتی رسمی ۱۸ ماهه"}',
            "is_copy": 0,
            "price_suspect": 0,
        }
        verified_shop = {"name": "فروشگاه مرکزی مدیا پردازش", "is_verified": 1}
        q_score, q_badge, reasons = score_offer_quality(official_offer, verified_shop)

        self.assertGreaterEqual(q_score, 0.85)
        self.assertIn("گارانتی معتبر شرکتی", q_badge)
        self.assertIn("گارانتی رسمی و معتبر شرکتی", reasons)

        # کالای کپی و فاقد گارانتی
        copy_offer = {
            "price_toman": 10000000,
            "warranty": None,
            "is_copy": 1,
            "price_suspect": 0,
        }
        unverified_shop = {"name": "فروشگاه متفرقه بازار", "is_verified": 0}
        q_copy, badge_copy, copy_reasons = score_offer_quality(copy_offer, unverified_shop)

        self.assertLess(q_copy, 0.40)
        self.assertIn("نسخه غیراصل / کپی", badge_copy)

    def test_04_same_shop_matching_boost(self):
        """آزمون الگوریتم SSIM: اولویت‌دهی و برچسب‌گذاری اقلام موجود در همان مغازه"""
        cursor = self.conn.cursor()
        # پیدا کردن یک مغازه که حداقل دو کالا دارد
        shop_row = cursor.execute("""
            SELECT s.shop_id, s.name, s.address, s.location_label, p.product_id, p.persian_title, p.category_name, p.brand_name, o.price_toman
            FROM shops s
            JOIN offers o ON s.shop_id = o.shop_id
            JOIN products p ON o.product_id = p.product_id
            GROUP BY s.shop_id
            HAVING COUNT(DISTINCT o.product_id) >= 2
            LIMIT 1;
        """).fetchone()

        if shop_row:
            shop_id, shop_name, addr, hub, pid, ptitle, cat, brand, price = shop_row
            base_product = {
                "product_id": pid,
                "title": ptitle,
                "category_name": cat,
                "brand_name": brand,
                "price": price or 1000000,
            }
            base_shop = {"shop_id": shop_id, "name": shop_name, "address": addr, "location_label": hub}

            recs, _ = find_grounded_complementary_items(self.conn, base_product, base_shop, limit=6)
            same_shop_items = [r for r in recs if r.get("is_same_shop")]

            # اگر همان فروشگاه کالای سازگار داشته باشد، باید برچسب موجود در همین مغازه داشته باشد
            for item in same_shop_items:
                self.assertIn("همین مغازه", item.get("same_shop_badge", ""))
                self.assertTrue(item.get("bundle_eligible"))

    def test_05_assistant_quality_inquiry_flow(self):
        """آزمون پاسخ دستیار به استعلام «کدوم مغازه جنس بهتر رو داره؟»"""
        # جستجوی اولیه گوشی سامسونگ
        search_res = self.assistant.process_message("گوشی سامسونگ A55")
        self.assertEqual(search_res["type"], "product_search")
        self.assertTrue(len(search_res["products"]) > 0)
        state = search_res["state"]

        # ارسال استعلام کیفیت
        inquiry_res = self.assistant.process_message("کدوم مغازه جنس بهتر و گارانتی معتبرتر داره؟", state=state)
        self.assertEqual(inquiry_res["type"], "consultation")
        self.assertIn("بهترین شرایط ثبت‌شده", inquiry_res["message"])
        # آفر کپی یا قیمت پرت نباید به عنوان «ارزان‌ترین» معرفی شود
        pid = state["active_product_id"]
        healthy_min = self.conn.execute(
            "SELECT MIN(price_toman) FROM offers WHERE product_id = ? AND is_copy = 0 AND price_suspect = 0", (pid,)).fetchone()[0]
        all_min = self.conn.execute("SELECT MIN(price_toman) FROM offers WHERE product_id = ?", (pid,)).fetchone()[0]
        if all_min < healthy_min:
            self.assertNotIn(f"{all_min:,}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")), inquiry_res["message"])
        # ادعای اصالت بدون پشتوانه داده نباید ساخته شود
        self.assertNotIn("۱۰۰٪", inquiry_res["message"])
        # پاسخ باید شامل مقایسه مغازه‌ها و امتیاز اصالت باشد
        self.assertIn("گارانتی", inquiry_res["message"])

    def test_06_assistant_same_shop_inquiry_flow(self):
        """آزمون پاسخ دستیار به استعلام موجودی همان مغازه در هر دو حالت اقلام جانبی و مشاوره یکجا"""
        search_res = self.assistant.process_message("گوشی سامسونگ A55")
        state = search_res["state"]

        # حالت اول: استعلام موجودی همان مغازه از طریق نیت مشاوره
        same_shop_res = self.assistant.process_message("آیا همین مغازه این اقلام رو یکجا داره؟", state=state)
        self.assertEqual(same_shop_res["type"], "consultation")
        self.assertIn("خرید یکجا از همین مغازه", same_shop_res["message"])

        # حالت دوم: درخواست اقلام مکمل و سازگار
        comp_res = self.assistant.process_message("اقلام مکمل و لوازم جانبی این چیه؟", state=state)
        self.assertEqual(comp_res["type"], "complementary_recommendations")
        self.assertTrue(len(comp_res["recommendations"]) > 0)


if __name__ == "__main__":
    unittest.main()
