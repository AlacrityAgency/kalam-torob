#!/usr/bin/env python3
"""
ساخت پایگاه داده SQLite کَلَم (torob.db) از CSVهای دیتاست ترب.

    python scripts/build_db.py                 # از CSVهای پوشه dataset/
    python scripts/build_db.py dataset.zip     # استخراج از zip و ساخت

- جدول‌های shops / products / offers با NULL واقعی به جای رشته "null"
- ستون‌های محاسبه‌شده: درگاه‌های اقساطی نرمال‌شده، مشخص بودن ساعت کاری، فروشگاه‌های دارای
  هویت آنلاین واقعی، برچسب آفر کپی/غیراصل و قیمت پرت
- جدول‌های آماری پیش‌محاسبه‌شده (product_stats، hub_stats، suggested_products) تا صفحه اول
  و فهرست مراکز خرید روی دیتاست کامل در چند میلی‌ثانیه پاسخ دهند
- FTS5 برای جستجوی تمام‌متن فارسی
- ساخت در فایل موقت و جایگزینی اتمیک، تا سرور در حال اجرا با پایگاه داده نیمه‌کاره روبه‌رو نشود

مسیر خروجی با متغیر محیطی KALAM_DB_PATH قابل تغییر است (برای دیسک دائمی در دیپلوی).
"""

import csv
import json
import os
import sqlite3
import sys
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

from backend.algorithms.credipay import analyze_payment_options  # noqa: E402
from backend.algorithms.hours import parse_weekly_hours  # noqa: E402
from backend.algorithms.offer_quality import is_copy_text, suspicious_prices  # noqa: E402

DATASET_DIR = os.path.join(WORKSPACE, "dataset")
DB_PATH = os.environ.get("KALAM_DB_PATH") or os.path.join(WORKSPACE, "torob.db")
SAMPLE_MARKER = os.path.join(DATASET_DIR, "SAMPLE_DATA")

# ستون‌های JSON (مثل specs) می‌توانند از سقف پیش‌فرض ۱۳۱ هزار کاراکتر ماژول csv بزرگ‌تر باشند.
# عدد ثابت به جای sys.maxsize، چون در ویندوز sys.maxsize از long زبان C بزرگ‌تر است.
csv.field_size_limit(2**31 - 1)

REQUIRED_FILES = ("shops.csv", "products.csv", "offers.csv")

# قوانین مکمل با الگوی LIKE روی نام دسته (نه نام دقیق)، تا با نام‌گذاری دیتاست واقعی هم کار کند.
# (الگوی دسته مبدأ، الگوی دسته مکمل، رده، وزن وابستگی، توضیح)
COMPLEMENTARY_RULES = [
    ("%گوشی موبایل%", "%کاور%گوشی%", 2, 0.65, "کاور برای محافظت بدنه"),
    ("%گوشی موبایل%", "%محافظ صفحه%", 2, 0.65, "محافظ صفحه نمایش"),
    ("%گوشی موبایل%", "%شارژر%", 2, 0.65, "شارژر و آداپتور"),
    ("%گوشی موبایل%", "%هندزفری%", 3, 0.30, "هندزفری یا هدفون"),
    ("%تبلت%", "%کاور%تبلت%", 2, 0.65, "کیف و کاور تبلت"),
    ("%تبلت%", "%محافظ صفحه%", 2, 0.65, "محافظ صفحه نمایش"),
    ("%لپ%تاپ%", "%ماوس%", 2, 0.65, "ماوس"),
    ("%لپ%تاپ%", "%کیف%لپ%", 2, 0.65, "کیف لپ‌تاپ"),
    ("%لپ%تاپ%", "%کول%لپ%", 2, 0.65, "کوله لپ‌تاپ"),
    ("%لپ%تاپ%", "%پایه خنک%", 3, 0.30, "پایه خنک‌کننده"),
    ("%ساعت%هوشمند%", "%بند%ساعت%", 3, 0.30, "بند یدک ساعت"),
    ("%دوربین مدار%", "%هارد%", 1, 1.0, "هارد ضبط تصاویر"),
    ("%دوربین مدار%", "%دی وی آر%", 1, 1.0, "دستگاه ضبط (DVR/NVR)"),
    ("%دوربین مدار%", "%کانکتور%", 1, 1.0, "فیش و اتصالات"),
    ("%دوربین مدار%", "%کابل%", 1, 1.0, "کابل تصویر و برق"),
    ("%کتانی%", "%جوراب%", 3, 0.30, "جوراب ورزشی"),
    ("%کفش%", "%جوراب%", 3, 0.30, "جوراب"),
    ("%کفش%", "%کفی%", 3, 0.30, "کفی طبی"),
    ("%دریل%", "%مته%", 1, 1.0, "مته متناسب"),
    ("%دریل%", "%سه نظام%", 2, 0.65, "سه‌نظام"),
    ("%پمپ%", "%لوازم جانبی پمپ%", 1, 1.0, "ست‌کنترل و منبع تحت فشار"),
    ("%پمپ%", "%ست کنترل%", 1, 1.0, "ست‌کنترل اتوماتیک"),
    ("%سیم و کابل%", "%فیوز%", 1, 1.0, "فیوز متناسب با قطر کابل"),
    ("%سیم و کابل%", "%کلید و پریز%", 2, 0.65, "کلید و پریز"),
    ("%سیم و کابل%", "%داکت%", 2, 0.65, "داکت و ترانکینگ"),
    ("%رله%", "%کنتاکتور%", 1, 1.0, "کنتاکتور"),
    ("%کنتاکتور%", "%فیوز%", 1, 1.0, "حفاظت بالادست"),
    ("%پروژکتور%", "%سنسور%", 1, 1.0, "سنسور حرکتی و فتوسل"),
]


def extract_dataset_zip(zip_path):
    """استخراج shops/products/offers.csv از فایل zip دیتاست (در هر پوشه‌ای از zip) به پوشه dataset/"""
    os.makedirs(DATASET_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = {os.path.basename(m): m for m in zf.namelist() if not m.endswith("/")}
        missing = [name for name in REQUIRED_FILES if name not in members]
        if missing:
            sys.exit(f"این فایل‌ها در zip پیدا نشدند: {', '.join(missing)}")
        for name in REQUIRED_FILES:
            print(f"Extracting {members[name]} -> dataset/{name}")
            with zf.open(members[name]) as src, open(os.path.join(DATASET_DIR, name), "wb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
    # داده واقعی جایگزین داده نمونه شد
    if os.path.exists(SAMPLE_MARKER):
        os.remove(SAMPLE_MARKER)


def check_dataset_files():
    missing = [n for n in REQUIRED_FILES if not os.path.exists(os.path.join(DATASET_DIR, n))]
    if missing:
        sys.exit(
            f"فایل‌های {', '.join(missing)} در پوشه dataset/ نیستند.\n"
            "مسیر zip دیتاست را بدهید:  python scripts/build_db.py path/to/dataset.zip\n"
            "یا برای داده نمونه:        python scripts/generate_sample_dataset.py"
        )


def nz(value):
    """دیتاست مقادیر خالی را با رشته null می‌نویسد؛ در پایگاه داده NULL واقعی ذخیره می‌شود."""
    if value is None:
        return None
    value = value.strip()
    return None if value in ("", "null") else value


def to_float(value):
    value = nz(value)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def read_csv(name):
    with open(os.path.join(DATASET_DIR, name), "r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE shops (
    shop_id TEXT PRIMARY KEY,
    name TEXT,
    address TEXT,
    location_label TEXT,
    lat REAL,
    lon REAL,
    payment_options TEXT,
    contacts TEXT,
    weekly_hours TEXT,
    instagram TEXT,
    website_url TEXT,
    supports_fast_delivery INTEGER,
    category_names TEXT,
    credit_providers TEXT,          -- کلیدهای نرمال‌شده با کاما: snapp_pay,torob_pay
    has_in_person_credit INTEGER,
    hours_known INTEGER,
    is_verified INTEGER,            -- اینستاگرام یا وب‌سایت واقعی دارد
    offer_count INTEGER DEFAULT 0
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    persian_title TEXT,
    category_name TEXT,
    brand_name TEXT,
    model TEXT,
    specs TEXT,
    image_urls TEXT
);

CREATE TABLE offers (
    offer_id TEXT PRIMARY KEY,
    product_id TEXT,
    shop_id TEXT,
    price_toman INTEGER,
    last_price_changed_at TEXT,
    warranty TEXT,
    description TEXT,
    seller_title TEXT,
    is_copy INTEGER DEFAULT 0,
    price_suspect INTEGER DEFAULT 0
);

CREATE VIRTUAL TABLE products_fts USING fts5(
    product_id UNINDEXED, persian_title, category_name, brand_name, model, tokenize='unicode61'
);

CREATE TABLE complementary_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_pattern TEXT,
    target_pattern TEXT,
    tier INTEGER,
    dep_score REAL,
    description_fa TEXT
);

CREATE TABLE product_stats (
    product_id TEXT PRIMARY KEY,
    min_price INTEGER,        -- از آفرهای سالم (غیر کپی، قیمت غیرپرت)
    max_price INTEGER,
    shop_count INTEGER,       -- فروشگاه‌های دارای قیمت ثبت‌شده
    offer_count INTEGER,
    flagged_count INTEGER     -- آفرهای کپی یا قیمت پرت
);

CREATE TABLE hub_stats (
    location_label TEXT PRIMARY KEY,
    shops_with_offers INTEGER,
    category_only_shops INTEGER,
    offer_count INTEGER
);

CREATE TABLE suggested_products (rank INTEGER PRIMARY KEY, product_id TEXT);
"""


def build(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA cache_size = -64000;")
    cur.execute("PRAGMA temp_store = MEMORY;")
    cur.executescript(SCHEMA)

    print("Loading shops...")
    shops = []
    for r in read_csv("shops.csv"):
        payment = nz(r.get("payment_options"))
        credit = analyze_payment_options(payment)
        hours = nz(r.get("weekly_hours"))
        instagram, website = nz(r.get("instagram")), nz(r.get("website_url"))
        fast = r.get("supports_fast_delivery")
        shops.append((
            r["shop_id"], nz(r.get("name")), nz(r.get("address")), nz(r.get("location_label")),
            to_float(r.get("lat")), to_float(r.get("lon")), payment, nz(r.get("contacts")), hours,
            instagram, website, 1 if fast == "true" else 0 if fast == "false" else None,
            nz(r.get("category_names")),
            ",".join(credit["supported_providers"]) or None,
            1 if any(b["is_in_person"] for b in credit["badges"]) else 0,
            1 if parse_weekly_hours(hours)["known"] else 0,
            1 if (instagram or website) else 0,
        ))
    cur.executemany("INSERT INTO shops (shop_id, name, address, location_label, lat, lon, payment_options, contacts, "
                    "weekly_hours, instagram, website_url, supports_fast_delivery, category_names, credit_providers, "
                    "has_in_person_credit, hours_known, is_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", shops)
    print(f"  {len(shops):,} shops")

    print("Loading products...")
    titles = {}
    batch = []
    for r in read_csv("products.csv"):
        row = (r["product_id"], nz(r.get("persian_title")), nz(r.get("category_name")), nz(r.get("brand_name")),
               nz(r.get("model")), nz(r.get("specs")), nz(r.get("image_urls")))
        titles[r["product_id"]] = row[1]
        batch.append(row)
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?)", batch)
    cur.executemany("INSERT INTO products_fts VALUES (?,?,?,?,?)", [(b[0], b[1], b[2], b[3], b[4]) for b in batch])
    print(f"  {len(batch):,} products")
    del batch

    print("Loading offers and computing quality flags...")
    offers = []
    for r in read_csv("offers.csv"):
        price = nz(r.get("price_toman"))
        try:
            price = int(float(price)) if price is not None else None
        except ValueError:
            price = None
        seller_title, description = nz(r.get("seller_title")), nz(r.get("description"))
        is_copy = is_copy_text(seller_title, description, titles.get(r["product_id"]))
        offers.append([r["offer_id"], r["product_id"], r["shop_id"], price, nz(r.get("last_price_changed_at")),
                       nz(r.get("warranty")), description, seller_title, 1 if is_copy else 0, 0])

    by_product = defaultdict(list)
    for i, o in enumerate(offers):
        by_product[o[1]].append(i)
    for idxs in by_product.values():
        # آفرهای کپی در محاسبه میانه نیستند تا قیمت اصل را پایین نکشند
        clean = [i for i in idxs if not offers[i][8]]
        for j in suspicious_prices([offers[i][3] for i in clean]):
            offers[clean[j]][9] = 1
    cur.executemany("INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?)", offers)
    print(f"  {len(offers):,} offers ({sum(o[8] for o in offers):,} copy, {sum(o[9] for o in offers):,} suspicious price)")
    del offers, by_product, titles

    print("Indexes...")
    cur.executescript("""
    CREATE INDEX idx_offers_product ON offers(product_id, price_toman);
    CREATE INDEX idx_offers_shop ON offers(shop_id);
    CREATE INDEX idx_shops_location ON shops(location_label);
    CREATE INDEX idx_products_category ON products(category_name);
    """)

    print("Precomputing stats...")
    cur.executescript("""
    UPDATE shops SET offer_count = (SELECT count(*) FROM offers o WHERE o.shop_id = shops.shop_id);

    INSERT INTO product_stats
    SELECT o.product_id,
           min(CASE WHEN o.is_copy = 0 AND o.price_suspect = 0 THEN o.price_toman END),
           max(CASE WHEN o.is_copy = 0 AND o.price_suspect = 0 THEN o.price_toman END),
           count(DISTINCT CASE WHEN o.price_toman IS NOT NULL THEN o.shop_id END),
           count(*),
           sum(o.is_copy OR o.price_suspect)
    FROM offers o GROUP BY o.product_id;

    INSERT INTO hub_stats
    SELECT location_label,
           sum(offer_count > 0),
           sum(offer_count = 0 AND category_names IS NOT NULL),
           sum(offer_count)
    FROM shops WHERE location_label IS NOT NULL GROUP BY location_label;

    INSERT INTO suggested_products (product_id)
    SELECT product_id FROM product_stats
    WHERE min_price > 200000 AND shop_count >= 3
    ORDER BY shop_count DESC, product_id LIMIT 12;
    """)

    cur.executemany("INSERT INTO complementary_rules (source_pattern, target_pattern, tier, dep_score, description_fa) "
                    "VALUES (?,?,?,?,?)", COMPLEMENTARY_RULES)
    source = "sample" if os.path.exists(SAMPLE_MARKER) else "dataset"
    cur.executemany("INSERT INTO meta VALUES (?,?)", [
        ("data_source", source),
        ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
    ])
    conn.commit()
    cur.execute("PRAGMA optimize;")
    conn.close()
    return source


def verify(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    print("\n--- Database Verification ---")
    for tbl in ["shops", "products", "offers", "products_fts", "product_stats", "hub_stats", "complementary_rules"]:
        print(f"Table {tbl}: {cur.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]:,} rows")
    t0 = time.time()
    cur.execute("SELECT product_id FROM products_fts WHERE products_fts MATCH '\"آیفون\"*' ORDER BY rank LIMIT 20")
    cur.fetchall()
    print(f"FTS5 search benchmark: {(time.time() - t0) * 1000:.2f} ms")
    conn.close()


def replace_db(tmp_path, final_path):
    for suffix in ("-wal", "-shm"):
        if os.path.exists(final_path + suffix):
            try:
                os.remove(final_path + suffix)
            except OSError:
                pass
    try:
        os.replace(tmp_path, final_path)
    except PermissionError:
        sys.exit("پایگاه داده قبلی در حال استفاده است (احتمالاً سرور روشن است). سرور را ببندید و دوباره اجرا کنید.")


if __name__ == "__main__":
    t_start = time.time()
    if len(sys.argv) > 1:
        extract_dataset_zip(sys.argv[1])
    check_dataset_files()
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    tmp = DB_PATH + ".building"
    for path in (tmp, tmp + "-wal", tmp + "-shm"):
        if os.path.exists(path):
            os.remove(path)
    source = build(tmp)
    # فایل WAL را در فایل اصلی ادغام کن تا جابه‌جایی یک فایل کامل باشد
    c = sqlite3.connect(tmp)
    c.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    c.execute("PRAGMA journal_mode = DELETE;")
    c.close()
    replace_db(tmp, DB_PATH)
    verify(DB_PATH)
    print(f"\nData source: {source}. Built {DB_PATH} in {time.time() - t_start:.1f}s.")
