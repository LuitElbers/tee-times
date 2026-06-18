import re
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
    {"api_url": "https://vlietlanden.baan.intogolf.nl/api/igg", "course_name": "De Vlietlanden", "booking_url": "https://vlietlanden.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://sluispolder.baan.intogolf.nl/api/igg", "course_name": "Sluispolder", "booking_url": "https://sluispolder.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://ooghduyne.baan.intogolf.nl/api/igg", "course_name": "Ooghduyne", "booking_url": "https://ooghduyne.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://rijswijkse.baan.intogolf.nl/api/igg", "course_name": "Rijswijkse", "booking_url": "https://rijswijkse.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://crayestein.baan.intogolf.nl/api/igg", "course_name": "Crayestein", "booking_url": "https://crayestein.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://duinzicht.baan.intogolf.nl/api/igg", "course_name": "Duinzicht", "booking_url": "https://duinzicht.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://leeuwenbergh.baan.intogolf.nl/api/igg", "course_name": "Leeuwenbergh", "booking_url": "https://leeuwenbergh.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://cromstrijen.baan.intogolf.nl/api/igg", "course_name": "Cromstrijen", "booking_url": "https://cromstrijen.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://goese.baan.intogolf.nl/api/igg", "course_name": "De Goese Golf", "booking_url": "https://goese.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://grevelingenhout.baan.intogolf.nl/api/igg", "course_name": "Grevelingenhout", "booking_url": "https://grevelingenhout.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://zeeuwsche.baan.intogolf.nl/api/igg", "course_name": "De Zeeuwsche", "booking_url": "https://zeeuwsche.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://kroonprins.baan.intogolf.nl/api/igg", "course_name": "De Kroonprins", "booking_url": "https://kroonprins.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://dronten.baan.intogolf.nl/api/igg", "course_name": "Golf Residentie Dronten", "booking_url": "https://dronten.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://delfland.baan.intogolf.nl/api/igg", "course_name": "Delfland", "booking_url": "https://www.delflandgolf.nl/reserveer-starttijd/reserveren-starttijd/"},
    {"api_url": "https://hattemse.baan.intogolf.nl/api/igg", "course_name": "De Hattemse", "booking_url": "https://hattemse.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://winterswijk.baan.intogolf.nl/api/igg", "course_name": "Winterswijk", "booking_url": "https://winterswijk.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://scherpenbergh.baan.intogolf.nl/api/igg", "course_name": "De Scherpenbergh", "booking_url": "https://scherpenbergh.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://engelenburg.baan.intogolf.nl/api/igg", "course_name": "Engelenburg", "booking_url": "https://engelenburg.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://batouwe.baan.intogolf.nl/api/igg", "course_name": "De Batouwe", "booking_url": "https://batouwe.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://keppelse.baan.intogolf.nl/api/igg", "course_name": "Keppelse", "booking_url": "https://keppelse.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://sallandsche.baan.intogolf.nl/api/igg", "course_name": "Sallandsche", "booking_url": "https://sallandsche.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://maasduinen.baan.intogolf.nl/api/igg", "course_name": "Maasduinen", "booking_url": "https://maasduinen.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://brunssummerheide.baan.intogolf.nl/api/igg", "course_name": "Brunssummerheide", "booking_url": "https://brunssummerheide.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://heidemeer.baan.intogolf.nl/api/igg", "course_name": "Heidemeer", "booking_url": "https://heidemeer.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://martensplek.baan.intogolf.nl/api/igg", "course_name": "Martensplek", "booking_url": "https://martensplek.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://semslanden.baan.intogolf.nl/api/igg", "course_name": "De Semslanden", "booking_url": "https://semslanden.golfer.intogolf.nl/#/teetimes"},
    {"api_url": "https://deherkenbosche.baan.intogolf.nl/api/igg", "course_name": "De Herkenbosche", "booking_url": "https://deherkenbosche.golfer.intogolf.nl/#/teetimes"},
]


def _parse_green_fee(raw) -> float | None:
    # Some clubs return a scalar price; others a list of fee objects with a "price" key.
    if not raw:
        return None
    if isinstance(raw, list):
        prices = [float(x["price"]) for x in raw if isinstance(x, dict) and x.get("price")]
        return min(prices) if prices else None
    return float(raw)


def _is_par3_course(name: str) -> bool:
    n = name.lower()
    if "par 3" in n or "par3" in n or "par-3" in n:
        return True
    return bool(re.search(r"\bp3\b", n))


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
                    price_eur=_parse_green_fee(raw_price),
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
