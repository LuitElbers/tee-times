import asyncio
from datetime import datetime, date as date_type
import httpx
from cachetools import TTLCache
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0)

_token_cache: TTLCache = TTLCache(maxsize=10, ttl=55 * 60)

COURSES = [
    {
        "origin": "https://dehogedijk.teecontrol.com",
        "course_name": "Hoge Dijk",
        "booking_url": "https://dehogedijk.teecontrol.com/book",
    },
    {
        "origin": "https://spaarnwoude.teecontrol.com",
        "course_name": "Spaarnwoude",
        "booking_url": "https://spaarnwoude.teecontrol.com/book",
    },
    {
        "origin": "https://liemeer.teecontrol.com",
        "course_name": "Liemeer",
        "booking_url": "https://liemeer.teecontrol.com/book",
    },
    {
        "origin": "https://bergvliet.teecontrol.com",
        "course_name": "Bergvliet",
        "booking_url": "https://bergvliet.teecontrol.com/book",
    },
]

API_BASE = "https://api.teecontrol.com"

# Sub-courses with no par-5 holes, verified from club scorecards
SHORT_COURSES = {"Abcoudebaan", "A-holes", "B-holes", "F-holes"}


async def _get_token(origin: str) -> str:
    if origin in _token_cache:
        return _token_cache[origin]
    resp = await _client.get(f"{API_BASE}/auth/guest", headers={"Origin": origin})
    resp.raise_for_status()
    token = resp.json()["token"]
    _token_cache[origin] = token
    return token


def _strip_season_prefix(name: str) -> str:
    if " | " in name:
        return name.split(" | ", 1)[1]
    return name


async def _fetch_course(course: dict, date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    origin = course["origin"]
    token = await _get_token(origin)
    headers = {"Authorization": f"Guest {token}", "Origin": origin}

    sets_resp = await _client.get(
        f"{API_BASE}/sets",
        params={"can_book_at": date},
        headers=headers,
    )
    sets_resp.raise_for_status()
    sets = sets_resp.json()

    filtered_sets = []
    for s in sets:
        if "footgolf" in s.get("name", "").lower():
            continue
        is_short = s.get("is_par_three") or _strip_season_prefix(s.get("name", "")) in SHORT_COURSES
        if is_short and not include_par3:
            continue
        if not is_short and not include_championship:
            continue
        if holes is not None and s.get("holes_amount") != holes:
            continue
        filtered_sets.append(s)

    async def _fetch_set(s: dict) -> list[TeeTime]:
        resp = await _client.get(
            f"{API_BASE}/start-times",
            params={
                "date": date,
                "slots": players,
                "set_uuid": s["uuid"],
                "with_players": 1,
                "with_unavailable": 0,
            },
            headers=headers,
        )
        resp.raise_for_status()
        items = resp.json()
        result = []
        for item in items:
            if not item.get("is_available"):
                continue
            occupied = item.get("occupied_slots", 0)
            price_val = item.get("player_price", {}).get("money", {}).get("value")
            result.append(TeeTime(
                course=course["course_name"],
                sub_course=_strip_season_prefix(s["name"]),
                time=item["time"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
                holes=item["set"]["holes_amount"],
                free_slots=4 - occupied,
                total_slots=4,
                price_eur=price_val,
                is_available=True,
                booking_url=course["booking_url"],
            ))
        return result

    set_results = await asyncio.gather(*[_fetch_set(s) for s in filtered_sets])
    return [tt for sublist in set_results for tt in sublist]


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    results = await asyncio.gather(
        *[_fetch_course(c, date, players, holes, include_par3, include_championship) for c in COURSES],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
