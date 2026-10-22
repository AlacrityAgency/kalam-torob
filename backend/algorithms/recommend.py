"""
پیشنهاد فروشگاه با دلیل قابل فهم («چرا این فروشگاه؟»).

امتیاز هر آفر سالم (غیر کپی، قیمت غیرپرت) از چهار معیار گام سوم چالش ساخته می‌شود:
قیمت، نزدیکی به کاربر، ساعت کاری (الان باز بودن) و تازگی قیمت. اگر موقعیت کاربر معلوم نباشد،
وزن فاصله بین بقیه معیارها پخش می‌شود. خروجی علاوه بر بهترین آفر، دلیل‌های متنی آن را دارد.
"""

from __future__ import annotations

from .textutil import to_fa_digits

WEIGHTS = {"price": 0.45, "distance": 0.25, "open": 0.15, "fresh": 0.15}
OPEN_SCORE = {"open": 1.0, "unknown": 0.6, "closed": 0.2}


def _fa_km(km: float) -> str:
    if km < 1:
        return f"{to_fa_digits(int(round(km * 1000, -1)))} متر"
    return f"{to_fa_digits(f'{km:.1f}').replace('.', '٫')} کیلومتر"


def rank_offers(offers: list[dict]) -> dict | None:
    """
    offers: هر آیتم شامل offer_id, price_toman, is_copy, price_suspect, distance_km,
            hours_state, days_since_update, has_credit
    خروجی: {"offer_id", "score", "reasons": [...], "cautions": [...], "scores": {offer_id: score}} یا None
    """
    pool = [o for o in offers if o.get("price_toman") and not o.get("is_copy") and not o.get("price_suspect")]
    if not pool:
        return None

    prices = [o["price_toman"] for o in pool]
    min_p = min(prices)
    dists = [o["distance_km"] for o in pool if o.get("distance_km") is not None]
    use_distance = len(dists) == len(pool) and len(pool) > 0
    weights = dict(WEIGHTS)
    if not use_distance:
        extra = weights.pop("distance")
        total = sum(weights.values())
        weights = {k: v + extra * v / total for k, v in weights.items()}

    scores = {}
    for o in pool:
        # نسبت به ارزان‌ترین (نه min-max): اختلاف ۵٪ قیمت نباید کل وزن قیمت را جابه‌جا کند
        price_s = min_p / o["price_toman"]
        age = o.get("days_since_update")
        fresh_s = 0.5 if age is None else max(0.0, 1 - age / 60)
        s = weights["price"] * price_s + weights["open"] * OPEN_SCORE.get(o.get("hours_state"), 0.6) + weights["fresh"] * fresh_s
        if use_distance:
            # ۰ کیلومتر = ۱، هر ۵ کیلومتر نصف
            s += weights["distance"] * (1 / (1 + o["distance_km"] / 5))
        scores[o["offer_id"]] = round(s, 4)

    best = max(pool, key=lambda o: (scores[o["offer_id"]], -o["price_toman"]))
    reasons, cautions = [], []
    cheaper_than = sum(1 for p in prices if p > best["price_toman"])
    if best["price_toman"] == min_p:
        reasons.append("ارزان‌ترین قیمت بین فروشگاه‌های معتبر")
    elif len(prices) > 2 and cheaper_than / len(prices) >= 0.5:
        reasons.append(f"ارزان‌تر از {to_fa_digits(cheaper_than)} فروشگاه از {to_fa_digits(len(prices))} فروشگاه")
    if use_distance:
        if best["distance_km"] == min(dists):
            reasons.append(f"نزدیک‌ترین فروشگاه ({_fa_km(best['distance_km'])} از شما)")
        else:
            reasons.append(f"{_fa_km(best['distance_km'])} از شما")
    if best.get("hours_state") == "open":
        reasons.append("الان باز است")
    elif best.get("hours_state") == "closed":
        cautions.append("الان بسته است؛ پیش از رفتن ساعت کاری را ببینید")
    else:
        cautions.append("ساعت کاری ثبت نشده؛ پیش از رفتن استعلام کنید")
    age = best.get("days_since_update")
    if age is None:
        cautions.append("تاریخ به‌روزرسانی قیمت نامشخص است")
    elif age > 60:
        cautions.append("قیمت قدیمی است؛ استعلام کنید")
    if age is not None and age <= 14:
        reasons.append(f"قیمت {to_fa_digits(age)} روز پیش به‌روز شده" if age else "قیمت امروز به‌روز شده")
    if best.get("has_credit"):
        reasons.append("خرید اقساطی دارد")

    return {"offer_id": best["offer_id"], "score": scores[best["offer_id"]], "reasons": reasons, "cautions": cautions,
            "scores": scores, "used_distance": use_distance}
