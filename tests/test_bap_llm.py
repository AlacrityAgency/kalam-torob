"""
آزمون‌های جامع الگوریتم BAP-LLM (Behavioral & Analytical Purchasing with LLM Reasoning)
شامل آزمون‌های فرمول ریاضی PACO 2.0، سه‌گانه شناختی، پرامپت‌های سلاح مذاکره بازار و آزمون‌های یکپارچگی.
"""

import os
import sqlite3
import unittest

from backend.algorithms.paco import calculate_paco_score, _infer_cognitive_role
from backend.algorithms.prompt_generator import generate_dynamic_prompts
from backend.algorithms.ai_product_intelligence import find_grounded_complementary_items
from backend.assistant import KalamAssistant
from backend.main import get_product_details


class TestPACO2MathematicalFormulation(unittest.TestCase):
    """آزمون‌های فرمول‌بندی ریاضی PACO 2.0 و اقتصاد رفتاری"""

    def setUp(self):
        self.base_phone = {
            "product_id": "phone_test",
            "title": "گوشی موبایل سامسونگ Galaxy A55",
            "core_model": "A55",
            "category_name": "گوشی موبایل",
            "price_toman": 20_000_000,
        }
        self.base_shop = {
            "shop_id": "s_origin",
            "name": "فروشگاه مرکزی چارسو",
            "address": "پاساژ چارسو، طبقه همکف، واحد ۱",
            "location_label": "چارسو",
        }

    def test_01_same_shop_bundle_bonus(self):
        """آزمون پاداش ۴۰ درصدی بسته تجمیعی در همان مغازه (Bundle Bonus = 1.40)"""
        cand_same_shop = {
            "title": "کاور سیلیکونی Galaxy A55",
            "category_name": "کیف و کاور گوشی",
            "price_toman": 300_000,
            "shop_id": "s_origin",
            "address": "پاساژ چارسو، طبقه همکف، واحد ۱",
            "location_label": "چارسو",
            "dep_score": 0.85,
        }
        cand_diff_shop = dict(cand_same_shop)
        cand_diff_shop["shop_id"] = "s_other"
        cand_diff_shop["address"] = "پاساژ چارسو، طبقه سوم، واحد ۳۵"

        score_same, det_same = calculate_paco_score(self.base_phone, self.base_shop, cand_same_shop)
        score_diff, det_diff = calculate_paco_score(self.base_phone, self.base_shop, cand_diff_shop)

        self.assertEqual(det_same["bundle_bonus"], 1.40)
        self.assertTrue(det_same["bundle_eligible"])
        self.assertEqual(det_diff["bundle_bonus"], 1.00)
        self.assertFalse(det_diff["bundle_eligible"])
        self.assertIn("۱۰ تا ۱۵ درصد تخفیف", det_same["bargaining_tip"])
        # امتیاز همان مغازه باید به مراتب بالاتر باشد
        self.assertGreater(score_same, score_diff * 1.5)

    def test_02_vertical_floor_decay(self):
        """آزمون افت تصاعدی اصطکاک جابه‌جایی بین طبقات (افت شدید در طبقات دیگر)"""
        cand_same_floor = {
            "title": "گلس سرامیکی مات Galaxy A55",
            "category_name": "محافظ صفحه نمایش گوشی",
            "price_toman": 150_000,
            "shop_id": "s_colleague",
            "address": "پاساژ چارسو، طبقه همکف، واحد ۱۰",
            "location_label": "چارسو",
            "dep_score": 0.85,
        }
        cand_diff_floor = dict(cand_same_floor)
        cand_diff_floor["shop_id"] = "s_floor3"
        cand_diff_floor["address"] = "پاساژ چارسو، طبقه سوم، واحد ۴۰"

        _, det_same_fl = calculate_paco_score(self.base_phone, self.base_shop, cand_same_floor)
        _, det_diff_fl = calculate_paco_score(self.base_phone, self.base_shop, cand_diff_floor)

        self.assertEqual(det_same_fl["psi_spatial"], 0.55)
        self.assertLessEqual(det_diff_fl["psi_spatial"], 0.30)
        self.assertGreater(det_same_fl["psi_spatial"], det_diff_fl["psi_spatial"])

    def test_03_role_sensitive_mental_accounting(self):
        """آزمون حسابداری ذهنی: کالای محافظتی تا ۳۰٪ ارزش کالا جریمه نمی‌شود"""
        # قاب گران‌قیمت ۲ میلیونی برای گوشی ۲۰ میلیونی (نسبت ۱۰٪)
        protective_cand = {
            "title": "کیف چرم ضربه‌گیر و گلس ارتش مناسب Galaxy A55",
            "category_name": "کیف و کاور گوشی",
            "price_toman": 2_000_000,
            "role": "protective",
            "dep_score": 0.85,
        }
        _, det_prot = calculate_paco_score(self.base_phone, {}, protective_cand)
        self.assertEqual(det_prot["omega_economic"], 1.00)
        self.assertEqual(det_prot["cognitive_role"], "protective")
        self.assertEqual(det_prot["cognitive_category"], "سپر محافظت از سرمایه")

    def test_04_cognitive_role_inference(self):
        """آزمون دسته‌بندی سه‌گانه شناختی بر اساس عناوین و دسته‌ها"""
        # ۱. سپر محافظت
        role1, cat1, thresh1 = _infer_cognitive_role("کاور و گلس نشکن", "محافظ گوشی")
        self.assertEqual(role1, "protective")
        self.assertEqual(cat1, "سپر محافظت از سرمایه")
        self.assertEqual(thresh1, 0.30)

        # ۲. راه‌اندازی فوری
        role2, cat2, thresh2 = _infer_cognitive_role("شارژر دیواری فست ۲۵ وات", "شارژر گوشی")
        self.assertEqual(role2, "consumable")
        self.assertEqual(cat2, "راه‌اندازی فوری در محل")
        self.assertEqual(thresh2, 0.20)

        # ۳. ارتقای کاربری و سینرژی
        role3, cat3, thresh3 = _infer_cognitive_role("هدفون بلوتوثی بادز پرو", "هدفون و هندزفری")
        self.assertEqual(role3, "synergy")
        self.assertEqual(cat3, "ارتقای کاربری و سینرژی")
        self.assertEqual(thresh3, 0.60)


class TestBazaarBattlePrompts(unittest.TestCase):
    """آزمون‌های تولید پرامپت‌های استعلام و سلاح مذاکره بازار"""

    def test_01_phone_battle_prompts(self):
        """آزمون سلاح‌های مذاکره در خرید گوشی موبایل"""
        phone = {"title": "سامسونگ Galaxy A55 5G", "category": "گوشی موبایل", "brand": "سامسونگ"}
        prompts = generate_dynamic_prompts(product=phone)
        # ۱. سپر ضد هزینه پنهان فعال‌سازی و نرم‌افزار
        self.assertTrue(any("هزینه اجباری فعال‌سازی" in p or "نرم‌افزار" in p for p in prompts))
        # ۲. اهرم تخفیف سبد
        self.assertTrue(any("تخفیف" in p for p in prompts))
        # ۳. استعلام پلمپ و گارانتی
        self.assertTrue(any("پلمپ" in p or "گارانتی" in p for p in prompts))

    def test_02_tool_battle_prompts(self):
        """آزمون سلاح‌های مذاکره در بازار ابزار حسن‌آباد"""
        tool = {"title": "دریل بتن کن رونیکس مدل 2701", "category": "دریل و بتن کن", "brand": "رونیکس"}
        prompts = generate_dynamic_prompts(product=tool)
        self.assertTrue(any("تست روشن شدن" in p or "گیربکس" in p for p in prompts))
        self.assertTrue(any("تخفیف نقدی پای پوز" in p or "تخفیف" in p for p in prompts))
        self.assertTrue(any("مته" in p for p in prompts))


class TestEndToEndBAPIntegration(unittest.TestCase):
    """آزمون یکپارچگی BAP-LLM با پایگاه داده و کاتالوگ"""

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect("torob.db")
        cls.assistant = KalamAssistant(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_01_grounded_items_have_cognitive_metadata(self):
        """اقلام مکمل عینی باید دارای متادیتای شناختی و راهنمای چانه‌زنی باشند"""
        cursor = self.conn.cursor()
        real_p = cursor.execute("SELECT product_id, persian_title, category_name FROM products WHERE persian_title LIKE '%سامسونگ%' LIMIT 1;").fetchone()
        if real_p:
            base = {"product_id": real_p[0], "persian_title": real_p[1], "category_name": real_p[2], "price_toman": 15_000_000}
            recs, _ = find_grounded_complementary_items(self.conn, base, limit=5)
            self.assertTrue(len(recs) > 0)
            for r in recs:
                self.assertIn("cognitive_category", r)
                self.assertIn("bargaining_tip", r)
                self.assertIn("bundle_eligible", r)
                self.assertIn("paco_score", r)

    def test_02_product_details_endpoint_returns_bap_fields(self):
        """متد get_product_details باید فیلدهای شناختی را برای کارت‌های فرانت بازگرداند"""
        cursor = self.conn.cursor()
        real_p = cursor.execute("SELECT product_id FROM products LIMIT 1;").fetchone()
        if real_p:
            d = get_product_details(real_p[0], hub=None, lat=None, lon=None, conn=self.conn)
            if d.get("complementary_count", 0) > 0:
                recs = d["recommendations"]
                for r in recs:
                    self.assertIn("cognitive_category", r)
                    self.assertIn("bargaining_tip", r)


if __name__ == "__main__":
    unittest.main()
