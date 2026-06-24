import asyncio
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, date as date_type
from models import TeeTime

# bernardusgolf.com serves an expired TLS cert; skip verification for this host only.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Bernardus Golf (Cromvoirt) — bespoke WordPress booking. Public 2-step flow:
#   POST wp-json/bernardus/v1/booking-start            -> {"uuid": <session>}
#   GET  wp-json/bernardus/v1/booking-start-times?date=YYYY-M-D&players=N&holes=H&session_uuid=<uuid>
# It's an 18-hole championship course bookable as 9 or 18 holes (day membership, ~€255).
BASE = "https://bernardusgolf.com/wp-json/bernardus/v1"
BOOKING_URL = "https://bernardusgolf.com/book-day-membership/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": BOOKING_URL}


def _post(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=12, context=_SSL_CTX) as r:
        return json.loads(r.read())


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=_SSL_CTX) as r:
        return json.loads(r.read())


def _fetch_sync(date: str, players: int, holes_list: list[int]) -> list[dict]:
    session = _post(f"{BASE}/booking-start").get("uuid")
    if not session:
        return []
    y, m, d = date.split("-")
    api_date = f"{int(y)}-{int(m)}-{int(d)}"
    out = []
    for h in holes_list:
        q = urllib.parse.urlencode({"date": api_date, "players": players, "holes": h, "session_uuid": session})
        out.extend(_get(f"{BASE}/booking-start-times?{q}"))
    return out


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    if not include_championship:
        return []
    holes_list = [holes] if holes in (9, 18) else [18, 9]
    raw = await asyncio.to_thread(_fetch_sync, date, players, holes_list)
    seen = set()
    result = []
    for tt in raw:
        key = (tt["start_time"], tt["holes"])
        if key in seen:
            continue
        seen.add(key)
        ts = datetime.fromisoformat(tt["timestamp"].replace("Z", "+00:00"))
        result.append(TeeTime(
            course="Bernardus",
            sub_course="Bernardus",
            time=tt["start_time"],
            timestamp=ts,
            holes=tt["holes"],
            free_slots=4,
            total_slots=4,
            price_eur=tt.get("price"),
            is_available=True,
            booking_url=BOOKING_URL,
            is_short=False,
        ))
    return result
