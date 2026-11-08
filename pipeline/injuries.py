"""League injury report by team with reported injury and expected return."""
import common as c
import hoopsmatic

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def parse(data):
    teams = []
    for t in (data or {}).get("injuries", []):
        players = []
        for inj in t.get("injuries", []):
            det = inj.get("details") or {}
            kind = " ".join(x for x in [det.get("side", ""), det.get("type", ""), det.get("detail", "")] if x).strip()
            note = inj.get("shortComment") or inj.get("longComment") or ""
            players.append(
                {
                    "name": inj.get("athlete", {}).get("displayName", ""),
                    "status": inj.get("status", ""),
                    "injury": kind or "Not specified",
                    "return": det.get("returnDate") or "",
                    "note": note,
                    "date": inj.get("date", ""),
                }
            )
        if players:
            teams.append({"team": t.get("displayName", ""), "players": players})
    teams.sort(key=lambda x: x["team"])
    return teams


def from_hoopsmatic():
    """Latest status per player from the HoopsHype injury feed, grouped by team via the contracts list."""
    contracts = c.read_data("contracts", {"players": []})["players"]
    team_of = {c.norm_name(p["name"]): p["team"] for p in contracts}
    cutoff = (c.now().timestamp() - 21 * 86400)
    by_team = {}
    for key, e in hoopsmatic.latest_injuries().items():
        status = e.get("status", "")
        d = c.parse_iso(e.get("date", "") + "T00:00:00+00:00")
        if status in ("Available", "") or key not in team_of or not d:
            continue
        if status != "Out" and d.timestamp() < cutoff:
            continue  # game day tags go stale; an Out stays until a newer entry replaces it
        by_team.setdefault(team_of[key], []).append(
            {"name": e["player"], "status": status, "injury": e.get("injury", "") or "Not specified", "return": "", "note": "", "date": e.get("date", "")}
        )
    return [{"team": t, "players": sorted(p, key=lambda x: x["name"])} for t, p in sorted(by_team.items())]


def merge_missing(teams, extra):
    """Add players that only the HoopsHype feed lists, so nobody is dropped."""
    have = {c.norm_name(p["name"]) for t in teams for p in t["players"]}
    by_name = {c.norm_name(t["team"]).split()[-1]: t for t in teams}
    for t in extra:
        key = c.norm_name(t["team"]).split()[-1]
        dest = by_name.get(key)
        for p in t["players"]:
            if c.norm_name(p["name"]) in have:
                continue
            if dest is None:
                dest = {"team": t["team"], "players": []}
                teams.append(dest)
                by_name[key] = dest
            dest["players"].append(p)
    teams.sort(key=lambda x: x["team"])
    return teams


def run():
    teams = parse(c.get_json(URL))
    try:
        extra = from_hoopsmatic()
    except Exception:
        extra = []
    teams = merge_missing(teams, extra) if teams else extra
    if not teams and c.read_data("injuries"):
        return
    c.write_data("injuries", {"teams": teams})


if __name__ == "__main__":
    run()
