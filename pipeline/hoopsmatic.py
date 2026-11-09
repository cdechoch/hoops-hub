"""Reads the data files that hoopsmatic.com publishes (contracts, roster and cap sheets, exceptions,
draft board, injuries) and turns them into the JSON the app uses.

If the site blocks the request, drop a saved copy of the file into config/hoopsmatic/ (same file name as
below) and the pipeline reads that instead. Set HOOPSMATIC_KEY to send an allowlist key as the
X-Hoops-Key header.
"""
import csv
import io
import os
import re

import common as c

BASE = "https://hoopsmatic.com/api/"
FILES = {
    "contracts": "contracts",
    "roster": "rm-roster",
    "exceptions": "rm-exceptions",
    "draft": "draft-csv",
    "holds": "rm-holds",
}
INJ_JSON = "https://raw.githubusercontent.com/aderoa/Injuries/main/injuries.json"


def fetch_csv(key):
    headers = {"Accept": "text/csv,*/*"}
    if os.environ.get("HOOPSMATIC_KEY"):
        headers["X-Hoops-Key"] = os.environ["HOOPSMATIC_KEY"]
    r = c.get(BASE + FILES[key], headers=headers, retries=1)
    text = r.text if r is not None and "," in r.text[:400] else None
    if text is None:
        local = c.CONFIG / "hoopsmatic" / f"{FILES[key]}.csv"
        if local.exists():
            text = local.read_text(encoding="utf-8")
    if text is None:
        return None
    return list(csv.reader(io.StringIO(text)))


def money(v):
    s = str(v or "").strip()
    if not s or s in ("-", "#N/A", "#REF!"):
        return None
    neg = "-" in s or s.startswith("(")
    digits = re.sub(r"[^0-9.]", "", s)
    if not digits:
        return None
    try:
        out = int(round(float(digits)))
    except ValueError:
        return None
    return -out if neg else out


def cell(row, i):
    return row[i].strip() if i < len(row) and row[i] is not None else ""


# ---------- contracts ----------
YEAR_COLS = [("2026-27", 10), ("2027-28", 13), ("2028-29", 16), ("2029-30", 19), ("2030-31", 22)]


def parse_contracts(rows):
    if not rows or len(rows) < 2:
        return []
    last = len(rows[0])
    out = []
    for r in rows[1:]:
        name = cell(r, 0)
        if not name or not cell(r, 2):
            continue
        years = []
        for label, i in YEAR_COLS + [("2031-32", last - 3)]:
            sal, status = money(cell(r, i + 1) or cell(r, i)), cell(r, i + 2)
            if sal:
                years.append({"y": label, "sal": sal, "ch": money(cell(r, i + 1)), "st": status})
        if not years:
            continue
        out.append(
            {
                "name": name, "team": cell(r, 2), "rat": cell(r, 3), "years": years,
                "total": money(cell(r, 28)), "option": cell(r, 26), "end": cell(r, 27),
                "signed": cell(r, 29), "signed_by": cell(r, 30), "exception": cell(r, 31), "notes": cell(r, 32),
                "kicker": cell(r, 33), "likely": cell(r, 34), "unlikely": cell(r, 35), "yos": cell(r, 38),
            }
        )
    return out


# ---------- roster and cap sheet ----------
def parse_roster(rows):
    """Team cap block (one row per team), trade exceptions, draft picks and player flags."""
    teams, tpes, picks, players = {}, [], [], {}
    for r in rows[1:]:
        t = cell(r, 34)
        if t and t not in teams:
            teams[t] = {
                "team": t, "salaries": money(cell(r, 35)), "cap_holds": money(cell(r, 36)), "dead_money": money(cell(r, 37)),
                "payroll": money(cell(r, 51)), "cap_space": money(cell(r, 52)), "tax_room": money(cell(r, 53)),
                "first_apron_room": money(cell(r, 54)), "hard_cap_first": cell(r, 55),
                "second_apron_room": money(cell(r, 56)), "hard_cap_second": cell(r, 57), "status": cell(r, 58),
                "players": cell(r, 42), "two_way": cell(r, 44),
            }
        if cell(r, 60) and money(cell(r, 62)):
            tpes.append({"team": cell(r, 60), "expires": cell(r, 61), "value": money(cell(r, 62))})
        if cell(r, 64) and cell(r, 66):
            picks.append(
                {"team": cell(r, 64), "round": cell(r, 65), "year": int(cell(r, 66)) if cell(r, 66).isdigit() else None,
                 "sure": cell(r, 67), "notes": cell(r, 68), "linked": cell(r, 69)}
            )
        name = cell(r, 0)
        if name and cell(r, 2):
            players[c.norm_name(name)] = {
                "headshot": cell(r, 25), "pos": cell(r, 26), "age": cell(r, 27), "gp": cell(r, 28),
                "out": cell(r, 22), "reason": cell(r, 23), "no_trade": cell(r, 12), "restrictions": cell(r, 13),
                "exception": cell(r, 20),
            }
    return {"teams": teams, "tpes": tpes, "picks": picks, "players": players}


def parse_exceptions(rows):
    out = {}
    for r in rows[1:]:
        team = cell(r, 0)
        if not team:
            continue
        used = []
        for p, a in ((5, 6), (7, 8)):
            if cell(r, p):
                used.append({"player": cell(r, p), "amount": money(cell(r, a))})
        out[team] = {
            "cap_space": money(cell(r, 1)), "tax_room": money(cell(r, 2)), "mle_type": cell(r, 3),
            "mle_left": money(cell(r, 4)), "mle_used_on": used, "bae": money(cell(r, 9)),
        }
    return out


def picks_for_rules(picks):
    """Convert the pick list into the shape picks.py evaluates, keyed by team."""
    out = {}
    for p in picks:
        if not p["year"]:
            continue
        rnd = 1 if p["round"].lower().startswith("1") else 2
        own = p["notes"].lower().startswith("own")
        out.setdefault(p["team"], []).append(
            {"year": p["year"], "round": rnd, "from": "own" if own else (p["notes"] or "other"), "protection": p["notes"]}
        )
    return out


# ---------- draft board ----------
def parse_draft(rows):
    if not rows or len(rows) < 2:
        return {"sources": [], "players": []}
    header = rows[0]
    src_idx = [(header[i].strip(), i) for i in range(2, 13) if i < len(header) and header[i].strip()]
    prof = {}
    for r in rows[1:]:
        n = cell(r, 26)
        if n:
            prof[c.norm_name(n)] = {
                "birth": cell(r, 27), "country": cell(r, 30), "age": cell(r, 34), "pos": cell(r, 36),
                "school": cell(r, 37), "entered": cell(r, 38), "combine": cell(r, 39),
            }
    players = []
    for r in rows[1:]:
        name, agg = cell(r, 0), cell(r, 1)
        if not name or not agg.isdigit():
            continue
        ranks = {s: int(cell(r, i)) for s, i in src_idx if cell(r, i).isdigit()}
        players.append({"name": name, "agg": int(agg), "ranks": ranks, "profile": prof.get(c.norm_name(name), {})})
    players.sort(key=lambda p: p["agg"])
    return {"sources": [s for s, _ in src_idx], "players": players}


# ---------- injuries ----------
def latest_injuries():
    data = c.get_json(INJ_JSON, retries=1)
    latest = {}
    for e in data or []:
        k = c.norm_name(e.get("player", ""))
        if k and e.get("date", "") >= latest.get(k, {}).get("date", ""):
            latest[k] = e
    return latest


# ---------- driver ----------
def run():
    contracts_rows = fetch_csv("contracts")
    roster_rows = fetch_csv("roster")
    exc_rows = fetch_csv("exceptions")
    draft_rows = fetch_csv("draft")

    if contracts_rows:
        contracts = parse_contracts(contracts_rows)
        if contracts:
            try:
                import contract_extras
                flags = {}
                if roster_rows:
                    flags = parse_roster(roster_rows)["players"]
                contract_extras.enrich(contracts, flags, draft_rows)
            except Exception as exc:  # extras are a bonus, the base table must still publish
                print("contract extras skipped:", exc)
            c.write_data("contracts", {"players": contracts})
            c.write_state("salaries", {c.norm_name(p["name"]): p["years"][0]["sal"] for p in contracts})
    if not contracts_rows:
        try:  # the data feed refuses GitHub's servers, so use the pasted copy of the contracts page
            import contracts_page
            contracts_page.run()
        except Exception as exc:
            print("contracts page skipped:", exc)
    if roster_rows:
        ros = parse_roster(roster_rows)
        c.write_state("roster_flags", ros["players"])
        c.write_state("picks_owned", picks_for_rules(ros["picks"]))
        exc = parse_exceptions(exc_rows) if exc_rows else {}
        teams = []
        for name, t in ros["teams"].items():
            e = exc.get(name, {})
            mine = [x for x in ros["tpes"] if x["team"] == name]
            teams.append(dict(t, exceptions=e, tpes=sorted(mine, key=lambda x: -x["value"])))
        if teams:
            c.write_data("cap", {"source": "HoopsMatic", "thresholds": c.read_config("cap_thresholds.json", {}), "teams": teams})
    if draft_rows:
        c.write_state("hm_draft", parse_draft(draft_rows))
    return bool(contracts_rows or roster_rows or (c.DATA / 'contracts.json').exists())


if __name__ == "__main__":
    print("hoopsmatic ok" if run() else "hoopsmatic unreachable, using fallbacks")
