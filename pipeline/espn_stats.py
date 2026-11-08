"""ESPN replacement for stats.nba.com, which blocks GitHub's servers.

Gives player per game and total stats, rosters (position, height, weight, experience), and team stats
built from the players. Output uses the same column names as nba_api so league.py works on either.
"""
import re

import pandas as pd

import common as c

BY_ATHLETE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/{league}/statistics/byathlete"
ROSTER = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{id}/roster"


def _num(v, default=0.0):
    try:
        if v is None or v == "" or v == "--":
            return default
        return float(str(v).replace(",", "").replace("%", ""))
    except ValueError:
        return default


def _pick(d, *names, default=None):
    low = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n.lower() in low and low[n.lower()] not in (None, ""):
            return low[n.lower()]
    return default


def _pct(v):
    x = _num(v)
    return x / 100.0 if x > 1.5 else x


def flatten_athlete(entry, cat_defs):
    """Merge every category of one athlete into one dict keyed by ESPN stat name."""
    flat = {}
    defs = {d.get("name"): d for d in cat_defs}
    for cat in entry.get("categories", []):
        d = defs.get(cat.get("name")) or {}
        names = d.get("names") or []
        vals = cat.get("values") or cat.get("totals") or []
        for n, v in zip(names, vals):
            flat[n] = v
    return flat


def parse_players(pages):
    """pages: list of ESPN byathlete JSON documents. Returns (per game rows, total rows)."""
    per, tot = [], []
    for data in pages:
        defs = data.get("categories") or []
        for e in data.get("athletes", []):
            a = e.get("athlete", {})
            s = flatten_athlete(e, defs)
            gp = int(_num(_pick(s, "gamesPlayed", "gp")))
            if gp <= 0 or not a.get("id"):
                continue
            pos = a.get("position")
            pos = (pos.get("abbreviation") if isinstance(pos, dict) else pos) or ""
            base = {
                "PLAYER_ID": int(a["id"]), "PLAYER_NAME": a.get("displayName", ""),
                "TEAM_ABBREVIATION": a.get("teamShortName") or a.get("teamName") or "", "POS": pos, "GP": gp,
            }
            g = lambda *n: _num(_pick(s, *n))
            row = dict(
                base, MIN=g("avgMinutes", "minutesPerGame"), PTS=g("avgPoints", "pointsPerGame"),
                REB=g("avgRebounds", "reboundsPerGame"), AST=g("avgAssists", "assistsPerGame"),
                STL=g("avgSteals", "stealsPerGame"), BLK=g("avgBlocks", "blocksPerGame"),
                TOV=g("avgTurnovers", "turnoversPerGame"),
                FGM=g("avgFieldGoalsMade"), FGA=g("avgFieldGoalsAttempted"),
                FG3M=g("avgThreePointFieldGoalsMade"), FG3A=g("avgThreePointFieldGoalsAttempted"),
                FTM=g("avgFreeThrowsMade"), FTA=g("avgFreeThrowsAttempted"),
                FG_PCT=_pct(_pick(s, "fieldGoalPct")), FG3_PCT=_pct(_pick(s, "threePointFieldGoalPct", "threePointPct")),
                FT_PCT=_pct(_pick(s, "freeThrowPct")),
            )
            per.append(row)
            exact = lambda total_name, avg: _num(_pick(s, total_name), default=None)
            t = dict(base)
            for col, tname in (("PTS", "points"), ("REB", "rebounds"), ("AST", "assists"), ("STL", "steals"), ("BLK", "blocks"),
                               ("TOV", "turnovers"), ("FG3M", "threePointFieldGoalsMade"), ("FGM", "fieldGoalsMade"), ("FTM", "freeThrowsMade")):
                v = _num(_pick(s, tname, "total" + tname[0].upper() + tname[1:]), default=None)
                t[col] = round(v) if v is not None else round(row[col] * gp)
            t["MIN"] = round(row["MIN"] * gp)
            t["GP"] = gp
            tot.append(t)
    return per, tot


def fetch_players(season_end, league="nba", max_pages=6):
    """league: "nba" or "mens-college-basketball"."""
    pages, page = [], 1
    while page <= max_pages:
        data = c.get_json(
            BY_ATHLETE.format(league=league),
            params={"region": "us", "lang": "en", "contentorigin": "espn", "isqualified": "false", "limit": 200,
                    "page": page, "sort": "offensive.avgPoints:desc", "season": season_end, "seasontype": 2},
        )
        if not data or not data.get("athletes"):
            break
        pages.append(data)
        if len(data["athletes"]) < 200:
            break
        page += 1
    per, tot = parse_players(pages)
    if not per:
        raise RuntimeError("ESPN returned no player stats")
    return pd.DataFrame(per), pd.DataFrame(tot)


def height_text(a):
    h = a.get("displayHeight") or ""
    m = re.match(r"\s*(\d+)'\s*(\d+)", h)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    inches = _num(a.get("height"), default=None)
    if inches:
        return f"{int(inches // 12)}-{int(round(inches % 12))}"
    return ""


def parse_roster(data):
    out = []
    for a in (data or {}).get("athletes", []):
        if isinstance(a, dict) and "items" in a:  # some responses group by position
            out.extend(parse_roster({"athletes": a["items"]}))
            continue
        pos = a.get("position")
        pos = (pos.get("abbreviation") if isinstance(pos, dict) else pos) or ""
        exp = a.get("experience") or {}
        years = exp.get("years")
        rookie = years == 0 or str(exp.get("displayValue", "")).upper() in ("R", "ROOKIE")
        college = a.get("college")
        out.append(
            {
                "id": int(a["id"]) if str(a.get("id", "")).isdigit() else None,
                "name": a.get("displayName") or a.get("fullName") or "",
                "pos": pos, "ht": height_text(a),
                "wt": int(_num(re.sub(r"[^\d.]", "", str(a.get("displayWeight") or a.get("weight") or "")))) or None,
                "rookie": rookie, "years": years,
                "college": (college.get("name") if isinstance(college, dict) else college) or "",
                "headshot": (a.get("headshot") or {}).get("href", "") if isinstance(a.get("headshot"), dict) else "",
            }
        )
    return out


def fetch_rosters(team_ids):
    """{team_id: [player dicts]} for every team that answers."""
    out = {}
    for tid in team_ids:
        data = c.get_json(ROSTER.format(id=tid))
        players = parse_roster(data)
        if players:
            out[str(tid)] = players
    return out


def team_stats_from_players(per_df, roster_ids, games):
    """Per game team totals built from player averages. roster_ids: ids on the team, games: team games played."""
    d = per_df[per_df["PLAYER_ID"].isin(roster_ids)]
    if d.empty or not games:
        return {}
    tot = lambda col: float((d[col] * d["GP"]).sum())
    safe = lambda a, b: (a / b) if b else 0.0
    return {
        "PTS": tot("PTS") / games, "REB": tot("REB") / games, "AST": tot("AST") / games, "STL": tot("STL") / games,
        "BLK": tot("BLK") / games, "TOV": tot("TOV") / games,
        "FG_PCT": safe(tot("FGM"), tot("FGA")), "FG3_PCT": safe(tot("FG3M"), tot("FG3A")), "FT_PCT": safe(tot("FTM"), tot("FTA")),
    }
