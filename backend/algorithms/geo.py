"""
محاسبات مکانی: فاصله هاورساین و اعتبارسنجی مختصات تهران.
"""

from __future__ import annotations

import math

# محدوده تقریبی تهران بزرگ؛ مختصات بیرون از آن به احتمال زیاد اشتباه است
TEHRAN_BOUNDS = (35.45, 35.95, 51.0, 51.75)


def valid_coord(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def distance_km(lat1, lon1, lat2, lon2) -> float | None:
    """فاصله هاورساین بین دو نقطه (کیلومتر)؛ اگر مختصات ناقص باشد None."""
    if not (valid_coord(lat1, lon1) and valid_coord(lat2, lon2)):
        return None
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp, dl = math.radians(float(lat2) - float(lat1)), math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
