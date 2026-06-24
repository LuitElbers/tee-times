import asyncio
import json
import urllib.request
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from models import TeeTime

# chronogolf's WAF 403s httpx (TLS fingerprint); plain urllib passes, so we fetch
# in a thread to keep the async interface.
AMS = ZoneInfo("Europe/Amsterdam")
API = "https://www.chronogolf.com/marketplace/v2/teetimes"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}

# Chronogolf (Lightspeed Golf). course_uuid comes from the __NEXT_DATA__ JSON on
# chronogolf.com/club/<slug> (pageProps.club.courses[].uuid). All NL clubs here are
# 9-hole regulation courses. Hoogland (highland-golf-club-amersfoort) is on chronogolf
# too but releases no greenfee online (0 teetimes every date), so it's excluded.
COURSES = [
    {"course_uuid": "9d47102f-2829-4174-b02c-bf1d21fd017d", "name": "Weesp", "slug": "golfbaan-weesp"},
    {"course_uuid": "4e453c71-a9d5-46ba-90f3-c0fcdef6760c", "name": "Golfcentrum Dongen", "slug": "golfcentrum-dongen"},
    {"course_uuid": "f1f454b0-6547-4bd4-a381-c1e09d244210", "name": "Golfcentrum Roosendaal", "slug": "golfcentrum-roosendaal"},
]


def _get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read())


async def _fetch_course(course: dict, date: str, players: int, holes: int | None) -> list[TeeTime]:
    booking_url = f"https://www.chronogolf.com/club/{course['slug']}"
    result: list[TeeTime] = []
    page = 1
    while True:
        data = await asyncio.to_thread(_get, {
            "start_date": date,
            "course_ids": course["course_uuid"],
            "holes": "9,18",
            "start_time": "00:00",
            "page": page,
        })
        teetimes = data.get("teetimes", [])
        if not teetimes:
            break
        for tt in teetimes:
            price = tt.get("default_price") or {}
            slot_holes = price.get("bookable_holes") or tt.get("course", {}).get("holes")
            if holes is not None and slot_holes != holes:
                continue
            if tt.get("max_player_size", 4) < players:
                continue
            ts = datetime.fromisoformat(tt["starts_at"].replace("Z", "+00:00"))
            result.append(TeeTime(
                course=course["name"],
                sub_course=tt.get("course", {}).get("name", course["name"]),
                time=ts.astimezone(AMS).strftime("%H:%M"),
                timestamp=ts,
                holes=slot_holes,
                free_slots=tt.get("max_player_size", 4),
                total_slots=4,
                price_eur=price.get("green_fee"),
                is_available=True,
                booking_url=booking_url,
                is_short=False,
            ))
        if len(teetimes) < 24:
            break
        page += 1
    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    if not include_championship:
        return []
    results = await asyncio.gather(
        *[_fetch_course(c, date, players, holes) for c in COURSES],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
