"""
سامانه کَلَم - دستیار هوشمند خرید حضوری ترب (Torob Physical Shopping Assistant)
FastAPI Backend Application exposing all 7 in-person retail algorithms, FTS5 search engine, and AI assistant.
"""

import os
import re
import sqlite3
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .algorithms.imwp import parse_mall_address
from .algorithms.ip_crp import InPersonCartRouter
from .algorithms.paco import calculate_paco_score
from .algorithms.credipay import analyze_payment_options, filter_and_rank_by_credit
from .algorithms.indp import detect_ambiguous_intent, DIAGNOSTIC_TREES
from .algorithms.svdp import compute_stock_certainty, generate_inquiry_dossier
from .algorithms.tfra import find_emergency_fallbacks
from .assistant import KalamAssistant

# مسیر پایگاه داده
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "torob.db")

def get_db():
    # sqlite3.connect فایل خالی می‌سازد؛ بدون پایگاه داده به جای خطای «no such table» پیام روشن بده
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=503,
            detail="پایگاه داده ساخته نشده است. ابتدا scripts/build_db.py را اجرا کنید.",
        )
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()

app = FastAPI(
    title="Kalam In-Person Shopping Assistant API",
    description="سیستم هوشمند خرید حضوری ترب - الگوریتم‌های ۷گانه بازار و پاساژگردی",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # API بدون کوکی و احراز هویت است؛ ترکیب "*" با credentials ناامن و بی‌مورد است
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Pydantic Models -----------------
MAX_CART_ITEMS = 50
MAX_SHOP_IDS = 200

class CartRouteRequest(BaseModel):
    product_ids: List[str] = Field(..., max_length=MAX_CART_ITEMS)
    preferred_hub: Optional[str] = None
    strategy: Optional[str] = "same_hub" # same_hub, single_stop, bargain

class PanicRequest(BaseModel):
    product_id: str
    failed_shop_id: str

class CreditFilterRequest(BaseModel):
    shop_ids: Optional[List[str]] = Field(None, max_length=MAX_SHOP_IDS)
    required_provider: Optional[str] = None
    in_person_only: Optional[bool] = False

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    cart_product_ids: Optional[List[str]] = Field(default_factory=list, max_length=MAX_CART_ITEMS)
    current_hub: Optional[str] = None
    active_product_id: Optional[str] = None
    active_shop_id: Optional[str] = None

# ----------------- Endpoints -----------------

@app.get("/api/health")
def health_check(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM shops;")
    shops_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM products;")
    products_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM offers;")
    offers_count = cursor.fetchone()[0]

    return {
        "status": "healthy",
        "service": "Kalam Torob Physical Assistant",
        "database": {
            "shops": shops_count,
            "products": products_count,
            "offers": offers_count
        },
        "active_algorithms": [
            "IP-CRP (In-Person Cart Routing Problem)",
            "PACO (Spatial & Asymmetric Complementarity)",
            "IMWP (Indoor Mall Wayfinding Parser)",
            "CrediPay (BNPL & In-Person POS Matcher)",
            "INDP (Interactive Need Decoupling Protocol)",
            "SVDP (Stock Certainty & 12s Inquiry Dossier)",
            "TFRA (Triple-Fallback Resilient Panic Architecture)"
        ]
    }

@app.get("/api/hubs")
def get_commercial_hubs(conn: sqlite3.Connection = Depends(get_db)):
    """
    دریافت هاب‌ها و مجتمع‌های تجاری بزرگ تهران همراه با تعداد فروشگاه‌های فعال
    """
    cursor = conn.cursor()
    cursor.execute("""
    SELECT location_label, count(DISTINCT s.shop_id) as shop_cnt, count(o.offer_id) as offer_cnt
    FROM shops s
    LEFT JOIN offers o ON s.shop_id = o.shop_id
    WHERE location_label IS NOT NULL AND location_label != ''
    GROUP BY location_label
    HAVING shop_cnt >= 2
    ORDER BY shop_cnt DESC
    LIMIT 20;
    """)
    rows = cursor.fetchall()
    
    hubs = []
    for r in rows:
        hubs.append({
            "name": r[0],
            "shop_count": r[1],
            "offer_count": r[2]
        })
    return {"hubs": hubs}

PERSIAN_SYNONYMS = {
    "لپتاپ": "لپ تاپ",
    "لپ‌تاپ": "لپ تاپ",
    "اسنپپی": "اسنپ پی",
    "اسنپ‌پی": "اسنپ پی",
    "تربپی": "ترب پی",
    "ترب‌پی": "ترب پی",
    "پاوربانک": "پاور بانک",
    "پاور‌بانک": "پاور بانک",
    "کتانی": "کتونی",
}


def normalize_query(q: str) -> str:
    """یکسان‌سازی حروف عربی/فارسی و املای رایج کلمات مرکب"""
    text = q.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    for k, v in PERSIAN_SYNONYMS.items():
        text = text.replace(k.replace("\u200c", " "), v)
    return text


def search_tokens(q: str) -> List[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", normalize_query(q))[:6]


SEARCH_SELECT = """
    SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, p.image_urls,
           min(o.price_toman) AS min_price, max(o.price_toman) AS max_price,
           count(DISTINCT o.shop_id) AS shop_count
    FROM products p
    JOIN offers o ON p.product_id = o.product_id AND o.price_toman IS NOT NULL
    JOIN shops s ON o.shop_id = s.shop_id
"""


@app.get("/api/search")
def search_products(
    q: str = Query(..., min_length=1, max_length=120),
    hub: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    جستجوی متنی سریع در میان محصولات با امکان فیلتر بر اساس هاب بازار و دسته
    ترتیب نتایج همان ترتیب ارتباط (rank) موتور FTS5 است.
    """
    cursor = conn.cursor()
    tokens = search_tokens(q)
    if not tokens:
        return {"query": q, "total_found": 0, "products": []}

    # ۱. FTS5 با ترتیب ارتباط؛ هر توکن به صورت پیشوندی و در کوتیشن (ایمن در برابر نحو FTS)
    ranked_ids: List[str] = []
    fts_query = " ".join(f'"{tok}"*' for tok in tokens)
    try:
        cursor.execute(
            "SELECT product_id FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT 400;",
            (fts_query,),
        )
        ranked_ids = [row[0] for row in cursor.fetchall()]
    except sqlite3.Error:
        ranked_ids = []

    filters, params = [], []
    if hub:
        filters.append("s.location_label = ?")
        params.append(hub)
    if category:
        filters.append("p.category_name = ?")
        params.append(category)

    if ranked_ids:
        placeholders = ",".join(["?"] * len(ranked_ids))
        where = [f"p.product_id IN ({placeholders})"] + filters
        cursor.execute(
            SEARCH_SELECT + f" WHERE {' AND '.join(where)} GROUP BY p.product_id;",
            ranked_ids + params,
        )
        order = {pid: i for i, pid in enumerate(ranked_ids)}
        rows = sorted(cursor.fetchall(), key=lambda r: order.get(r[0], len(order)))[:limit]
    else:
        # ۲. جایگزین LIKE: همه توکن‌ها باید در عنوان، دسته یا برند باشند
        token_where = []
        for tok in tokens:
            token_where.append("(p.persian_title LIKE ? OR p.category_name LIKE ? OR p.brand_name LIKE ?)")
        like_params = [f"%{tok}%" for tok in tokens for _ in range(3)]
        cursor.execute(
            SEARCH_SELECT + f" WHERE {' AND '.join(token_where + filters)}"
            " GROUP BY p.product_id ORDER BY shop_count DESC LIMIT ?;",
            like_params + params + [limit],
        )
        rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "product_id": r[0],
            "persian_title": r[1],
            "category_name": r[2],
            "brand_name": r[3],
            "image_url": r[4],
            "min_price_toman": r[5],
            "max_price_toman": r[6],
            "available_offline_shops_count": r[7]
        })

    return {"query": q, "total_found": len(results), "products": results}

@app.get("/api/products/suggested")
def get_suggested_products(conn: sqlite3.Connection = Depends(get_db)):
    """
    کالاهای پرتقاضای نمونه برای تست آنی خریدار در هکاتون
    """
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, p.image_urls,
           min(o.price_toman) as min_price, count(DISTINCT o.shop_id) as shop_count
    FROM products p
    JOIN offers o ON p.product_id = o.product_id
    WHERE o.price_toman > 200000
    GROUP BY p.product_id
    HAVING shop_count >= 3
    ORDER BY shop_count DESC
    LIMIT 12;
    """)
    suggested = []
    for r in cursor.fetchall():
        suggested.append({
            "product_id": r[0],
            "persian_title": r[1],
            "category_name": r[2],
            "brand_name": r[3],
            "image_url": r[4],
            "min_price_toman": r[5],
            "available_offline_shops_count": r[6]
        })
    return {"suggested": suggested}

@app.get("/api/product/{product_id}")
def get_product_details(product_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """
    جزئیات کامل محصول، لیست تمام آفرهای حضوری و شاخص اطمینان موجودی
    """
    cursor = conn.cursor()
    cursor.execute("""
    SELECT product_id, persian_title, category_name, brand_name, image_urls
    FROM products WHERE product_id = ?;
    """, (product_id,))
    prod = cursor.fetchone()
    if not prod:
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")

    cursor.execute("""
    SELECT o.offer_id, o.price_toman, o.last_price_changed_at, o.warranty,
           s.shop_id, s.name, s.address, s.location_label, s.payment_options, s.contacts, s.weekly_hours
    FROM offers o
    JOIN shops s ON o.shop_id = s.shop_id
    WHERE o.product_id = ? AND o.price_toman IS NOT NULL
    ORDER BY o.price_toman ASC;
    """, (product_id,))
    
    offers_list = []
    prices = []
    for row in cursor.fetchall():
        off_id, price, last_ch, warranty, sid, sname, addr, loc, pay_opts, contacts, hours = row
        prices.append(price)
        parsed_addr = parse_mall_address(addr, loc)
        stock_info = compute_stock_certainty({"price_toman": price, "last_price_changed_at": last_ch}, {"weekly_hours": hours})
        dossier = generate_inquiry_dossier(prod[1], price, sname, contacts)
        credit_info = analyze_payment_options(pay_opts)

        offers_list.append({
            "offer_id": off_id,
            "price_toman": price,
            "last_price_changed_at": last_ch,
            "warranty": warranty if warranty and warranty != "null" else None,
            "shop": {
                "shop_id": sid,
                "name": sname,
                "address": addr,
                "location_label": loc,
                "parsed_address": parsed_addr,
                "credit_info": credit_info
            },
            "stock_certainty": stock_info,
            "dossier": dossier
        })

    return {
        "product": {
            "product_id": prod[0],
            "title": prod[1],
            "category": prod[2],
            "brand": prod[3],
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "offline_shops_count": len(offers_list),
            "image_url": prod[4]
        },
        "offers_count": len(offers_list),
        "offers": offers_list
    }


@app.post("/api/cart/route")
def solve_cart_route(req: CartRouteRequest, conn: sqlite3.Connection = Depends(get_db)):
    """
    الگوریتم ۱: حل مسئله سبد خرید حضوری چندقلمی (IP-CRP Router)
    """
    router = InPersonCartRouter(conn)
    result = router.solve_cart(
        product_ids=req.product_ids,
        preferred_hub=req.preferred_hub,
        strategy=req.strategy
    )
    return result

@app.get("/api/complementary/{product_id}")
def get_complementary_items(
    product_id: str,
    shop_id: Optional[str] = None,
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    الگوریتم ۲: موتور مکمل نامتقارن و فضایی (PACO Engine)
    """
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, min(o.price_toman)
    FROM products p
    LEFT JOIN offers o ON p.product_id = o.product_id
    WHERE p.product_id = ?
    GROUP BY p.product_id;
    """, (product_id,))
    base_prod_row = cursor.fetchone()
    if not base_prod_row:
        raise HTTPException(status_code=404, detail="محصول مبدأ یافت نشد.")

    base_product = {
        "product_id": base_prod_row[0],
        "title": base_prod_row[1],
        "category_name": base_prod_row[2],
        "brand_name": base_prod_row[3],
        "price": base_prod_row[4] or 0
    }

    base_shop = {}
    if shop_id:
        cursor.execute("SELECT shop_id, name, address, location_label FROM shops WHERE shop_id = ?;", (shop_id,))
        s_row = cursor.fetchone()
        if s_row:
            base_shop = {"shop_id": s_row[0], "name": s_row[1], "address": s_row[2], "location_label": s_row[3]}

    # جستجوی قوانین مکمل برای دسته محصول (dep_score هر قانون در امتیاز استفاده می‌شود)
    cursor.execute("""
    SELECT target_category, dep_score
    FROM complementary_rules
    WHERE source_category = ?;
    """, (base_product["category_name"],))
    dep_by_category = {r[0]: r[1] for r in cursor.fetchall()}

    if not dep_by_category:
        # قوانین مکمل عمومی (نام دسته‌ها مطابق دیتاست ترب)
        dep_by_category = {
            "کیف و کاور گوشی": 0.65,
            "محافظ صفحه نمایش گوشی و تبلت": 0.65,
            "شارژر تبلت و موبایل": 0.65,
            "هدفون، هدست و هندزفری": 0.30,
        }
    dep_by_category.pop(base_product["category_name"], None)
    if not dep_by_category:
        return {"base_product": base_product, "complementary_count": 0, "recommendations": []}

    comp_categories = list(dep_by_category)
    placeholders = ",".join(["?"] * len(comp_categories))
    cursor.execute(f"""
    SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, o.price_toman,
           o.last_price_changed_at, s.shop_id, s.name, s.address, s.location_label
    FROM products p
    JOIN offers o ON p.product_id = o.product_id
    JOIN shops s ON o.shop_id = s.shop_id
    WHERE p.category_name IN ({placeholders}) AND o.price_toman IS NOT NULL
    ORDER BY o.price_toman ASC
    LIMIT 400;
    """, comp_categories)

    # برای هر کالای مکمل فقط بهترین پیشنهاد (بیشترین امتیاز) نگه داشته می‌شود
    best_by_product = {}
    for c in cursor.fetchall():
        cand_dict = {
            "product_id": c[0],
            "title": c[1],
            "category_name": c[2],
            "brand_name": c[3],
            "price_toman": c[4],
            "last_price_changed_at": c[5],
            "shop_id": c[6],
            "shop_name": c[7],
            "address": c[8],
            "location_label": c[9],
            "dep_score": dep_by_category.get(c[2]),
        }
        score, details = calculate_paco_score(base_product, base_shop, cand_dict)
        if score <= 0:
            continue
        current = best_by_product.get(cand_dict["product_id"])
        if current and current["paco_score"] >= score:
            continue
        cand_dict["paco_score"] = score
        cand_dict["location_description"] = details["location_description"]
        cand_dict["freshness_badge"] = details["freshness_badge"]
        cand_dict["parsed_address"] = parse_mall_address(cand_dict["address"], cand_dict["location_label"])
        best_by_product[cand_dict["product_id"]] = cand_dict

    scored_items = sorted(best_by_product.values(), key=lambda x: x["paco_score"], reverse=True)
    return {
        "base_product": base_product,
        "complementary_count": len(scored_items),
        "recommendations": scored_items[:8]
    }

@app.get("/api/wayfinding/{shop_id}")
def get_wayfinding(shop_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """
    الگوریتم ۳: ناوبری کلامی سه‌مرحله‌ای پاساژ (IMWP)
    """
    cursor = conn.cursor()
    cursor.execute("SELECT shop_id, name, address, location_label FROM shops WHERE shop_id = ?;", (shop_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="فروشگاه یافت نشد.")

    parsed = parse_mall_address(row[2], row[3])
    return {
        "shop_id": row[0],
        "shop_name": row[1],
        "navigation": parsed
    }

@app.post("/api/fallback/panic")
def trigger_panic_fallback(req: PanicRequest, conn: sqlite3.Connection = Depends(get_db)):
    """
    الگوریتم ۷: معماری نجات اضطراری سه‌لایه خریدار در پاساژ (TFRA Panic Button)
    """
    fallbacks = find_emergency_fallbacks(conn, req.product_id, req.failed_shop_id)
    return fallbacks

@app.post("/api/credit/filter")
def filter_credit_shops(req: CreditFilterRequest, conn: sqlite3.Connection = Depends(get_db)):
    """
    الگوریتم ۴: رتبه‌بندی فروشگاه‌های دارای ترمینال اقساطی BNPL (CrediPay)
    """
    cursor = conn.cursor()
    if req.shop_ids:
        placeholders = ",".join(["?"] * len(req.shop_ids))
        cursor.execute(f"SELECT shop_id, name, address, location_label, payment_options FROM shops WHERE shop_id IN ({placeholders});", req.shop_ids)
    else:
        cursor.execute("""
        SELECT shop_id, name, address, location_label, payment_options FROM shops
        WHERE payment_options IS NOT NULL AND payment_options NOT IN ('', 'null', '[]')
        LIMIT 500;
        """)
    
    shops = []
    for r in cursor.fetchall():
        shops.append({
            "shop_id": r[0], "name": r[1], "address": r[2], "location_label": r[3], "payment_options": r[4]
        })

    ranked = filter_and_rank_by_credit(shops, req.required_provider, req.in_person_only)
    return {"total": len(ranked), "shops": ranked[:50]}

@app.get("/api/inquiry/dossier")
def get_inquiry_dossier(
    product_title: str = Query(..., max_length=300),
    price_toman: Optional[int] = Query(None, ge=0),
    shop_name: str = Query(..., max_length=200),
    shop_id: Optional[str] = None,
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    الگوریتم ۶: پرونده استعلام صوتی و اسکریپت ۱۲ ثانیه‌ای تماس (SVDP)
    """
    contacts_raw = ""
    if shop_id:
        cursor = conn.cursor()
        cursor.execute("SELECT contacts FROM shops WHERE shop_id = ?;", (shop_id,))
        c_row = cursor.fetchone()
        if c_row:
            contacts_raw = c_row[0]

    dossier = generate_inquiry_dossier(product_title, price_toman, shop_name, contacts_raw)
    return dossier

@app.get("/api/need/diagnose")
def get_need_diagnose(q: Optional[str] = None):
    """
    الگوریتم ۵: غربالگری تعاملی نیاز مبهم (INDP)
    """
    if q:
        intent = detect_ambiguous_intent(q)
        if intent["needs_decoupling"]:
            return {"active_tree": intent["tree"], "all_trees": DIAGNOSTIC_TREES}
    return {"all_trees": DIAGNOSTIC_TREES}

@app.post("/api/chat")
def chat_with_assistant(req: ChatRequest, conn: sqlite3.Connection = Depends(get_db)):
    """
    هوش مصنوعی دستیار خریدار کَلَم همراه با گاردریل‌های ۵گانه و اجرای ابزارها
    """
    assistant = KalamAssistant(conn)
    response = assistant.process_message(
        user_text=req.message,
        context={
            "cart_product_ids": req.cart_product_ids,
            "current_hub": req.current_hub,
            "active_product_id": req.active_product_id,
            "active_shop_id": req.active_shop_id
        }
    )
    return response

# ----------------- Serve Frontend Static Files -----------------
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if not os.path.exists(PUBLIC_DIR):
    os.makedirs(PUBLIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")

