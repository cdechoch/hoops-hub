"""Aggregate basketball news from many RSS feeds and Reddit, add a one sentence summary, and score how hot each story is."""
import difflib
import hashlib
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor

import feedparser
from bs4 import BeautifulSoup

import common as c

# kind "ball": the feed covers basketball only. kind "wide": a general sports feed, filtered to basketball.
FEEDS = {
    # Major basketball and NBA outlets
    "HoopsHype": ("https://hoopshype.com/feed/", "ball"),
    "HoopsHype News": ("https://news.google.com/rss/search?q=site:hoopshype.com&hl=en-US&gl=US&ceid=US:en", "ball"),
    "HoopsHype Rumors": ("https://feeds.hoopshype.com/xml/rumors.xml", "ball"),
    "HoopsRumors": ("https://www.hoopsrumors.com/feed", "ball"),
    "RealGM": ("https://basketball.realgm.com/rss/wiretap/0/0.xml", "ball"),
    "ESPN": ("https://www.espn.com/espn/rss/nba/news", "ball"),
    "ESPN College": ("https://www.espn.com/espn/rss/ncb/news", "ball"),
    "NBA.com": ("https://www.nba.com/rss/nba_rss.xml", "ball"),
    "SB Nation": ("https://www.sbnation.com/rss/nba/index.xml", "ball"),
    "SB Nation Partner": ("https://www.sbnation.com/rss/partner/sb-nation-nba/index.xml", "ball"),
    "ClutchPoints": ("https://clutchpoints.com/nba/feed", "ball"),
    "Sports Illustrated": ("https://www.si.com/rss/si_nba.rss", "ball"),
    "CBS Sports": ("https://www.cbssports.com/rss/headlines/nba/", "ball"),
    "CBS College": ("https://www.cbssports.com/rss/headlines/college-basketball/", "ball"),
    "Yahoo Sports": ("https://sports.yahoo.com/nba/rss/", "ball"),
    "Yahoo Sports News": ("https://sports.yahoo.com/nba/news/rss/", "ball"),
    "SLAM": ("https://www.slamonline.com/feed/", "ball"),
    "Basketball News": ("https://basketballnews.com/feed", "ball"),
    "Bleacher Report": ("https://bleacherreport.com/articles/feed?tag_id=19", "ball"),
    "The Athletic": ("https://theathletic.com/rss-feed/", "wide"),
    "New York Post": ("https://nypost.com/nba/feed/", "ball"),
    "NYT College Basketball": ("https://www.nytimes.com/athletic/rss/college-basketball/", "ball"),
    "BBC Basketball": ("https://feeds.bbci.co.uk/sport/basketball/rss.xml", "ball"),
    "Toronto Star": ("https://www.thestar.com/search/?f=rss&t=article&c=sports/basketball*&l=50&s=start_time&sd=desc", "ball"),
    "Basketball HOF": ("https://www.hoophall.com/news/feed", "ball"),
    # Analysis and rumors
    "Hoops Habit": ("https://hoopshabit.com/feed", "ball"),
    "NBA Analysis Network": ("https://nbaanalysis.net/feed", "ball"),
    "TalkBasket": ("https://www.talkbasket.net/feed", "ball"),
    "The Hoop Doctors": ("https://thehoopdoctors.com/feed", "ball"),
    "thePeachBasket": ("https://thepeachbasket.net/feed", "ball"),
    "Crisp Bounce Pass": ("https://crispbouncepass.com/feed", "ball"),
    "Inside Hoops": ("https://www.insidehoops.com/blog/feed", "ball"),
    "Basketball Insiders": ("https://www.basketballinsiders.com/feed/", "ball"),
    "The Sports Daily": ("https://thesportsdaily.com/category/nba/feed", "ball"),
    # Eastern Conference blogs
    "Posting and Toasting": ("https://www.postingandtoasting.com/rss/index.xml", "ball"),
    "KnickerBlogger": ("https://knickerblogger.net/feed", "ball"),
    "Raptors Republic": ("https://raptorsrepublic.com/feed", "ball"),
    "The Slipper Still Fits": ("https://www.slipperstillfits.com/rss/index.xml", "ball"),
    "CelticsBlog": ("https://www.celticsblog.com/rss/index.xml", "ball"),
    "The Sixer Sense": ("https://thesixersense.com/feed/", "ball"),
    "Raptors Cage": ("https://raptorscage.ca/feed", "ball"),
    # Western Conference blogs
    "Forum Blue and Gold": ("https://forumblueandgold.com/feed", "ball"),
    "Valley of the Suns": ("https://valleyofthesuns.com/feed", "ball"),
    "Project Spurs": ("https://projectspurs.com/feed", "ball"),
    "ClutchFans": ("https://clutchfans.net/feed", "ball"),
    "Daily Thunder": ("https://dailythunder.com/feed", "ball"),
    "Oklahoman Thunder": ("https://oklahoman.com/sports/thunder/rss", "ball"),
    "Dunking with Wolves": ("https://dunkingwithwolves.com/feed", "ball"),
    "The J Notes": ("https://thejnotes.com/feed", "ball"),
    "Pelican Debrief": ("https://pelicandebrief.com/feed", "ball"),
    # Draft
    "NBADraft.net": ("https://nbadraft.net/feed", "ball"),
    "NBA Draft Room": ("https://nbadraftroom.com/feed", "ball"),
    # International
    "Eurohoops": ("https://www.eurohoops.net/en/feed/", "ball"),
    "BallinEurope": ("https://feeds.feedburner.com/BiE", "ball"),
    "Sportando": ("https://sportando.basketball/feed", "ball"),
    "Blog de Basket": ("https://www.blogdebasket.com/en/feed", "ball"),
    "NBL": ("https://nbl.com.au/news/feed", "ball"),
    "NZ Herald": ("https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/sport/basketball/?outputType=xml", "ball"),
    "Basketball Australia": ("https://australia.basketball/news/feed", "ball"),
    "The Pick and Roll": ("https://pickandroll.com.au/feed", "ball"),
}
REDDIT = [("r/nba", "https://www.reddit.com/r/nba/hot.json"), ("r/nba new", "https://www.reddit.com/r/nba/new.json")]
STOP = set("the a an of to in for and on at with is as by from after will vs his her their says report reports".split())

TEAM_WORDS = (
    "hawks celtics nets hornets bulls cavaliers cavs mavericks mavs nuggets pistons warriors rockets pacers clippers lakers "
    "grizzlies heat bucks timberwolves wolves pelicans knicks thunder magic sixers 76ers suns blazers kings spurs raptors jazz wizards"
).split()
BALL = re.compile(r"\b(nba|basketball|hoops|g league|euroleague|wnba|march madness|ncaa tournament|college hoops|" + "|".join(TEAM_WORDS) + r")\b", re.I)
NOT_BALL = re.compile(r"\b(nfl|mlb|nhl|mls|premier league|quarterback|touchdown|pitcher|home run)\b", re.I)


def is_basketball(title, summary=""):
    text = f"{title} {summary}"
    return bool(BALL.search(text)) and not (NOT_BALL.search(text) and not re.search(r"\b(nba|basketball|hoops)\b", text, re.I))


def keywords(title):
    return {w for w in re.findall(r"[a-z0-9']+", title.lower()) if w not in STOP and len(w) > 2}


def item_id(url, title):
    return hashlib.sha1((url or title).encode()).hexdigest()[:12]


JUNK_TAIL = re.compile(r"(the post .*? appeared first on .*|read more.*|continue reading.*|click here.*|\[\s*(…|\.\.\.)\s*\])$", re.I)


def first_sentence(text, title="", limit=230):
    """One clean sentence from a feed blurb. Returns '' when the blurb adds nothing beyond the headline."""
    if not text:
        return ""
    text = BeautifulSoup(html.unescape(text), "lxml").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    text = JUNK_TAIL.sub("", text).strip()
    if len(text) < 40:
        return ""
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    sent = m.group(1) if m and len(m.group(1)) >= 40 else text
    if len(sent) > limit:
        sent = sent[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    if difflib.SequenceMatcher(None, sent.lower(), (title or "").lower()).ratio() > 0.8:
        return ""
    return sent


def entry_summary(e, title):
    candidates = [e.get("summary"), e.get("description")]
    for ct in e.get("content", []) or []:
        candidates.append(ct.get("value"))
    for cand in candidates:
        s = first_sentence(cand, title)
        if s:
            return s
    return ""


def fetch_feed(source, url, kind):
    r = c.get(url, timeout=12, retries=1)
    if r is None:
        return source, []
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries[:30]:
        title = re.sub(r"\s+", " ", html.unescape(e.get("title", ""))).strip()
        title = re.sub(r"\s+[-|]\s+(HoopsHype|hoopshype\.com)$", "", title)
        summary = entry_summary(e, title)
        if kind == "wide" and not is_basketball(title, summary):
            continue
        ts = e.get("published_parsed") or e.get("updated_parsed")
        published = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", ts) if ts else c.now_iso()
        items.append(
            {"id": item_id(e.get("link"), title), "title": title, "url": e.get("link", ""), "source": source,
             "published": published, "engage": 0, "summary": summary}
        )
    return source, items


def fetch_rss():
    out, ok = [], 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        for source, items in pool.map(lambda kv: fetch_feed(kv[0], kv[1][0], kv[1][1]), FEEDS.items()):
            if items:
                ok += 1
            out.extend(items)
    print(f"news: {ok} of {len(FEEDS)} feeds returned stories")
    return out


def fetch_reddit():
    items = []
    for label, url in REDDIT:
        data = c.get_json(url, params={"limit": 50, "raw_json": 1})
        for ch in ((data or {}).get("data", {}).get("children", [])):
            d = ch.get("data", {})
            if d.get("stickied"):
                continue
            published = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(d.get("created_utc", 0)))
            text = d.get("selftext", "")
            items.append(
                {"id": "r" + d.get("id", ""), "title": d.get("title", ""), "url": "https://www.reddit.com" + d.get("permalink", ""),
                 "source": "Reddit", "published": published, "engage": int(d.get("score", 0)) + 3 * int(d.get("num_comments", 0)),
                 "summary": first_sentence(text, d.get("title", ""))}
            )
    return items


def page_description(url):
    """Meta description of the article page, used when a feed gives no blurb."""
    r = c.get(url, timeout=8, retries=0)
    if r is None:
        return ""
    try:
        soup = BeautifulSoup(r.text[:200000], "lxml")
    except Exception:
        return ""
    for attrs in ({"property": "og:description"}, {"name": "description"}, {"name": "twitter:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"]
    return ""


def fill_summaries(items, limit=60):
    """Fetch missing summaries for the newest stories. Results are cached in state so each page is read once."""
    cache = c.read_state("summaries", {})
    for it in items:
        if not it.get("summary") and it["id"] in cache:
            it["summary"] = cache[it["id"]]
    need = [i for i in items if not i.get("summary") and i["url"] and i["id"] not in cache and i["source"] != "Reddit"][:limit]

    def work(it):
        return it["id"], first_sentence(page_description(it["url"]), it["title"])

    if need:
        with ThreadPoolExecutor(max_workers=10) as pool:
            for iid, text in pool.map(work, need):
                cache[iid] = text
        for it in items:
            if not it.get("summary") and cache.get(it["id"]):
                it["summary"] = cache[it["id"]]
    keep = {i["id"] for i in items}
    c.write_state("summaries", {k: v for k, v in cache.items() if k in keep or len(cache) < 800})


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
    unique = unique[:400]
    fill_summaries(unique[:80])

    old = c.read_state("seen_news", [])
    fresh = [i for i in unique if i["id"] not in old and i["hot"] >= 20][:3]
    for i in fresh:
        c.notify(f'Hot: {i["source"]}', i["title"], click=i["url"], tags=["newspaper"])
    c.write_state("seen_news", list({i["id"] for i in unique} | set(old))[-800:])
    c.write_data("news", {"items": unique})


if __name__ == "__main__":
    run()
