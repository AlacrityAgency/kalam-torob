#!/usr/bin/env python3
"""
Build high-performance SQLite database (torob.db) from Torob dataset CSVs.
Features:
- Normalized tables: shops, products, offers
- FTS5 full-text search virtual table for instant Persian text searching
- B-Tree indexes on shop_id, product_id, location_label, price_toman
- WAL mode enabled for maximum concurrent read performance
"""

import csv
import json
import os
import sqlite3
import time

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(WORKSPACE, "dataset")
DB_PATH = os.path.join(WORKSPACE, "torob.db")

def init_db():
    if os.path.exists(DB_PATH):
        print(f"Removing existing {DB_PATH}...")
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Optimization pragmas
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA cache_size = -64000;")
    cursor.execute("PRAGMA temp_store = MEMORY;")

    print("Creating tables...")
    cursor.execute("""
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
        supports_fast_delivery INTEGER
    );
    """)

    cursor.execute("""
    CREATE TABLE products (
        product_id TEXT PRIMARY KEY,
        persian_title TEXT,
        category_name TEXT,
        brand_name TEXT,
        model TEXT,
        specs TEXT,
        image_urls TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE offers (
        offer_id TEXT PRIMARY KEY,
        product_id TEXT,
        shop_id TEXT,
        price_toman INTEGER,
        last_price_changed_at TEXT,
        warranty TEXT,
        description TEXT,
        seller_title TEXT,
        FOREIGN KEY (product_id) REFERENCES products(product_id),
        FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
    );
    """)

    # FTS5 full text search table
    cursor.execute("""
    CREATE VIRTUAL TABLE products_fts USING fts5(
        product_id UNINDEXED,
        persian_title,
        category_name,
        brand_name,
        model,
        tokenize='unicode61'
    );
    """)

    # Knowledge base for complementary products (PACO Engine)
    cursor.execute("""
    CREATE TABLE complementary_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_category TEXT,
        target_category TEXT,
        tier INTEGER,           -- 1: Mandatory Operational, 2: Protection/Durability, 3: Optional Accessory
        dep_score REAL,         -- 1.0 (Tier 1), 0.65 (Tier 2), 0.3 (Tier 3)
        description_fa TEXT
    );
    """)

    conn.commit()
    conn.close()

def populate_shops():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    csv_path = os.path.join(DATASET_DIR, "shops.csv")
    print(f"Loading {csv_path}...")
    
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lat = float(r["lat"]) if r["lat"] and r["lat"] != "null" else None
            lon = float(r["lon"]) if r["lon"] and r["lon"] != "null" else None
            fast_del = 1 if r.get("supports_fast_delivery") == "true" else 0
            rows.append((
                r["shop_id"],
                r["name"],
                r["address"],
                r["location_label"],
                lat,
                lon,
                r["payment_options"],
                r["contacts"],
                r["weekly_hours"],
                r.get("instagram"),
                r.get("website_url"),
                fast_del
            ))
            
    cursor.executemany("""
    INSERT INTO shops (
        shop_id, name, address, location_label, lat, lon,
        payment_options, contacts, weekly_hours, instagram, website_url, supports_fast_delivery
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} shops.")
    conn.close()

def populate_products():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    csv_path = os.path.join(DATASET_DIR, "products.csv")
    print(f"Loading {csv_path}...")

    rows = []
    fts_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pid = r["product_id"]
            title = r["persian_title"]
            cat = r["category_name"]
            brand = r["brand_name"]
            model = r["model"]
            rows.append((
                pid,
                title,
                cat,
                brand,
                model,
                r["specs"],
                r["image_urls"]
            ))
            fts_rows.append((
                pid,
                title,
                cat,
                brand,
                model
            ))

    cursor.executemany("""
    INSERT INTO products (
        product_id, persian_title, category_name, brand_name, model, specs, image_urls
    ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, rows)

    cursor.executemany("""
    INSERT INTO products_fts (
        product_id, persian_title, category_name, brand_name, model
    ) VALUES (?, ?, ?, ?, ?);
    """, fts_rows)

    conn.commit()
    print(f"Inserted {len(rows)} products and FTS index.")
    conn.close()

def populate_offers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    csv_path = os.path.join(DATASET_DIR, "offers.csv")
    print(f"Loading {csv_path}...")

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            price = None
            if r["price_toman"] and r["price_toman"] != "null":
                try:
                    price = int(r["price_toman"])
                except:
                    price = None
            rows.append((
                r["offer_id"],
                r["product_id"],
                r["shop_id"],
                price,
                r["last_price_changed_at"],
                r.get("warranty"),
                r.get("description"),
                r.get("seller_title")
            ))

    cursor.executemany("""
    INSERT INTO offers (
        offer_id, product_id, shop_id, price_toman, last_price_changed_at, warranty, description, seller_title
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} offers.")
    conn.close()

def populate_complementary_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("Populating complementary rules...")
    
    rules = [
        # Mobile & Tech
        ("کیف و کاور گوشی", "محافظ صفحه نمایش گوشی و تبلت", 1, 1.0, "محافظت کامل صفحه نمایش در برابر ضربه"),
        ("کیف و کاور گوشی", "شارژر تبلت و موبایل", 2, 0.65, "شارژر اصلی با توان استاندارد و کابل تقویت‌شده"),
        ("کیف و کاور گوشی", "هدفون، هدست و هندزفری", 3, 0.30, "هندزفری بلوتوثی یا باسیم همراه"),
        
        # Security & CCTV
        ("دوربین مدار بسته", "سوکت و کانکتور", 1, 1.0, "فیش و اتصالات BNC برای انتقال تصویر بدون نویز"),
        ("دوربین مدار بسته", "سیم و کابل برق ساختمان", 1, 1.0, "کابل کواکسیال ترکیبی RG59 تصویر و برق"),
        ("دوربین مدار بسته", "هارد دیسک", 1, 1.0, "هارد نظارتی ضبط مداوم تصاویر امنیتی"),
        
        # Electrical & Building
        ("سیم و کابل برق ساختمان", "کلید و فیوز مینیاتوری", 1, 1.0, "فیوز محافظت جریان و اضافه بار متناسب با قطر کابل"),
        ("سیم و کابل برق ساختمان", "کلید و پریز", 2, 0.65, "پریز استاندارد ارت‌دار برای انتهای خط"),
        ("سیم و کابل برق ساختمان", "داکت و ترانکینگ", 2, 0.65, "محافظت و زیبایی مسیر سیم‌کشی روکار"),
        
        # Lighting
        ("چراغ پنلی و سقفی", "پروژکتور و وال واشر", 2, 0.65, "روشنایی محوطه و تکمیل نورپردازی"),
        ("پروژکتور و وال واشر", "سنسور حرکتی و فتوسل", 1, 1.0, "کنترل هوشمند خاموش/روشن روشنایی شبانه"),
        
        # Industrial & Pumps
        ("پمپ خانگی و صنعتی", "لوازم جانبی پمپ", 1, 1.0, "ست‌کنترل اتوماتیک، پنج‌راهی برنجی و منبع انبساط"),
        ("رله و بیمتال", "کنتاکتور", 1, 1.0, "کنتاکتور متناسب جهت قطع و وصل بار قدرت"),
        ("کنتاکتور", "کلید و فیوز مینیاتوری", 1, 1.0, "حفاظت بالادست مدار فرمان و قدرت")
    ]
    
    cursor.executemany("""
    INSERT INTO complementary_rules (
        source_category, target_category, tier, dep_score, description_fa
    ) VALUES (?, ?, ?, ?, ?);
    """, rules)
    conn.commit()
    conn.close()

def create_indexes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("Creating B-Tree indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_offers_product ON offers(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_offers_shop ON offers(shop_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_offers_price ON offers(price_toman);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shops_location ON shops(location_label);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_name);")
    conn.commit()
    conn.close()

def verify_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("\n--- Database Verification ---")
    
    for tbl in ["shops", "products", "offers", "products_fts", "complementary_rules"]:
        cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
        cnt = cursor.fetchone()[0]
        print(f"Table {tbl}: {cnt:,} rows")
        
    # Quick sample search test
    t0 = time.time()
    cursor.execute("""
    SELECT p.persian_title, p.category_name, o.price_toman, s.name, s.location_label, s.address
    FROM products_fts f
    JOIN products p ON f.product_id = p.product_id
    JOIN offers o ON p.product_id = o.product_id
    JOIN shops s ON o.shop_id = s.shop_id
    WHERE products_fts MATCH 'آیفون' AND o.price_toman IS NOT NULL
    ORDER BY o.price_toman ASC
    LIMIT 5;
    """)
    res = cursor.fetchall()
    dt = (time.time() - t0) * 1000
    print(f"\nFTS5 Search benchmark for 'آیفون': {dt:.2f} ms")
    for r in res:
        print(f"  {r[0][:30]} | {r[2]:,} T | {r[3]} ({r[4]})")
        
    conn.close()

if __name__ == "__main__":
    t_start = time.time()
    init_db()
    populate_shops()
    populate_products()
    populate_offers()
    populate_complementary_rules()
    create_indexes()
    verify_db()
    print(f"\nAll operations completed in {time.time() - t_start:.2f}s.")
