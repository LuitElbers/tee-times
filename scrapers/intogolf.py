from datetime import datetime, date as date_type
from zoneinfo import ZoneInfo
import httpx
from models import TeeTime

_client = httpx.AsyncClient(timeout=15.0)

AMS = ZoneInfo("Europe/Amsterdam")

CLUBS = [
    {
        "api_url": "https://wilnis.baan.intogolf.nl/api/igg",
        "course_name": "Wilnis",
        "booking_url": "https://wilnis.golfer.intogolf.nl/#/teetimes",
    },
    {
        "api_url": "https://zaanse.baan.intogolf.nl/api/igg",
        "course_name": "Zaanse",
        "booking_url": "https://zaanse.golfer.intogolf.nl/#/teetimes",
    },
]


def _is_par3_course(name: str) -> bool:
    return "par 3" in name.lower() or "par3" in name.lower()


async def _fetch_club(club: dict, date: str, players: int, holes: int | None, include_par3: bool, include_championship: bool) -> list[TeeTime]:
    resp = await _client.get(club["api_url"], params={"date": date})
    resp.raise_for_status()
    payload = resp.json()["payload"]

    parsed_date = date_type.fromisoformat(date)
    result = []

    for course in payload:
        crl_name = course["crlName"]
        if "footgolf" in crl_name.lower():
            continue
        is_short = _is_par3_course(crl_name)
        if is_short and not include_par3:
            continue
        if not is_short and not include_championship:
            continue

        for slot in course["times"]:
            slot_holes = slot["hole"]
            if holes is not None and slot_holes != holes:
                continue

            max_players = slot["sttMaxPlayers"]
            player_count = slot["playerCount"]
            free_slots = max_players - player_count
            if free_slots < players:
                continue

            minutes = slot["sttTimeFrom"]
            local_dt = datetime(
                parsed_date.year, parsed_date.month, parsed_date.day,
                minutes // 60, minutes % 60,
                tzinfo=AMS,
            )
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

            raw_price = slot["greenFeePrice9"] if slot_holes == 9 else slot["greenFeePrice18"]
            price_eur = float(raw_price) if raw_price else None

            result.append(TeeTime(
                course=club["course_name"],
                sub_course=crl_name,
                time=f"{minutes // 60:02d}:{minutes % 60:02d}",
                timestamp=utc_dt,
                holes=slot_holes,
                free_slots=free_slots,
                total_slots=max_players,
                price_eur=price_eur,
                is_available=True,
                booking_url=club["booking_url"],
            ))

    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    import asyncio
    results = await asyncio.gather(
        *[_fetch_club(club, date, players, holes, include_par3, include_championship) for club in CLUBS],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
