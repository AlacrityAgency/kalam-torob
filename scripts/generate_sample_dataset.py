#!/usr/bin/env python3
"""
تولید دیتاست نمونه (ساختگی) با همان ساختار CSVهای دیتاست ترب
برای اجرای محلی کَلَم وقتی فایل‌های واقعی در پوشه dataset/ موجود نیستند.

داده‌های این اسکریپت واقعی نیستند: نام مغازه‌ها، قیمت‌ها و شماره‌ها نمونه‌اند
(شماره‌ها با پیش‌شماره نامعتبر 0210000 ساخته می‌شوند تا به شماره واقعی کسی وصل نشوند).

اجرا:
    python scripts/generate_sample_dataset.py
    python scripts/build_db.py
"""

import csv
import json
import os
import random
from datetime import datetime, timedelta, timezone

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(WORKSPACE, "dataset")

random.seed(1405)

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# هاب‌های تجاری (location_label) و پاساژهای هر هاب
HUBS = {
    "چارسو": {"malls": ["پاساژ چارسو"], "street": "خیابان جمهوری", "cats": ["mobile", "headphone", "case", "screen", "charger", "watch", "laptop"]},
    "علاءالدین": {"malls": ["پاساژ علاءالدین"], "street": "چهارراه استانبول", "cats": ["mobile", "case", "screen", "charger", "headphone", "watch"]},
    "پایتخت": {"malls": ["مجتمع تجاری پایتخت"], "street": "خیابان میرداماد", "cats": ["laptop", "mouse", "headphone", "charger", "watch"]},
    "لاله زار": {"malls": ["بازار لاله زار"], "street": "خیابان لاله زار", "cats": ["cable", "fuse", "generator", "pump", "pump_acc", "drill", "socket"]},
    "امجد": {"malls": ["پاساژ امجد"], "street": "خیابان جمهوری", "cats": ["cctv", "socket", "hdd", "cable"]},
    "سپه سالار": {"malls": ["پاساژ سپه سالار"], "street": "خیابان سپه سالار", "cats": ["shoes"]},
    "بازار بزرگ": {"malls": ["بازار بزرگ تهران"], "street": "خیابان ۱۵ خرداد", "cats": ["shoes", "case", "charger"]},
}

# دسته‌ها با نام‌هایی که در الگوریتم‌ها (HEAVY_CATEGORIES، complementary_rules) استفاده شده‌اند
CATEGORIES = {
    "mobile": ("گوشی موبایل", [
        ("سامسونگ", "گوشی موبایل سامسونگ مدل Galaxy A55 ظرفیت 256 گیگابایت رم 8 گیگابایت", 21_000_000),
        ("سامسونگ", "گوشی موبایل سامسونگ مدل Galaxy A35 ظرفیت 128 گیگابایت رم 8 گیگابایت", 15_500_000),
        ("سامسونگ", "گوشی موبایل سامسونگ مدل Galaxy S24 FE ظرفیت 256 گیگابایت", 38_000_000),
        ("شیائومی", "گوشی موبایل شیائومی مدل Redmi Note 13 Pro ظرفیت 256 گیگابایت رم 8 گیگابایت", 16_800_000),
        ("شیائومی", "گوشی موبایل شیائومی مدل Poco X6 Pro ظرفیت 512 گیگابایت", 22_400_000),
        ("اپل", "گوشی موبایل اپل مدل iPhone 13 CH ظرفیت 128 گیگابایت", 52_000_000),
        ("اپل", "گوشی موبایل اپل مدل iPhone 15 ZAA ظرفیت 128 گیگابایت", 78_000_000),
        ("آنر", "گوشی موبایل آنر مدل X8b ظرفیت 256 گیگابایت", 11_900_000),
    ]),
    "laptop": ("لپ تاپ و نوت بوک", [
        ("ایسوس", "لپ تاپ 15.6 اینچی ایسوس مدل VivoBook 15 X1504VA-i5 1335U 16GB 512SSD", 39_000_000),
        ("ایسوس", "لپ تاپ 15.6 اینچی ایسوس مدل TUF Gaming F15 FX507ZC4-i7 12700H 16GB 512SSD RTX3050", 68_000_000),
        ("لنوو", "لپ تاپ 15.6 اینچی لنوو مدل IdeaPad Slim 3 15IRH8-i5 13420H 8GB 512SSD", 33_500_000),
        ("اچ پی", "لپ تاپ 15.6 اینچی اچ پی مدل 15-fd0336nia-i3 1315U 8GB 256SSD", 24_900_000),
        ("اپل", "لپ تاپ 13 اینچی اپل مدل MacBook Air MGN63 2020-M1 8GB 256SSD", 49_000_000),
    ]),
    "headphone": ("هدفون، هدست و هندزفری", [
        ("اپل", "هدفون بی سیم اپل مدل AirPods Pro 2 (ایرپاد پرو ۲)", 12_500_000),
        ("سامسونگ", "هدفون بی سیم سامسونگ مدل Galaxy Buds FE", 4_300_000),
        ("شیائومی", "هندزفری بلوتوثی شیائومی مدل Redmi Buds 4 Active", 1_150_000),
        ("انکر", "هندزفری بلوتوثی انکر مدل Soundcore Life P2 Mini", 1_600_000),
    ]),
    "mouse": ("ماوس", [
        ("لاجیتک", "ماوس بی سیم لاجیتک مدل M185", 520_000),
        ("لاجیتک", "ماوس گیمینگ لاجیتک مدل G102 Lightsync", 1_250_000),
        ("لاجیتک", "ماوس بی سیم لاجیتک مدل MX Master 3S", 5_400_000),
        ("تسکو", "ماوس تسکو مدل TM 285", 190_000),
    ]),
    "case": ("کیف و کاور گوشی", [
        ("متفرقه", "کاور سیلیکونی مناسب برای گوشی سامسونگ Galaxy A55", 180_000),
        ("متفرقه", "کاور مگنتی مناسب برای گوشی اپل iPhone 13", 350_000),
        ("متفرقه", "کیف کلاسوری مناسب برای گوشی شیائومی Redmi Note 13 Pro", 260_000),
    ]),
    "screen": ("محافظ صفحه نمایش گوشی و تبلت", [
        ("متفرقه", "محافظ صفحه نمایش سرامیکی مناسب برای گوشی سامسونگ Galaxy A55", 120_000),
        ("متفرقه", "محافظ صفحه نمایش شیشه‌ای مناسب برای گوشی اپل iPhone 13", 150_000),
    ]),
    "charger": ("شارژر تبلت و موبایل", [
        ("سامسونگ", "شارژر دیواری سامسونگ مدل EP-TA800 توان 25 وات", 780_000),
        ("انکر", "شارژر دیواری انکر مدل A2633 توان 20 وات", 950_000),
        ("اپل", "آداپتور شارژ اپل مدل 20W USB-C اصلی", 1_400_000),
    ]),
    "watch": ("ساعت و مچ بند هوشمند", [
        ("شیائومی", "مچ بند هوشمند شیائومی مدل Smart Band 8", 1_900_000),
        ("سامسونگ", "ساعت هوشمند سامسونگ مدل Galaxy Watch6 44mm", 11_000_000),
    ]),
    "shoes": ("کفش و کتونی", [
        ("اسکچرز", "کفش پیاده روی مردانه اسکچرز مدل Go Walk 6", 3_400_000),
        ("نایکی", "کتونی رانینگ مردانه نایکی مدل Air Zoom Pegasus 40", 5_800_000),
        ("آدیداس", "کتونی رانینگ آدیداس مدل Duramo SL", 2_700_000),
        ("ملی", "کفش طبی راحتی ملی مدل پیاده روی سبک", 1_450_000),
        ("متفرقه", "کفش طبی زنانه مدل ارتوپدی راحتی", 890_000),
    ]),
    "cctv": ("دوربین مدار بسته", [
        ("هایک ویژن", "دوربین مداربسته بولت هایک ویژن مدل DS-2CE16D0T دید در شب", 1_650_000),
        ("داهوا", "دوربین مداربسته دام داهوا مدل HAC-HDW1200 سقفی", 1_380_000),
    ]),
    "socket": ("سوکت و کانکتور", [
        ("متفرقه", "فیش BNC پیچی دوربین مداربسته بسته 10 عددی", 95_000),
        ("متفرقه", "کانکتور برق DC نری دوربین مداربسته", 40_000),
    ]),
    "hdd": ("هارد دیسک", [
        ("وسترن دیجیتال", "هارد دیسک اینترنال وسترن دیجیتال مدل Purple ظرفیت 2 ترابایت", 4_100_000),
    ]),
    "cable": ("سیم و کابل برق ساختمان", [
        ("خراسان", "کابل برق افشان 2 در 2.5 سیمکو خراسان حلقه 100 متری", 6_900_000),
        ("البرز", "سیم برق 1 در 1.5 البرز الکتریک نوین حلقه 100 متری", 2_350_000),
    ]),
    "fuse": ("کلید و فیوز مینیاتوری", [
        ("اشنایدر", "فیوز مینیاتوری تک پل 16 آمپر اشنایدر الکتریک", 310_000),
        ("پارس فانال", "کلید مینیاتوری 25 آمپر پارس فانال", 185_000),
    ]),
    "generator": ("ژنراتور و موتور برق", [
        ("رونیکس", "موتور برق بنزینی رونیکس مدل RH-4728 توان 2.8 کیلووات", 24_500_000),
        ("کراتوس", "موتور برق بنزینی کراتوس مدل 3500 توان 3.5 کیلووات", 31_000_000),
    ]),
    "pump": ("پمپ خانگی و صنعتی", [
        ("پنتاکس", "پمپ آب خانگی پنتاکس مدل CM100 نیم اسب", 7_800_000),
        ("دیزل ایران", "پمپ آب طبقاتی دیزل ایران یک اسب", 12_600_000),
    ]),
    "pump_acc": ("لوازم جانبی پمپ", [
        ("متفرقه", "ست کنترل اتوماتیک پمپ آب مدل PC-13", 1_250_000),
        ("متفرقه", "منبع تحت فشار 24 لیتری پمپ آب", 1_900_000),
    ]),
    "drill": ("دریل و پیچ گوشتی برقی و شارژی", [
        ("رونیکس", "دریل پیچ گوشتی شارژی رونیکس مدل 8618 دو باتری", 4_200_000),
        ("بوش", "دریل بتن کن بوش مدل GBH 2-26 DRE", 13_500_000),
    ]),
}

SHOP_PREFIXES = ["فروشگاه", "موبایل", "دیجیتال", "گالری", "بازرگانی", "تجهیزات", "پخش"]
SHOP_NAMES = ["آرین", "پارسیان", "نوین", "ستاره", "کیان", "مهرگان", "آوا", "سپهر", "رایان", "امید",
              "پرشین", "تک", "آسمان", "دانیال", "ماهان", "کوثر", "نگین", "البرز", "صدرا", "آریا"]
FLOORS = [("زیرهمکف", 1), ("همکف", 4), ("اول", 3), ("دوم", 2), ("سوم", 1)]
PROVIDERS = ["snapp_pay", "torob_pay", "tara", "digi_pay"]
WARRANTIES = ["گارانتی ۱۸ ماهه شرکتی", "گارانتی ۱۲ ماهه", "گارانتی اصالت و سلامت فیزیکی", None]


def fa(n):
    return str(n).translate(FA_DIGITS)


def weighted_floor():
    words = [w for w, _ in FLOORS]
    weights = [c for _, c in FLOORS]
    return random.choices(words, weights=weights)[0]


def build_shops():
    shops = []
    sid = 1000
    for hub, info in HUBS.items():
        n = 14 if hub in ("چارسو", "علاءالدین", "پایتخت", "لاله زار") else 9
        for _ in range(n):
            sid += 1
            mall = random.choice(info["malls"])
            name = f"{random.choice(SHOP_PREFIXES)} {random.choice(SHOP_NAMES)}"
            unit = random.randint(1, 340)
            address = f"تهران، {info['street']}، {mall}، طبقه {weighted_floor()}، واحد {fa(unit)}"
            payment = []
            for p in random.sample(PROVIDERS, k=random.randint(0, 2)):
                payment.append({"provider_name": p, "channel": random.choice(["in_person", "in_person", "online"])})
            contacts = [{"type": "phone", "value": f"0210000{random.randint(1000, 9999)}"}]
            hours = {"sat-wed": "10:00-20:00", "thu": "10:00-14:00"}
            shops.append({
                "shop_id": str(sid),
                "name": name,
                "address": address,
                "location_label": hub,
                "lat": round(35.68 + random.uniform(-0.05, 0.05), 6),
                "lon": round(51.41 + random.uniform(-0.05, 0.05), 6),
                "payment_options": json.dumps(payment, ensure_ascii=False) if payment else "null",
                "contacts": json.dumps(contacts, ensure_ascii=False),
                "weekly_hours": json.dumps(hours, ensure_ascii=False),
                "instagram": "null",
                "website_url": "null",
                "supports_fast_delivery": random.choice(["true", "false"]),
                "category_names": "null",
                "_cats": info["cats"],
            })
    return shops


def build_products():
    products = []
    pid = 50000
    for key, (cat_name, items) in CATEGORIES.items():
        for brand, title, base in items:
            pid += 1
            products.append({
                "product_id": str(pid),
                "persian_title": title,
                "category_name": cat_name,
                "brand_name": brand,
                "model": "null",
                "specs": "null",
                "image_urls": "[]",
                "_key": key,
                "_base": base,
            })
    return products


def build_offers(shops, products):
    offers = []
    oid = 900000
    now = datetime.now(timezone.utc)
    by_key = {}
    for p in products:
        by_key.setdefault(p["_key"], []).append(p)
    for s in shops:
        for key in s["_cats"]:
            for p in by_key.get(key, []):
                if random.random() > 0.55:
                    continue
                oid += 1
                price = int(p["_base"] * random.uniform(0.93, 1.12) / 10_000) * 10_000
                changed = now - timedelta(days=random.choice([0, 1, 2, 4, 7, 12, 20, 35, 70, 120]), hours=random.randint(0, 23))
                offers.append({
                    "offer_id": str(oid),
                    "product_id": p["product_id"],
                    "shop_id": s["shop_id"],
                    "price_toman": str(price) if random.random() > 0.04 else "null",
                    "last_price_changed_at": changed.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "warranty": random.choice(WARRANTIES) or "null",
                    "description": "null",
                    "seller_title": s["name"],
                })
    return offers


def write_csv(name, rows, columns):
    path = os.path.join(DATASET_DIR, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows):,} rows to {path}")


if __name__ == "__main__":
    os.makedirs(DATASET_DIR, exist_ok=True)
    shops = build_shops()
    products = build_products()
    offers = build_offers(shops, products)
    write_csv("shops.csv", shops, ["address", "category_names", "contacts", "instagram", "lat", "location_label", "lon",
                                   "name", "payment_options", "shop_id", "supports_fast_delivery", "website_url", "weekly_hours"])
    write_csv("products.csv", products, ["brand_name", "category_name", "image_urls", "model", "persian_title", "product_id", "specs"])
    write_csv("offers.csv", offers, ["description", "last_price_changed_at", "offer_id", "price_toman", "product_id",
                                     "seller_title", "shop_id", "warranty"])
