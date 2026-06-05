import re
import asyncio
from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0)
AMS = ZoneInfo("Europe/Amsterdam")

COURSES = [
    {
        "slug": "golf-amsteldijk",
        "name": "Amsteldijk",
        "booking_url": "https://www.nexxchange.com/search/teetimes/golf-amsteldijk?sortIndex=1",
    },
]


async def _fetch_course(course: dict, date: str, players: int, holes: int | None, include_par3: bool, include_championship: bool) -> list[TeeTime]:
    parsed_date = date_type.fromisoformat(date)
    date_str = f"{parsed_date.day}.{parsed_date.month}.{parsed_date.year}"

    url = f"https://www.nexxchange.com/search/optimized-teetimes/content/{course['slug']}"
    resp = await _client.get(url, params={"sortIndex": 1, "courseId": 1, "date": date_str})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = []
    for section in soup.find_all(id=re.compile(r"^tt-\d{4}$")):
        tt_id = section["id"]
        time_str = f"{tt_id[3:5]}:{tt_id[5:7]}"

        booked = len(section.select(".player-box.booked"))
        free = len(section.select(".player-box.none"))
        total = booked + free
        if total == 0 or free < players:
            continue

        local_dt = datetime(
            parsed_date.year, parsed_date.month, parsed_date.day,
            int(time_str[:2]), int(time_str[3:]),
            tzinfo=AMS,
        )
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        result.append(TeeTime(
            course=course["name"],
            sub_course="",
            time=time_str,
            timestamp=utc_dt,
            holes=18,
            free_slots=free,
            total_slots=total,
            price_eur=None,
            is_available=True,
            booking_url=course["booking_url"],
        ))

    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    if holes == 9:
        return []
    results = await asyncio.gather(
        *[_fetch_course(c, date, players, holes, include_par3, include_championship) for c in COURSES],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
