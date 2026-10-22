#!/usr/bin/env python3
"""
بنچمارک کَلَم در مقیاس دیتاست واقعی (داده ساختگی با همان ابعاد و ساختار).

    python scripts/benchmark.py            # ساخت داده هم‌اندازه، ساخت پایگاه داده، اندازه‌گیری
    python scripts/benchmark.py --db path  # اندازه‌گیری روی یک torob.db موجود (مثلاً دیتاست واقعی)

خروجی: جدول زمان پاسخ (میانه و صدک ۹۵) برای اندپوینت‌های اصلی در docs/benchmark.md.
زمان‌ها از فراخوانی مستقیم توابع اندپوینت با اتصال تازه SQLite است (بدون سربار HTTP).
"""

import argparse
import contextlib
import csv
import io
import json
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

N_SHOPS, N_PRODUCTS, N_OFFERS = 6_476, 225_903, 331_506

CATS = ["گوشی موبایل", "لپ تاپ و نوت بوک", "هدفون، هدست و هندزفری", "کیف و کاور گوشی", "محافظ صفحه نمایش گوشی",
        "شارژر تبلت و موبایل", "کتانی و کفش اسپرت", "دوربین مدار بسته", "سیم و کابل برق ساختمان", "دریل و پیچ گوشتی برقی",
        "ماوس", "ساعت و مچ بند هوشمند", "لوازم آشپزخانه", "روشنایی و لامپ", "قطعات کامپیوتر"]
BRANDS = ["سامسونگ", "شیائومی", "اپل", "ایسوس", "لنوو", "اچ پی", "نایکی", "آدیداس", "رونیکس", "بوش", "انکر", "لاجیتک", "هایک ویژن"]
WORDS = ["مدل", "پرو", "مکس", "لایت", "پلاس", "اولترا", "مشکی", "سفید", "ظرفیت", "گیگابایت", "اورجینال", "طرح جدید"]
AREAS = [("فردوسی", 35.690, 51.420, 0.5), ("شیخ هادی", 35.693, 51.405, 0.25), ("بهارستان", 35.692, 51.432, 0.1),
         ("آسمان", 35.79, 51.48, 0.03), ("باغ فیض", 35.725, 51.33, 0.03), ("ایرانشهر", 35.708, 51.42, 0.03),
         ("سنائی", 35.715, 51.41, 0.02), ("تجریش", 35.805, 51.43, 0.02), ("سهروردی", 35.725, 51.435, 0.02)]
MALLS = ["مرکز کامپیوتر ایران", "مرکز کامپیوتر نور", "بازار بزرگ چارسو", "پاساژ علاءالدین", "پاساژ الکترونیک امجد", "مجتمع تجاری کوروش"]
HOURS = [{}, {"saturday": "10:00-20:00", "sunday": "10:00-20:00", "monday": "10:00-20:00", "tuesday": "10:00-20:00",
              "wednesday": "10:00-20:00", "thursday": "10:00-14:00"},
         {"شنبه": ["10:00-14:00", "16:00-21:00"], "پنجشنبه": ["10:00-15:00"], "جمعه": ["16:00-20:00"]}]
PAY = [None, None, None, None, [{"provider_name": "ترب‌پی", "channel": "in_person"}],
       [{"provider_name": "اسنپ‌پی", "channel": "unknown"}], [{"provider_name": "دیجی‌پی", "channel": "online"}]]


def generate(folder):
    rnd = random.Random(1405)
    with open(os.path.join(folder, "shops.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shop_id", "name", "address", "location_label", "lat", "lon", "payment_options", "contacts",
                    "weekly_hours", "instagram", "website_url", "category_names", "supports_fast_delivery"])
        for i in range(N_SHOPS):
            area, lat, lon, _ = rnd.choices(AREAS, weights=[a[3] for a in AREAS])[0]
            pay = rnd.choice(PAY)
            w.writerow([f"s{i}", f"فروشگاه {i}", f"تهران، {rnd.choice(MALLS)}، طبقه {rnd.choice(['همکف', 'اول', 'دوم', 'منفی یک'])}، واحد {rnd.randint(1, 400)}",
                        area, lat + rnd.uniform(-0.01, 0.01), lon + rnd.uniform(-0.01, 0.01),
                        json.dumps(pay, ensure_ascii=False) if pay else "null",
                        json.dumps([{"channel": "phone", "display_number": "02100000000"}]),
                        json.dumps(rnd.choice(HOURS), ensure_ascii=False), "null", "null",
                        json.dumps(rnd.sample(CATS, 2), ensure_ascii=False), "null"])
    with open(os.path.join(folder, "products.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "persian_title", "category_name", "brand_name", "model", "specs", "image_urls"])
        for i in range(N_PRODUCTS):
            cat, brand = rnd.choice(CATS), rnd.choice(BRANDS)
            title = f"{cat.split('،')[0]} {brand} {' '.join(rnd.sample(WORDS, 3))} {rnd.randint(1, 999)}"
            w.writerow([f"p{i}", title, cat, brand if rnd.random() < 0.25 else "null", "null",
                        json.dumps({"وزن": f"{rnd.randint(100, 900)} گرم"}, ensure_ascii=False) if rnd.random() < 0.64 else "null", "[]"])
    with open(os.path.join(folder, "offers.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["offer_id", "product_id", "shop_id", "price_toman", "last_price_changed_at", "seller_title", "warranty", "description"])
        popular = [f"p{i}" for i in range(40_000)]
        for i in range(N_OFFERS):
            pid = f"p{i}" if i < N_PRODUCTS else rnd.choice(popular)  # هر کالا حداقل یک آفر؛ بقیه روی کالاهای پرتکرار
            price = "null" if rnd.random() < 0.045 else str(rnd.randint(100, 50_000) * 1_000)
            w.writerow([f"o{i}", pid, f"s{rnd.randrange(N_SHOPS)}", price,
                        f"2026-{rnd.randint(1, 10):02d}-{rnd.randint(1, 28):02d}T10:00:00Z", "null", "null", "null"])


def timed(fn, runs):
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return statistics.median(samples), samples[max(0, int(len(samples) * 0.95) - 1)]


def measure(db_path, runs=30):
    from backend import main
    from backend.assistant import KalamAssistant

    conn = lambda: sqlite3.connect(db_path)  # noqa: E731
    pid = sqlite3.connect(db_path).execute(
        "SELECT product_id FROM product_stats ORDER BY shop_count DESC LIMIT 1").fetchone()[0]
    oid = sqlite3.connect(db_path).execute("SELECT offer_id FROM offers WHERE product_id = ? LIMIT 1", (pid,)).fetchone()[0]
    search_args = dict(hub=None, category=None, limit=60, min_price=None, max_price=None, credit=False, provider=None,
                       fresh=False, hours_known=False, open_now=False, include_copies=False, lat=None, lon=None, max_km=None)
    cases = [
        ("صفحه اول: کالاهای پیشنهادی", lambda: (main._CACHE.clear(), main.get_suggested_products(conn=conn()))),
        ("فهرست محدوده‌ها", lambda: (main._CACHE.clear(), main.get_commercial_hubs(conn=conn()))),
        ("جستجو «گوشی سامسونگ»", lambda: main.search_endpoint(q="گوشی سامسونگ", conn=conn(), **search_args)),
        ("جستجو با اقساط، الان باز و فاصله", lambda: main.search_endpoint(
            q="هدفون", conn=conn(), **{**search_args, "credit": True, "open_now": True, "lat": 35.69, "lon": 51.42})),
        ("صفحه کالا با موقعیت کاربر", lambda: main.get_product_details(pid, hub=None, lat=35.69, lon=51.42, conn=conn())),
        ("کالاهای مکمل", lambda: main.get_complementary_items(pid, shop_id=None, conn=conn())),
        ("پیگیری خودکار با فروشنده", lambda: main.agent_follow_up(main.FollowUpRequest(offer_id=oid), conn=conn())),
        ("دستیار: «گوشی سامسونگ قسطی در فردوسی تا ۲۰ میلیون»", lambda: KalamAssistant(conn()).process_message(
            "گوشی سامسونگ قسطی در فردوسی تا ۲۰ میلیون")),
    ]
    with mock.patch.object(main, "DB_PATH", db_path):
        return [(name, *timed(fn, runs)) for name, fn in cases]


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="اندازه‌گیری روی پایگاه داده موجود")
    ap.add_argument("--runs", type=int, default=30)
    args = ap.parse_args()

    tmp = None
    db = args.db
    build_s = None
    if not db:
        import build_db

        tmp = tempfile.mkdtemp(prefix="kalam-bench-")
        print("Generating full-size synthetic dataset...")
        generate(tmp)
        db = os.path.join(tmp, "bench.db")
        t0 = time.perf_counter()
        with mock.patch.object(build_db, "DATASET_DIR", tmp), mock.patch.object(build_db, "SAMPLE_MARKER", os.path.join(tmp, "x")), \
                contextlib.redirect_stdout(io.StringIO()):
            build_db.build(db)
        build_s = time.perf_counter() - t0

    c = sqlite3.connect(db)
    counts = [c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("shops", "products", "offers")]
    size_mb = os.path.getsize(db) / 1e6
    rows = measure(db, args.runs)

    lines = [
        "# بنچمارک کَلَم",
        "",
        f"داده: {'ساختگی هم‌اندازه دیتاست واقعی' if not args.db else 'پایگاه داده ' + os.path.basename(db)} — "
        f"{counts[0]:,} فروشگاه، {counts[1]:,} کالا، {counts[2]:,} آفر؛ حجم پایگاه داده {size_mb:.0f} مگابایت"
        + (f"؛ زمان ساخت {build_s:.0f} ثانیه" if build_s else "") + ".",
        f"هر مورد {args.runs} بار با اتصال تازه SQLite اجرا شده (بدون سربار HTTP).",
        "",
        "| عملیات | میانه (ms) | صدک ۹۵ (ms) |",
        "|---|---|---|",
    ] + [f"| {n} | {m:.1f} | {p:.1f} |" for n, m, p in rows]
    report = "\n".join(lines) + "\n"
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "benchmark.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main_cli()
