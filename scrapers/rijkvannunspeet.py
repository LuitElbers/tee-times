import re
import asyncio
from datetime import datetime, date as date_type
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
AMS = ZoneInfo("Europe/Amsterdam")

SITES = [
    {
        "sitecode": "RvNu",
        "display": "Rijk van Nunspeet",
        "site_id": "5",
        "site_name": "Het Rijk van Nunspeet",
        "courses": [
            {"id": "4", "name": "Nunspeet Noord", "guid": "51a11769-e795-4993-b4cb-512fed18d484", "par3": False},
            {"id": "5", "name": "Nunspeet Oost", "guid": "d76a62e5-b75e-4684-93e5-9b629dcb1799", "par3": False},
            {"id": "6", "name": "Nunspeet Zuid", "guid": "c93d4655-0586-4041-a16e-613e564201ad", "par3": False},
        ],
    },
    {
        "sitecode": "RvN",
        "display": "Rijk van Nijmegen",
        "site_id": "2",
        "site_name": "Het Rijk van Nijmegen",
        "courses": [
            {"id": "12", "name": "Nieuwe Baan 1-9", "guid": "2df7b711-0e0d-42a0-85e9-f3b75103d63f", "par3": False},
            {"id": "34", "name": "Nieuwe Baan 1-9 V", "guid": "6ac39d12-fc88-49fc-aac0-ee790be806b6", "par3": False},
            {"id": "13", "name": "Nieuwe Baan 10-18", "guid": "7d08aecc-40eb-4f33-a5e8-8836120a7197", "par3": False},
            {"id": "35", "name": "Nieuwe Baan 10-18 V", "guid": "6404cfa0-f506-473a-b221-f9ba8ed06e17", "par3": False},
            {"id": "25", "name": "Groesbeek Noord", "guid": "edf074c6-45c7-4522-aa04-ae127b32696c", "par3": False},
            {"id": "31", "name": "Groesbeek Noord V", "guid": "917e447b-0f9e-412d-8cd6-9402dcee5e07", "par3": False},
            {"id": "26", "name": "Groesbeek Oost", "guid": "6b3295dc-7074-4772-b625-4b6980230228", "par3": False},
            {"id": "32", "name": "Groesbeek Oost V", "guid": "9fa6d516-4c09-4863-89c3-465c4bc6a166", "par3": False},
            {"id": "27", "name": "Groesbeek Zuid", "guid": "d5285b95-21c9-476e-b134-d486af6b66c1", "par3": False},
            {"id": "33", "name": "Groesbeek Zuid V", "guid": "78fa7176-69da-44d9-9943-d3b698f22fb6", "par3": False},
        ],
    },
    {
        "sitecode": "RvS",
        "display": "Rijk van Sybrook",
        "site_id": "4",
        "site_name": "Het Rijk van Sybrook",
        "courses": [
            {"id": "7", "name": "Sybrook Noord", "guid": "84c510c4-5c6d-4de3-b426-d56e2a0c39c3", "par3": False},
            {"id": "9", "name": "Sybrook Zuid", "guid": "0bf16953-684a-43be-afb0-32ac6e5d8a61", "par3": False},
            {"id": "8", "name": "Sybrook Oost", "guid": "1e02c4db-1786-4025-9402-6beffbcc87d2", "par3": False},
        ],
    },
    {
        "sitecode": "RvM",
        "display": "Rijk van Margraten",
        "site_id": "3",
        "site_name": "Het Rijk van Margraten",
        "courses": [
            {"id": "2", "name": "Margraten 1", "guid": "8ea21f36-e004-437e-a288-ab28590c0661", "par3": False},
            {"id": "3", "name": "Margraten 10", "guid": "9f9b10d1-6751-453e-8a63-c2feb8251de7", "par3": False},
        ],
    },
]


async def _fetch_site(site: dict, date: str, parsed_date: date_type, date_str: str, players: int, holes: int | None, include_par3: bool, include_championship: bool) -> list[TeeTime]:
    base_url = f"https://reserveren.hetrijkgolfbanen.nl/OnlineRes/{site['sitecode']}/Home/WidgetView/?Option=bezoekers"

    resp = await _client.get(base_url)
    resp.raise_for_status()
    session_url = str(resp.url)
    post_url = re.sub(r"/Home/WidgetView.*", "/Home/WidgetView/nl", session_url)

    data: list[tuple[str, str]] = [
        ("Option", "0"),
        ("OptionForSpecialRow", "Search"),
        ("SelectedTeeSheetId", "0"),
        ("FromDateString", ""),
        ("FromDate", date_str),
        ("TabbedViewStartTime", "AnyTime"),
    ]
    for c in site["courses"]:
        data.append(("SelectedCourses", c["id"]))
    data += [
        ("PlayerNumber", str(players)),
        ("MinimumPlayer", "1"),
        ("MaximumPlayer", "4"),
        ("DefaultNumberOfPlayer", "99"),
        ("DefaultHole", "SearchAny"),
    ]
    for i, c in enumerate(site["courses"]):
        cd = {
            "CourseName": c["name"],
            "SiteId": site["site_id"],
            "SiteName": site["site_name"],
            "CourseId": c["id"],
            "CourseGUID": c["guid"],
            "Selected": "True",
        }
        for key, val in cd.items():
            data.append((f"Courses[{i}].{key}", val))

    resp = await _client.post(
        post_url,
        content=urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    name_by_id = {int(c["id"]): c["name"] for c in site["courses"]}
    par3_by_id = {int(c["id"]): c["par3"] for c in site["courses"]}
    booking_url = base_url

    result = []
    for slot_div in soup.select("div[data-teesheetid]"):
        time_str = slot_div.get("teetime", "")
        if not time_str or ":" not in time_str:
            continue

        course_id = int(slot_div.get("courseid", 0))
        sub_course = name_by_id.get(course_id, "")
        is_par3 = par3_by_id.get(course_id, False)
        if is_par3 and not include_par3:
            continue
        if not is_par3 and not include_championship:
            continue

        player_p = slot_div.select_one(".player p")
        free_slots = 4
        if player_p:
            m = re.search(r"(\d+)\s+tot\s+(\d+)", player_p.text)
            if m:
                free_slots = int(m.group(2))
        if free_slots < players:
            continue

        hole_div = slot_div.select_one(".hole-icon div")
        slot_holes = int(hole_div.text.strip()) if hole_div and hole_div.text.strip().isdigit() else 18
        if holes is not None and slot_holes != holes:
            continue

        h, mn = int(time_str[:2]), int(time_str[3:])
        local_dt = datetime(parsed_date.year, parsed_date.month, parsed_date.day, h, mn, tzinfo=AMS)
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        result.append(TeeTime(
            course=site["display"],
            sub_course=sub_course,
            time=time_str,
            timestamp=utc_dt,
            holes=slot_holes,
            free_slots=free_slots,
            total_slots=4,
            price_eur=None,
            is_available=True,
            booking_url=booking_url,
        ))

    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    parsed_date = date_type.fromisoformat(date)
    date_str = parsed_date.strftime("%d-%m-%Y")

    results = await asyncio.gather(*[
        _fetch_site(site, date, parsed_date, date_str, players, holes, include_par3, include_championship)
        for site in SITES
    ])
    return [t for sub in results for t in sub]
