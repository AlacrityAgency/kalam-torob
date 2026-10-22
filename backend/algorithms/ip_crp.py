"""
الگوریتم ۱: موتور بهینه‌سازی سبد خرید حضوری و مسیریابی بهینه مغازه‌ها (IP-CRP Router)
حل مسئله NP-Hard سبد خرید چندقلمی در فضای سه‌بعدی پاساژها با قید پیمایش یک‌طرفه طبقات و کالای سنگین.
"""

from collections import defaultdict
from .imwp import parse_mall_address

# دسته‌های مشمول قید کالای سنگین
HEAVY_CATEGORIES = [
    "ژنراتور و موتور برق", "پمپ خانگی و صنعتی", "سیم و کابل برق ساختمان",
    "سایر الکتروموتور و لوازم جانبی", "دریل و پیچ گوشتی برقی و شارژی"
]

class InPersonCartRouter:
    def __init__(self, db_conn):
        self.conn = db_conn

    def solve_cart(self, product_ids: list, preferred_hub: str = None, strategy: str = "same_hub"):
        """
        ورودی: لیست شناسه‌های کالا
        استراتژی‌ها:
          - same_hub: مسیر طلایی پاساژ (پیشنهادی - پیمایش یک‌طرفه در یک مرکز خرید)
          - single_stop: تک‌فروشگاه (یک فاکتور بدون جابه‌جایی)
          - bargain: ارزان‌ترین قیمت ممکن در کل شهر
        """
        # حذف شناسه‌های تکراری با حفظ ترتیب
        product_ids = list(dict.fromkeys(product_ids or []))
        if not product_ids:
            return {"error": "سبد خرید خالی است."}

        cursor = self.conn.cursor()
        
        # استخراج اطلاعات کالاها
        placeholders = ",".join(["?"] * len(product_ids))
        cursor.execute(f"""
        SELECT product_id, persian_title, category_name, brand_name, image_urls
        FROM products
        WHERE product_id IN ({placeholders})
        """, product_ids)
        products = {row[0]: {
            "product_id": row[0],
            "title": row[1],
            "category_name": row[2],
            "brand": row[3],
            "image_urls": row[4],
            "is_heavy": row[2] in HEAVY_CATEGORIES
        } for row in cursor.fetchall()}

        # استخراج تمام آفرها و فروشگاه‌های دارای این کالاها
        cursor.execute(f"""
        SELECT o.product_id, o.price_toman, o.last_price_changed_at, o.warranty,
               s.shop_id, s.name, s.address, s.location_label, s.lat, s.lon, s.payment_options
        FROM offers o
        JOIN shops s ON o.shop_id = s.shop_id
        WHERE o.product_id IN ({placeholders}) AND o.price_toman IS NOT NULL
        ORDER BY o.price_toman ASC
        """, product_ids)
        
        offers = cursor.fetchall()
        
        # نگاشت داده‌ها
        prod_offers = defaultdict(list)
        shop_inventory = defaultdict(dict)
        shops_info = {}

        for off in offers:
            pid, price, last_changed, warranty, sid, sname, addr, loc, lat, lon, pay_opts = off
            prod_offers[pid].append({
                "shop_id": sid, "price": price, "warranty": warranty
            })
            # اگر مغازه چند پیشنهاد برای یک کالا دارد، ارزان‌ترین نگه داشته می‌شود
            current = shop_inventory[sid].get(pid)
            if current is None or price < current["price"]:
                shop_inventory[sid][pid] = {
                    "price": price, "warranty": warranty, "last_changed": last_changed
                }
            if sid not in shops_info:
                shops_info[sid] = {
                    "shop_id": sid, "name": sname, "address": addr,
                    "location_label": loc, "lat": lat, "lon": lon,
                    "payment_options": pay_opts
                }

        # ۱. تحلیل تک‌فروشگاه (Single-Stop)
        single_stops = []
        for sid, inv in shop_inventory.items():
            if all(p in inv for p in product_ids):
                total_p = sum(inv[p]["price"] for p in product_ids)
                s_info = shops_info[sid]
                parsed_addr = parse_mall_address(s_info["address"], s_info["location_label"])
                single_stops.append({
                    "shop_id": sid,
                    "shop_name": s_info["name"],
                    "hub": s_info["location_label"] or "نامشخص",
                    "address": s_info["address"],
                    "parsed_address": parsed_addr,
                    "total_price": total_p,
                    "stops_count": 1,
                    "items": [
                        {
                            "product_id": p,
                            "title": self._title(products, p),
                            "price": inv[p]["price"]
                        } for p in product_ids
                    ]
                })
        single_stops.sort(key=lambda x: (bool(preferred_hub) and x["hub"] != preferred_hub, x["total_price"]))

        # ۲. تحلیل هاب‌محور (Same-Hub / Mall Golden Path)
        # گروه‌بندی مغازه‌ها بر اساس location_label
        hubs = defaultdict(set)
        for sid, s_info in shops_info.items():
            # مغازه‌های بدون هاب در یک «هاب نامشخص» ساختگی کنار هم قرار نمی‌گیرند
            if s_info["location_label"]:
                hubs[s_info["location_label"]].add(sid)

        hub_routes = []
        for h, sids in hubs.items():
            # بررسی اینکه آیا تمام اقلام در این هاب موجودند؟
            hub_covered = True
            chosen_items_map = {}
            hub_price = 0

            for p in product_ids:
                p_in_hub = [
                    (s, shop_inventory[s][p]["price"])
                    for s in sids if p in shop_inventory[s]
                ]
                if not p_in_hub:
                    hub_covered = False
                    break
                best_sid, best_price = min(p_in_hub, key=lambda x: x[1])
                chosen_items_map[p] = (best_sid, best_price)
                hub_price += best_price

            if hub_covered:
                distinct_sids = list(set(s for s, pr in chosen_items_map.values()))
                ordered_stops = self._sequence_stops(distinct_sids, chosen_items_map, shops_info, products)
                
                # تخمین پیاده‌روی کل در پاساژ
                walking_meters = len(distinct_sids) * 45  # میانگین ۴۵ متر فاصله بین مغازه‌های پاساژ
                time_est_minutes = 15 + (len(distinct_sids) * 10)  # ۱۰ دقیقه معطلی تسویه هر مغازه

                hub_routes.append({
                    "hub": h,
                    "total_price": hub_price,
                    "stops_count": len(distinct_sids),
                    "walking_meters": walking_meters,
                    "time_estimate_minutes": time_est_minutes,
                    "stops": ordered_stops
                })

        # مرتب‌سازی هاب‌ها: اول مرکز خرید انتخابی کاربر، بعد تعداد توقف کمتر و قیمت کمتر
        hub_routes.sort(key=lambda x: (x["hub"] != preferred_hub, x["stops_count"], x["total_price"]))
        for route in hub_routes:
            route["is_preferred_hub"] = bool(preferred_hub) and route["hub"] == preferred_hub

        # ۳. تحلیل چندمرکزی شهر (Multi-Hub / City Coverage Fallback)
        city_chosen_map = {}
        city_price = 0
        for p in product_ids:
            if prod_offers[p]:
                best_off = min(prod_offers[p], key=lambda x: x["price"])
                city_chosen_map[p] = (best_off["shop_id"], best_off["price"])
                city_price += best_off["price"]
        
        multi_hub_route = None
        if city_chosen_map and len(city_chosen_map) == len(product_ids):
            distinct_sids = list(set(s for s, pr in city_chosen_map.values()))
            ordered_stops = self._sequence_stops(distinct_sids, city_chosen_map, shops_info, products)
            hubs_involved = sorted(set(shops_info[s]["location_label"] or "نامشخص" for s in distinct_sids))
            hub_name_str = " و ".join(hubs_involved[:2]) + ("..." if len(hubs_involved) > 2 else "")
            multi_hub_route = {
                "hub": f"راسته‌های {hub_name_str}",
                "strategy": "مسیر ترکیبی بازارهای شهر (پوشش کامل اقلام)",
                "total_price": city_price,
                "stops_count": len(distinct_sids),
                "walking_meters": len(distinct_sids) * 60,
                "time_estimate_minutes": 20 + (len(distinct_sids) * 12),
                "stops": ordered_stops
            }

        # محاسبه درصد صرفه‌جویی
        savings = None
        if single_stops and hub_routes:
            best_single_p = single_stops[0]["total_price"]
            best_hub_p = hub_routes[0]["total_price"]
            diff = best_single_p - best_hub_p
            if diff > 0:
                pct = round((diff / best_single_p) * 100, 1)
                savings = {
                    "diff_toman": diff,
                    "percent": pct,
                    "description": f"{diff:,} تومان ({pct}٪) صرفه‌جویی نسبت به تک‌مغازه با فقط چند قدم پیاده‌روی!"
                }

        # انتخاب مسیر برگزیده بر اساس استراتژی درخواستی
        if strategy == "single_stop" and single_stops:
            primary_route = {
                "strategy": "تک‌فروشگاه (یک فاکتور بدون جابه‌جایی)",
                "hub": single_stops[0]["hub"],
                "total_price": single_stops[0]["total_price"],
                "stops_count": 1,
                "stops": [{
                    "step_number": 1,
                    "shop_id": single_stops[0]["shop_id"],
                    "shop_name": single_stops[0]["shop_name"],
                    "parsed_address": single_stops[0]["parsed_address"],
                    "items": single_stops[0]["items"]
                }]
            }
        elif strategy == "bargain" and multi_hub_route:
            primary_route = multi_hub_route
        else:
            primary_route = hub_routes[0] if hub_routes else (single_stops[0] if single_stops else multi_hub_route)

        return {
            "requested_items_count": len(product_ids),
            "primary_route": primary_route,
            "savings": savings,
            "single_stop_available": len(single_stops) > 0,
            "best_single_stop": single_stops[0] if single_stops else None,
            "available_hubs": hub_routes[:5]
        }

    @staticmethod
    def _title(products, pid):
        return products[pid]["title"] if pid in products else f"کالای {pid}"

    def _sequence_stops(self, distinct_sids, chosen_items_map, shops_info, products):
        """
        مرتب‌سازی توقف‌ها بر اساس پیمایش یک‌طرفه طبقات (Monotonic Floor Order)
        و قید کالای سنگین در ایستگاه آخر (Heavy-Item Last Constraint)
        """
        raw_stops = []
        for sid in distinct_sids:
            s_info = shops_info[sid]
            parsed_addr = parse_mall_address(s_info["address"], s_info["location_label"])
            
            # اقلام مربوط به این مغازه
            items = []
            has_heavy = False
            for p, (s, pr) in chosen_items_map.items():
                if s == sid:
                    is_heavy = products.get(p, {}).get("is_heavy", False)
                    items.append({
                        "product_id": p,
                        "title": self._title(products, p),
                        "price": pr,
                        "is_heavy": is_heavy
                    })
                    if is_heavy:
                        has_heavy = True

            raw_stops.append({
                "shop_id": sid,
                "shop_name": s_info["name"],
                "address": s_info["address"],
                "parsed_address": parsed_addr,
                "floor_level": parsed_addr["floor_level"],
                "hub": s_info["location_label"] or "",
                "payment_options": s_info["payment_options"],
                "has_heavy_item": has_heavy,
                "items": items
            })

        # مرتب‌سازی صعودی یکنواخت طبقات: همکف (0) -> اول (1) -> دوم (2)...
        # با حفظ قید: اگر مغازه‌ای کالای سنگین دارد، با اولویت به انتهای مسیر منتقل شود.
        # در مسیر چندهابی، توقف‌های هر هاب کنار هم می‌مانند تا بین راسته‌ها رفت‌وبرگشت نشود.
        raw_stops.sort(key=lambda s: (1 if s["has_heavy_item"] else 0, s["hub"], s["floor_level"]))

        # شماره‌گذاری گام‌ها
        for idx, stop in enumerate(raw_stops, 1):
            stop["step_number"] = idx

        return raw_stops
