"""Aggregate big board for the upcoming draft cycle (top 150), refreshed weekly."""
import csv
import io
import re

import pandas as pd
from bs4 import BeautifulSoup

import common as c
import excel_import
import espn_stats

CFG = c.read_config("draft_sources.json", {})
PROFILE_FIELDS = {
    "pos": ("pos", "position"), "school": ("school", "team", "club"), "class": ("class", "yr", "year"),
    "height": ("ht", "height"), "weight": ("wt", "weight"), "hometown": ("hometown", "home town", "from"),
    "wingspan": ("wingspan", "ws"),
}


def table_players(html):
    """Largest table with a player or name column. Returns ordered rows with profile fields."""
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return []
    best = []
    for t in tables:
        cols = {str(x).lower(): x for x in t.columns}
        key = next((cols[k] for k in cols if "player" in k or k == "name"), None)
        if key is None:
            continue
        rows = []
        for _, r in t.iterrows():
            name = str(r[key]).strip()
            if not re.search(r"[A-Za-z]{2,} [A-Za-z]{2,}", name):
                continue
            row = {"name": name}
            for field, aliases in PROFILE_FIELDS.items():
                for a in aliases:
                    if a in cols and str(r[cols[a]]) not in ("nan", ""):
                        row[field] = str(r[cols[a]])
                        break
            rows.append(row)
        if len(rows) > len(best):
            best = rows
    return best


def link_players(html):
    """Fallback: ordered anchor text for links that look like player pages."""
    soup = BeautifulSoup(html, "lxml")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        if not re.search(r"/(players?|prospects?)/", a["href"]):
            continue
        name = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if re.fullmatch(r"[A-Za-z.'\- ]{5,40}", name) and " " in name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name})
    return out


def fetch_source(src):
    r = c.get(src["url"])
    rows = []
    if r is not None:
        rows = table_players(r.text) or link_players(r.text)
    manual = c.CONFIG / "manual_rankings" / f'{re.sub(r"[^a-z0-9]", "", src["name"].lower())}.csv'
    if not rows and manual.exists():
        rows = [{k: v for k, v in row.items() if v} for row in csv.DictReader(manual.open())]
    return rows[:150]


YT_LINE = re.compile(r"^\s*#?\s*(\d{1,3})\s*[.):\-]\s*([A-Za-z.'\- ]{4,40}?)(?:\s*[\-|,(–]\s*(.+?))?\)?\s*$")


def youtube_rankings(handle):
    """Latest mock draft found in the channel's video descriptions."""
    page = c.get(f"https://www.youtube.com/@{handle}")
    if page is None:
        return []
    m = re.search(r'"channelId":"(UC[\w-]{20,})"', page.text) or re.search(r"channel_id=(UC[\w-]{20,})", page.text)
    if not m:
        return []
    feed = c.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}")
    if feed is None:
        return []
    soup = BeautifulSoup(feed.text, "xml")
    year = str(c.draft_cycle_year())
    for entry in soup.find_all("entry"):
        title = entry.find("title").get_text() if entry.find("title") else ""
        desc = entry.find("media:description").get_text() if entry.find("media:description") else ""
        if "mock" not in title.lower() and "big board" not in title.lower() and "rank" not in title.lower():
            continue
        if year not in title and year not in desc:
            continue
        rows = []
        for line in desc.splitlines():
            mm = YT_LINE.match(line)
            if mm:
                rows.append({"name": mm.group(2).strip(), "school": (mm.group(3) or "").strip()})
        if len(rows) >= 10:
            return rows
    return []


def aggregate(per_source, weights, cfg):
    names = {}
    for src, rows in per_source.items():
        for i, row in enumerate(rows, 1):
            key = c.norm_name(row["name"])
            rank_val = row.get("rank", i)
            e = names.setdefault(key, {"name": row["name"], "ranks": {}, "profile": {}})
            e["ranks"][src] = rank_val
            for f in PROFILE_FIELDS:
                if row.get(f) and f not in e["profile"]:
                    e["profile"][f] = row[f]
    missing_rank, missing_w = cfg.get("missing_rank", 80), cfg.get("missing_weight", 0.5)
    scored = []
    for key, e in names.items():
        tot, wsum = 0.0, 0.0
        for src in per_source:
            if src in e["ranks"]:
                w = weights.get(src, cfg.get("default_weight", 1.0))
                tot += w * e["ranks"][src]
                wsum += w
            else:
                tot += missing_w * missing_rank
                wsum += missing_w
        e["avg"] = round(tot / wsum, 2)
        e["key"] = key
        scored.append(e)
    scored.sort(key=lambda e: (e["avg"], e["name"]))
    return scored[:150]


def hoopsmatic_is_current(hm, cycle):
    """HoopsMatic keeps last year's board up until it is rebuilt. If most of its top prospects were
    already drafted (per the workbook bio sheet), the board is for a past class and is skipped."""
    bio = excel_import.load_bio()
    top = hm.get("players", [])[:20]
    if not top:
        return False
    drafted = sum(1 for p in top if (bio.get(c.norm_name(p["name"]), {}).get("draft") or 9999) < cycle)
    return drafted <= len(top) // 4


def college_stats():
    """Current college per game stats by player name, from ESPN. Keeps last week's copy if ESPN fails."""
    try:
        pg, _ = espn_stats.fetch_players(c.season_end_year(), league="mens-college-basketball", max_pages=3)
        out = {}
        for _, r in pg.iterrows():
            key = c.norm_name(r["PLAYER_NAME"])
            if key in out and out[key]["gp"] >= int(r["GP"]):
                continue
            out[key] = {"gp": int(r["GP"]), "min": round(float(r["MIN"]), 1), "pts": round(float(r["PTS"]), 1),
                        "reb": round(float(r["REB"]), 1), "ast": round(float(r["AST"]), 1), "stl": round(float(r["STL"]), 1),
                        "blk": round(float(r["BLK"]), 1), "fg": round(float(r["FG_PCT"]) * 100, 1),
                        "tp": round(float(r["FG3_PCT"]) * 100, 1), "ft": round(float(r["FT_PCT"]) * 100, 1)}
        if out:
            c.write_state("college_stats", out)
            return out
    except Exception as exc:
        print("college stats unavailable:", exc)
    return c.read_state("college_stats", {})


def add_seed(per_source, cycle):
    """Starting board compiled from published mocks. Live sources replace it as they come in."""
    seed = c.read_config("draft_seed.json", {})
    if seed.get("cycle") != cycle:
        return {}
    stamp = c.parse_iso(seed.get("date", "") + "T00:00:00+00:00")
    age = (c.now() - stamp).days if stamp else 999
    live = len(per_source)
    for src, names in seed.get("sources", {}).items():
        if src in per_source or (live >= 3 and age > 28):
            continue
        per_source[src] = [{"name": n} for n in names]
    return {c.norm_name(k): v for k, v in seed.get("profiles", {}).items()}


MOCK_SOURCES = (("v1", "Cyro & Mikey Mock 1.0"), ("v2", "Cyro & Mikey Mock 2.0"))


def add_mocks(per_source, cycle):
    """Cyro Asseo and Mikey Visenberg's mock drafts count as two more sources in the consensus (pick number = rank)."""
    mocks = c.read_config("cyro_mocks.json", {})
    if mocks.get("cycle") != cycle:
        return
    for key, label in MOCK_SOURCES:
        picks = (mocks.get(key) or {}).get("picks")
        if picks:
            per_source[label] = [{"name": x["player"], "rank": x["pick"]} for x in sorted(picks, key=lambda x: x["pick"])]


def run():
    cycle = c.draft_cycle_year()
    per_source, hm_profiles = {}, {}
    hm = c.read_state("hm_draft", {})
    hm_used = bool(hm.get("players")) and hoopsmatic_is_current(hm, cycle)
    if hm_used:
        for src in hm["sources"]:
            rows = [{"name": p["name"], "rank": p["ranks"][src]} for p in hm["players"] if src in p["ranks"]]
            rows.sort(key=lambda r: r["rank"])
            if rows:
                per_source[src] = rows
        hm_profiles = {c.norm_name(p["name"]): p["profile"] for p in hm["players"]}
    else:
        for src in CFG.get("sources", []):
            rows = fetch_source(src)
            if rows:
                per_source[src["name"]] = rows
    yt = youtube_rankings(CFG.get("youtube_handle", "cyroasseo"))
    manual_cyro = c.CONFIG / "manual_rankings" / "cyroasseo.csv"
    if not yt and manual_cyro.exists():
        yt = [{k: v for k, v in r.items() if v} for r in csv.DictReader(manual_cyro.open())]
    if yt:
        per_source["Cyro Asseo"] = yt
    seed_profiles = add_seed(per_source, cycle)
    add_mocks(per_source, cycle)
    if not per_source:
        print("No draft sources returned data")
        return
    board = aggregate(per_source, CFG.get("weights", {}), CFG)

    state = c.read_state("draft_ranks", {})
    current = {e["key"]: i for i, e in enumerate(board, 1)}
    prev = state.get("prev", {})
    stamp = c.parse_iso(state.get("date")) if state.get("date") else None
    if state.get("cycle") != cycle:
        prev, stamp = {}, None
    if stamp is None or (c.now() - stamp).days >= 6:
        prev = state.get("current", {}) if state.get("cycle") == cycle else {}
        c.write_state("draft_ranks", {"cycle": cycle, "date": c.now_iso(), "prev": prev, "current": current})
    else:
        c.write_state("draft_ranks", {"cycle": cycle, "date": state["date"], "prev": prev, "current": current})

    profiles = c.read_config("prospect_profiles.json", {})
    combine = excel_import.load_combine()
    bio = excel_import.load_bio()
    news = c.read_data("news", {"items": []})["items"]
    college = college_stats()
    players = []
    for i, e in enumerate(board, 1):
        pr = dict(e["profile"])
        hp = hm_profiles.get(e["key"], {})
        for k_src, k_dst in (("pos", "pos"), ("school", "school"), ("country", "country"), ("age", "age")):
            if hp.get(k_src) and k_dst not in pr:
                pr[k_dst] = hp[k_src]
        b = bio.get(e["key"], {})
        for k_src, k_dst in (("ht", "height"), ("wt", "weight"), ("city", "hometown"), ("college", "school")):
            if b.get(k_src) and k_dst not in pr:
                pr[k_dst] = str(int(b[k_src])) if k_src == "wt" else b[k_src]
        cb = combine.get(e["key"])
        if cb:
            pr["combine"] = {k: v for k, v in cb.items() if k in ("year", "height_bare", "wingspan", "reach", "weight", "standing_vert", "max_vert", "lane", "sprint")}
        for k in ("pos", "school", "class", "height", "wingspan", "note"):
            v = seed_profiles.get(e["key"], {}).get(k)
            if v and k not in e["profile"]:
                pr[k] = v
        if college.get(e["key"]):
            pr["stats"] = college[e["key"]]
        pr.update(profiles.get(e["key"], {}))
        intel = [
            {"title": n["title"], "url": n["url"], "source": n["source"]}
            for n in news if e["key"] in c.norm_name(n["title"])
        ][:3]
        p0 = prev.get(e["key"])
        players.append(
            {
                "rank": i, "prev": p0, "move": (p0 - i) if p0 else None, "name": e["name"], "avg": e["avg"],
                "ranks": e["ranks"], "profile": pr, "intel": intel,
            }
        )
    c.write_data("draft", {"cycle": cycle, "label": f"{cycle} NBA Draft", "sources": list(per_source), "players": players,
                           "mocks": c.read_config("cyro_mocks.json", {}),
                           "hoopsmatic": "used" if hm_used else ("skipped, board is for a past class" if hm.get("players") else "unavailable")})


if __name__ == "__main__":
    run()
