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
            max_players = slot["sttMaxPlayers"]
            player_count = slot["playerCount"]
            free_slots = max_players - player_count
            if free_slots < players:
                continue

            # sttCrlNrNext != 0 means this slot can be booked as 18 holes
            # (play this course then continue to the linked next course)
            has_18h = slot.get("sttCrlNrNext", 0) != 0

            minutes = slot["sttTimeFrom"]
            local_dt = datetime(
                parsed_date.year, parsed_date.month, parsed_date.day,
                minutes // 60, minutes % 60,
                tzinfo=AMS,
            )
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
            time_str = f"{minutes // 60:02d}:{minutes % 60:02d}"

            def make_tt(h: int) -> TeeTime:
                raw_price = slot["greenFeePrice9"] if h == 9 else slot["greenFeePrice18"]
                return TeeTime(
                    course=club["course_name"],
                    sub_course=crl_name,
                    time=time_str,
                    timestamp=utc_dt,
                    holes=h,
                    free_slots=free_slots,
                    total_slots=max_players,
                    price_eur=float(raw_price) if raw_price else None,
                    is_available=True,
                    booking_url=club["booking_url"],
                )

            if holes is None or holes == 9:
                result.append(make_tt(9))
            if has_18h and (holes is None or holes == 18):
                result.append(make_tt(18))

    return result


async def fetch_tee_times(date: str, players: int, holes: int | None, include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    import asyncio
    results = await asyncio.gather(
        *[_fetch_club(club, date, players, holes, include_par3, include_championship) for club in CLUBS],
        return_exceptions=True,
    )
    return [tt for r in results if isinstance(r, list) for tt in r]
