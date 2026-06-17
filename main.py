from datetime import date as date_type
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
import asyncio
from scrapers.intogolf import fetch_tee_times as ig_fetch
from scrapers.hollandschegolfclub import fetch_tee_times as hgc_fetch
from scrapers.egolf4u import fetch_tee_times as eg_fetch
from scrapers.rijkvannunspeet import fetch_tee_times as rvn_fetch
from scrapers.asparagi import fetch_tee_times as asp_fetch
from cache_backend import fetch_tee_times as cached_fetch
from models import TeeTime

app = FastAPI()

# Cap each backend so one slow/rate-limited backend (teecontrol) can't block the
# whole response. A timed-out backend returns nothing this request; its short-TTL
# response cache warms over subsequent loads so its courses fill in. 8s keeps the
# worst-case response under Vercel's default 10s function limit.
BACKEND_TIMEOUT = 8.0


async def _run_backend(coro):
    try:
        return await asyncio.wait_for(coro, BACKEND_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"WARNING: backend timed out after {BACKEND_TIMEOUT}s; returning partial results")
        return []


@app.get("/")
async def index():
    return RedirectResponse("/index.html")


@app.get("/api/_sleeptest")
async def _sleeptest(secs: float = Query(default=20.0)):
    import time as _t
    start = _t.time()
    await asyncio.sleep(secs)
    return {"requested": secs, "actual": round(_t.time() - start, 1)}


@app.get("/api/tee-times")
async def get_tee_times(
    date: str = Query(default=None),
    players: int = Query(default=2, ge=1, le=4),
    holes: str = Query(default="all"),
    include_par3: bool = Query(default=False),
    include_championship: bool = Query(default=True),
):
    if date is None:
        date = date_type.today().isoformat()

    holes_int = None if holes == "all" else int(holes)

    # teecontrol, nexxchange and golfmanager are too slow / rate-limited / token-gated
    # to finish inside the request limit, so they are served from warm.json (built
    # out-of-band by warm.py, read via cache_backend) instead of scraped live here.
    scrapers = [
        ig_fetch(date, players, holes_int, include_par3, include_championship),
        hgc_fetch(date, players, holes_int, include_par3, include_championship),
        eg_fetch(date, players, holes_int, include_par3, include_championship),
        rvn_fetch(date, players, holes_int, include_par3, include_championship),
        asp_fetch(date, players, holes_int, include_par3, include_championship),
        cached_fetch(date, players, holes_int, include_par3, include_championship),
    ]

    all_results = await asyncio.gather(*[_run_backend(s) for s in scrapers], return_exceptions=True)

    results: list[TeeTime] = [
        tt for r in all_results
        if isinstance(r, list)
        for tt in r
    ]
    results.sort(key=lambda t: t.timestamp)

    return [t.model_dump(mode="json") for t in results]
