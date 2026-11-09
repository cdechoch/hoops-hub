"""Rebuilds web/seed/draft.json (the board shown before the first live update) from the seed sources plus the Cyro and Mikey mocks."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import common as c, draft  # noqa: E402

path = ROOT / "web" / "seed" / "draft.json"
old = json.loads(path.read_text())
per = {}
profiles = draft.add_seed(per, old["cycle"])
draft.add_mocks(per, old["cycle"])
board = draft.aggregate(per, draft.CFG.get("weights", {}), draft.CFG)
by_key = {c.norm_name(p["name"]): p for p in old["players"]}
players = []
for i, e in enumerate(board, 1):
    o = by_key.get(e["key"], {})
    pr = o.get("profile") or {k: v for k, v in profiles.get(e["key"], {}).items() if k in ("pos", "school", "class", "height", "wingspan", "note")}
    players.append({"rank": i, "prev": None, "move": None, "name": e["name"], "avg": e["avg"], "ranks": e["ranks"], "profile": pr, "intel": o.get("intel", [])})
old.update(players=players, sources=list(per), mocks=c.read_config("cyro_mocks.json", {}))
path.write_text(json.dumps(old, separators=(",", ":")))
print(len(players), "prospects;", ", ".join(per))
