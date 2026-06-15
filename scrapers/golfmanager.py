from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0)

COURSES = [
    {
        "base_url": "https://eu.golfmanager.com/golfwaterland",
        "area": 2,
        "course_name": "Waterland",
        "is_par3": False,
        "booking_url": "https://eu.golfmanager.com/golfwaterland/consumer/book?area=2",
    },
]


def _parse_holes(name: str) -> int | None:
    n = name.lower()
    if "9 hole" in n:
        return 9
    if "18 hole" in n:
        return 18
    return None


def items_to_teetimes(course: dict, items: list, players: int = 1, holes: int | None = None) -> list[TeeTime]:
    seen = set()
    result = []
    for item in items:
        slot_holes = _parse_holes(item.get("name", ""))
        if slot_holes is None:
            continue
        if holes is not None and slot_holes != holes:
            continue

        free_slots = item.get("slots", 0)
        if free_slots < players:
            continue

        start_str = item["start"]
        dt = datetime.fromisoformat(start_str)
        resource_name = item.get("resourceName", "")
        key = (start_str, resource_name, slot_holes)
        if key in seen:
            continue
        seen.add(key)

        result.append(TeeTime(
            course=course["course_name"],
            sub_course=resource_name,
            time=dt.strftime("%H:%M"),
            timestamp=dt.astimezone(ZoneInfo("UTC")),
            holes=slot_holes,
            free_slots=free_slots,
            total_slots=4,
            price_eur=item.get("price"),
            is_available=True,
            booking_url=course["booking_url"],
        ))

    return result


async def _fetch_course(course: dict, date: str, players: int, holes: int | None, include_par3: bool, include_championship: bool) -> list[TeeTime]:
    if course["is_par3"] and not include_par3:
        return []
    if not course["is_par3"] and not include_championship:
        return []
    url = f"{course['base_url']}/consumer/availability.json"
    resp = await _client.get(url, params={"date": f"{date}T00:00", "area": course["area"]})
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items_to_teetimes(course, items, players, holes)


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    import asyncio
    results = await asyncio.gather(
        *[_fetch_course(c, date, players, holes, include_par3, include_championship) for c in COURSES],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
