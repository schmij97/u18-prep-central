"""Turn the raw feed files in data/ into compact JSON files under site/data/ and build the page.

The page loads core/logos/rosters/gamelogs at startup and fetches a game's box score
(site/data/box/<id>.json) only when that game is opened. File hashes go into the page as
?v= query strings so phones pick up new data as soon as it's published."""
import hashlib, json, pathlib, re, shutil
import rankings

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"


def load(name, key):
    return json.loads((DATA / name).read_text())["SiteKit"][key]


def short(nick):
    return re.sub(r"\s*U18 Prep$", "", nick).strip()


def abbr(code):
    return re.sub(r"18P$", "", code)


def teams_from(schedule):
    t = {}
    for g in schedule:
        for side, pre in (("home_team", "home_team_"), ("visiting_team", "visiting_team_")):
            t[g[side]] = {"name": short(g[pre + "nickname"]), "full": g[pre + "name"], "abbr": abbr(g[pre + "code"])}
    return t


def finals(schedule):
    return [
        dict(home_id=g["home_team"], away_id=g["visiting_team"],
             home_goals=int(g["home_goal_count"]), away_goals=int(g["visiting_goal_count"]),
             extra=g["overtime"] == "1" or g["shootout"] == "1")
        for g in schedule if g["final"] == "1"
    ]


def game_row(g):
    suffix = "SO" if g["shootout"] == "1" else ("OT" if g["overtime"] == "1" else "")
    return {
        "id": g["game_id"], "date": g["date_played"], "iso": g["GameDateISO8601"], "day": g["date_with_day"],
        "h": g["home_team"], "a": g["visiting_team"],
        "hg": int(g["home_goal_count"]), "ag": int(g["visiting_goal_count"]),
        "final": g["final"] == "1", "started": g["started"] == "1",
        "status": g["game_status"], "suffix": suffix,
        "tz": g.get("timezone", ""), "venue": g.get("venue_name", ""), "city": g.get("venue_location", ""),
    }


def main():
    cur = load("schedule.json", "Schedule")
    prev = load("schedule_2526.json", "Schedule")
    teams = teams_from(prev)
    teams.update(teams_from(cur))
    logos = json.loads((DATA / "logos.json").read_text())

    rk_cur, _ = rankings.compute(finals(cur))
    rk_prev, _ = rankings.compute(finals(prev))
    rnd = lambda rows: [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]

    standings = [
        {k: s[k] for k in ("team_id", "games_played", "wins", "losses", "ot_losses", "shootout_losses",
                           "regulation_wins", "points", "goals_for", "goals_against", "goals_diff",
                           "percentage", "power_play_pct", "penalty_kill_pct", "streak_wl", "past_10",
                           "power_play_goals", "power_plays", "times_short_handed", "power_play_goals_against",
                           "short_handed_goals_for", "short_handed_goals_against",
                           "home_record", "visiting_record", "rank")}
        for s in load("standings.json", "Statviewtype") if "team_id" in s
    ]

    skaters = [
        {"id": p["player_id"], "name": p["name"], "num": p["jersey_number"], "pos": p["position"], "team": p["team_id"],
         "gp": int(p["games_played"]), "g": int(p["goals"]), "a": int(p["assists"]), "pts": int(p["points"]),
         "ppg": int(p.get("power_play_goals") or 0), "gwg": int(p.get("game_winning_goals") or 0),
         "pim": int(p.get("penalty_minutes") or 0), "pmg": float(p["points_per_game"] or 0),
         "born": p.get("birthdate_year", ""), "home": p.get("hometownprov", "")}
        for p in load("scorers.json", "Statviewtype") if p.get("player_id") and int(p["games_played"] or 0) > 0
    ]
    goalies = [
        {"id": p["player_id"], "name": p["name"], "team": p["team_id"], "gp": int(p["games_played"]),
         "w": int(p["wins"] or 0), "l": int(p["losses"] or 0), "otl": int(p.get("ot_losses") or 0),
         "sv": float(p["save_percentage"] or 0), "gaa": float(p.get("goals_against_average") or 0),
         "so": int(p["shutouts"] or 0), "saves": int(p["saves"] or 0), "min": int(p.get("minutes_played") or 0)}
        for p in load("goalies.json", "Statviewtype") if p.get("player_id") and int(p["games_played"] or 0) > 0
    ]

    # rosters: refreshed weekly by fetch_rosters.py; optional so the site still builds without it
    rpath = DATA / "rosters.json"
    rosters = json.loads(rpath.read_text()) if rpath.exists() else {"fetched": None, "players": []}

    # game-by-game logs: refreshed daily by fetch_gamelogs.py; optional
    gpath = DATA / "gamelogs.json"
    gamelogs = json.loads(gpath.read_text()) if gpath.exists() else {"fetched": None, "skaters": {}, "goalies": {}}

    # box scores, one file per finished game (fetch_boxscores.py)
    boxscores = {}
    for f in sorted((DATA / "games").glob("*.json")) if (DATA / "games").exists() else []:
        boxscores[f.stem] = json.loads(f.read_text())

    core = {
        "updated": max(g["date_played"] for g in cur if g["final"] == "1"),
        "teams": teams,
        "games": [game_row(g) for g in cur],
        "box_ids": sorted(boxscores), "rating_base": rankings.RATING_BASE,
        "standings": standings, "skaters": skaters, "goalies": goalies,
        "rankings": {"2026-27": rnd(rk_cur), "2025-26": rnd(rk_prev)},
    }

    out = ROOT / "site"; out.mkdir(exist_ok=True)
    od = out / "data"
    if od.exists():
        shutil.rmtree(od)
    (od / "box").mkdir(parents=True)
    dump = lambda obj: json.dumps(obj, separators=(",", ":"))
    digest = lambda text: hashlib.sha1(text.encode()).hexdigest()[:10]

    files, total = {}, 0
    for name, obj in (("core", core), ("logos", logos), ("rosters", rosters), ("gamelogs", gamelogs)):
        text = dump(obj)
        (od / f"{name}.json").write_text(text)
        files[name] = digest(text); total += len(text)
    box_hash = hashlib.sha1()
    for gid, b in boxscores.items():
        text = dump(b)
        (od / "box" / f"{gid}.json").write_text(text)
        box_hash.update(gid.encode() + text.encode())
    files["box"] = box_hash.hexdigest()[:10]

    html = (ROOT / "template.html").read_text(encoding="utf-8").replace("/*__FILES__*/null", dump(files))
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "CNAME").write_text("pcha.renslip.com\n")  # custom domain for GitHub Pages
    print("built site/index.html", len(html) // 1024, "KB + startup data", total // 1024, "KB +",
          len(boxscores), "box scores;", len(skaters), "skaters,", len(goalies), "goalies,", len(core["games"]), "games")


if __name__ == "__main__":
    main()
