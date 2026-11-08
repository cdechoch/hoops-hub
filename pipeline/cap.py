"""Team cap sheets from Spotrac, measured against the league thresholds in config/cap_thresholds.json."""
import io
import re

import pandas as pd

import common as c

SPOTROP = "https://www.spotrac.com/nba/cap/"
TEAM_URL = "https://www.spotrac.com/nba/{slug}/cap/"


def money(v):
    s = str(v).strip()
    neg = s.startswith("(") or s.startswith("-")
    digits = re.sub(r"[^0-9.]", "", s)
    if not digits:
        return None
    val = float(digits)
    mult = 1_000_000 if re.search(r"[mM]\b", s) else 1
    out = int(val * mult)
    return -out if neg else out


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def league_table(html):
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return []
    for t in tables:
        cols = [str(x).lower() for x in t.columns]
        tcol = next((i for i, x in enumerate(cols) if "team" in x), None)
        pcol = next((i for i, x in enumerate(cols) if "payroll" in x or "total cap" in x or "cap total" in x), None)
        if tcol is None or pcol is None:
            continue
        out = []
        for _, r in t.iterrows():
            name = re.sub(r"\s+", " ", str(r.iloc[tcol])).strip()
            payroll = money(r.iloc[pcol])
            if name and payroll and payroll > 1_000_000:
                out.append({"team": name, "payroll": payroll})
        if len(out) >= 25:
            return out
    return []


def team_exceptions(html):
    """Rows on a team cap page that mention an exception: type, amount, expiry, origin."""
    found = []
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return found
    for t in tables:
        flat = " ".join(str(x) for x in t.columns).lower()
        text = " ".join(t.astype(str).stack().tolist()).lower() if len(t) else ""
        if "exception" not in flat + text:
            continue
        for _, r in t.iterrows():
            cells = [re.sub(r"\s+", " ", str(v)).strip() for v in r.tolist() if str(v) != "nan"]
            if cells and any("exception" in x.lower() or "tpe" in x.lower() for x in cells + [flat]):
                found.append({"cells": cells})
    return found[:12]


def run():
    th = c.read_config("cap_thresholds.json", {})
    r = c.get(SPOTROP)
    rows = league_table(r.text) if r is not None else []
    if not rows:
        print("Spotrac league table not refreshed")
        return
    teams = []
    for row in rows:
        p = row["payroll"]
        team = {
            "team": row["team"],
            "payroll": p,
            "cap_space": th["salary_cap"] - p,
            "tax_room": th["luxury_tax"] - p,
            "first_apron_room": th["first_apron"] - p,
            "second_apron_room": th["second_apron"] - p,
            "status": "",
            "exceptions": {},
            "tpes": [],
            "raw_exceptions": [],
        }
        tr = c.get(TEAM_URL.format(slug=slugify(row["team"])))
        if tr is not None:
            team["raw_exceptions"] = team_exceptions(tr.text)
        teams.append(team)
    teams.sort(key=lambda t: t["payroll"], reverse=True)
    c.write_data("cap", {"source": "Spotrac", "thresholds": th, "teams": teams})


if __name__ == "__main__":
    run()
