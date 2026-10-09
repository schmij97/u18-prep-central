"""Pull CSSHL U18 Prep data from the HockeyTech feed into data/.

The client code and key are the public ones the league's own stats pages use.
Cache results and run on a schedule rather than calling the feed on every page view.
"""
import json, pathlib, urllib.request, urllib.parse, base64

BASE = "https://lscluster.hockeytech.com/feed/index.php"
COMMON = {"key": "dbb3085c9c2968c6", "client_code": "csshl", "lang": "en", "fmt": "json", "league_id": 6}
CURRENT_SEASON = 212   # 2026-27 U18 Prep regular season
PRIOR_SEASON = 192     # 2025-26
DATA = pathlib.Path(__file__).parent / "data"


def get(**params):
    url = BASE + "?" + urllib.parse.urlencode({**COMMON, **params})
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def main():
    DATA.mkdir(exist_ok=True)
    jobs = {
        "schedule.json": dict(feed="modulekit", view="schedule", season_id=CURRENT_SEASON),
        "schedule_2526.json": dict(feed="modulekit", view="schedule", season_id=PRIOR_SEASON),
        "standings.json": dict(feed="modulekit", view="statviewtype", type="standings", stat="conference", season_id=CURRENT_SEASON),
        "scorers.json": dict(feed="modulekit", view="statviewtype", type="topscorers", season_id=CURRENT_SEASON, first=0, limit=2000),
        "goalies.json": dict(feed="modulekit", view="statviewtype", type="topgoalies", season_id=CURRENT_SEASON, first=0, limit=500, qualified="all"),
    }
    for name, p in jobs.items():
        (DATA / name).write_text(json.dumps(get(**p)))
        print("saved", name)

    # team logos (small versions), saved for embedding
    logos = {}
    sched = json.loads((DATA / "schedule.json").read_text())["SiteKit"]["Schedule"]
    sched += json.loads((DATA / "schedule_2526.json").read_text())["SiteKit"]["Schedule"]
    ids = {g["home_team"] for g in sched} | {g["visiting_team"] for g in sched}
    for tid in sorted(ids):
        try:
            with urllib.request.urlopen(f"https://assets.leaguestat.com/csshl/logos/50x50/{tid}.png", timeout=15) as r:
                logos[tid] = "data:image/png;base64," + base64.b64encode(r.read()).decode()
        except Exception as e:
            print("no logo for", tid, e)
    (DATA / "logos.json").write_text(json.dumps(logos))
    print("logos", len(logos))


if __name__ == "__main__":
    main()
    import fetch_boxscores  # box scores for live, unofficial and newly finished games
    fetch_boxscores.main()
