# Hoops Hub

A phone app (installable web app) for live NBA scores, Kansas and Miami games, news, trends, injuries, the draft board, rookies, leaderboards, team pages and cap sheets.

## How it works

- `pipeline/` is Python. GitHub Actions runs it every 5 minutes, writes JSON into `web/data/`, and publishes `web/` to GitHub Pages.
- `web/` is the app. It reloads its data every minute while open and can be saved to your Home Screen.
- Alerts reach your phone and computer through ntfy, plus in-app alerts while the app is open.

| Job | When | Sections |
| --- | --- | --- |
| live | every 5 minutes | scores, standings with streaks and last 10, hot and cold players, news (50+ feeds), trends, injuries |
| hourly | top of each hour | leaders, rookies, top 150, teams, salaries on team pages (stats.nba.com first, ESPN if it is blocked) |
| hourly | top of each hour | HoopsMatic contracts, cap sheets, exceptions, picks |
| daily | 09:00 UTC | HoopsHype and Spotrac fallbacks if HoopsMatic is unreachable |
| weekly | Monday 09:00 UTC | draft board with last week's rank for movement |

A section with no data yet runs its job on the next tick, so a fresh deploy fills every tab on its first run. The app also keeps the last data it saw and paints it the moment you open it, then swaps in fresh data.

The draft year and rookie class roll forward on their own. The draft cycle switches on July 10, two weeks after a late June draft.

## The draft board

- `config/draft_seed.json` is the starting board, compiled on 2026-11-08 from published 2027 mocks and big boards (ESPN, CBS Sports, Sports Illustrated, Yahoo Sports, Bleacher Report, FanSided). `web/seed/draft.json` is the same board already built, so the Draft tab is full even before the first run.
- Every Monday the pipeline reads Tankathon, NBADraft.net, ESPN, Bleacher Report, No Ceilings and your YouTube mocks, then rebuilds the board. The seed sources stay in the average for four weeks, then drop out once at least three live sources are working.
- To refresh the starting board by hand, edit `scripts/make_draft_seed.py` and run `python scripts/make_draft_seed.py`.
- College stats for prospects come from ESPN each Monday. International prospects have no stat line.

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

- Leaders, rookies and team pages use NBA.com data when it answers and ESPN when it does not. On the ESPN path, team stats are added up from player stats and only points allowed is shown for opponents.
- GitHub's fastest schedule is 5 minutes, so "every minute" is not possible on this setup. The app itself checks for new data every minute. For true one-minute polling, run `python pipeline/run_all.py` in a loop on a server.
- X and TikTok have no free public data. Trends use headlines, Reddit and Google Trends.
- Trade exceptions show the holder, size and expiry. HoopsMatic's file does not say which trade created each one.
- The HoopsMatic parsers were checked against real sample rows, but the full files could not be downloaded in the build sandbox. The ESPN stats and standings parsers, the news feeds, and the HoopsHype, Spotrac, Tankathon, NBADraft.net, Bleacher Report and No Ceilings parsers read public pages and have not been run against the live sites yet. Check the first run's log and use the manual files above if a source returns nothing.
- Per-prospect stats, measurements and injuries need `prospect_profiles.json` or table data on the source page. Headlines fill the "word on the street" line.

## Tests

`python -m pytest tests`

## Design

The look is an early 2000s sports portal: pinstripe page, brushed metal header, folder tabs, a scrolling score ticker and aqua buttons for the selected control. Type is Helvetica. Colors and sizes live at the top of `web/style.css`. `scripts/dev_fixture.py` writes made up data into `web/data` so you can preview the app offline (those files are never committed).

## Update notes (Nov 2026)
- Square corners everywhere, light mode only.
- Team logos on every player and team row (`pipeline/logos.py`, built-in table in `web/seed/logos.json`). Missing logos show initials.
- Draft tab: Cyro Asseo and Mikey Visenberg Mock Draft 2.0 and 1.0 (edit `config/cyro_mocks.json`). Team pages show each team's mock 2.0 picks.
- Contracts tab: with team since, extension eligibility, trade restriction, max contract percent, filters (`pipeline/contract_extras.py`, rules follow hoopsmatic.com/contracts).
- News: HoopsHype Rumors feed is in `pipeline/news.py`.

## If Contracts or Future Picks are empty
GitHub's servers can be blocked by hoopsmatic.com. Run `scripts/sync_hoopsmatic.sh` on your Mac (it downloads the sheets from your own connection and pushes them), then re-run the workflow.
Future draft picks (RealGM) come from `config/team_picks_raw.txt`: copy the whole page, then run `scripts/paste_picks.sh`.
Contracts come from `config/contracts_raw.txt`: on hoopsmatic.com/contracts press Cmd+A, Cmd+C, then run `pbpaste > config/contracts_raw.txt`, commit and push.
