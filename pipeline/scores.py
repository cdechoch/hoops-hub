"""Live scores for NBA plus followed college teams (Kansas, Miami), with hot and cold players."""
import common as c

BASE = "https://site.api.espn.com/apis/site/v2/sports"
FEEDS = [
    ("NBA", f"{BASE}/basketball/nba/scoreboard", {}),
    ("KU/UM Basketball", f"{BASE}/basketball/mens-college-basketball/scoreboard", {"groups": 50, "limit": 400}),
    ("KU/UM Football", f"{BASE}/football/college-football/scoreboard", {"groups": 80, "limit": 400}),
]
FOLLOWED = {"Kansas Jayhawks": "ku", "Miami Hurricanes": "um"}


def _team(comp):
    t = comp.get("team", {})
    try:
        score = int(comp.get("score", 0) or 0)
    except ValueError:
        score = 0
    return {
        "name": t.get("displayName", ""),
        "abbr": t.get("abbreviation", ""),
        "logo": t.get("logo", ""),
        "score": score,
        "record": (comp.get("records") or [{}])[0].get("summary", ""),
        "winner": bool(comp.get("winner")),
    }


def parse_scoreboard(label, data):
    games = []
    for ev in (data or {}).get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        sides = comp.get("competitors", [])
        home = next((s for s in sides if s.get("homeAway") == "home"), None)
        away = next((s for s in sides if s.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        h, a = _team(home), _team(away)
        tags = [FOLLOWED[n] for n in (h["name"], a["name"]) if n in FOLLOWED]
        if label != "NBA" and not tags:
            continue
        st = ev.get("status", {})
        games.append(
            {
                "id": ev.get("id"),
                "league": label,
                "sport": "nba" if label == "NBA" else ("cfb" if "Football" in label else "cbb"),
                "state": st.get("type", {}).get("state", "pre"),
                "detail": st.get("type", {}).get("shortDetail", ""),
                "clock": st.get("displayClock", ""),
                "period": st.get("period", 0),
                "start": ev.get("date"),
                "home": h,
                "away": a,
                "followed": tags,
                "performers": [],
            }
        )
    return games


def game_score(p):
    """Hollinger game score from a box score line."""
    return (
        p["pts"] + 0.4 * p["fgm"] - 0.7 * p["fga"] - 0.4 * (p["fta"] - p["ftm"])
        + 0.7 * p["oreb"] + 0.3 * p["dreb"] + p["stl"] + 0.7 * p["ast"] + 0.7 * p["blk"]
        - 0.4 * p["pf"] - p["tov"]
    )


def _pair(v):
    try:
        m, a = str(v).split("-")
        return int(m), int(a)
    except ValueError:
        return 0, 0


def parse_boxscore(summary, abbr_by_team=None):
    """Return hot and cold performers from an ESPN NBA summary payload."""
    out = []
    for team in (summary or {}).get("boxscore", {}).get("players", []):
        abbr = team.get("team", {}).get("abbreviation", "")
        for block in team.get("statistics", []):
            labels = block.get("labels", [])
            for ath in block.get("athletes", []):
                st = ath.get("stats", [])
                if len(st) != len(labels) or not st:
                    continue
                d = dict(zip(labels, st))
                try:
                    mins = int(float(d.get("MIN", 0) or 0))
                except ValueError:
                    mins = 0
                if mins < 8:
                    continue
                fgm, fga = _pair(d.get("FG", "0-0"))
                ftm, fta = _pair(d.get("FT", "0-0"))
                tpm, tpa = _pair(d.get("3PT", "0-0"))
                num = lambda k: int(float(d.get(k, 0) or 0)) if str(d.get(k, "0")).lstrip("-").replace(".", "").isdigit() else 0
                p = {
                    "pts": num("PTS"), "reb": num("REB"), "ast": num("AST"), "stl": num("STL"),
                    "blk": num("BLK"), "tov": num("TO"), "pf": num("PF"), "oreb": num("OREB"),
                    "dreb": num("DREB"), "fgm": fgm, "fga": fga, "ftm": ftm, "fta": fta,
                }
                gs = game_score(p)
                line = f'{p["pts"]} pts, {p["reb"]} reb, {p["ast"]} ast on {fgm}-{fga} FG'
                out.append(
                    {
                        "name": ath.get("athlete", {}).get("displayName", ""),
                        "team": abbr, "line": line, "min": mins, "gs": round(gs, 1),
                    }
                )
    out.sort(key=lambda x: x["gs"], reverse=True)
    hot = [dict(x, tag="hot") for x in out if x["gs"] >= 18][:3]
    cold = [dict(x, tag="cold") for x in out if x["min"] >= 14 and x["gs"] <= 2][-3:]
    return hot + cold


def detect_events(games, prev):
    """Compare with the last run and return notification events."""
    events = []
    for g in games:
        old = prev.get(g["id"])
        names = f'{g["away"]["abbr"]} at {g["home"]["abbr"]}'
        score = f'{g["away"]["abbr"]} {g["away"]["score"]}, {g["home"]["abbr"]} {g["home"]["score"]}'
        if not old:
            if g["state"] == "in":
                events.append((f"Tipoff: {names}", score, g))
            continue
        if old["state"] == "pre" and g["state"] == "in":
            events.append((f"Starting now: {names}", g["league"], g))
        if old["state"] != "post" and g["state"] == "post":
            events.append((f"Final: {names}", score, g))
        if g["state"] == "in" and g["sport"] in ("nba", "cbb") and g["period"] >= 4:
            close = abs(g["home"]["score"] - g["away"]["score"]) <= 5
            if close and not old.get("close"):
                events.append((f"Close game: {names}", f'{score}, {g["detail"]}', g))
    return events


def run():
    games = []
    for label, url, params in FEEDS:
        games += parse_scoreboard(label, c.get_json(url, params=params))
    for g in games:
        if g["sport"] == "nba" and g["state"] in ("in", "post"):
            summ = c.get_json(f"{BASE}/basketball/nba/summary", params={"event": g["id"]})
            g["performers"] = parse_boxscore(summ)
    if not games and c.read_data("scores"):
        return  # keep last good data if the feeds failed
    prev = c.read_state("prev_scores", {})
    for title, body, g in detect_events(games, prev):
        prio = 4 if g["followed"] else 3
        c.notify(title, body, tags=["basketball" if g["sport"] != "cfb" else "football"], priority=prio)
    c.write_state(
        "prev_scores",
        {
            g["id"]: {
                "state": g["state"],
                "close": g["state"] == "in" and abs(g["home"]["score"] - g["away"]["score"]) <= 5 and g["period"] >= 4,
            }
            for g in games
        },
    )
    order = {"in": 0, "pre": 1, "post": 2}
    games.sort(key=lambda g: (0 if g["followed"] else 1, order.get(g["state"], 3), g["start"] or ""))
    c.write_data("scores", {"games": games})


if __name__ == "__main__":
    run()
