import asyncio
from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
AMS = ZoneInfo("Europe/Amsterdam")

# Each "baan" is a bookable course variant from the e-golf4u baan dropdown.
# baan id, holes and par-3 flag come from the site's own labels (authoritative).
COURSES = [
    {
        "subdomain": "dehaenen",
        "name": "Haenen",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
            {"baan": 4, "sub": "Par 3", "holes": 9, "is_par3": True},
        ],
    },
    {
        "subdomain": "heemskerkse",
        "name": "Heemskerk",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 7, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 8, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
            {"baan": 2, "sub": "Par 3 18 holes AB", "holes": 18, "is_par3": True},
            {"baan": 6, "sub": "Par 3 9 holes A", "holes": 9, "is_par3": True},
            {"baan": 12, "sub": "Par 3 9 holes B", "holes": 9, "is_par3": True},
            {"baan": 14, "sub": "Par 3 18 holes BA", "holes": 18, "is_par3": True},
        ],
    },
]


async def _fetch_baan(course: dict, baan: dict, date: str, players: int) -> list[TeeTime]:
    parsed = date_type.fromisoformat(date)
    datum = parsed.strftime("%d-%m-%Y")
    url = f"https://{course['subdomain']}.teetime.e-golf4u.nl/app/booking/teetime"
    params = {"baan": baan["baan"], "datum": datum, "holes": baan["holes"], "tijd": "", "view": "grid"}
    resp = await _client.get(url, params=params)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = []
    for slot_div in soup.select("div.teetime-grid div.btn.teetime"):
        if "niet-beschikbaar" in (slot_div.get("class") or []):
            continue

        vrij = len(slot_div.select("span.icon.vrij"))
        bezet = len(slot_div.select("span.icon.bezet"))
        total_slots = vrij + bezet or 4
        free_slots = vrij
        if free_slots < players:
            continue

        time_span = slot_div.select_one("span.time")
        if not time_span:
            continue
        time_str = time_span.get_text(strip=True)
        h, mn = int(time_str[:2]), int(time_str[3:5])
        local_dt = datetime(parsed.year, parsed.month, parsed.day, h, mn, tzinfo=AMS)

        result.append(TeeTime(
            course=course["name"],
            sub_course=baan["sub"],
            time=time_str,
            timestamp=local_dt.astimezone(ZoneInfo("UTC")),
            holes=baan["holes"],
            free_slots=free_slots,
            total_slots=total_slots,
            price_eur=None,
            is_available=True,
            booking_url=f"{url}?baan={baan['baan']}&datum={datum}&holes={baan['holes']}&view=grid",
        ))

    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    tasks = []
    for course in COURSES:
        for baan in course["baans"]:
            if baan["is_par3"] and not include_par3:
                continue
            if not baan["is_par3"] and not include_championship:
                continue
            if holes in (9, 18) and baan["holes"] != holes:
                continue
            tasks.append(_fetch_baan(course, baan, date, players))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [tt for r in results if isinstance(r, list) for tt in r]
