"""Shared helpers for the Hoops Hub data pipeline."""
import datetime as dt
import json
import os
import pathlib
import re
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "data"
STATE = DATA / "_state"
CONFIG = ROOT / "config"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DATA.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)


def now():
    return dt.datetime.now(dt.timezone.utc)


def now_iso():
    return now().isoformat(timespec="seconds")


def get(url, params=None, timeout=25, retries=2, headers=None):
    """GET with small retry. Returns a Response or None."""
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(1.5 * (attempt + 1))
    return None


def get_json(url, params=None, **kw):
    r = get(url, params=params, **kw)
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def write_data(name, obj):
    obj = dict(obj)
    obj["updated"] = now_iso()
    (DATA / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def read_data(name, default=None):
    p = DATA / f"{name}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    return default


def write_state(name, obj):
    (STATE / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False))


def read_state(name, default=None):
    p = STATE / f"{name}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    return default


def read_config(name, default=None):
    p = CONFIG / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    return default


def notify(title, message, click=None, tags=None, priority=3):
    """Push through ntfy.sh. Needs the NTFY_TOPIC environment variable."""
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    body = {"topic": topic, "title": title, "message": message, "priority": priority}
    if click:
        body["click"] = click
    if tags:
        body["tags"] = tags
    try:
        r = requests.post("https://ntfy.sh/", json=body, timeout=15)
        return r.status_code == 200
    except requests.RequestException:
        return False


def season_end_year(today=None):
    """NBA season is labelled by the year it ends. Oct onward means next year."""
    today = today or now()
    return today.year + 1 if today.month >= 10 else today.year


def season_string(today=None):
    end = season_end_year(today)
    return f"{end - 1}-{str(end)[2:]}"


def draft_cycle_year(today=None):
    """Upcoming draft year. The cycle rolls over two weeks after a late June draft."""
    today = today or now()
    cutoff = dt.datetime(today.year, 7, 10, tzinfo=dt.timezone.utc)
    return today.year if today < cutoff else today.year + 1


def norm_name(s):
    s = re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("-", " "))
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
