"""Which draft picks each team can trade, using the Stepien rule and the seven year limit.

Input: config/picks.json, a map of team name to the picks it owns:
{"Miami Heat": [{"year": 2027, "round": 1, "from": "own", "protection": ""}, ...]}
Edit that file when trades happen. Picks are evaluated one at a time against the rule.
"""
import common as c


def evaluate_team(picks, cycle_year):
    window = list(range(cycle_year, cycle_year + 7))
    has_first = {y: any(p["round"] == 1 and p["year"] == y for p in picks) for y in window}
    tradable, locked = [], []
    for p in sorted(picks, key=lambda p: (p["year"], p["round"])):
        label = {"year": p["year"], "round": p["round"], "from": p.get("from", "own"), "protection": p.get("protection", "")}
        if p["year"] not in window:
            locked.append(dict(label, reason="More than seven drafts away"))
            continue
        if p["round"] == 1 and p.get("from", "own") == "own":
            test = dict(has_first)
            others = [q for q in picks if q["round"] == 1 and q["year"] == p["year"] and q is not p]
            test[p["year"]] = bool(others)
            bad = any(
                not test.get(y) and not test.get(y + 1, True) for y in window if y + 1 <= window[-1] + 1
            )
            if bad:
                locked.append(dict(label, reason="Stepien rule"))
                continue
        tradable.append(label)
    return {"tradable": tradable, "locked": locked}


def load_and_evaluate():
    owned = c.read_state("picks_owned", None) or c.read_config("picks.json", {})
    cycle = c.draft_cycle_year()
    return {team: evaluate_team(p, cycle) for team, p in owned.items() if isinstance(p, list)}
