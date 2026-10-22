"""
تست‌های واحد الگوریتم‌ها و اندپوینت‌های کَلَم.
اجرا:  python -m unittest discover -s tests
"""

import json
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

from backend import main  # noqa: E402
from backend.assistant import KalamAssistant  # noqa: E402
from backend.algorithms.credipay import analyze_payment_options  # noqa: E402
from backend.algorithms.imwp import parse_mall_address  # noqa: E402
from backend.algorithms.indp import detect_ambiguous_intent  # noqa: E402
from backend.algorithms.ip_crp import InPersonCartRouter  # noqa: E402
from backend.algorithms.paco import calculate_paco_score  # noqa: E402
from backend.algorithms.svdp import compute_stock_certainty, generate_inquiry_dossier, parse_phone_number  # noqa: E402
from backend.algorithms.textutil import days_since, has_word  # noqa: E402
from backend.algorithms.tfra import find_emergency_fallbacks  # noqa: E402

RECENT = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")


CONNECTIONS = []


def tearDownModule():
    for conn in CONNECTIONS:
        conn.close()


def make_db():
    """پایگاه داده کوچک درون‌حافظه با همان ساختار build_db.py"""
    conn = sqlite3.connect(":memory:")
    CONNECTIONS.append(conn)
    conn.executescript("""
    CREATE TABLE shops (shop_id TEXT PRIMARY KEY, name TEXT, address TEXT, location_label TEXT,
        lat REAL, lon REAL, payment_options TEXT, contacts TEXT, weekly_hours TEXT,
        instagram TEXT, website_url TEXT, supports_fast_delivery INTEGER);
    CREATE TABLE products (product_id TEXT PRIMARY KEY, persian_title TEXT, category_name TEXT,
        brand_name TEXT, model TEXT, specs TEXT, image_urls TEXT);
    CREATE TABLE offers (offer_id TEXT PRIMARY KEY, product_id TEXT, shop_id TEXT, price_toman INTEGER,
        last_price_changed_at TEXT, warranty TEXT, description TEXT, seller_title TEXT);
    CREATE VIRTUAL TABLE products_fts USING fts5(product_id UNINDEXED, persian_title, category_name,
        brand_name, model, tokenize='unicode61');
    CREATE TABLE complementary_rules (rule_id INTEGER PRIMARY KEY AUTOINCREMENT, source_category TEXT,
        target_category TEXT, tier INTEGER, dep_score REAL, description_fa TEXT);
    """)
    shops = [
        ("s1", "فروشگاه الف", "پاساژ چارسو، طبقه اول، واحد ۱۰", "چارسو", 35.69, 51.41, None, '[{"value":"02100001111"}]', None),
        ("s2", "فروشگاه ب", "پاساژ چارسو، طبقه اول، واحد ۲۰", "چارسو", 35.69, 51.41, None, None, None),
        ("s3", "فروشگاه ج", "پاساژ چارسو، طبقه سوم، واحد ۳۰", "چارسو", 35.69, 51.41,
         '[{"provider_name":"snapp_pay","channel":"in_person"}]', None, None),
        ("s4", "فروشگاه د", "مجتمع تجاری پایتخت، طبقه همکف", "پایتخت", 35.76, 51.43, None, None, None),
        ("s5", "فروشگاه بی‌آدرس", None, None, None, None, None, None, None),
        ("s6", "فروشگاه تهرانی", "تهران، خیابان جمهوری، نزدیک چهارراه", "امجد", 35.70, 51.42, None, None, None),
    ]
    conn.executemany("INSERT INTO shops VALUES (?,?,?,?,?,?,?,?,?,NULL,NULL,0)", shops)
    products = [
        ("p1", "گوشی موبایل سامسونگ Galaxy A55", "گوشی موبایل", "سامسونگ"),
        ("p2", "کاور سیلیکونی سامسونگ Galaxy A55", "کیف و کاور گوشی", "متفرقه"),
        ("p3", "دریل شارژی رونیکس", "دریل و پیچ گوشتی برقی و شارژی", "رونیکس"),
    ]
    for pid, title, cat, brand in products:
        conn.execute("INSERT INTO products VALUES (?,?,?,?,NULL,NULL,NULL)", (pid, title, cat, brand))
        conn.execute("INSERT INTO products_fts VALUES (?,?,?,?,NULL)", (pid, title, cat, brand))
    offers = [
        ("o1", "p1", "s1", 20_000_000), ("o1b", "p1", "s1", 25_000_000),  # دو پیشنهاد در یک مغازه
        ("o2", "p1", "s2", 21_000_000), ("o3", "p1", "s3", 22_000_000), ("o4", "p1", "s4", 19_000_000),
        ("o5", "p1", "s5", 18_000_000), ("o6", "p1", "s6", 23_000_000),
        ("o7", "p2", "s2", 200_000), ("o8", "p2", "s4", 150_000),
        ("o9", "p3", "s3", 4_000_000), ("o10", "p3", "s4", 4_100_000),
        ("o11", "p1", "s2", None),
    ]
    conn.executemany("INSERT INTO offers VALUES (?,?,?,?,?,NULL,NULL,NULL)",
                     [(oid, pid, sid, price, RECENT) for oid, pid, sid, price in offers])
    conn.execute("INSERT INTO complementary_rules (source_category, target_category, tier, dep_score) VALUES (?,?,?,?)",
                 ("گوشی موبایل", "کیف و کاور گوشی", 2, 0.65))
    conn.commit()
    return conn


class TextUtilTests(unittest.TestCase):
    def test_has_word_is_whole_word(self):
        self.assertFalse(has_word("خیابان جمهوری نزدیک چهارراه", "یک"))
        self.assertTrue(has_word("طبقه یک", "یک"))
        self.assertFalse(has_word("کیف کوچک", "چک"))

    def test_days_since_handles_naive_and_date_only(self):
        self.assertIsNotNone(days_since("2026-01-01T10:00:00"))
        self.assertIsNotNone(days_since("2026-01-01"))
        self.assertIsNone(days_since("not a date"))
        self.assertIsNone(days_since("null"))


class AddressParserTests(unittest.TestCase):
    def check(self, address, mall, floor, unit):
        r = parse_mall_address(address, "تهران")
        self.assertEqual(r["mall_name"], mall, address)
        self.assertEqual(r["floor_level"], floor, address)
        self.assertEqual(r["unit_number"], unit, address)

    def test_persian_digits(self):
        self.check("پاساژ چارسو طبقه ۲ واحد ۵", "پاساژ چارسو", 2, "واحد ۵")

    def test_negative_floor_in_words_and_digits(self):
        self.check("پاساژ علاءالدین طبقه منفی یک واحد ۱۲", "پاساژ علاءالدین", -1, "واحد ۱۲")
        self.check("مجتمع تجاری پایتخت طبقه -1 غرفه 12", "مجتمع تجاری پایتخت", -1, "غرفه ۱۲")

    def test_two_digit_floor(self):
        self.check("پاساژ پایتخت طبقه 10", "پاساژ پایتخت", 10, None)

    def test_no_substring_false_positives(self):
        for address in ("خیابان جمهوری نزدیک چهارراه", "خیابان مدرسه پلاک ۴"):
            r = parse_mall_address(address, "تهران")
            self.assertFalse(r["floor_known"], address)
            self.assertEqual(r["floor_label"], "طبقه نامشخص")
            self.assertFalse(r["mall_detected"])

    def test_bare_unit_after_floor(self):
        self.check("پاساژ امجد، طبقه دوم، 214", "پاساژ امجد", 2, "واحد ۲۱۴")

    def test_empty_address(self):
        r = parse_mall_address(None, "چارسو")
        self.assertEqual(r["mall_name"], "چارسو")
        self.assertFalse(r["floor_known"])


class SvdpTests(unittest.TestCase):
    def test_phone_formats(self):
        self.assertEqual(parse_phone_number('[{"value":"۰۲۱-۶۶۷۰ ۱۲۳۴"}]'), "02166701234")
        self.assertEqual(parse_phone_number('{"mobile":"+989121234567"}'), "09121234567")
        self.assertIsNone(parse_phone_number("null"))

    def test_no_fake_phone(self):
        self.assertIsNone(generate_inquiry_dossier("کالا", 1000, "مغازه", None)["phone_number"])

    def test_naive_timestamp_is_not_treated_as_30_days(self):
        r = compute_stock_certainty({"price_toman": 1, "last_price_changed_at": RECENT.rstrip("Z")}, {})
        self.assertLessEqual(r["days_since_update"], 4)


class CrediPayTests(unittest.TestCase):
    def test_object_instead_of_list_does_not_crash(self):
        r = analyze_payment_options('{"provider_name":"tara","channel":"in_person"}')
        self.assertEqual(r["supported_providers"], ["tara"])
        self.assertFalse(analyze_payment_options('{"x": 1}')["has_credit"])
        self.assertFalse(analyze_payment_options("not json")["has_credit"])


class IndpTests(unittest.TestCase):
    def test_phone_camera_goes_to_mobile(self):
        self.assertEqual(detect_ambiguous_intent("دوربین گوشی خوب")["category_key"], "mobile")
        self.assertFalse(detect_ambiguous_intent("کفشک")["needs_decoupling"])


class CartRouterTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()
        self.router = InPersonCartRouter(self.conn)

    def test_keeps_cheapest_offer_per_shop(self):
        # s1 دو پیشنهاد ۲۰ و ۲۵ میلیونی دارد؛ ارزان‌تر باید انتخاب شود
        route = self.router.solve_cart(["p1"], preferred_hub="چارسو")["primary_route"]
        self.assertEqual(route["hub"], "چارسو")
        self.assertEqual(route["total_price"], 20_000_000)

    def test_preferred_hub_is_honoured(self):
        r = self.router.solve_cart(["p1", "p3"], preferred_hub="چارسو")
        self.assertEqual(r["primary_route"]["hub"], "چارسو")
        r = self.router.solve_cart(["p1", "p3"], preferred_hub="پایتخت")
        self.assertEqual(r["primary_route"]["hub"], "پایتخت")

    def test_shops_without_hub_are_not_grouped(self):
        r = self.router.solve_cart(["p1"])
        self.assertNotIn(None, [h["hub"] for h in r["available_hubs"]])
        self.assertNotIn("نامشخص", [h["hub"] for h in r["available_hubs"]])

    def test_duplicates_and_unknown_ids(self):
        r = self.router.solve_cart(["p1", "p1", "missing"])
        self.assertEqual(r["requested_items_count"], 2)
        self.assertIsNone(r["primary_route"])


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def test_tiers(self):
        r = find_emergency_fallbacks(self.conn, "p1", "s1")
        tiers = {f["shop_id"]: f["tier"] for f in r["recommended_fallbacks"]}
        self.assertEqual(tiers.get("s2"), 1)  # همان پاساژ و همان طبقه
        self.assertEqual(tiers.get("s3"), 2)  # همان پاساژ، طبقه دیگر
        self.assertEqual(r["layer3_count"], 3)

    def test_city_fallback_name_does_not_match_every_address(self):
        # آدرس s6 پاساژ ندارد و «تهران» در آدرس بقیه هم هست؛ نباید هم‌پاساژ حساب شود
        r = find_emergency_fallbacks(self.conn, "p1", "s6")
        self.assertEqual(r["layer1_count"] + r["layer2_count"], 0)

    def test_shop_without_address_does_not_crash(self):
        r = find_emergency_fallbacks(self.conn, "p1", "s5")
        self.assertIn("recommended_fallbacks", r)


class PacoTests(unittest.TestCase):
    def test_same_category_is_substitute(self):
        score, _ = calculate_paco_score({"category_name": "گوشی موبایل", "brand_name": "a"}, {},
                                        {"category_name": "گوشی موبایل", "brand_name": "a", "price_toman": 1})
        self.assertEqual(score, 0.0)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def test_missing_db_returns_503(self):
        with mock.patch.object(main, "DB_PATH", "/nonexistent/torob.db"):
            with self.assertRaises(HTTPException) as ctx:
                next(main.get_db())
        self.assertEqual(ctx.exception.status_code, 503)

    def test_search_counts_distinct_shops_and_filters(self):
        r = main.search_products(q="سامسونگ", hub=None, category=None, limit=25, conn=self.conn)
        p1 = next(p for p in r["products"] if p["product_id"] == "p1")
        self.assertEqual(p1["available_offline_shops_count"], 6)
        r = main.search_products(q="سامسونگ", hub="پایتخت", category="کیف و کاور گوشی", limit=25, conn=self.conn)
        self.assertEqual([p["product_id"] for p in r["products"]], ["p2"])

    def test_complementary_uses_rules_and_dedupes(self):
        r = main.get_complementary_items("p1", shop_id="s2", conn=self.conn)
        ids = [c["product_id"] for c in r["recommendations"]]
        self.assertEqual(ids, ["p2"])
        self.assertEqual(r["recommendations"][0]["shop_id"], "s2")  # همان مغازه امتیاز بیشتری دارد

    def test_cart_request_limit(self):
        with self.assertRaises(Exception):
            main.CartRouteRequest(product_ids=[str(i) for i in range(main.MAX_CART_ITEMS + 1)])


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.assistant = KalamAssistant(make_db())

    def test_panic_without_context_does_not_invent_data(self):
        r = self.assistant.process_message("مغازه بسته بود")
        self.assertEqual(r["type"], "text")

    def test_panic_with_context(self):
        r = self.assistant.process_message("مغازه بسته بود", {"active_product_id": "p1", "active_shop_id": "s1"})
        self.assertEqual(r["type"], "panic_fallback")

    def test_empty_cart_route_does_not_invent_items(self):
        r = self.assistant.process_message("مسیر خرید رو بچین", {"cart_product_ids": []})
        self.assertEqual(r["type"], "text")

    def test_small_bag_is_not_credit(self):
        r = self.assistant.process_message("کیف کوچک")
        self.assertNotEqual(r["type"], "credit_shops")

    def test_no_results_does_not_return_random_products(self):
        r = self.assistant.process_message("یخچال ساید بای ساید")
        self.assertEqual(r["products"], [])

    def test_product_search_skips_null_prices(self):
        r = self.assistant.process_message("گوشی سامسونگ مدل A55")
        self.assertTrue(r["products"])
        self.assertIsNotNone(r["products"][0]["best_shop"]["price"])


if __name__ == "__main__":
    unittest.main()
