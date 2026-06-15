"""Out-of-band warmer for the slow / rate-limited backends.

Vercel kills each request at 10s, but teecontrol (~55s, hard rate limit),
nexxchange (~43s, rate limit) and golfmanager/Waterland (JS-token gated) cannot
finish in that window, so they silently vanish from the live app. This script
runs in GitHub Actions (no time limit), fetches them gently for the next week at
the WIDEST settings, and writes warm.json. The app reads that file and filters
per request. See cache_backend.py for the read side.
"""
import asyncio
import sys
import json
from collections import defaultdict
from datetime import date as date_type, timedelta, datetime, timezone
from pathlib import Path

from scrapers import teecontrol as tc
from scrapers import nexxchange as nx
from scrapers import golfmanager as gm

DAYS = 7
OUT = Path(__file__).parent / "warm.json"

# teecontrol and nexxchange rate-limit a concurrent fan-out (a burst of all clubs
# at once 429s and gets silently dropped). Fetch a few clubs at a time and retry
# transient failures, so coverage is complete and we can tell "empty" from "failed".
_CONCURRENCY = 3
_ATTEMPTS = 4


def _dates() -> list[str]:
    today = date_type.today()
    return [(today + timedelta(days=i)).isoformat() for i in range(DAYS)]


async def _with_retry(make_coro, attempts: int = _ATTEMPTS):
    last = None
    for i in range(attempts):
        try:
            return await make_coro()
        except Exception as e:
            last = e
            await asyncio.sleep(0.8 * (2 ** i))
    raise last


async def _warm_clubs(name: str, courses: list, fetch_one, key, status: dict) -> dict[str, list]:
    """Warm one backend club-by-club (bounded concurrency + retry). fetch_one(course,
    date) -> list[TeeTime]; key(course) -> course display name. Records per-course
    status so a club that breaks is visible, never silently dropped."""
    sem = asyncio.Semaphore(_CONCURRENCY)
    by_day: dict[str, list] = defaultdict(list)
    per_course: dict[str, dict] = {}

    async def do(course):
        ok, failed, errors = 0, 0, []
        for d in _dates():
            async with sem:
                try:
                    tts = await _with_retry(lambda: fetch_one(course, d))
                    by_day[d].extend(t.model_dump(mode="json") for t in tts)
                    ok += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"{d}: {type(e).__name__}: {e}")
                    print(f"WARNING {name} {key(course)} {d}: {e}", file=sys.stderr)
        per_course[key(course)] = {"ok": failed == 0, "dates_ok": ok, "dates_failed": failed, "errors": errors}

    await asyncio.gather(*[do(c) for c in courses])
    status[name] = per_course
    return by_day


async def _warm_waterland(status: dict) -> dict[str, list]:
    """Waterland's availability API is gated by a client-side signed token, so a
    real browser is the reliable way in. Capture the availability.json response."""
    by_day: dict[str, list] = defaultdict(list)
    per_course: dict[str, dict] = {}
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        for course in gm.COURSES:
            per_course[course["course_name"]] = {"ok": False, "dates_ok": 0, "dates_failed": DAYS,
                                                 "errors": [f"playwright not installed: {e}"]}
        status["golfmanager"] = per_course
        return by_day

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        captured: dict[str, dict] = {}

        async def on_response(resp):
            if "availability.json" in resp.url:
                try:
                    captured[resp.url] = await resp.json()
                except Exception:
                    pass

        page.on("response", on_response)

        for course in gm.COURSES:
            ok, failed, errors = 0, 0, []
            for d in _dates():
                captured.clear()
                url = f"{course['base_url']}/consumer/book?area={course['area']}&date={d}T00:00"
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    data = next((v for k, v in captured.items() if d in k), None)
                    if data is None:
                        data = next(iter(captured.values()), None)
                    if data is None:
                        raise RuntimeError("no availability.json captured")
                    items = data.get("items", [])
                    tts = gm.items_to_teetimes(course, items)
                    by_day[d].extend(t.model_dump(mode="json") for t in tts)
                    ok += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"{d}: {type(e).__name__}: {e}")
                    print(f"WARNING golfmanager {course['course_name']} {d}: {e}", file=sys.stderr)
            per_course[course["course_name"]] = {"ok": failed == 0, "dates_ok": ok, "dates_failed": failed, "errors": errors}

        await browser.close()

    status["golfmanager"] = per_course
    return by_day


def _merge(target: dict[str, list], src: dict[str, list]) -> None:
    for d, rows in src.items():
        target.setdefault(d, []).extend(rows)


async def main() -> None:
    status: dict = {}
    tc_days, nx_days, gw_days = await asyncio.gather(
        _warm_clubs("teecontrol", tc.COURSES,
                    lambda c, d: tc._fetch_course(c, d, 1, None, True, True),
                    lambda c: c["course_name"], status),
        _warm_clubs("nexxchange", nx.COURSES,
                    lambda c, d: nx._fetch_course(c, d, 1, None),
                    lambda c: c["name"], status),
        _warm_waterland(status),
    )

    days: dict[str, list] = {}
    for part in (tc_days, nx_days, gw_days):
        _merge(days, part)
    for d in days:
        days[d].sort(key=lambda t: t["timestamp"])

    courses_seen: dict[str, int] = {}
    for rows in days.values():
        for r in rows:
            courses_seen[r["course"]] = courses_seen.get(r["course"], 0) + 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "status": status,
        "courses_seen": dict(sorted(courses_seen.items())),
    }
    OUT.write_text(json.dumps(out), encoding="utf-8")

    total = sum(len(v) for v in days.values())
    print(f"warm.json written: {total} tee times across {len(days)} days, {len(courses_seen)} courses")
    broken = []
    for backend, per_course in status.items():
        n_ok = sum(1 for c in per_course.values() if c["ok"])
        print(f"  {backend}: {n_ok}/{len(per_course)} clubs fully fetched")
        broken += [f"{backend}/{name}" for name, c in per_course.items() if not c["ok"]]
    if broken:
        print(f"  BROKEN ({len(broken)}): {', '.join(broken)}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
