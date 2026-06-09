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

BASE_URL = "https://reserveren.hetrijkgolfbanen.nl/OnlineRes/RvNu/Home/WidgetView/?Option=bezoekers"
BOOKING_URL = "https://reserveren.hetrijkgolfbanen.nl/OnlineRes/RvNu/Home/WidgetView/?Option=bezoekers"

COURSE_NAMES = {4: "Nunspeet Noord", 5: "Nunspeet Oost", 6: "Nunspeet Zuid"}
COURSE_IS_PAR3 = {4: False, 5: False, 6: False}

COURSE_DATA = [
    {"CourseName": "Nunspeet Noord ", "SiteId": "5", "SiteName": "Het Rijk van Nunspeet", "CourseId": "4", "CourseGUID": "51a11769-e795-4993-b4cb-512fed18d484", "SiteStreet1": "Plesmanlaan 30", "SiteStreet2": "info@golfbaanhetrijkvannunspeet.nl", "SiteCity": "Nunspeet", "SiteState": "Gelderland", "SitePostalCode": "8072PT", "SitePhone": "0341255255", "SiteFax": "0341255285", "Selected": "True"},
    {"CourseName": "Nunspeet Oost", "SiteId": "5", "SiteName": "Het Rijk van Nunspeet", "CourseId": "5", "CourseGUID": "d76a62e5-b75e-4684-93e5-9b629dcb1799", "SiteStreet1": "Plesmanlaan 30", "SiteStreet2": "info@golfbaanhetrijkvannunspeet.nl", "SiteCity": "Nunspeet", "SiteState": "Gelderland", "SitePostalCode": "8072PT", "SitePhone": "0341255255", "SiteFax": "0341255285", "Selected": "True"},
    {"CourseName": "Nunspeet Zuid", "SiteId": "5", "SiteName": "Het Rijk van Nunspeet", "CourseId": "6", "CourseGUID": "c93d4655-0586-4041-a16e-613e564201ad", "SiteStreet1": "Plesmanlaan 30", "SiteStreet2": "info@golfbaanhetrijkvannunspeet.nl", "SiteCity": "Nunspeet", "SiteState": "Gelderland", "SitePostalCode": "8072PT", "SitePhone": "0341255255", "SiteFax": "0341255285", "Selected": "True"},
]


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    parsed_date = date_type.fromisoformat(date)
    date_str = parsed_date.strftime("%d-%m-%Y")

    resp = await _client.get(BASE_URL)
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
        ("SelectedCourses", "4"),
        ("SelectedCourses", "5"),
        ("SelectedCourses", "6"),
        ("PlayerNumber", str(players)),
        ("MinimumPlayer", "1"),
        ("MaximumPlayer", "4"),
        ("DefaultNumberOfPlayer", "99"),
        ("DefaultHole", "SearchAny"),
    ]
    for i, cd in enumerate(COURSE_DATA):
        for key, val in cd.items():
            data.append((f"Courses[{i}].{key}", val))

    resp = await _client.post(
        post_url,
        content=urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = []
    for slot_div in soup.select("div[data-teesheetid]"):
        time_str = slot_div.get("teetime", "")
        if not time_str or ":" not in time_str:
            continue

        course_id = int(slot_div.get("courseid", 0))
        sub_course = COURSE_NAMES.get(course_id, "")
        is_par3 = COURSE_IS_PAR3.get(course_id, False)
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
            course="Rijk van Nunspeet",
            sub_course=sub_course,
            time=time_str,
            timestamp=utc_dt,
            holes=slot_holes,
            free_slots=free_slots,
            total_slots=4,
            price_eur=None,
            is_available=True,
            booking_url=BOOKING_URL,
        ))

    return result
