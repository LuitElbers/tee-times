"""Enforces the championship/short classification (course_types.COURSE_TYPES).

Hard requirement: a course may only appear under the app's "Championship" filter if it
is a verified full-length regulation course. This test guarantees that by checking, for
every course any backend can emit, that the backend's championship-eligibility matches
the registry — and that no course is left unclassified (a new course fails the test until
it is explicitly added to course_types.py, i.e. default-deny).

Run: `python -m pytest tests/test_course_types.py`  or  `python tests/test_course_types.py`.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from course_types import COURSE_TYPES, is_championship
from scrapers import (
    nexxchange, asparagi, chronogolf, golfmanager,
    teecontrol, intogolf, egolf4u, hollandschegolfclub, rijkvannunspeet,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _backend_championship_eligibility() -> dict[str, bool]:
    """course name -> True if that backend can serve it as a (non-short) championship
    course. A course is championship-eligible iff it offers >=1 regulation variant."""
    elig: dict[str, bool] = {}

    def add(name: str, champ: bool):
        elig[name] = elig.get(name, False) or champ

    for c in nexxchange.COURSES:
        add(c["name"], not c["is_par3"])
    for c in asparagi.COURSES:
        add(c["name"], not c["is_par3"])
    for c in chronogolf.COURSES:
        add(c["name"], not c["is_short"])
    for c in golfmanager.COURSES:
        add(c["course_name"], not c["is_par3"])
    for c in teecontrol.COURSES:
        # whole-short courses flagged "short"; mixed clubs keep their championship sets
        add(c["course_name"], not c.get("short", False))
    for c in intogolf.CLUBS:
        add(c["course_name"], not c.get("short", False))
    for c in egolf4u.COURSES:
        add(c["name"], any(not b["is_par3"] for b in c["baans"]))
    for loc in hollandschegolfclub.LOCATIONS:
        add(loc["name"], not loc.get("short", False))
    for site in rijkvannunspeet.SITES:
        add(site["display"], any(not cc["par3"] for cc in site["courses"]))
    # bernardus serves one course, a full 18-hole championship
    add("Bernardus", True)
    return elig


def _course_order() -> list[str]:
    html = open(os.path.join(ROOT, "public", "index.html"), encoding="utf-8").read()
    m = re.search(r"const COURSE_ORDER = \[(.*?)\];", html, re.S)
    assert m, "COURSE_ORDER not found in public/index.html"
    return re.findall(r'"([^"]+)"', m.group(1))


def test_every_app_course_is_classified():
    """Every course shown in the app must have an explicit classification.
    A new, unclassified course fails here (default-deny)."""
    missing = [n for n in _course_order() if n not in COURSE_TYPES]
    assert not missing, f"Courses in the app but not classified in course_types.py: {missing}"


def test_every_backend_course_is_classified():
    """Every course any scraper can emit must be classified (catches new scraper adds)."""
    missing = sorted(n for n in _backend_championship_eligibility() if n not in COURSE_TYPES)
    assert not missing, f"Courses served by a scraper but not in course_types.py: {missing}"


def test_registry_has_no_orphans():
    """The registry must not list courses the app no longer shows (keeps it in sync)."""
    order = set(_course_order())
    orphans = sorted(n for n in COURSE_TYPES if n not in order)
    assert not orphans, f"course_types.py lists courses not in the app: {orphans}"


def test_backend_classification_matches_registry():
    """The crux: each backend's championship-eligibility must equal the registry.
    - registry 'short'        -> backend must NOT serve it as championship
    - registry 'championship' -> backend MUST be able to serve a championship variant
    """
    elig = _backend_championship_eligibility()
    wrong_short = [n for n, champ in elig.items()
                   if champ and not is_championship(n)]
    wrong_champ = [n for n, champ in elig.items()
                   if not champ and is_championship(n)]
    msg = []
    if wrong_short:
        msg.append("Classified 'short' but a backend still serves them as Championship "
                   f"(fix the scraper flag): {sorted(wrong_short)}")
    if wrong_champ:
        msg.append("Classified 'championship' but no backend offers a championship variant "
                   f"(fix the registry or the scraper flag): {sorted(wrong_champ)}")
    assert not msg, "\n".join(msg)


def test_known_short_courses_are_short():
    """Anchor a few hand-verified short courses so a regression is obvious."""
    for n in ["Soestduinen", "De Bonte Bij", "Weesp", "Kavel II Beemster",
              "Riel", "Concordia", "De Vlietlanden", "Ockenburgh"]:
        assert COURSE_TYPES.get(n) == "short", f"{n} must be classified short"
        assert not is_championship(n)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if failures else 0)
