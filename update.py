"""One command for every update: python update.py

Each run:
  - always refreshes scores, standings, stats and new box scores (fetch.py)
  - refreshes player game logs once per day, on the 10 PM run (fetch_gamelogs.py)
  - refreshes rosters and junior rights once per week (fetch_rosters.py)
  - rebuilds the site (build.py)

Production schedule (GitHub runs `update.py --scheduled` every hour; it only
updates when due, in Mountain time):
  Fri, Sat, Sun  from 8 AM until 1 AM that night (the big game days; covers late BC/WA games)
  Mon - Thu      once a day at 10 PM
Because game logs and rosters track their own last-run date, running this
hourly never re-downloads them more than once a day / once a week.
"""
import datetime, json, os, sys
try:
    from zoneinfo import ZoneInfo
    LOCAL = ZoneInfo("America/Edmonton")
except Exception:      # Windows Python without the tzdata package: use the PC's own clock
    LOCAL = None

import fetch, fetch_gamelogs, fetch_rosters, build
from fetch import DATA

ROSTER_EVERY_DAYS = 7


def last_fetched(name):
    p = DATA / name
    try:
        return datetime.date.fromisoformat(json.loads(p.read_text())["fetched"])
    except Exception:
        return None


STAMP = DATA / "last_update.txt"   # date of the last scheduled Mon-Thu update


def due_now():
    """Scheduler gate. GitHub runs this hourly; we only update when our schedule says so
    (Mountain time, so daylight saving is handled automatically):
      Fri-Sun: from 8 AM until 1 AM that night (so Sat/Sun/Mon 12:00-1:00 AM count too)
      Mon-Thu: once, at 10 PM. If GitHub runs late and the job lands at 11 PM, it still
               runs once (GitHub's hourly timer can be delayed when it's busy)."""
    now = datetime.datetime.now(LOCAL)
    wd = now.weekday()              # Mon=0 ... Fri=4, Sat=5, Sun=6
    if wd >= 4 and now.hour >= 8:   # Fri-Sun daytime and evening
        return True
    if wd in (5, 6, 0) and (now.hour == 0 or (now.hour == 1 and now.minute < 5)):
        return True                 # after midnight following a Fri/Sat/Sun game night
    if wd >= 4:
        return False
    if now.hour >= 22:
        last = STAMP.read_text().strip() if STAMP.exists() else ""
        return last != now.date().isoformat()
    return False


def main(force=False):
    today = datetime.datetime.now(LOCAL).date()
    print(f"== update {datetime.datetime.now():%Y-%m-%d %H:%M}")

    print("-- scores, standings, stats, box scores")
    fetch.main()
    import fetch_boxscores
    fetch_boxscores.main()

    # game logs: nightly, on the late runs (10 PM, 11 PM and the after-midnight run on
    # weekends) so late games are included; at most once an hour
    gl = last_fetched("gamelogs.json")
    now = datetime.datetime.now(LOCAL)
    try:
        gl_at = datetime.datetime.fromisoformat(json.loads((DATA / "gamelogs.json").read_text()).get("fetched_at", ""))
    except Exception:
        gl_at = None
    late = now.hour >= 22 or now.hour == 0
    stale = gl_at is None or (now - gl_at.astimezone(now.tzinfo) if gl_at.tzinfo and now.tzinfo else datetime.timedelta(hours=2)) >= datetime.timedelta(minutes=55)
    if force or gl is None or (late and stale):
        print("-- player game logs (daily)")
        fetch_gamelogs.main()
    else:
        print("-- game logs update on the late-night runs, skipping")

    ro = last_fetched("rosters.json")
    if force or ro is None or (today - ro).days >= ROSTER_EVERY_DAYS:
        print("-- rosters and junior rights (weekly)")
        fetch_rosters.main()
    else:
        print(f"-- rosters updated {ro}, next after {ro + datetime.timedelta(days=ROSTER_EVERY_DAYS)}, skipping")

    print("-- building site")
    build.main()


if __name__ == "__main__":
    if "--scheduled" in sys.argv and not due_now():
        print("not scheduled to update this hour; nothing to do")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            open(out, "a").write("ran=false\n")
        sys.exit(0)
    main(force="--all" in sys.argv)
    if "--scheduled" in sys.argv:   # manual runs mustn't use up the Mon-Thu 10 PM run
        DATA.mkdir(exist_ok=True)
        STAMP.write_text(datetime.datetime.now(LOCAL).date().isoformat())
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        open(out, "a").write("ran=true\n")
