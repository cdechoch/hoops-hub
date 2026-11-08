# Hoops Hub

A phone app (installable web app) for live NBA scores, Kansas and Miami games, news, trends, injuries, the draft board, rookies, leaderboards, team pages and cap sheets.

## How it works

- `pipeline/` is Python. GitHub Actions runs it every 5 minutes, writes JSON into `web/data/`, and publishes `web/` to GitHub Pages.
- `web/` is the app. It reloads its data every minute while open and can be saved to your Home Screen.
- Alerts reach your phone and computer through ntfy, plus in-app alerts while the app is open.

| Job | When | Sections |
| --- | --- | --- |
| live | every 5 minutes | scores, hot and cold players, news, trends, injuries |
| hourly | top of each hour | leaders, rookies, top 150, teams, standings, salaries on team pages |
| hourly | top of each hour | HoopsMatic contracts, cap sheets, exceptions, picks |
| daily | 09:00 UTC | HoopsHype and Spotrac fallbacks if HoopsMatic is unreachable |
| weekly | Monday 09:00 UTC | draft board with last week's rank for movement |

The draft year and rookie class roll forward on their own. The draft cycle switches on July 10, two weeks after a late June draft.

## Data from HoopsMatic and the HoopsHype workbook

- `pipeline/hoopsmatic.py` reads the data files hoopsmatic.com publishes: contracts by year, team cap and apron room, mid-level and bi-annual exceptions, trade exceptions, every team's draft picks, and the injury feed. It runs hourly and feeds the Contracts, Cap and Teams tabs. Spotrac and the HoopsHype salary page are only used if HoopsMatic cannot be reached.
- Draft picks come from HoopsMatic and the app works out which ones can be traded (Stepien rule and the seven year limit).
- `pipeline/excel_import.py` turns the All-Time Database workbook into `config/db/bio.json` (height, weight, birthplace, college, draft slot) and `config/db/combine.json` (combine measurements). Teams and Draft use them. Re-run it when the workbook changes: `python pipeline/excel_import.py All-Time_Database_2_0.xlsx`.
- HoopsMatic's draft board is only used when it is for the current class. Right now it is still labeled the 2026 draft and the workbook lists those players as drafted in 2026, so the app skips it and uses its other sources until HoopsMatic rebuilds it for 2027.
- If the site blocks GitHub's servers, ask for an allowlist key, add it as the secret `HOOPSMATIC_KEY` (sent as the `X-Hoops-Key` header), or save copies of the files into `config/hoopsmatic/` (`contracts.csv`, `rm-roster.csv`, `rm-exceptions.csv`, `draft-csv.csv`).

## Setup (about 10 minutes)

1. Create a GitHub repo and push this folder to `main`.
2. In the repo, open Settings, then Pages, and set the source to GitHub Actions.
3. Open Settings, then Secrets and variables, then Actions. Add a secret `NTFY_TOPIC` with a long random name, for example `hoops-k3j9x2mq7p`. Add a variable `SITE_URL` with your Pages address, for example `https://yourname.github.io/hoops-hub`.
4. Open the Actions tab, pick "Refresh and publish", and run it once with "Run every job" checked.
5. On your phone, install the free ntfy app and subscribe to your topic. On your computer, open `https://ntfy.sh/your-topic` and allow notifications.
6. Open your Pages address on your phone. iPhone: Share, then Add to Home Screen. Android: menu, then Install app.

Cloudflare Pages also works: point it at the `web` folder. The workflow publishes to GitHub Pages by default.

## What you get alerts for

- Kansas and Miami football and basketball: tipoff, close games late, finals.
- NBA: tipoff, close games late, finals.
- A hot headline covered by several outlets.
- A new number one name trending in the last hour.

## Edit these files

- `config/draft_sources.json`: big board sources, and the weight of your own board (1.5 by default).
- `config/manual_rankings/`: drop a CSV named `tankathon.csv`, `espn.csv`, `bleacherreport.csv`, `noceilings.csv`, `nbadraftnet.csv` or `cyroasseo.csv` (columns `rank,name,pos,school`) when a site blocks the scraper.
- `config/prospect_profiles.json`: measurements, hometown and stats per prospect, keyed by lowercase name without punctuation.
- `config/picks.json`: backup list of each team's picks, used only if HoopsMatic is unreachable.
- `config/cap_thresholds.json`: cap, tax and apron lines. 2026-27 numbers come from the NBA release.

## Known limits

- GitHub's fastest schedule is 5 minutes, so "every minute" is not possible on this setup. The app itself checks for new data every minute. For true one-minute polling, run `python pipeline/run_all.py` in a loop on a server.
- X and TikTok have no free public data. Trends use headlines, Reddit and Google Trends.
- stats.nba.com sometimes blocks GitHub's servers. If leaders, rookies or teams stay empty, run `JOBS=hourly python pipeline/run_all.py` from your own computer.
- Trade exceptions show the holder, size and expiry. HoopsMatic's file does not say which trade created each one.
- The HoopsMatic parsers were checked against real sample rows, but the full files could not be downloaded in the build sandbox. The HoopsHype, Spotrac, Tankathon, NBADraft.net, ESPN, Bleacher Report and No Ceilings parsers read public pages and have not been run against the live sites yet. Check the first run's log and use the manual files above if a source returns nothing.
- Per-prospect stats, measurements and injuries need `prospect_profiles.json` or table data on the source page. Headlines fill the "word on the street" line.

## Tests

`python -m pytest tests`
