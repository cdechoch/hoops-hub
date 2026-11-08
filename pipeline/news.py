"""Aggregate NBA news from RSS and Reddit, then score how hot each story is."""
import hashlib
import re
import time

import feedparser

import common as c

FEEDS = {
    "HoopsHype": "https://hoopshype.com/feed/",
    "HoopsRumors": "https://www.hoopsrumors.com/feed",
    "RealGM": "https://basketball.realgm.com/rss/wiretap/0/0.xml",
    "ESPN": "https://www.espn.com/espn/rss/nba/news",
    "NBA.com": "https://www.nba.com/rss/nba_rss.xml",
    "Bleacher Report": "https://bleacherreport.com/articles/feed?tag_id=19",
}
REDDIT = [("r/nba", "https://www.reddit.com/r/nba/hot.json"), ("r/nba new", "https://www.reddit.com/r/nba/new.json")]
STOP = set("the a an of to in for and on at with is as by from after will vs his her their says report reports".split())


def keywords(title):
    return {w for w in re.findall(r"[a-z0-9']+", title.lower()) if w not in STOP and len(w) > 2}


def item_id(url, title):
    return hashlib.sha1((url or title).encode()).hexdigest()[:12]


def fetch_rss():
    items = []
    for source, url in FEEDS.items():
        r = c.get(url)
        if r is None:
            continue
        feed = feedparser.parse(r.content)
        for e in feed.entries[:40]:
            ts = e.get("published_parsed") or e.get("updated_parsed")
            published = (
                time.strftime("%Y-%m-%dT%H:%M:%S+00:00", ts) if ts else c.now_iso()
            )
            items.append(
                {
                    "id": item_id(e.get("link"), e.get("title", "")),
                    "title": re.sub(r"\s+", " ", e.get("title", "")).strip(),
                    "url": e.get("link", ""),
                    "source": source,
                    "published": published,
                    "engage": 0,
                }
            )
    return items


def fetch_reddit():
    items = []
    for label, url in REDDIT:
        data = c.get_json(url, params={"limit": 50, "raw_json": 1})
        for ch in ((data or {}).get("data", {}).get("children", [])):
            d = ch.get("data", {})
            if d.get("stickied"):
                continue
            published = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(d.get("created_utc", 0)))
            items.append(
                {
                    "id": "r" + d.get("id", ""),
                    "title": d.get("title", ""),
                    "url": "https://www.reddit.com" + d.get("permalink", ""),
                    "source": "Reddit",
                    "published": published,
                    "engage": int(d.get("score", 0)) + 3 * int(d.get("num_comments", 0)),
                }
            )
    return items


def score_items(items):
    """Hot score: engagement, plus how many outlets cover the same story, with a recency boost."""
    now = c.now()
    kws = [keywords(i["title"]) for i in items]
    for idx, it in enumerate(items):
        similar = set()
        for jdx, other in enumerate(items):
            if idx == jdx or it["source"] == other["source"]:
                continue
            inter = kws[idx] & kws[jdx]
            if len(inter) >= 3 and len(inter) / max(1, min(len(kws[idx]), len(kws[jdx]))) >= 0.5:
                similar.add(other["source"])
        it["outlets"] = len(similar) + 1
        pub = c.parse_iso(it["published"]) or now
        age_h = max(0.0, (now - pub).total_seconds() / 3600)
        recency = 1.0 / (1.0 + age_h / 6.0)
        it["hot"] = round((it["engage"] / 50.0 + 12 * len(similar) + 3) * recency, 2)
    return items


def run():
    items = fetch_rss() + fetch_reddit()
    if not items and c.read_data("news"):
        return
    seen, unique = set(), []
    for it in items:
        key = (it["url"] or it["title"]).split("?")[0]
        if key in seen or not it["title"]:
            continue
        seen.add(key)
        unique.append(it)
    cutoff = c.now().timestamp() - 48 * 3600
    unique = [i for i in unique if (c.parse_iso(i["published"]) or c.now()).timestamp() >= cutoff]
    unique = score_items(unique)
    unique.sort(key=lambda i: i["published"], reverse=True)

    old = c.read_state("seen_news", [])
    fresh = [i for i in unique if i["id"] not in old and i["hot"] >= 20][:3]
    for i in fresh:
        c.notify(f'Hot: {i["source"]}', i["title"], click=i["url"], tags=["newspaper"])
    c.write_state("seen_news", list({i["id"] for i in unique} | set(old))[-600:])
    c.write_data("news", {"items": unique[:300]})


if __name__ == "__main__":
    run()
