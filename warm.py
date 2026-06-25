"""Out-of-band warmer for the slow / rate-limited backends.

Vercel kills each request at 10s, but teecontrol (~55s, hard rate limit),
nexxchange (~43s, rate limit) and golfmanager/Waterland (JS-token gated) cannot
finish in that window, so they silently vanish from the live app. This script
runs in GitHub Actions (no time limit), fetches them for the next week at the
WIDEST settings, and writes warm.json. The app reads that file and filters per
request. See cache_backend.py for the read side.

teecontrol/nexxchange rate-limit PER IP, so the work is SHARDED across several
GitHub runners (each its own IP) to fit a tighter refresh interval:

    python warm.py --shard I --of N   # one runner: fetch its slice -> warm_shard_I.json
    python warm.py --merge --of N     # combine the shard files -> warm.json

The merge CARRIES FORWARD the previous warm.json for any course a shard failed
to fetch, so a single flaky shard never silently drops courses; it only makes
those courses slightly stale (and the monitor — monitor.py — alerts on it).
`course_fresh_at` records, per course, when it was last successfully fetched;
that is the signal the monitor watches.
"""
import argparse
import asyncio
import sys
import json
from collections import defaultdict
from datetime import date as date_type, timedelta, datetime, timezone
from pathlib import Path

import httpx

from scrapers import teecontrol as tc
from scrapers import nexxchange as nx
from scrapers import golfmanager as gm

DAYS = 7
HERE = Path(__file__).parent
OUT = HERE / "warm.json"
PREV_URL = "https://raw.githubusercontent.com/LuitElbers/tee-times/data/warm.json"

# teecontrol and nexxchange rate-limit a concurrent fan-out (a burst of all clubs
# at once 429s and gets silently dropped). Fetch a few clubs at a time and retry
# transient failures, so coverage is complete and we can tell "empty" from "failed".
_CONCURRENCY = 3
_ATTEMPTS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dates() -> list[str]:
    today = date_type.today()
    return [(today + timedelta(days=i)).isoformat() for i in range(DAYS)]


def _shard(seq: list, shard: int, total: int) -> list:
    """Deterministic interleave so each shard gets ~even load from each backend."""
    return [c for i, c in enumerate(seq) if i % total == shard]


def expected_courses() -> set[str]:
    """Every course the warmer is responsible for (the warmed backends only).
    The monitor and the carry-forward both key off this set, by course name."""
    names = {c["course_name"] for c in tc.COURSES}
    names |= {c["name"] for c in nx.COURSES}
    names |= {c["course_name"] for c in gm.COURSES}
    return names


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

        for course in gm.COURSES:
            ok, failed, errors = 0, 0, []
            for d in _dates():
                url = f"{course['base_url']}/consumer/book?area={course['area']}&date={d}T00:00"
                try:
                    async with page.expect_response(
                        lambda r: "availability.json" in r.url and d in r.url, timeout=20000
                    ) as resp_info:
                        await page.goto(url, wait_until="commit", timeout=20000)
                    data = await (await resp_info.value).json()
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


def _fresh_course_names(status: dict) -> set[str]:
    """A course is 'fresh' only if at least one date was fetched successfully.
    A course attempted but all-dates-failed is NOT fresh (so it carries forward).
    A course fetched with zero tee times IS fresh (legitimately empty)."""
    fresh = set()
    for per_course in status.values():
        for course, info in per_course.items():
            if info.get("dates_ok", 0) > 0:
                fresh.add(course)
    return fresh


async def fetch_slice(shard: int, total: int) -> None:
    status: dict = {}
    tc_courses = _shard(tc.COURSES, shard, total)
    nx_courses = _shard(nx.COURSES, shard, total)

    tasks = [
        _warm_clubs("teecontrol", tc_courses,
                    lambda c, d: tc._fetch_course(c, d, 1, None, True, True),
                    lambda c: c["course_name"], status),
        _warm_clubs("nexxchange", nx_courses,
                    lambda c, d: nx._fetch_course(c, d, 1, None),
                    lambda c: c["name"], status),
    ]
    parts = list(await asyncio.gather(*tasks))

    # Waterland is a single Playwright course; only shard 0 runs it (no point
    # installing/driving a browser on every runner).
    if shard == 0:
        parts.append(await _warm_waterland(status))

    days: dict[str, list] = {}
    for part in parts:
        _merge(days, part)

    out = {
        "shard": shard,
        "total": total,
        "generated_at": _now(),
        "days": days,
        "status": status,
        "fresh_courses": sorted(_fresh_course_names(status)),
    }
    path = HERE / f"warm_shard_{shard}.json"
    path.write_text(json.dumps(out), encoding="utf-8")
    nfresh = len(out["fresh_courses"])
    total_rows = sum(len(v) for v in days.values())
    print(f"shard {shard}/{total}: {nfresh} fresh courses, {total_rows} tee times -> {path.name}")


def _load_prev() -> dict:
    try:
        r = httpx.get(PREV_URL, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"WARNING merge: no previous warm.json ({e}); nothing to carry forward", file=sys.stderr)
        return {}


def do_merge(total: int) -> None:
    now = _now()
    shard_files = sorted(HERE.glob("warm_shard_*.json"))
    present = []
    for f in shard_files:
        try:
            present.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"WARNING merge: could not read {f.name}: {e}", file=sys.stderr)
    present_ids = sorted(p.get("shard") for p in present)
    print(f"merge: {len(present)}/{total} shards present: {present_ids}")

    days: dict[str, list] = {}
    status: dict = {}
    course_fresh_at: dict[str, str] = {}
    fresh: set[str] = set()
    for part in present:
        _merge(days, part.get("days", {}))
        for backend, per in part.get("status", {}).items():
            status.setdefault(backend, {}).update(per)
        for c in part.get("fresh_courses", []):
            course_fresh_at[c] = part.get("generated_at", now)
            fresh.add(c)

    # Carry forward any expected course that wasn't freshly fetched (shard missing
    # or that course's fetch failed), so courses never silently disappear.
    prev = _load_prev()
    prev_days = prev.get("days", {})
    prev_fresh_at = prev.get("course_fresh_at", {})
    carried = sorted(expected_courses() - fresh)
    carried_with_data = []
    for c in carried:
        if c in prev_fresh_at:
            course_fresh_at[c] = prev_fresh_at[c]
    if carried and prev_days:
        carried_set = set(carried)
        for d, rows in prev_days.items():
            kept = [r for r in rows if r.get("course") in carried_set]
            if kept:
                days.setdefault(d, []).extend(kept)
        carried_with_data = sorted({r.get("course") for rows in prev_days.values()
                                    for r in rows if r.get("course") in set(carried)})

    for d in days:
        days[d].sort(key=lambda t: t["timestamp"])

    courses_seen: dict[str, int] = {}
    for rows in days.values():
        for r in rows:
            courses_seen[r["course"]] = courses_seen.get(r["course"], 0) + 1

    out = {
        "generated_at": now,
        "days": days,
        "status": status,
        "courses_seen": dict(sorted(courses_seen.items())),
        "course_fresh_at": course_fresh_at,
        "shards_total": total,
        "shards_present": present_ids,
        "fresh_courses": sorted(fresh),
        "carried_courses": carried,            # expected courses not freshly fetched this run
        "carried_with_data": carried_with_data,  # of those, the ones we still have prior data for
    }
    OUT.write_text(json.dumps(out), encoding="utf-8")

    total_rows = sum(len(v) for v in days.values())
    print(f"warm.json written: {total_rows} tee times, {len(courses_seen)} courses seen, "
          f"{len(fresh)} fresh, {len(carried)} carried-forward")
    if present_ids != list(range(total)):
        print(f"  WARNING: missing shards {sorted(set(range(total)) - set(present_ids))} "
              f"-> {len(carried)} courses served from previous warm.json", file=sys.stderr)
    if carried:
        print(f"  carried-forward courses: {', '.join(carried)}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1, dest="total")
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    if args.merge:
        do_merge(args.total)
    else:
        asyncio.run(fetch_slice(args.shard, args.total))


if __name__ == "__main__":
    main()
