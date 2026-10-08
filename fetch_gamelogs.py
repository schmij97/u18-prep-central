"""Pull each player's game-by-game log for the current season.

One request per player who has played, so run this once a day (fetch.py handles
scores and stats more often). Saves data/gamelogs.json. Run fetch.py first so the
player lists are current.
"""
import json, datetime
from concurrent.futures import ThreadPoolExecutor
from fetch import get, CURRENT_SEASON, DATA

WORKERS = 4  # a few at a time, to be gentle on the league's server


def skater_row(g):
    return {"gid": g["id"], "date": g["date_played"], "home": g["home"] == "1",
            "opp": g["visiting_team"] if g["home"] == "1" else g["home_team"],
            "g": int(g.get("goals") or 0), "a": int(g.get("assists") or 0), "pts": int(g.get("points") or 0),
            "ppg": int(g.get("power_play_goals") or 0), "shg": int(g.get("short_handed_goals") or 0),
            "gwg": int(g.get("game_winning_goals") or 0),
            "pim": int(float(g.get("penalty_minutes") or 0))}


def goalie_row(g):
    return {"gid": g["id"], "date": g["date_played"], "home": g["home"] == "1",
            "opp": g["visiting_team"] if g["home"] == "1" else g["home_team"],
            "dec": "W" if g.get("win") == "1" else "OTL" if g.get("ot_loss") == "1" or g.get("shootout_loss") == "1" else "L" if g.get("loss") == "1" else "",
            "sa": int(g.get("shots_against") or 0), "ga": int(g.get("goals_against") or 0),
            "sv": int(g.get("saves") or 0), "svpct": float(g.get("svpct") or 0),
            "so": g.get("shutout") == "1", "min": g.get("minutes", "")}


def one(pid, goalie):
    try:
        games = get(feed="modulekit", view="player", category="gamebygame",
                    player_id=pid, season_id=CURRENT_SEASON)["SiteKit"]["Player"].get("games") or []
    except Exception as e:
        print("failed", pid, e)
        return pid, None
    rows = [goalie_row(g) if goalie else skater_row(g) for g in games
            if (g.get("goalie") == "1") == goalie]
    return pid, rows


def main():
    played = lambda f: [p["player_id"] for p in json.loads((DATA / f).read_text())["SiteKit"]["Statviewtype"]
                        if p.get("player_id") and int(p.get("games_played") or 0) > 0]
    jobs = [(pid, False) for pid in played("scorers.json")] + [(pid, True) for pid in played("goalies.json")]

    # keep yesterday's log for anyone whose request fails today
    path = DATA / "gamelogs.json"
    old = json.loads(path.read_text()) if path.exists() else {"skaters": {}, "goalies": {}}
    out = {"fetched": datetime.date.today().isoformat(), "skaters": {}, "goalies": {}}
    with ThreadPoolExecutor(WORKERS) as ex:
        for (pid, rows), (_, goalie) in zip(ex.map(lambda j: one(*j), jobs), jobs):
            key = "goalies" if goalie else "skaters"
            out[key][pid] = rows if rows is not None else old[key].get(pid, [])
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"game logs saved: {len(out['skaters'])} skaters, {len(out['goalies'])} goalies")


if __name__ == "__main__":
    main()
