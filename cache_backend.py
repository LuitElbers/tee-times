"""Read side of the warmer. Serves teecontrol / nexxchange / golfmanager from the
pre-fetched warm.json (built by warm.py, committed to the `data` branch) instead
of scraping them live, because they can't finish inside Vercel's 10s request
limit. warm.json holds the WIDEST result set; we filter per request here.
"""
import sys
import time
import httpx
from models import TeeTime

WARM_URL = "https://raw.githubusercontent.com/LuitElbers/tee-times/data/warm.json"
_TTL = 60.0
_cache: dict = {"at": 0.0, "data": None}


async def _load() -> dict:
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < _TTL:
        return _cache["data"]
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(WARM_URL)
        resp.raise_for_status()
        data = resp.json()
    _cache["data"] = data
    _cache["at"] = now
    return data


async def fetch_tee_times(date: str, players: int, holes: int | None,
                          include_par3: bool = False, include_championship: bool = True) -> list[TeeTime]:
    try:
        data = await _load()
    except Exception as e:
        print(f"WARNING cache_backend: could not load warm.json: {e}", file=sys.stderr)
        return []

    rows = data.get("days", {}).get(date, [])
    out: list[TeeTime] = []
    for r in rows:
        if r["free_slots"] < players:
            continue
        if holes is not None and r["holes"] != holes:
            continue
        is_short = r.get("is_short", False)
        if is_short and not include_par3:
            continue
        if not is_short and not include_championship:
            continue
        out.append(TeeTime(**r))
    return out
