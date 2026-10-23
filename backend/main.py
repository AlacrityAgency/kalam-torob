"""
سامانه کَلَم - دستیار هوشمند خرید حضوری ترب (Torob Physical Shopping Assistant)
FastAPI Backend: الگوریتم‌های ۷گانه خرید حضوری، جستجوی FTS5 با شرایط خرید، و دستیار گفتگو.
"""

import os
import sqlite3
from typing import Annotated, List, Literal, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .algorithms.geo import distance_km
from .algorithms.recommend import rank_offers
from .algorithms.credipay import analyze_payment_options, canonical_provider, filter_and_rank_by_credit
from .algorithms.hours import hours_status
from .algorithms.imwp import parse_mall_address
from .algorithms.indp import DIAGNOSTIC_TREES, detect_ambiguous_intent
from .algorithms.ip_crp import InPersonCartRouter
from .algorithms.offer_quality import flatten_specs
from .algorithms.paco import calculate_paco_score
from .algorithms.prompt_generator import extract_model_and_brand, generate_dynamic_prompts
from .algorithms.svdp import INQUIRY_QUESTIONS, compute_stock_certainty, generate_inquiry_dossier, simulate_inquiry
from .algorithms.tfra import find_emergency_fallbacks
from .agent import follow_up
from .mission import run_mission
from .assistant import KalamAssistant
from .nlu import llm_enabled
from .search import SEARCH_STOPWORDS, search_products, tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# برای دیپلوی می‌توان پایگاه داده را روی دیسک دائمی گذاشت (مثلاً /data/torob.db)
DB_PATH = os.environ.get("KALAM_DB_PATH") or os.path.join(ROOT, "torob.db")


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


# نتایج ثابت (فهرست هاب‌ها، کالاهای پیشنهادی) تا وقتی فایل پایگاه داده عوض نشده در حافظه می‌مانند
_CACHE: dict = {}


def cached(key, conn, compute):
    try:
        mtime = os.path.getmtime(DB_PATH)
    except OSError:
        mtime = None
    hit = _CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    value = compute(conn)
    _CACHE[key] = (mtime, value)
    return value


app = FastAPI(
    title="Kalam In-Person Shopping Assistant API",
    description="سیستم هوشمند خرید حضوری ترب - الگوریتم‌های ۷گانه بازار و پاساژگردی",
    version="2.0.0"
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
    strategy: Optional[str] = "same_hub"  # same_hub, single_stop, bargain


class PanicRequest(BaseModel):
    product_id: str
    failed_shop_id: str


class CreditFilterRequest(BaseModel):
    shop_ids: Optional[List[str]] = Field(None, max_length=MAX_SHOP_IDS)
    required_provider: Optional[str] = None
    in_person_only: Optional[bool] = False


class TreeAnswer(BaseModel):
    category_key: str
    option_index: int = Field(..., ge=0, le=10)
    budget_index: Optional[int] = Field(None, ge=0, le=10)


class ChatRequest(BaseModel):
    message: str = Field("", max_length=500)
    cart_product_ids: Optional[List[str]] = Field(default_factory=list, max_length=MAX_CART_ITEMS)
    current_hub: Optional[str] = None
    active_product_id: Optional[str] = None
    active_shop_id: Optional[str] = None
    user_lat: Optional[float] = Field(None, ge=-90, le=90)
    user_lon: Optional[float] = Field(None, ge=-180, le=180)
    # حافظه گفتگو: وضعیت جستجوی قبلی که پاسخ قبلی برگردانده بود
    state: Optional[dict] = None
    # پاسخ ساختاریافته درخت نیاز مبهم؛ به جای درک متن مستقیم به جستجو می‌رود
    tree: Optional[TreeAnswer] = None


class InquirySimulationRequest(BaseModel):
    offer_id: str
    question: Literal["availability", "warranty", "credit", "hours", "reserve"]


# ----------------- Endpoints -----------------

@app.get("/api/health")
def health_check(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    counts = {t: cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("shops", "products", "offers")}
    meta = dict(cursor.execute("SELECT key, value FROM meta").fetchall())
    return {
        "status": "healthy",
        "service": "Kalam Torob Physical Assistant",
        "database": counts,
        "data_source": meta.get("data_source", "dataset"),
        "built_at": meta.get("built_at"),
        "nlu": "claude+local" if llm_enabled() else "local",
        "notice": "نام فروشگاه‌ها و شماره‌های تماس در دیتاست آزمایشی ترب ساختگی‌اند.",
    }


@app.get("/api/hubs")
def get_commercial_hubs(conn: sqlite3.Connection = Depends(get_db)):
    """
    محدوده‌های تجاری (location_label) با تفکیک فروشگاه‌های دارای آفر از فروشگاه‌هایی که فقط
    دسته فعالیتشان معلوم است. از جدول پیش‌محاسبه‌شده hub_stats خوانده می‌شود.
    """
    def compute(c):
        rows = c.execute("""
            SELECT location_label, shops_with_offers, category_only_shops, offer_count, lat, lon
            FROM hub_stats WHERE shops_with_offers >= 2
            ORDER BY shops_with_offers DESC LIMIT 30
        """).fetchall()
        return {"hubs": [{"name": r[0], "shop_count": r[1], "category_only_count": r[2], "offer_count": r[3],
                          "lat": r[4], "lon": r[5]} for r in rows]}

    return cached("hubs", conn, compute)


@app.get("/api/search")
def search_endpoint(
    q: str = Query(..., min_length=1, max_length=120),
    hub: Optional[str] = Query(None, max_length=80),
    category: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    credit: bool = False,
    provider: Optional[str] = None,
    fresh: bool = False,
    hours_known: bool = False,
    open_now: bool = False,
    include_copies: bool = False,
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    max_km: Optional[float] = Query(None, gt=0, le=100),
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    جستجوی کالا با شرایط خرید. ترتیب نتایج = ارتباط FTS5. کمترین قیمت از آفرهای سالم و منطبق با شرایط.
    hub می‌تواند نام محدوده (location_label) یا نام پاساژ داخل آدرس باشد.
    """
    tokens = tokenize(q, stopwords=SEARCH_STOPWORDS)
    filters = {
        "place": hub, "min_price": min_price, "max_price": max_price, "credit": credit,
        "provider": canonical_provider(provider), "fresh": fresh, "hours_known": hours_known,
        "open_now": open_now, "include_copies": include_copies,
    }
    results = search_products(conn, tokens, category=category, limit=limit, user_lat=lat, user_lon=lon,
                              max_km=max_km, **filters) if tokens else []
    return {"query": q, "total_found": len(results), "filters": filters, "products": results}


@app.get("/api/products/suggested")
def get_suggested_products(conn: sqlite3.Connection = Depends(get_db)):
    """کالاهای دارای بیشترین فروشگاه حضوری (پیش‌محاسبه‌شده هنگام ساخت پایگاه داده)"""
    def compute(c):
        rows = c.execute("""
            SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, p.image_urls,
                   ps.min_price, ps.shop_count
            FROM suggested_products sp
            JOIN product_stats ps ON ps.product_id = sp.product_id
            JOIN products p ON p.product_id = sp.product_id
            ORDER BY sp.rank
        """).fetchall()
        return {"suggested": [{
            "product_id": r[0], "persian_title": r[1], "category_name": r[2], "brand_name": r[3],
            "image_url": r[4], "min_price_toman": r[5], "available_offline_shops_count": r[6],
        } for r in rows]}

    return cached("suggested", conn, compute)


def _shop_public(row: dict) -> dict:
    """اطلاعات فروشگاه برای نمایش؛ فیلدهای نامشخص صریحاً None می‌مانند تا UI «ثبت‌نشده» نشان دهد"""
    return {
        "shop_id": row["shop_id"],
        "name": row["name"],
        "address": row["address"],
        "location_label": row["location_label"],
        "parsed_address": parse_mall_address(row["address"], row["location_label"]),
        "credit_info": analyze_payment_options(row["payment_options"]),
        "hours": hours_status(row["weekly_hours"]),
        "instagram": row.get("instagram"),
        "website_url": row.get("website_url"),
        "is_verified": bool(row.get("is_verified")),
    }


@app.get("/api/product/{product_id}")
def get_product_details(product_id: str, hub: Optional[str] = Query(None, max_length=80),
                        lat: Optional[float] = Query(None, ge=-90, le=90),
                        lon: Optional[float] = Query(None, ge=-180, le=180),
                        conn: sqlite3.Connection = Depends(get_db)):
    """
    جزئیات کالا، مشخصات فنی، همه آفرهای حضوری (با برچسب کپی/قیمت پرت) و فروشگاه‌های هم‌صنفی که
    فقط دسته فعالیتشان معلوم است (بدون آفر؛ موجودی نامشخص).
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    prod = cursor.execute("""
        SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, p.image_urls, p.specs,
               ps.min_price, ps.max_price, ps.flagged_count
        FROM products p LEFT JOIN product_stats ps ON ps.product_id = p.product_id
        WHERE p.product_id = ?
    """, (product_id,)).fetchone()
    if not prod:
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")

    rows = cursor.execute("""
        SELECT o.offer_id, o.price_toman, o.last_price_changed_at, o.warranty, o.seller_title, o.description,
               o.is_copy, o.price_suspect,
               s.shop_id, s.name, s.address, s.location_label, s.payment_options, s.contacts, s.weekly_hours,
               s.instagram, s.website_url, s.is_verified, s.lat AS shop_lat, s.lon AS shop_lon
        FROM offers o JOIN shops s ON o.shop_id = s.shop_id
        WHERE o.product_id = ?
        ORDER BY o.is_copy, o.price_suspect, o.price_toman IS NULL, o.price_toman ASC
    """, (product_id,)).fetchall()

    hub_val = hub if isinstance(hub, str) else ""
    lat_val = lat if isinstance(lat, (int, float)) else None
    lon_val = lon if isinstance(lon, (int, float)) else None

    offers_list = []
    for r in map(dict, rows):
        dist = distance_km(lat_val, lon_val, r["shop_lat"], r["shop_lon"])
        offers_list.append({
            "offer_id": r["offer_id"],
            "price_toman": r["price_toman"],
            "last_price_changed_at": r["last_price_changed_at"],
            "warranty": r["warranty"],
            "seller_title": r["seller_title"],
            "description": r["description"],
            "is_copy": bool(r["is_copy"]),
            "price_suspect": bool(r["price_suspect"]),
            "shop": {**_shop_public(r), "lat": r["shop_lat"], "lon": r["shop_lon"]},
            "distance_km": round(dist, 2) if dist is not None else None,
            "stock_certainty": compute_stock_certainty(
                {"price_toman": r["price_toman"], "last_price_changed_at": r["last_price_changed_at"]},
                {"weekly_hours": r["weekly_hours"]},
            ),
            "dossier": generate_inquiry_dossier(prod["persian_title"], r["price_toman"], r["name"], r["contacts"]),
        })

    # فروشگاه‌های هم‌صنف بدون آفر: دسته فعالیت به‌تنهایی نشانه موجود بودن کالا نیست
    category_only = []
    if prod["category_name"]:
        cand = cursor.execute("""
            SELECT shop_id, name, address, location_label, payment_options, weekly_hours,
                   instagram, website_url, is_verified
            FROM shops
            WHERE offer_count = 0 AND category_names LIKE ?
            ORDER BY (location_label = ?) DESC, is_verified DESC, hours_known DESC
            LIMIT 6
        """, (f"%{prod['category_name']}%", hub_val)).fetchall()
        category_only = [_shop_public(dict(r)) for r in cand]

    # پیشنهاد کلم: بهترین ترکیب قیمت، نزدیکی، باز بودن و تازگی قیمت، با دلیل
    recommendation = rank_offers([{
        "offer_id": o["offer_id"], "price_toman": o["price_toman"], "is_copy": o["is_copy"],
        "price_suspect": o["price_suspect"], "distance_km": o["distance_km"],
        "hours_state": o["shop"]["hours"]["state"],
        "days_since_update": o["stock_certainty"]["days_since_update"],
        "has_credit": o["shop"]["credit_info"]["has_credit"],
    } for o in offers_list])

    return {
        "recommendation": recommendation,
        "product": {
            "product_id": prod["product_id"],
            "title": prod["persian_title"],
            "category": prod["category_name"],
            "brand": prod["brand_name"],
            "min_price": prod["min_price"],
            "max_price": prod["max_price"],
            "flagged_offers": prod["flagged_count"] or 0,
            "offline_shops_count": len({o["shop"]["shop_id"] for o in offers_list}),
            "image_url": prod["image_urls"],
            "specs": flatten_specs(prod["specs"]),
        },
        "offers_count": len(offers_list),
        "offers": offers_list,
        "category_only_shops": category_only,
    }


@app.post("/api/cart/route")
def solve_cart_route(req: CartRouteRequest, conn: sqlite3.Connection = Depends(get_db)):
    """الگوریتم ۱: حل مسئله سبد خرید حضوری چندقلمی (IP-CRP Router)"""
    router = InPersonCartRouter(conn)
    return router.solve_cart(product_ids=req.product_ids, preferred_hub=req.preferred_hub, strategy=req.strategy)


@app.get("/api/complementary/{product_id}")
def get_complementary_items(product_id: str, shop_id: Optional[str] = None,
                            conn: sqlite3.Connection = Depends(get_db)):
    """
    الگوریتم ۲: موتور مکمل نامتقارن و فضایی (PACO). قوانین با الگوی نام دسته تطبیق داده می‌شوند؛
    اگر قانونی برای دسته نباشد، چیزی پیشنهاد نمی‌شود (نه کاور گوشی زیر صفحه دریل).
    """
    cursor = conn.cursor()
    row = cursor.execute("""
        SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, ps.min_price
        FROM products p LEFT JOIN product_stats ps ON ps.product_id = p.product_id
        WHERE p.product_id = ?
    """, (product_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="محصول مبدأ یافت نشد.")
    meta = extract_model_and_brand(row[1], row[3])
    base_product = {
        "product_id": row[0],
        "title": row[1],
        "category_name": row[2],
        "brand_name": row[3],
        "price": row[4] or 0,
        "core_model": meta.get("core_model"),
    }
    core_model = meta.get("core_model") or ""

    base_shop = {}
    if shop_id:
        s_row = cursor.execute("SELECT shop_id, name, address, location_label FROM shops WHERE shop_id = ?;", (shop_id,)).fetchone()
        if s_row:
            base_shop = {"shop_id": s_row[0], "name": s_row[1], "address": s_row[2], "location_label": s_row[3]}

    # ۱. فراخوانی موتور هوش مصنوعی کالا (DCA) با پوشش ۱۰۰٪ اجناس کاتالوگ
    from .algorithms.ai_product_intelligence import find_grounded_complementary_items
    scored, ai_prompts = find_grounded_complementary_items(conn, base_product, base_shop, limit=8)
    for cand in scored:
        cand["reason"] = cand.get("ai_reason") or cand.get("reason")
        cand["location_description"] = cand.get("location_desc") or cand.get("loc_desc")
        if "parsed_address" not in cand:
            cand["parsed_address"] = parse_mall_address(cand.get("address"), cand.get("location_label"))

    if scored:
        return {
            "base_product": base_product,
            "complementary_count": len(scored),
            "recommendations": scored[:8],
            "in_store_prompts": ai_prompts,
            "source": "ai_dynamic_architecture",
        }

    rules = cursor.execute("""
        SELECT target_pattern, dep_score, description_fa FROM complementary_rules WHERE ? LIKE source_pattern
    """, (base_product["category_name"] or "",)).fetchall()
    if not rules:
        return {"base_product": base_product, "complementary_count": 0, "recommendations": []}

    best_by_product = {}
    for target_pattern, dep_score, reason in rules:
        cats = [r[0] for r in cursor.execute(
            "SELECT category_name FROM categories WHERE category_name LIKE ? AND category_name != ?",
            (target_pattern, base_product["category_name"]))]
        if not cats:
            continue
        ph = ",".join("?" * len(cats))
        candidates = cursor.execute(f"""
            SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, o.price_toman,
                   o.last_price_changed_at, s.shop_id, s.name, s.address, s.location_label
            FROM products p
            JOIN offers o ON p.product_id = o.product_id
            JOIN shops s ON o.shop_id = s.shop_id
            WHERE p.category_name IN ({ph})
              AND o.price_toman IS NOT NULL AND o.is_copy = 0 AND o.price_suspect = 0
            ORDER BY (s.shop_id = ?) DESC, (p.persian_title LIKE ?) DESC, (s.location_label = ?) DESC, o.price_toman ASC
            LIMIT 120
        """, (*cats, shop_id or "", f"%{core_model}%", base_shop.get("location_label") or "")).fetchall()
        for c in candidates:
            cand = {
                "product_id": c[0], "title": c[1], "category_name": c[2], "brand_name": c[3], "price_toman": c[4],
                "last_price_changed_at": c[5], "shop_id": c[6], "shop_name": c[7], "address": c[8],
                "location_label": c[9], "dep_score": dep_score,
            }
            score, details = calculate_paco_score(base_product, base_shop, cand)
            if score <= 0:
                continue
            current = best_by_product.get(cand["product_id"])
            if current and current["paco_score"] >= score:
                continue
            cand.update({
                "paco_score": score,
                "reason": reason,
                "location_description": details["location_description"],
                "freshness_badge": details["freshness_badge"],
                "bundle_bonus": details.get("bundle_bonus", 1.0),
                "bundle_eligible": details.get("bundle_eligible", False),
                "cognitive_role": details.get("cognitive_role"),
                "cognitive_category": details.get("cognitive_category"),
                "bargaining_tip": details.get("bargaining_tip"),
                "parsed_address": parse_mall_address(cand["address"], cand["location_label"]),
            })
            best_by_product[cand["product_id"]] = cand

    scored = sorted(best_by_product.values(), key=lambda x: x["paco_score"], reverse=True)
    return {"base_product": base_product, "complementary_count": len(scored), "recommendations": scored[:8]}


@app.get("/api/prompts")
def get_prompts_endpoint(
    product_id: Annotated[Optional[str], Query(max_length=64)] = None,
    shop_id: Annotated[Optional[str], Query(max_length=64)] = None,
    cart_product_ids: Annotated[Optional[str], Query(max_length=2000)] = None,
    hub: Annotated[Optional[str], Query(max_length=80)] = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    الگوریتم تولید داینامیک سوالات آماده و راهنما (DCPG) متناسب با کالا، فروشگاه و سبد خرید
    """
    cursor = conn.cursor()
    product = None
    shop = None
    cart_items = []

    if product_id:
        p_row = cursor.execute("""
            SELECT product_id, persian_title, category_name, brand_name
            FROM products WHERE product_id = ?
        """, (product_id,)).fetchone()
        if p_row:
            product = {
                "product_id": p_row[0],
                "title": p_row[1],
                "category_name": p_row[2],
                "brand_name": p_row[3],
            }

    if shop_id:
        s_row = cursor.execute("""
            SELECT shop_id, name, address, location_label
            FROM shops WHERE shop_id = ?
        """, (shop_id,)).fetchone()
        if s_row:
            shop = {
                "shop_id": s_row[0],
                "name": s_row[1],
                "address": s_row[2],
                "location_label": s_row[3],
                "parsed_address": parse_mall_address(s_row[2], s_row[3]),
            }

    if cart_product_ids:
        c_ids = list(dict.fromkeys(i.strip() for i in cart_product_ids.split(",") if i.strip()))[:20]
        if c_ids:
            ph = ",".join("?" * len(c_ids))
            c_rows = cursor.execute(f"""
                SELECT product_id, persian_title, category_name, brand_name
                FROM products WHERE product_id IN ({ph})
            """, c_ids).fetchall()
            cart_items = [{"product_id": r[0], "title": r[1], "category_name": r[2], "brand_name": r[3]} for r in c_rows]

    prompts = generate_dynamic_prompts(
        product=product,
        shop=shop,
        cart_items=cart_items,
        mall_name=hub,
    )
    return {"prompts": prompts}


@app.get("/api/wayfinding/{shop_id}")
def get_wayfinding(shop_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """الگوریتم ۳: ناوبری کلامی سه‌مرحله‌ای پاساژ (IMWP) + ساعت کاری"""
    row = conn.execute("SELECT shop_id, name, address, location_label, weekly_hours FROM shops WHERE shop_id = ?;",
                       (shop_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="فروشگاه یافت نشد.")
    return {
        "shop_id": row[0],
        "shop_name": row[1],
        "navigation": parse_mall_address(row[2], row[3]),
        "hours": hours_status(row[4]),
    }


@app.post("/api/fallback/panic")
def trigger_panic_fallback(req: PanicRequest, conn: sqlite3.Connection = Depends(get_db)):
    """الگوریتم ۷: معماری نجات اضطراری سه‌لایه خریدار در پاساژ (TFRA)"""
    return find_emergency_fallbacks(conn, req.product_id, req.failed_shop_id)


@app.post("/api/credit/filter")
def filter_credit_shops(req: CreditFilterRequest, conn: sqlite3.Connection = Depends(get_db)):
    """الگوریتم ۴: رتبه‌بندی فروشگاه‌های دارای درگاه اقساطی (CrediPay)"""
    cursor = conn.cursor()
    if req.shop_ids:
        placeholders = ",".join(["?"] * len(req.shop_ids))
        cursor.execute(f"SELECT shop_id, name, address, location_label, payment_options FROM shops WHERE shop_id IN ({placeholders});", req.shop_ids)
    else:
        cursor.execute("SELECT shop_id, name, address, location_label, payment_options FROM shops WHERE credit_providers IS NOT NULL LIMIT 1000;")
    shops = [{"shop_id": r[0], "name": r[1], "address": r[2], "location_label": r[3], "payment_options": r[4]} for r in cursor.fetchall()]
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
    """الگوریتم ۶: پرونده استعلام و اسکریپت ۱۲ ثانیه‌ای تماس (SVDP)"""
    contacts_raw = ""
    if shop_id:
        c_row = conn.execute("SELECT contacts FROM shops WHERE shop_id = ?;", (shop_id,)).fetchone()
        if c_row:
            contacts_raw = c_row[0]
    return generate_inquiry_dossier(product_title, price_toman, shop_name, contacts_raw)


@app.post("/api/inquiry/simulate")
def simulate_inquiry_endpoint(req: InquirySimulationRequest, conn: sqlite3.Connection = Depends(get_db)):
    """
    شبیه‌ساز استعلام (Sandbox): پاسخ فروشنده از روی داده‌های ثبت‌شده همان آفر بازسازی می‌شود.
    شماره‌های دیتاست ساختگی‌اند، پس این پاسخ‌ها جایگزین تماس واقعی نیستند و همیشه برچسب شبیه‌سازی دارند.
    """
    row = conn.execute("""
        SELECT p.persian_title, o.price_toman, o.last_price_changed_at, o.warranty, o.seller_title, o.is_copy,
               o.price_suspect, s.name, s.payment_options, s.weekly_hours
        FROM offers o JOIN shops s ON o.shop_id = s.shop_id JOIN products p ON p.product_id = o.product_id
        WHERE o.offer_id = ?
    """, (req.offer_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="آفر یافت نشد.")
    keys = ["product_title", "price_toman", "last_price_changed_at", "warranty", "seller_title", "is_copy",
            "price_suspect", "shop_name", "payment_options", "weekly_hours"]
    return simulate_inquiry(dict(zip(keys, row)), req.question)


class FollowUpRequest(BaseModel):
    offer_id: str = Field(..., max_length=64)


@app.post("/api/agent/follow-up")
def agent_follow_up(req: FollowUpRequest, conn: sqlite3.Connection = Depends(get_db)):
    """ایجنت پیگیری: ساعت کاری ← پاسخ‌گویی ← قیمت/موجودی ← گارانتی ← اقساط ← تصمیم و جایگزین‌ها (شبیه‌سازی)"""
    result = follow_up(conn, req.offer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="آفر یافت نشد.")
    return result


class MissionRequest(BaseModel):
    message: str = Field("", max_length=300)
    current_hub: Optional[str] = Field(None, max_length=80)
    active_product_id: Optional[str] = Field(None, max_length=64)
    user_lat: Optional[float] = Field(None, ge=-90, le=90)
    user_lon: Optional[float] = Field(None, ge=-180, le=180)


@app.post("/api/agent/mission")
def agent_mission(req: MissionRequest, conn: sqlite3.Connection = Depends(get_db)):
    """حالت ایجنت: فهم درخواست ← جستجو ← مقایسه فروشگاه‌ها ← پیگیری ← برنامه مراجعه ← خرید یکجا"""
    return run_mission(conn, req.message, {
        "current_hub": req.current_hub, "active_product_id": req.active_product_id,
        "user_lat": req.user_lat, "user_lon": req.user_lon,
    })


@app.get("/api/inquiry/questions")
def inquiry_questions():
    return {"questions": [{"key": k, "label": v} for k, v in INQUIRY_QUESTIONS.items()]}


@app.get("/api/need/diagnose")
def get_need_diagnose(q: Optional[str] = None):
    """الگوریتم ۵: غربالگری تعاملی نیاز مبهم (INDP)"""
    if q:
        intent = detect_ambiguous_intent(q, tokens=tokenize(q, stopwords=SEARCH_STOPWORDS))
        if intent["needs_decoupling"]:
            return {"active_tree": intent["tree"], "category_key": intent["category_key"], "all_trees": DIAGNOSTIC_TREES}
    return {"all_trees": DIAGNOSTIC_TREES}


@app.post("/api/chat")
def chat_with_assistant(req: ChatRequest, conn: sqlite3.Connection = Depends(get_db)):
    """دستیار گفتگوی کَلَم: درک پیام (Claude یا پارسر محلی)، حافظه گفتگو و اجرای ابزارها"""
    if not req.message.strip() and not req.tree:
        raise HTTPException(status_code=422, detail="پیام خالی است.")
    if req.tree and req.tree.category_key not in DIAGNOSTIC_TREES:
        raise HTTPException(status_code=422, detail="درخت نامعتبر است.")
    places = cached("places", conn, lambda c: [r[0] for r in c.execute(
        "SELECT location_label FROM hub_stats WHERE shops_with_offers > 0")])
    assistant = KalamAssistant(conn, places=places)
    return assistant.process_message(
        user_text=req.message,
        context={
            "cart_product_ids": req.cart_product_ids,
            "current_hub": req.current_hub,
            "active_product_id": req.active_product_id,
            "active_shop_id": req.active_shop_id,
            "user_lat": req.user_lat,
            "user_lon": req.user_lon,
        },
        state=req.state,
        tree=req.tree.model_dump() if req.tree else None,
    )


# ----------------- Serve Frontend Static Files -----------------
PUBLIC_DIR = os.path.join(ROOT, "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
