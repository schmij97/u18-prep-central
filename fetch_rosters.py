"""Pull every U18 Prep team roster, including WHL/junior rights and signings.

Rosters and signings change slowly, so run this once a week (fetch.py handles
scores and stats more often). Saves data/rosters.json.
"""
import json, pathlib, datetime
from fetch import get, CURRENT_SEASON, DATA


def rights(p):
    """Junior/league rights from draftinfo, de-duplicated across the feed's language copies."""
    seen = {}
    for d in p.get("draftinfo") or []:
        key = d.get("id")
        cur = seen.get(key)
        # prefer the English copy, but fill a blank status from the other language copy
        if cur is None or (not cur["status"] and d.get("draft_status")):
            seen[key] = {
                "team": d.get("draft_team", ""), "league": d.get("draft_league", ""),
                "year": d.get("draft_year", ""), "round": d.get("draft_round", ""),
                "pick": d.get("draft_rank", ""),
                "status": d.get("draft_status", "") or (cur or {}).get("status", ""),
            }
    return sorted(seen.values(), key=lambda r: r["year"], reverse=True)


def main():
    standings = json.loads((DATA / "standings.json").read_text())["SiteKit"]["Statviewtype"]
    team_ids = [s["team_id"] for s in standings if "team_id" in s]
    players = []
    for tid in team_ids:
        roster = get(feed="modulekit", view="roster", team_id=tid, season_id=CURRENT_SEASON)["SiteKit"]["Roster"]
        for p in roster:
            if not isinstance(p, dict) or not p.get("player_id") or p.get("hidden") == "1":
                continue
            players.append({
                "id": p["player_id"], "team": tid, "name": p["name"],
                "first": p["first_name"], "last": p["last_name"],
                "num": "" if p.get("tp_jersey_number") in ("", "0", None) else p["tp_jersey_number"],
                "pos": p.get("position", ""),
                "shoots": p.get("shoots") or p.get("catches") or "",
                "ht": p.get("height", ""), "wt": p.get("weight", ""),
                "dob": p.get("rawbirthdate") or p.get("birthdate", ""),
                "home": p.get("homeplace", ""),
                "commit": p.get("college_commitments_school", ""),
                "rights": rights(p),
            })
        print(f"team {tid}: roster saved")
    out = {"fetched": datetime.date.today().isoformat(), "players": players}
    (DATA / "rosters.json").write_text(json.dumps(out))
    signed = sum(1 for p in players if any(r["status"] == "Signed" for r in p["rights"]))
    print(f"{len(players)} players, {signed} signed")


if __name__ == "__main__":
    main()
