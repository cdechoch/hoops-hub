"""Reads the text of hoopsmatic.com/contracts (select all on the page, copy, paste into config/contracts_raw.txt).
The site's data feed refuses GitHub's servers, so this is the reliable way to get every column the page shows."""
import re

import common as c

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE = re.compile(rf"^({MONTHS}) \d{{1,2}}, \d{{4}}$")
FIRST_SEASON = 2026  # the first salary column is 2026-27
SEASONS = [f"{FIRST_SEASON + i}-{str(FIRST_SEASON + i + 1)[-2:]}" for i in range(6)]
SEASON_END = lambda i: FIRST_SEASON + 1 + i  # calendar year in which season i ends


def money(text):
    m = re.match(r"^\$?([\d,]*\.?\d+)\s*([KM]?)", str(text or "").strip())
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return int(round(v * {"K": 1e3, "M": 1e6, "": 1}[m.group(2)]))


def year_cell(text):
    """('$13.1MTO') -> (13100000, 'TEAM OPTION'); '—' -> (None, '')."""
    t = text.strip()
    if not t or t == "—":
        return None, ""
    sal = money(t)
    tail = re.sub(r"^\$?[\d,]*\.?\d+[KM]?", "", t)
    if tail.startswith("TO"):
        return sal, "TEAM OPTION"
    if tail.startswith("PO"):
        return sal, "PLAYER OPTION"
    m = re.match(r"G:\s*(\$[\d,\.]+[KM]?)", tail)
    if m:
        g = money(m.group(1))
        return sal, "NON-GUARANTEED" if not g else "PARTIAL"
    return sal, "GUARANTEED"


def ext_info(text):
    first = (text or "").split("\n")[0].strip()
    dv = "Designated Veteran" in first
    first = first.replace("Designated Veteran", "").strip()
    if DATE.match(first):
        status = "future"
    elif first == "Eligible":
        status = "eligible"
    elif first == "Ineligible":
        status = "ineligible"
    elif first.startswith("Rookie"):
        status = "rookie"
    elif first.startswith("Standard") or first in ("N/A", ""):
        status = "na"
    else:
        status = "unknown"
    return {"status": status, "text": first or "-", "detail": "Designated Veteran eligible" if dv else "", "dv": dv}


def trade_info(text):
    t = (text or "").strip()
    if not t:
        return None
    if t == "Expiring":
        return {"type": "expiring", "text": "Expiring"}
    if t.startswith("No-Trade"):
        return {"type": "ntc", "text": "No-Trade Clause"}
    if DATE.match(t):
        return {"type": "restricted", "text": t, "detail": f"Cannot be traded until {t}"}
    return {"type": "restricted", "text": t}


def record_starts(lines):
    return [i for i in range(len(lines) - 3)
            if lines[i + 1] == "\t" and lines[i].strip() and not lines[i].startswith("\t")
            and lines[i + 2].strip() and not lines[i + 2].startswith("\t") and lines[i + 3].startswith("\t")]


def parse(text):
    lines = text.replace("\r", "").split("\n")
    starts = record_starts(lines)
    out = []
    for n, s in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        cells = "\n".join(lines[s + 3:end]).split("\t")[1:]
        if len(cells) < 18:
            continue
        years, holds, opt = [], {}, ""
        for i, raw in enumerate(cells[:6]):
            sal, st = year_cell(raw)
            years.append({"y": SEASONS[i], "sal": sal, "ch": sal, "st": st})
            if st in ("TEAM OPTION", "PLAYER OPTION") and not opt:
                opt = ("Team option " if st == "TEAM OPTION" else "Player option ") + SEASONS[i]
        for m in re.finditer(r"(\d{4})CH:\s*(\$[\d,\.]+[KM]?)", cells[6]):
            holds[int(m.group(1))] = money(m.group(2))
        for i, y in enumerate(years):
            if SEASON_END(i) in holds:
                y["ch"] = holds[SEASON_END(i)]
        live = [(i, y) for i, y in enumerate(years) if y["sal"]]
        if not live:
            continue
        last = live[-1][0]
        since = cells[12].strip()
        r = {
            "name": lines[s].strip(), "team": lines[s + 2].strip(),
            "years": [y for y in years if y["sal"] is not None],
            "total": money(cells[8]), "option": opt, "end": str(SEASON_END(last)),
            "signed": cells[10].strip(), "signed_by": cells[11].strip(), "exception": cells[9].strip(), "notes": "",
            "kicker": cells[13].strip(), "likely": cells[15].strip(), "unlikely": cells[16].strip(), "yos": "",
            "since": since, "ext": ext_info(cells[17]), "trade": trade_info(cells[14]), "dv": "Designated Veteran" in cells[17].split("\n")[0],
        }
        out.append(r)
    return out


def run():
    p = c.CONFIG / "contracts_raw.txt"
    if not p.exists():
        print("contracts page: config/contracts_raw.txt not found")
        return None
    players = parse(p.read_text(encoding="utf-8"))
    if not players:
        print("contracts page: nothing parsed from config/contracts_raw.txt")
        return None
    c.write_data("contracts", {"players": players, "source": "hoopsmatic.com/contracts"})
    c.write_state("salaries", {c.norm_name(r["name"]): r["years"][0]["sal"] for r in players})
    print(f"contracts page: {len(players)} players")
    return players


if __name__ == "__main__":
    run()
