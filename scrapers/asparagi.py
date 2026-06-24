import re
import asyncio
from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

# ikgagolfen / Asparagi shared NGF portal. The public greenfee grid is served by
# a classic ASP form: GET the page (per-club via exclusiveCrsNr) to obtain a
# session action URL + hidden fields, then POST playdate/flightsize/_mbr as
# multipart to get that date's grid. Availability is filtered server-side by
# flightsize, so a returned cell means the requested party size fits.
# Cert chain is incomplete on some hosts -> verify disabled (matches egolf4u).
_client = httpx.AsyncClient(timeout=20.0, follow_redirects=True, verify=False,
                            headers={"User-Agent": "Mozilla/5.0"})
AMS = ZoneInfo("Europe/Amsterdam")
PORTAL = "https://www.ikgagolfen.nl/asparagi/ikgagolfen/site2/teetimes/teetimes.asp"

COURSES = [
    {"crs": 908, "name": "Ockenburgh", "is_par3": True},
    {"crs": 71, "name": "Capelle", "is_par3": False},
    {"crs": 952, "name": "Concordia", "is_par3": True},
    {"crs": 58, "name": "De Turfvaert", "is_par3": False},
    {"crs": 915, "name": "Hoenshuis", "is_par3": False},
    {"crs": 958, "name": "Twentse Golfpark", "is_par3": False},
]


def _allowed_holes(token: str) -> set[int]:
    # token examples: "9h", "18h", "9/18h"
    return {int(n) for n in re.findall(r"\d+", token)}


async def _fetch_course(course: dict, date: str, players: int, holes: int | None) -> list[TeeTime]:
    parsed = date_type.fromisoformat(date)
    playdate = parsed.strftime("%d/%m/%Y")
    booking_url = f"{PORTAL}?exclusiveCrsNr={course['crs']}"

    page = await _client.get(booking_url)
    form = BeautifulSoup(page.text, "html.parser").find("form", {"name": "sel"})
    if form is None:
        return []

    data = {i["name"]: i.get("value", "") for i in form.find_all("input") if i.get("name")}
    data["playdate"] = playdate
    data["flightsize"] = str(max(1, min(players, 4)))
    data["_mbr"] = "0"

    action = form["action"]
    post_url = "https://www2.ikgagolfen.nl" + action if action.startswith("/") else action
    resp = await _client.post(
        post_url,
        files={k: (None, v) for k, v in data.items()},
        headers={"Referer": str(page.url)},
    )
    soup = BeautifulSoup(resp.text, "html.parser")

    result = []
    for cell in soup.find_all("td", class_=re.compile(r"tt_avh?$")):
        text = cell.get_text(" ", strip=True)
        m = re.match(r"(\d{2}):(\d{2})\s*(\S+)?", text)
        if not m:
            continue
        time_str = f"{m.group(1)}:{m.group(2)}"
        allowed = _allowed_holes(m.group(3) or "")
        if holes is not None:
            if holes not in allowed:
                continue
            slot_holes = holes
        else:
            slot_holes = 18 if 18 in allowed else (9 if allowed else 18)

        local_dt = datetime(parsed.year, parsed.month, parsed.day, int(m.group(1)), int(m.group(2)), tzinfo=AMS)
        result.append(TeeTime(
            course=course["name"],
            sub_course="",
            time=time_str,
            timestamp=local_dt.astimezone(ZoneInfo("UTC")),
            holes=slot_holes,
            free_slots=max(1, min(players, 4)),
            total_slots=4,
            price_eur=None,
            is_available=True,
            booking_url=booking_url,
            is_short=course["is_par3"],
        ))
    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    tasks = [
        _fetch_course(c, date, players, holes)
        for c in COURSES
        if (c["is_par3"] and include_par3) or (not c["is_par3"] and include_championship)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [tt for r in results if isinstance(r, list) for tt in r]
