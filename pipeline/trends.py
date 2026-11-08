"""Which players and teams are trending in the last hour, 4 hours and 24 hours.

Signals: mentions in news headlines, Reddit post titles and comment counts, and Google Trends.
X and TikTok have no free public feeds, so they are not part of this score.
"""
from collections import defaultdict

import common as c

WINDOWS = {"1h": 1, "4h": 4, "24h": 24}


def entity_names():
    from nba_api.stats.static import players, teams

    ents = {}
    for t in teams.get_teams():
        ents[c.norm_name(t["full_name"])] = (t["full_name"], "team")
        ents[c.norm_name(t["nickname"])] = (t["full_name"], "team")
    for p in players.get_active_players():
        full = c.norm_name(p["full_name"])
        if len(full.split()) >= 2:
            ents[full] = (p["full_name"], "player")
    return ents


def google_trending():
    try:
        from pytrends.request import TrendReq

        py = TrendReq(hl="en-US", tz=300, timeout=(10, 25))
        df = py.trending_searches(pn="united_states")
        return [str(x) for x in df[0].tolist()][:30]
    except Exception:
        return []


def run():
    news = c.read_data("news", {"items": []})["items"]
    ents = entity_names()
    keys = sorted(ents, key=len, reverse=True)
    google = google_trending()
    google_norm = [c.norm_name(g) for g in google]
    now = c.now()
    result = {}
    for label, hours in WINDOWS.items():
        agg = defaultdict(lambda: {"news": 0, "reddit": 0, "trends": 0, "score": 0.0})
        for it in news:
            pub = c.parse_iso(it["published"])
            if not pub or (now - pub).total_seconds() > hours * 3600:
                continue
            text = " " + c.norm_name(it["title"]) + " "
            matched = set()
            for k in keys:
                if f" {k} " in text:
                    matched.add(ents[k])
            for name, kind in matched:
                a = agg[(name, kind)]
                if it["source"] == "Reddit":
                    a["reddit"] += 1
                    a["score"] += 1 + it["engage"] / 200.0
                else:
                    a["news"] += 1
                    a["score"] += 1.5
        for (name, kind), a in agg.items():
            n = c.norm_name(name)
            if any(n in g or g in n for g in google_norm if g):
                a["trends"] = 1
                a["score"] += 5
        rows = [
            {"name": n, "kind": k, "news": a["news"], "reddit": a["reddit"], "trends": a["trends"], "score": round(a["score"], 1)}
            for (n, k), a in agg.items()
        ]
        rows.sort(key=lambda r: r["score"], reverse=True)
        result[label] = rows[:25]
    if not any(result.values()) and c.read_data("trends"):
        return
    c.write_data("trends", {"windows": result, "google": google})

    top = result["1h"][:1]
    prev = c.read_state("prev_trend", "")
    if top and top[0]["name"] != prev and top[0]["score"] >= 8:
        c.notify("Trending now", f'{top[0]["name"]} is the hottest name in the last hour', tags=["fire"])
    c.write_state("prev_trend", top[0]["name"] if top else "")


if __name__ == "__main__":
    run()
