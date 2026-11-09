"""Future draft picks by team (RealGM's "NBA Future Draft Picks By Team" page).
Copy the page text into config/team_picks_raw.txt (see README) and this turns it into data/team_picks.json."""
import csv
import io
import re

import common as c

HEADER = re.compile(r"^(.+?) Future NBA Draft Picks\s*$")
YEAR = re.compile(r"^(20\d\d)\s*$")
COUNT = re.compile(r"^\d+(\s*\+\s*\d+)?\s*$")


def items(lines):
    """Split the text lines of one cell into one entry per pick or condition (entries end with ';')."""
    out, cur = [], []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln == "---":
            if ln == "---" and cur:
                cur.append("|")
            continue
        cur.append(ln)
        if ln.endswith(";"):
            out.append(" ".join(cur).rstrip(";").strip())
            cur = []
    if cur:
        out.append(" ".join(cur).strip())
    return [x.replace(" | ", " Note: ").replace(" |", "").strip() for x in out if x]


def parse(text):
    """Returns {team: [{year, r1: {items, count}, r2: {items, count}}]}."""
    teams, team, year, buf = {}, None, None, []

    def close():
        nonlocal buf
        if team is None or year is None:
            buf = []
            return
        cells, cur = [], []
        for ln in buf:
            if COUNT.match(ln.strip() or "x"):
                cells.append({"items": items(cur), "count": re.sub(r"\s+", " ", ln.strip())})
                cur = []
            else:
                cur.append(ln)
        while len(cells) < 2:
            cells.append({"items": [], "count": "0"})
        teams[team].append({"year": int(year), "r1": cells[0], "r2": cells[1]})
        buf = []

    for raw in text.splitlines():
        ln = raw.strip()
        m = HEADER.match(ln)
        if m:
            close()
            team, year = m.group(1).strip(), None
            teams[team] = []
            continue
        if ln.lower().startswith("year") and "first round" in ln.lower():
            continue
        y = YEAR.match(ln)
        if y and team:
            close()
            year = y.group(1)
            continue
        if year and ln != "":
            buf.append(raw)
    close()
    return {t: v for t, v in teams.items() if v}


def parse_csv(text):
    """RealGM's export: a 'Team Future NBA Draft Picks' row, a Year row, then one row per year with each cell's last line as the pick count."""
    teams, team = {}, None

    def cell(raw):
        lines = [x.strip() for x in str(raw).split("\n")]
        lines = [x for x in lines if x != ""]
        count = "0"
        if lines and COUNT.match(lines[-1]):
            count = re.sub(r"\s+", " ", lines.pop())
        return {"items": items(lines), "count": count}

    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        m = HEADER.match(row[0].strip())
        if m:
            team = m.group(1).strip()
            teams[team] = []
            continue
        if team and YEAR.match(row[0].strip()) and len(row) >= 3:
            teams[team].append({"year": int(row[0]), "r1": cell(row[1]), "r2": cell(row[2])})
    return {t: v for t, v in teams.items() if v}


def run():
    csv_path = c.CONFIG / "team_picks.csv"
    if csv_path.exists():
        teams = parse_csv(csv_path.read_text(encoding="utf-8"))
        if teams:
            c.write_data("team_picks", {"source": "RealGM", "teams": teams})
            print(f"team picks: {len(teams)} teams")
            return True
    p = c.CONFIG / "team_picks_raw.txt"
    if not p.exists():
        print("team picks: config/team_picks_raw.txt not found, skipping")
        return False
    teams = parse(p.read_text(encoding="utf-8"))
    if not teams:
        print("team picks: nothing parsed from config/team_picks_raw.txt")
        return False
    c.write_data("team_picks", {"source": "RealGM", "teams": teams})
    print(f"team picks: {len(teams)} teams")
    return True


if __name__ == "__main__":
    run()
