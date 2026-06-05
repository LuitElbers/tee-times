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
        "facets": [
            {"facet_id": 1, "holes": 9},
            {"facet_id": 2, "holes": 18},
        ],
    },
]


def _parse_price(text: str) -> float | None:
    m = re.search(r"(\d+)[,.](\d{2})", text.replace("\xa0", ""))
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    return None


async def _fetch_facet(course: dict, facet: dict, date: str, players: int, holes: int | None) -> list[TeeTime]:
    if holes is not None and holes != facet["holes"]:
        return []

    parsed_date = date_type.fromisoformat(date)
    date_str = f"{parsed_date.day}.{parsed_date.month}.{parsed_date.year}"

    url = f"https://www.nexxchange.com/search/optimized-teetimes/content/{course['slug']}"
    resp = await _client.get(url, params={"sortIndex": 1, "courseId": 1, "date": date_str, "facetId": facet["facet_id"]})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen: dict[str, TeeTime] = {}
    for section in soup.find_all(id=re.compile(r"^tt-\d{4}$")):
        tt_id = section["id"]
        time_str = f"{tt_id[3:5]}:{tt_id[5:7]}"

        booked = len(section.select(".player-box.booked"))
        free_boxes = section.select(".player-box.none")
        free = len(free_boxes)
        total = booked + free
        if total == 0 or free < players:
            continue

        price_eur = None
        for box in free_boxes:
            span = box.select_one("span")
            if span:
                price_eur = _parse_price(span.get_text())
                break

        local_dt = datetime(
            parsed_date.year, parsed_date.month, parsed_date.day,
            int(time_str[:2]), int(time_str[3:]),
            tzinfo=AMS,
        )
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        tt = TeeTime(
            course=course["name"],
            sub_course="",
            time=time_str,
            timestamp=utc_dt,
            holes=facet["holes"],
            free_slots=free,
            total_slots=total,
            price_eur=price_eur,
            is_available=True,
            booking_url=course["booking_url"],
        )
        if time_str not in seen or free > seen[time_str].free_slots:
            seen[time_str] = tt

    return list(seen.values())


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    tasks = [
        _fetch_facet(course, facet, date, players, holes)
        for course in COURSES
        for facet in course["facets"]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [tt for r in results if isinstance(r, list) for tt in r]
