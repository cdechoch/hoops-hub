"""DEV ONLY. Writes made-up sample data into web/data so the UI can be previewed offline. The folder is gitignored."""
import json, pathlib, random, datetime as dt

random.seed(7)
D = pathlib.Path(__file__).resolve().parent.parent / "web" / "data"
D.mkdir(parents=True, exist_ok=True)
now = dt.datetime.now(dt.timezone.utc)
iso = lambda m=0: (now - dt.timedelta(minutes=m)).isoformat(timespec="seconds")
w = lambda n, o: (D / f"{n}.json").write_text(json.dumps(dict(o, updated=iso(6))))

EAST = ["Boston Celtics", "New York Knicks", "Cleveland Cavaliers", "Orlando Magic", "Miami Heat", "Atlanta Hawks", "Milwaukee Bucks", "Detroit Pistons",
        "Philadelphia 76ers", "Toronto Raptors", "Charlotte Hornets", "Chicago Bulls", "Indiana Pacers", "Brooklyn Nets", "Washington Wizards"]
WEST = ["Oklahoma City Thunder", "San Antonio Spurs", "Houston Rockets", "Denver Nuggets", "Los Angeles Lakers", "Minnesota Timberwolves", "Golden State Warriors",
        "Phoenix Suns", "LA Clippers", "Memphis Grizzlies", "Dallas Mavericks", "Portland Trail Blazers", "Sacramento Kings", "Utah Jazz", "New Orleans Pelicans"]
ab = lambda n: "".join(x[0] for x in n.split())[:3].upper()
teams = []
for conf, names in (("East", EAST), ("West", WEST)):
    for i, n in enumerate(names, 1):
        wn = 12 - i // 2 + random.randint(0, 1); l = 4 + i // 2
        st = random.choice([-5, -3, -2, -1, 1, 2, 3, 4, 6])
        l10w = max(1, min(9, 5 + st // 2 + random.randint(-1, 1)))
        teams.append({"id": str(len(teams) + 1), "name": n, "abbr": ab(n), "logo": "", "conf": conf, "w": str(wn), "l": str(l), "pct": f"{wn/(wn+l):.3f}",
                      "gb": "-" if i == 1 else f"{i/2:.1f}", "seed": str(i), "streak": ("W" if st > 0 else "L") + str(abs(st)), "streakN": st,
                      "home": f"{wn//2+1}-{l//2}", "away": f"{wn//2}-{l//2+1}", "l10": f"{l10w}-{10-l10w}", "l10w": l10w, "diff": f"{(8-i)*0.9:+.1f}",
                      "ppg": "114.2", "oppg": "110.8"})
w("standings", {"teams": teams})

def team(n, sc, rec): return {"name": n, "abbr": ab(n), "logo": "", "score": sc, "record": rec, "winner": False}
games = [
    {"id": "1", "league": "Kansas Basketball", "sport": "cbb", "state": "in", "detail": "2nd Half 8:41", "start": iso(80), "followed": ["ku"], "performers": [],
     "home": team("Kansas Jayhawks", 61, "2-0"), "away": team("Fordham Rams", 44, "1-1")},
    {"id": "2", "league": "Miami Football", "sport": "cfb", "state": "pre", "detail": "", "start": iso(-180), "followed": ["um"], "performers": [],
     "home": team("Miami Hurricanes", 0, "8-1"), "away": team("Syracuse Orange", 0, "4-5")},
    {"id": "3", "league": "NBA", "sport": "nba", "state": "in", "detail": "Q3 5:12", "start": iso(100), "followed": [],
     "performers": [{"name": "Jalen Brunson", "team": "NYK", "tag": "hot", "line": "31 pts, 4 reb, 8 ast on 11-19 FG"}, {"name": "Jaylen Brown", "team": "BOS", "tag": "cold", "line": "3 pts, 2 reb, 1 ast on 1-11 FG"}],
     "home": team("New York Knicks", 78, "10-4"), "away": team("Boston Celtics", 71, "11-3")},
    {"id": "4", "league": "NBA", "sport": "nba", "state": "post", "detail": "Final", "start": iso(260), "followed": [], "performers": [{"name": "Nikola Jokic", "team": "DEN", "tag": "hot", "line": "27 pts, 14 reb, 12 ast on 10-16 FG"}],
     "home": dict(team("Denver Nuggets", 118, "9-5"), winner=True), "away": team("Utah Jazz", 104, "5-9")},
    {"id": "5", "league": "NBA", "sport": "nba", "state": "pre", "detail": "", "start": iso(-120), "followed": [], "performers": [],
     "home": team("Los Angeles Lakers", 0, "8-5"), "away": team("Miami Heat", 0, "9-4")},
]
w("scores", {"games": games})

news = []
srcs = ["HoopsHype", "ESPN", "RealGM", "HoopsRumors", "ClutchPoints", "SLAM", "CBS Sports", "Hoops Habit", "Eurohoops"]
titles = ["Knicks extend Brunson's hot start with road win over Celtics", "Report: Heat open to moving veteran guard before the deadline", "Kansas freshman Tyran Stokes posts 15 in rout of Fordham",
          "Nuggets lean on Jokic as Utah slides again", "League fines two teams for resting players on national TV", "Spurs lock in extension talks with their young core",
          "Lakers weighing rotation changes after back to back", "Pelicans list forward as out two weeks with ankle sprain", "Mock draft roundup: who is climbing after week one",
          "Thunder remain the team to beat in the West", "Bucks sign veteran big on a minimum deal", "EuroLeague: Baskonia guard Stefan Joksimovic continues rise"]
for i, t in enumerate(titles * 3):
    news.append({"id": f"n{i}", "title": t + ("" if i < 12 else f" ({i})"), "url": "https://example.com/" + str(i), "source": srcs[i % len(srcs)], "published": iso(8 + i * 17),
                 "engage": 0, "outlets": 1 + (i % 4 == 0) * 2, "hot": round(30 / (1 + i / 3), 2),
                 "summary": "" if i % 7 == 3 else "A short summary of the story that gives the reader the key fact in a single sentence so they can decide whether to open it."})
w("news", {"items": news})

w("trends", {"google": [], "windows": {
    "1h": [{"name": "Jalen Brunson", "kind": "player", "news": 3, "reddit": 2, "trends": 0, "game": "hot", "score": 14.5, "earlier": False},
           {"name": "New York Knicks", "kind": "team", "news": 4, "reddit": 1, "trends": 0, "game": "", "score": 9.5, "earlier": False}] +
          [{"name": n, "kind": "player", "news": 1, "reddit": 0, "trends": 0, "game": "", "score": round(4 - i * .3, 1), "earlier": True} for i, n in enumerate(["Nikola Jokic", "Tyrese Haliburton", "Victor Wembanyama", "Jayson Tatum", "Anthony Edwards", "Luka Doncic", "Cooper Flagg", "Shai Gilgeous-Alexander"])],
    "4h": [{"name": "Heat", "kind": "team", "news": 5, "reddit": 3, "trends": 1, "game": "", "score": 18, "earlier": False}] * 1,
    "24h": [{"name": "Cooper Flagg", "kind": "player", "news": 9, "reddit": 6, "trends": 1, "game": "", "score": 30, "earlier": False}]}})

w("injuries", {"teams": [{"team": "Miami Heat", "players": [{"name": "Tyler Herro", "status": "Day-To-Day", "injury": "Left ankle soreness", "return": "", "note": "Questionable tonight", "date": "2026-11-07"}]},
                          {"team": "Boston Celtics", "players": [{"name": "Jayson Tatum", "status": "Out", "injury": "Right Achilles recovery", "return": "2026-12-01", "note": "", "date": "2026-11-01"}]}]})

stat = lambda n, t, r, g=10: {"id": r, "name": n, "team": t, "gp": g, "min": 31.2, "pts": 20.1 - r * .3, "reb": 5.4, "ast": 4.2, "stl": 1.1, "blk": .6, "tov": 2.1, "fg": 47.2, "tp": 36.1, "ft": 82.3, "rank": r}
names = ["Shai Gilgeous-Alexander", "Luka Doncic", "Nikola Jokic", "Jalen Brunson", "Victor Wembanyama", "Anthony Edwards", "Jayson Tatum", "Tyrese Maxey", "Cade Cunningham", "Donovan Mitchell"] * 3
top = [stat(n, "NYK", i + 1) for i, n in enumerate(names)]
w("leaders", {"perGame": {"PTS": [{"name": n, "team": "OKC", "val": round(33 - i * .8, 1)} for i, n in enumerate(names[:12])], "REB": [{"name": n, "team": "SAS", "val": round(13 - i * .3, 1)} for i, n in enumerate(names[:12])]},
              "totals": {"PTS": [{"name": n, "team": "OKC", "val": 400 - i * 9} for i, n in enumerate(names[:12])]}, "top150": top, "byPosition": {"G": top[:10], "F": top[:10], "C": top[:10]}})
w("rookies", {"class_label": "2027 rookies (2026-27 season)", "top15": [dict(stat(n, "DAL", i + 1, 9), rank=i + 1) for i, n in enumerate(["Cooper Flagg", "Dylan Harper", "Ace Bailey", "VJ Edgecombe", "Kon Knueppel"])],
              "players": [stat(n, "DAL", 0, 9) for n in ["Cooper Flagg", "Dylan Harper", "Ace Bailey", "VJ Edgecombe", "Kon Knueppel", "Tre Johnson"]]})
tm = []
for s in teams[:3]:
    tm.append(dict(s, stats={"PTS": {"v": 118.2, "r": 3}, "REB": {"v": 44.1, "r": 14}, "AST": {"v": 26.0, "r": 27}}, opp={"OPP_PTS": {"v": 109.4, "r": 4}},
                   players=[dict(top[i], name=names[i], salary=32_000_000 - i * 3_000_000, pos="G", ht="6-5", wt=205, contract_end="2029") for i in range(8)],
                   picks={"tradable": [{"year": 2028, "round": 1, "from": "own"}], "locked": [{"year": 2027, "round": 1, "from": "own", "reason": "Stepien rule"}]}))
w("teams", {"teams": tm, "source": "ESPN"})
w("contracts", {"players": [{"name": names[i], "team": "New York Knicks", "years": [{"y": "2026-27", "sal": 38e6, "ch": 38e6, "st": "GUARANTEED"}], "end": "2030", "option": "", "total": 150e6} for i in range(6)]})
w("cap", {"source": "HoopsMatic", "thresholds": {"season": "2026-27", "salary_cap": 164961000, "luxury_tax": 200428000, "first_apron": 209015000, "second_apron": 221686000},
          "teams": [{"team": t["name"], "payroll": 180e6, "cap_space": -15e6, "tax_room": 20e6, "first_apron_room": 29e6, "second_apron_room": 41e6, "status": "BELOW TAX", "exceptions": {"mle_type": "Non-taxpayer", "mle_left": 14e6, "bae": 5e6}, "tpes": []} for t in teams[:6]]})
print("fixtures written to", D)
