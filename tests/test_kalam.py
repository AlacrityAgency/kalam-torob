"""
تست‌های واحد الگوریتم‌ها، جستجو، دستیار و اندپوینت‌های کَلَم.
اجرا:  python -m unittest discover -s tests

پایگاه داده تست با همان scripts/build_db.py از CSVهای کوچک ساخته می‌شود تا شِمای تست و برنامه یکی بماند.
"""

import contextlib
import csv
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from fastapi import HTTPException  # noqa: E402

import build_db  # noqa: E402
from backend import main  # noqa: E402
from backend.assistant import KalamAssistant  # noqa: E402
from backend.algorithms.credipay import analyze_payment_options, canonical_provider, filter_and_rank_by_credit  # noqa: E402
from backend.algorithms.hours import TEHRAN_TZ, hours_status, parse_weekly_hours  # noqa: E402
from backend.algorithms.imwp import parse_mall_address  # noqa: E402
from backend.algorithms.indp import detect_ambiguous_intent  # noqa: E402
from backend.algorithms.ip_crp import InPersonCartRouter  # noqa: E402
from backend.algorithms.offer_quality import flatten_specs, is_copy_text, suspicious_prices  # noqa: E402
from backend.algorithms.paco import calculate_paco_score  # noqa: E402
from backend.algorithms.svdp import compute_stock_certainty, generate_inquiry_dossier, parse_phone_number, simulate_inquiry  # noqa: E402
from backend.algorithms.textutil import days_since, has_word  # noqa: E402
from backend.algorithms.tfra import find_emergency_fallbacks  # noqa: E402
from backend.nlu import local_extract, parse_budget  # noqa: E402
from backend.agent import follow_up  # noqa: E402
from backend.algorithms.hours import common_open_window  # noqa: E402
from backend.algorithms.recommend import rank_offers  # noqa: E402
from backend.search import search_products, tokenize  # noqa: E402

RECENT = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
OLD = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
ALWAYS_OPEN = json.dumps({d: "00:00-23:59" for d in
                          ("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday")})

SHOPS = [
    # shop_id, name, address, location_label, lat, lon, payment_options, contacts, weekly_hours, instagram, website, category_names
    ("s1", "فروشگاه الف", "پاساژ چارسو، طبقه اول، واحد ۱۰", "شیخ هادی", 35.69, 51.41, "null",
     '[{"channel":"phone","display_number":"۰۲۱۲۶۴۶۷۱۸۰"}]', ALWAYS_OPEN, "null", "null", "null"),
    ("s2", "فروشگاه ب", "پاساژ چارسو، طبقه اول، واحد ۲۰", "شیخ هادی", 35.69, 51.41,
     '[{"provider_name":"اسنپ‌پی","channel":"unknown"}]', "null", "{}", "null", "null", "null"),
    ("s3", "فروشگاه ج", "پاساژ چارسو، طبقه سوم، واحد ۳۰", "شیخ هادی", 35.69, 51.41,
     '[{"provider_name":"ترب‌پی","channel":"in_person"}]', "null", ALWAYS_OPEN, "kalam_test", "null", "null"),
    ("s4", "فروشگاه د", "مجتمع تجاری پایتخت، طبقه همکف", "فردوسی", 35.76, 51.43, "null", "null", "{}", "null",
     "https://example.com", "null"),
    ("s5", "فروشگاه بی‌آدرس", "null", "null", "null", "null", "null", "null", "null", "null", "null", "null"),
    ("s6", "فروشگاه تهرانی", "تهران، خیابان جمهوری، نزدیک چهارراه", "بهارستان", 35.70, 51.42, "null", "null",
     "null", "null", "null", "null"),
    ("s7", "فروشگاه هم‌صنف", "پاساژ چارسو، طبقه دوم", "شیخ هادی", 35.69, 51.41, "null", "null", "{}", "null", "null",
     '["گوشی موبایل"]'),
]
PRODUCTS = [
    ("p1", "گوشی موبایل سامسونگ Galaxy A55", "گوشی موبایل", "سامسونگ", '{"رم": "8 گیگابایت"}'),
    ("p2", "کاور سیلیکونی مناسب برای گوشی سامسونگ Galaxy A55", "کیف و کاور گوشی", "null", "null"),
    ("p3", "دریل شارژی رونیکس", "دریل و پیچ گوشتی برقی و شارژی", "رونیکس", "null"),
    ("p4", "کتونی رانینگ نایکی", "کتانی و کفش اسپرت", "نایکی", "null"),
]
OFFERS = [
    # offer_id, product_id, shop_id, price, date, seller_title
    ("o1", "p1", "s1", 20_000_000, RECENT, "null"), ("o1b", "p1", "s1", 25_000_000, RECENT, "null"),
    ("o2", "p1", "s2", 21_000_000, RECENT, "null"), ("o3", "p1", "s3", 22_000_000, OLD, "null"),
    ("o4", "p1", "s4", 19_000_000, RECENT, "null"), ("o5", "p1", "s5", 18_000_000, RECENT, "null"),
    ("o6", "p1", "s6", 23_000_000, RECENT, "null"),
    ("o6c", "p1", "s6", 600_000, RECENT, "طرح اصلی"),          # کپی
    ("o6x", "p1", "s2", 1, RECENT, "null"),                     # قیمت تستی
    ("o7", "p2", "s2", 200_000, RECENT, "null"), ("o8", "p2", "s4", 150_000, RECENT, "null"),
    ("o9", "p3", "s3", 4_000_000, RECENT, "null"), ("o10", "p3", "s4", 4_100_000, RECENT, "null"),
    ("o11", "p1", "s2", "null", RECENT, "null"),
    ("o12", "p4", "s1", 2_500_000, RECENT, "null"),
]

_TMP = tempfile.mkdtemp(prefix="kalam-test-")
DB_FILE = os.path.join(_TMP, "test.db")


def _write_csvs(folder):
    def write(name, header, rows):
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    write("shops.csv", ["shop_id", "name", "address", "location_label", "lat", "lon", "payment_options", "contacts",
                        "weekly_hours", "instagram", "website_url", "category_names", "supports_fast_delivery"],
          [s + ("null",) for s in SHOPS])
    write("products.csv", ["product_id", "persian_title", "category_name", "brand_name", "specs", "model", "image_urls"],
          [p + ("null", "[]") for p in PRODUCTS])
    write("offers.csv", ["offer_id", "product_id", "shop_id", "price_toman", "last_price_changed_at", "seller_title",
                         "warranty", "description"],
          [o + ("null", "null") for o in OFFERS])


def setUpModule():
    with mock.patch.object(build_db, "DATASET_DIR", _TMP), \
            mock.patch.object(build_db, "SAMPLE_MARKER", os.path.join(_TMP, "SAMPLE_DATA")):
        _write_csvs(_TMP)
        with contextlib.redirect_stdout(io.StringIO()):
            build_db.build(DB_FILE)


CONNECTIONS = []


def tearDownModule():
    for conn in CONNECTIONS:
        conn.close()
    shutil.rmtree(_TMP, ignore_errors=True)


def make_db():
    conn = sqlite3.connect(DB_FILE)
    CONNECTIONS.append(conn)
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

    def test_tokenize_strips_persian_punctuation(self):
        self.assertEqual(tokenize("گوشی A55 دارید؟"), ["گوشی", "a55", "دارید"])


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

    def test_bare_unit_after_floor(self):
        self.check("پاساژ امجد، طبقه دوم، 214", "پاساژ امجد", 2, "واحد ۲۱۴")


class HoursTests(unittest.TestCase):
    SAT_15 = datetime(2026, 10, 24, 15, 0, tzinfo=TEHRAN_TZ)   # شنبه
    FRI_12 = datetime(2026, 10, 23, 12, 0, tzinfo=TEHRAN_TZ)   # جمعه

    def test_split_shift_and_next_opening(self):
        raw = '{"saturday": "10:00-14:00, 16:00-21:00", "thursday": "10-14"}'
        r = hours_status(raw, self.SAT_15)
        self.assertEqual(r["state"], "closed")
        self.assertIn("۱۶:۰۰", r["label"])
        self.assertTrue(r["friday_closed"])
        self.assertEqual(hours_status(raw, datetime(2026, 10, 24, 11, 0, tzinfo=TEHRAN_TZ))["state"], "open")

    def test_persian_day_names_and_object_ranges(self):
        raw = '{"شنبه": [{"start": "09:00", "end": "20:00"}], "جمعه": ["16:00-20:00"]}'
        self.assertEqual(hours_status(raw, self.SAT_15)["state"], "open")
        self.assertFalse(hours_status(raw, self.FRI_12)["friday_closed"])

    def test_unknown_is_never_guessed(self):
        for raw in ("{}", "null", '"garbage"', '{"saturday": "00:00-00:00"}', '[{"day": "saturday", "shifts": ["00:00-00:00"]}]'):
            self.assertFalse(parse_weekly_hours(raw)["known"], raw)
            self.assertEqual(hours_status(raw, self.SAT_15)["state"], "unknown", raw)


class OfferQualityTests(unittest.TestCase):
    def test_copy_phrases(self):
        self.assertTrue(is_copy_text("ایرپاد پرو طرح اصلی"))
        self.assertTrue(is_copy_text("های‌کپی"))
        self.assertFalse(is_copy_text("گارانتی اصالت"))
        self.assertFalse(is_copy_text("کپی‌برداری ممنوع"))

    def test_outliers(self):
        self.assertEqual(suspicious_prices([15_000_000, 14_800_000, 600_000, 15_200_000, 1, None]), {2, 4})

    def test_specs(self):
        self.assertEqual(flatten_specs('{"رم": "8GB", "نمایش": {"اندازه": "6.6"}}'),
                         [{"name": "رم", "value": "8GB"}, {"name": "نمایش / اندازه", "value": "6.6"}])


class SvdpTests(unittest.TestCase):
    def test_phone_formats(self):
        self.assertEqual(parse_phone_number('[{"channel":"phone","display_number":"۰۲۱۲۶۴۶۷۱۸۰"}]'), "02126467180")
        self.assertEqual(parse_phone_number('{"mobile":"+989121234567"}'), "09121234567")
        self.assertIsNone(parse_phone_number("null"))

    def test_no_fake_phone(self):
        self.assertIsNone(generate_inquiry_dossier("کالا", 1000, "مغازه", None)["phone_number"])

    def test_known_hours_raise_certainty(self):
        offer = {"price_toman": 1, "last_price_changed_at": RECENT}
        self.assertGreater(compute_stock_certainty(offer, {"weekly_hours": ALWAYS_OPEN})["confidence_percentage"],
                           compute_stock_certainty(offer, {"weekly_hours": "{}"})["confidence_percentage"])

    def test_simulation_is_labelled_and_grounded(self):
        r = simulate_inquiry({"product_title": "x", "price_toman": 100, "last_price_changed_at": OLD}, "availability")
        self.assertTrue(r["simulated"])
        self.assertEqual(r["level"], "low")
        r = simulate_inquiry({"product_title": "x", "is_copy": 1, "seller_title": "طرح اصلی"}, "warranty")
        self.assertIn("اصل نیست", r["seller"])


class CrediPayTests(unittest.TestCase):
    def test_persian_provider_names(self):
        r = analyze_payment_options('[{"provider_name":"اسنپ‌پی","channel":"unknown"}]')
        self.assertEqual(r["supported_providers"], ["snapp_pay"])
        self.assertEqual(canonical_provider("ازکی‌وام"), "azki_vam")
        shops = [{"payment_options": '[{"provider_name":"اسنپ‌پی","channel":"unknown"}]'}]
        self.assertEqual(len(filter_and_rank_by_credit(shops, "snapp_pay")), 1)
        self.assertEqual(len(filter_and_rank_by_credit(shops, "snapp_pay", in_person_only=True)), 0)

    def test_object_instead_of_list_does_not_crash(self):
        self.assertEqual(analyze_payment_options('{"provider_name":"tara","channel":"in_person"}')["supported_providers"], ["tara"])
        self.assertFalse(analyze_payment_options("not json")["has_credit"])


class NluTests(unittest.TestCase):
    def test_one_sentence_slots(self):
        r = local_extract("گوشی A55 قسطی در چارسو دارید؟", ["فردوسی"])
        self.assertEqual((r["tokens"], r["place"], r["credit"]), (["گوشی", "a55"], "چارسو", True))
        r = local_extract("کتونی تا ۳ تومن می‌خوام ولی فقط مغازه‌هایی که اسنپ‌پی دارن", [])
        self.assertEqual((r["tokens"], r["budget_max"], r["provider"]), (["کتونی"], 3_000_000, "snapp_pay"))

    def test_budget_forms(self):
        self.assertEqual(parse_budget("بین ۳۰ تا ۴۰ میلیون"), (30_000_000, 40_000_000))
        self.assertEqual(parse_budget("زیر ۵۰۰ هزار"), (None, 500_000))
        self.assertEqual(parse_budget("بالای ۲ میلیون"), (2_000_000, None))

    def test_intents(self):
        self.assertEqual(local_extract("فروشگاه‌های دارای اقساط اسنپ پی", [])["intent"], "credit")
        self.assertEqual(local_extract("جمعه کدوم مغازه‌ها بازن؟", [])["intent"], "hours")
        self.assertTrue(local_extract("ارزون‌ترش کدومه؟", [])["refers_previous"])


class IndpTests(unittest.TestCase):
    def test_generic_vs_specific(self):
        self.assertTrue(detect_ambiguous_intent("کفش خوب برای پیاده روی", tokens=["کفش", "پیاده", "روی"])["needs_decoupling"])
        self.assertFalse(detect_ambiguous_intent("کفش نایکی", tokens=["کفش", "نایکی"])["needs_decoupling"])
        self.assertFalse(detect_ambiguous_intent("گوشی", tokens=["گوشی"], has_budget=True)["needs_decoupling"])
        self.assertFalse(detect_ambiguous_intent("دوربین عکاسی")["needs_decoupling"])


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def test_synonyms_both_ways(self):
        self.assertEqual([p["product_id"] for p in search_products(self.conn, ["کتونی"])], ["p4"])
        self.assertEqual([p["product_id"] for p in search_products(self.conn, ["کتانی"])], ["p4"])

    def test_min_price_ignores_copies_and_outliers(self):
        p1 = next(p for p in search_products(self.conn, ["سامسونگ"]) if p["product_id"] == "p1")
        self.assertEqual(p1["min_price_toman"], 18_000_000)
        with_copies = next(p for p in search_products(self.conn, ["سامسونگ"], include_copies=True) if p["product_id"] == "p1")
        self.assertEqual(with_copies["min_price_toman"], 1)

    def test_conditions(self):
        ids = lambda **f: [p["product_id"] for p in search_products(self.conn, ["سامسونگ"], **f)]
        self.assertEqual(ids(provider="torob_pay"), ["p1"])
        credit = next(p for p in search_products(self.conn, ["گوشی"], credit=True))
        self.assertEqual(credit["available_offline_shops_count"], 2)
        self.assertEqual(ids(place="چارسو", max_price=20_500_000), ["p1", "p2"])  # کاور بعد از گوشی
        fresh = next(p for p in search_products(self.conn, ["گوشی"], place="چارسو", fresh=True))
        self.assertEqual(fresh["available_offline_shops_count"], 2)  # s3 قیمت قدیمی دارد
        self.assertEqual(next(p for p in search_products(self.conn, ["گوشی"], open_now=True))["available_offline_shops_count"], 2)

    def test_accessories_after_main_product(self):
        self.assertEqual([p["product_id"] for p in search_products(self.conn, ["galaxy", "a55"])], ["p1", "p2"])
        self.assertEqual([p["product_id"] for p in search_products(self.conn, ["galaxy", "a55"], accessories="exclude")], ["p1"])
        self.assertEqual([p["product_id"] for p in search_products(self.conn, ["کاور", "a55"])], ["p2"])


class CartRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = InPersonCartRouter(make_db())

    def test_keeps_cheapest_clean_offer_per_shop(self):
        route = self.router.solve_cart(["p1"], preferred_hub="شیخ هادی")["primary_route"]
        self.assertEqual(route["hub"], "شیخ هادی")
        self.assertEqual(route["total_price"], 20_000_000)  # آفر ۱ تومانی s2 حذف شده
        self.assertIn("hours", route["stops"][0])
        self.assertTrue(route["stops"][0]["items"][0]["offer_id"])

    def test_preferred_hub_is_honoured(self):
        self.assertEqual(self.router.solve_cart(["p1", "p3"], preferred_hub="شیخ هادی")["primary_route"]["hub"], "شیخ هادی")
        self.assertEqual(self.router.solve_cart(["p1", "p3"], preferred_hub="فردوسی")["primary_route"]["hub"], "فردوسی")

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
        self.assertEqual(tiers.get("s2"), 1)
        self.assertEqual(tiers.get("s3"), 2)
        self.assertTrue(all("hours" in f for f in r["recommended_fallbacks"]))

    def test_city_fallback_name_does_not_match_every_address(self):
        r = find_emergency_fallbacks(self.conn, "p1", "s6")
        self.assertEqual(r["layer1_count"] + r["layer2_count"], 0)

    def test_shop_without_address_does_not_crash(self):
        self.assertIn("recommended_fallbacks", find_emergency_fallbacks(self.conn, "p1", "s5"))


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

    def test_product_details_transparency(self):
        d = main.get_product_details("p1", hub=None, conn=make_db())
        self.assertEqual(d["product"]["min_price"], 18_000_000)
        self.assertEqual(d["product"]["specs"], [{"name": "رم", "value": "8 گیگابایت"}])
        flagged = [o for o in d["offers"] if o["is_copy"] or o["price_suspect"]]
        self.assertEqual(len(flagged), 2)
        s3 = next(o for o in d["offers"] if o["shop"]["shop_id"] == "s3")
        self.assertEqual(s3["shop"]["instagram"], "kalam_test")
        self.assertEqual([s["shop_id"] for s in d["category_only_shops"]], ["s7"])

    def test_hubs_count_only_shops_with_offers(self):
        with mock.patch.object(main, "DB_PATH", DB_FILE):
            hubs = {h["name"]: h for h in main.get_commercial_hubs(conn=self.conn)["hubs"]}
        self.assertEqual(hubs["شیخ هادی"]["shop_count"], 3)
        self.assertEqual(hubs["شیخ هادی"]["category_only_count"], 1)

    def test_complementary_patterns_and_no_unrelated_fallback(self):
        r = main.get_complementary_items("p1", shop_id="s2", conn=self.conn)
        self.assertEqual([c["product_id"] for c in r["recommendations"]], ["p2"])
        self.assertEqual(main.get_complementary_items("p4", shop_id=None, conn=self.conn)["recommendations"], [])

    def test_simulate_endpoint(self):
        r = main.simulate_inquiry_endpoint(main.InquirySimulationRequest(offer_id="o6c", question="availability"), conn=self.conn)
        self.assertTrue(r["simulated"])
        self.assertEqual(r["level"], "low")

    def test_cart_request_limit(self):
        with self.assertRaises(Exception):
            main.CartRouteRequest(product_ids=[str(i) for i in range(main.MAX_CART_ITEMS + 1)])


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.assistant = KalamAssistant(make_db())

    def test_panic_without_context_does_not_invent_data(self):
        self.assertEqual(self.assistant.process_message("مغازه بسته بود")["type"], "text")

    def test_panic_with_context(self):
        r = self.assistant.process_message("مغازه بسته بود", {"active_product_id": "p1", "active_shop_id": "s1"})
        self.assertEqual(r["type"], "panic_fallback")

    def test_empty_cart_route_does_not_invent_items(self):
        self.assertEqual(self.assistant.process_message("مسیر خرید رو بچین", {"cart_product_ids": []})["type"], "text")

    def test_one_sentence_with_place_and_credit(self):
        r = self.assistant.process_message("گوشی A55 قسطی در چارسو دارید؟")
        self.assertEqual([p["product_id"] for p in r["products"]], ["p1"])
        self.assertIn(r["products"][0]["best_shop"]["shop_id"], {"s2", "s3"})

    def test_memory_refines_previous_search(self):
        first = self.assistant.process_message("گوشی سامسونگ در چارسو")
        r = self.assistant.process_message("تا ۲۰ میلیون چی؟", state=first["state"])
        self.assertEqual(r["products"][0]["best_shop"]["price"], 20_000_000)
        r = self.assistant.process_message("قسطی هم داره؟", state=r["state"])
        self.assertEqual(r["products"], [])  # s1 اقساط ندارد؛ صادقانه «پیدا نشد»

    def test_tree_does_not_loop(self):
        r = self.assistant.process_message("دنبال یه کفش کتونی خوب برای پیاده‌روی هستم")
        self.assertEqual(r["type"], "diagnostic_tree")
        r = self.assistant.process_message("", tree={"category_key": "shoes", "option_index": 1, "budget_index": 1})
        self.assertEqual(r["type"], "product_search")
        self.assertEqual([p["product_id"] for p in r["products"]], ["p4"])

    def test_credit_shop_list_uses_persian_provider_names(self):
        r = self.assistant.process_message("فروشگاه‌های دارای اقساط اسنپ پی")
        self.assertEqual(r["type"], "credit_shops")
        self.assertEqual([s["shop_id"] for s in r["shops"]], ["s2"])

    def test_small_bag_is_not_credit(self):
        self.assertNotEqual(self.assistant.process_message("کیف کوچک")["type"], "credit_shops")

    def test_no_results_does_not_return_random_products(self):
        self.assertEqual(self.assistant.process_message("یخچال ساید بای ساید")["products"], [])

    def test_accessory_not_shown_as_phone(self):
        r = self.assistant.process_message("گوشی A55 تا ۱۵ میلیون")
        self.assertEqual(r["products"], [])


class LocationAndRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def test_search_reports_nearest_distance_and_max_km(self):
        p = next(p for p in search_products(self.conn, ["گوشی"], user_lat=35.76, user_lon=51.43))
        self.assertLess(p["nearest_km"], 0.1)  # s4 دقیقاً در همین نقطه است
        far = search_products(self.conn, ["دریل"], user_lat=35.69, user_lon=51.41, max_km=1)
        self.assertEqual([x["available_offline_shops_count"] for x in far], [1])

    def test_recommendation_prefers_cheap_near_open_and_explains(self):
        offers = [
            {"offer_id": "a", "price_toman": 100, "distance_km": 8.0, "hours_state": "closed", "days_since_update": 90},
            {"offer_id": "b", "price_toman": 105, "distance_km": 0.4, "hours_state": "open", "days_since_update": 2},
            {"offer_id": "c", "price_toman": 10, "is_copy": True, "distance_km": 0.1, "hours_state": "open", "days_since_update": 1},
        ]
        r = rank_offers(offers)
        self.assertEqual(r["offer_id"], "b")
        self.assertTrue(any("نزدیک‌ترین" in x for x in r["reasons"]))
        self.assertTrue(any("الان باز" in x for x in r["reasons"]))
        self.assertNotIn("c", r["scores"])  # آفر کپی رتبه‌بندی نمی‌شود

    def test_recommendation_without_location_ignores_distance(self):
        r = rank_offers([{"offer_id": "a", "price_toman": 100}, {"offer_id": "b", "price_toman": 200}])
        self.assertEqual(r["offer_id"], "a")
        self.assertFalse(r["used_distance"])

    def test_product_api_returns_distance_and_recommendation(self):
        d = main.get_product_details("p1", hub=None, lat=35.69, lon=51.41, conn=make_db())
        self.assertIsNotNone(d["recommendation"])
        s1 = next(o for o in d["offers"] if o["shop"]["shop_id"] == "s1")
        self.assertLess(s1["distance_km"], 0.1)

    def test_nearest_in_chat(self):
        r = KalamAssistant(make_db()).process_message("نزدیک‌ترین گوشی سامسونگ", {"user_lat": 35.76, "user_lon": 51.43})
        self.assertEqual(r["products"][0]["best_shop"]["shop_id"], "s4")


class VisitAndFollowUpTests(unittest.TestCase):
    def test_common_window(self):
        sat_15 = datetime(2026, 10, 24, 15, 0, tzinfo=TEHRAN_TZ)
        a = '{"saturday": "10:00-14:00, 16:00-21:00", "sunday": "10-20"}'
        b = '{"saturday": "09:00-18:00", "sunday": "09:00-18:00"}'
        r = common_open_window([a, b, "{}"], sat_15)
        self.assertTrue(r["found"])
        self.assertIn("امروز از ۱۶:۰۰ تا ۱۸:۰۰", r["label"])
        self.assertEqual(r["unknown_count"], 1)
        self.assertFalse(common_open_window(["{}"])["found"])

    def test_route_has_visit_plan(self):
        r = InPersonCartRouter(make_db()).solve_cart(["p1"])
        self.assertIn("visit_plan", r)

    def test_follow_up_decision_and_alternatives(self):
        conn = make_db()
        r = follow_up(conn, "o6c")  # آفر کپی
        self.assertTrue(r["simulated"])
        self.assertEqual(r["decision"]["action"], "alternative")
        self.assertTrue(r["alternatives"])
        r = follow_up(conn, "o9")   # s3 همیشه باز، اینستاگرام واقعی
        self.assertIn("instagram", [c["type"] for c in r["contact_channels"]])
        self.assertEqual(r["steps"][0]["status"], "ok")
        self.assertIsNone(follow_up(conn, "missing"))

    def test_visit_intent(self):
        r = KalamAssistant(make_db()).process_message("کی برم که همه باز باشن؟", {"cart_product_ids": ["p1"]})
        self.assertEqual(r["type"], "cart_route")
        self.assertIn("بهترین زمان مراجعه", r["message"])


if __name__ == "__main__":
    unittest.main()
