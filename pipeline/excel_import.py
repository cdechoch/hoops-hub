"""One-off import of the HoopsHype All-Time Database workbook into compact JSON under config/db/.

Usage: python pipeline/excel_import.py path/to/All-Time_Database_2_0.xlsx
Re-run it whenever the workbook is updated and commit the JSON it writes.
"""
import datetime as dt
import json
import pathlib
import sys

import pandas as pd

import common as c

OUT = c.CONFIG / "db"


def clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) in ("nan", "NaT", "None", "#N/A", ""):
        return None
    return v


def height_from_excel(v):
    """The workbook stored heights like 6-9 as dates (2026-06-09). Month is feet, day is inches."""
    v = clean(v)
    if v is None:
        return None
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return f"{v.month}-{v.day}"
    s = str(v)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{int(s[5:7])}-{int(s[8:10])}"
    return s


def num(v):
    v = clean(v)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def date_str(v):
    v = clean(v)
    return str(v)[:10] if v is not None else None


def bio(path):
    df = pd.read_excel(path, sheet_name="Bio Data", header=0, engine="openpyxl")
    out = {}
    for _, r in df.iterrows():
        name = clean(r.get("PLAYER"))
        if not name:
            continue
        out[c.norm_name(str(name))] = {
            "name": str(name),
            "birth": date_str(r.get("BIRTHDAY")),
            "state": clean(r.get("BIRTH STATE / COUNTRY")),
            "city": clean(r.get("BIRTH CITY")),
            "nat": clean(r.get("NATIONALITY")),
            "pos": clean(r.get("POS")),
            "ht": height_from_excel(r.get("HEIGHT")),
            "wt": num(r.get("WEIGHT")),
            "college": clean(r.get("COLLEGE / TEAM")),
            "draft": num(r.get("DRAFT")),
            "pick": num(r.get("PICK")),
            "team": clean(r.get("TEAM")),
        }
    return {k: {a: b for a, b in v.items() if b is not None} for k, v in out.items()}


def combine(path):
    df = pd.read_excel(path, sheet_name="Combine", header=0, engine="openpyxl")
    df.columns = [str(x).replace("\xa0", " ").strip() for x in df.columns]
    out = {}
    for _, r in df.iterrows():
        name = clean(r.get("PLAYER"))
        year = num(r.get("YEAR"))
        if not name or year is None:
            continue
        key = c.norm_name(str(name))
        row = {
            "year": int(year), "pos": clean(r.get("POS")), "weight": num(r.get("WEIGHT (LBS)")),
            "height_shoes": num(r.get("HEIGHT")), "height_bare": clean(r.get("HEIGHT W/O SHOES")),
            "wingspan": clean(r.get("WINGSPAN")) if isinstance(clean(r.get("WINGSPAN")), str) else None,
            "reach": clean(r.get("STANDING REACH")), "hand": num(r.get("HAND SIZE")),
            "body_fat": num(r.get("BODY FAT %")), "lane": num(r.get("LANE AGILITY")),
            "shuttle": num(r.get("SHUTTLE RUN")), "sprint": num(r.get("3/4 SPRINT")),
            "standing_vert": num(r.get("STANDING VERT")), "max_vert": num(r.get("MAX VERT")),
        }
        row = {a: b for a, b in row.items() if b is not None}
        if key not in out or row["year"] >= out[key]["year"]:
            out[key] = row
    return out


def main(path):
    OUT.mkdir(parents=True, exist_ok=True)
    b = bio(path)
    cb = combine(path)
    (OUT / "bio.json").write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")))
    (OUT / "combine.json").write_text(json.dumps(cb, ensure_ascii=False, separators=(",", ":")))
    print(f"bio {len(b)} players, combine {len(cb)} players")


def load_bio():
    return c.read_config("db/bio.json", {})


def load_combine():
    return c.read_config("db/combine.json", {})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "All-Time_Database_2_0.xlsx")
