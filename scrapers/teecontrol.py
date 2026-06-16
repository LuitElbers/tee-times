import asyncio
from datetime import datetime, date as date_type
import httpx
from cachetools import TTLCache
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0)

# api.teecontrol.com enforces a per-IP request-RATE limit. A global throttle (min
# gap between request starts) is the only thing that reliably serves all clubs.
# This backend is now warmer-only (warm.py fetches 23 clubs × 7 days), so it pays
# for completeness over latency: 0.1s (10/s) sustained still triggered 429 storms
# across that many requests, so we run gentler. Tokens cache 55min; 429s retry
# with backoff as a safety net. If a future run still shows 429s, raise this.
_MIN_INTERVAL = 0.3
_rate_lock = asyncio.Lock()
_next_slot = 0.0
_resp_cache: TTLCache = TTLCache(maxsize=512, ttl=60)
_token_cache: TTLCache = TTLCache(maxsize=64, ttl=55 * 60)


async def _throttle() -> None:
    global _next_slot
    async with _rate_lock:
        now = asyncio.get_event_loop().time()
        wait = _next_slot - now
        if wait > 0:
            await asyncio.sleep(wait)
        _next_slot = max(now, _next_slot) + _MIN_INTERVAL


async def _get(url: str, *, params=None, headers=None, cache_key: str | None = None, retries: int = 6):
    if cache_key is not None and cache_key in _resp_cache:
        return _resp_cache[cache_key]
    for attempt in range(retries):
        await _throttle()
        resp = await _client.get(url, params=params, headers=headers)
        if resp.status_code == 429 and attempt < retries - 1:
            await asyncio.sleep(0.5 * (2 ** attempt))
            continue
        resp.raise_for_status()
        data = resp.json()
        if cache_key is not None:
            _resp_cache[cache_key] = data
        return data
    resp.raise_for_status()

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
    {"origin": "https://dirkshorn.teecontrol.com", "course_name": "Dirkshorn", "booking_url": "https://dirkshorn.teecontrol.com/book"},
    {"origin": "https://haarlemmermeersche.teecontrol.com", "course_name": "Haarlemmermeersche", "booking_url": "https://haarlemmermeersche.teecontrol.com/book"},
    {"origin": "https://golfpark-spandersbosch.teecontrol.com", "course_name": "Spandersbosch", "booking_url": "https://golfpark-spandersbosch.teecontrol.com/book"},
    {"origin": "https://kralingen.teecontrol.com", "course_name": "Kralingen", "booking_url": "https://kralingen.teecontrol.com/book"},
    {"origin": "https://bentwoud.teecontrol.com", "course_name": "Bentwoud", "booking_url": "https://bentwoud.teecontrol.com/book"},
    {"origin": "https://zeegersloot.teecontrol.com", "course_name": "Zeegersloot", "booking_url": "https://zeegersloot.teecontrol.com/book"},
    {"origin": "https://dehoogerotterdamsche.teecontrol.com", "course_name": "De Hooge Rotterdamsche", "booking_url": "https://dehoogerotterdamsche.teecontrol.com/book"},
    {"origin": "https://hitland.teecontrol.com", "course_name": "Hitland", "booking_url": "https://hitland.teecontrol.com/book"},
    {"origin": "https://zeewolde.teecontrol.com", "course_name": "Zeewolde", "booking_url": "https://zeewolde.teecontrol.com/book"},
    {"origin": "https://harderwold.teecontrol.com", "course_name": "Harderwold", "booking_url": "https://harderwold.teecontrol.com/book"},
    {"origin": "https://emmeloord.teecontrol.com", "course_name": "Emmeloord", "booking_url": "https://emmeloord.teecontrol.com/book"},
    {"origin": "https://gulbergen.teecontrol.com", "course_name": "De Gulbergen", "booking_url": "https://gulbergen.teecontrol.com/book"},
    {"origin": "https://nieuwkerk.teecontrol.com", "course_name": "Landgoed Nieuwkerk", "booking_url": "https://nieuwkerk.teecontrol.com/book"},
    {"origin": "https://heelsum.teecontrol.com", "course_name": "Heelsum", "booking_url": "https://heelsum.teecontrol.com/book"},
    {"origin": "https://welderen.teecontrol.com", "course_name": "Welderen", "booking_url": "https://welderen.teecontrol.com/book"},
    {"origin": "https://prise-deau.teecontrol.com", "course_name": "Prise d'Eau", "booking_url": "https://prise-deau.teecontrol.com/book"},
    {"origin": "https://golfbaantespelduyn.teecontrol.com", "course_name": "Tespelduyn", "booking_url": "https://golfbaantespelduyn.teecontrol.com/book"},
    {"origin": "https://egcp.teecontrol.com", "course_name": "Edese", "booking_url": "https://egcp.teecontrol.com/book"},
    {"origin": "https://gcdecompagnie.teecontrol.com", "course_name": "De Compagnie", "booking_url": "https://gcdecompagnie.teecontrol.com/book"},
]

API_BASE = "https://api.teecontrol.com"

# The app distinguishes two course types: "championship" (has par-5 holes) and "par 3/4" (no par-5 holes).
# The teecontrol API provides is_par_three per sub-course, but that flag means every hole is par 3 —
# it does NOT cover par 3/4 courses (mix of par 3 and par 4, no par 5). Those require explicit overrides.
#
# SHORT_COURSES: sub-courses verified to have no par-5 holes (par 3 or par 3/4).
# Add to this set when a sub-course should be treated as "par 3/4" but is_par_three is False.
#
# To find the exact name to add: query GET https://api.teecontrol.com/sets?can_book_at=<date>
# with a guest token (Origin: https://<club>.teecontrol.com). The name to use is everything
# after " | " in the "name" field (or the full name if no " | " is present).
#
# Note: there is no public Dutch course database with per-hole par data. The NGF has one
# internally but it requires an affiliated software supplier agreement to access.
SHORT_COURSES = {
    # Spaarnwoude: verified par 3/4 sub-courses (no par-5 holes on scorecard)
    "Abcoudebaan", "A-holes", "B-holes", "F-holes",
    # Liemeer: Bovenlandenbaan is par 3/4; is_par_three=False is correct, but still needs filtering
    "9 holes - par 3/4", "18 holes - par 3/4",
    # Welderen: par 3/4 course, is_par_three=False (note the double space in the 9-hole name)
    "Par 3-4  9 holes", "Par 3-4 18 holes",
    # Bentwoud: Noordwoud is par 3/4, is_par_three=False
    "Noordwoud (Par 3/4)", "Dagkaart Par 3/4 Noordwoud",
}


async def _get_token(origin: str) -> str:
    if origin in _token_cache:
        return _token_cache[origin]
    data = await _get(f"{API_BASE}/auth/guest", headers={"Origin": origin})
    token = data["token"]
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

    sets = await _get(
        f"{API_BASE}/sets",
        params={"can_book_at": date},
        headers=headers,
        cache_key=f"sets:{origin}:{date}",
    )

    filtered_sets = []
    for s in sets:
        if "footgolf" in s.get("name", "").lower():
            continue
        raw_name = _strip_season_prefix(s.get("name", ""))
        is_short = bool(s.get("is_par_three") or raw_name in SHORT_COURSES)
        if is_short and not include_par3:
            continue
        if not is_short and not include_championship:
            continue
        if holes is not None and s.get("holes_amount") != holes:
            continue
        s["_is_short"] = is_short
        filtered_sets.append(s)

    async def _fetch_set(s: dict) -> list[TeeTime]:
        items = await _get(
            f"{API_BASE}/start-times",
            params={
                "date": date,
                "slots": players,
                "set_uuid": s["uuid"],
                "with_players": 1,
                "with_unavailable": 0,
            },
            headers=headers,
            cache_key=f"st:{origin}:{date}:{players}:{s['uuid']}",
        )
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
                is_short=s.get("_is_short", False),
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
