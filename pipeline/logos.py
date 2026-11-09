"""Team logo lookup tables, built from ESPN's team lists (NBA and men's college basketball).
Keys are lowercase letters and digits only, so "LA Clippers", "la-clippers" and "LAC" all find the same file."""
import re

import common as c

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams"


def key(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def teams_from(data):
    out = []
    for sport in (data or {}).get("sports", []):
        for lg in sport.get("leagues", []):
            for t in lg.get("teams", []):
                out.append(t.get("team", t))
    return out


def build(data):
    """Returns {key: logo url} for one league's ESPN team list."""
    m = {}
    for t in teams_from(data):
        logo = (t.get("logos") or [{}])[0].get("href", "")
        if not logo:
            continue
        for field in ("displayName", "shortDisplayName", "location", "abbreviation", "nickname", "name"):
            k = key(t.get(field))
            if k and k not in m:
                m[k] = logo
    return m


def run():
    nba = build(c.get_json(URL.format(league="nba"), params={"limit": 40}))
    col = build(c.get_json(URL.format(league="mens-college-basketball"), params={"limit": 500}))
    if not nba and not col:
        print("logos: ESPN unreachable, the app uses its built-in table")
        return False
    c.write_data("logos", {"nba": nba, "college": col})
    return True


if __name__ == "__main__":
    run()
