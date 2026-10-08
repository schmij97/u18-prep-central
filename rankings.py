"""Power ratings using a goal-differential + strength-of-schedule method.

Rating = AGD + SCHED
  AGD   = team's average goal differential per game, each game capped at +/- GD_CAP
  SCHED = average Rating of the opponents the team played

Because each rating depends on opponents' ratings, the system is solved iteratively
until it stops changing. Ratings are then shifted onto a display scale where the
league average is RATING_BASE. Only differences matter: a team rated 98.00 should
beat a 96.00 team by about 2 goals. SCHED is shown on the same scale, so
Rating = AGD + SCHED still adds up on the page.
"""
from collections import defaultdict

GD_CAP = 7          # max goal differential counted in a single game
RATING_BASE = 97.52  # league-average rating; calibrated so 2025-26 matches MHR (Kelowna 99.99, SAHA 99.60)
MAX_ITER = 10000
TOL = 1e-9


def compute(games):
    """games: list of dicts with home_id, away_id, home_goals, away_goals (finals only)."""
    played = defaultdict(list)  # team -> [(opp, capped_gd)]
    for g in games:
        gd = g["home_goals"] - g["away_goals"]
        gd = max(-GD_CAP, min(GD_CAP, gd))
        played[g["home_id"]].append((g["away_id"], gd))
        played[g["away_id"]].append((g["home_id"], -gd))

    teams = list(played)
    agd = {t: sum(d for _, d in played[t]) / len(played[t]) for t in teams}
    rating = dict(agd)

    for it in range(MAX_ITER):
        sched = {t: sum(rating[o] for o, _ in played[t]) / len(played[t]) for t in teams}
        new = {t: agd[t] + sched[t] for t in teams}
        # centre on 0 -- the system only defines ratings relative to each other
        mean = sum(new.values()) / len(new)
        new = {t: v - mean for t, v in new.items()}
        # damping keeps the iteration stable on sparse early-season schedules
        new = {t: 0.5 * rating[t] + 0.5 * new[t] for t in teams}
        delta = max(abs(new[t] - rating[t]) for t in teams)
        rating = new
        if delta < TOL:
            break

    sched = {t: sum(rating[o] for o, _ in played[t]) / len(played[t]) for t in teams}

    # W-L-OTL records (an overtime or shootout loss counts as OTL)
    rec = defaultdict(lambda: [0, 0, 0])
    for g in games:
        if g["home_goals"] == g["away_goals"]:
            continue  # no ties expected (shootouts decide games); skip if one appears
        hw = g["home_goals"] > g["away_goals"]
        win, lose = (g["home_id"], g["away_id"]) if hw else (g["away_id"], g["home_id"])
        rec[win][0] += 1
        rec[lose][2 if g.get("extra") else 1] += 1

    out = [
        {"team_id": t, "gp": len(played[t]), "w": rec[t][0], "l": rec[t][1], "otl": rec[t][2],
         "agd": agd[t], "sched": sched[t] + RATING_BASE, "rating": rating[t] + RATING_BASE}
        for t in teams
    ]
    out.sort(key=lambda r: -r["rating"])
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out, it + 1
