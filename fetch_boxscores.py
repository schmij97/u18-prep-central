"""Download box scores for started games into data/games/<game_id>.json.

Live and unofficial games are re-downloaded on every run until the league marks them final.
After that, games from the last 3 days are re-downloaded in case the league corrects a stat.
fetch.py calls this automatically; it can also be run on its own.
"""
import json, datetime, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from fetch import BASE, COMMON, DATA

GAMES = DATA / "games"
RECHECK_DAYS = 3


def raw_summary(game_id):
    q = {**COMMON, "feed": "statviewfeed", "view": "gameSummary", "game_id": game_id, "site_id": 8}
    with urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(q), timeout=30) as r:
        t = r.read().decode("utf-8").strip()
    if t.startswith("(") and t.endswith(")"):  # this feed wraps its JSON in brackets
        t = t[1:-1]
    return json.loads(t)


def person(p):
    p = p or {}
    if not p.get("id") or str(p.get("id")) == "0":
        return None
    return {"id": str(p["id"]), "name": f'{p.get("firstName") or ""} {p.get("lastName") or ""}'.strip(),
            "num": str(p.get("jerseyNumber") or "")}


def compact(d):
    def side(t):
        st = t.get("stats") or {}
        sk = [{**person(s["info"]), "pos": s["info"].get("position") or "",
               "g": int(s["stats"].get("goals") or 0), "a": int(s["stats"].get("assists") or 0),
               "pts": int(s["stats"].get("points") or 0), "pim": int(s["stats"].get("penaltyMinutes") or 0)}
              for s in t.get("skaters") or [] if person(s.get("info"))]
        go = []
        for s in t.get("goalieLog") or []:
            if not person(s.get("info")):
                continue
            x = s.get("stats") or {}
            go.append({**person(s["info"]), "toi": x.get("timeOnIce") or "", "sa": int(x.get("shotsAgainst") or 0),
                       "ga": int(x.get("goalsAgainst") or 0), "sv": int(x.get("saves") or 0),
                       "res": s.get("result") or ""})
        return {"id": str(t["info"]["id"]), "shots": int(st.get("shots") or 0),
                "ppg": int(st.get("powerPlayGoals") or 0), "ppo": int(st.get("powerPlayOpportunities") or 0),
                "pim": int(st.get("penaltyMinuteCount") or 0), "skaters": sk, "goalies": go,
                "coach": next((f'{c["firstName"]} {c["lastName"]}' for c in t.get("coaches") or [] if c.get("role") == "Head Coach"), "")}

    periods, goals, pens = [], [], []
    for p in d.get("periods") or []:
        name = p["info"].get("longName") or p["info"].get("shortName")
        s = p.get("stats") or {}
        periods.append({"name": name, "hg": int(s.get("homeGoals") or 0), "hs": int(s.get("homeShots") or 0),
                        "ag": int(s.get("visitingGoals") or 0), "as": int(s.get("visitingShots") or 0)})
        for g in p.get("goals") or []:
            pr = g.get("properties") or {}
            goals.append({"per": name, "time": g.get("time"), "team": str(g["team"]["id"]),
                          "by": person(g.get("scoredBy")), "n": g.get("scorerGoalNumber"),
                          "ast": [a for a in (person(x) for x in g.get("assists") or []) if a],
                          "pp": pr.get("isPowerPlay") == "1", "sh": pr.get("isShortHanded") == "1",
                          "en": pr.get("isEmptyNet") == "1", "ps": pr.get("isPenaltyShot") == "1",
                          "gwg": pr.get("isGameWinningGoal") == "1"})
        for x in p.get("penalties") or []:
            pens.append({"per": name, "time": x.get("time"), "team": str(x["againstTeam"]["id"]),
                         "by": person(x.get("takenBy")), "bench": bool(x.get("isBench")),
                         "min": x.get("minutes"), "desc": x.get("description") or ""})
    # shootout attempts, in the order the feed lists them for each team
    so = d.get("shootoutDetails") or {}
    shootout = {k: [{"by": person(x.get("shooter")), "goal": bool(x.get("isGoal")), "win": bool(x.get("isGameWinningGoal"))}
                    for x in so.get(src) or [] if person(x.get("shooter"))]
                for k, src in (("home", "homeTeamShots"), ("away", "visitingTeamShots"))}
    det = d.get("details") or {}
    return {"id": str(det.get("id")), "start": det.get("startTime"), "venue": det.get("venue"),
            "att": det.get("attendance") or 0, "status": det.get("status"), "so": bool(d.get("hasShootout")), "shootout": shootout,
            "periods": periods, "goals": goals, "pens": pens,
            "home": side(d["homeTeam"]), "away": side(d["visitingTeam"])}


def main():
    GAMES.mkdir(exist_ok=True)
    sched = json.loads((DATA / "schedule.json").read_text())["SiteKit"]["Schedule"]
    cutoff = (datetime.date.today() - datetime.timedelta(days=RECHECK_DAYS)).isoformat()
    todo = [g["game_id"] for g in sched if g["started"] == "1"
            and (g["final"] != "1" or not (GAMES / f'{g["game_id"]}.json').exists() or g["date_played"] >= cutoff)]

    def one(gid):
        try:
            (GAMES / f"{gid}.json").write_text(json.dumps(compact(raw_summary(gid)), separators=(",", ":")))
            return True
        except Exception as e:
            print("box score failed", gid, e)
            return False

    with ThreadPoolExecutor(4) as ex:
        ok = sum(ex.map(one, todo))
    print(f"box scores: {ok} downloaded, {len(list(GAMES.glob('*.json')))} on file")


if __name__ == "__main__":
    main()
