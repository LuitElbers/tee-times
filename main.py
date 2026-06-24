from datetime import date as date_type, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
import asyncio
from scrapers.intogolf import fetch_tee_times as ig_fetch
from scrapers.hollandschegolfclub import fetch_tee_times as hgc_fetch
from scrapers.egolf4u import fetch_tee_times as eg_fetch
from scrapers.rijkvannunspeet import fetch_tee_times as rvn_fetch
from scrapers.asparagi import fetch_tee_times as asp_fetch
from scrapers.teecontrol import fetch_tee_times as tc_fetch, set_min_interval as _tc_set_interval
from scrapers.nexxchange import fetch_tee_times as nx_fetch
from scrapers.chronogolf import fetch_tee_times as cg_fetch
from scrapers.bernardus import fetch_tee_times as bern_fetch
from cache_backend import fetch_tee_times as cached_fetch
from models import TeeTime

app = FastAPI()

# On-demand far-date fetches are a single date (small burst), so teecontrol can run
# faster here than the warmer's gentle rate (~28s vs ~38s per date).
_tc_set_interval(0.15)

# Fast backends are capped so one slow one can't block the response. The slow,
# rate-limited backends (teecontrol/nexxchange) are normally served pre-fetched
# from warm.json, but for dates beyond the warm window we fetch them live with a
# much longer cap (the function platform allows ~50s+, verified).
BACKEND_TIMEOUT = 8.0
FAR_BACKEND_TIMEOUT = 48.0

# warm.py warms today..today+6 (7 days). Beyond that, fetch the slow backends live.
WARM_DAYS = 7


async def _run_backend(coro, timeout=BACKEND_TIMEOUT):
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        print(f"WARNING: backend timed out after {timeout}s; returning partial results")
        return []


@app.get("/")
async def index():
    return RedirectResponse("/index.html")


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

    # Fast backends are always fetched live.
    fast = [
        ig_fetch(date, players, holes_int, include_par3, include_championship),
        hgc_fetch(date, players, holes_int, include_par3, include_championship),
        eg_fetch(date, players, holes_int, include_par3, include_championship),
        rvn_fetch(date, players, holes_int, include_par3, include_championship),
        asp_fetch(date, players, holes_int, include_par3, include_championship),
        cg_fetch(date, players, holes_int, include_par3, include_championship),
        bern_fetch(date, players, holes_int, include_par3, include_championship),
    ]
    tasks = [_run_backend(s) for s in fast]
    notices: list[str] = []

    # Slow/rate-limited backends: served from warm.json within the warm window, or
    # fetched live (slower) for dates beyond it. Waterland needs a browser to fetch
    # and isn't available live, so it's flagged rather than silently dropped.
    if _is_far_date(date):
        tasks.append(_run_backend(tc_fetch(date, players, holes_int, include_par3, include_championship), FAR_BACKEND_TIMEOUT))
        tasks.append(_run_backend(nx_fetch(date, players, holes_int, include_par3, include_championship), FAR_BACKEND_TIMEOUT))
        notices.append("Waterland kon niet laden voor deze datum.")
    else:
        tasks.append(_run_backend(cached_fetch(date, players, holes_int, include_par3, include_championship)))

    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[TeeTime] = [
        tt for r in all_results
        if isinstance(r, list)
        for tt in r
    ]
    results.sort(key=lambda t: t.timestamp)

    return {"tee_times": [t.model_dump(mode="json") for t in results], "notices": notices}


def _is_far_date(date: str) -> bool:
    try:
        return date_type.fromisoformat(date) > date_type.today() + timedelta(days=WARM_DAYS - 1)
    except ValueError:
        return False
