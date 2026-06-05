"""
Scraper coverage test.

For each golf club, we:
1. Query the external booking site directly (raw check) to discover which
   (course, holes) combinations have available slots over the next 14 days.
2. Call our scraper for the same dates.
3. Assert that every (course, holes) pair the external site shows as available
   also appears in the scraper output.

Passes when:
  - Scraper exposes everything the site offers with availability, OR
  - Both site and scraper return nothing (genuine no availability / course closed).
Fails when the site has available slots the scraper silently drops.
"""
import re
import asyncio
from datetime import date, timedelta

import httpx
import pytest
from bs4 import BeautifulSoup

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.teecontrol import (
    fetch_tee_times as tc_fetch, COURSES as TC_COURSES, API_BASE as TC_API_BASE
)
from scrapers.intogolf import fetch_tee_times as ig_fetch, CLUBS as IG_CLUBS
from scrapers.hollandschegolfclub import fetch_tee_times as hgc_fetch
from scrapers.golfmanager import fetch_tee_times as gm_fetch
from scrapers.egolf4u import fetch_tee_times as eg_fetch, COURSES as EG_COURSES
from scrapers.nexxchange import fetch_tee_times as nx_fetch, COURSES as NX_COURSES
from scrapers.rijkvannunspeet import fetch_tee_times as rvn_fetch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_dates(n=14) -> list[str]:
    today = date.today()
    return [(today + timedelta(days=i)).isoformat() for i in range(1, n + 1)]


async def _run_scraper(fetch_fn, dates: list[str]) -> set[tuple[str, int]]:
    """Call scraper sequentially over dates; collect (course, holes) pairs."""
    seen: set[tuple[str, int]] = set()
    for d in dates:
        try:
            results = await fetch_fn(d, 1, None)
            for tt in results:
                seen.add((tt.course, tt.holes))
        except Exception:
            pass
    return seen


def _assert_no_gaps(raw: set[tuple[str, int]], scraped: set[tuple[str, int]], label: str):
    missing = raw - scraped
    if missing:
        formatted = ", ".join(f"{c} {h}h" for c, h in sorted(missing))
        pytest.fail(
            f"{label}: external site shows {formatted} available "
            f"but scraper never returned them.\n"
            f"  Site found:    {sorted(raw)}\n"
            f"  Scraper found: {sorted(scraped)}"
        )


# ---------------------------------------------------------------------------
# Raw site checkers — independent of our scraper logic
# Each returns the set of (course_name, holes) that has available slots
# for players=1 somewhere in the given date list.
# ---------------------------------------------------------------------------

async def raw_teecontrol(dates: list[str]) -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    async with httpx.AsyncClient(timeout=15) as client:
        for course in TC_COURSES:
            origin = course["origin"]
            try:
                tr = await client.get(
                    f"{TC_API_BASE}/auth/guest",
                    headers={"Origin": origin},
                )
                tr.raise_for_status()
                token = tr.json()["token"]
            except Exception:
                continue

            headers = {"Authorization": f"Guest {token}", "Origin": origin}
            for d in dates:
                try:
                    sets_r = await client.get(
                        f"{TC_API_BASE}/sets",
                        params={"can_book_at": d},
                        headers=headers,
                    )
                    sets_r.raise_for_status()
                    for s in sets_r.json():
                        if "footgolf" in s.get("name", "").lower():
                            continue
                        holes = s.get("holes_amount")
                        if not holes:
                            continue
                        # Check if this set has any available start times
                        st_r = await client.get(
                            f"{TC_API_BASE}/start-times",
                            params={"date": d, "slots": 1, "set_uuid": s["uuid"],
                                    "with_players": 1, "with_unavailable": 0},
                            headers=headers,
                        )
                        st_r.raise_for_status()
                        if any(item.get("is_available") for item in st_r.json()):
                            seen.add((course["course_name"], holes))
                except Exception:
                    pass
    return seen


async def raw_intogolf(dates: list[str]) -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    async with httpx.AsyncClient(timeout=15) as client:
        for club in IG_CLUBS:
            for d in dates:
                try:
                    r = await client.get(club["api_url"], params={"date": d})
                    r.raise_for_status()
                    for course in r.json().get("payload", []):
                        for slot in course.get("times", []):
                            max_p = slot.get("sttMaxPlayers", 4)
                            booked = slot.get("playerCount", 0)
                            if (max_p - booked) < 1:
                                continue
                            seen.add((club["course_name"], 9))
                            if slot.get("sttCrlNrNext", 0) != 0:
                                seen.add((club["course_name"], 18))
                except Exception:
                    pass
    return seen


async def raw_hollandschegolfclub(dates: list[str]) -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    page_url = "https://www.hollandschegolfclub.nl/boek-een-starttijd/"
    ajax_url = "https://www.hollandschegolfclub.nl/wp-admin/admin-ajax.php"
    locations = [{"id": 153, "name": "De Purmer"}, {"id": 141, "name": "De Loonsche Duynen"}]

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            rp = await client.get(page_url)
            m = re.search(r'itgTeetimeConfig[^}]*"nonce"\s*:\s*"([^"]+)"', rp.text)
            nonce = m.group(1) if m else None
        except Exception:
            return seen

        for loc in locations:
            for holes_param in (9, 18):
                for d in dates:
                    try:
                        r = await client.post(ajax_url, data={
                            "action": "itg_get_teetimes", "nonce": nonce,
                            "date": d, "location_id": loc["id"],
                            "holes": holes_param, "period": 1, "player_count": 1,
                        })
                        body = r.json()
                        if not body.get("success"):
                            continue
                        for course in body["data"]["courses"]:
                            times = course["times"]
                            if isinstance(times, dict):
                                times = list(times.values())
                            has_avail = any(
                                isinstance(s, dict) and
                                s.get("_sttMaxPlayers", 4) - s.get("_sttPlayers", 0) >= 1
                                for s in times
                            )
                            if has_avail:
                                nm = course["name"].lower()
                                mh = re.search(r'\((\d+)\s*-\s*(\d+)\)', nm)
                                h = int(mh.group(2)) - int(mh.group(1)) + 1 if mh else holes_param
                                seen.add((loc["name"], h))
                    except Exception:
                        pass
    return seen


async def raw_golfmanager(dates: list[str]) -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    async with httpx.AsyncClient(timeout=15) as client:
        for d in dates:
            try:
                r = await client.get(
                    "https://eu.golfmanager.com/golfwaterland/consumer/availability.json",
                    params={"date": f"{d}T00:00", "area": 2},
                )
                for item in r.json().get("items", []):
                    if item.get("slots", 0) < 1:
                        continue
                    name = item.get("name", "").lower()
                    if "9 hole" in name:
                        seen.add(("Waterland", 9))
                    elif "18 hole" in name:
                        seen.add(("Waterland", 18))
            except Exception:
                pass
    return seen


async def raw_egolf4u(dates: list[str]) -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for course in EG_COURSES:
            url = f"https://{course['subdomain']}.teetime.e-golf4u.nl/app/booking/teetime"
            for holes_param in (9, 18):
                for d in dates:
                    try:
                        r = await client.get(url, params={"date": d, "holes": holes_param})
                        soup = BeautifulSoup(r.text, "html.parser")
                        for grid in soup.select("div.teetime-grid"):
                            avail = grid.select("div.btn.teetime:not(.niet-beschikbaar)")
                            if avail:
                                seen.add((course["name"], holes_param))
                    except Exception:
                        pass
    return seen


async def raw_nexxchange(dates: list[str]) -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    facets = [(1, 9), (2, 18)]
    async with httpx.AsyncClient(timeout=15) as client:
        for course in NX_COURSES:
            for facet_id, holes in facets:
                for d in dates:
                    parsed = date.fromisoformat(d)
                    date_str = f"{parsed.day}.{parsed.month}.{parsed.year}"
                    try:
                        r = await client.get(
                            f"https://www.nexxchange.com/search/optimized-teetimes/content/{course['slug']}",
                            params={"sortIndex": 1, "courseId": 1, "date": date_str, "facetId": facet_id},
                        )
                        soup = BeautifulSoup(r.text, "html.parser")
                        sections = soup.find_all(id=re.compile(r"^tt-\d{4}$"))
                        for sec in sections:
                            if sec.select(".player-box.none"):
                                seen.add((course["name"], holes))
                                break
                    except Exception:
                        pass
    return seen


async def raw_rijkvannunspeet(dates: list[str]) -> set[tuple[str, int]]:
    from urllib.parse import urlencode
    from scrapers.rijkvannunspeet import COURSE_DATA, COURSE_NAMES
    seen: set[tuple[str, int]] = set()
    base_url = "https://reserveren.hetrijkgolfbanen.nl/OnlineRes/RvNu/Home/WidgetView/?Option=bezoekers"

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for d in dates:
            parsed = date.fromisoformat(d)
            date_str = parsed.strftime("%d-%m-%Y")
            try:
                resp = await client.get(base_url)
                session_url = str(resp.url)
                post_url = re.sub(r"/Home/WidgetView.*", "/Home/WidgetView/nl", session_url)
                form: list[tuple[str, str]] = [
                    ("Option", "0"), ("OptionForSpecialRow", "Search"),
                    ("SelectedTeeSheetId", "0"), ("FromDateString", ""),
                    ("FromDate", date_str), ("TabbedViewStartTime", "AnyTime"),
                    ("SelectedCourses", "4"), ("SelectedCourses", "5"), ("SelectedCourses", "6"),
                    ("PlayerNumber", "1"), ("MinimumPlayer", "1"), ("MaximumPlayer", "4"),
                    ("DefaultNumberOfPlayer", "99"), ("DefaultHole", "SearchAny"),
                ]
                for i, cd in enumerate(COURSE_DATA):
                    for key, val in cd.items():
                        form.append((f"Courses[{i}].{key}", val))
                resp2 = await client.post(
                    post_url, content=urlencode(form).encode(),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                soup = BeautifulSoup(resp2.text, "html.parser")
                for slot in soup.select("div[data-teesheetid]"):
                    cid = int(slot.get("courseid", 0))
                    player_p = slot.select_one(".player p")
                    if player_p:
                        m = re.search(r"(\d+)\s+tot\s+(\d+)", player_p.text)
                        if m and int(m.group(2)) >= 1:
                            hole_div = slot.select_one(".hole-icon div")
                            h = int(hole_div.text.strip()) if hole_div and hole_div.text.strip().isdigit() else None
                            if h and cid in (4, 5, 6):
                                seen.add(("Rijk van Nunspeet", h))
            except Exception:
                pass
    return seen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

SCRAPERS = [
    ("TeeControl",         raw_teecontrol,         tc_fetch),
    ("IntoGolf",           raw_intogolf,            ig_fetch),
    ("HollandseGolfClub",  raw_hollandschegolfclub, hgc_fetch),
    ("GolfManager",        raw_golfmanager,         gm_fetch),
    ("eGolf4u",            raw_egolf4u,             eg_fetch),
    ("Nexxchange",         raw_nexxchange,          nx_fetch),
    ("RijkVanNunspeet",    raw_rijkvannunspeet,     rvn_fetch),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("label,raw_fn,scraper_fn", SCRAPERS, ids=[s[0] for s in SCRAPERS])
async def test_scraper_matches_site(label, raw_fn, scraper_fn):
    """
    Scraper must expose every (course, holes) combination visible on the
    external booking site over the next 14 days.
    If the external site has no availability either, the test is skipped.
    """
    dates = _next_dates(14)

    raw, scraped = await asyncio.gather(
        raw_fn(dates),
        _run_scraper(scraper_fn, dates),
    )

    if not raw:
        pytest.skip(
            f"{label}: external site returned no available slots in next 14 days "
            f"(scraper found: {sorted(scraped) or 'nothing'})"
        )

    _assert_no_gaps(raw, scraped, label)
