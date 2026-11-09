"""Extra contract columns that hoopsmatic.com/contracts shows: years with the team, trade restriction,
extension eligibility (with Designated Veteran and rookie scale rules) and max contract percent.
The rules are ported from the page's own script so the app and the site agree."""
import datetime as dt
import re

import common as c

END_YEARS = [2026, 2027, 2028, 2029, 2030, 2031, 2032]
HIGHER_MAX = ["Defensive Player of the Year", "All-NBA First Team", "All-NBA Second Team", "All-NBA Third Team"]
DV_SHORT = {"Most Valuable Player": "MVP", "Defensive Player of the Year": "DPOY", "All-NBA First Team": "All-NBA 1st",
            "All-NBA Second Team": "All-NBA 2nd", "All-NBA Third Team": "All-NBA 3rd"}
TENURE_URLS = ["https://hoopsmatic.com/tenure_data.json", "https://jsierrahoopshype.github.io/Contracts/tenure_data.json"]
TENURE_ALIASES = {"nicolas claxton": "nic claxton", "santiago aldama": "santi aldama", "herb jones": "herbert jones", "cameron payne": "cam payne",
                  "sviatoslav mykhailiuk": "svi mykhailiuk", "carlton carrington": "bub carrington", "jeenathan williams": "nate williams",
                  "dennis schroeder": "dennis schroder", "david jones": "david jones-garcia"}


def key(name):
    s = re.sub(r"[^a-z0-9 ]", "", c.norm_name(name))
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s).strip()


def norm_status(raw):
    s = str(raw or "").upper().strip()
    if not s:
        return ""
    if "OPT" in s:
        return "PLAYER OPT" if "PLAYER" in s else "TEAM OPT"
    if "TWO" in s:
        return "TWO-WAY"
    if "10" in s and "DAY" in s:
        return "10-DAY"
    if "PARTIAL" in s:
        return "PARTIAL G"
    if s.startswith("NON"):
        return "NON-GUARANTEED"
    return "GUARANTEED" if "GUAR" in s else s


def fmt(d):
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def mdy(text):
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", str(text or ""))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def safe_date(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return dt.date(y, m, 28)


# ---------- feeds ----------
def load_tenure():
    for url in TENURE_URLS:
        data = c.get_json(url, retries=0)
        if isinstance(data, dict) and data.get("players"):
            return {key(n): v for n, v in data["players"].items()}, data.get("season", "")
    return {}, ""


def load_awards():
    """Awards from hoopsmatic's /api/awards sheet: {player key: [{award, year}]}."""
    import csv, io
    r = c.get("https://hoopsmatic.com/api/awards", retries=1)
    out = {}
    if r is None:
        return out
    for row in csv.reader(io.StringIO(r.text)):
        if len(row) > 5 and row[2] and row[3].isdigit() and row[5]:
            out.setdefault(key(row[5]), []).append({"award": row[2], "year": int(row[3])})
    return out


def draft_info(draft_rows):
    """{player key: (draft pick, draft year)} from the draft sheet's right-most PLAYER, DRAFT POS and DRAFT YEAR columns."""
    if not draft_rows:
        return {}
    hdr = [h.strip().upper() for h in draft_rows[0]]
    if "DRAFT POS" not in hdr:
        return {}
    di = len(hdr) - 1 - hdr[::-1].index("DRAFT POS")
    ni = next((k for k in range(di - 1, -1, -1) if hdr[k] == "PLAYER"), -1)
    yi = len(hdr) - 1 - hdr[::-1].index("DRAFT YEAR") if "DRAFT YEAR" in hdr else 61
    out = {}
    for r in draft_rows[1:]:
        if ni < 0 or len(r) <= max(ni, di):
            continue
        n = r[ni].strip()
        pick = int(r[di]) if r[di].strip().isdigit() else 0
        year = int(r[yi]) if yi < len(r) and r[yi].strip().isdigit() else 0
        if n and (pick or year):
            out[key(n)] = (pick, year)
    return out


# ---------- rules ----------
def higher_max(awards, ref):
    win = {ref, ref - 1, ref - 2}
    if any(a["award"] == "Most Valuable Player" and a["year"] in win for a in awards):
        return True
    seasons = {a["year"] for a in awards if a["award"] in HIGHER_MAX and a["year"] in win}
    return ref in seasons or len(seasons) >= 2


def max_pct(p):
    if p["dv"] or p["yos"] >= 10:
        return 35
    return 30 if p["yos"] >= 7 else 25


def dv_label(p):
    if not p["dv"] or not p["dv_awards"]:
        return ""
    items = ", ".join(f"{DV_SHORT.get(a['award'], a['award'])} '{str(a['year'])[-2:]}" for a in p["dv_awards"])
    return f" · Designated Veteran Eligible ({items})"


def guaranteed_end(p):
    last = -1
    for i in range(len(p["yrs"]) - 1, -1, -1):
        y = p["yrs"][i]
        if y["sal"] and y["st"] and y["st"] not in ("PLAYER OPT", "TEAM OPT"):
            last = i
            break
    return END_YEARS[last] if last >= 0 else None


def ext_elig(p, today):
    dv, pct = dv_label(p), f" · Max {max_pct(p)}%"
    notes = (p["notes"] or "").lower()
    out = lambda status, text, detail="": {"status": status, "text": text, "detail": detail, "dv": p["dv"]}
    if not p["team"]:
        return out("na", "Free Agent")
    if "two-way" in notes or all(y["st"] in ("TWO-WAY", "") for y in p["yrs"]):
        return out("na", "Standard Contract Conversion Eligible", "Two-Way Contract")
    if "10-day" in notes or all(y["st"] in ("10-DAY", "") for y in p["yrs"]):
        return out("na", "N/A", "10-Day")
    sig = mdy(p["sig"])
    try:
        end_year = int(p["end"])
    except ValueError:
        end_year = None

    def anniv_state(month, day, year, length, label):
        if length <= 2:
            return None
        wait = 2 if length <= 4 else 3
        when = safe_date(year + wait, month, day)
        return {"when": when, "text": fmt(when), "wait": wait, "elig": when <= today, "len": length}

    if "extension" in notes and "rookie scale" not in notes:
        if not sig or end_year is None:
            return out("extended", "Extended", p["notes"] + dv + pct)
        m, d, y = sig
        d = 1 if (m == 10 and d >= 2) else d
        total = end_year - (y + 1 if m >= 7 else y) + 1
        if total <= 2:
            return out("extended", "Extended", f"{p['notes']} · {total}-yr total, next ext. ineligible" + dv)
        st = anniv_state(m, d, y, total, "")
        if st["elig"]:
            return out("eligible", "Eligible", f"Extended ({p['notes']}) · Re-eligible since {st['text']}" + dv + pct)
        return out("future", st["text"], f"Extended ({p['notes']}) · {total}-yr total, {'2nd' if st['wait'] == 2 else '3rd'} anniv." + dv + pct)
    if "rookie scale" in notes:
        season_end = today.year + 1 if today.month >= 7 else today.year
        if end_year == season_end:
            return out("ineligible", "Ineligible", f"Expiring rookie scale (RFA {season_end})" + dv)
        designated = higher_max(p["awards"], p["recent"])
        label = "Des. Rookie Scale Ext. / Max (30%)" if designated else "Rookie Scale Ext. / Max (25%)"
        if p["draft_year"] > 0:
            elig, dead = dt.date(p["draft_year"] + 3, 7, 1), dt.date(p["draft_year"] + 4, 10, 21)
            if today >= dead:
                return out("ineligible", "Ineligible", f"Rookie scale window closed ({fmt(dead)})" + dv)
            if today >= elig:
                return out("eligible", label, f"Eligible since {fmt(elig)} · Deadline: {fmt(dead)}" + dv)
            return out("future", fmt(elig), f"Rookie scale · {label} · Window: {fmt(elig)} to {fmt(dead)}" + dv)
        return out("rookie", "Rookie Scale", label + dv)
    if not sig or end_year is None:
        return out("unknown", "-")
    m, d, y = sig
    d = 1 if (m == 10 and d >= 2) else d
    first_end = y + 1 if m >= 7 else y
    length = end_year - first_end + 1
    gend = guaranteed_end(p)
    has_opts = bool(gend and gend < end_year)
    guar_len = gend - first_end + 1 if has_opts else length
    full = anniv_state(m, d, y, length, "")
    if not has_opts:
        if full is None:
            return out("ineligible", "Ineligible", f"{length}-year deal" + dv)
        if full["elig"]:
            return out("eligible", "Eligible", f"Since {full['text']}" + dv + pct)
        return out("future", full["text"], f"{length}-year deal, {'2nd' if full['wait'] == 2 else '3rd'} anniv." + dv + pct)
    opt = "PO" if any(yy["st"] == "PLAYER OPT" for yy in p["yrs"]) else "TO"
    decl = anniv_state(m, d, y, guar_len, "")
    if full is None:
        if decl is None:
            return out("ineligible", "Ineligible", f"{length}-year deal · Also ineligible if {opt} declined" + dv)
        if decl["elig"]:
            return out("eligible", "Eligible", f"Ineligible if {opt} exercised ({length}-yr) · Eligible if declined ({guar_len}-yr, since {decl['text']})" + dv + pct)
        return out("future", decl["text"], f"Ineligible if {opt} exercised ({length}-yr) · If declined: {guar_len}-yr, eligible {decl['text']}" + dv + pct)
    note = ""
    if decl is None:
        note = f" · Ineligible if {opt} declined"
    elif decl["elig"] and (not full["elig"] or decl["when"] < full["when"]):
        note = f" · {'Already eligible' if not full['elig'] else 'Earlier'} if {opt} declined"
    elif not decl["elig"] and decl["when"] < full["when"]:
        note = f" · Earlier ({decl['text']}) if {opt} declined"
    if full["elig"]:
        return out("eligible", "Eligible", f"Since {full['text']}" + note + dv + pct)
    return out("future", full["text"], f"{length}-year deal, {'2nd' if full['wait'] == 2 else '3rd'} anniv." + note + dv + pct)


def restriction_date(text, today):
    s = str(text or "").strip()
    low = s.lower()
    for month, mi in (("dec", 12), ("jan", 1)):
        if re.search(rf"\b{month}(ember|uary)?\b", low) and re.search(r"\b15\b", low):
            d = dt.date(today.year, mi, 15)
            return d if d >= today else dt.date(today.year + 1, mi, 15)
    for f in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def trade_status(p, today):
    cutoff = dt.date(today.year, 4, 20)
    season_end = today.year + 1 if today.month >= 7 else today.year
    has_opts = any(y["sal"] and y["st"] in ("PLAYER OPT", "TEAM OPT") for y in p["yrs"])
    try:
        expiring = int(p["end"]) == season_end and not has_opts
    except ValueError:
        expiring = False
    if p["ntc"]:
        return {"type": "ntc", "text": "No-Trade Clause"}
    if expiring:
        return {"type": "expiring", "text": "Expiring"}
    rd = restriction_date(p["restriction"], today) if p["restriction"] else None
    if rd and rd > today and rd > cutoff:
        return {"type": "restricted", "text": fmt(rd), "detail": f"Cannot be traded until {fmt(rd)}"}
    sig = mdy(p["sig"])
    if sig:
        m, d, y = sig
        signed = safe_date(y, m, d)
        three = safe_date(y + (m + 2) // 12, (m + 2) % 12 + 1, d)
        if signed >= dt.date(2026, 6, 15):
            dec15 = dt.date(2026, 12, 15)
            elig = max(three, dec15)
            by_dec = elig == dec15
        else:
            elig, by_dec = three, False
        if elig > today and elig > cutoff:
            return {"type": "restricted", "text": fmt(elig),
                    "detail": f"Signed {p['sig']} · Tradeable {fmt(elig)} ({'Dec 15 rule' if by_dec else '3-month rule'})"}
    return None


def enrich(contracts, flags, draft_rows, today=None):
    """Adds since, trade, ext, dv and maxpct to each contract dict in place."""
    today = today or c.now().date()
    recent = c.season_end_year() - 1 if today.month >= 7 else c.season_end_year() - 1
    tenure, tenure_season = load_tenure()
    awards = load_awards()
    drafted = draft_info(draft_rows)
    for r in contracts:
        k = key(r["name"])
        by_label = {y["y"]: y for y in r["years"]}
        yrs = []
        for yr in END_YEARS:
            label = f"{yr}-{str(yr + 1)[-2:]}"
            y = by_label.get(label)
            yrs.append({"sal": y["sal"] if y else None, "st": norm_status(y["st"]) if y else ""})
        flag = flags.get(c.norm_name(r["name"]), {})
        aw = awards.get(k, [])
        win = {recent, recent - 1, recent - 2}
        pick, dyear = drafted.get(k, (0, 0))
        p = {"team": r["team"], "yrs": yrs, "notes": r["notes"], "sig": r["signed"], "end": r["end"], "draft_year": dyear, "awards": aw,
             "recent": recent, "yos": int(r["yos"]) if str(r["yos"]).isdigit() else 0,
             "dv_awards": [a for a in aw if a["award"] in DV_SHORT and a["year"] in win], "dv": higher_max(aw, recent),
             "ntc": flag.get("no_trade", ""), "restriction": flag.get("restrictions", "")}
        t = tenure.get(k) or tenure.get(TENURE_ALIASES.get(k, ""))
        if t:
            r["since"] = t.get("joined_season", "")
        elif mdy(r["signed"]):
            m, _, y = mdy(r["signed"])
            start = y if m >= 7 else y - 1
            r["since"] = f"{start}-{str(start + 1)[-2:]}"
        try:
            r["ext"] = ext_elig(p, today)
        except Exception as exc:  # one odd row must not hide the rest
            r["ext"] = {"status": "unknown", "text": "-", "detail": str(exc), "dv": False}
        r["trade"] = trade_status(p, today)
        r["dv"] = p["dv"]
        r["maxpct"] = max_pct(p)
        if pick:
            r["draft_pick"] = pick
        if dyear:
            r["draft_year"] = dyear
    return contracts
