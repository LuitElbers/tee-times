import asyncio
from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
_client_noverify = httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False)
AMS = ZoneInfo("Europe/Amsterdam")

# Each "baan" is a bookable course variant from the e-golf4u baan dropdown.
# baan id, holes and par-3 flag come from the site's own labels (authoritative).
COURSES = [
    {
        "host": "dehaenen.teetime.e-golf4u.nl",
        "name": "Haenen",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
            {"baan": 4, "sub": "Par 3", "holes": 9, "is_par3": True},
        ],
    },
    {
        "host": "heemskerkse.teetime.e-golf4u.nl",
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
    {
        "host": "teetime.texelse.nl",
        "name": "De Texelse",
        "noverify": True,
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
            {"baan": 4, "sub": "Par 3", "holes": 9, "is_par3": True},
            {"baan": 6, "sub": "Par 3 18 holes", "holes": 18, "is_par3": True},
        ],
    },
    {
        "host": "regthuys.teetime.e-golf4u.nl",
        "name": "Regthuys",
        "baans": [
            {"baan": 1, "sub": "Dijklus - Tulpenlus", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "Dijklus", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "Tulpenlus", "holes": 9, "is_par3": False},
            {"baan": 6, "sub": "Tulpenlus - Dijklus", "holes": 18, "is_par3": False},
            {"baan": 4, "sub": "Par 3", "holes": 9, "is_par3": True},
            {"baan": 21, "sub": "Par 3 18 holes", "holes": 18, "is_par3": True},
        ],
    },
    {
        "host": "westwoud.teetime.e-golf4u.nl",
        "name": "Westfriese",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "aoc.teetime.e-golf4u.nl",
        "name": "Amsterdam Old Course",
        "baans": [
            {"baan": 26, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 20, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "broekpolder.teetime.e-golf4u.nl",
        "name": "Broekpolder",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 3, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 4, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "woestekop.teetime.e-golf4u.nl",
        "name": "De Woeste Kop",
        "baans": [
            {"baan": 1, "sub": "Start hole 1", "holes": 18, "is_par3": False},
            {"baan": 3, "sub": "Watertoren", "holes": 9, "is_par3": False},
            {"baan": 6, "sub": "Grote Kreek", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "krommerijn.teetime.e-golf4u.nl",
        "name": "Kromme Rijn",
        "baans": [
            {"baan": 8, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 3, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "schaerweijde.teetime.e-golf4u.nl",
        "name": "Schaerweijde",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 7, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "wouwse.teetime.e-golf4u.nl",
        "name": "Wouwse Plantage",
        "baans": [
            {"baan": 27, "sub": "18 holes Bleekloop/Plantage", "holes": 18, "is_par3": False},
            {"baan": 72, "sub": "18 holes Plantage/Bleekloop", "holes": 18, "is_par3": False},
            {"baan": 30, "sub": "9 holes De Bleekloop", "holes": 9, "is_par3": False},
            {"baan": 33, "sub": "9 holes De Plantage", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "princenbosch.teetime.e-golf4u.nl",
        "name": "Princenbosch",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
        ],
    },
    {
        "host": "boisleduc.teetime.e-golf4u.nl",
        "name": "Parc de Pettelaar",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "swinkelsche.teetime.e-golf4u.nl",
        "name": "De Swinkelsche",
        "baans": [
            {"baan": 1, "sub": "Championship Course 18 holes", "holes": 18, "is_par3": False},
            {"baan": 6, "sub": "Championship Course 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "teetime.golfclubvught.nl",
        "name": "Vught",
        "baans": [
            {"baan": 23, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 18, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "teetime.gcdedommel.nl",
        "name": "De Dommel",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "overbrug.teetime.e-golf4u.nl",
        "name": "Overbrug",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "9 holes", "holes": 9, "is_par3": False},
            {"baan": 5, "sub": "2e 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "riel.teetime.e-golf4u.nl",
        "name": "Riel",
        "baans": [
            {"baan": 6, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 1, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "oosterhoutse.teetime.e-golf4u.nl",
        "name": "De Oosterhoutse",
        "baans": [
            {"baan": 15, "sub": "18 holes Start Tee 1", "holes": 18, "is_par3": False},
            {"baan": 17, "sub": "18 holes Start Tee 10", "holes": 18, "is_par3": False},
            {"baan": 20, "sub": "9 holes Start Tee 1", "holes": 9, "is_par3": False},
            {"baan": 23, "sub": "9 holes Start Tee 10", "holes": 9, "is_par3": False},
            {"baan": 26, "sub": "Academy 9 holes", "holes": 9, "is_par3": True},
            {"baan": 29, "sub": "Academy 18 holes", "holes": 18, "is_par3": True},
        ],
    },
    {
        "host": "teetime.golfbaan-stippelberg.com",
        "name": "Stippelberg",
        "baans": [
            {"baan": 1, "sub": "Championship Course 18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "CC 1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 3, "sub": "CC 2de 9 holes", "holes": 9, "is_par3": False},
            {"baan": 4, "sub": "Eagle Course 18 holes", "holes": 18, "is_par3": False},
            {"baan": 9, "sub": "Eagle Course 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "golfhorst.teetime.e-golf4u.nl",
        "name": "De Golfhorst",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 2, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "haviksoord.teetime.e-golf4u.nl",
        "name": "Haviksoord",
        "baans": [
            {"baan": 1, "sub": "Championship Course", "holes": 18, "is_par3": False},
        ],
    },
    {
        "host": "zwolle.teetime.e-golf4u.nl",
        "name": "Zwolle",
        "baans": [
            {"baan": 1, "sub": "18 holes Boschwijk-Veldwijk", "holes": 18, "is_par3": False},
            {"baan": 6, "sub": "Boschwijk 9 holes", "holes": 9, "is_par3": False},
            {"baan": 7, "sub": "Veldwijk 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "dekoepel.teetime.e-golf4u.nl",
        "name": "De Koepel",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 1, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "rosendaelsche.teetime.e-golf4u.nl",
        "name": "Rosendaelsche",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 6, "sub": "1ste 9 holes", "holes": 9, "is_par3": False},
            {"baan": 7, "sub": "2de 9 holes", "holes": 9, "is_par3": False},
        ],
    },
    {
        "host": "dorpswaard.teetime.e-golf4u.nl",
        "name": "De Dorpswaard",
        "baans": [
            {"baan": 1, "sub": "18 holes", "holes": 18, "is_par3": False},
            {"baan": 6, "sub": "9 holes", "holes": 9, "is_par3": False},
        ],
    },
]


async def _fetch_baan(course: dict, baan: dict, date: str, players: int) -> list[TeeTime]:
    parsed = date_type.fromisoformat(date)
    datum = parsed.strftime("%d-%m-%Y")
    url = f"https://{course['host']}/app/booking/teetime"
    params = {"baan": baan["baan"], "datum": datum, "holes": baan["holes"], "tijd": "", "view": "grid"}
    client = _client_noverify if course.get("noverify") else _client
    resp = await client.get(url, params=params)
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
