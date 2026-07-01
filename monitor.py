"""Independent health monitor for the warmer.

The warmer (warm.py, GitHub Actions) republishes warm.json every ~30 min. If it
silently stops (the failure that prompted this), or a backend keeps failing so a
group of courses stops updating, tee-time availability goes stale and nobody
notices. This runs on its OWN schedule (so it still fires even if the warmer
workflow is completely dead) and alerts on Telegram.

State lives on the `monitor` branch (monitor_state.json) so we alert ONCE when an
outage starts, again every 6h while it persists, and once on recovery — never an
hourly spam. Reuses the warmer's orphan-branch publish pattern.

Telegram creds come from env (GitHub secrets): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from warm import expected_courses, PREV_URL  # PREV_URL = data-branch warm.json

STATE_URL = "https://raw.githubusercontent.com/LuitElbers/tee-times/monitor/monitor_state.json"
STATE_OUT = Path(__file__).parent / "monitor_state.json"

OVERALL_STALE_H = 2     # warm.json should republish every ~30 min; >2h = warmer down
COURSE_STALE_H = 3      # a course not freshly fetched in >3h = that backend persistently failing
STALE_COURSE_MIN = 4    # only alert on a "bunch" (e.g. a whole backend); 1-2 flaky
                        # courses are covered by carry-forward and just noted, not alerted
REALERT_H = 6           # while still down, re-alert at most this often


def _get_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"could not load {url}: {e}", file=sys.stderr)
        return None


def _age_h(iso: str, now: datetime) -> float:
    try:
        return (now - datetime.fromisoformat(iso)).total_seconds() / 3600.0
    except Exception:
        return float("inf")


def assess(warm: dict | None, now: datetime) -> tuple[bool, str]:
    """Return (healthy, human summary)."""
    if not warm:
        return False, "warm.json could not be loaded at all (warmer never published, or the data branch is broken)."

    lines: list[str] = []
    gen_age = _age_h(warm.get("generated_at", ""), now)
    if gen_age > OVERALL_STALE_H:
        lines.append(f"warm.json last republished {gen_age:.1f}h ago (expected every ~30 min).")

    # Per-course freshness only applies when the map exists. If it's absent (a
    # legacy/transition warm.json) we rely on generated_at alone rather than
    # falsely reporting every course as "never fetched".
    fresh_at = warm.get("course_fresh_at", {})
    stale = []
    if fresh_at:
        for course in sorted(expected_courses()):
            ts = fresh_at.get(course)
            age = float("inf") if ts is None else _age_h(ts, now)
            if age > COURSE_STALE_H:
                stale.append((course, "never" if ts is None else f"{age:.1f}h"))
    # A bunch of stale courses (a backend persistently failing) is an alert; 1-3
    # flaky ones are covered by carry-forward, so note them but don't alarm.
    if len(stale) >= STALE_COURSE_MIN:
        shown = ", ".join(f"{c} ({a})" for c, a in stale[:12])
        more = f" +{len(stale) - 12} more" if len(stale) > 12 else ""
        lines.append(f"{len(stale)} courses not updated in >{COURSE_STALE_H}h: {shown}{more}.")

    note = ""
    if 0 < len(stale) < STALE_COURSE_MIN:
        note = "  (note, not alerting: " + ", ".join(c for c, _ in stale) + " stale but carried forward.)"

    if lines:
        return False, "\n".join(lines)
    return True, (f"healthy - warm.json {gen_age:.1f}h old, "
                  f"{len(expected_courses()) - len(stale)}/{len(expected_courses())} courses fresh.{note}")


def _telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("WARNING: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set; cannot alert", file=sys.stderr)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()
    print("telegram alert sent")


def main() -> None:
    now = datetime.now(timezone.utc)
    warm = _get_json(PREV_URL)
    healthy, summary = assess(warm, now)
    print(("HEALTHY: " if healthy else "UNHEALTHY: ") + summary)

    state = _get_json(STATE_URL) or {"status": "ok", "since": None, "last_alert": None}
    new_state = dict(state)

    if not healthy:
        last_alert_age = _age_h(state.get("last_alert") or "", now)
        if state.get("status") != "down":
            _telegram(f"\U0001F534 Tee Times warmer DOWN\n\n{summary}\n\n"
                      f"(near-date tee-time availability is going stale.)")
            new_state = {"status": "down", "since": now.isoformat(), "last_alert": now.isoformat()}
        elif last_alert_age >= REALERT_H:
            since = state.get("since")
            dur = f"{_age_h(since, now):.1f}h" if since else "a while"
            _telegram(f"\U0001F534 Tee Times warmer STILL down ({dur})\n\n{summary}")
            new_state["last_alert"] = now.isoformat()
        else:
            print("already alerted recently; staying quiet")
    else:
        if state.get("status") == "down":
            since = state.get("since")
            dur = f"{_age_h(since, now):.1f}h" if since else "?"
            _telegram(f"\U0001F7E2 Tee Times warmer RECOVERED (was down ~{dur}).\n\n{summary}")
        new_state = {"status": "ok", "since": None, "last_alert": None}

    STATE_OUT.write_text(json.dumps(new_state), encoding="utf-8")


if __name__ == "__main__":
    main()
