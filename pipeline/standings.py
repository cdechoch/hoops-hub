"""Conference standings with win and loss streaks and last 10 games. Runs on every tick."""
import re

import common as c

STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{id}/schedule"


def streak_value(text):
    """'W4' -> 4, 'L2' -> -2, anything else -> 0."""
    m = re.match(r"\s*([WL])\s*(\d+)", str(text or ""), re.I)
    if not m:
        return 0
    return int(m.group(2)) * (1 if m.group(1).upper() == "W" else -1)


def record_wins(text):
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)", str(text or ""))
    return int(m.group(1)) if m else None


def parse(data):
    out = []
    for conf in (data or {}).get("children", []):
        conf_name = conf.get("name", "").replace(" Conference", "")
        for e in conf.get("standings", {}).get("entries", []):
            stats = {}
            for s in e.get("stats", []):
                val = s.get("displayValue", "")
                for k in (s.get("name"), s.get("shortDisplayName"), s.get("displayName"), s.get("abbreviation")):
                    if k:
                        stats[str(k).lower().replace(" ", "")] = val
            t = e.get("team", {})
            logo = (t.get("logos") or [{}])[0].get("href", "")
            g = lambda *keys: next((stats[k] for k in keys if stats.get(k) not in (None, "")), "")
            row = {
                "id": str(t.get("id", "")), "name": t.get("displayName", ""), "abbr": t.get("abbreviation", ""), "logo": logo,
                "conf": conf_name,
                "w": g("wins", "w"), "l": g("losses", "l"), "pct": g("winpercent", "pct", "winpct"),
                "gb": g("gamesbehind", "gb"), "seed": g("playoffseed", "seed"),
                "streak": g("streak", "strk"), "home": g("home"), "away": g("road", "away"),
                "l10": g("lasttengames", "l10", "lastten"),
                "diff": g("differential", "pointdifferential", "diff"),
                "ppg": g("avgpointsfor", "pointspergame"), "oppg": g("avgpointsagainst", "oppointspergame"),
            }
            out.append(row)
    return out


def form_from_schedule(team_id):
    """Last 10 record and current streak from a team's completed games, used when standings lack them."""
    data = c.get_json(SCHEDULE.format(id=team_id))
    results = []
    for ev in (data or {}).get("events", []):
        for comp in ev.get("competitions", []):
            if not comp.get("status", {}).get("type", {}).get("completed"):
                continue
            for team in comp.get("competitors", []):
                if str(team.get("team", {}).get("id", team.get("id", ""))) == str(team_id) or str(team.get("id", "")) == str(team_id):
                    results.append((ev.get("date", ""), bool(team.get("winner"))))
    results.sort()
    if not results:
        return None
    last10 = results[-10:]
    wins = sum(1 for _, w in last10 if w)
    n, cur = 0, results[-1][1]
    for _, w in reversed(results):
        if w != cur:
            break
        n += 1
    return {"l10": f"{wins}-{len(last10) - wins}", "streak": f'{"W" if cur else "L"}{n}'}


def build():
    rows = parse(c.get_json(STANDINGS))
    for r in rows:
        if (not r["streak"] or not r["l10"]) and r["id"]:
            form = form_from_schedule(r["id"])
            if form:
                r["streak"] = r["streak"] or form["streak"]
                r["l10"] = r["l10"] or form["l10"]
        r["streakN"] = streak_value(r["streak"])
        r["l10w"] = record_wins(r["l10"])
    return rows


def sort_seed(rows):
    def key(r):
        seed = int(r["seed"]) if str(r["seed"]).isdigit() else 99
        pct = float(r["pct"]) if str(r["pct"]).replace(".", "", 1).isdigit() else 0.0
        return (r["conf"], seed, -pct)
    return sorted(rows, key=key)


def run():
    rows = build()
    if not rows:
        return
    c.write_data("standings", {"teams": sort_seed(rows)})


if __name__ == "__main__":
    run()
