import re
import asyncio
from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0)
AMS = ZoneInfo("Europe/Amsterdam")

PAGE_URL = "https://www.hollandschegolfclub.nl/boek-een-starttijd/"
AJAX_URL = "https://www.hollandschegolfclub.nl/wp-admin/admin-ajax.php"
BOOKING_URL = "https://www.hollandschegolfclub.nl/boek-een-starttijd/"

LOCATIONS = [
    {"id": 153, "name": "De Purmer"},
    {"id": 141, "name": "De Loonsche Duynen"},
]

_nonce_cache: dict = {}


async def _get_nonce() -> str:
    if "nonce" in _nonce_cache:
        return _nonce_cache["nonce"]
    resp = await _client.get(PAGE_URL)
    resp.raise_for_status()
    match = re.search(r'itgTeetimeConfig\s*=\s*\{[^}]*"nonce"\s*:\s*"([^"]+)"', resp.text)
    if not match:
        raise RuntimeError("Could not find ITG nonce on HGC page")
    nonce = match.group(1)
    _nonce_cache["nonce"] = nonce
    return nonce


def _parse_holes(course_name: str) -> int | None:
    name = course_name.lower()
    m = re.search(r'\((\d+)\s*-\s*(\d+)\)', name)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        return high - low + 1
    if "18" in name:
        return 18
    if "9" in name:
        return 9
    return None


async def _fetch_location(loc: dict, date: str, players: int, holes: int | None, include_par3: bool, include_championship: bool, nonce: str) -> list[TeeTime]:
    # When holes filter is unset, fetch both 9 and 18 hole products from the API
    holes_params = [9, 18] if holes is None else [holes]
    if not holes_params[0] in (9, 18):
        holes_params = [9, 18]

    import asyncio as _asyncio
    sub_results = await _asyncio.gather(
        *[_fetch_location_holes(loc, date, players, holes, include_par3, include_championship, nonce, hp) for hp in holes_params],
        return_exceptions=True,
    )
    return [tt for r in sub_results if isinstance(r, list) for tt in r]


async def _fetch_location_holes(loc: dict, date: str, players: int, holes: int | None, include_par3: bool, include_championship: bool, nonce: str, holes_param: int) -> list[TeeTime]:
    resp = await _client.post(AJAX_URL, data={
        "action": "itg_get_teetimes",
        "nonce": nonce,
        "date": date,
        "location_id": loc["id"],
        "holes": holes_param,
        "period": 1,
        "player_count": players,
    })
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return []

    parsed_date = date_type.fromisoformat(date)
    result = []

    for course in body["data"]["courses"]:
        crl_name = course["name"]
        is_short = "par 3" in crl_name.lower() or "par3" in crl_name.lower() or "short" in crl_name.lower()
        if is_short and not include_par3:
            continue
        if not is_short and not include_championship:
            continue

        slot_holes = _parse_holes(crl_name) or holes_param  # fallback to what we requested
        if holes is not None and slot_holes != holes:
            continue

        times = course["times"]
        if isinstance(times, dict):
            times = times.values()
        for slot in times:
            max_players = slot.get("_sttMaxPlayers", 4)
            booked = slot.get("_sttPlayers", 0)
            free_slots = max_players - booked
            if free_slots < players:
                continue

            minutes = slot["_sttTimeFrom"]
            local_dt = datetime(
                parsed_date.year, parsed_date.month, parsed_date.day,
                minutes // 60, minutes % 60,
                tzinfo=AMS,
            )
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

            result.append(TeeTime(
                course=loc["name"],
                sub_course=crl_name,
                time=f"{minutes // 60:02d}:{minutes % 60:02d}",
                timestamp=utc_dt,
                holes=slot_holes,
                free_slots=free_slots,
                total_slots=max_players,
                price_eur=None,
                is_available=True,
                booking_url=BOOKING_URL,
            ))

    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    try:
        nonce = await _get_nonce()
    except Exception:
        _nonce_cache.clear()
        raise
    results = await asyncio.gather(
        *[_fetch_location(loc, date, players, holes, include_par3, include_championship, nonce) for loc in LOCATIONS],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
