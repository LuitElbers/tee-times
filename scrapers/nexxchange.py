import re
import asyncio
from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

_HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
AMS = ZoneInfo("Europe/Amsterdam")

COURSES = [
    {"slug": "golf-amsteldijk", "name": "Amsteldijk", "is_par3": False, "holes": [9, 18]},
    {"slug": "golf-countryclub-heiloo", "name": "Heiloo", "is_par3": False, "holes": [9, 18]},
    {"slug": "kavel-2-beemster", "name": "Kavel II Beemster", "is_par3": False, "holes": [9, 18]},
    {"slug": "domburgsche-golfclub", "name": "Domburgsche", "is_par3": False, "holes": [9, 18]},
    {"slug": "openbare-golfclub-dronten", "name": "Openbare Golfclub Dronten", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfclub-putten", "name": "Putten", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfclub-anderstein", "name": "Anderstein", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfclub-flevoland", "name": "Flevoland", "is_par3": False, "holes": [9, 18]},
    {"slug": "golf-club-havelte", "name": "Havelte", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfpark-soestduinen", "name": "Soestduinen", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfpark-de-bonte-bij", "name": "De Bonte Bij", "is_par3": False, "holes": [9]},
    {"slug": "golfbaan-de-lage-mors", "name": "De Lage Mors", "is_par3": False, "holes": [9, 18]},
    {"slug": "eyckenduyn", "name": "Eyckenduyn", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfclub-gaasterland", "name": "Gaasterland", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfclub-holthuizen", "name": "Holthuizen", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfparc-sandur", "name": "Sandur", "is_par3": False, "holes": [9, 18]},
    {"slug": "golfpark-exloo", "name": "Exloo", "is_par3": False, "holes": [9, 18]},
]


def _parse_price(text: str) -> float | None:
    m = re.search(r"(\d+)[,.](\d{2})", text.replace("\xa0", ""))
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    return None


def _facet_map(soup: BeautifulSoup) -> dict[int, int]:
    out: dict[int, int] = {}
    for a in soup.select("#facet-name-list a"):
        m = re.search(r"facetId=(\d+)", a.get("href", ""))
        if not m:
            continue
        label = a.select_one(".facet-name")
        if not label:
            continue
        n = re.match(r"\s*(\d+)", label.get_text(strip=True))
        if n:
            out[int(n.group(1))] = int(m.group(1))
    return out


def _parse_sections(soup: BeautifulSoup, course: dict, holes: int, players: int, parsed_date: date_type) -> dict[str, TeeTime]:
    booking_url = f"https://www.nexxchange.com/search/teetimes/{course['slug']}"
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
            holes=holes,
            free_slots=free,
            total_slots=total,
            price_eur=price_eur,
            is_available=True,
            booking_url=booking_url,
        )
        if time_str not in seen or free > seen[time_str].free_slots:
            seen[time_str] = tt
    return seen


async def _fetch_course(course: dict, date: str, players: int, holes: int | None) -> list[TeeTime]:
    wanted = [h for h in course["holes"] if holes is None or h == holes]
    if not wanted:
        return []

    parsed_date = date_type.fromisoformat(date)
    date_str = f"{parsed_date.day}.{parsed_date.month}.{parsed_date.year}"

    grid_url = f"https://www.nexxchange.com/search/teetimes/{course['slug']}"
    url = f"https://www.nexxchange.com/search/optimized-teetimes/content/{course['slug']}"
    hx = {"hx-request": "true", "hx-current-url": grid_url, "referer": grid_url}

    out: list[TeeTime] = []
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=_HEADERS) as client:
        await client.get(grid_url)

        resp = await client.get(url, params={"courseId": 1, "date": date_str}, headers=hx)
        resp.raise_for_status()
        facet_ids = _facet_map(BeautifulSoup(resp.text, "html.parser"))

        for h in wanted:
            facet_id = facet_ids.get(h)
            if facet_id is None:
                continue
            r = await client.get(url, params={"courseId": 1, "date": date_str, "facetId": facet_id}, headers=hx)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            out.extend(_parse_sections(soup, course, h, players, parsed_date).values())
    return out


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    sem = asyncio.Semaphore(3)

    async def guarded(course: dict) -> list[TeeTime]:
        async with sem:
            return await _fetch_course(course, date, players, holes)

    tasks = [
        guarded(course)
        for course in COURSES
        if (course["is_par3"] and include_par3) or (not course["is_par3"] and include_championship)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [tt for r in results if isinstance(r, list) for tt in r]
