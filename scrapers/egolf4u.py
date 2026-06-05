import re
import asyncio
from datetime import datetime, date as date_type, timezone
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
AMS = ZoneInfo("Europe/Amsterdam")

COURSES = [
    {"subdomain": "heemskerkse", "name": "Heemskerk"},
    {"subdomain": "dehaenen", "name": "Haenen"},
]


async def _fetch_course(course: dict, date: str, players: int, holes: int | None, include_par3: bool, include_championship: bool) -> list[TeeTime]:
    parsed_date = date_type.fromisoformat(date)
    url = f"https://{course['subdomain']}.teetime.e-golf4u.nl/app/booking/teetime"
    resp = await _client.get(url, params={"date": date})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    booking_url = url
    result = []

    for grid in soup.select("div.teetime-grid"):
        baan = grid.get("data-baan", "1")
        sub_course = f"Baan {baan}"

        for slot_div in grid.select("div.btn.teetime"):
            if "niet-beschikbaar" in (slot_div.get("class") or []):
                continue

            vrij = len(slot_div.select("span.icon.vrij"))
            bezet = len(slot_div.select("span.icon.bezet"))
            total_slots = vrij + bezet
            if total_slots == 0:
                total_slots = 4

            # Prefer title attr for free count, fall back to icon count
            title = slot_div.get("title", "")
            m = re.search(r"(\d+)\s+beschikbare", title)
            free_slots = int(m.group(1)) if m else vrij
            if free_slots < players:
                continue

            # Prefer data-time (unix) for timestamp, fall back to span.time + date
            data_time = slot_div.get("data-time")
            if data_time:
                ts = datetime.fromtimestamp(int(data_time), tz=timezone.utc)
                time_str = ts.astimezone(AMS).strftime("%H:%M")
            else:
                time_span = slot_div.select_one("span.time")
                if not time_span:
                    continue
                time_str = time_span.text.strip()
                h, mn = int(time_str[:2]), int(time_str[3:])
                local_dt = datetime(parsed_date.year, parsed_date.month, parsed_date.day, h, mn, tzinfo=AMS)
                ts = local_dt.astimezone(ZoneInfo("UTC"))

            result.append(TeeTime(
                course=course["name"],
                sub_course=sub_course,
                time=time_str,
                timestamp=ts,
                holes=18,
                free_slots=free_slots,
                total_slots=total_slots,
                price_eur=None,
                is_available=True,
                booking_url=booking_url,
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
