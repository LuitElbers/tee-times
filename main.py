from datetime import date as date_type
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from scrapers.teecontrol import fetch_tee_times as tc_fetch
from scrapers.intogolf import fetch_tee_times as ig_fetch
from scrapers.hollandschegolfclub import fetch_tee_times as hgc_fetch
from scrapers.golfmanager import fetch_tee_times as gm_fetch
from scrapers.egolf4u import fetch_tee_times as eg_fetch
from scrapers.nexxchange import fetch_tee_times as nx_fetch
from scrapers.rijkvannunspeet import fetch_tee_times as rvn_fetch
from models import TeeTime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


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

    scrapers = [
        tc_fetch(date, players, holes_int, include_par3, include_championship),
        ig_fetch(date, players, holes_int, include_par3, include_championship),
        hgc_fetch(date, players, holes_int, include_par3, include_championship),
        gm_fetch(date, players, holes_int, include_par3, include_championship),
        eg_fetch(date, players, holes_int, include_par3, include_championship),
        nx_fetch(date, players, holes_int, include_par3, include_championship),
        rvn_fetch(date, players, holes_int, include_par3, include_championship),
    ]

    all_results = await asyncio.gather(*scrapers, return_exceptions=True)

    results: list[TeeTime] = [
        tt for r in all_results
        if isinstance(r, list)
        for tt in r
    ]
    results.sort(key=lambda t: t.timestamp)

    return [t.model_dump(mode="json") for t in results]
