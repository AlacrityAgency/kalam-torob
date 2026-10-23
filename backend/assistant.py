"""
دستیار هوشمند کَلَم (Kalam Conversational AI Core)

۱. درک پیام (backend/nlu.py): Claude در صورت تنظیم کلید، وگرنه پارسر محلی فارسی؛ کالا، محدوده،
   بودجه، درگاه اقساطی و نیت را هم‌زمان از یک جمله استخراج می‌کند.
۲. حافظه گفتگو: وضعیت جستجوی قبلی (state) به کلاینت برمی‌گردد و با پیام بعدی فرستاده می‌شود؛
   «ارزون‌ترش کدومه؟» یا «تا ۲۰ میلیون چی؟» روی همان جستجوی قبلی اعمال می‌شود.
۳. اجرای ابزار: جستجو با شرایط خرید، مسیر سبد (IP-CRP)، جایگزین مغازه بسته (TFRA)،
   فروشگاه‌های اقساطی (CrediPay)، ساعت کاری، و درخت نیاز مبهم (INDP).

گاردریل اصلی: هر پاسخ فقط از داده‌های پایگاه داده ساخته می‌شود. اگر داده کافی نباشد،
همین را صادقانه می‌گوید و چیزی نمی‌سازد.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

from .algorithms.credipay import PROVIDER_LABELS, filter_and_rank_by_credit
from .algorithms.geo import distance_km
from .algorithms.hours import hours_status
from .algorithms.imwp import parse_mall_address
from .algorithms.indp import detect_ambiguous_intent, resolve_tree_answers, DIAGNOSTIC_TREES
from .algorithms.ip_crp import InPersonCartRouter
from .algorithms.paco import calculate_paco_score
from .algorithms.prompt_generator import extract_model_and_brand, generate_dynamic_prompts
from .algorithms.svdp import compute_stock_certainty, generate_inquiry_dossier
from .algorithms.textutil import to_fa_digits
from .algorithms.tfra import find_emergency_fallbacks
from .mission import is_mission, run_mission
from .nlu import extract
from .search import OFFER_COLUMNS, offer_matches, place_matches, search_products

STATE_KEYS = ("tokens", "optional", "category", "colloquial_concept", "colloquial_label", "bazaar_hub_guide", "where_to_buy",
              "place", "budget_min", "budget_max", "provider", "credit", "open_now", "near", "cheapest",
              "active_product_id", "active_product_title", "active_shop_id")


def _fa_price(n) -> str:
    return to_fa_digits(f"{int(n):,}") if n else "?"


def describe_filters(s: dict) -> str:
    parts = []
    if s.get("place"):
        parts.append(f"در {s['place']}")
    if s.get("budget_min") and s.get("budget_max"):
        parts.append(f"بین {_fa_price(s['budget_min'])} تا {_fa_price(s['budget_max'])} تومان")
    elif s.get("budget_max"):
        parts.append(f"تا {_fa_price(s['budget_max'])} تومان")
    elif s.get("budget_min"):
        parts.append(f"بالای {_fa_price(s['budget_min'])} تومان")
    if s.get("provider"):
        parts.append(f"با {PROVIDER_LABELS.get(s['provider'], s['provider'])}")
    elif s.get("credit"):
        parts.append("با امکان خرید اقساطی")
    if s.get("open_now"):
        parts.append("فقط مغازه‌های باز")
    return "، ".join(parts)


class KalamAssistant:
    def __init__(self, db_conn: sqlite3.Connection, places: list[str] | None = None):
        self.conn = db_conn
        self.router = InPersonCartRouter(db_conn)
        self.places = places if places is not None else [
            r[0] for r in db_conn.execute("SELECT DISTINCT location_label FROM shops WHERE location_label IS NOT NULL")
        ]

    def process_message(self, user_text: str, context: Dict[str, Any] = None, state: dict | None = None,
                        tree: dict | None = None) -> Dict[str, Any]:
        """
        پردازش پیام خریدار و هدایت به مناسب‌ترین ماژول الگوریتمی.
        tree: پاسخ ساختاریافته درخت نیاز ({category_key, option_index, budget_index}) — بدون درک متن.
        """
        context = context or {}
        state = {k: v for k, v in (state or {}).items() if k in STATE_KEYS}
        self._active_shop_id = context.get("active_shop_id") or state.get("active_shop_id")
        cart_ids = context.get("cart_product_ids") or []

        if tree:
            resolved = resolve_tree_answers(tree["category_key"], tree["option_index"], tree.get("budget_index"))
            self.user_loc = (context.get("user_lat"), context.get("user_lon"))
            slots = {**resolved, "place": context.get("current_hub") or state.get("place"), "provider": None,
                     "credit": False, "open_now": False}
            response = self._search(slots, intro=f"گزینه‌های {resolved['label']}")
            response["nlu"] = "tree"
            return response

        self.user_loc = (context.get("user_lat"), context.get("user_lon"))
        # ایجنت داخل همین دستیار است: پیامی که کار کامل می‌خواهد («پیدا کن و هماهنگ کن») مأموریت اجرا می‌کند
        if is_mission(user_text):
            response = run_mission(self.conn, user_text, {
                "current_hub": context.get("current_hub"),
                "active_product_id": context.get("active_product_id") or state.get("active_product_id"),
                "user_lat": context.get("user_lat"), "user_lon": context.get("user_lon"),
            })
            response["state"] = {**state, **(response.get("state") or {})}
            response.setdefault("nlu", "local")
            return response
        slots, source = extract(user_text or "", self.places, state)
        if not slots.get("place") and context.get("current_hub"):
            slots["place"] = context["current_hub"]
        response = self._dispatch(user_text or "", slots, state, cart_ids, context)
        response["nlu"] = source
        return response

    # ------------------------------------------------------------------

    def _dispatch(self, text, slots, state, cart_ids, context):
        intent = slots["intent"]
        if intent == "panic":
            return self._panic(context, cart_ids)
        if intent in ("route", "visit"):
            if any(w in text for w in ("همین مغازه", "همین فروشگاه", "همین فروشنده")):
                return self._consultation(text, slots, state, cart_ids, context)
            return self._route(cart_ids, slots.get("place"), visit=intent == "visit")
        if intent == "complementary":
            return self._complementary(context, cart_ids, state, slots)
        if intent == "consultation":
            return self._consultation(text, slots, state, cart_ids, context)
        if intent == "out_of_domain":
            return {
                "type": "text",
                "message": "من دستیار هوشمند کَلَم برای استعلام کالا و خرید حضوری از بازار و مراکز خرید تهران هستم. برای مشاوره‌های پزشکی، درمانی، برنامه‌نویسی و امور خارج از حوزه فروشگاه و کالا، لطفاً از مراجع و ابزارهای تخصصی کمک بگیرید.",
                "products": [],
                "state": state,
            }
        if intent == "greeting":
            return {"type": "text", "message": "سلام! نام کالا را بگویید؛ می‌توانید محدوده، بودجه و اقساطی بودن را هم در همان جمله بنویسید. مثلاً «گوشی A55 قسطی در چارسو تا ۲۵ میلیون».", "state": state}

        tokens = slots.get("tokens") or []
        # ادامه جستجوی قبلی: «ارزون‌ترش؟»، «تا ۲۰ میلیون چی؟»، «در چارسو هم هست؟»
        refinement = any(slots.get(k) for k in ("budget_min", "budget_max", "provider", "place", "open_now")) or slots.get("credit")
        shop_list = slots.get("shop_oriented") and intent in ("credit", "hours")
        if not tokens and state.get("tokens") and not shop_list and (slots.get("refers_previous") or refinement):
            merged = dict(state)
            for key in ("place", "budget_min", "budget_max", "provider", "credit", "open_now", "category", "optional", "colloquial_concept", "colloquial_label"):
                if slots.get(key):
                    merged[key] = slots[key]
            merged["cheapest"] = slots.get("cheapest")
            merged["near"] = slots.get("near")
            return self._search(merged, intro="با شرایط جدید", cart_ids=cart_ids)

        if not tokens:
            if intent == "credit" or slots.get("credit"):
                return self._credit(slots, state)
            if intent == "hours" or slots.get("open_now") or slots.get("friday"):
                return self._open_shops(slots, state)
            return {"type": "text", "message": "نام کالایی که می‌خواهید را بنویسید؛ مثلاً «ایرپاد پرو» یا «دریل شارژی».", "state": state}

        has_budget = bool(slots.get("budget_min") or slots.get("budget_max"))
        ambiguous = detect_ambiguous_intent(text, tokens=tokens, has_budget=has_budget)
        if ambiguous["needs_decoupling"]:
            tree = ambiguous["tree"]
            return {
                "type": "diagnostic_tree",
                "message": "برای اینکه وقتتان در پاساژ تلف نشود، دو سؤال کوتاه:",
                "category_key": ambiguous["category_key"],
                "diagnostic": {"title": tree["title"], "steps": tree["steps"]},
                "state": state,
            }
        return self._search(slots, cart_ids=cart_ids)

    # ------------------------------------------------------------------

    def _search(self, slots, intro=None, cart_ids=None):
        filters = {
            "place": slots.get("place"),
            "min_price": slots.get("budget_min"),
            "max_price": slots.get("budget_max"),
            "provider": slots.get("provider"),
            "credit": bool(slots.get("credit")),
            "open_now": bool(slots.get("open_now")),
        }
        tokens, optional = slots.get("tokens") or [], slots.get("optional")
        category = slots.get("category")
        # در گفتگو لوازم جانبی به جای کالای اصلی نشان داده نمی‌شوند («گوشی A55» ≠ «کاور A55»)
        ulat, ulon = getattr(self, "user_loc", (None, None))
        products = search_products(self.conn, tokens, optional=optional, category=category, limit=4, accessories="exclude",
                                   user_lat=ulat, user_lon=ulon, **filters)
        if not products and category:
            # در صورتی که با محدودیت دقیق دسته‌بندی کالایی نبود، بدون قید دسته‌بندی دوباره بررسی شود
            products = search_products(self.conn, tokens, optional=optional, limit=4, accessories="exclude",
                                       user_lat=ulat, user_lon=ulon, **filters)
        if slots.get("cheapest"):
            products.sort(key=lambda p: p["min_price_toman"])
        near = bool(slots.get("near")) and ulat is not None
        if near:
            products.sort(key=lambda p: (p["nearest_km"] is None, p["nearest_km"] or 0))

        new_state = {k: slots.get(k) for k in STATE_KEYS}
        if products:
            new_state["active_product_id"] = products[0]["product_id"]
            new_state["active_product_title"] = products[0].get("persian_title") or products[0].get("title")
        query_label = slots.get("colloquial_label") or " ".join(tokens)
        conditions = describe_filters(slots)

        if not products:
            # کدام شرط باعث نبود نتیجه شده؟ بدون فیلترها دوباره امتحان کن
            loose = search_products(self.conn, tokens, optional=optional, category=category, limit=1, accessories="exclude")
            if not loose and category:
                loose = search_products(self.conn, tokens, optional=optional, limit=1, accessories="exclude")
            if loose and conditions:
                msg = f"برای «{query_label}» با شرط‌های «{conditions}» فروشگاهی پیدا نشد؛ بدون این شرط‌ها نتیجه هست. محدوده یا بودجه را تغییر دهید."
            else:
                msg = f"برای «{query_label}» فروشگاه حضوری پیدا نشد. عبارت کوتاه‌تر یا نام برند را امتحان کنید."
            return {"type": "product_search", "message": msg, "products": [], "state": new_state}

        prod_list = [self._with_best_offer(p, filters, nearest=near) for p in products]
        if prod_list and prod_list[0].get("best_shop"):
            new_state["active_shop_id"] = prod_list[0]["best_shop"]["shop_id"]
        head = intro or ("نزدیک‌ترین فروشگاه‌ها" if near else "نتایج خرید حضوری")
        if slots.get("near") and ulat is None:
            conditions = (conditions + "، " if conditions else "") + "برای «نزدیک‌ترین»، موقعیتتان را از دکمه «موقعیت من» تعیین کنید"
        msg = f"{head} برای «{query_label}»" + (f" ({conditions})" if conditions else "") + ":"
        hub_guide = slots.get("bazaar_hub_guide")
        where_to_buy = bool(slots.get("where_to_buy"))
        if hub_guide and (where_to_buy or not slots.get("place")):
            msg += f"\n💡 {hub_guide}"

        # تولید سوالات تکمیلی هوشمند بر اساس الگوریتم هوش مصنوعی کالا و الگوریتم DCPG
        suggested_prompts = []
        if products:
            c_items = [{"product_id": pid} for pid in (cart_ids or [])]
            try:
                from .algorithms.ai_product_intelligence import get_product_intelligence
                intel = get_product_intelligence(self.conn, products[0], mall_name=slots.get("place"))
                if intel.get("in_store_prompts"):
                    suggested_prompts = list(intel["in_store_prompts"])
            except Exception:
                pass
            if not suggested_prompts:
                suggested_prompts = generate_dynamic_prompts(
                    product=products[0],
                    shop=products[0].get("best_shop"),
                    cart_items=c_items,
                    mall_name=slots.get("place"),
                )

        return {
            "type": "product_search",
            "message": msg,
            "products": prod_list,
            "applied_filters": filters,
            "state": new_state,
            "suggested_prompts": suggested_prompts,
        }

    def _with_best_offer(self, p, filters, nearest=False):
        """ارزان‌ترین (یا نزدیک‌ترین) آفر منطبق با همان شرایط خرید، با ساعت کاری، فاصله و استعلام"""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            SELECT {OFFER_COLUMNS}, o.warranty, s.name, s.contacts, s.is_verified
            FROM offers o JOIN shops s ON o.shop_id = s.shop_id
            WHERE o.product_id = ? AND o.price_toman IS NOT NULL
            ORDER BY o.price_toman ASC
        """, (p["product_id"],))
        cols = [d[0] for d in cursor.description]
        ulat, ulon = getattr(self, "user_loc", (None, None))
        matches = []
        for values in cursor.fetchall():
            row = dict(zip(cols, values))
            if offer_matches(row, **filters):
                row["distance_km"] = distance_km(ulat, ulon, row["lat"], row["lon"])
                matches.append(row)
        best = None
        if matches:
            best = min(matches, key=lambda r: (r["distance_km"] is None, r["distance_km"] or 0)) if nearest else matches[0]
        item = {
            "product_id": p["product_id"],
            "title": p["persian_title"],
            "category": p["category_name"],
            "brand": p["brand_name"],
            "min_price": p["min_price_toman"],
            "offline_shops_count": p["available_offline_shops_count"],
            "best_shop": None,
        }
        if best:
            hours = hours_status(best["weekly_hours"])
            from .algorithms.ai_product_intelligence import score_offer_quality
            q_score, q_badge, q_reasons = score_offer_quality(
                best, {"name": best["name"], "is_verified": best.get("is_verified", 0)}
            )
            ref_shop_id = getattr(self, "_active_shop_id", None)
            is_same_shop = bool(ref_shop_id and str(best["shop_id"]) == str(ref_shop_id))
            item["best_shop"] = {
                "shop_id": best["shop_id"],
                "name": best["name"],
                "hub": best["location_label"],
                "price": best["price_toman"],
                "warranty": best["warranty"],
                "quality_score": q_score,
                "quality_badge": q_badge,
                "quality_reasons": q_reasons,
                "is_same_shop": is_same_shop,
                "same_shop_badge": ("موجود در همین مغازه 🏬" if is_same_shop else None),
                "hours": hours["label"],
                "hours_state": hours["state"],
                "distance_km": round(best["distance_km"], 2) if best["distance_km"] is not None else None,
                "parsed_address": parse_mall_address(best["address"], best["location_label"]),
            }
            item["stock_info"] = compute_stock_certainty(
                {"price_toman": best["price_toman"], "last_price_changed_at": best["last_price_changed_at"]},
                {"weekly_hours": best["weekly_hours"]},
            )
            item["dossier"] = generate_inquiry_dossier(p["persian_title"], best["price_toman"], best["name"], best["contacts"])
        return item

    def _complementary(self, context, cart_ids, state, slots):
        product_id = None
        prompt_tokens = slots.get("tokens") or []
        query_tokens = [t for t in prompt_tokens if t not in ("اقلام", "مکمل", "تکمیل", "خرید", "این", "چیه", "برای", "سازگار", "لوازم", "جانبی")]
        if query_tokens:
            matched = search_products(self.conn, query_tokens, limit=1, accessories="exclude")
            if matched:
                product_id = matched[0]["product_id"]

        if not product_id and state.get("active_product_id"):
            product_id = state.get("active_product_id")

        if not product_id:
            product_id = context.get("active_product_id") or (cart_ids[-1] if cart_ids else None)

        if not product_id and state.get("tokens"):
            tokens = state.get("tokens") or []
            loose = search_products(self.conn, tokens, limit=1, accessories="exclude")
            if loose:
                product_id = loose[0]["product_id"]

        shop_id = context.get("active_shop_id") or state.get("active_shop_id")

        if not product_id:
            return {
                "type": "text",
                "message": "برای دریافت اقلام مکمل، لطفاً ابتدا یک کالا (مثلاً گوشی سامسونگ یا دریل) را انتخاب کرده یا به سبد خرید اضافه کنید تا لوازم جانبی سازگار با آن را از همان مغازه یا همان پاساژ پیشنهاد دهم.",
                "state": state,
            }

        cursor = self.conn.cursor()
        row = cursor.execute("""
            SELECT p.product_id, p.persian_title, p.category_name, p.brand_name, ps.min_price
            FROM products p LEFT JOIN product_stats ps ON ps.product_id = p.product_id
            WHERE p.product_id = ?
        """, (product_id,)).fetchone()
        if not row:
            return {"type": "text", "message": "اطلاعات کالای مبدأ پیدا نشد.", "state": state}

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

        # ۱. تحلیل پویا و استخراج عینی از طریق موتور هوش مصنوعی کالا (DCA) با پوشش ۱۰۰٪ کاتالوگ
        from .algorithms.ai_product_intelligence import find_grounded_complementary_items
        scored, ai_prompts = find_grounded_complementary_items(self.conn, base_product, base_shop, limit=4)
        for cand in scored:
            cand["reason"] = cand.get("ai_reason") or cand.get("reason")
            cand["location_description"] = cand.get("location_desc") or cand.get("loc_desc")
            if "parsed_address" not in cand:
                cand["parsed_address"] = parse_mall_address(cand.get("address"), cand.get("location_label"))

        # ۲. در صورتی که نتیجه‌ای حاصل نشد، بررسی جدول قواعد به عنوان پشتیبان
        if not scored:
            rules = cursor.execute("""
                SELECT target_pattern, dep_score, description_fa FROM complementary_rules WHERE ? LIKE source_pattern
            """, (base_product["category_name"] or "",)).fetchall()

            if not rules:
                return {
                    "type": "text",
                    "message": f"برای «{base_product['title']}» در حال حاضر قلم مکمل سازگار در فروشگاه‌های ثبت‌شده این راسته پیدا نشد.",
                    "state": state,
                }

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
                    LIMIT 80
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
                        "parsed_address": parse_mall_address(cand["address"], cand["location_label"]),
                    })
                    best_by_product[cand["product_id"]] = cand

            scored = sorted(best_by_product.values(), key=lambda x: x["paco_score"], reverse=True)[:4]
        if not scored:
            return {
                "type": "text",
                "message": f"برای «{base_product['title']}» در حال حاضر کالای مکمل فیزیکی با قیمت تاییدشده در پاساژ ثبت نشده است.",
                "state": state,
            }

        return {
            "type": "complementary_recommendations",
            "message": f"اقلام مکمل و سازگار برای «{base_product['title']}» (محاسبه‌شده با الگوریتم PACO):",
            "recommendations": scored,
            "suggested_prompts": ai_prompts or [],
            "state": state,
        }

    def _panic(self, context, cart_ids):
        product_id = context.get("active_product_id") or (cart_ids[0] if cart_ids else None)
        shop_id = context.get("active_shop_id")
        if not product_id or not shop_id:
            return {
                "type": "text",
                "message": "برای پیدا کردن جایگزین باید بدانم کدام کالا و کدام مغازه. در صفحه کالا یا برنامه حرکت سبد، کنار همان مغازه دکمه «بسته بود؟» را بزنید تا جایگزین‌های همان طبقه و همان پاساژ را نشان بدهم.",
            }
        fallbacks = find_emergency_fallbacks(self.conn, product_id, shop_id)
        if fallbacks.get("error"):
            return {"type": "text", "message": "این مغازه در پایگاه داده پیدا نشد؛ لطفاً از صفحه کالا دوباره امتحان کنید."}
        return {"type": "panic_fallback", "message": fallbacks["action_guide"], "fallback_data": fallbacks}

    def _route(self, cart_ids, place, visit=False):
        if not cart_ids:
            return {
                "type": "text",
                "message": "سبد خرید حضوری شما خالی است. کالاهایی را که می‌خواهید با «افزودن به سبد خرید حضوری» اضافه کنید تا مسیر خرید را بچینم.",
            }
        route_result = self.router.solve_cart(cart_ids, preferred_hub=place)
        primary = route_result.get("primary_route")
        if not primary:
            return {"type": "text", "message": "برای همه اقلام سبد شما فروشگاه حضوری با قیمت ثبت‌شده پیدا نشد."}
        savings = route_result.get("savings")
        note = ""
        if place and primary.get("hub") != place:
            note = f"\nدر {place} همه اقلام موجود نبود؛ بهترین مسیر جایگزین را انتخاب کردم."
        closed = [s["shop_name"] for s in primary.get("stops", []) if (s.get("hours") or {}).get("state") == "closed"]
        if closed:
            note += f"\n⚠️ این مغازه‌ها الان بسته‌اند: {'، '.join(closed)}"
        savings_msg = f"\n**{savings['description']}**" if savings else ""
        plan = route_result.get("visit_plan")
        plan_msg = f"\n🕒 **بهترین زمان مراجعه:** {plan['label']}" if plan else ""
        head = f"برای {to_fa_digits(primary.get('stops_count', 0))} مغازه مسیر خریدتان" if visit else \
            f"مسیر خرید حضوری در {primary.get('hub') or 'مراکز خرید تهران'} با {to_fa_digits(primary.get('stops_count', 0))} توقف آماده شد."
        if visit:
            return {"type": "cart_route", "message": f"{head}:{plan_msg}{note}", "route": route_result}
        return {
            "type": "cart_route",
            "message": f"{head}{note}{plan_msg}{savings_msg}",
            "route": route_result,
        }

    def _credit(self, slots, state):
        place = slots.get("place")
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT shop_id, name, address, location_label, payment_options, weekly_hours
            FROM shops WHERE credit_providers IS NOT NULL AND offer_count > 0
        """)
        shops = [
            {"shop_id": r[0], "name": r[1], "address": r[2], "location_label": r[3], "payment_options": r[4], "weekly_hours": r[5]}
            for r in cursor.fetchall() if place_matches(place, r[3], r[2])
        ]
        ranked = filter_and_rank_by_credit(shops, required_provider=slots.get("provider"),
                                           in_person_only=bool(slots.get("in_person")))
        where = describe_filters({"place": place, "provider": slots.get("provider")})
        if not ranked:
            return {"type": "text", "message": f"فروشگاه دارای خرید اقساطی ({where or 'در کل تهران'}) پیدا نشد.", "state": state}
        credit_shops = [{
            "shop_id": s["shop_id"],
            "name": s["name"],
            "hub": s["location_label"],
            "parsed_address": parse_mall_address(s["address"], s["location_label"]),
            "credit_analysis": s["credit_analysis"],
            "hours": hours_status(s["weekly_hours"])["label"],
        } for s in ranked[:6]]
        return {
            "type": "credit_shops",
            "message": f"{to_fa_digits(len(ranked))} فروشگاه با خرید اقساطی" + (f" ({where})" if where else "") +
                       ". کانال «نامشخص» یعنی در ترب ثبت نشده که اقساط با کارتخوان حضوری هم ممکن است یا نه؛ پیش از رفتن بپرسید.",
            "shops": credit_shops,
            "state": state,
        }

    def _open_shops(self, slots, state):
        """فروشگاه‌های الان باز، یا (اگر «جمعه» گفته شده) فروشگاه‌هایی که جمعه‌ها باز هستند"""
        place = slots.get("place")
        friday = bool(slots.get("friday"))
        cursor = self.conn.cursor()
        cursor.execute("SELECT shop_id, name, address, location_label, weekly_hours FROM shops WHERE hours_known = 1 AND offer_count > 0")
        rows = [r for r in cursor.fetchall() if place_matches(place, r[3], r[2])]
        matches = []
        for r in rows:
            h = hours_status(r[4])
            ok = h["friday_closed"] is False if friday else h["state"] == "open"
            if ok:
                label = next((d["hours"] for d in h["week"] if d["day"] == "جمعه"), "") if friday else h["label"]
                matches.append({"shop_id": r[0], "name": r[1], "hub": r[3], "hours": (f"جمعه: {label}" if friday else label),
                                "parsed_address": parse_mall_address(r[2], r[3])})
        where = f" در {place}" if place else ""
        when = "جمعه‌ها" if friday else "الان"
        if not matches:
            return {"type": "text", "message": f"از {to_fa_digits(len(rows))} فروشگاهی که ساعت کاری ثبت کرده‌اند{where}، {when} هیچ‌کدام باز نیست.", "state": state}
        return {
            "type": "open_shops",
            "message": f"{to_fa_digits(len(matches))} فروشگاه{where} {when} باز است (از {to_fa_digits(len(rows))} فروشگاه دارای ساعت کاری ثبت‌شده). فروشگاه‌های بدون ساعت کاری ثبت‌شده در این فهرست نیستند.",
            "shops": matches[:6],
            "state": state,
        }

    def _consultation(self, text, slots, state, cart_ids, context):
        active_pid = context.get("active_product_id") or state.get("active_product_id")
        if not active_pid and cart_ids:
            active_pid = cart_ids[-1]
        if not active_pid and state.get("tokens"):
            loose = search_products(self.conn, state["tokens"], limit=1, accessories="exclude")
            if loose:
                active_pid = loose[0]["product_id"]
        active_sid = context.get("active_shop_id") or state.get("active_shop_id")
        from .algorithms.ai_product_intelligence import answer_consultation_inquiry
        ans = answer_consultation_inquiry(
            self.conn,
            text,
            active_product_id=active_pid,
            active_shop_id=active_sid,
            context=context,
        )
        products = [ans["active_product"]] if ans.get("active_product") else []
        if products and products[0].get("best_shop"):
            state["active_shop_id"] = products[0]["best_shop"]["shop_id"]
        return {
            "type": "consultation",
            "message": ans["message"],
            "products": products,
            "suggested_prompts": ans.get("suggested_prompts", []),
            "state": state,
        }


__all__ = ["KalamAssistant", "DIAGNOSTIC_TREES"]
