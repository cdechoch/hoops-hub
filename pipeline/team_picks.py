"""Future draft picks by team (HoopsMatic's "NBA Future Draft Picks By Team" page).
Copy the page text into config/team_picks_raw.txt (see README) and this turns it into data/team_picks.json."""
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


def run():
    p = c.CONFIG / "team_picks_raw.txt"
    if not p.exists():
        print("team picks: config/team_picks_raw.txt not found, skipping")
        return False
    teams = parse(p.read_text(encoding="utf-8"))
    if not teams:
        print("team picks: nothing parsed from config/team_picks_raw.txt")
        return False
    c.write_data("team_picks", {"source": "HoopsMatic", "teams": teams})
    print(f"team picks: {len(teams)} teams")
    return True


if __name__ == "__main__":
    run()
