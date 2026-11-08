"""League stats: leaders, rookies, top 30 by position, top 150, and team pages."""
import common as c
import salaries
import picks as picks_mod
import excel_import

NBA_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": c.HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}

PER_GAME_CATS = ["PTS", "REB", "AST", "STL", "BLK", "FG3M", "FG_PCT", "FG3_PCT", "FT_PCT", "TOV", "MIN"]
TOTAL_CATS = ["PTS", "REB", "AST", "STL", "BLK", "FG3M", "FGM", "FTM", "TOV", "MIN"]
PCT_MINIMUMS = {"FG_PCT": ("FGA", 5.0), "FG3_PCT": ("FG3A", 2.0), "FT_PCT": ("FTA", 2.0)}


def player_stats(per_mode, **kw):
    from nba_api.stats.endpoints import leaguedashplayerstats

    return leaguedashplayerstats.LeagueDashPlayerStats(
        season=c.season_string(), per_mode_detailed=per_mode, timeout=60, headers=NBA_HEADERS, **kw
    ).get_data_frames()[0]


def team_stats(measure):
    from nba_api.stats.endpoints import leaguedashteamstats

    return leaguedashteamstats.LeagueDashTeamStats(
        season=c.season_string(), per_mode_detailed="PerGame", measure_type_detailed_defense=measure,
        timeout=60, headers=NBA_HEADERS,
    ).get_data_frames()[0]


def player_positions():
    from nba_api.stats.endpoints import playerindex

    df = playerindex.PlayerIndex(season=c.season_string(), timeout=60, headers=NBA_HEADERS).get_data_frames()[0]
    return {int(r["PERSON_ID"]): str(r["POSITION"] or "") for _, r in df.iterrows()}


def impact(row):
    """Simple per game impact index used for consensus rankings."""
    return row["PTS"] + 0.7 * row["REB"] + 0.8 * row["AST"] + 1.2 * (row["STL"] + row["BLK"]) - 1.0 * row["TOV"] \
        + 6.0 * (row.get("FG_PCT", 0) - 0.45)


def slim(row, cat=None):
    d = {
        "id": int(row["PLAYER_ID"]), "name": row["PLAYER_NAME"], "team": row["TEAM_ABBREVIATION"],
        "gp": int(row["GP"]), "min": round(float(row["MIN"]), 1), "pts": round(float(row["PTS"]), 1),
        "reb": round(float(row["REB"]), 1), "ast": round(float(row["AST"]), 1), "stl": round(float(row["STL"]), 1),
        "blk": round(float(row["BLK"]), 1), "tov": round(float(row["TOV"]), 1),
        "fg": round(float(row["FG_PCT"]) * 100, 1), "tp": round(float(row["FG3_PCT"]) * 100, 1),
        "ft": round(float(row["FT_PCT"]) * 100, 1),
    }
    if "IMPACT" in row:
        d["impact"] = round(float(row["IMPACT"]), 1)
    return d


def build_leaders(pg, tot, positions):
    max_gp = int(pg["GP"].max()) if len(pg) else 0
    per_game, totals = {}, {}
    for cat in PER_GAME_CATS:
        df = pg
        if cat in PCT_MINIMUMS:
            col, minimum = PCT_MINIMUMS[cat]
            df = df[(df[col] >= minimum) & (df["GP"] >= max(1, max_gp * 0.5))]
        df = df.sort_values(cat, ascending=(False)).head(25)
        scale = 100 if cat.endswith("PCT") else 1
        per_game[cat] = [
            {"name": r["PLAYER_NAME"], "team": r["TEAM_ABBREVIATION"], "val": round(float(r[cat]) * scale, 1)}
            for _, r in df.iterrows()
        ]
    for cat in TOTAL_CATS:
        df = tot.sort_values(cat, ascending=False).head(25)
        totals[cat] = [
            {"name": r["PLAYER_NAME"], "team": r["TEAM_ABBREVIATION"], "val": int(r[cat])} for _, r in df.iterrows()
        ]
    qualified = pg[(pg["GP"] >= max(1, max_gp * 0.4)) & (pg["MIN"] >= 12)].copy()
    qualified["IMPACT"] = qualified.apply(impact, axis=1)
    qualified = qualified.sort_values("IMPACT", ascending=False)
    ranked = []
    for i, (_, r) in enumerate(qualified.head(150).iterrows(), 1):
        d = slim(r)
        d["rank"] = i
        d["pos"] = positions.get(int(r["PLAYER_ID"]), "")
        ranked.append(d)
    by_pos = {"G": [], "F": [], "C": []}
    for _, r in qualified.iterrows():
        pos = positions.get(int(r["PLAYER_ID"]), "")[:1].upper()
        if pos in by_pos and len(by_pos[pos]) < 30:
            d = slim(r)
            d["rank"] = len(by_pos[pos]) + 1
            d["pos"] = positions.get(int(r["PLAYER_ID"]), "")
            by_pos[pos].append(d)
    return {"perGame": per_game, "totals": totals, "top150": ranked, "byPosition": by_pos}


def build_rookies():
    df = player_stats("PerGame", player_experience_nullable="Rookie")
    df = df[df["GP"] > 0].copy()
    if df.empty:
        return {"players": [], "top15": []}
    df["IMPACT"] = df.apply(impact, axis=1)
    max_gp = int(df["GP"].max())
    eligible = df[(df["GP"] >= max(1, max_gp * 0.3)) & (df["MIN"] >= 8)]
    top = eligible.sort_values("IMPACT", ascending=False).head(15)
    players = df.sort_values("PTS", ascending=False)
    end = c.season_end_year()
    return {
        "class_label": f"{end} rookies ({c.season_string()} season)",
        "top15": [dict(slim(r), rank=i) for i, (_, r) in enumerate(top.iterrows(), 1)],
        "players": [slim(r) for _, r in players.iterrows()],
    }


def espn_standings():
    data = c.get_json("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings")
    out = []
    for conf in (data or {}).get("children", []):
        for e in conf.get("standings", {}).get("entries", []):
            stats = {}
            for s in e.get("stats", []):
                for k in (s.get("name"), s.get("shortDisplayName"), s.get("displayName")):
                    if k:
                        stats[str(k).lower()] = s.get("displayValue", "")
            t = e.get("team", {})
            logo = (t.get("logos") or [{}])[0].get("href", "")
            out.append(
                {
                    "name": t.get("displayName", ""), "abbr": t.get("abbreviation", ""), "logo": logo,
                    "conf": conf.get("name", ""),
                    "w": stats.get("wins", stats.get("w", "")), "l": stats.get("losses", stats.get("l", "")),
                    "pct": stats.get("winpercent", stats.get("pct", "")),
                    "gb": stats.get("gamesbehind", stats.get("gb", "")),
                    "seed": stats.get("playoffseed", stats.get("seed", "")),
                    "streak": stats.get("streak", stats.get("strk", "")),
                    "home": stats.get("home", ""), "away": stats.get("road", stats.get("away", "")),
                    "l10": stats.get("last ten games", stats.get("l10", "")),
                    "diff": stats.get("differential", stats.get("diff", "")),
                }
            )
    return out


def nick(name):
    return (name or "").split()[-1].lower()


def rank_cols(df, cols, ascending=()):
    out = {}
    for col in cols:
        asc = col in ascending
        out[col] = df[col].rank(ascending=asc, method="min")
    return out


def build_teams(pg, positions_by_id=None):
    positions_by_id = positions_by_id or {}
    standings = espn_standings()
    base = team_stats("Base")
    opp = team_stats("Opponent")
    base_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "FG_PCT", "FG3_PCT", "FT_PCT"]
    opp_cols = ["OPP_PTS", "OPP_REB", "OPP_AST", "OPP_FG_PCT", "OPP_FG3_PCT", "OPP_TOV"]
    base_rank = rank_cols(base, base_cols, ascending=("TOV",))
    opp_rank = rank_cols(opp, opp_cols, ascending=("OPP_PTS", "OPP_REB", "OPP_AST", "OPP_FG_PCT", "OPP_FG3_PCT"))
    sal = salaries.load()
    bio = excel_import.load_bio()
    flags = c.read_state("roster_flags", {})
    contract_info = {c.norm_name(p["name"]): p for p in c.read_data("contracts", {"players": []})["players"]}
    tradable = picks_mod.load_and_evaluate()
    teams = []
    for s in standings:
        key = nick(s["name"])
        bi = base[base["TEAM_NAME"].map(nick) == key]
        oi = opp[opp["TEAM_NAME"].map(nick) == key]
        stats, ostats = {}, {}
        if len(bi):
            i = bi.index[0]
            stats = {k: {"v": round(float(base.loc[i, k]) * (100 if k.endswith("PCT") else 1), 1), "r": int(base_rank[k][i])} for k in base_cols}
        if len(oi):
            i = oi.index[0]
            ostats = {k: {"v": round(float(opp.loc[i, k]) * (100 if k.endswith("PCT") else 1), 1), "r": int(opp_rank[k][i])} for k in opp_cols}
        abbr_rows = pg[pg["TEAM_ABBREVIATION"].isin(base[base["TEAM_NAME"].map(nick) == key]["TEAM_ABBREVIATION"])] if len(bi) else pg.iloc[0:0]
        roster = []
        for _, r in abbr_rows.sort_values("PTS", ascending=False).iterrows():
            d = slim(r)
            k = c.norm_name(r["PLAYER_NAME"])
            d["salary"] = sal.get(k)
            b = bio.get(k, {})
            d["ht"], d["wt"], d["college"] = b.get("ht"), b.get("wt"), b.get("college")
            d["pos"] = positions_by_id.get(int(r["PLAYER_ID"])) or b.get("pos") or flags.get(k, {}).get("pos", "")
            ci = contract_info.get(k)
            if ci:
                d["contract_end"], d["option"] = ci["end"], ci["option"]
            if flags.get(k, {}).get("headshot"):
                d["headshot"] = flags[k]["headshot"]
            roster.append(d)
        teams.append(dict(s, stats=stats, opp=ostats, players=roster, picks=tradable.get(s["name"], {"tradable": [], "locked": []})))
    teams.sort(key=lambda t: (t["conf"], int(t["seed"]) if str(t["seed"]).isdigit() else 99))
    return teams


def run():
    try:
        pg = player_stats("PerGame")
        tot = player_stats("Totals")
        positions = player_positions()
    except Exception as exc:  # stats.nba.com often blocks cloud IPs
        print("stats.nba.com unavailable:", exc)
        return
    leaders = build_leaders(pg, tot, positions)
    c.write_data("leaders", leaders)
    c.write_data("rookies", build_rookies())
    try:
        c.write_data("teams", {"teams": build_teams(pg, positions)})
    except Exception as exc:
        print("team build failed:", exc)


if __name__ == "__main__":
    run()
