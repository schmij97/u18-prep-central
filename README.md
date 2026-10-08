# U18 Prep Central

CSSHL U18 Prep scores, schedule, standings, stats, power rankings, rosters and
Game Centre, built from the league's HockeyTech feed. Published at
https://pcha.renslip.com

## How it works

- `update.py` downloads the data and builds `site/index.html`.
  - every run: scores, standings, stats, new box scores (`fetch.py`, `fetch_boxscores.py`)
  - once a day, on the 10 PM run: player game logs (`fetch_gamelogs.py`)
  - once a week: rosters and junior rights (`fetch_rosters.py`)
  - then the page is built from `template.html` (`build.py`); power rankings come from `rankings.py`
- GitHub Actions (`.github/workflows/update.yml`) runs every hour. The update only
  happens when due, in Mountain time: every hour from 8 AM to 11 PM Friday to Sunday,
  and once at 10 PM Monday to Thursday. Player game logs refresh on the 10 PM run.
  Downloaded data is saved back into `data/`, and the site is published to GitHub Pages.
- Manual update: Actions tab > "Update site" > Run workflow (tick the box to also refresh rosters).

## Run locally

    python update.py          # normal update
    python update.py --all    # also refresh rosters and game logs now

Then open `site/index.html`.

## One-time setup

1. Push this folder to a **public** GitHub repository (Actions is free for public repos).
2. Repository Settings > Pages > Build and deployment > Source: **GitHub Actions**.
3. Settings > Pages > Custom domain: `pcha.renslip.com`, then tick **Enforce HTTPS** once offered.
4. At the DNS provider for renslip.com, add a record:
   `CNAME  pcha  ->  <your-github-username>.github.io`
5. Actions tab > "Update site" > Run workflow (tick "all") for the first build.

## Season rollover

Update `CURRENT_SEASON` and `PRIOR_SEASON` in `fetch.py` (season ids come from the
HockeyTech seasons feed) and `RATING_BASE` in `rankings.py` if recalibrating.
