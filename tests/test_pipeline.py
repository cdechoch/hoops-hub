import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "pipeline"))

import cap, draft, injuries, news, picks, scores  # noqa: E402


def team(name, abbr, score, home):
    return {"homeAway": "home" if home else "away", "score": str(score), "team": {"displayName": name, "abbreviation": abbr, "logo": ""}}


def test_scoreboard_filters_college_to_followed_teams():
    data = {"events": [
        {"id": "1", "date": "2026-11-07T20:00Z", "status": {"type": {"state": "in", "shortDetail": "2nd Half"}, "period": 2},
         "competitions": [{"competitors": [team("Kansas Jayhawks", "KU", 40, False), team("Iowa State Cyclones", "ISU", 38, True)]}]},
        {"id": "2", "date": "2026-11-07T20:00Z", "status": {"type": {"state": "in"}},
         "competitions": [{"competitors": [team("Duke Blue Devils", "DUKE", 10, False), team("UNC Tar Heels", "UNC", 8, True)]}]},
    ]}
    games = scores.parse_scoreboard("KU/UM Basketball", data)
    assert [g["id"] for g in games] == ["1"] and games[0]["followed"] == ["ku"]
    assert len(scores.parse_scoreboard("NBA", data)) == 2


def test_boxscore_hot_and_cold():
    labels = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF", "+/-"]
    hot = ["36", "38", "14-22", "4-8", "6-6", "9", "7", "2", "1", "1", "1", "8", "2", "+12"]
    cold = ["30", "2", "1-12", "0-5", "0-0", "2", "1", "4", "0", "0", "0", "2", "3", "-14"]
    summ = {"boxscore": {"players": [{"team": {"abbreviation": "MIA"}, "statistics": [{"labels": labels, "athletes": [
        {"athlete": {"displayName": "Star Guy"}, "stats": hot}, {"athlete": {"displayName": "Cold Guy"}, "stats": cold}]}]}]}}
    out = scores.parse_boxscore(summ)
    tags = {p["name"]: p["tag"] for p in out}
    assert tags == {"Star Guy": "hot", "Cold Guy": "cold"}


def test_events_fire_on_start_and_final():
    g = {"id": "9", "league": "NBA", "sport": "nba", "state": "post", "period": 4, "detail": "Final", "followed": [],
         "home": {"abbr": "MIA", "score": 100}, "away": {"abbr": "BOS", "score": 98}}
    assert [e[0] for e in scores.detect_events([g], {"9": {"state": "in"}})] == ["Final: BOS at MIA"]
    g["state"] = "in"
    assert [e[0] for e in scores.detect_events([g], {"9": {"state": "pre"}})][0].startswith("Starting now")


def test_injuries_parse():
    data = {"injuries": [{"displayName": "Miami Heat", "injuries": [
        {"athlete": {"displayName": "A Player"}, "status": "Out", "shortComment": "Out two weeks",
         "details": {"type": "Ankle", "returnDate": "2026-11-20"}}]}]}
    t = injuries.parse(data)
    assert t[0]["players"][0]["return"] == "2026-11-20" and t[0]["players"][0]["injury"] == "Ankle"


def test_news_scoring_clusters_same_story():
    items = [
        {"title": "Lakers trade for star guard in blockbuster deal", "source": "ESPN", "published": "2099-01-01T00:00:00+00:00", "engage": 0, "url": "a", "id": "a"},
        {"title": "Lakers acquire star guard in blockbuster trade deal", "source": "HoopsHype", "published": "2099-01-01T00:00:00+00:00", "engage": 0, "url": "b", "id": "b"},
        {"title": "Unrelated preseason note about hydration", "source": "RealGM", "published": "2099-01-01T00:00:00+00:00", "engage": 0, "url": "c", "id": "c"},
    ]
    out = news.score_items(items)
    assert out[0]["outlets"] == 2 and out[2]["outlets"] == 1 and out[0]["hot"] > out[2]["hot"]


def test_stepien_locks_consecutive_firsts():
    full = [{"year": y, "round": 1, "from": "own"} for y in range(2027, 2034)]
    res = picks.evaluate_team(full, 2027)
    assert len(res["tradable"]) == 7 and not res["locked"]
    traded_2028 = [p for p in full if p["year"] != 2028]
    res2 = picks.evaluate_team(traded_2028, 2027)
    locked = {p["year"]: p["reason"] for p in res2["locked"]}
    assert locked.get(2027) == "Stepien rule" and locked.get(2029) == "Stepien rule"
    assert 2031 in {p["year"] for p in res2["tradable"]}
    beyond = picks.evaluate_team([{"year": 2040, "round": 1, "from": "own"}], 2027)
    assert beyond["locked"][0]["reason"] == "More than seven drafts away"


def test_draft_aggregate_and_youtube_lines():
    per = {"A": [{"name": "Player One"}, {"name": "Player Two"}], "Cyro Asseo": [{"name": "Player Two"}, {"name": "Player One"}]}
    board = draft.aggregate(per, {"Cyro Asseo": 1.5}, {"missing_rank": 80, "missing_weight": 0.5, "default_weight": 1.0})
    assert [e["name"] for e in board] == ["Player Two", "Player One"]
    m = draft.YT_LINE.match("1. Darryn Peterson - Kansas")
    assert m and m.group(2) == "Darryn Peterson" and m.group(3) == "Kansas"


def test_cap_money_and_table():
    assert cap.money("$155,300,000") == 155300000 and cap.money("($4,000,000)") == -4000000
    html = "<table><tr><th>Team</th><th>Total Cap</th></tr>" + "".join(f"<tr><td>T{i}</td><td>$150,000,000</td></tr>" for i in range(30)) + "</table>"
    assert len(cap.league_table(html)) == 30


# ---------- HoopsMatic and workbook imports ----------
import csv, io  # noqa: E402
import excel_import, hoopsmatic  # noqa: E402

CONTRACTS = '''PLAYER,,TEAM,RAT 365,2025,CH 24-25,ST 24-25,2026,CH 25-26,ST 25-26,2027,CH 26-27,ST 26-27,2028,CH 27-28,ST 27-28,2029,CH 28-29,ST 28-29,2030,CH 29-30,ST 29-30,2031,CH 30-31,ST 30-31,TOTAL GUARANTEED (with 2024-25),OPTION,END,TOTAL GUARANTEED,LAST SIGNING DATE,SIGNING TEAM,EXCEPTION,OTHER NOTES,TRADE KICKER,LIKELY BONUS,UNLIKELY BONUS,GUARANTEE,% GUARANTEE,YOS,,PLAYER / COACH,AWARD,YEAR,,AWARD,,2031,CH 31-32,ST 31-32
Jalen Johnson,,Atlanta,17.92,"$4,510,905","$4,510,905",GUARANTEED,"$30,000,000","$30,000,000",GUARANTEED,"$30,000,000","$30,000,000",GUARANTEED,"$30,000,000","$30,000,000",GUARANTEED,"$30,000,000","$30,000,000",GUARANTEED,"$30,000,000","$30,000,000",GUARANTEED,,,,"$154,510,905",,2030,"$120,000,000",10/21/2024,Atlanta,Bird Exception,Rookie Scale Extension,,,,,,5,,Alonzo Mourning,All-Defensive First Team,2000,,All-Defensive First Team
'''


def test_contracts_parse_uses_current_year_columns():
    rows = list(csv.reader(io.StringIO(CONTRACTS)))
    out = hoopsmatic.parse_contracts(rows)
    assert out[0]["name"] == "Jalen Johnson" and out[0]["team"] == "Atlanta"
    assert out[0]["years"][0] == {"y": "2026-27", "sal": 30000000, "ch": 30000000, "st": "GUARANTEED"}
    assert out[0]["end"] == "2030" and out[0]["exception"] == "Bird Exception" and out[0]["total"] == 120000000


def test_exceptions_parse():
    text = ',CAP,TAX,MLE TYPE,MLE,,,,,BAE\nAtlanta,"-$30,802,307","$4,664,693",Non-taxpayer,"$944,000",Jock Landale,"$14,100,000",,,"$5,477,000"\n'
    out = hoopsmatic.parse_exceptions(list(csv.reader(io.StringIO(text))))
    a = out["Atlanta"]
    assert a["cap_space"] == -30802307 and a["tax_room"] == 4664693 and a["mle_type"] == "Non-taxpayer"
    assert a["mle_used_on"] == [{"player": "Jock Landale", "amount": 14100000}] and a["bae"] == 5477000


def test_roster_parse_team_block_tpes_and_picks():
    def row(**cols):
        r = [""] * 80
        for k, v in cols.items():
            r[int(k[1:])] = v
        return r
    hdr = [""] * 80
    r1 = row(c0="Jalen Johnson", c2="Atlanta", c34="Atlanta", c51="$195,763,321", c52="-$30,802,307", c53="$4,664,693", c54="$12,055,431",
             c55="HC 1st", c56="$24,726,431", c58="BELOW TAX", c60="Philadelphia", c61="07/30/2027", c62="$2,150,917",
             c64="Atlanta", c65="1st", c66="2027", c68="Own pick", c25="http://x/h.png", c26="SF")
    out = hoopsmatic.parse_roster([hdr, r1])
    t = out["teams"]["Atlanta"]
    assert t["payroll"] == 195763321 and t["cap_space"] == -30802307 and t["second_apron_room"] == 24726431
    assert out["tpes"] == [{"team": "Philadelphia", "expires": "07/30/2027", "value": 2150917}]
    assert hoopsmatic.picks_for_rules(out["picks"])["Atlanta"][0] == {"year": 2027, "round": 1, "from": "own", "protection": "Own pick"}
    assert out["players"]["jalen johnson"]["headshot"] == "http://x/h.png"


def test_hoopsmatic_draft_parse_and_staleness():
    hdr = ["", "AGG RANK", "ESPN", "NBADraft", "CBS Sports", "Athletic", "Bleacher", "Babcock", "The Ringer", "HoopsHQ", "SB Nation", "USAT", "Yahoo!"] + [""] * 34
    r = ["AJ Dybantsa", "1"] + ["1"] * 10 + ["1/29/2007"] + [""] * 33
    r2 = [""] * 26 + ["AJ Dybantsa", "1/29/2007", "7234", ".", "United States"] + [""] * 5 + ["SF", "BYU", "YES", "YES"]
    out = hoopsmatic.parse_draft([hdr, r, r2])
    p = out["players"][0]
    assert p["agg"] == 1 and p["ranks"]["ESPN"] == 1 and p["profile"]["school"] == "BYU"
    # the workbook says this player was drafted in 2026, so a 2027 cycle must treat the board as stale
    assert draft.hoopsmatic_is_current(out, 2027) is False


def test_bio_height_repair():
    import datetime as dt
    assert excel_import.height_from_excel(dt.datetime(2026, 6, 9)) == "6-9"
    assert excel_import.height_from_excel("2026-06-10 00:00:00") == "6-10"


# ---------- standings, ESPN stats fallback, news summaries, trending fill, draft seed ----------
import espn_stats, standings, trends  # noqa: E402


def test_streak_and_last10_parsing():
    assert standings.streak_value("W4") == 4 and standings.streak_value("L2") == -2 and standings.streak_value("") == 0
    assert standings.record_wins("7-3") == 7
    data = {"children": [{"name": "Eastern Conference", "standings": {"entries": [{"team": {"id": "2", "displayName": "Boston Celtics", "abbreviation": "BOS"},
            "stats": [{"name": "wins", "displayValue": "11"}, {"name": "losses", "displayValue": "3"}, {"name": "streak", "displayValue": "W5"},
                      {"name": "lasttengames", "displayName": "Last Ten Games", "displayValue": "8-2"}, {"name": "playoffseed", "displayValue": "1"}]}]}}]}
    t = standings.parse(data)[0]
    assert t["conf"] == "Eastern" and t["streak"] == "W5" and t["l10"] == "8-2" and t["seed"] == "1" and t["w"] == "11"


def test_form_from_schedule_when_standings_lack_it(monkeypatch):
    def ev(day, win):
        return {"date": f"2026-11-{day:02d}T00:00Z", "competitions": [{"status": {"type": {"completed": True}},
                "competitors": [{"id": "2", "winner": win, "team": {"id": "2"}}, {"id": "9", "winner": not win, "team": {"id": "9"}}]}]}
    sched = {"events": [ev(d, d != 3) for d in range(1, 8)]}
    monkeypatch.setattr(standings.c, "get_json", lambda *a, **k: sched)
    form = standings.form_from_schedule("2")
    assert form == {"l10": "6-1", "streak": "W4"}


def test_espn_player_parse_and_roster():
    page = {"categories": [{"name": "general", "names": ["gamesPlayed", "avgMinutes", "avgRebounds"]},
                           {"name": "offensive", "names": ["avgPoints", "avgFieldGoalsMade", "avgFieldGoalsAttempted", "fieldGoalPct", "avgAssists"]}],
            "athletes": [{"athlete": {"id": "1", "displayName": "Test Guard", "teamShortName": "NYK", "position": {"abbreviation": "PG"}},
                          "categories": [{"name": "general", "values": [10, 32.5, 4.0]}, {"name": "offensive", "values": [25.1, 9.0, 18.0, 50.0, 7.2]}]}]}
    per, tot = espn_stats.parse_players([page])
    assert per[0]["PTS"] == 25.1 and per[0]["FG_PCT"] == 0.5 and per[0]["GP"] == 10 and tot[0]["PTS"] == 251
    roster = espn_stats.parse_roster({"athletes": [{"id": "1", "displayName": "Test Guard", "position": {"abbreviation": "PG"}, "displayHeight": "6' 3\"",
                                                    "displayWeight": "195 lbs", "experience": {"years": 0}, "college": {"name": "Kansas"}}]})
    assert roster[0]["ht"] == "6-3" and roster[0]["wt"] == 195 and roster[0]["rookie"] is True and roster[0]["college"] == "Kansas"


def test_team_stats_from_players():
    import pandas as pd
    pg = pd.DataFrame([{"PLAYER_ID": 1, "GP": 10, "PTS": 20.0, "REB": 5.0, "AST": 4.0, "STL": 1.0, "BLK": 0.5, "TOV": 2.0, "FGM": 8.0, "FGA": 16.0, "FG3M": 2.0, "FG3A": 5.0, "FTM": 2.0, "FTA": 2.0},
                       {"PLAYER_ID": 2, "GP": 10, "PTS": 10.0, "REB": 3.0, "AST": 2.0, "STL": 0.5, "BLK": 0.5, "TOV": 1.0, "FGM": 4.0, "FGA": 10.0, "FG3M": 1.0, "FG3A": 3.0, "FTM": 1.0, "FTA": 2.0}])
    s = espn_stats.team_stats_from_players(pg, {1, 2}, 10)
    assert s["PTS"] == 30.0 and round(s["FG_PCT"], 3) == round(12 / 26, 3) and s["TOV"] == 3.0


def test_news_summary_and_basketball_filter():
    s = news.first_sentence("<p>The Lakers signed a guard to a two-way deal on Friday. Read more here.</p> The post X appeared first on Y.", "Lakers sign guard")
    assert s == "The Lakers signed a guard to a two-way deal on Friday."
    assert news.first_sentence("Lakers sign guard to deal", "Lakers sign guard to deal") == ""  # adds nothing beyond the headline
    assert news.is_basketball("Knicks beat Celtics in overtime") and not news.is_basketball("Chiefs beat Bills in NFL thriller")
    assert all(u.startswith("http") for u, _ in news.FEEDS.values()) and len(news.FEEDS) >= 45


def test_trending_quiet_hour_is_filled_from_wider_window():
    import datetime as dt
    now = c_now = trends.c.now()
    ents = {"lakers": ("Los Angeles Lakers", "team"), "lebron james": ("LeBron James", "player")}
    items = [{"title": "Lakers win", "source": "ESPN", "published": (now - dt.timedelta(hours=3)).isoformat(), "engage": 0},
             {"title": "LeBron James hurt", "source": "HoopsHype", "published": (now - dt.timedelta(minutes=20)).isoformat(), "engage": 0}]
    keys = sorted(ents, key=len, reverse=True)
    one = trends.score_window(items, ents, keys, now, 1, [], {})
    four = trends.score_window(items, ents, keys, now, 4, [], {})
    assert [r["name"] for r in trends.rows_from(one)] == ["LeBron James"] and len(four) == 2
    assert all(r["earlier"] for r in trends.rows_from(four, earlier=True))


def test_draft_seed_board_builds_without_network():
    seed = draft.c.read_config("draft_seed.json", {})
    per = {}
    profiles = draft.add_seed(per, seed["cycle"])
    assert len(per) == 6 and profiles["tyran stokes"]["school"] == "Kansas"
    board = draft.aggregate(per, {}, draft.CFG)
    assert board[0]["name"] == "Tyran Stokes" and len(board) >= 70


def test_logo_keys_and_mocks():
    import json, logos
    assert logos.key("LA Clippers") == logos.key("la-clippers")
    got = logos.build({"sports": [{"leagues": [{"teams": [{"team": {"displayName": "Kansas Jayhawks", "location": "Kansas", "abbreviation": "KU", "logos": [{"href": "u.png"}]}}]}]}]})
    assert got["kansas"] == got["ku"] == got["kansasjayhawks"] == "u.png"
    m = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "cyro_mocks.json").read_text())
    assert len(m["v1"]["picks"]) == 30 and len(m["v2"]["picks"]) == 30 and m["v2"]["picks"][0]["team"] == "New Orleans Pelicans"


def test_contract_extension_and_trade_rules():
    import datetime as dt, contract_extras as x
    today = dt.date(2026, 11, 8)
    yrs = lambda n, st="GUARANTEED": [{"sal": 10e6 if i < n else None, "st": st if i < n else ""} for i in range(7)]
    base = dict(team="Miami Heat", notes="", end="2029", sig="7/1/2025", draft_year=0, awards=[], recent=2025, yos=5, dv_awards=[], dv=False, ntc="", restriction="")
    four_year = dict(base, yrs=yrs(4))
    assert x.ext_elig(four_year, today)["status"] == "future"  # 4 year deal waits until the 2nd anniversary
    assert x.max_pct(dict(base, yos=8)) == 30 and x.max_pct(dict(base, yos=3)) == 25
    fresh = dict(base, sig="7/6/2026", end="2030", yrs=yrs(4))
    assert x.trade_status(fresh, today)["type"] == "restricted"
    assert x.trade_status(dict(base, ntc="Yes", yrs=yrs(4)), today)["type"] == "ntc"


def test_team_picks_parse():
    import team_picks
    txt = "Atlanta Hawks Future NBA Draft Picks\nYear \tFirst Round \tSecond Round\n\n2027\n\t\n\nTo SAN;\n\nLess favorable of MIL and NOP (via NOP)\n\n1\n\t\n\n31-55 Own;\n56-60 to DAL\n\n1\n"
    got = team_picks.parse(txt)["Atlanta Hawks"][0]
    assert got["year"] == 2027 and got["r1"]["items"] == ["To SAN", "Less favorable of MIL and NOP (via NOP)"] and got["r2"]["items"][1] == "56-60 to DAL" and got["r2"]["count"] == "1"


def test_contracts_page_parse():
    import contracts_page as cp
    txt = ("Intro\n\nJalen Johnson\n\t\nAtlanta\n\t$30.0M\t$30.0M\t$13.1MTO\t—\t—\t—\t2030CH: $45.0M\t\t$120.0M\tBird\t10/21/2024\tAtlanta\t2021-22\t\tDec 15, 2026\t\t\tOct 1, 2027Designated Veteran\n"
           "Reece Beekman\n\t\nWashington\n\t$679K\t—\t—\t—\t—\t—\t2027CH: $2.3M\t\t\t\t10/17/2026\tWashington\t2026-27\t\tExpiring\t\t\tStandard Contract Conversion Eligible\n")
    a, b = cp.parse(txt)
    assert a["team"] == "Atlanta" and a["years"][2]["st"] == "TEAM OPTION" and a["since"] == "2021-22" and a["dv"] and a["ext"]["status"] == "future"
    assert a["trade"]["type"] == "restricted" and b["trade"]["type"] == "expiring" and b["ext"]["status"] == "na" and b["years"][0]["sal"] == 679000


def test_team_picks_csv():
    import pathlib, team_picks
    got = team_picks.parse_csv((pathlib.Path(__file__).resolve().parent.parent / "config" / "team_picks.csv").read_text(encoding="utf-8"))
    assert len(got) == 30 and all(len(v) == 7 for v in got.values())
    atl = got["Atlanta Hawks"][0]
    assert atl["year"] == 2027 and atl["r1"]["items"][0] == "To SAN" and atl["r2"]["items"][1] == "56-60 to DAL" and atl["r2"]["count"] == "1"
    det33 = got["Detroit Pistons"][-1]["r2"]
    assert det33["count"] == "1" and "LAC" in det33["items"][0]
