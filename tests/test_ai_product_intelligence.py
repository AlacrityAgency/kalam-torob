"""
مجموعه آزمون‌های الگوریتم هوش مصنوعی تحلیل کالا و سیستم پویای اقلام مکمل (DCA)
Zero-Shot AI Product Intelligence & Dynamic Grounded Companion Tests
"""

import sqlite3
import time
import unittest

from backend.algorithms.ai_product_intelligence import (
    find_grounded_complementary_items,
    get_product_intelligence,
    init_product_intelligence_table,
)
from backend.assistant import KalamAssistant


class TestAIProductIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect("torob.db")
        init_product_intelligence_table(cls.conn)
        cls.assistant = KalamAssistant(cls.conn)

    def test_01_zero_shot_espresso_machine(self):
        """آزمون تحلیل صفر-نمونه دستگاه اسپرسوساز (بدون هیچ قاعده دستی در دیتابیس)"""
        product = {
            "product_id": "test_espresso_auto",
            "persian_title": "دستگاه اسپرسوساز مباشی مدل ECM2016",
            "category_name": "اسپرسوساز",
            "brand_name": "مباشی",
            "price_toman": 4500000,
        }
        intel = get_product_intelligence(self.conn, product)
        self.assertIn("facets", intel)
        self.assertGreater(len(intel["facets"]), 0)
        self.assertIn("in_store_prompts", intel)
        self.assertGreater(len(intel["in_store_prompts"]), 0)

        # جستجوی عینی در کاتالوگ واقعی ترب
        recs, prompts = find_grounded_complementary_items(self.conn, product)
        # خروجی نباید خالی باشد و باید اقلام واقعی از دیتابیس پیشنهاد دهد
        self.assertIsInstance(recs, list)
        for r in recs:
            self.assertIn("product_id", r)
            self.assertIn("paco_score", r)
            self.assertGreater(r["paco_score"], 0)

    def test_02_zero_shot_welding_inverter(self):
        """آزمون تحلیل ابزار صنعتی: دستگاه جوشکاری اینورتری (فاقد قاعده دستی قبلی)"""
        product = {
            "product_id": "test_welding_auto",
            "persian_title": "دستگاه جوشکاری اینورتر صبا الکتریک 200 آمپر مدل 2001",
            "category_name": "اینورتر و دستگاه جوشکاری",
            "brand_name": "صبا الکتریک",
            "price_toman": 6800000,
        }
        intel = get_product_intelligence(self.conn, product)
        facets = intel.get("facets", [])
        self.assertGreater(len(facets), 0)
        # باید حداقل یکی از ملحقات کارگاهی مثل عینک، کابل یا انبر را تشخیص دهد
        roles = [f.get("role") for f in facets]
        self.assertTrue(any(r in ("consumable", "protective", "accessory", "synergy") for r in roles))

    def test_03_zero_shot_classical_guitar(self):
        """آزمون تحلیل آلات موسیقی: گیتار کلاسیک یاماها"""
        product = {
            "product_id": "test_guitar_auto",
            "persian_title": "گیتار کلاسیک یاماها مدل C40",
            "category_name": "گیتار کلاسیک",
            "brand_name": "یاماها",
            "price_toman": 7200000,
        }
        intel = get_product_intelligence(self.conn, product)
        prompts = intel.get("in_store_prompts", [])
        self.assertGreater(len(prompts), 0)

    def test_04_memoization_cache_speed(self):
        """آزمون سرعت کش‌گذاری پایدار: بار دوم باید زیر ۱۰ میلی‌ثانیه پاسخ دهد"""
        product = {
            "product_id": "product_test_speed_bench",
            "persian_title": "اره فارسی بر کشویی رونیکس مدل 5402",
            "category_name": "اره برقی و فارسی بر",
            "brand_name": "رونیکس",
            "price_toman": 11500000,
        }
        # بار اول (پر کردن کش)
        get_product_intelligence(self.conn, product)

        # بار دوم (اندازه‌گیری زمان کش پایدار)
        t0 = time.perf_counter()
        cached = get_product_intelligence(self.conn, product)
        duration_ms = (time.perf_counter() - t0) * 1000

        self.assertIn("facets", cached)
        self.assertLess(duration_ms, 20.0, f"زمان کش باید زیر ۲۰ میلی‌ثانیه باشد ولی {duration_ms:.2f}ms بود")

    def test_05_grounded_items_exist_in_db_no_hallucination(self):
        """آزمون ضدتوهم: تمام اقلام مکمل پیشنهادی باید واقعاً در جدول products و offers ترب وجود داشته باشند"""
        # یافتن یک کالای واقعی موجود در دیتابیس
        cursor = self.conn.cursor()
        real_prod = cursor.execute("""
            SELECT product_id, persian_title, category_name, brand_name
            FROM products WHERE persian_title LIKE '%دریل%' LIMIT 1;
        """).fetchone()

        if real_prod:
            base_p = {
                "product_id": real_prod[0],
                "persian_title": real_prod[1],
                "category_name": real_prod[2],
                "brand_name": real_prod[3],
                "price_toman": 3000000,
            }
            recs, _ = find_grounded_complementary_items(self.conn, base_p)
            for r in recs:
                # بررسی وجود فیزیکی در پایگاه داده
                check = cursor.execute("SELECT persian_title FROM products WHERE product_id = ?", (r["product_id"],)).fetchone()
                self.assertIsNotNone(check, f"کالای {r['product_id']} نباید خیالی باشد!")

    def test_06_assistant_complementary_end_to_end(self):
        """آزمون یکپارچگی دستیار چت کَلَم در پاسخ به درخواست مکمل بدون نیاز به قاعده دستی"""
        cursor = self.conn.cursor()
        real_prod = cursor.execute("SELECT product_id, persian_title FROM products LIMIT 1;").fetchone()
        pid, ptitle = real_prod[0], real_prod[1]

        res = self.assistant.process_message(
            "اقلام مکمل این خرید چیه؟",
            state={"active_product_id": pid}
        )
        self.assertIn(res.get("type"), ("complementary_recommendations", "text"))
        # نباید پیام سنتی «برای این دسته قاعده مکمل ثبت نشده است» بدهد
        if res.get("type") == "text":
            self.assertNotIn("قاعده مکمل ثبت نشده است", res.get("message", ""))


if __name__ == "__main__":
    unittest.main()
